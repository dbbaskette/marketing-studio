"""How research jobs are named and recorded, and what the last try at research took.

Part of the schema-2 Harness Research integration; studio_core.research_contract
re-exports every name here."""
import re


# The rounds of writing and independent checking one try at research may take.
ROUNDS = 3


# The names research jobs were recorded under before they were named for their round.
LEGACY_JOBS = ('research-author', 'research-review')


def job_name(phase, number):
    """What one research job is recorded as: `research:author-2`, `research:review-2`."""
    return f'research:{phase}-{number}'


def job_round(name):
    """(phase, round) of a research job's name, or None for another step's. A job recorded
    before rounds were named has round None."""
    if name in LEGACY_JOBS:
        return name.partition('-')[2], None
    parallel = re.fullmatch(r'research:(investigate|synthesize)-(\d+)(?:-area[123])?', str(name))
    if parallel:
        return parallel[1], int(parallel[2])
    head, _, rest = str(name).partition(':')
    phase, _, number = rest.rpartition('-')
    if head == 'research' and phase in ('author', 'review') and number.isdigit():
        return phase, int(number)
    return None


def doing_words(phase, number):
    """What a research job is doing, as the page says it while the job runs."""
    of = f'round {number} of {ROUNDS}'
    if phase == 'author':
        return (f'Investigating sources and writing the report ({of})' if number == 1
                else f'Correcting the research after its independent check ({of})')
    return (f'Independently checking the research ({of})' if number == 1
            else f'Independently checking the corrected research ({of})')


def last_rounds(attempts_by_name):
    """What the last try at the research took: {'rounds', 'jobs', 'seconds', 'dollars'}
    from the recorded tries of its jobs, given as {name: [attempt, ...]}. The last try
    begins with its last first round; jobs recorded before rounds were named all count.
    None when no research job is recorded."""
    tried = [(job_round(name), attempt) for name, attempts in attempts_by_name.items()
             if job_round(name) for attempt in attempts]
    if not tried:
        return None
    groups = [attempt for _, attempt in tried if attempt.get('research_attempt')]
    if groups:
        last = max(groups, key=lambda a: a.get('started_at') or '')['research_attempt']
        tried = [(found, attempt) for found, attempt in tried
                 if attempt.get('research_attempt') == last]
    starts = [attempt.get('started_at') or '' for (phase, number), attempt in tried
              if phase == 'author' and number == 1]
    since = max(starts) if starts else ''
    these = [(found, attempt) for found, attempt in tried
             if (attempt.get('started_at') or '') >= since]
    dollars = [attempt['dollars'] for _, attempt in these if attempt.get('dollars') is not None]
    return {'rounds': max([number or 0 for (_, number), _ in these] or [0]),
            'jobs': len(these),
            'seconds': round(sum(attempt.get('seconds') or 0 for _, attempt in these), 1),
            'dollars': round(sum(dollars), 4) if dollars else None}
