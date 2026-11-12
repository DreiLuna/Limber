import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.models  # noqa: F401  (registers every table)
from app.core.config import get_settings
from app.modules.notifications.email_reminders import run_email_reminder_worker
from app.modules.assessment.router import router as assessment_router
from app.modules.catalog.router import router as catalog_router
from app.modules.notifications.router import router as notifications_router
from app.modules.plans.router import router as plans_router
from app.modules.progress.router import router as progress_router
from app.modules.reevaluation.router import router as reevaluation_router
from app.modules.sessions.router import router as sessions_router
from app.modules.users.router import router as users_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    worker = None
    if get_settings().email_reminders_enabled:
        worker = asyncio.create_task(run_email_reminder_worker())
    try:
        yield
    finally:
        if worker is not None:
            worker.cancel()
            with suppress(asyncio.CancelledError):
                await worker


app = FastAPI(title="LIMBER API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

api = APIRouter(prefix="/api")
for r in (users_router, assessment_router, catalog_router, plans_router,
          sessions_router, progress_router, reevaluation_router, notifications_router):
    api.include_router(r)


@api.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(api)
