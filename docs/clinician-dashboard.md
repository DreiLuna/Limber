# Clinician dashboard

A physical therapist can see anonymized data across all patients and tune the deterministic rules and the
AI prompt that drive LIMBER, without editing code. Every change is saved as a version, every record notes
which version produced it, and any version can be re-activated.

- Frontend: `/clinician` (Overview, Patients, Model config), code in `frontend/src/clinician/`
- Backend: `app/modules/clinician/` (analytics, anonymization) and `app/modules/model_config/` (versions)
- Tests: `tests/test_clinician.py`, `tests/test_model_config.py`, `tests/test_seed_script.py`

## Getting a clinician account

`users.role` is `patient` (the default) or `clinician`. The public API never sets it: a `role` field sent
to `/auth/register` is ignored. Create or promote accounts from the backend folder:

```bash
python -m scripts.create_clinician --email pt@example.com            # new account, prompts for a password
python -m scripts.create_clinician --email someone@example.com --promote
python -m scripts.create_clinician --email someone@example.com --demote
```

In Docker, prefix with `docker compose exec backend`. Clinicians land on `/clinician` after sign-in and
the patient navigation is hidden for them (a clinician account has no patient data of its own). Patients who
open `/clinician` are sent to their plan, and every `/api/clinician/*` route returns `403` for them.

## Demo data

```bash
python -m scripts.seed_synthetic_patients            # 40 fake patients over the last 10 weeks
python -m scripts.seed_synthetic_patients -n 80 --reset
python -m scripts.seed_synthetic_patients --single-version
```

Accounts use `@synthetic.example.com` and can't sign in. By default the first half of the timeline is
recorded under config v1, then the script saves a v2 (pain 6 becomes out of scope, one extra prompt line)
and records the second half under it, so the "By config version" table has two rows to compare.
`--reset` deletes only the synthetic accounts and their records.

## What "anonymized" means here

Enforced in `clinician/anonymize.py` and checked by `test_no_identifying_data_in_any_response`:

| Rule | How |
|---|---|
| No identity | Patients appear as `P-XXXXXX`, an HMAC-SHA256 of the user id. No id, email or name is returned. |
| No calendar dates per patient | Patient events are "day N since first intake". Calendar weeks appear only as cohort chart buckets. |
| No free text | Assessment descriptions, session notes and raw AI requests and responses are never returned. |
| No values in reason strings | `pain_too_high:8` becomes `pain_too_high`, `session_pain_8` becomes `session_pain`. Fixed vocabulary (red flags, regions, exception class names) is kept. |
| Patients only | Clinician accounts are never listed or counted. |

The HMAC key is `PSEUDONYM_SECRET`, falling back to `JWT_SECRET`. Codes are stable while the key stays the
same; changing it reissues every code.

Limits: this is pseudonymization, not full de-identification. With a very small cohort, a weekly bucket plus
a patient's day offsets could still point to one person. For anything beyond the class MVP, suppress cells
under 5 and review with whoever owns data protection.

## Analytics API

All routes are `GET`, need a clinician token, and accept the same filters:

| Param | Meaning |
|---|---|
| `start`, `end` | Inclusive ISO dates, matched against when each record was created |
| `region` | Body region of the intake that produced the record |
| `level` | Starting difficulty (1 to 3) of that intake |
| `version` | Only records produced by this config version number (`404` if unknown) |

Region and level follow each record back to its intake: a plan, progress week, decision or AI call is
counted under the intake that produced it. On `/patients` they match each patient's latest intake.

| Route | Returns |
|---|---|
| `/clinician/overview` | Patients, intakes, in-scope rate, active plans, average completion, average pain drop, referral rate, AI calls, AI fallback rate |
| `/clinician/analytics/intake` | Totals, out-of-scope reasons, region mix, starting level mix, weekly intakes vs out of scope |
| `/clinician/analytics/outcomes` | Plans by status and source; average post-session pain, completion and missed sessions by plan week; pain drop by region |
| `/clinician/analytics/rules` | Decisions by action and by reason, patients evaluated vs referred, referral rate, weekly actions |
| `/clinician/analytics/ai` | Calls, valid vs fallback, fallback rate, median and 95th-percentile latency, error types, by task, weekly |
| `/clinician/analytics/by-version` | The headline metrics above, one row per config version (records from before versioning appear as a "before versioning" row) |
| `/clinician/patients` | One row per patient: code, region, level, intake pain, days in program, plan status/level/source, weeks logged, latest pain and completion, last decision |
| `/clinician/patients/{code}` | One patient's intakes, plans with exercises, weekly progress, sessions (pain before and after), decisions and AI calls, all by day offset. `404` for an unknown or malformed code |

"Pain drop" is intake pain minus the most recent weekly average post-session pain, per plan.
"Referral rate" is patients with at least one `refer` decision divided by patients with any decision.

Aggregation runs in Python over filtered rows so SQLite and Postgres behave the same. Each call takes about
0.25 s on SQLite with 60 patients; move to SQL `GROUP BY` if volume grows.

## Model config versions

`model_config_versions` holds the full thresholds (the same shape as `config/thresholds.yaml`), the
editable prompt instructions, a required note, the author, the parent version and an active flag. A
partial unique index allows only one active row.

- **Version 1** is created from `thresholds.yaml` and the built-in prompt the first time the backend starts.
  Until then (and in unit tests) the YAML values are used directly.
- **Saving** creates a new version (append-only). "Save and activate" makes it live immediately; "Save
  draft" stores it without activating.
- **Rollback** is activating an older version. Nothing is deleted.
- **One version per request.** Intake, plan creation and reevaluation load the active version once and pass
  it down, so a request can't mix two versions. `assessments`, `recovery_plans`, `reevaluation_decisions`
  and `ai_output_logs` each store the `config_version_id` that produced them.

### What a save is checked against

`model_config/service.py` rejects a version (HTTP `422` with `{"errors": [...]}`) when:

- a key is unknown or missing, or a number is outside its range;
- a region isn't covered by the exercise catalog (`lower_back`, `shoulder`, `knee`, `ankle`), or a red flag
  isn't in the vocabulary;
- any in-scope pain level (0 to the highest starting pain allowed) has no difficulty band, or two bands
  overlap;
- the fewest exercises per plan is above the most;
- the "reduce" completion threshold is above the "increase" one;
- the session pain that triggers a referral isn't above the highest starting pain allowed;
- the prompt instructions are empty, longer than 4,000 characters, or contain `USER CONTEXT:` or
  `ELIGIBLE:`;
- the note is empty.

### Prompt structure

```
<clinician-editable instructions>

Rules (always enforced):                      <- locked, built from the active thresholds
- Choose between {min} and {max} exercises from the ELIGIBLE list below.
- Use only exercise ids that appear in ELIGIBLE; never invent ids or repeat one.
- For each exercise, sets must be within its [min, max] 'sets' range and reps within its [min, max] 'reps' range.

USER CONTEXT: {...}                            <- injected
ELIGIBLE: [...]                                <- injected
```

The locked block mirrors what `ai/validation.py` enforces, so editing the instructions changes the AI's
guidance but cannot weaken validation. Any output that fails validation still falls back to the rule-based
plan.

### Config API

All under `/api/clinician/config`, clinician only.

| Method | Route | Does |
|---|---|---|
| GET | `/active` | Active thresholds and instructions, plus the locked rules text |
| GET | `/defaults` | The YAML thresholds and built-in instructions (for "Load defaults") |
| GET | `/versions` | Version list, newest first (seeds v1 if none exist) |
| GET | `/versions/{n}` | One version in full |
| POST | `/versions` | `{thresholds, prompt_instructions, note, activate}` → new version (`201`) or `422` with errors |
| POST | `/versions/{n}/activate` | Make version n live (rollback) |
| GET | `/diff?base=&target=` | Changed threshold paths (before and after), whether the prompt changed, both prompts |
| POST | `/preview-prompt` | `{prompt_instructions, thresholds?}` → the full prompt with sample (non-patient) data, plus any validation errors |

## Reading the dashboard to tune the model

| If you see | Look at |
|---|---|
| High out-of-scope rate for "Starting pain too high" | `scope.max_starting_pain` and the difficulty bands |
| Many `reduce` decisions from low completion | `reevaluation.reduce_completion_below`, or `plan.default_frequency_per_week` |
| Few `increase` decisions while pain falls | `reevaluation.increase_completion_at_least` and `increase_stable_weeks` |
| Referral rate rising after a change | Compare rows in "By config version", then roll back if needed |
| AI fallback driven by "Wrong number of exercises" or "Sets out of range" | Prompt wording first; the limits themselves are in "Plan shape" |
| AI fallback driven by timeouts | `LLM_TIMEOUT_S` in `.env` (the `ai.timeout_seconds` threshold is stored but not read by the planner) |

Thresholds are student MVP policy values, not clinically validated rules. Record the published guidance or
clinician review behind a change in its note.
