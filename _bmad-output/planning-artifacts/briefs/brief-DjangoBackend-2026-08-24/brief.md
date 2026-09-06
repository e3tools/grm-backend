---
title: "Product Brief: Agentic Customization Wizard (GRM)"
status: final
created: 2026-08-24
updated: 2026-08-29
---

# Product Brief: Agentic Customization Wizard

## Executive Summary

GRM ships with no taxonomy. Administrative levels, departments, issue types, categories,
statuses and routing rules are defined per deployment through an eleven-section wizard that
blocks the application until it is finished. The wizard asks the operator to work in the
platform's data model — type vs subtype vs category, department scoped to an administrative
level, redirection protocol — and assumes they understand it.

PIU staff do not. They know their own grievance process very well; they do not know how it
maps onto the schema. We have tried Word configuration forms and we have tried the wizard, and
the wizard was not understood even by the PIU's own developer. Every deployment therefore needs
human onboarding from our team and produces a configuration nobody can verify afterwards.
Some PIUs have taken more than a year to go live, and we still do not know whether their
routing tables are correct.

This feature replaces the form-first wizard with an agent that asks about the grievance process
in the PIU's own language, proposes the configuration, explains each choice in terms of what
will happen to a real case, and then surfaces — permanently, not just at launch — which parts
of the configuration have nobody behind them. The value is not saved keystrokes. It is a
deployment that can be signed off, and a routing gap that is visible as a number on a screen
instead of as a citizen whose complaint went nowhere.

## Where this gets built

This repository. The re-base that made that true is done and in review as
[PR #5](https://github.com/e3tools/grm-backend/pull/5): the 2023 CouchDB tree was replaced with
the upstream fork's `develop2`, so `src/wizard/` and `src/issues/` now exist here along with the
Postgres domain, the API and the Celery tasks.

That re-base was a filter, and it caught what it was looking for — personal data and credentials
were stripped before anything reached a public repo. It did not catch the `check_issues`
regression below, which came across intact, leaving the open-source repo momentarily less
correct than the code it replaced. That is this brief's argument in miniature: a defect
invisible until something queries for it, surviving review by people who were paying attention.

## The Problem

**The vocabulary gap.** The wizard's hardest steps — departments, types and subtypes, then the
category routing table — require the operator to hold the platform's model in their head. What
is a department *for*? What does "head of department" versus "person with fewest issues" do to
an actual case? Nothing in the wizard answers those questions, so we answer them, in meetings,
every deployment. Two previous attempts to close this with better forms did not work.

**Nobody can verify the output.** Testing a configuration by hand is slow and the failure mode
is silent. Confirmed defect classes:

| Defect | What happens |
|---|---|
| Dead route — no resolver | Category routes to a department/region with no `GovernmentWorker`. Cases land unassigned. |
| Appeal route dead by default | The wizard never sets `IssueDepartment.head`, but the hourly appeal job needs it. Appealed cases retry forever, silently, and appear in no interface. |
| Dead category | Category exists, no issue is ever filed under it. Noise in the reporter's dropdown. |
| Inert escalation config | Step 6 collects `assigned_escalation_department`; the escalation code never reads it. |
| Unmet SLA | Thresholds set to values the department cannot meet, so everything escalates or nothing does. |
| Assignment never runs | `check_issues` uses single-underscore ORM lookups (`assignee_in`) and raises `FieldError` every run. It sets assignees, backfills internal codes and anonymises citizen contact data, and is the only cron wired on Vercel. |
| Scheduler not running | Without the Celery containers, escalation, appeals, notifications and metrics all silently do nothing. A deployment fact that makes configured behaviour inert. |

**It is one-shot.** The wizard runs once per installation and then returns 404. Whatever comes
out of that room routes real grievances for the life of the deployment.

**And correctness decays.** A worker transfers out of a commune and every category routing
there goes dead. A department head's account is deleted and `on_delete=SET_NULL` nulls the
head, breaking appeals with no error anywhere. This is why the answer is a permanent health
check rather than a launch checklist — and it is what makes the work worth doing at one or two
deployments, because a launch gate is used twice while a health check is used every week for
years.

## The Solution

Three parts. The agent is the surface; the other two are what make it worth trusting.

**Elicitation.** A conversational panel inside the wizard that asks about the grievance process
rather than the schema: who handles what, where, how long they get, what happens when they miss.
It proposes a draft configuration and explains each choice as a consequence — "a health
complaint filed in Commune X goes to the health department at commune level; nobody is assigned
there yet." The admin edits and accepts, and the existing formsets stay as the commit surface,
so nothing is written that a human has not seen. The UI stub for this is already scaffolded and
commented out in the wizard template.

**Assignment that climbs.** `get_assignee` matches a worker on an *exact* region, while
`get_assignee_to_escalate` twelve lines away climbs to the root. So a commune officer does not
pick up a village case — but if that case escalates, the same officer is found. Making
assignment climb, as escalation already does, collapses the dead-route space from
categories × regions to categories × root-path. It is about a day of work and it shrinks the
problem the rest of the feature manages, so it comes first. The governance call this needed is
made: a village case *is* handled by the commune officer when no village officer exists.

**Warning, never blocking.** Citizen intake is never gated. Collecting the grievance matters
even when nothing can route it — an unassigned case is recorded, not lost, and once someone is
assigned to that cell the backlog drains on its own, because `check_issues` re-sweeps
assignee-null issues every five minutes. The retroactive unblock needs no new code. It needs
`check_issues` to work, which it currently does not.

This is the organising principle: **the wizard configures taxonomy, the readiness surface
handles people.** Departments, categories, statuses and regions are decided once. Who staffs
them, whether a department has a head, whether anyone covers a given region — those are
questions about people, they change after go-live, and they belong on a surface that keeps
watching. It is why the wizard does not collect department heads even though missing heads
break every appeal.

Three interfaces make the gap visible: a **coverage map** of departments × administrative
levels, showing where a case *would* land unassigned before any case does; an **unassigned
queue** where every row carries a diagnosis rather than a null flag ("no worker in Water at
Commune X or any ancestor") and two actions, assign someone now or create the worker for that cell; and a
**persistent warning count**, with a forecast version on the wizard Summary step. Severity is
**age**, not count — fifty issues filed this morning is normal, one that is sixty days old is
the failure.

## What Makes This Different

There is no technical moat and the brief should not claim one. The verification checks are
ordinary queries; their value is that nobody has written them. The agent's advantage is domain
knowledge — it knows this schema and its specific failure modes — and that we own both the
schema and the client relationship.

Two alternatives were considered and rejected as insufficient alone:

- **Configuration presets.** Cheaper and faster, but presets assume you already understand what
  you are choosing between. They do not close the vocabulary gap. Worth building as a
  complement, not a substitute.
- **Better documentation and training.** Already attempted twice. The Word configuration forms
  were exactly this, and they did not survive contact with a PIU.

## Who This Serves

**PIU staff running a deployment** — primary. They own the grievance policy and are accountable
for it. They are not developers, and the one developer they had could not use the wizard.
Success is finishing configuration without needing us on the call.

**Our implementation team** — secondary, and currently the workaround. We are the human
translation layer that makes the wizard usable. This feature exists to stop being it.

**Citizens** — never see the wizard, and absorb the cost of a dead route as a complaint nobody
answers.

## Success Criteria

- **Defects found by running the checks against a real configuration.** This is the baseline and
  is worth producing before anything is built. If it returns zero, the premise here is weaker
  than we think. An existing live deployment is the obvious candidate, where read access allows.
- Zero dead routes at go-live: every category has a reachable resolver, or the gap is
  documented and explicitly accepted.
- A PIU completes at least one wizard section without our team present.
- Time from wizard start to sign-off, against a baseline of more than a year.
- Oldest unassigned issue age stays under an agreed threshold after go-live — the measure that
  proves the health check is being acted on rather than admired.
- The PIU can state, unprompted, what happens to a case in a given category.

## Scope

**In:** the elicitation agent across the configuration sections; hierarchical assignment in
`get_assignee`; the coverage map, unassigned queue and warning count; diagnosis strings; the
agent explaining check failures in the same language it used to ask the questions.

**Out:** the re-base itself (done, PR #5); interactive flow diagrams and role
impersonation (adjacent, tracked in the upstream strategy docs); multi-tenancy; replacing the
formsets — the agent proposes, the forms still commit; gating citizen intake, explicitly
rejected.

## Open Questions

1. **Direct write or approvable diff?** Does the agent write to the wizard models, or produce a
   change set the admin approves? Decides the audit story.
2. **Does unassigned time count against SLA?** The issue sits in its initial status while
   nobody owns it, so `threshold_days` is burning. Probably correct, but it means dead cells
   quietly poison performance numbers and the coverage map has to show that.
3. **The inert escalation field.** Remove `assigned_escalation_department`, or keep collecting
   it? An agent that helps fill a field with no effect makes things worse, and the re-base
   carried the field across unchanged.
4. **LLM provider, cost per run, and data residency** for a government deployment.
5. **Language.** The PIUs we work with operate in French. The agent must elicit in French, and the
   quality of that conversation is the whole feature.
6. **Is the three-level type/subtype/category hierarchy necessary?** Part of the vocabulary gap
   may be a model one level deeper than the domain requires. Worth asking before building an
   agent to explain it.

## Vision

If this works, configuring a GRM deployment stops being a consulting engagement and becomes a
conversation the client can have on their own, ending in a configuration that shows, on one
screen, that every case has somewhere to go. That is the difference between a codebase another
country could fork and a product another country can adopt.
