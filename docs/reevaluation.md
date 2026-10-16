# Reevaluation implementation

`POST /api/reevaluations` requires a JWT and evaluates the current user's latest
plan. A session save also evaluates the active plan in the same database
transaction. This is event-driven automation, not a scheduled background job.

The response preserves the existing contract:

```json
{"plan_id": 12, "action": "reduce", "reasons": ["completion_0.333333"]}
```

The action is `refer`, `reduce`, `increase`, `reassess`, or `continue`. A missing
plan returns 404; missing authentication returns 401. A stopped plan returns its
saved terminal decision on repeated reviews. Referred plans created by intake
without a reevaluation decision return 409 with a request for a new check-in.

## Evidence and priority

The service reads the plan's assessment, scheduled sessions, exercise-session
logs, and session-linked pain reports directly. It does not depend on someone
opening the progress screen or on cached ProgressRecords. Only records owned by
the current user and linked to this plan participate.

1. Referral wins: assessment scope failure, any new red flag, or any session's
   before/after pain at or above the configured referral threshold stops the plan
   immediately. The existing weekly rise and six-week no-improvement rules also
   refer. A previous continue/reduce/increase does not suppress a new referral.
2. Reduce: lower frequency by one session per week, with a floor of one. Rebuild
   only future unlogged scheduled sessions and their unread reminders. Preserve
   past/today's schedule IDs and all logs. At the floor, retain one session and
   include `already_at_minimum_frequency` in the reasons.
3. Increase: raise difficulty by one level, at most level three, and replace the
   exercise assignments using the deterministic fallback after filtering again
   for the assessment's region, limitations and target difficulty. Catalog dose
   limits still apply. If the next level has too few eligible exercises, stop for
   reassessment rather than use excluded exercises or invent a short plan.
4. Reassess: mark `reassessment_required`, cancel future unread reminders and ask
   for a new intake. Creating another plan from the same assessment returns 409.
5. Continue: keep the plan unchanged.

Referral marks `referred`, cancels future unread reminders, prevents additional
session logs, and requires a new assessment before generating another plan.
Decision and notification writes commit with the session/plan change. The service
does not invoke AI or change the prototype threshold values.

## Time and repeat behavior

A full week is seven days from the plan's start date, using the server's UTC date
for reevaluation. Only finished weeks drive trend/adherence adjustments. Partial
weeks cannot trigger a low-completion reduction. Completion counts distinct
completed scheduled sessions; extra sessions affect pain metrics but cannot
inflate adherence. Missing weeks remain explicit so a gap does not count as
consecutive stable weeks. Assessment age is measured from assessment creation.

At most one non-referral decision is applied per seven-day evaluation period,
using the stored decision timestamp. Repeated calls return that decision. Late
logs do not trigger another non-referral adjustment in the same period, but
referral data is always checked. PostgreSQL callers lock the plan row until the
transaction commits. SQLite remains the single-user local development option;
it does not provide PostgreSQL's row-lock concurrency guarantees.

## User interface

Progress has a **Review my plan** action. Saving a session automatically reviews
the plan. Terminal outcomes preserve saved session history and display the care
or reassessment notification even though there is no longer an active plan.

## Verification

`tests/test_reevaluation_api.py` exercises all five API outcomes, automatic
session-triggered changes, user isolation, repeated calls, urgency overriding a
previous decision, safe next-level exercise doses, catalog shortages, frequency
floor, difficulty ceiling, extra-session adherence, historical schedule IDs,
updated reminders, and the fresh-intake requirement. Existing pure-rule tests
continue to cover threshold priority. Run:

```bash
cd backend
python -m pytest
ruff check app tests scripts
cd ../frontend
npm ci
npm run build
```

These checks verify software behavior against the team's prototype rules. They
do not establish clinical validity; catalog tags and thresholds still need the
external grounding requested in the proposal feedback.
