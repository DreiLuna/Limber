"""Clinician dashboard API. Every route requires role "clinician" and returns anonymized data only."""
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_clinician
from app.core.vocab import BodyRegion
from app.modules.clinician import analytics
from app.modules.clinician import schemas as s
from app.modules.clinician.anonymize import resolve_pseudonym
from app.modules.model_config.models import ModelConfigVersion

router = APIRouter(prefix="/clinician", tags=["clinician"], dependencies=[Depends(require_clinician)])


def filters(
    start: date | None = Query(None, description="Inclusive start date (YYYY-MM-DD)"),
    end: date | None = Query(None, description="Inclusive end date (YYYY-MM-DD)"),
    region: BodyRegion | None = Query(None, description="Body region of the intake"),
    level: int | None = Query(None, ge=1, le=3, description="Starting difficulty of the intake"),
    version: int | None = Query(None, ge=1, description="Only records produced by this config version"),
    db: Session = Depends(get_db),
) -> analytics.Filters:
    if start and end and start > end:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "start must be on or before end")
    version_id = None
    if version is not None:
        version_id = db.scalar(select(ModelConfigVersion.id).where(ModelConfigVersion.version == version))
        if version_id is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"No config version {version}")
    return analytics.Filters(
        start=start, end=end, region=region.value if region else None, level=level,
        filter_version=version is not None, config_version_id=version_id, version=version,
    )


@router.get("/overview", response_model=s.Overview)
def overview(f: analytics.Filters = Depends(filters), db: Session = Depends(get_db)) -> s.Overview:
    return analytics.overview(db, f)


@router.get("/analytics/intake", response_model=s.IntakeAnalytics)
def intake(f: analytics.Filters = Depends(filters), db: Session = Depends(get_db)) -> s.IntakeAnalytics:
    return analytics.intake_analytics(db, f)


@router.get("/analytics/outcomes", response_model=s.OutcomeAnalytics)
def outcomes(f: analytics.Filters = Depends(filters), db: Session = Depends(get_db)) -> s.OutcomeAnalytics:
    return analytics.outcome_analytics(db, f)


@router.get("/analytics/rules", response_model=s.RuleAnalytics)
def rules(f: analytics.Filters = Depends(filters), db: Session = Depends(get_db)) -> s.RuleAnalytics:
    return analytics.rule_analytics(db, f)


@router.get("/analytics/ai", response_model=s.AIAnalytics)
def ai(f: analytics.Filters = Depends(filters), db: Session = Depends(get_db)) -> s.AIAnalytics:
    return analytics.ai_analytics(db, f)


@router.get("/analytics/by-version", response_model=list[s.VersionMetrics])
def by_version(f: analytics.Filters = Depends(filters), db: Session = Depends(get_db)) -> list[s.VersionMetrics]:
    """Headline metrics per config version. The version filter is ignored here."""
    return analytics.by_version(db, f)


@router.get("/patients", response_model=list[s.PatientSummary])
def patients(f: analytics.Filters = Depends(filters), db: Session = Depends(get_db)) -> list[s.PatientSummary]:
    return analytics.list_patients(db, f)


@router.get("/patients/{code}", response_model=s.PatientDetail)
def patient(code: str, db: Session = Depends(get_db)) -> s.PatientDetail:
    user_id = resolve_pseudonym(db, code.upper())
    if user_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown patient code")
    return analytics.patient_detail(db, user_id)
