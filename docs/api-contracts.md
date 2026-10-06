# API Contracts (v0.1)

Milestone in parentheses is when the endpoint is due in the proposal. Several are already done.

All routes live under `/api`. Request and response bodies are JSON unless noted.
Every route except `auth/*`, `exercises`, and `health` needs `Authorization: Bearer <token>`,
and every query is scoped to the token's user. Interactive docs run at `http://localhost:8000/docs`.

Status column: **done** = implemented and tested, **stub** = contract fixed, returns 501 until its milestone.

| Method | Path | Module (owner) | Status |
|---|---|---|---|
| POST | `/auth/register` | Users (M2) | done |
| POST | `/auth/login` (form: `username`, `password`) | Users (M2) | done |
| GET | `/users/me` | Users (M2) | done |
| POST | `/assessments` | Assessment (M2) | done |
| GET | `/assessments/latest` | Assessment (M2) | done |
| GET | `/exercises?region=&difficulty=` | Catalog (M2) | done |
| GET | `/exercises/{id}` | Catalog (M2) | done |
| POST | `/plans` | Plans + Recommendation + AI (M3, M5) | done (fallback only) |
| GET | `/plans/current` | Plans (M3) | done |
| POST | `/sessions` | Sessions (M3) | stub |
| GET | `/sessions` | Sessions (M3) | stub |
| GET | `/progress` | Progress (M4) | stub |
| POST | `/reevaluations` | Reevaluation (M4) | stub |
| GET | `/notifications` | Notifications | done (read only) |
| GET | `/health` | | done |

## Shared vocabularies

Defined once in `backend/app/core/vocab.py` and mirrored in `frontend/src/types.ts`.

- **body_region**: `lower_back`, `shoulder`, `knee`, `ankle` (supported) and `neck`, `hip`, `wrist`, `other` (accepted so they can be referred)
- **limitations**: `cannot_kneel`, `cannot_lie_on_floor`, `limited_overhead_reach`, `poor_balance`, `no_equipment`
- **activity_difficulties**: `walking`, `climbing_stairs`, `squatting`, `bending`, `lifting`, `reaching_overhead`, `sitting_long`, `running`
- **red_flags**: `numbness`, `swelling`, `loss_of_function`, `pain_unrelated_to_activity`
- **reevaluation action**: `refer`, `reduce`, `increase`, `reassess`, `continue`

## Auth

`POST /auth/register`
```json
{ "email": "a@b.com", "password": "at least 8 chars", "display_name": "optional" }
```
`201 { "access_token": "...", "token_type": "bearer" }`, `409` if the email exists.

`POST /auth/login` takes form fields `username` (the email) and `password`. `401` on bad credentials.

## Assessment

`POST /assessments`
```json
{
  "body_region": "knee",
  "pain_level": 4,
  "limitations": ["cannot_kneel"],
  "activity_difficulties": ["climbing_stairs"],
  "red_flags": [],
  "description": "optional free text"
}
```
`201` returns the stored assessment plus the scope result:
```json
{ "id": 1, "in_scope": true, "referral_reasons": [], "starting_difficulty": 2, "...": "..." }
```
Out-of-scope example: `"in_scope": false, "referral_reasons": ["pain_too_high:8", "red_flag:numbness"]`.
Values outside the vocabularies or a pain level outside 0 to 10 return `422`.

## Plans

`POST /plans` (no body) builds a plan from the latest assessment:
scope check, then filtering, then AI (M5) or the rule-based fallback, then a 4-week schedule.

`201`
```json
{
  "id": 7, "assessment_id": 3, "status": "active", "difficulty_level": 1,
  "frequency_per_week": 3, "source": "fallback", "start_date": "2026-10-01",
  "items": [{ "exercise_id": "Cat_Stretch", "position": 0, "sets": 1, "reps": 1 }],
  "schedule": [{ "id": 1, "scheduled_date": "2026-10-01", "week_index": 0 }]
}
```
`409` if there is no assessment, the assessment is out of scope (body includes `referral_reasons`),
or fewer than 4 exercises are eligible. Creating a plan marks any older active plan `superseded`.

## Sessions (M3, contract only)

`POST /sessions`
```json
{
  "scheduled_session_id": 12, "completed": true,
  "pain_before": 4, "pain_after": 3, "perceived_difficulty": 3,
  "too_difficult_exercise_ids": [], "new_red_flags": [], "notes": null
}
```
`perceived_difficulty` is 1 (too easy) to 5 (too hard). A non-empty `new_red_flags` must
trigger reevaluation, which will refer.

## Progress (M4, contract only)

`GET /progress`
```json
{
  "plan_id": 7,
  "weeks": [{ "week_index": 0, "completion_rate": 0.67, "avg_post_pain": 3.5,
              "max_session_pain": 5, "pain_change": null, "missed_sessions": 1 }],
  "explanation": "AI text if it passed validation, else a template"
}
```
Computed by `progress.metrics.compute_weekly_stats`.

## Reevaluation (M4, contract only)

`POST /reevaluations` returns `{ "plan_id": 7, "action": "reduce", "reasons": ["completion_0.33"] }`.
Computed by `reevaluation.rules.evaluate`. On `refer` the plan status becomes `referred`
and automatic changes stop.

## AI structured outputs (M5)

The LLM must return JSON matching the Pydantic models in `backend/app/modules/ai/validation.py`:
`AIPlanOutput`, `AIIntakeSuggestion`, `AIAdjustment`, and plain text for explanations.
Anything that fails validation is logged in `ai_output_logs` and replaced by the fallback.
