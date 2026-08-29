### Mini PRD — Escalation, De-escalation & Automatic Escalation Rules (GRM Issues)

GRM — Case Management  
Author: Leonardo Simon Gutierrez Hernandez

### What’s the problem? Why?
Issues can get **stuck** (slow processing, no progress in a status, unclear ownership) and need a reliable way to:
- **Move accountability upward** when thresholds are exceeded
- **Support escalation requests** (from reporters or staff)
- **Undo escalation** when needed (send back down to an operational level)
- **Automate** escalation based on configurable rules, without manual monitoring

Without consistent escalation + rules:
- **Threshold breaches go unnoticed**
- **Ownership becomes unclear**
- **Managers spend time chasing instead of acting**
- **Users lose trust** when issues don’t progress

---

### What use cases to cover? What is required?

#### Core Use Cases
- **Manual escalation (dashboard)**  
  A GRM Manager / PIU staff escalates an issue to the next “higher” administrative level responsible user.
- **Manual de-escalation (dashboard)**  
  A GRM Manager / PIU staff de-escalates an issue back down when appropriate.
- **Village Secretary-driven escalation request (API)**  
  A reporter flags an issue for escalation and provides an optional reason.
- **Automatic escalation by time-in-status (rules + background jobs)**  
  Issues that exceed a configured threshold in their current status are automatically flagged and escalated.

#### Product Requirements (current behavior)
- **Permissions**
  - Dashboard escalate/de-escalate only for **GRM Manager / PIU staff**
  - API update allowed only for **assignee** (token-auth)
- **Escalation routing (current)**
  - Escalate moves the assignee **up the administrative region hierarchy** (parent → parent …) within the **same assigned department** for the issue’s category.
  - De-escalate moves the assignee **down the hierarchy** (children → descendants) within the **same department**, selecting the first available match.
- **Automatic escalation rules (current)**
  - Each `IssueStatus` can define `threshold_days_to_escalate` (optional).
  - A daily job marks qualifying issues with `escalate_flag=True` when days-in-status **strictly greater** than the threshold.
  - A frequent job (every 5 minutes) escalates issues with `escalate_flag=True` and adds a **system comment** explaining automatic escalation.
- **Audit fields**
  - On actual escalation (manual or automatic): set `escalated_date`.
  - Store escalation request text in `escalation_reason` (via API update).

---

### How should it work?

#### 1) Manual escalation (Dashboard)
- **Trigger**
  - User clicks **Escalate** button on Issue Detail page.
- **Behavior**
  - UI disables button if no valid escalation target exists.
  - On success:
    - Reassign `issue.assignee` to the next valid “up-hierarchy” user (same department)
    - Clear `issue.escalate_flag` (if it was set)
    - Set `issue.escalated_date = now`
    - UI refreshes assignee + buttons state
  - On failure:
    - Show error: no users available to escalate

#### 2) Manual de-escalation (Dashboard)
- **Trigger**
  - User clicks **De-escalate** button on Issue Detail page.
- **Behavior**
  - UI disables button if no valid de-escalation target exists.
  - On success:
    - Reassign `issue.assignee` to a valid “down-hierarchy” user (same department)
    - UI refreshes assignee + buttons state
  - On failure:
    - Show error: no users available to de-escalate

#### 3) Escalation request via API (Assignee)
- **Trigger**
  - `PATCH /issues/:id` with:
    - `escalate_flag=true`
    - optional `escalation_reason`
- **Behavior**
  - Issue becomes eligible for automatic escalation execution (see next section).
  - Role restrictions still apply for other fields (e.g., only assignee can change status, only reporter can set rating).

#### 4) Automatic escalation by rules (Background)
- **Step A — Daily “marking” job**
  - Finds confirmed issues where:
    - not already flagged for escalation
    - status is not final/rejected
    - status has `threshold_days_to_escalate`
    - days spent in current status > threshold
  - Bulk updates: `escalate_flag=True`

- **Step B — Frequent “execution” job (every 5 minutes)**
  - For each issue with `escalate_flag=True` and an assignee:
    - Compute escalation target (up-hierarchy within department)
    - If found:
      - assign it, clear flag, set `escalated_date`, add system comment
    - If not found:
      - keep it flagged (continues retrying on next run)

---

### Configuration
- **Wizard configuration**
  - Issue Status: configure `threshold_days_to_escalate` (shown for initial/open statuses)
  - Categories: capture `assigned_escalation_department` (currently available for configuration, even if routing is still based on the category’s assigned department + region hierarchy)

---

### Phases

#### Phase 1 — MVP (current scope)
- Manual escalation & de-escalation in dashboard with proper enable/disable states
- API-based escalation request (`escalate_flag`, `escalation_reason`)
- Automatic escalation rules:
  - configurable per status via `threshold_days_to_escalate`
  - daily marking + periodic execution
- Audit via `escalated_date` and system comment on auto escalation

#### Phase 2 — Enhancements
- Route escalations via configured **Escalation Department** (when/if desired), not only hierarchy-in-same-department
- Add clearer audit trail:
  - who escalated/de-escalated (manual)
  - escalation level count, previous assignee history, reason required rules
- Alerts/notifications (email/SMS/in-app) to new assignee and/or managers
- Ops dashboards:
  - count of flagged issues
  - “no escalation target available” backlog
- Rule tuning:
  - per-category or per-region overrides
  - “>= threshold” vs “> threshold” behavior as a configurable option

---

### User Stories

| Name | User Story | Notes |
|---|---|---|
| Manual Escalation | As a GRM Manager/PIU staff, I want to escalate an issue so it is handled at a higher administrative level when needed. | Reassigns assignee upward; sets escalated date. |
| Manual De-escalation | As a GRM Manager/PIU staff, I want to de-escalate an issue so it can be handled at a more local operational level. | Reassigns downward if possible. |
| Assignee Escalation Request | As a assignee, I want to request escalation and explain why, so my issue gets more attention when stuck. | API-driven `escalate_flag` + reason. |
| Automatic Escalation by Time | As the system, I want to automatically escalate issues that exceed a status threshold, so SLA breaches are addressed without manual monitoring. | Daily marking + 5-min execution with system comment. |

---

### Success Metrics
- **% issues escalated automatically** that had breached thresholds (coverage)
- **Time-to-assignment after escalation flag** (should drop with frequent execution job)
- **Reduction in issues exceeding threshold_days_to_escalate** (before vs after)
- **Retry backlog size**: issues flagged but with no available escalation target
- **Manual escalations per week** (should decrease if auto rules work well)

---


