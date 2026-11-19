# LIMBER: Physical Therapy Recovery App

CSCI 5030 team project. A low-cost web app that gives people with minor lower back, shoulder,
knee, or ankle pain a structured exercise plan, tracks their recovery, and sends them to a
licensed physical therapist when the rules say they need one.

**Core idea:** rules decide what is allowed, the AI personalizes inside those limits,
validation checks the AI, and only valid output reaches the user.

## Stack

React + TypeScript + Tailwind (Vite) · Python 3.12 + FastAPI + Pydantic · SQLAlchemy 2 + Alembic ·
PostgreSQL 16 · JWT + Argon2 · free-exercise-db · pytest · Docker Compose · GitHub Actions

## Quick start (Docker)

```bash
cp .env.example .env          # then set JWT_SECRET
docker compose up --build
docker compose exec backend python -m scripts.import_catalog --load-only
```

- Frontend: http://localhost:5173
- API docs (Swagger): http://localhost:8000/docs

The backend container runs `alembic upgrade head` on start. The catalog load step only needs to run once
per fresh database.

### Optional email reminders

I added optional email reminders so users can get a message before a scheduled recovery session. The
app's in-app reminders still work when email is turned off. To try email reminders, add the SMTP
settings below to the root `.env` file and restart the backend:

```env
EMAIL_REMINDERS_ENABLED=true
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=your-gmail-address
SMTP_PASSWORD=your-google-app-password
SMTP_FROM=your-gmail-address
```

For Gmail, I use an App Password with 2-Step Verification enabled. The backend checks once a minute
for sessions coming up within 24 hours, and it does not email a reminder for a session that has already
been logged. I keep `.env` out of Git so account credentials are not shared with the project.

### Clinician dashboard

Physical therapists get an anonymized dashboard at `/clinician`: cohort analytics, a per-patient drill-down
by pseudonymous code, and an editor for the rule thresholds and AI prompt with version history and
rollback. Create a clinician account and, for a demo, some synthetic patients:

```bash
docker compose exec backend python -m scripts.create_clinician --email pt@example.com
docker compose exec backend python -m scripts.seed_synthetic_patients
```

Sign in with that account and you land on the dashboard. Details, anonymization rules and the API are in
`docs/clinician-dashboard.md`.

## Local development without Docker

Requires Python 3.12+ and Node 20+.

```bash
cd backend
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
export DATABASE_URL=sqlite:///./dev.db               # or point at a local Postgres
alembic upgrade head
python -m scripts.import_catalog --load-only
uvicorn app.main:app --reload

cd ../frontend
npm install
npm run dev
```

## Tests

```bash
cd backend
pytest --cov=app        # 180 tests, uses a throwaway SQLite database
ruff check app tests scripts
```

If `.env` sets `LLM_PROVIDER` and `LLM_API_KEY`, tests that create plans call the real LLM and run slowly.
Clear them for a fast offline run (PowerShell: `$env:LLM_PROVIDER=""; $env:LLM_API_KEY=""; pytest`).

CI runs the same tests, checks that migrations apply on Postgres, and builds the frontend.
The workflow file is in `ci/ci.yml`; move it to `.github/workflows/ci.yml` before pushing so GitHub picks it up.

## Repository layout

```
backend/
  app/
    core/            config, database, security (Argon2, JWT), shared vocab, auth dependency
    modules/
      users/         register, login, profile, subscription            Member 1
      assessment/    intake + deterministic scope check                Member 1
      catalog/       approved exercise table and read API              Member 2
      recommendation/ rule-based filtering + fallback planner          Member 2
      plans/         recovery plan + weekly schedule                   Member 2
      ai/            planner interface + output validation layer       Members 2 and 4
      sessions/      session logging (stub)                            Member 3
      progress/      weekly metrics                                    Member 3
      reevaluation/  priority-ordered decision rules                   Member 3
      notifications/ reminders and alerts (read only for now)
      clinician/     anonymized cohort analytics + patient drill-down for PTs
      model_config/  versioned thresholds + AI prompt instructions, rollback
    main.py          mounts every module router under /api
  alembic/           migrations (0001 creates all 13 tables)
  config/thresholds.yaml   default thresholds; seeds config version 1
  data/catalog.json        approved catalog generated from free-exercise-db
  data/catalog_overrides.yaml   manual curation on top of the auto tags
  scripts/import_catalog.py    import, tag, coverage report
  scripts/create_clinician.py  create or promote a physical therapist account
  scripts/seed_synthetic_patients.py   fake patients for dashboard demos
  tests/
frontend/            React app: sign in, intake, plan, progress; /clinician dashboard
docs/
  clinician-dashboard.md   PT dashboard: access, anonymization, analytics, config versions
  api-contracts.md   endpoint and payload contracts between modules
  dataset-coverage.md   generated by the import script
```

## Where each proposal rule lives

| Proposal rule | Code | Tests |
|---|---|---|
| Out of scope: pain 7+, unsupported region, red flag | `assessment/scope.py` | `test_scope.py` |
| Starting difficulty from pain (5 to 6 is L1, 3 to 4 is L2, 0 to 2 is L3) | `assessment/scope.py` | `test_scope.py` |
| Filter by region, then limitations, then difficulty | `recommendation/filtering.py` | `test_filtering.py` |
| Fallback: lowest difficulty, then most activity matches | `recommendation/filtering.py` | `test_filtering.py` |
| AI output validation (ids, set/rep ranges, one-level change, intake values, numbers in explanations) | `ai/validation.py` | `test_ai_validation.py` |
| Invalid or unavailable AI uses fallback | `ai/planner.py` | `test_ai_validation.py` |
| Weekly completion, average post-session pain, week change, missed sessions | `progress/metrics.py` | `test_progress_metrics.py` |
| Reevaluation priority: refer, reduce, increase, reassess, continue | `reevaluation/rules.py` | `test_reevaluation.py` |
| Users cannot access each other's records | `core/deps.py` + per-user queries | `test_api.py` |

All numbers come from the active model config version, which a clinician can edit on the dashboard.
Version 1 is seeded from `backend/config/thresholds.yaml`.

| Dashboard rule | Code | Tests |
|---|---|---|
| Only clinicians can read cohort data; patients get 403 | `core/deps.py` (`require_clinician`) | `test_clinician.py` |
| No ids, emails, names, free text or per-patient dates leave the clinician API | `clinician/anonymize.py` | `test_clinician.py` |
| Config edits are validated; one active version; rollback | `model_config/service.py` | `test_model_config.py` |
| Each intake, plan, decision and AI call records its config version | `assessment/router.py`, `plans/router.py`, `reevaluation/service.py` | `test_model_config.py` |

## M1 status (Foundations, Sep 21 to Oct 4)

- [x] Repository structure, Docker Compose, CI workflow
- [x] API contracts between modules (`docs/api-contracts.md`)
- [x] Initial database schema and migration
- [x] YAML threshold configuration
- [x] free-exercise-db coverage review (`docs/dataset-coverage.md`)
- [x] Ahead of plan: auth, intake scope check, filtering, fallback plans, reevaluation rules, AI validator
- [ ] Move `ci/ci.yml` into `.github/workflows/`, push to GitHub, set up the Issues board, and confirm the repo runs on every member's machine

## Dataset review (M1 exit criterion)

145 of 876 free-exercise-db exercises pass the low-intensity filter. Region and level 1 coverage is fine
everywhere, but these cells have fewer than the 4 exercises a plan needs:

- shoulder level 3 (0)
- knee level 3 (3)
- ankle level 2 (3) and level 3 (0)

Options for the team: hand-tag more exercises in `catalog_overrides.yaml`, set
`filtering.difficulty_match: at_most` so higher levels can reuse easier exercises, or cap
shoulder and ankle at a lower level. Right now those cases return a 409 with a therapist recommendation
rather than a short plan.

The auto tagging is a heuristic and needs a human pass. Examples spotted already: "Flutter Kicks" needs a
bench even though the dataset lists "body only", and `cannot_lie_on_floor` may be over-matching on lower
back exercises (77 down to 23).

## Interpretations to confirm as a team

These were judgment calls where the proposal wording allows more than one reading. Each is one line in
the code or the YAML file, so they are easy to change.

1. **"Average pain rises by 2 or more points over two consecutive weeks"** is read as the latest weekly
   average minus the average from two weeks earlier.
2. **"Pain is stable or decreasing for two consecutive weeks"** (increase rule) is read as: the last two
   weeks both have 80%+ completion and pain did not go up from the first to the second.
3. **"Pain has not decreased after six weeks"** compares the latest weekly average with intake pain.
4. **Difficulty mapping**: stretching keeps the dataset level (beginner 1, intermediate 2); strength is one
   level higher (beginner 2, intermediate 3). Expert, plyometric, and high-impact exercises are excluded.
5. **Fallback sets and reps** use the bottom of each catalog range, the most conservative choice.
6. **Schedule** is 3 sessions a week for 4 weeks (until the reassess rule), spread across each week.
