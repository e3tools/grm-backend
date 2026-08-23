# Conference — Benin GRM demo (presenter script)

Approximate length: **8–12 minutes** (depends on Q&A and network / Pinecone availability).

## Prerequisites

- **PostgreSQL** (or whatever database this project is configured for), environment variables aligned with `src/grm/example.env`.
- **Django**: dependencies installed (`pip install -r src/requirements.txt` from the repo root, or equivalent).
- **Migrations**: `cd src && python manage.py migrate`.
- **Pinecone (recommended for `/search/`)**: `PINECONE_API_KEY` and `PINECONE_INDEX_NAME` in `.env`. Without a key, semantic search shows an informational message and no vector hits.
- **CouchDB**: if your local stack expects it when starting the app or tests, run it per project docs (dashboard integration tests may connect to it).

## “Empty” database setup

The `set_benin_demo` command **only runs when** the database still has no users, administrative regions, levels, statuses, or issues. Use a disposable database or a fresh instance.

```bash
cd src
python manage.py migrate
python manage.py set_benin_demo
```

### What gets loaded (summary)

- Benin administrative tree (departments / communes), statuses, programme departments, **3 issue types**, **7 categories** (each with its own subtype), component, age bands, **citizen groups** for search filters.
- **Presenter** account (GRM owner / manager, wizard marked complete).
- **Facilitators** (`facilitator-1@grm-benin.local`, …): active accounts **without** web dashboard login (realistic field-reported grievances).
- **75 confirmed issues** (see `NUM_DEMO_ISSUES` in `set_benin_demo.py`), each issue’s **category and type** picked with **`random.choice`** among the seven categories (**`random.seed(42)`** at the start of the demo seed so runs are reproducible but counts per category/type are **uneven**, closer to real traffic). French narrative text, **image attachments** (minimal PNG) on many records, linked **citizens** for Pinecone metadata / filters, **status history** on a subset. Assignees are **commune-level case managers** (`GovernmentWorker` on the village-tier department). **Five** issues are seeded **in appeal** (`appeal_status=True` with a reason); **three** others have **escalation** flags for the escalation / de-escalation UI.
- **Department heads** on all three programme departments (including the **appeal** department used by `reassign_issues_to_appeal`), plus a **dense worker grid**: commune `d1` workers, duplicate `d1` worker on the first demo commune, department-level `d1` workers for escalate targets, a **`d2` line worker**, and the appeal head as a **`d3` worker** at the country region.
- Aggregations: `populate_performance_metrics`, `populate_region_performance_metrics`, `populate_status_bottlenecks`.
- If `PINECONE_API_KEY` is set: automatic `etl_upload_issues_to_pinecone` (error message to stdout on network / API failure).

Quick sanity check (optional, Django shell):

```bash
python manage.py shell -c "from authentication.models import User; from issues.models import Issue, IssueAttachment, IssueType, IssueCategory; print('users', User.objects.count(), 'types', IssueType.objects.count(), 'categories', IssueCategory.objects.count(), 'issues', Issue.objects.filter(confirmed=True).count(), 'attachments', IssueAttachment.objects.count())"
```

## Dashboard login

- **URL**: whatever your `runserver` or deployment uses (e.g. `http://127.0.0.1:8000/`).
- **Credentials**: email **`demo@grm-benin.local`**, password **`demo`** (constants `DEMO_EMAIL` / `DEMO_PASSWORD` in `issues/management/commands/set_benin_demo.py` — the form expects **email**, not username).

## Case managers and department heads

Wizard sections are marked complete for the demo, so **case managers and heads** can log in even without `grm_owner` (see dashboard `CustomLoginView`).

All of the following use the same password as the presenter unless you changed **`CASE_MANAGER_PASSWORD`** in `set_benin_demo.py` (default: same as **`DEMO_PASSWORD`** / `demo`).

| Role | Example email (pattern) |
|------|-------------------------|
| Department head (village-tier / **d1**) | `head-d1-village@grm-benin.local` |
| Department head (**d2**) | `head-d2-local@grm-benin.local` |
| Department head / appeal officer (**d3**) | `head-d3-appeal@grm-benin.local` |
| `d2` line case manager | `case-mgr-d2@grm-benin.local` |
| Commune case manager | `case-mgr-d1-c{region_id}@grm-benin.local` (one per facilitator commune; `{region_id}` is the commune’s database id) |
| Second case manager (same “hot” commune) | `case-mgr-d1-c{region_id}-b@grm-benin.local` for that commune |
| Department-level `d1` coordinator | `case-mgr-d1-dept-{department_region_id}@grm-benin.local` |

**Escalation / de-escalation**: open a confirmed issue as a case manager (or as the presenter), use **Escalate** / **De-escalate** on the issue detail page. Targets resolve via `GovernmentWorker` rows at parent / child regions for **d1**.

**Appeal reassignment (Celery task)**: several seeded issues stay **in appeal** until you run the task. From `cd src`:

```bash
python manage.py shell -c "from grm.tasks import reassign_issues_to_appeal; print(reassign_issues_to_appeal.apply().result)"
```

That assigns open appeals to **`d3`’s department head** and clears `appeal_status` / `appeal_reason` on success. Use this in the demo after showing KPIs or filters that surface appeals.

## Suggested demo flow

1. **Dashboard**: home / indicators after aggregates are populated.
2. **Issue list or detail**: pick one with an attachment (several demo issues have one); show region context and status. Optionally log in as a **commune case manager** and open an issue assigned to that user.
3. **Escalation**: on issue detail, show **Escalate** / **De-escalate** (enabled when workers exist at parent / child regions).
4. **Appeal**: mention issues in appeal, then run the **`reassign_issues_to_appeal`** snippet above and refresh to show assignee handoff to the appeal head.
5. **Performance diagnostics**: `/dashboard/performance-diagnostics/` — metrics and bottlenecks fed by the chained management commands.
6. **Semantic search**: `/search/` — enter a natural-language query. Demo descriptions are in French, so examples such as *eau potable*, *intrants*, *indemnisation* match seeded text. Try a filter (region, type, age group, citizen group) when Pinecone is populated.
7. **First Pinecone query**: mention that the **first** query can be slower (index / network warm-up).

## If Pinecone is unavailable

- `/search/` shows that the key is missing or the service failed.
- **Plan B**: walk through **issue list**, **attachments**, and **diagnostics**; say NLP search will be shown from a screenshot or an environment with a valid key.

## Tweaking (without changing the product plan)

- Facilitator count, issue count (default **75**), attachments, case manager password: module-level constants in `set_benin_demo.py` (`NUM_FACILITATORS`, `NUM_DEMO_ISSUES`, `ATTACHMENT_PROBABILITY`, `MIN_ATTACHMENTS_PER_ISSUE`, `FACILITATOR_PASSWORD`, `CASE_MANAGER_PASSWORD`). Per-issue category/type uses **seeded random** choice among the seven categories; changing category/type counts requires editing `_create_reference_data` in the same file.
- To skip issues, metrics, and upload entirely: set `NUM_DEMO_ISSUES = 0`.

## After the conference

- If you added issues outside this command, refresh Pinecone manually: `python manage.py etl_upload_issues_to_pinecone`.
