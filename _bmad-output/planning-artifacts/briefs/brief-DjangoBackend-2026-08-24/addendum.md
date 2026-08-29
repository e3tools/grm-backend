---
title: "Addendum: Agentic Customization Wizard"
status: draft
created: 2026-08-29
updated: 2026-08-29
---

# Addendum

Depth for the PRD and architecture work, not the brief.

## Repo survey

| Repo | Remote | Last commit | Wizard | Data layer |
|---|---|---|---|---|
| `GRMOpenSourceDjangoBackend` (target) | `github.com/e3tools/grm-backend` | 2023-05-26 | No | CouchDB |
| `grm-backend` | `gitlab.com/ecube3/grm-backend` | 2023-04-19 | No | CouchDB |
| `GRM-Web-App-Benin` (reference) | `github.com/Corasec/GRM-Web-App-Benin` | 2026-08-19 | Yes | Postgres |

The two grm-backend checkouts are the same 2023 open-source original. Neither has a `wizard/`
or `issues/` app. `grm-backend` carries `masterTogo`, `masterAws` and `develop_rwanda_mod`
branches, so it is the codebase that actually reached multiple countries — worth mining for
what those deployments needed, since it is the only evidence of the multi-country case.

Everything the brief describes about wizard mechanics, routing and assignment is read from the
Benin fork. It is reference material, not the target.

## Porting checklist — defects not to carry across

The re-base is a filter. These are known-bad in the Benin fork:

- **`check_issues` ORM lookups.** `grm/tasks.py:42,43,45` use single underscores
  (`internal_code_in`, `citizen_in`, `assignee_in`) where Django needs `__in`. Line 44 is
  correct, which is why it survived. No such fields exist on `Issue`, so the queryset raises
  `FieldError` on evaluation and the task has never completed. It backfills `internal_code`,
  anonymises citizen contact data, and sets `assignee`; it runs every 5 minutes under Celery and
  is the only cron wired on Vercel (`grm/cron_views.py:27`). No test covers it. The 2023 base is
  clean — its CouchDB Mango selector is well-formed — so this is a rewrite regression.
  - The anonymisation consequence is the serious one: categories set to `Anonymous`
    confidentiality have been storing citizen contact details unmasked.
- **`get_assignee` dead branches** (`issues/models.py:778-833`):
  - `confidentiality_level == "Confidential"` (line 828) can never match — the choices are
    `"low"` and `"anonymous"` (`grm/constants.py:93-96`).
  - Same line hardcodes `administrative_region=1`, assuming region pk 1 is the root.
  - The no-redirection-protocol path falls to `department.head` behind
    `print("not supposed to be here")`.
  - The least-loaded query filters workers across *all* regions, not the issue's region.
- **`IssueCategory.assigned_escalation_department`** — collected by wizard step 6, never read.
  Carries `# TODO: Remove this field`.
- **Wizard step 9 `restricted_deletion`** filters `Citizen.objects.filter(age_group=OuterRef("pk"))`
  (`wizard/views.py:501`) — compares a `CitizenGroup` pk against the age-group FK.
- **`COUCHDB_*` settings** are read with no defaults, so Django will not boot without them even
  on installs that never touch CouchDB. The re-base should drop this outright.

Ask the stopped Benin session for its sweep of other single-underscore `_in=` / `_isnull=` /
`_gte=` instances; that list belongs here.

## Wizard mechanics the PRD will need

- Eleven `WizardSection` rows seeded by migration `0009_wizardsection_refactor`. State is
  `not_started → in_progress → completed`; there is no session data. `WizardSection` is the
  wizard's entire state.
- Steps wire up through a registry decorator (`@register_wizard_step`); URLs are generated from
  the database row, so reordering is a data change — except step 3, whose upload modal
  hardcodes `{% url 'wizard:setup_step_3' %}`.
- Every step view returns an HTML fragment loaded by AJAX into `#formAjax`. Any agent panel
  lives in that shell.
- `WizardSection.name` uses `choices=WIZARD_SECTION_CHOICES`, which omits `summary`. The seeded
  summary row is valid in the DB but fails `full_clean()`.
- `WizardRedirectMiddleware` only fires on the `dashboard` and `wizard` namespaces. `/admin/`
  and the `/issues/` API are not gated — so a superuser can create users and workers during the
  wizard, and any intake gating would need a DRF permission rather than this middleware.

## Interface detail

**Coverage map.** Departments × administrative levels rather than × regions: five levels is a
readable grid, 77+ communes needs a tree. A cell counts as covered if any ancestor on the path
to root has a worker, once assignment climbs. Levels granularity is enough to spot real gaps;
region granularity is a later refinement if it earns itself.

**Unassigned queue.** Confirmed issues with a null assignee, diagnosed:

| Code | Category | Region | Age | Why |
|---|---|---|---|---|
| GRM-1042 | Water access | Commune de Zè | 43d | No worker in Water dept at Zè or any ancestor |
| GRM-1108 | Land dispute | Cotonou | 12d | Category has no redirection protocol set |
| GRM-0997 | Health | Abomey | 61d | Under appeal — Health dept has no head |

The diagnosis is computed from the same rules `get_assignee` applies, so it cannot drift from
actual behaviour. Sort by age.

Appeal rows deserve their own treatment: `reassign_issues_to_appeal` builds an
`appeal_is_not_available` list on every hourly run and discards it. Those issues retry forever
and appear in no interface today.

**State.** Compute checks live on every view; never store results, which go stale and produce a
green dashboard describing last month's staffing. If a go-live acknowledgement is wanted later,
store only the decision — who, when, which warnings they accepted.

**Rough code shape.** A `readiness.py` with one function per check returning pass/fail plus an
explanation string the agent can read out; a dashboard page under `diagnostics`, which already
hosts issue statistics.

## Rejected alternatives — rationale

**Configuration presets / import-export.** Listed as idea #2 in the Benin strategy doc. Three
curated presets would ship in about a week. Rejected as *sufficient* because the failure is
comprehension, not blank-page paralysis: a PIU that cannot explain the difference between a type
and a category cannot judge whether a preset fits their programme. Worth building alongside.

**Better forms and documentation.** Tried twice. Word configuration forms preceded the wizard;
the wizard replaced them. Neither was understood by the PIU, including by their developer.

**Gating citizen intake on readiness.** Considered and rejected by Leonardo: collecting the
grievance matters even when nothing can route it. An unassigned issue is recorded, not lost, and
drains automatically once someone is assigned to that cell.

**Forward-porting the wizard into the 2023 base.** Rejected in favour of re-basing on Benin.
Porting means re-implementing the Postgres domain, the issues app and the API across a
three-year gap; extraction means deleting client-specific content from code that already works.

## Adjacent workstreams, out of scope

The Benin strategy docs cover live interactive flow diagrams generated from real config, and
role impersonation ("view as citizen / facilitator / case manager"), with Stitch mockup prompts
for both. The ideas doc argues diagrams are a technical dependency of both the wizard preview
and the impersonation launcher; if that holds, sequencing matters and the agent may want the
diagram work first.
