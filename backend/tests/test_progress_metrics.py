import pytest

from app.modules.progress.metrics import SessionLog, compute_weekly_stats


def log(week, completed=True, before=2, after=2, difficulty=1):
    return SessionLog(
        week_index=week,
        completed=completed,
        pain_before=before,
        pain_after=after,
        perceived_difficulty=difficulty,
    )

def rate(sessions, scheduled, week):
    stats = compute_weekly_stats(sessions, scheduled)
    return next(s for s in stats if s.week_index == week).completion_rate

def test_weekly_stats():
    sessions = [
        SessionLog(0, True, 4), SessionLog(0, True, 6), SessionLog(0, False, 7),
        SessionLog(1, True, 3), SessionLog(1, True, 3), SessionLog(1, True, 3),
    ]
    w0, w1, w2 = compute_weekly_stats(sessions, {0: 3, 1: 3, 2: 3})
    assert (w0.completion_rate, w0.avg_post_pain, w0.max_session_pain, w0.missed_sessions) == (0.67, 5.0, 7, 1)
    assert w0.pain_change is None
    assert (w1.completion_rate, w1.avg_post_pain, w1.pain_change, w1.missed_sessions) == (1.0, 3.0, -2.0, 0)
    assert (w2.completion_rate, w2.avg_post_pain, w2.missed_sessions) == (0.0, None, 3)


def test_completion_capped_at_one():
    (w,) = compute_weekly_stats([SessionLog(0, True, 2)] * 5, {0: 3})
    assert w.completion_rate == 1.0

# --- Pain adjustment --------------------------------------------------------

def test_pain_increase_reduces_completion():
    # base 1.0, change = 3, penalty = 3 * 0.1 * 2 = 0.6  ->  0.4
    sessions = [log(1, before=2, after=5, difficulty=2)]
    assert rate(sessions, {1: 1}, 1) == pytest.approx(0.4)


def test_pain_decrease_does_not_push_above_one():
    sessions = [log(1, before=6, after=2, difficulty=3)]
    assert rate(sessions, {1: 1}, 1) == 1.0


def test_no_pain_change_means_no_penalty_regardless_of_difficulty():
    sessions = [log(1, before=4, after=4, difficulty=10)]
    assert rate(sessions, {1: 1}, 1) == 1.0


def test_never_negative():
    # penalty = 10 * 0.1 * 10 = 10  ->  must clamp to 0.0 (currently -9.0)
    sessions = [log(1, before=0, after=10, difficulty=10)]
    assert rate(sessions, {1: 1}, 1) == 0.0


def test_always_within_bounds():
    cases = [(0, 10, 10), (10, 0, 10), (5, 5, 5), (0, 3, 1), (9, 1, 10)]
    for before, after, difficulty in cases:
        value = rate([log(1, before=before, after=after, difficulty=difficulty)], {1: 1}, 1)
        assert 0.0 <= value <= 1.0