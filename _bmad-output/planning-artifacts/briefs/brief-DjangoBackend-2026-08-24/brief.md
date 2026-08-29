---
title: "Product Brief: Agentic Customization Wizard (GRM)"
status: draft
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
Benin has taken more than a year to go live and we still do not know whether its routing table
is correct.

This feature replaces the form-first wizard with an agent that asks about the grievance process
in the PIU's own language, proposes the configuration, explains each choice in terms of what
will happen to a real case, and then surfaces — permanently, not just at launch — which parts
of the configuration have nobody behind them. The value is not saved keystrokes. It is a
deployment that can be signed off, and a routing gap that is visible as a number on a screen
instead of as a citizen whose complaint went nowhere.

## Where this gets built

This is a prerequisite, not a detail. The agentic wizard is being built in
**GRMOpenSourceDjangoBackend**, which today is the 2023 open-source CouchDB codebase and has
neither a `wizard/` app nor an `issues/` app. The wizard, the Postgres domain it configures,
and the DRF API all live in the Benin fork, which is roughly three years and one datastore
migration ahead and is no longer a repo our team develops in.

The agreed direction is to **re-base this repository on the Benin code** — extract it, strip
client-specific content, keep this repo's identity — rather than forward-port a 2026 codebase
into a 2023 one. Extraction is subtraction; porting is re-implementation.

Two things follow. First, no part of this brief can start until the re-base does, and the
re-base is larger than the feature. Second, the re-base is the moment to *not* carry defects
across: the `check_issues` regression described below exists only in the Benin fork, and the
2023 base is clean. Porting is a filter, and we should use it as one.

Whether the client agreement permits this is an open question. It has not been verified.

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

**Elicitation.** A conversational panel inside the wizard that asks about the grievance process,
not the schema: who handles what, where, how long they get, what happens when they miss. It
proposes a draft configuration and explains each choice as a consequence — "a health complaint
filed in Commune X goes to the health department at commune level; nobody is assigned there
yet." The admin edits and accepts; the existing formsets stay as the commit surface, so nothing
is written that a human has not seen. The UI stub for this already exists, scaffolded and
commented out, in the Benin wizard template.

**Assignment that climbs.** Today `get_assignee` matches a worker on an *exact* region, while
`get_assignee_to_escalate` twelve lines away climbs the region tree to the root. So a commune
officer does not pick up a village case — but if that case escalates, the same officer is
found. Making assignment climb, like escalation already does, collapses the dead-route space
from categories × regions to categories × root-path. This is roughly a day of work and it
shrinks the problem the rest of the feature exists to manage, so it comes first.

It requires one governance decision, not a technical one: should a village case be handled by
the commune officer when no village officer exists? If the answer is no, this whole approach is
wrong and the dead-route surface stays large.

**Warning, never blocking.** Citizen intake is never gated. Collecting the grievance matters
even when nothing can route it yet — an unassigned case is recorded, not lost, and once someone
is assigned to that cell the backlog drains by itself, because `check_issues` re-sweeps
assignee-null issues every five minutes. That retroactive unblock needs no new code. It needs
`check_issues` to work, which in the Benin fork it does not.

Three interfaces make the gap visible:

1. **Coverage map** — departments × administrative levels, showing where a case *would* land
   unassigned before any case does. The only view that works during the wizard, since it reads
   configuration and staffing rather than issues.
2. **Unassigned queue** — every confirmed issue with no assignee, each row carrying a
   *diagnosis*, not a null flag: "no worker in Water at Zè or any ancestor", "category has no
   redirection protocol", "under appeal, Health has no head". Two actions per row: assign
   someone now, or create the worker for that cell, which fixes the row and every future case
   in it.
3. **A persistent warning count** in the dashboard chrome, and its forecast version on the
   wizard Summary step.

Severity is **age**, not count. Fifty unassigned issues filed this morning is normal; one that
is sixty days old is the failure.

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
  than we think. Benin is the obvious candidate if read access survives the handover.
- Zero dead routes at go-live: every category has a reachable resolver, or the gap is
  documented and explicitly accepted.
- A PIU completes at least one wizard section without our team present.
- Time from wizard start to sign-off, against a baseline of more than a year for Benin.
- Oldest unassigned issue age stays under an agreed threshold after go-live — the measure that
  proves the health check is being acted on rather than admired.
- The PIU can state, unprompted, what happens to a case in a given category.

## Scope

**In:** the elicitation agent across the configuration sections; hierarchical assignment in
`get_assignee`; the coverage map, unassigned queue and warning count; diagnosis strings; the
agent explaining check failures in the same language it used to ask the questions.

**Out:** the re-base itself (prerequisite, separate work); interactive flow diagrams and role
impersonation (adjacent, tracked in the Benin strategy docs); multi-tenancy; replacing the
formsets — the agent proposes, the forms still commit; gating citizen intake, explicitly
rejected.

## Open Questions

1. **Does the client agreement permit re-basing on the Benin code?** Not verified. It decides
   whether the plan of record is legal, so it is first.
2. **Should assignment climb the region tree?** A governance decision about where accountability
   sits. Everything in the warning surfaces is sized by the answer.
3. **Direct write or approvable diff?** Does the agent write to the wizard models, or produce a
   change set the admin approves? Decides the audit story.
4. **Does unassigned time count against SLA?** The issue sits in its initial status while
   nobody owns it, so `threshold_days` is burning. Probably correct, but it means dead cells
   quietly poison performance numbers and the coverage map has to show that.
5. **Should the wizard collect department heads?** A field in step 4 kills the appeal defect at
   its source and is smaller than any readiness work — but the head must be an existing user,
   which the wizard's own gating makes awkward.
6. **The inert escalation field.** Remove `assigned_escalation_department`, or keep collecting
   it? An agent that helps fill a field with no effect makes things worse. The re-base is the
   natural moment to drop it.
7. **LLM provider, cost per run, and data residency** for a government deployment.
8. **Language.** Benin's PIU works in French. The agent must elicit in French, and the quality
   of that conversation is the whole feature.
9. **Is the three-level type/subtype/category hierarchy necessary?** Part of the vocabulary gap
   may be a model one level deeper than the domain requires. Worth asking before building an
   agent to explain it.

## Vision

If this works, configuring a GRM deployment stops being a consulting engagement and becomes a
conversation the client can have on their own, ending in a configuration that shows, on one
screen, that every case has somewhere to go. That is the difference between a codebase another
country could fork and a product another country can adopt.
