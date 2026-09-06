---
title: Agentic Customization Wizard
status: final
created: 2026-09-05
updated: 2026-09-06
---

# PRD: Agentic Customization Wizard

## 0. Document Purpose

For the team building this and for `bmad-create-epics-and-stories` downstream. Vocabulary is
fixed in §3 and used verbatim everywhere else; features are grouped in §4 with globally
numbered FRs nested under them; inferences are tagged `[ASSUMPTION]` inline and indexed in §12.

Built on the product brief at
`_bmad-output/planning-artifacts/briefs/brief-DjangoBackend-2026-08-24/` — brief plus addendum.
The brief carries the problem evidence and the rejected alternatives; this document does not
repeat them. The addendum carries the porting-defect checklist and interface detail that
architecture work will need.

Requirements here are grounded against code in this repository as of `3987c99`, not against a
described system.

## 1. Vision

GRM ships with no taxonomy. Every deployment defines its administrative levels, departments,
issue types, categories, statuses and routing rules through an eleven-section wizard that
blocks the application until it is finished. The wizard asks its operator to think in the
platform's data model. PIU staff think in their own grievance process, and the two do not
line up without a person from our team sitting in the room translating.

The result is a configuration that takes months to produce and that nobody can check. Some
PIUs have taken more than a year to go live, and their routing tables have never been
verified. When a category points at a department with nobody behind it, cases land unassigned
and no screen anywhere says so.

This work adds three things to the wizard: an assistant that asks about the grievance process
instead of the schema and proposes the configuration as a reviewable change set; assignment
that walks the region tree instead of demanding an exact match; and a Readiness Surface that
keeps answering "does every case have somewhere to go?" long after the wizard has closed. The
measure is not time saved filling forms. It is a deployment that can be signed off, and a
routing gap that shows up as a number instead of as a citizen whose complaint went nowhere.

## 2. Target User

### 2.1 Jobs To Be Done

- **Configure a deployment without needing our team on the call.** The PIU owns the grievance
  policy and is accountable for it; today they cannot express it in the wizard unaided.
- **Know whether the configuration is correct**, before go-live and continuously after.
- **Find out why a specific case is stuck**, and fix it in the same place.
- **Answer, unprompted, what happens to a case in a given category** — the test that the
  vocabulary gap has actually closed.

### 2.2 Non-Users (v1)

- **Citizens.** Never see the wizard or the Readiness Surface. They are affected by dead routes
  and are the reason this exists, but they are not users of it.
- **Facilitators and village secretaries.** Mobile and API only; no dashboard access.
- **Case managers**, for the readiness surface specifically — they work their own queue. The
  Readiness Surface is for whoever is accountable for the deployment.

### 2.3 Key User Journeys

- **UJ-1. Aminata configures the routing table without calling us.**
  Aminata runs the PIU. She has reached wizard step 6, Issue Categories, which is where every
  previous deployment stalled. Authenticated as `grm_owner`, wizard incomplete, dashboard
  still locked. She opens the assistant panel and describes, in French, what her programme
  actually handles — water access complaints go to the water directorate, land disputes go to
  a committee, both are handled at commune level, and anything about a minor is confidential.
  The assistant proposes eight categories as a change set: each one showing its subtype,
  department, confidentiality and redirection protocol, with a plain sentence underneath
  saying what will happen to a case. She corrects two of them inline, rejects one, approves
  the rest. **Climax:** the formset fills in with values she recognises as her own policy, and
  she clicks Save herself. **Resolution:** step 6 is complete, and the record shows she
  approved it, not us. **Edge case:** if her description is too thin to propose a department,
  the assistant says which fact it is missing rather than guessing.

- **UJ-2. Koffi finds out why a case has sat for six weeks.**
  Koffi is a GRM Manager, three months after go-live. The dashboard header shows a warning
  count of 12. He opens the unassigned queue, sorted by age. The oldest row is 43 days: a
  water access case in a commune, with the reason written next to it — no worker in the water
  department at that commune or any level above it. He clicks the row's second action, creates
  the worker for that cell, and the case is assigned on the next sweep along with four others
  waiting on the same gap. **Resolution:** the warning count drops to 7, and Koffi never had
  to know what `IssueDepartmentAdministrativeLevel` is.

- **UJ-3. The implementation lead signs off before go-live.**
  Before handover, the lead opens the coverage map. Departments run down the side,
  administrative levels across the top. Three cells are red. Two are real gaps the PIU has to
  staff; one is a category nobody will ever file under, which gets deleted instead. Nothing is
  blocked and nothing is forced — the lead accepts the remaining gap explicitly, and the
  acceptance is recorded against their name. **Resolution:** go-live happens with the gaps
  known rather than discovered later.

## 3. Glossary

Downstream work uses these terms exactly. No synonyms elsewhere in this document.

- **Assistant** — the conversational panel inside the wizard that elicits configuration in
  domain language and proposes it as a Change Set. Not "the agent", not "the bot".
- **Change Set** — a proposed configuration modification the Assistant produces: a set of
  field-level before/after values scoped to one Wizard Section, which an Approver accepts,
  edits or rejects. Never written without approval.
- **Approver** — the authenticated `grm_owner` or GRM Manager who accepts a Change Set. The
  only actor that causes a configuration write.
- **Wizard Section** — one of the eleven `WizardSection` rows (`project`,
  `administrative_levels`, `administrative_regions`, `departments`, `issue_types`,
  `categories`, `issue_status`, `citizen_age_groups`, `citizen_groups`, `components`,
  `summary`).
- **Routing Cell** — the pair (Department, Administrative Region) that determines who receives
  a case. A cell is *covered* when a `GovernmentWorker` exists for that department at that
  region or at any ancestor region up to the root.
- **Dead Route** — a Routing Cell reachable by at least one Issue Category that is not covered.
- **Health Check** — one named, deterministic query over configuration and staffing that
  returns pass or fail plus a Diagnosis. Computed on read, never stored.
- **Diagnosis** — the human-readable sentence a failing Health Check produces, naming the
  missing fact and the action that resolves it. Not an error code.
- **Readiness Surface** — the dashboard area holding the Coverage Map, the Unassigned Queue
  and the Warning Count. Reachable after the wizard completes.
- **Coverage Map** — Departments × Administrative Levels grid showing which Routing Cells are
  covered. Predictive: reads configuration and staffing, not Issues.
- **Unassigned Queue** — confirmed Issues with no assignee, each carrying a Diagnosis and an
  age.
- **Warning Count** — the persistent badge showing open Health Check failures.
- **LLM Provider** — a configured adapter supplying the Assistant's language model, following
  the same pattern as the notification providers in `src/integrations/providers/`.

## 4. Features

*Document order is not build order.* The dependency runs §4.5 → §4.2 → §4.3 → §4.4 → §4.1:
the assignment sweep must work before the retroactive drain in FR-23 means anything, climbing
assignment must land before Dead Route counts are meaningful, and the Assistant is last because
it is the largest piece and the only one that needs the others to be trustworthy. Story creation
should follow the dependency, not the headings.

### 4.1 Configuration Assistant

**Description:** A panel inside the wizard shell that elicits configuration in the language of
the grievance process and returns a Change Set for the current Wizard Section. It asks who
handles what, where, how long they get and what happens when they miss — never "choose a
redirection protocol". Every proposed value carries a one-sentence consequence in the same
language the Approver used. The Assistant never writes; approval routes through the wizard's
existing formset save path, so the commit surface does not change. Realizes UJ-1.

The UI stub for this panel already exists, commented out, in
`src/wizard/templates/wizard/grm_customization.html`. The wizard shell loads each step as an
AJAX fragment into `#formAjax`, so the panel lives alongside that fragment rather than
replacing it.

All eleven Wizard Sections get purpose-built elicitation in v1. There is no fallback tier: an
Assistant that helps for three steps and goes quiet for the rest reads as broken rather than
scoped, and the sections that look trivial are not uniformly so — the administrative level
structure is the most consequential decision in the wizard, and the resolution process asks for
escalation thresholds, which are policy questions in schema clothing.

**Functional Requirements:**

#### FR-1: Assistant panel in the wizard shell
An Approver can open an Assistant panel from any Wizard Section without leaving the step.
Realizes UJ-1.
**Consequences (testable):**
- The panel renders inside the existing two-pane shell and does not replace `#formAjax`.
- Closing the panel leaves the step's form state unchanged.
- The panel is unavailable once `WizardSection.wizard_setup_is_completed()` is true.

#### FR-2: Domain-language elicitation
The Assistant asks questions about the grievance process, not about the data model.
**Consequences (testable):**
- Each section's prompt inventory is reviewed against a banned-term list containing the
  schema nouns in §3; a prompt containing one fails review.
- When the Approver's answer is insufficient to propose a value, the Assistant names the
  missing fact rather than inventing one.

#### FR-3: Change Set proposal
The Assistant returns a Change Set: field-level before/after values scoped to one Wizard
Section. Realizes UJ-1.
**Consequences (testable):**
- Every proposed field shows current value and proposed value.
- A Change Set never spans more than one Wizard Section.
- An empty Change Set is a valid result and is reported as "nothing to change".

#### FR-4: Consequence explanation
Each proposed value carries a plain-language statement of its effect on a real case.
**Consequences (testable):**
- Every proposed Issue Category renders a sentence naming the department and region that
  would receive a case, and whether that Routing Cell is currently covered.
- Explanations use the Approver's session language.

#### FR-5: Approve, edit or reject
An Approver can accept a Change Set whole, edit any field before accepting, or reject it.
Realizes UJ-1.
**Consequences (testable):**
- Rejecting writes nothing and leaves the form untouched.
- Editing a field before approval records the edited value, not the proposed one.
- Approval populates the existing formset; the Approver still triggers the save.

#### FR-6: Approval provenance
Every approved Change Set is recorded with its Approver, timestamp, Wizard Section, the
proposed values and the values actually committed.
**Consequences (testable):**
- The record distinguishes proposed-and-accepted from proposed-and-edited.
- Records are queryable per Wizard Section and survive wizard completion.
- No configuration write attributable to the Assistant exists without a corresponding record.

#### FR-7: Pluggable LLM Provider
The Assistant's language model is supplied by a configured LLM Provider adapter.
**Consequences (testable):**
- Adding a provider requires no change to Assistant logic, matching the adapter pattern in
  `src/integrations/providers/`.
- With no provider configured, the wizard works exactly as it does today and the panel reports
  that the Assistant is unavailable.
- Provider credentials are read from settings, never stored in wizard models.

**Feature-specific NFRs:**
- A failed or slow provider call must never block the underlying form. Timeout degrades to the
  plain wizard.

### 4.2 Hierarchical Assignment

**Description:** `Issue.get_assignee` currently matches a `GovernmentWorker` on an exact
`administrative_region`, while `get_assignee_to_escalate` twelve lines below it climbs to the
root. A commune officer therefore does not receive a village case, though the same officer is
found the moment that case escalates. Making assignment climb collapses the Dead Route space
from categories × regions to categories × root-path. The governance decision this needed is
made: a case *is* handled at the nearest covering level above it.

**Functional Requirements:**

#### FR-8: Assignment climbs the region tree
When no `GovernmentWorker` exists for the category's department at the Issue's region,
assignment searches ancestor regions toward the root and assigns the nearest match.
**Consequences (testable):**
- An Issue in a village with no village-level worker is assigned to the commune-level worker
  of the same department.
- Search order is nearest-ancestor-first; the root is tried last.
- With no worker anywhere on the path, the Issue remains unassigned and appears in the
  Unassigned Queue with a Diagnosis naming the path searched.
- Existing exact-match behaviour is preserved when a worker does exist at the exact region.

#### FR-9: Resolution level is recorded
The administrative level that satisfied assignment is recorded on the Issue.
**Consequences (testable):**
- A case assigned by climbing is distinguishable from one assigned at its own level.
- The Coverage Map can report how many cells are covered only by an ancestor.

### 4.3 Configuration Health Checks

**Description:** Named, deterministic queries over configuration and staffing. Each returns
pass/fail and a Diagnosis naming the missing fact and its remedy. Computed on read — stored
results go stale and produce a green screen describing last month's staffing. These are
ordinary queries; their value is that nobody has written them.

**Functional Requirements:**

#### FR-10: Dead Route check
Reports every Issue Category whose Routing Cell is uncovered. Realizes UJ-3.
**Consequences (testable):**
- Coverage accounts for ancestor workers per FR-8.
- Diagnosis names the department, the region, and the fact that no worker exists on the path.

#### FR-11: Missing department head check
Reports every `IssueDepartment` used as an appeal department that has no `head`.
**Consequences (testable):**
- Fails for any department set as `assigned_appeal_department` on a category with `head` null.
- Diagnosis states that appeals for those categories will retry indefinitely without
  reassigning.

#### FR-12: Unreachable category check
Reports Issue Categories that cannot receive cases or have never received one.
**Consequences (testable):**
- Distinguishes structurally unreachable (no subtype parent, no department) from merely unused.
- Unused is reported as informational, not failure, before go-live.
- "Unused" is evaluated over a configured window, defaulting to since-go-live.

#### FR-13: Status and threshold structural check
Reports issue statuses whose thresholds are absent or whose semantic flags are unassigned.
Structural only — whether a threshold is *achievable* is out of scope, see §6.2.
**Consequences (testable):**
- Fails when the four semantic flags (`initial_status`, `open_status`, `rejected_status`,
  `final_status`) are not each assigned to exactly one status.
- Fails when an open-ended status has no `threshold_days`.

#### FR-14: Scheduler liveness check
Reports whether the background scheduler has run recently enough for configured behaviour to
be real.
**Consequences (testable):**
- Fails when no scheduled task has completed within a configured window.
- Diagnosis states which behaviours are inert while it fails: escalation, appeal routing,
  queued notifications, metric refresh.
- Liveness is read from a dedicated heartbeat task that writes a timestamp on each run. The
  timestamp advances only when beat fired *and* a worker executed the task, so the check
  catches a dead scheduler and a dead worker, which are separate failures.
- The check does not read `django_celery_results`: `CELERY_RESULT_BACKEND` is read from the
  environment and the deployment templates point it at Redis, so the installed `TaskResult`
  table is not populated (`src/grm/settings.py:240-242`).
- The check does not contact the broker during a web request.

#### FR-15: Checks compute on read
Health Check results are computed per request and never persisted.
**Consequences (testable):**
- No stored result is served.
- Two consecutive loads across a staffing change reflect the change without an intervening job.

### 4.4 Readiness Surface

**Description:** Where Health Check output becomes usable. Three views: the Coverage Map
(predictive, works before any case exists), the Unassigned Queue (reactive, what is stuck now
and why), and the Warning Count (the thing that makes someone look). Reachable after the
wizard completes and returns 404, so it needs its own route. Realizes UJ-2, UJ-3.

**Functional Requirements:**

#### FR-16: Coverage Map
Departments × Administrative Levels grid showing which Routing Cells are covered. Realizes UJ-3.
**Consequences (testable):**
- A cell covered only by an ancestor is visually distinct from one covered at its own level.
- Selecting a cell lists the categories routing through it.

#### FR-17: Unassigned Queue with Diagnosis
Lists confirmed Issues with no assignee, each with a Diagnosis and an age. Realizes UJ-2.
**Consequences (testable):**
- Default sort is oldest first.
- Every row carries a Diagnosis sentence, never a bare null or error code.
- The Diagnosis derives from the same rules as FR-8, so it cannot contradict actual assignment
  behaviour.

#### FR-18: Act from the row
Each Unassigned Queue row offers assigning a user directly, or creating the
`GovernmentWorker` for the Routing Cell. Realizes UJ-2.
**Consequences (testable):**
- Creating the worker for a cell resolves every queued Issue waiting on that cell, not only
  the row acted on.
- Both actions are permitted only to GRM Managers and `grm_owner`.

#### FR-19: Warning Count
A persistent count of open Health Check failures in the dashboard chrome, linking to the
Readiness Surface. Realizes UJ-2.
**Consequences (testable):**
- Visible on every dashboard page for users permitted to see it.
- Reflects current state per FR-15.

#### FR-20: Pre-completion forecast
The wizard Summary section shows the Coverage Map as a forecast.
**Consequences (testable):**
- Presented as a forecast, since no `GovernmentWorker` exists before the wizard completes.
- Does not block completion under any condition.

#### FR-21: Explicit gap acceptance
An Approver can accept a failing Health Check, recording who accepted it and when.
**Consequences (testable):**
- Accepted failures are visually separated from unaccepted ones, not hidden.
- Acceptance never suppresses a check from recomputing.

### 4.5 Assignment Pipeline Repair

**Description:** `check_issues` in `src/grm/tasks.py` uses single-underscore ORM lookups
(`internal_code_in`, `citizen_in`, `assignee_in`) where Django requires `__in`, and raises
`FieldError` on evaluation. It is the task that sets assignees, backfills internal codes and
anonymises citizen contact data, and it is the only cron wired on Vercel. Nothing else in this
PRD works while it is broken: the retroactive drain in UJ-2 is this task re-sweeping
assignee-null Issues, and it needs no new code — only a working query.

**Functional Requirements:**

#### FR-22: Repair the assignment sweep
`check_issues` completes without error and performs its three jobs.
**Consequences (testable):**
- The task runs to completion against a populated database.
- Confirmed Issues with a null assignee receive one where a covered Routing Cell exists.
- Issues in categories requiring anonymisation have contact data anonymised.
- Regression test coverage exists; there is none today.

#### FR-23: Retroactive drain
Issues that were unassignable when filed are assigned once their Routing Cell becomes covered.
Realizes UJ-2.
**Consequences (testable):**
- Creating a worker for a previously uncovered cell assigns the waiting Issues on the next
  sweep with no manual step.

**Notes:** `[NOTE FOR PM]` This defect reached this repository through the re-base in PR #5;
the code it replaced did not have it. The addendum's porting checklist holds the related
sweep for other single-underscore lookups, which has not been run.

## 5. Non-Goals (Explicit)

- **Not gating citizen intake.** Considered and rejected. Collecting a grievance matters even
  when nothing can route it. No Health Check failure ever blocks the intake API.
- **Not replacing the formsets.** The Assistant proposes; the existing forms commit.
- **Not a configuration editor after the wizard.** Post-wizard configuration changes stay in
  Django admin and the settings screens.
- **Not multi-tenancy.** One deployment per installation, unchanged.
- **Not interactive flow diagrams or role impersonation.** Adjacent workstreams in the
  upstream strategy docs.
- **Not collecting department heads in the wizard.** Staffing facts belong to the Readiness
  Surface, per the organising principle: the wizard configures taxonomy, the Readiness Surface
  handles people.

## 6. MVP Scope

### 6.1 In Scope

- Configuration Assistant with Change Set approval and provenance (§4.1)
- Hierarchical assignment (§4.2)
- The six Health Checks (§4.3)
- Coverage Map, Unassigned Queue, Warning Count, forecast, gap acceptance (§4.4)
- `check_issues` repair with regression coverage (§4.5)
- French and English. Both ship in v1 — the PIUs work in French, and French elicitation
  quality is what the feature is judged on, so English-only would be untestable against the
  real user.

A staged alternative was considered — ship the repair, climbing assignment and the Readiness
Surface first, and hold the Assistant for v2 on the grounds that the deterministic half helps an
existing deployment immediately while the Assistant is the largest and riskiest piece. It was
rejected: the deterministic half alone does not address the vocabulary gap, which is the stated
problem, and shipping verification without elicitation would leave PIUs exactly as dependent on
our team as they are today.

### 6.2 Out of Scope for MVP

- Configuration presets. Complementary and cheap, but they do not close the vocabulary gap.
  `[NOTE FOR PM]` worth revisiting as a fast follow; it is roughly a week.
- Region-granular Coverage Map. v1 is departments × levels; per-region needs a tree view.
- Removing `assigned_escalation_department`. Open question 3.
- Detecting unmeetable SLA thresholds — a threshold the department cannot actually meet, so
  everything escalates or nothing does. FR-13 catches only absent thresholds and unassigned
  status flags. Comparing configured `threshold_days` against observed time-in-status from
  `IssueStatusChange` needs post-go-live history, and belongs to a later Health Check rather
  than to configuration validation. `[NOTE FOR PM]` this is a real defect class from the brief,
  deferred rather than solved.
- Notifying anyone about Health Check failures. v1 is pull, not push.

## 7. Success Metrics

**Primary**
- **SM-1**: Defects found by running the Health Checks against an existing live configuration,
  before any of this ships. Baseline measurement. Validates FR-10 through FR-14. If it returns
  zero, the premise of this work is weaker than believed.
- **SM-2**: Dead Routes at go-live = 0, or every remaining one explicitly accepted per FR-21.
  Validates FR-10, FR-16, FR-21.
- **SM-3**: A PIU completes at least one Wizard Section with no one from our team present.
  Validates FR-1 through FR-5.

**Secondary**
- **SM-4**: Time from wizard start to sign-off, against a baseline of more than a year.
- **SM-5**: Age of the oldest Issue in the Unassigned Queue stays under an agreed threshold
  after go-live. Validates FR-17, FR-23 — and proves the surface is acted on rather than
  admired.
- **SM-6**: A PIU member can state, unprompted, what happens to a case in a given category.
  Validates FR-4.

**Counter-metrics (do not optimize)**
- **SM-C1**: Change Set edit rate. If Approvers accept everything verbatim, the approval step
  has become rubber-stamping and the audit trail in FR-6 records consent without review —
  functionally the direct-write model that was rejected. A healthy rate is well above zero.
  Counterbalances SM-3.
- **SM-C2**: Count of Health Checks disabled or permanently accepted. Driving the Warning
  Count to zero by accepting failures rather than fixing them satisfies SM-2 while leaving
  citizens exactly where they started. Counterbalances SM-2.
- **SM-C3**: Assistant conversation length. Optimizing for fewer turns produces confident
  proposals from thin input, which is the failure mode FR-2 exists to prevent.

## 8. Cross-Cutting NFRs

- **Availability degradation.** Every Assistant feature degrades to the current wizard. No LLM
  Provider, no network, or a provider timeout must leave a working form.
- **Health Check cost.** The Readiness Surface must remain responsive on deployments whose
  region tree runs to tens of thousands of rows, while still computing on read per FR-15. How
  that is achieved is an architecture decision; the addendum records what the existing code
  does and does not provide.
- **Permissions.** The Readiness Surface and its actions are limited to `grm_owner` and GRM
  Managers, consistent with the existing dashboard permission rules.
- **Localization.** All Assistant output, Diagnosis strings and Health Check names are
  translatable through the existing Django i18n setup.

## 9. Constraints and Guardrails

**Privacy and data governance.** What the Assistant sends to an LLM Provider divides in two,
and the two are not equivalent.

*Structured configuration* — department, category, administrative region and status names,
threshold numbers — is public administrative fact and may be sent to any configured provider.

*Free-text elicitation input* is treated as potentially sensitive. FR-2 asks the Approver to
describe their grievance process in their own words, and that input is unbounded: someone
explaining why they need a category will often explain it with a real case. Therefore:
- The input surface carries a visible instruction not to include case details, citizen names
  or incident specifics.
- Free-text input is used to produce the Change Set and is not retained afterwards. It is never
  written to the provenance record in FR-6, which stores field values only.
- A deployment that considers even structured configuration sensitive uses a self-hosted
  provider under FR-7.

Under no circumstances does the Assistant send Issue content, `Citizen` records, or contact
information. This matters more than usual here: `check_issues` performs the anonymisation and
has never run (FR-22), so citizen contact data is not currently in the state the configuration
claims it is.

**Cost.** At one or two deployments in 24 months, per-run LLM cost is not the constraint —
provider lock-in is. FR-7 exists so a deployment that cannot use a hosted provider is not
excluded from the feature.

**Safety.** The Assistant proposes configuration that routes real grievances. FR-5 and FR-6
exist so no configuration reaches production without a named human accepting it. The Assistant
holds no write path of its own.

## 10. Integration and Dependencies

- **Wizard shell** — the AJAX fragment loader in `wizard.js` and the two-pane template. The
  Assistant panel coexists with it.
- **Formsets** — `src/wizard/forms.py` remains the only configuration write path.
- **`Issue.get_assignee`** — modified by FR-8; `get_assignee_to_escalate` already implements
  the climb and is the reference.
- **Celery / `django_celery_beat`** — FR-14 adds a heartbeat task to the periodic schedule;
  FR-23 depends on the `check_issues` sweep actually running.
- **`src/integrations/providers/`** — the adapter pattern FR-7 follows.
- **Django i18n and locale middleware** — already present.

## 11. Open Questions

1. **Does time spent unassigned count against SLA?** The Issue sits in its initial status
   while nobody owns it, so `threshold_days` is burning. Probably correct, but it means Dead
   Routes quietly poison performance metrics, and the Coverage Map should show that.
2. **Remove `assigned_escalation_department`?** Collected by the categories section, never
   read by escalation code, carries `# TODO: Remove this field`. An Assistant that helps fill
   a field with no effect makes the problem worse.
3. **Is the type → subtype → category hierarchy necessary?** Part of the vocabulary gap may be
   a model one level deeper than the domain needs. Worth asking before building an Assistant
   to explain it.
4. **What is the Health Check window for FR-14?** Depends on the deployment's slowest periodic
   task.
5. **Does the Assistant see existing configuration from other sections?** Proposing categories
   is better with knowledge of the departments already defined, but it widens what is sent to
   the provider.

## 12. Assumptions Index

None outstanding. Every assumption the first draft carried was walked and closed on 2026-09-06.
Two were found to be factually wrong against the code rather than merely unconfirmed; the
corrections are recorded in §4.3 FR-14 (the result backend is Redis, so `TaskResult` is never
populated) and §8 (there is no ancestor CTE helper, only a descendant one). Decisions that
replaced the assumptions are stated where they apply rather than tagged.
