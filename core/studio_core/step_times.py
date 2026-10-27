"""How long a step usually takes on this computer, from its recent runs.

A studio keeps a small JSON file of step durations, `{key: [seconds, ...]}`, newest last,
through the store it passes in (`studio_core.drafting.store`). The estimate is the median
of the recent runs here, in minutes and at least one, or the studio's own guess when there
are none. Writing down a time is best effort: a problem never stops the step it timed.
"""

import statistics
from datetime import datetime, timezone

TIMES = 20  # step durations kept per step, for the estimate


def seconds(job):
    """How long a job ran, from `started_at` to `finished_at`, or None."""
    try:
        return (
            datetime.fromisoformat(job['finished_at']) - datetime.fromisoformat(job['started_at'])
        ).total_seconds()
    except (KeyError, TypeError, ValueError):
        return None


def note(store, path, key, took):
    """Keep how long a step took on this computer; best effort."""
    try:
        found = store.read_json(path) if path.is_file() else {}
        found = found if isinstance(found, dict) else {}
        kept = [value for value in found.get(key, []) if isinstance(value, (int, float))]
        found[key] = (kept + [round(took, 1)])[-TIMES:]
        store.write_json(path, found)
    except (ValueError, OSError):
        pass


def expected(store, path, key, guess):
    """How long a step usually takes, in minutes: the median of its recent runs here, at
    least one, else `guess` (a number, or a function that gives one)."""
    try:
        found = store.read_json(path) if path.is_file() else {}
        recent = [v for v in found.get(key, []) if isinstance(v, (int, float))]
    except (ValueError, OSError, AttributeError):
        recent = []
    if recent:
        return max(1, statistics.median(recent) / 60)
    return guess() if callable(guess) else guess


def left(expected, job, now=None):
    """About how many minutes are left, and whether the step under way has overrun.

    `expected` lists the minutes each step left is expected to take, the step under way
    first; `job` is that step's job (its `started_at`, or `created_at`, and `busy`)."""
    began = (job or {}).get('started_at') or (job or {}).get('created_at')
    now = now or datetime.now(timezone.utc)
    try:
        spent = (now - datetime.fromisoformat(began)).total_seconds() / 60
    except (TypeError, ValueError):
        spent = 0
    first, later = (expected[0], sum(expected[1:])) if expected else (0, 0)
    return {
        'minutes_left': max(1, round(max(0, first - spent) + later)),
        'over': bool(job and job.get('busy') and spent > first),
    }
