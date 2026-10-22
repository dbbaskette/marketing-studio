"""What a studio's run says when a step stops for one of its limits or for its assistant,
in the same words in Training Studio and Presentation Studio.

What a caller needs to know
---------------------------
    stops.MORE_TIME                       # the action that gives a run more time, and its label
    stops.floor(limit)                    # the least a job is started with, in dollars
    stops.timed_out(label, seconds, tries)            # a step that ran out of time
    stops.more_time(seconds)              # the step limit it gives: twice the one that ran out
    stops.spent(thing, dollars, limit, left, label, go)   # (what, kept) of a stop for money
    stops.account_limit(outcome)          # an agent's account refused: usage or rate limit
    stops.unusable(title, detail)         # an agent that could not be used, and where to look

- `thing` is what the studio makes, as a person calls it: 'training' or 'deck'.
- A step limit is the run's own: the one Settings gave it when it started or was last
  carried on, made larger by "more time". Settings keeps the limit for new runs.
- A job is never started with less than FLOOR dollars left to spend, or a quarter of a
  limit smaller than four times that, so that no job starts only to run out at once.
- Nothing here reads or writes anything.
"""
FLOOR = 0.50
MORE_TIME = 'more-time'
MORE_TIME_LABEL = 'Give it more time and try again'
SETTINGS = 'Settings, under Limits'
# Words in an agent's account of a `limit` that mean its account refused the job, not that
# the job reached a limit of its own.
ACCOUNT = ('usage limit', 'rate limit', 'quota')


def lasted(seconds) -> str:
    """A length of time as a person says it: 45 seconds, 15 minutes, 1 hour 30 minutes."""
    whole = round(seconds or 0)
    if whole < 60:
        return f"{whole} second{'' if whole == 1 else 's'}"
    minutes = round(whole / 60)
    if minutes < 60:
        return f"{minutes} minute{'' if minutes == 1 else 's'}"
    hours, minutes = divmod(minutes, 60)
    return (f"{hours} hour{'' if hours == 1 else 's'}"
            + (f" {minutes} minute{'' if minutes == 1 else 's'}" if minutes else ''))


def floor(limit) -> float:
    """The least a job is started with: FLOOR, or a quarter of a small limit."""
    return min(FLOOR, max(0.0, float(limit or 0)) / 4)


def timed_out(label: str, seconds, tries: int) -> str:
    """What a stop says of a step whose last try ran out of the time a step may take."""
    said = (f'{label} ran out of the time a step may take: it was stopped after '
            f'{lasted(seconds)}.' if tries <= 1 else
            f'{label} ran out of the time a step may take: its last try was stopped after '
            f'{lasted(seconds)}, and it did not work in {tries} tries.')
    return said + f' That limit, {lasted(seconds)} a step, is in {SETTINGS}.'


def more_time(seconds) -> int:
    """The step limit "more time" gives a run: twice the one that ran out."""
    return int(seconds) * 2


def spent(thing: str, dollars, limit, left=None, label: str | None = None,
          go: str = 'Carry on') -> tuple[str, str]:
    """(what, kept) of a stop because the run spent what it may before it asks. `left` is
    what it may still spend, when a job was not started for want of it; `label` names the
    step that was stopped mid-way because it spent what was left; `go` is how the page names
    the action that carries on."""
    dollars, limit = float(dollars or 0), float(limit or 0)
    asks = f'It stops and asks each time it has spent another ${limit:,.2f}.'
    if label:
        what = (f'{label} was stopped when this {thing} reached what it may spend: it has '
                f'spent ${dollars:,.2f}. {asks}')
        kept = ('Everything finished before this step is kept, and the step starts again '
                f'when you {go.lower()}.')
    elif left is not None and left > 0:
        what = (f'This {thing} has spent ${dollars:,.2f}, and the ${left:,.2f} it may still '
                f'spend is too little to start another step. {asks}')
        kept = 'Everything made so far is kept.'
    else:
        what = f'This {thing} has spent ${dollars:,.2f}. {asks}'
        kept = 'Everything made so far is kept.'
    return what, (f'{kept} {go} lets it spend up to another ${limit:,.2f}. To let it '
                  f'spend more before it asks, raise the limit in {SETTINGS}, then '
                  f'{go.lower()}.')


def account_limit(outcome) -> bool:
    """True for a `limit` an agent's account set: a usage or rate limit, not the job's."""
    return (getattr(outcome, 'reason', None) == 'limit' and not getattr(outcome, 'budget', False)
            and any(mark in str(getattr(outcome, 'detail', '')).lower() for mark in ACCOUNT))


def unusable(title: str, detail: str) -> str:
    """What a stop says of an agent that could not be used: not installed, not signed in,
    out of reach or refused by its account."""
    said = ' '.join(str(detail or '').split())
    return (f'{title} could not be used.' + (f' {said}' if said else '')
            + ' Check this computer, on the Status screen, says what it needs.')
