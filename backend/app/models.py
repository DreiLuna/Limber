"""Import every module's models so Base.metadata sees all tables (used by Alembic and tests)."""
from app.modules.ai.models import AIOutputLog  # noqa: F401
from app.modules.assessment.models import Assessment  # noqa: F401
from app.modules.catalog.models import Exercise  # noqa: F401
from app.modules.notifications.models import Notification  # noqa: F401
from app.modules.plans.models import PlanItem, RecoveryPlan, ScheduledSession  # noqa: F401
from app.modules.progress.models import ProgressRecord  # noqa: F401
from app.modules.reevaluation.models import ReevaluationDecision  # noqa: F401
from app.modules.sessions.models import ExerciseSession, PainReport  # noqa: F401
from app.modules.users.models import Subscription, User  # noqa: F401
