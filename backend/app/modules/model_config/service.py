"""Active model configuration: decision thresholds plus the editable part of the AI prompt.

`get_active_config()` is what the rest of the app reads. It returns the active
model_config_versions row, or the YAML defaults (id None) when there is no row yet or the
table can't be read, so pure rule tests and fresh databases keep working.

Edits are checked by `validate_thresholds` / `validate_instructions` before they are saved;
a clinician can tune numbers and wording but cannot produce a config the rules can't run on.
"""
import copy
import logging
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.config import load_default_thresholds
from app.core.database import SessionLocal
from app.core.vocab import RedFlag
from app.modules.model_config.models import ModelConfigVersion

logger = logging.getLogger(__name__)

# Regions the approved catalog actually covers. A config may drop one but never add another.
PLANNABLE_REGIONS = ("lower_back", "shoulder", "knee", "ankle")
MAX_INSTRUCTIONS_CHARS = 4000
_RESERVED_MARKERS = ("USER CONTEXT:", "ELIGIBLE:")

DEFAULT_PROMPT_INSTRUCTIONS = (
    "You are helping build a home exercise plan for a recovery app.\n"
    "Guidance:\n"
    "- Prefer exercises whose targets_activities match the user's activity difficulties.\n"
    "- Keep the rationale to one or two plain sentences."
)


@dataclass(frozen=True)
class ActiveConfig:
    id: int | None
    version: int | None
    thresholds: dict[str, Any]
    prompt_instructions: str


def default_config() -> ActiveConfig:
    """YAML defaults. Returns the cached dict itself (as get_thresholds always did); copy before mutating."""
    return ActiveConfig(None, None, load_default_thresholds(), DEFAULT_PROMPT_INSTRUCTIONS)


def get_active_config(db: Session | None = None) -> ActiveConfig:
    try:
        if db is not None:
            row = _active_row(db)
        else:
            with SessionLocal() as own:
                row = _active_row(own)
    except SQLAlchemyError:
        logger.debug("model_config_versions unavailable; using YAML defaults", exc_info=True)
        return default_config()
    if row is None:
        return default_config()
    return ActiveConfig(row.id, row.version, copy.deepcopy(row.thresholds), row.prompt_instructions)


def _active_row(db: Session) -> ModelConfigVersion | None:
    return db.scalar(select(ModelConfigVersion).where(ModelConfigVersion.is_active.is_(True)).limit(1))


# ---------- validation ----------

class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Scope(_Strict):
    supported_regions: list[str] = Field(min_length=1)
    max_starting_pain: int = Field(ge=0, le=10)
    red_flags: list[str]


class _Band(_Strict):
    min_pain: int = Field(ge=0, le=10)
    max_pain: int = Field(ge=0, le=10)
    level: int = Field(ge=1, le=3)


class _Filtering(_Strict):
    difficulty_match: Literal["exact", "at_most"]


class _Plan(_Strict):
    min_exercises: int = Field(ge=1, le=12)
    max_exercises: int = Field(ge=1, le=12)
    default_frequency_per_week: int = Field(ge=1, le=7)


class _Reevaluation(_Strict):
    referral_session_pain: int = Field(ge=1, le=10)
    referral_avg_pain_rise_two_weeks: float = Field(gt=0, le=10)
    referral_no_improvement_weeks: int = Field(ge=1, le=52)
    reduce_avg_pain_rise_one_week: float = Field(gt=0, le=10)
    reduce_completion_below: float = Field(ge=0, le=1)
    increase_completion_at_least: float = Field(ge=0, le=1)
    increase_stable_weeks: int = Field(ge=1, le=12)
    reassess_after_weeks: int = Field(ge=1, le=52)


class _AI(_Strict):
    timeout_seconds: int = Field(ge=1, le=120)
    max_difficulty_change: int = Field(ge=0, le=2)


class ThresholdsModel(_Strict):
    scope: _Scope
    difficulty_by_pain: list[_Band] = Field(min_length=1)
    filtering: _Filtering
    plan: _Plan
    reevaluation: _Reevaluation
    ai: _AI

    @model_validator(mode="after")
    def _cross_checks(self) -> "ThresholdsModel":
        errors: list[str] = []
        bad_regions = set(self.scope.supported_regions) - set(PLANNABLE_REGIONS)
        if bad_regions:
            errors.append(f"scope.supported_regions: not in the exercise catalog: {sorted(bad_regions)}")
        bad_flags = set(self.scope.red_flags) - {f.value for f in RedFlag}
        if bad_flags:
            errors.append(f"scope.red_flags: unknown flags {sorted(bad_flags)}")

        # Every in-scope starting pain (0..max_starting_pain) must map to exactly one level.
        covered: dict[int, int] = {}
        for i, band in enumerate(self.difficulty_by_pain):
            if band.min_pain > band.max_pain:
                errors.append(f"difficulty_by_pain[{i}]: min_pain is above max_pain")
            for p in range(band.min_pain, band.max_pain + 1):
                if p in covered:
                    errors.append(f"difficulty_by_pain: pain {p} is in more than one band")
                covered[p] = band.level
        missing = [p for p in range(self.scope.max_starting_pain + 1) if p not in covered]
        if missing:
            errors.append(f"difficulty_by_pain: no band for in-scope pain {missing}")

        if self.plan.min_exercises > self.plan.max_exercises:
            errors.append("plan: min_exercises is above max_exercises")
        r = self.reevaluation
        if r.reduce_completion_below > r.increase_completion_at_least:
            errors.append("reevaluation: reduce_completion_below is above increase_completion_at_least")
        if r.referral_session_pain <= self.scope.max_starting_pain:
            errors.append("reevaluation: referral_session_pain must be above scope.max_starting_pain")
        if errors:
            raise ValueError("; ".join(errors))
        return self


def validate_thresholds(raw: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    try:
        model = ThresholdsModel.model_validate(raw)
    except ValidationError as e:
        return None, [_fmt(err) for err in e.errors()]
    return model.model_dump(), []


def _fmt(err: dict[str, Any]) -> str:
    loc = ".".join(str(x) for x in err.get("loc", ()))
    msg = str(err.get("msg", "")).removeprefix("Value error, ")
    return f"{loc}: {msg}" if loc else msg


def validate_instructions(text: str) -> list[str]:
    errors = []
    if not text.strip():
        errors.append("prompt_instructions: must not be empty")
    if len(text) > MAX_INSTRUCTIONS_CHARS:
        errors.append(f"prompt_instructions: longer than {MAX_INSTRUCTIONS_CHARS} characters")
    for marker in _RESERVED_MARKERS:
        if marker in text:
            errors.append(f"prompt_instructions: may not contain the reserved marker {marker!r}")
    return errors


# ---------- versions ----------

class ConfigError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


def ensure_seed_version(db: Session) -> ModelConfigVersion:
    """Create version 1 from the YAML defaults if no version exists yet. Safe to call repeatedly."""
    existing = db.scalar(select(ModelConfigVersion).order_by(ModelConfigVersion.version).limit(1))
    if existing is not None:
        return existing
    d = default_config()
    row = ModelConfigVersion(
        version=1, thresholds=copy.deepcopy(d.thresholds), prompt_instructions=d.prompt_instructions,
        note="Initial defaults from config/thresholds.yaml", is_active=True,
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:  # another worker seeded first
        db.rollback()
        return db.scalar(select(ModelConfigVersion).where(ModelConfigVersion.version == 1))
    return row


def create_version(
    db: Session, *, thresholds: dict[str, Any], prompt_instructions: str, note: str,
    author_id: int | None, activate: bool = True,
) -> ModelConfigVersion:
    clean, errors = validate_thresholds(thresholds)
    errors += validate_instructions(prompt_instructions)
    if not note.strip():
        errors.append("note: describe why this change is being made")
    if errors:
        raise ConfigError(errors)
    ensure_seed_version(db)
    active = _active_row(db)
    next_version = (db.scalar(select(func.max(ModelConfigVersion.version))) or 0) + 1
    if activate:
        db.execute(update(ModelConfigVersion).values(is_active=False))
    row = ModelConfigVersion(
        version=next_version, thresholds=clean, prompt_instructions=prompt_instructions.strip(),
        note=note.strip(), author_id=author_id, parent_version=active.version if active else None,
        is_active=activate,
    )
    db.add(row)
    db.commit()
    return row


def activate_version(db: Session, version: int) -> ModelConfigVersion:
    row = db.scalar(select(ModelConfigVersion).where(ModelConfigVersion.version == version))
    if row is None:
        raise LookupError(version)
    db.execute(update(ModelConfigVersion).values(is_active=False))
    row.is_active = True
    db.commit()
    return row


def flatten(d: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """{"a": {"b": 1}} -> {"a.b": 1}. Lists are kept whole so band edits read as one change."""
    out: dict[str, Any] = {}
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out.update(flatten(v, key + "."))
        else:
            out[key] = v
    return out


def diff_thresholds(a: dict[str, Any], b: dict[str, Any]) -> list[dict[str, Any]]:
    fa, fb = flatten(a), flatten(b)
    return [
        {"path": k, "before": fa.get(k), "after": fb.get(k)}
        for k in sorted(set(fa) | set(fb)) if fa.get(k) != fb.get(k)
    ]
