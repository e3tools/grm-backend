---
title: "Addendum: Agentic Customization Wizard PRD"
status: final
created: 2026-09-05
updated: 2026-09-05
---

# Addendum

Options considered and mechanism detail. Belongs to architecture work, not the PRD.

## Agent write models considered

Three were on the table for how the Assistant reaches the database. FR-5 and FR-6 implement
the second.

| Model | What it does | Why not chosen |
|---|---|---|
| Propose into the form, human commits | Assistant pre-fills the existing formsets; the Approver clicks Save. No new write path, no new model. | Simplest, and it does satisfy "the forms still commit". Rejected because it leaves no record of what was proposed versus what was accepted — so there is no way to measure SM-C1, and no provenance for a configuration that routes real grievances. |
| **Approvable Change Set with provenance** | Assistant emits field-level before/after values; approval writes through the formset and records Approver, timestamp, proposed values and committed values. | **Chosen.** Costs a model and a diff view. Buys configuration provenance the wizard has never had, and makes rubber-stamping visible. |
| Direct write with undo | Assistant writes immediately; Approver can revert. | Fastest conversation, weakest accountability. Hard to defend in a government deployment, and it inverts the safety property that no configuration reaches production without a named human accepting it. |

Note the relationship between the first and second: they differ only in whether the proposal is
recorded. SM-C1 exists because an approval step that is always rubber-stamped collapses the
second into the first without anyone noticing.

## MVP staging alternative

Rejected in favour of shipping all four parts together. Summarised in §6.1 of the PRD; the
fuller argument:

The deterministic half — `check_issues` repair, hierarchical assignment, Health Checks and the
Readiness Surface — has a customer immediately, because an existing deployment's configuration
correctness is unknown today and these are ordinary queries. The Assistant helps the *next*
deployment, and there are one or two of those in 24 months.

That argues for staging. It was rejected because the vocabulary gap is the stated problem, and
verification without elicitation leaves PIUs exactly as dependent on our team as they are now —
it changes what we can see, not what they can do. The counter-consideration worth carrying into
planning: if the Assistant slips, the deterministic half should still ship rather than waiting.

## LLM Provider adapter shape

FR-7 follows the existing pattern in `src/integrations/providers/` (`twilio.py`,
`sendgrid.py`, `africas_talking.py`, `klaviyo.py`, `mailchimp.py`), with `NotificationProvider`
in `src/integrations/models.py` as the model precedent — a named provider row with a type
discriminator and per-provider capability flags.

Two settings paths already exist and are read with no defaults: `OPENAI_API_KEY` (used by the
AI-insight feature) and `HUGGINGFACE_API_KEY` plus `HUGGINGFACE_API_BASE_URL`, the latter
making a self-hosted endpoint plausible without new plumbing.

## Health Check computation

FR-15 requires computation on read, and §8 requires that to stay responsive on large region
trees. What the code currently provides shapes how to do that.

`AdministrativeRegion` has **one** recursive CTE helper, `get_descendant_ids`
(`src/issues/models.py:151`), which walks *down*. There is no ancestor helper. `get_assignee_to_escalate`
walks *up* using plain Python recursion — one query per level.

The obvious implementation of coverage is therefore also the expensive one: for each region,
climb to the root looking for a worker. That needs a helper that does not exist and costs
roughly regions × depth queries.

**Invert it.** A worker at region R covers R and every descendant of R. Coverage for a
department is the union of `get_descendant_ids(R)` across the regions where that department has
a worker. Workers number in the tens; regions in the thousands. Descending from the few is
cheaper than climbing from the many, and it uses the helper that already exists.

Keep this separate from FR-8. Climbing assignment genuinely walks up, but it does so for one
Issue at a time at assignment, which is what `get_assignee_to_escalate` already does at
acceptable cost. Same tree, opposite direction, different cost profile — they should not share
an implementation because they share a concept.

If compute-on-read still proves too slow, the fallback is a short-TTL cache invalidated on
`GovernmentWorker` writes — not a stored result table, which is what FR-15 exists to prevent.

## Known-defect context

The `check_issues` lookups repaired by FR-22 arrived in this repository through the re-base in
PR #5; the 2023 code they replaced used a well-formed CouchDB Mango selector. The brief's
addendum carries a porting checklist of related defects — dead branches in `get_assignee`
(a `confidentiality_level == "Confidential"` comparison that can never match, a hardcoded
`administrative_region=1`, a `print("not supposed to be here")` fallback), the step 9
`restricted_deletion` filter comparing a `CitizenGroup` pk against an age-group FK, and the
mandatory `COUCHDB_*` settings. None are in this PRD's scope; all are worth tickets.
