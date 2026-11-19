#!/bin/sh
set -eu
python -c 'import os; key=os.environ.get("JWT_SECRET", ""); assert len(key) >= 32 and key != "change-me-in-.env", "Set a unique JWT_SECRET of at least 32 characters"'
alembic upgrade head
python scripts/import_catalog.py --load-only
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
