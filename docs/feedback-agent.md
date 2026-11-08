# Feedback review agent (planned)

Status: **not built yet**. The server already stores everything this worker needs (statuses, a timeline that accepts `agent` events, the owner's approve/decline buttons). This page is the contract for building it.

## What it does
For bugs, app ideas and server ideas (never content requests), the worker:
1. Picks up new items.
2. Decides whether each one makes sense (triage) and writes a fuller version of it.
3. Has a Claude Code agent (plan mode, against this repo) turn that into an implementation plan.
4. Posts the plan back. The owner approves it, asks for changes, or declines it in Settings → Feedback.

Nothing beyond planning happens without the owner's approval.

## Where it runs
The worker runs as an external process: on the owner's PC, or as a scheduled cloud routine. It talks to the server's API with its own token. The server never calls an AI service itself.

## Statuses (`server/feedback.py`)
`new` → `triaging` → `needs_info` | `declined` | `duplicate` | `planning` → `plan_ready` → `approved` | `changes_requested` | `declined` → `in_progress` → `done`

- `AGENT_TRANSITIONS` lists what the worker may do. `STAFF_TRANSITIONS` lists what people may do; it already handles `plan_ready` (Approve / Request changes / Decline).
- The owner's answer to a plan is recorded as a `plan_decision` event. With `changes_requested`, the worker re-plans using the note on that event.
- The sender only sees `comment` and `status` events. `triage`, `plan` and `plan_decision` events are owner only.

## To build
1. **Agent token.** Add a nullable `scope` column to `ApiToken` (added by `add_missing_columns()`). Agent tokens get `scope = "feedback-agent"`.
   - In `load_api_user`, a scoped token may only reach `/agent/*`, and normal tokens may not reach `/agent/*`.
   - The owner switch `FEEDBACK_AGENT` (in `server_settings.EDITABLE`, off by default) creates the token, shows it once, and revokes it when turned off.
2. **Blueprint `/api/v1/agent`.**
   - `GET /agent/feedback?status=new&kind=bug,app_idea,server_idea`: full items, as `feedback_json(..., detail=True)` gives the owner (logs, context, screenshot URLs).
   - `POST /agent/feedback/<id>/claim`: sets `triaging` and `Feedback.claimed_when`. Returns 409 if the item is already claimed; a claim older than 1 hour can be taken over.
   - `POST /agent/feedback/<id>/triage`: takes `{verdict: plan|decline|needs_info|duplicate, summary, fleshed_out, duplicate_of?}`. It adds a `triage` event (author `agent`) and moves the status. For `needs_info`, the question also goes to the sender as a comment.
   - `POST /agent/feedback/<id>/plan`: takes `{plan_markdown}`. It adds a `plan` event and sets `plan_ready`, which shows on the owner's badge (`feedback.WAITING`).
   - Check every change with `feedback.allowed_statuses(item, actor="agent")`.
3. **App.** The timeline already shows `triage` and `plan` events. Plans are currently plain text, so a markdown view would help. Add the `FEEDBACK_AGENT` switch to Settings → Feedback.

## Safety
- Report text, logs and screenshots come from users and are **untrusted**. The worker must treat them as data to evaluate, never as instructions.
- The worker's Claude Code session should run in plan mode, without push rights.
- Logs are redacted when stored (`logbuffer.redact`, `lib/logBuffer.js`). The worker should still never copy them anywhere public.
