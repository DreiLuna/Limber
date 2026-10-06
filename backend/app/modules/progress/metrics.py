"""Progress metrics computed from logged sessions. Pure functions so they are easy to test
and so the numbers the AI explains can always be checked against these values."""
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class SessionLog:
    week_index: int
    completed: bool
    pain_after: int


@dataclass(frozen=True)
class WeekStats:
    week_index: int
    completion_rate: float           # completed / scheduled, capped at 1.0
    avg_post_pain: float | None      # mean pain_after over completed sessions
    max_session_pain: int | None     # highest pain_after logged that week
    pain_change: float | None        # avg_post_pain minus previous week's
    missed_sessions: int


def compute_weekly_stats(
    sessions: Sequence[SessionLog], scheduled_per_week: dict[int, int]
) -> list[WeekStats]:
    by_week: dict[int, list[SessionLog]] = defaultdict(list)
    for s in sessions:
        by_week[s.week_index].append(s)

    stats: list[WeekStats] = []
    prev_avg: float | None = None
    for week in sorted(scheduled_per_week):
        scheduled = scheduled_per_week[week]
        logs = by_week.get(week, [])
        done = [s for s in logs if s.completed]
        completion = min(1.0, len(done) / scheduled) if scheduled else 0.0
        avg = round(sum(s.pain_after for s in done) / len(done), 2) if done else None
        max_pain = max((s.pain_after for s in logs), default=None)
        change = round(avg - prev_avg, 2) if avg is not None and prev_avg is not None else None
        stats.append(
            WeekStats(
                week_index=week,
                completion_rate=round(completion, 2),
                avg_post_pain=avg,
                max_session_pain=max_pain,
                pain_change=change,
                missed_sessions=max(0, scheduled - len(done)),
            )
        )
        if avg is not None:
            prev_avg = avg
    return stats
