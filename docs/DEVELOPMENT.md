# Development Notes

This document captures the current engineering state of the bot: what has been tested, what behavior is intentional, what bugs were fixed, and what still needs attention.

## Current testing checklist

Completed:

1. User flow and command flow
   - onboarding
   - Gmail connect flow
   - cycle flow
   - application/task commands
2. Classification of non-application emails
   - offers
   - rejections
   - assessments
3. Manual scan and incremental scan behavior
4. Interview round pickup in scan flow
   - round 1
   - round 2
   - final round
5. Sankey diagram generation
6. Daily auto-scan and action reminder flow

Still worth rechecking periodically:

1. Daily scheduled Gmail scan trigger
2. End-to-end behavior after model/prompt changes
3. Telegram formatting after long-message chunking changes

## Product direction

This project is intended to be:

- open source
- self-hosted
- BYOK

That means:

- users bring their own Telegram bot token
- users bring their own Google OAuth credentials
- users bring their own Google AI Studio API key for Gemma
- Gmail tokens and scan history stay in the user's own deployment

## Important implementation decisions

### Scan window

Fixed start dates are gone.

The bot stores scan timestamps per user and uses them to calculate the next scan window:

- first manual scan for a new cycle: backfill last 14 days
- later scans: `max(last_scan, now - 24 hours)`

Both manual scans and auto scans update the stored scan timestamps after a successful scan.

### Interview chain model

Interviews are stored as a chain:

```text
application -> interview_1 -> interview_2 -> interview_3
```

Not all interview rows point directly to the application root.

This matters for:

- `/timeline`
- `/sankey`
- stats
- remove/delete behavior

### Follow-up events must normalize onto one application root

Offers, rejections, OAs, HireVues, and interviews should affect stats and Sankey only after they are attached to a single application chain.

If an original application confirmation email was never scanned:

- create a ghost application anchor
- attach the follow-up event to that ghost anchor

This applies both to funnel stats and Sankey rendering.

### Timezone behavior

Command UX is based on each user's stored timezone:

- reminder labels
- `TODAY`
- `OVERDUE`
- `Xd remaining`
- daily auto-scan timing

The default timezone comes from `BOT_TIMEZONE`, falling back to `Asia/Singapore`.
New users store that value in `users.timezone`.

Telegram does not provide a reliable user timezone to bots, so BYOK/self-hosted deployments should configure `BOT_TIMEZONE` explicitly.

### Daily auto-scan and reminders

The scheduler wakes hourly and calls `run_daily_auto_scan`.

Each user is scanned when their local hour is `09:00`.

Expected behavior:

- scan Gmail using the normal incremental scan window
- send the grouped scan summary when new emails are classified
- send `No new updates.` when the scan finds no new classified emails
- send a second action-needed reminder message when pending items exist

Action-needed reminders are grouped by:

- assessments
- interviews

Each group is sorted:

1. unscheduled
2. overdue
3. upcoming by soonest date

The action reminder does not create usable `/done` indexes by itself; users should run `/tasks` before using `/done` or `/remove`.

### Task indexes

`/tasks` keeps separate numbered lists for assessments and interviews.

Current command syntax:

- `/done <assessment_index>`
- `/done i<interview_index>`
- `/remove <assessment_index>`
- `/remove i<interview_index>`

`/applied` keeps the application list:

- `/remove <app_index>`
- `/timeline <app_index>`
- `/offer <app_index>`
- `/reject <app_index>`

## Bugs fixed

### 1. Interview invite -> scheduling -> confirmation dedup

Recruiters often send:

1. initial interview invite
2. availability/scheduling email
3. confirmation with final booked time

These should not create three interview rounds.

Current expected behavior:

- one interview row for that round
- invitation emails create an interview row and infer the next round when the model gives no explicit round
- invitation emails with no concrete date/time keep `interview_date = NULL` and show as `UNSCHEDULED`
- scheduling/rescheduling emails without a booked time create or keep an unscheduled interview row
- confirmation emails update the existing row
- `interview_date`, `interview_platform`, and `confirmed_at` get filled in when the booking is confirmed
- interview-like emails with subtype `unknown` are skipped, because general prep notes or recruiter Q&A should not create new rounds

### 2. Ghost application anchors

Problem:

- follow-up email arrives
- no application confirmation exists in DB

Fix:

- create a ghost application node
- attach the follow-up event there

This prevents orphan rows and keeps stats/Sankey coherent.

### 3. Interview round handling

Companies may send:

- recruiter screens
- technicals
- behavioral rounds
- leadership/final rounds

Fixes:

- separate interview rounds in DB
- round-aware Sankey nodes
- if the model gives no explicit round, infer it from the current interview count in the chain
- if final round is detected, keep `is_final_round = 1` and still use the round count / explicit round logic consistently

### 4. Telegram chunking for large lists

Problem:

- list-style commands can exceed Telegram message limits

Fix:

- chunk long list outputs safely across multiple messages

Commands most at risk:

- `/applied`
- `/tasks`
- `/upcoming`
- `/help`
- `/cycles`
- `/stats`
- `/timeline`
- scan summaries
- daily digest

### 5. Removal behavior and chain safety

Guard rails for false detections:

- `/remove` can delete an application or a task

Rules:

- removing an application:
  - cascading delete over all descendants
- removing a non-application task:
  - delete only that row
  - reparent any direct children to the deleted row's parent

This avoids blowing away the full chain for a single false-positive follow-up task.

### 6. Outcome attachment

Offers and rejections should attach to the latest relevant stage in the chain, not always directly to the application root.

Examples:

- `application -> oa -> offer`
- `application -> interview_1 -> rejection`

### 7. Upcoming/tasks time handling

Interviews use `interview_date`, not `deadline`.

Unscheduled interviews:

- show as `UNSCHEDULED`
- should not appear as if they are due on the email arrival date

### 8. Stats interviewing definition

`/stats` is intentionally compact.

`Interviewing` means active application chains that:

- have at least one real non-ghost interview row
- do not yet have an offer or rejection outcome

This means a completed round 1 still counts as interviewing if the application has not reached an offer/rejection yet.

Applications that already ended in offer/rejection are not counted as currently interviewing, even if they had interviews.

## Current cautions

### Open model usage

The project currently uses:

- `gemma-4-31b-it`

This is handled through the Google Generative AI client stack, and transient upstream failures do happen.

Current mitigation:

- retry on transient API failures
- continue scanning after failed retries

README should continue to mention this behavior so operators know classification is not guaranteed to be perfect or uninterrupted.

### Follow-up events and stats

Yes, follow-up events should influence stats:

- OA
- HireVue
- interview
- offer
- rejection

But only after they are normalized onto a single application root.

That same normalization principle also drives Sankey behavior.

### Overdue tasks

Current behavior:

- tasks remain in `/tasks`
- tasks remain in `/upcoming` if they are within the upcoming window logic
- overdue assessments continue acting as reminders until manually marked done
- incomplete interviews with past confirmed times show as already happened until manually marked done

## Future ideas

1. Reminder to reply to recruiter outreach
2. Detect interview reschedules cleanly
3. More robust handling for ambiguous interview labels
4. Better repair tooling for old bad chain data

## Recommended regression checks after major changes

After modifying scan, linking, or LLM prompt logic, re-test:

1. `/scan` on:
   - application confirmation
   - OA
   - interview invite
   - interview confirmation
   - offer
   - rejection
2. `/timeline`
3. `/sankey`
4. `/stats`
5. `/tasks`
6. `/upcoming`
7. long-output chunking
