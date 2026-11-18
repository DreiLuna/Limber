# Hosted course demo

The root Dockerfile builds the Vite client and serves it with FastAPI from one
origin. `/camera` and `/progress` work on direct navigation; `/api` retains JSON
routing. HTTPS is supplied by the host. Startup migrates Postgres, loads the
curated catalog and starts Uvicorn. No development server or reload worker is
used. A unique JWT secret of at least 32 characters is mandatory. Email delivery
and AI planning are disabled in the deployment template.

`render.yaml` prepares a free demo web service and Postgres database in the same
region, a generated signing secret, `/api/health` checks and deployments after
CI passes. It does not create a deployment by existing in GitHub. Docker itself
is not installed in the development workspace, so the container build must be
verified by CI/hosting. The API and built-client routing have automated tests.

After teammate review and merge, connect this repository to a Render account,
create a Blueprint from `render.yaml` and inspect the proposed resources before
applying it. Do not select paid plans without the account owner's agreement.
The free demo database has provider limits and an expiry; confirm them in the
[free service documentation](https://render.com/docs/free) before depending on
it for the final presentation. Use fictional demonstration accounts rather than
collecting real patient information in a course demo.

The final delivery needs the returned HTTPS URL and a successful hosted smoke
test: health, signup/login, intake, plan, camera model loading, save and progress
reload. A deployment has not been created from this workspace; no hosted URL is
claimed. The deployment account and final public project name remain team
choices. Keep the existing branch protection and obtain teammate review before
merging; do not bypass review to deploy this branch.

Reference: [Render Blueprint specification](https://render.com/docs/blueprint-spec).
