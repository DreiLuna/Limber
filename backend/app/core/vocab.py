"""Controlled vocabularies shared by intake, the catalog tags, and AI validation.
Keeping them in one place means the AI can only suggest values that exist here."""
from enum import StrEnum


class BodyRegion(StrEnum):
    LOWER_BACK = "lower_back"
    SHOULDER = "shoulder"
    KNEE = "knee"
    ANKLE = "ankle"
    # Accepted at intake so we can route them to a therapist, never planned for.
    NECK = "neck"
    HIP = "hip"
    WRIST = "wrist"
    OTHER = "other"


class RedFlag(StrEnum):
    NUMBNESS = "numbness"
    SWELLING = "swelling"
    LOSS_OF_FUNCTION = "loss_of_function"
    PAIN_UNRELATED_TO_ACTIVITY = "pain_unrelated_to_activity"


class Limitation(StrEnum):
    """Mobility limitations reported at intake. Catalog exercises carry the same
    tags as contraindications."""
    CANNOT_KNEEL = "cannot_kneel"
    CANNOT_LIE_ON_FLOOR = "cannot_lie_on_floor"
    LIMITED_OVERHEAD_REACH = "limited_overhead_reach"
    POOR_BALANCE = "poor_balance"
    NO_EQUIPMENT = "no_equipment"


class ActivityDifficulty(StrEnum):
    WALKING = "walking"
    CLIMBING_STAIRS = "climbing_stairs"
    SQUATTING = "squatting"
    BENDING = "bending"
    LIFTING = "lifting"
    REACHING_OVERHEAD = "reaching_overhead"
    SITTING_LONG = "sitting_long"
    RUNNING = "running"


class ReevaluationAction(StrEnum):
    REFER = "refer"
    REDUCE = "reduce"
    INCREASE = "increase"
    REASSESS = "reassess"
    CONTINUE = "continue"
