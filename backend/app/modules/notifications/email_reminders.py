"""Send scheduled-session reminder email through a configured SMTP account."""
import asyncio
import logging
import smtplib
import ssl
from datetime import timedelta
from email.message import EmailMessage

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import SessionLocal, utcnow
from app.modules.notifications.models import Notification
from app.modules.plans.models import RecoveryPlan, ScheduledSession
from app.modules.sessions.models import ExerciseSession
from app.modules.users.models import User

logger = logging.getLogger(__name__)


def _smtp_ready() -> bool:
    settings = get_settings()
    return bool(
        settings.email_reminders_enabled
        and settings.smtp_host
        and settings.smtp_username
        and settings.smtp_password.get_secret_value()
    )


def _send_email(recipient: str, scheduled_date) -> None:
    settings = get_settings()
    sender = settings.smtp_from or settings.smtp_username
    message = EmailMessage()
    message["Subject"] = "LIMBER session reminder"
    message["From"] = sender
    message["To"] = recipient
    message.set_content(
        "You have a LIMBER recovery session scheduled for "
        f"{scheduled_date:%A, %B %d}. Open {settings.app_base_url}/plan "
        "to follow your exercises and log your session."
    )

    context = ssl.create_default_context()
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as smtp:
        smtp.ehlo()
        smtp.starttls(context=context)
        smtp.ehlo()
        smtp.login(settings.smtp_username, settings.smtp_password.get_secret_value())
        smtp.send_message(message)


def deliver_due_reminder_emails(db: Session, now=None) -> int:
    """Send unsent reminders within 24 hours of an active plan session."""
    if not _smtp_ready():
        return 0

    current = now or utcnow()
    due_limit = current + timedelta(hours=24)
    already_logged = exists(select(ExerciseSession.id).where(
        ExerciseSession.scheduled_session_id == ScheduledSession.id
    ))
    rows = db.execute(
        select(Notification, User.email, ScheduledSession.scheduled_date)
        .join(ScheduledSession, Notification.scheduled_session_id == ScheduledSession.id)
        .join(RecoveryPlan, ScheduledSession.plan_id == RecoveryPlan.id)
        .join(User, Notification.user_id == User.id)
        .where(
            Notification.kind == "reminder",
            Notification.email_sent_at.is_(None),
            Notification.send_at <= due_limit,
            ScheduledSession.scheduled_date >= current.date(),
            RecoveryPlan.status == "active",
            ~already_logged,
        )
        .order_by(Notification.send_at, Notification.id)
    ).all()

    sent = 0
    for notification, recipient, scheduled_date in rows:
        try:
            _send_email(recipient, scheduled_date)
        except (OSError, smtplib.SMTPException):
            logger.exception("Could not send email reminder for notification %s", notification.id)
            continue

        notification.email_sent_at = current
        db.commit()
        sent += 1
        logger.info("Sent email reminder for notification %s", notification.id)
    return sent


async def run_email_reminder_worker() -> None:
    settings = get_settings()
    if not _smtp_ready():
        logger.warning("Email reminders are enabled but SMTP credentials are incomplete; worker is stopped")
        return

    logger.info("Email reminder worker started")
    while True:
        try:
            await asyncio.to_thread(_deliver_due_reminder_emails)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Email reminder worker failed; it will retry on the next cycle")
        await asyncio.sleep(max(30, settings.email_reminder_poll_seconds))


def _deliver_due_reminder_emails() -> None:
    with SessionLocal() as db:
        deliver_due_reminder_emails(db)
