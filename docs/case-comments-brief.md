# Product brief: Case comments ("Steps Taken")

## TL;DR

Comments are the running history of a case. Staff use them to log what they did, and the
system adds its own notes. They work, but they can't be trusted as an audit trail yet: case
participants can delete other people's comments without leaving a trace. Also, managers who
can comment on the web can't comment on mobile. These two items need a decision.

## What it is

Every case has a "Steps Taken" timeline. Each entry shows who wrote it, when, and what it
says, with the newest entry first.

Entries come from three sources:

- **People writing updates.** The case handler or field agent types a note, for example
  "Called the complainant, visit scheduled for Monday."
- **Automatic notes on actions.** When someone adds or removes a file, resolves a case, or
  rejects it, a note is logged under that person's name.
- **System notes.** When the platform assigns a case or escalates it because the deadline
  passed, it logs a note signed "GRM system."

Comments from the old system were migrated in.

## Who can do what today

| Who                                           | Web dashboard              | Mobile app                  |
|-----------------------------------------------|----------------------------|-----------------------------|
| GRM manager                                   | Read and write             | No access                   |
| Staff responsible for the case's area         | Read and write             | Only if currently assigned  |
| Person currently assigned to the case         | Read and write             | Read, write, delete         |
| Person who registered the case                | Read only (before confirmation) | Read, write, delete    |

Nobody can edit a comment after posting it.

## Problems

### 1. History can be erased (high)

On mobile, anyone on the case can delete any comment on it, including notes from colleagues
and system notes. Nothing records that a comment was deleted.

**Impact:** The timeline is the evidence of how a complaint was handled. If it can be quietly
changed, it won't hold up in a dispute, an audit, or a donor review.

### 2. Web and mobile give different access (medium)

Managers can comment on the web but are blocked on mobile. When a case escalates to someone
new, the previous handler loses mobile access to its history.

**Impact:** Field staff and managers get inconsistent behavior, and handovers lose context.

### 3. Nobody is told about new comments (medium)

Posting a comment sends no alert. People only see updates when they open the case.

**Impact:** Questions sit unanswered and handovers are slow, which eats into the case
deadline.

### 4. Typed notes and automatic notes look alike (low)

Notes logged automatically on actions (files, resolution, rejection) look the same as notes
someone typed.

**Impact:** The timeline is harder to read, and it's harder to tell what a person actually did
from what the system recorded.

### 5. Long cases load everything at once (low)

**Impact:** The case page slows down on cases with a long history.

## Decisions needed

1. **Deletion policy.** Pick one:
   - (a) No deletion. Recommended: simplest, and the timeline stays complete.
   - (b) Authors can delete only their own comments, and the timeline shows "comment deleted."
   - (c) Keep it as it is.
2. **Mobile access.** Should managers and area staff get the same comment access on mobile
   that they have on the web?
3. **Notifications.** Who gets alerted when a comment is posted, and through which channel
   (in-app, email, SMS)?

## Suggested next step

Fix #1 first: it's small and has the largest risk. Settle #2 and #3 together because they
touch the same users. #4 and #5 can wait for the backlog.

## Open questions

- Does the client or donor require a complete, unchangeable case history? If yes, #1 becomes
  mandatory.
- Should comments ever be visible to the complainant? Today they never are.
