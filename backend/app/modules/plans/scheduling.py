"""Turn a frequency into concrete session dates."""
from datetime import date, timedelta


def weekly_offsets(frequency_per_week: int) -> list[int]:
    """Spread sessions across a 7-day week, e.g. 3 -> [0, 2, 5]."""
    f = max(1, min(7, frequency_per_week))
    return sorted({int(i * 7 / f) for i in range(f)})


def build_schedule(start: date, frequency_per_week: int, weeks: int) -> list[tuple[date, int]]:
    """Return (date, week_index) pairs for the given number of weeks."""
    return [
        (start + timedelta(days=7 * w + d), w)
        for w in range(weeks)
        for d in weekly_offsets(frequency_per_week)
    ]
