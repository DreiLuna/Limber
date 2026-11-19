"""Clinician endpoints for viewing, editing, diffing and rolling back the model config."""
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import require_clinician
from app.modules.ai.planner import build_plan_prompt, locked_rules
from app.modules.model_config import schemas as s
from app.modules.model_config import service
from app.modules.model_config.models import ModelConfigVersion
from app.modules.users.models import User

router = APIRouter(prefix="/clinician/config", tags=["clinician-config"],
                   dependencies=[Depends(require_clinician)])

# Made-up exercises and context so the preview shows the full prompt without patient data.
_SAMPLE_ELIGIBLE = [
    {"id": "sample_bridge", "difficulty": 1, "sets": [1, 3], "reps": [8, 12], "targets_activities": ["bending"]},
    {"id": "sample_wall_sit", "difficulty": 1, "sets": [1, 3], "reps": [5, 10], "targets_activities": ["squatting"]},
]
_SAMPLE_CONTEXT = {"body_region": "knee", "pain_level": 4, "limitations": [],
                   "activity_difficulties": ["climbing_stairs"], "starting_difficulty": 2}


def _author(db: Session, author_id: int | None) -> str | None:
    if author_id is None:
        return None
    u = db.get(User, author_id)
    return (u.display_name or u.email) if u else None


def _summary(db: Session, row: ModelConfigVersion) -> dict[str, Any]:
    return {"version": row.version, "is_active": row.is_active, "note": row.note,
            "author": _author(db, row.author_id), "parent_version": row.parent_version,
            "created_at": row.created_at.isoformat()}


def _full(db: Session, row: ModelConfigVersion) -> dict[str, Any]:
    return {**_summary(db, row), "thresholds": row.thresholds, "prompt_instructions": row.prompt_instructions}


def _get(db: Session, version: int) -> ModelConfigVersion:
    row = db.scalar(select(ModelConfigVersion).where(ModelConfigVersion.version == version))
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"No config version {version}")
    return row


@router.get("/active", response_model=s.ActiveOut)
def active(db: Session = Depends(get_db)) -> s.ActiveOut:
    c = service.get_active_config(db)
    return s.ActiveOut(version=c.version, thresholds=c.thresholds, prompt_instructions=c.prompt_instructions,
                       locked_rules=locked_rules(c.thresholds))


@router.get("/defaults", response_model=s.ActiveOut)
def defaults() -> s.ActiveOut:
    """The YAML thresholds and built-in prompt, for a "reset to defaults" button."""
    d = service.default_config()
    return s.ActiveOut(version=None, thresholds=d.thresholds, prompt_instructions=d.prompt_instructions,
                       locked_rules=locked_rules(d.thresholds))


@router.get("/versions", response_model=list[s.VersionSummary])
def versions(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    service.ensure_seed_version(db)
    rows = db.scalars(select(ModelConfigVersion).order_by(ModelConfigVersion.version.desc()))
    return [_summary(db, r) for r in rows]


@router.get("/versions/{version}", response_model=s.VersionOut)
def version(version: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    return _full(db, _get(db, version))


@router.post("/versions", response_model=s.VersionOut, status_code=status.HTTP_201_CREATED)
def create(
    body: s.VersionCreate, user: User = Depends(require_clinician), db: Session = Depends(get_db)
) -> dict[str, Any]:
    try:
        row = service.create_version(
            db, thresholds=body.thresholds, prompt_instructions=body.prompt_instructions,
            note=body.note, author_id=user.id, activate=body.activate,
        )
    except service.ConfigError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, {"errors": e.errors}) from e
    return _full(db, row)


@router.post("/versions/{version}/activate", response_model=s.VersionSummary)
def activate(version: int, db: Session = Depends(get_db)) -> dict[str, Any]:
    """Make an existing version live. Rolling back is activating an older version."""
    _get(db, version)
    return _summary(db, service.activate_version(db, version))


@router.get("/diff", response_model=s.DiffOut)
def diff(base: int = Query(...), target: int = Query(...), db: Session = Depends(get_db)) -> s.DiffOut:
    a, b = _get(db, base), _get(db, target)
    return s.DiffOut(
        base=base, target=target,
        threshold_changes=[s.FieldChange(**c) for c in service.diff_thresholds(a.thresholds, b.thresholds)],
        prompt_changed=a.prompt_instructions != b.prompt_instructions,
        base_prompt=a.prompt_instructions, target_prompt=b.prompt_instructions,
    )


@router.post("/preview-prompt", response_model=s.PreviewOut)
def preview(body: s.PreviewRequest, db: Session = Depends(get_db)) -> s.PreviewOut:
    """Render the full prompt the AI would receive, using sample (non-patient) data."""
    errors = service.validate_instructions(body.prompt_instructions)
    t = service.get_active_config(db).thresholds
    if body.thresholds is not None:
        clean, t_errors = service.validate_thresholds(body.thresholds)
        errors += t_errors
        t = clean or t
    return s.PreviewOut(
        prompt=build_plan_prompt(_SAMPLE_ELIGIBLE, _SAMPLE_CONTEXT, t, body.prompt_instructions), errors=errors,
    )
