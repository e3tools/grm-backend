# PRD Quality Review — Agentic Customization Wizard

## Overall verdict

The PRD has a real thesis and the features follow from it rather than being a wishlist with
headings. Every FR carries testable consequences, the counter-metrics do genuine work, and the
code references are grounded rather than described. Two things are at risk: one confirmed
defect class from the brief was quietly narrowed when it became an FR, and the feature order
runs opposite to the build order, so a team reading top-down starts with the riskiest and most
dependent piece.

## Decision-readiness — strong

Decisions are stated as decisions. The write model (approvable Change Set, §4.1 FR-5/FR-6),
the warn-never-block stance (§5), and the organising principle (§5, last bullet) are all
committed positions with their reasoning attached. Open Questions are genuinely open — none of
them answer themselves in the following sentence.

### Findings
- **medium** Scope decision not defended (§6.1) — "all four in v1" is presented as a list with
  no account of what phasing would have bought or cost. A reader who was not in the discovery
  conversation cannot see that a staged alternative was considered and rejected. *Fix:* one
  sentence in §6.1 naming the rejected alternative and the reason, or move the rationale to an
  addendum and reference it.

## Substance over theater — strong

No persona theater: three UJs, each producing requirements that appear in the FRs. No
innovation theater — the PRD makes no novelty claim, matching the brief's explicit refusal to
fabricate a moat. The NFRs in §8 are product-specific (degradation to the plain wizard, region
scale, existing permission rules) rather than "must be secure and scalable" boilerplate.

SM-C1 is the strongest content in the document: it identifies that an approval step everyone
rubber-stamps is functionally the direct-write model that was rejected, and makes that
measurable.

## Strategic coherence — strong

The thesis is explicit — configuration nobody can verify is the failure, not slow form-filling
— and the organising principle (taxonomy vs. people) is derived from it rather than asserted.
SM-1 is a falsification test that could invalidate the premise before build starts, which is
rare and worth keeping.

### Findings
- **medium** Feature order inverts build order (§4) — §4.5 (`check_issues` repair) is the
  prerequisite for FR-23's retroactive drain and therefore for the entire warn-never-block
  model, but it appears last. §4.1, the largest and most dependent feature, appears first.
  *Fix:* either reorder §4 to repair → climb → check → surface → assist, or add an explicit
  build-sequence note so downstream story creation does not follow document order.

## Done-ness clarity — adequate

Most FRs would tell an engineer what done means. Three do not.

### Findings
- **high** FR-13 narrows a confirmed defect class without saying so (§4.3) — the brief lists
  "Unmet SLA: thresholds set to values the department cannot meet, so everything escalates or
  nothing does." FR-13 tests only for *missing* thresholds and unassigned status flags. The
  harder half — comparing configured thresholds against observed resolution times — is dropped
  silently. Either the check covers it or §6.2 says it does not. *Fix:* add a consequence
  comparing `threshold_days` against historical time-in-status, or list unmeetable-threshold
  detection under Out of Scope with a reason.
- **medium** FR-2 has no mechanically verifiable consequence (§4.1) — "Prompts may not require
  the Approver to know Glossary or schema terms" is a judgment, not a test. *Fix:* make it a
  reviewable artifact ("the prompt inventory for each section is reviewed against a banned-term
  list that includes the schema nouns in §3").
- **low** FR-12 lacks a time window (§4.3) — "has never received one" cannot be evaluated
  without saying never-since-when. *Fix:* name the window or scope it to since-go-live.

## Scope honesty — strong

§5 does real work; the non-goals are the ones a developer would otherwise drift into,
particularly "not gating citizen intake" and "not collecting department heads." Deferred items
in §6.2 carry reasons rather than bare bullets.

Open-items density: 5 Open Questions + 5 indexed assumptions + 2 `[NOTE FOR PM]` = 12 on a
build-ready PRD. Moderate, not blocking. Two touch FRs directly (OQ-1 on SLA accounting, OQ-2
on the inert escalation field) and should be resolved before the stories that depend on them.

## Downstream usability — strong

Glossary is present and load-bearing, FR-1 through FR-23 are contiguous with no gaps and no
dangling references, UJ-1 through UJ-3 are all defined and all referenced, and every section
survives being pulled out on its own.

### Findings
- **low** Glossary drift (§1, §2.2) — "health surface" appears three times where the canonical
  term is "Readiness Surface". *Fix:* replace all three.

## Shape fit — strong

Brownfield internal tool feeding story creation. Three UJs across three distinct roles is
proportionate — not the UJ density that would be overhead for a single-operator tool, not the
absence that would under-serve a multi-role surface. Existing-code references were verified
against the working tree rather than described from memory, which is the bar for brownfield.

## Mechanical notes

- FR IDs: 1–23 contiguous, no duplicates, no unresolved references.
- UJ IDs: 1–3, all defined, all referenced, each with a named protagonist carrying context
  inline.
- SM IDs: SM-1–6 plus SM-C1–C3. Every counter-metric names what it counterbalances.
- Assumptions Index roundtrip: 5 inline tags, 5 index entries, matched.
- **low** §6.1 carries a bare `[ASSUMPTION]` with no inline text, unlike the other four which
  state their content inline. *Fix:* inline the assumption text.
- Vague-language sweep (gracefully / reasonable / user-friendly / robust / seamless): no hits.
