"""Turns patient rows into anonymous records for the clinician dashboard.

Rules every clinician response follows:
  - patients are identified only by a pseudonym (P-XXXXXX), never id, email, or name;
  - timestamps are expressed as "day N since intake", not calendar dates;
  - free text (assessment description, session notes) and raw AI payloads are dropped;
  - only users with role "patient" are ever included.
"""
import hashlib
import hmac
import re
from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.modules.users.models import User

PSEUDONYM_PREFIX = "P-"
_CODE_RE = re.compile(r"^P-[0-9A-F]{6}$")


def _secret() -> bytes:
    s = get_settings()
    return (s.pseudonym_secret or s.jwt_secret).encode()


def pseudonym(user_id: int) -> str:
    """Stable, non-reversible code for a patient. Same id -> same code while the secret is unchanged."""
    digest = hmac.new(_secret(), f"patient:{user_id}".encode(), hashlib.sha256).hexdigest()
    return PSEUDONYM_PREFIX + digest[:6].upper()


def is_valid_code(code: str) -> bool:
    return bool(_CODE_RE.match(code))


def patient_ids(db: Session) -> list[int]:
    return list(db.scalars(select(User.id).where(User.role == "patient").order_by(User.id)))


def resolve_pseudonym(db: Session, code: str) -> int | None:
    """Map a pseudonym back to a patient id by recomputing codes (fine at MVP scale)."""
    if not is_valid_code(code):
        return None
    for uid in patient_ids(db):
        if hmac.compare_digest(pseudonym(uid), code):
            return uid
    return None


def day_offset(when: datetime | date | None, origin: datetime | date | None) -> int | None:
    """Whole days between the patient's intake and an event. Never returns the raw date."""
    if when is None or origin is None:
        return None
    a = when.date() if isinstance(when, datetime) else when
    b = origin.date() if isinstance(origin, datetime) else origin
    return (a - b).days


_KEEP_TAIL = {"red_flag", "unsupported_region", "client_error"}
_NUM_SEGMENT = re.compile(r"_-?\d+(\.\d+)?(?=_|$)")


def reason_key(reason: str) -> str:
    """Collapse a reason string to its rule key so values (pain levels, ids) aren't exposed.

    "pain_too_high:8" -> "pain_too_high", "red_flag:numbness" -> "red_flag:numbness" (flag kept,
    it's a fixed vocabulary), "session_pain_8" -> "session_pain",
    "avg_pain_rose_2_over_two_weeks" -> "avg_pain_rose_over_two_weeks".
    """
    if ":" in reason:
        head = reason.split(":", 1)[0]
        # These tails are fixed vocabulary or exception class names, not patient values.
        return reason if head in _KEEP_TAIL else head
    return _NUM_SEGMENT.sub("", reason)
