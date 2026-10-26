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
    stops.agent_stopped(title, outcome, detail)   # either of those, or None
    stops.agent_action(outcome)           # what that stop offers: 'status' or 'retry'
    stops.took(attempts)                  # {'jobs', 'seconds', 'dollars'} of a run's jobs
    stops.cost(seconds, dollars)          # "12 minutes and about $1.40"
    stops.redone(first, steps, seconds, dollars)   # what a change draws again, priced

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
STATUS = 'status'   # an agent that could not be used: its stop opens Status, which says why
# What a stop's one action is called on the page.
ACTION_LABELS = {'retry': 'Try again', MORE_TIME: MORE_TIME_LABEL, STATUS: 'Open Status'}
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


def took(attempts) -> dict:
    """What a run's jobs took together: how many, their seconds, and their dollars only
    when every one of them reported a number."""
    attempts = [one for one in attempts or () if isinstance(one, dict)]
    seconds = sum(float(one.get('seconds') or 0) for one in attempts)
    priced = [one.get('dollars') for one in attempts]
    dollars = (round(sum(float(d) for d in priced), 2)
               if attempts and all(isinstance(d, (int, float)) and not isinstance(d, bool)
                                   for d in priced) else None)
    return {'jobs': len(attempts), 'seconds': seconds, 'dollars': dollars}


def cost(seconds, dollars) -> str:
    """Time and money as a person says them: "12 minutes and about $1.40", or the time and
    that the assistant reported no cost. A cost of nothing is never said as "$0.00": none
    reported is said so, and a few tenths of a cent are less than $0.01."""
    if dollars is None or float(dollars) <= 0:
        return f'{lasted(seconds)}; the assistant reported no cost'
    if float(dollars) < 0.005:
        return f'{lasted(seconds)} and less than $0.01'
    return f'{lasted(seconds)} and about ${float(dollars):,.2f}'


def redone(first: str, steps: int, seconds, dollars, after: str = 'every step after it') -> str:
    """What an Ask for changes sheet says before it is sent: what is drawn again, from
    `first` on, and what those steps took the last time they ran. `seconds` is None when
    this computer has no record of one of them. `after` says which other steps are counted:
    every one after it, or, where that is what runs again, what is written from it."""
    many = steps > 1
    said = f'Drawn again: {first}' + (f' and {after}, {steps} steps' if many else '')
    if seconds is None:
        return said + f'; this computer has no record of what {"they" if many else "it"} cost.'
    return said + f'. Last time {"they" if many else "it"} took {cost(seconds, dollars)}.'


def floor(limit) -> float:
    """The least a job is started with: FLOOR, or a quarter of a small limit."""
    return min(FLOOR, max(0.0, float(limit or 0)) / 4)


def timed_out(label: str, seconds, tries: int, thing: str = 'run', own: bool = False) -> str:
    """What a stop says of a step whose last try ran out of the time a step may take.
    `own` says the limit was the run's own, given by more time, not the one in Settings."""
    said = (f'{label} ran out of the time a step may take: it was stopped after '
            f'{lasted(seconds)}.' if tries <= 1 else
            f'{label} ran out of the time a step may take: its last try was stopped after '
            f'{lasted(seconds)}, and it did not work in {tries} tries.')
    if own:
        return said + (f' That limit, now {lasted(seconds)} a step for this {thing}, was given '
                       f'when you asked for more time; the limit for every {thing} is in '
                       f'{SETTINGS}.')
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
    """True for a `limit` an agent's account set: a usage or rate limit, not the job's.
    Known from the agent's own report (`account`, as Claude Code's status 429), or else
    from its words."""
    return (getattr(outcome, 'reason', None) == 'limit' and not getattr(outcome, 'budget', False)
            and (bool(getattr(outcome, 'account', False))
                 or any(mark in str(getattr(outcome, 'detail', '')).lower() for mark in ACCOUNT)))


def account_stop(title: str) -> str:
    """What a stop says of an agent whose account reached a usage or rate limit. Check
    this computer cannot show such a limit, so it is not named."""
    return f"{title}'s account reached a usage or rate limit. Wait until it resets, then Try again."


def agent_stopped(title: str, outcome, detail: str) -> str | None:
    """What a stop says when the agent itself is why a job did not finish: its account
    reached a limit, or it could not be used. None when it is not."""
    if account_limit(outcome):
        return account_stop(title)
    if getattr(outcome, 'reason', None) == 'unavailable':
        return unusable(title, detail)
    return None


def agent_action(outcome) -> str:
    """The action a stop offers when the agent is why a job did not finish: Open Status for
    one that could not be used, where Check this computer says what it needs; else Try
    again."""
    return STATUS if getattr(outcome, 'reason', None) == 'unavailable' else 'retry'


def unusable(title: str, detail: str) -> str:
    """What a stop says of an agent that could not be used: not installed, not signed in,
    out of reach or refused by its account."""
    said = ' '.join(str(detail or '').split())
    return (f'{title} could not be used.' + (f' {said}' if said else '')
            + ' Check this computer, on the Status screen, says what it needs.')
