"""Wall time is an interval union; assistant time is a sum, never a speed estimate."""
from datetime import datetime, timezone


def stamp(value):
    try:
        found = datetime.fromisoformat(value)
        return found.timestamp() if found.tzinfo else None
    except (TypeError, ValueError):
        return None


def account(started, attempts, workers=(), now=None):
    now = (now or datetime.now(timezone.utc)).timestamp()
    began = stamp(started)
    intervals, assistant, incomplete = [], 0.0, False
    for attempt in attempts:
        left, right = stamp(attempt.get('started_at')), stamp(attempt.get('ended_at'))
        seconds = attempt.get('seconds')
        if isinstance(seconds, (int, float)) and seconds >= 0:
            assistant += seconds
        if left is None or right is None or right < left:
            incomplete = True
            continue
        intervals.append((left, min(right, now)))
    for worker in workers:
        left = stamp(worker.get('started_at'))
        if left is None or left > now:
            incomplete = True
            continue
        intervals.append((left, now))
        assistant += now - left
    merged = []
    for left, right in sorted(intervals):
        left = max(left, began) if began is not None else left
        if right < left:
            continue
        if merged and left <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(right, merged[-1][1]))
        else:
            merged.append((left, right))
    active = sum(right - left for left, right in merged)
    elapsed = max(0, now - began) if began is not None else None
    return {'active_seconds': round(active, 1),
            'assistant_seconds': round(assistant, 1),
            'elapsed_seconds': round(elapsed, 1) if elapsed is not None else None,
            'not_working_seconds': round(max(0, elapsed - active), 1)
            if elapsed is not None and not incomplete else None,
            'incomplete': incomplete or began is None}
