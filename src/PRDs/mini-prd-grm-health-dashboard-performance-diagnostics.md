### Mini PRD — GRM Health Dashboard (Performance Diagnostics)

GRM — Operations / System Health  
Author: Leonardo Simon Gutierrez Hernandez

### What’s the problem? Why?
GRM managers need a **single place** to quickly answer:
- **Is the GRM system healthy right now?** (adoption, throughput, satisfaction)
- **Where is work getting stuck?** (workflow/status bottlenecks)
- **Which geographies are struggling?** (administrative levels/regions)
- **Which staff are disengaged and need a nudge?** (inactive case managers/facilitators)

Today, these signals are either not visible, are scattered, or require manual analysis—leading to late detection of backlog, uneven performance across regions, and weak accountability.

---

### What use cases to cover? What is required?

#### Core Use Cases (MVP)
- **Health KPIs (dashboard)**
  - See KPI cards for user adoption, issue resolution, and citizen satisfaction, with trend deltas.
- **Workflow bottleneck detection (dashboard)**
  - See which statuses have the highest average time-in-status and their “good/at-risk/critical” badge.
- **Regional performance triage (dashboard)**
  - Compare performance across administrative levels under the selected region.
  - Sort by performance, open issues, resolution time, and worker activity.
- **Inactive user follow-up (dashboard)**
  - Identify case managers/facilitators who have not been active recently and optionally have open assigned work.
  - Select users and send a bulk reminder via Email/SMS.

#### Filters (must-have)
- **Date Range**: period (e.g., 7d / 30d / 90d)
- **Category**: issue category or all categories
- **Administrative region**: a region selection that applies to all panels

#### Permissions (must-have)
- Page access restricted to **GRM Managers** (403 for non-managers).
- All dashboard “send reminders” actions restricted to **GRM Managers**.

---

### How should it work?

#### 1) Filters & page structure
- The view is served at `dashboard/performance-diagnostics/`.
- Changing any filter triggers a refresh of:
  - KPI cards (HTML fragment)
  - Status bottlenecks (HTML fragment)
  - Region performance table (server-side DataTables JSON)
  - Inactive users table (server-side DataTables JSON)
- “Clear all filters” resets category/region and returns period to the default.

#### 2) KPI Cards (Health summary)
Three cards, each showing:
- **Primary KPI** (the “health” number)
- **Secondary KPI** (supporting signal)
- **Delta vs previous period** (percentage)
- **Status badge** (Good / At Risk / Critical / Unknown)

**User Adoption**
- Primary: Active users count (WAU/MAU/QAU depending on period)
- Secondary: New issues count (created in selected period)
- Status (example logic):
  - Good: adoption change \(>= 0\%\)
  - At risk: \(0\% >\) change \(>= -10\%\)
  - Critical: change \(< -10\%\)

**Issue Resolution**
- Primary: Avg resolution time (days)
- Secondary: Resolution rate (%) with numerator/denominator
- Status: computed vs a target (e.g., target avg resolution time = 10 days)

**Citizen Satisfaction**
- Primary: Avg satisfaction rating (0–5) with count of rated issues
- Secondary: Appeal rate (%) with numerator/denominator
- Status: computed vs a target (e.g., target avg satisfaction = 4.0)

**Data display behaviors**
- If no precomputed metrics exist for the filter combination: show “No metrics available for the selected filters.”
- Show “Last Updated” timestamp based on the snapshot’s `calculated_at`.

#### 3) Issue Lifecycle Bottlenecks (by Status)
- Table: one row per issue status
- Columns:
  - Status name
  - Issues in status (snapshot count; for terminal statuses, may fall back to a live count)
  - Avg time in status (days) or N/A
  - Performance badge (Good / At Risk / Critical / N/A)
- Optional “Insight” banner:
  - When a critical status exists, show a sentence pointing to the first critical bottleneck and its average days.

#### 4) Performance by Administrative Level (Regional triage)
- Table is hierarchical in intent:
  - If a region is selected and it has children: show child regions’ performance.
  - If a region is selected and it has no children: show the selected region and display an info message.
  - If no region is selected: show children of the root region (or root if no children exist).
- Columns:
  - Administrative Level (region name)
  - Open issues (count badge)
  - Avg resolution time (days badge)
  - Active workers (active/total and % badge)
  - Performance (badge derived from overall score)
  - Actions

**Actions (Phase 2, currently “Coming soon” UX is acceptable in MVP)**
- Investigate: deep dive into why performance is poor in the selected region.
- View Details: a region-level drilldown dashboard.
- Best Practices: guidance surfaced when the region is performing well.

#### 5) Inactive Case Managers / Facilitators (User engagement)
- Table lists users who have been inactive beyond a threshold (default 7+ days).
- Supports filters:
  - Role filter: case managers vs facilitators vs all
  - Open issues filter: has open assigned issues vs none vs all
- Allows:
  - Selecting users (including “select all” on current page)
  - Bulk action bar appears when \(n > 0\) users selected
  - “Send reminder” modal with:
    - Notification method: Email / SMS / Email & SMS
    - Message (required; max length 500; SMS warning about truncation)
    - Preview list of selected users and whether they have required contact info
  - Confirmation step before send
- After send:
  - Show success/failure summary (sent, skipped due to missing contact info, failed)
  - Clear selection

---

### Data & freshness requirements

#### Snapshot-first philosophy (must-have)
This dashboard should be **fast** and safe to load in production:
- KPI cards and status bottlenecks are **read-only** and must come from **precomputed snapshots**, not computed on request.
- Region performance should come from **precomputed region metrics**.

#### Data sources (current + required alignment)
- **Issues**: only **confirmed** issues should be used for “system health” metrics.
- **Administrative region filtering**: region filters should include descendants (where available).
- **Category filtering**:
  - If no category is selected, use a dedicated “all categories” aggregate (category = null).

#### Jobs / pipelines (required)
- A scheduled process must populate/update:
  - `PerformanceMetrics` for the supported periods and filter combinations
  - `StatusBottleneckMetrics` for each status and supported filters
  - `RegionPerformanceMetrics` for each region (and optionally by category) and supported periods

---

### Non-goals (explicitly out of scope for MVP)
- Real-time recalculation of metrics on dashboard load
- SLA configuration UI (e.g., per-status thresholds) inside this view
- Automatic corrective actions (auto-reassignment/escalation) directly from this dashboard

---

### User Stories

| Name | User Story | Notes |
|---|---|---|
| Quick Health Check | As a GRM Manager, I want to see overall GRM health at a glance so I can react quickly. | KPI cards + last updated timestamp. |
| Find Workflow Bottlenecks | As a GRM Manager, I want to see which statuses are bottlenecks so I can address process issues. | Avg days in status + performance badges + insight banner. |
| Identify Struggling Regions | As a GRM Manager, I want to compare performance by administrative level so I can prioritize interventions. | Sortable region table; child-region logic. |
| Nudge Inactive Staff | As a GRM Manager, I want to identify inactive case managers/facilitators and send reminders so issues don’t stall. | Filters + selection + email/SMS bulk send. |

---

### Success Metrics
- **Dashboard adoption**: weekly active GRM managers using `performance-diagnostics/`
- **Time-to-detection**: median time from backlog growth to manager action (proxy via usage + follow-up actions)
- **Backlog health**:
  - reduction in avg time-in-status for critical statuses (before vs after)
  - reduction in regions flagged “Critical” over time
- **Engagement outcomes**:
  - % of contacted users who log in within 7 days after a reminder
  - reduction in “inactive with open issues” users over time
- **Performance**:
  - page load and filter refresh latency within acceptable bounds (snapshot-first)

---

### Phases

#### Phase 1 — MVP (Health dashboard baseline)
- Filters: period, category, administrative region
- KPI cards with last-updated timestamp and “no data” state
- Status bottlenecks table + insight banner
- Region performance table with sorting/paging and “no children” message
- Inactive users table with filters + bulk reminder send (email/SMS)

#### Phase 2 — Drilldowns & operational tooling
- Replace “Coming soon” actions with real drilldowns:
  - Investigate (root-cause hints: categories, statuses, worker activity distribution)
  - View Details (region page with trends & top issue types)
  - Best Practices (playbooks and success patterns)
- Export/reporting (CSV/PDF) for regional and inactive user tables
- Configurable thresholds:
  - inactivity threshold per deployment
  - target resolution days / target satisfaction score

