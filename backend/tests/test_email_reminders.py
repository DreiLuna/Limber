import smtplib
from datetime import UTC, date, datetime, time, timedelta
from uuid import uuid4

import pytest

from app.core.config import Settings
from app.core.database import SessionLocal
from app.modules.assessment.models import Assessment
from app.modules.notifications import email_reminders
from app.modules.notifications.models import Notification
from app.modules.plans.models import RecoveryPlan, ScheduledSession
from app.modules.sessions.models import ExerciseSession
from app.modules.users.models import User

NOW = datetime(2026, 11, 12, 9, tzinfo=UTC)


@pytest.fixture
def reminder_db():
    with SessionLocal() as db:
        yield db


def create_reminder(db, days_ahead=1):
    user = User(email=f"reminder-{uuid4()}@example.com", password_hash="unused")
    db.add(user)
    db.flush()

    assessment = Assessment(
        user_id=user.id,
        body_region="knee",
        pain_level=3,
        limitations=[],
        activity_difficulties=[],
        red_flags=[],
        in_scope=True,
        referral_reasons=[],
        starting_difficulty=1,
    )
    db.add(assessment)
    db.flush()

    scheduled_date = NOW.date() + timedelta(days=days_ahead)
    plan = RecoveryPlan(
        user_id=user.id,
        assessment_id=assessment.id,
        status="active",
        difficulty_level=1,
        frequency_per_week=3,
        source="fallback",
        start_date=NOW.date(),
    )
    db.add(plan)
    db.flush()

    scheduled = ScheduledSession(
        plan_id=plan.id,
        user_id=user.id,
        scheduled_date=scheduled_date,
        week_index=0,
    )
    db.add(scheduled)
    db.flush()

    notification = Notification(
        user_id=user.id,
        kind="reminder",
        message="Session reminder",
        send_at=datetime.combine(scheduled_date, time(9), tzinfo=UTC),
        read=False,
        scheduled_session_id=scheduled.id,
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)
    return user, plan, scheduled, notification


def enable_test_smtp(monkeypatch):
    settings = Settings(
        _env_file=None,
        email_reminders_enabled=True,
        smtp_username="sender@example.com",
        smtp_password="test-app-password",
    )
    monkeypatch.setattr(email_reminders, "get_settings", lambda: settings)


def test_sends_due_reminder_once(reminder_db, monkeypatch):
    user, _, _, notification = create_reminder(reminder_db)
    sent = []
    enable_test_smtp(monkeypatch)
    monkeypatch.setattr(email_reminders, "_send_email", lambda recipient, day: sent.append((recipient, day)))

    assert email_reminders.deliver_due_reminder_emails(reminder_db, now=NOW) >= 1
    reminder_db.refresh(notification)
    assert notification.email_sent_at.replace(tzinfo=UTC) == NOW
    assert (user.email, NOW.date() + timedelta(days=1)) in sent

    assert email_reminders.deliver_due_reminder_emails(reminder_db, now=NOW) == 0


def test_does_not_send_outside_reminder_window(reminder_db, monkeypatch):
    create_reminder(reminder_db, days_ahead=3)
    sent = []
    enable_test_smtp(monkeypatch)
    monkeypatch.setattr(email_reminders, "_send_email", lambda recipient, day: sent.append(recipient))

    assert email_reminders.deliver_due_reminder_emails(reminder_db, now=NOW) == 0
    assert sent == []


def test_skips_already_logged_session(reminder_db, monkeypatch):
    user, plan, scheduled, _ = create_reminder(reminder_db)
    reminder_db.add(ExerciseSession(
        user_id=user.id,
        plan_id=plan.id,
        scheduled_session_id=scheduled.id,
        completed=True,
        pain_before=3,
        pain_after=2,
        perceived_difficulty=2,
    ))
    reminder_db.commit()
    sent = []
    enable_test_smtp(monkeypatch)
    monkeypatch.setattr(email_reminders, "_send_email", lambda recipient, day: sent.append(recipient))

    assert email_reminders.deliver_due_reminder_emails(reminder_db, now=NOW) == 0
    assert sent == []


def test_smtp_failure_leaves_reminder_retryable(reminder_db, monkeypatch):
    _, _, _, notification = create_reminder(reminder_db)
    enable_test_smtp(monkeypatch)

    def fail_send(recipient, day):
        raise smtplib.SMTPException("temporary SMTP failure")

    monkeypatch.setattr(email_reminders, "_send_email", fail_send)

    assert email_reminders.deliver_due_reminder_emails(reminder_db, now=NOW) == 0
    reminder_db.refresh(notification)
    assert notification.email_sent_at is None


def test_email_reminders_stay_disabled_without_smtp_opt_in(reminder_db, monkeypatch):
    create_reminder(reminder_db)
    monkeypatch.setattr(email_reminders, "get_settings", lambda: Settings(_env_file=None))
    monkeypatch.setattr(email_reminders, "_send_email", lambda *_: pytest.fail("SMTP should not run"))

    assert email_reminders.deliver_due_reminder_emails(reminder_db, now=NOW) == 0


def test_builds_and_sends_gmail_message_with_starttls(monkeypatch):
    settings = Settings(
        _env_file=None,
        email_reminders_enabled=True,
        smtp_username="sender@example.com",
        smtp_password="test-app-password",
        smtp_from="reminders@example.com",
        app_base_url="http://localhost:5173",
    )
    monkeypatch.setattr(email_reminders, "get_settings", lambda: settings)
    captured = {}

    class FakeSMTP:
        def __init__(self, host, port, timeout):
            captured["connection"] = (host, port, timeout)

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def ehlo(self):
            captured["ehlo"] = captured.get("ehlo", 0) + 1

        def starttls(self, context):
            captured["tls_context"] = context

        def login(self, username, password):
            captured["login"] = (username, password)

        def send_message(self, message):
            captured["message"] = message

    monkeypatch.setattr(email_reminders.smtplib, "SMTP", FakeSMTP)

    email_reminders._send_email("patient@example.com", date(2026, 11, 13))

    message = captured["message"]
    assert captured["connection"] == ("smtp.gmail.com", 587, 20)
    assert captured["ehlo"] == 2
    assert captured["tls_context"] is not None
    assert captured["login"] == ("sender@example.com", "test-app-password")
    assert message["From"] == "reminders@example.com"
    assert message["To"] == "patient@example.com"
    assert message["Subject"] == "LIMBER session reminder"
    assert "Friday, November 13" in message.get_content()
    assert "http://localhost:5173/plan" in message.get_content()
