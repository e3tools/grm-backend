# Case comments

How comments on a case (an `Issue`) work in the GRM backend: where they are stored, who can
read and write them, what the system writes on its own, and known gaps.

In the dashboard the comment list is the **"Steps Taken"** panel on the case detail page. It
holds what staff type in and also an audit trail the system writes for them.

## Data model

`Comment` — `src/issues/models.py:863`

| Field          | Type                         | Notes                                                        |
|----------------|------------------------------|--------------------------------------------------------------|
| `comment`      | `TextField`                  | Free text. Required.                                         |
| `user`         | FK `authentication.User`     | Nullable. `NULL` = written by the system (shown as "GRM system"). `on_delete=CASCADE`: deleting a user deletes their comments. |
| `issue`        | FK `Issue`                   | `related_name='comments'`. `on_delete=CASCADE`.               |
| `due_date`     | `DateTimeField`              | Defaults to `now`. This is the comment's timestamp in the UI and the sort key. The ETL import sets it from CouchDB `due_at`. |
| `created_date` | `DateTimeField`              | `auto_now_add`.                                              |
| `updated_date` | `DateTimeField`              | `auto_now`.                                                  |

Default ordering is `-due_date`: newest first, everywhere.

There is no edit endpoint. A comment can be created or deleted, and that's it. The mobile API
can delete. The dashboard can't.

## Who writes comments

### 1. People, via the mobile API (DRF, token auth)

Routes in `src/issues/urls.py:44-46`, views in `src/issues/views.py:1738-2190`.

| Method   | Path                                   | View                          | Result                                  |
|----------|----------------------------------------|-------------------------------|-----------------------------------------|
| `POST`   | `/issues/<issue_id>/add-comment`       | `IssueCommentCreateAPIView`   | 201 `{message, data: Comment}`          |
| `GET`    | `/issues/<issue_id>/comments/`         | `IssueCommentsListAPIView`    | 200, paginated (`PAGE_SIZE` = 20)       |
| `DELETE` | `/issues/delete-comment/<comment_id>/` | `IssueCommentDeleteAPIView`   | 204                                     |

Request body for create: `{"comment": "text"}` (`CommentCreateSerializer`). The view sets
`issue` and `user` (the token's user). DRF strips leading and trailing whitespace. An empty or
whitespace-only value returns 400.

Response shape (`CommentSerializer`): `id, comment, user {basic}, issue, due_date,
created_date, updated_date`.

**Permission:** `IsReporterOrAssigneePermission` (`src/issues/permissions.py:8`). The caller
must be the issue's `reporter` or its current `assignee`. Anyone else gets 403. A missing issue
or comment returns 404.

Create and delete both call `user.update_last_activity()`.

### 2. People, via the web dashboard (session auth, AJAX)

Routes in `src/dashboard/grm/urls.py:81-90`, views in `src/dashboard/grm/views.py:765-799`.

| Path                                  | View                     | Notes                                          |
|---------------------------------------|--------------------------|------------------------------------------------|
| `POST add-comment-to-issue/<issue>/`  | `AddCommentToIssueView`  | Strips the text and cuts it to `TEXTAREA_MAX_LENGTH` (65000). Empty text → error flash message, nothing saved. |
| `GET issue-comments/<issue>/`         | `IssueCommentListView`   | Renders `grm/issue_comments.html`. There's no pagination, so every comment is returned. |

The case detail page (`dashboard/templates/grm/issue_detail.html:200-235`) loads the list. The
**Save** button posts the comment and then reloads `#comments`.

**Permission:**
- Reading: `IssueMixin.check_permissions` → `user_can_access_issue`
  (`src/dashboard/grm/permissions.py:10`). For a confirmed issue that means GRM Managers, plus
  case managers who are PIU staff for the issue. For an unconfirmed issue, only the reporter.
- The comment box only shows when `issue.is_piu_staff(user) or user.grm_manager`
  (`src/dashboard/grm/views.py:714`).

### 3. Side effects of other dashboard actions (attributed to the acting user)

| Action                         | Comment text                                              | Where                          |
|--------------------------------|-----------------------------------------------------------|--------------------------------|
| Upload attachment              | "A new attachment {name} has been added to the issue."    | `dashboard/grm/views.py:184`   |
| Delete attachment              | "The attachment {name} has been deleted to the issue."    | `dashboard/grm/views.py:222`   |
| Submit research result (resolve) | "The complaint has been resolved"                       | `dashboard/grm/views.py:905`   |
| Reject case                    | "The complaint has been rejected"                         | `dashboard/grm/views.py:951`   |

These are ordinary `Comment` rows. Nothing marks them as system-generated, so they can't be
told apart from typed comments except by their text.

### 4. Celery tasks (`user=NULL`, shown as "GRM system")

| Task                          | Comment text                                                                  | Where               |
|-------------------------------|-------------------------------------------------------------------------------|---------------------|
| Auto-assign unassigned issues | "The issue has been assigned to {assignee}."                                  | `grm/tasks.py:88`   |
| `escalate_issues`             | "The complaint has been escalated automatically because the processing time has passed." | `grm/tasks.py:123`  |

### 5. ETL import from CouchDB

`process_comments_data` (`src/etl/utils.py:543`) reads `comments[]` from each CouchDB issue
document. It maps `due_at` → `due_date` and sets `user_id` only when the source `id` is an
int. It skips any comment whose `(issue external_id, due_date)` pair already exists.

The demo seeder `set_benin_demo` also creates comments (`issues/management/commands/set_benin_demo.py`).

## Notifications

None. No signal, task, or email fires when a comment is created. Other users only see a new
comment when they reload the case.

## Known gaps

1. **Any reporter or assignee can delete any comment on the issue**, including comments
   written by someone else and system comments. The delete view checks rights on the issue,
   not on who wrote the comment (`issues/views.py:2093-2131`). The test
   `test_assignee_can_delete_own_comment` only covers the author's own comment. The tests
   don't cover deleting someone else's comment.
2. **Mobile API access is narrower than dashboard access.** On the API, only the reporter and
   the current assignee can use comments. GRM Managers and other PIU staff can comment in the
   dashboard but get 403 on the API. After escalation the previous assignee loses API access
   to the thread.
3. **The dashboard POST doesn't check the comment-box rule.** `AddCommentToIssueView` only
   checks read access. On an unconfirmed issue the reporter can post through the endpoint
   directly, even though the UI hides the box.
4. **A missing `comment` field returns 500 on the dashboard.** `request.POST.get("comment")`
   returns `None`, then `.strip()` raises (`dashboard/grm/views.py:771`).
5. **No audit of deletes.** A deleted comment is gone for good. No log entry or tombstone is
   kept.
6. **Typed comments and system comments aren't separated.** System comments are only marked
   by `user IS NULL`. The action comments from section 3 don't even have that.
7. **The ETL duplicate check is weak.** It matches on `(issue, due_date)` only. Two comments
   on the same issue with the same `due_at` collapse into one.
8. **The dashboard list has no pagination.** A case with a long history renders every comment
   in one response.

## Tests

- API: `src/issues/tests/integration_tests/test_issue_comment_create_api_view.py`,
  `test_issue_comments_list_api_view.py`, `test_issue_comment_delete_api_view.py`
- Permission class: `src/issues/tests/unit_tests/test_is_reporter_or_assignee_permission.py`
- Dashboard: `src/dashboard/grm/tests/integration_tests/test_add_comment_to_issue_view.py`,
  `test_issue_comment_list_view.py`
