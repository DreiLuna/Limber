from app.modules.progress.metrics import SessionLog, compute_weekly_stats


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
