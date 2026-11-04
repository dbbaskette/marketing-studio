"""What an assistant does while it works: the lines a page shows live, and a log per project.

What a caller needs to know
---------------------------
    lines = activity_log.Lines()                 # give lines.append as agents' activity=
    run.workers[ident] = {'label': ..., 'started_at': ..., 'lines': lines}
    activity_log.live(run.workers.items())       # running jobs, as a page polls them
    activity_log.running_lines(run.workers.items(), ident, since)   # one job's lines, opened
    entry = activity_log.entry('Investigating research area 1', 'research:investigate-1-a',
                               started_at, activity_log.ending(outcome), lines,
                               detail=outcome.detail)
    with engine.files:                           # the studio's existing files lock
        activity_log.append(project / 'work' / activity_log.FILE, entry)
    activity_log.view(project / 'work' / activity_log.FILE)   # newest first, without lines
    activity_log.entry_lines(project / 'work' / activity_log.FILE, entry_id)   # one entry's

- A line is the plain sentence `agents` makes of one thing an assistant did ("Searching the
  web: …", "Reading saved source S3"), with the time it was said. Nothing else is kept:
  never a raw event, a prompt, a task, source text, a token count or a credential. A line
  that is itself JSON is dropped, and every line is clipped to LINE_LENGTH characters.
- `Lines` keeps the newest LINES lines of a running job, the oldest dropped first, and how
  many were said in all. It is safe to append to from the worker's thread while the page
  reads it from another.
- `live` is what a page is sent on every poll for each running job: its label, when it
  started, its latest line as `now` and how many lines it has said, `count`; never the lines
  themselves, so a poll stays small. `running_lines(workers, ident, since)` gives one running
  job's lines from the `since`th on, oldest first, each `{'at', 'text'}`: the page asks for
  them only while its Show activity is open, and only for the lines it has not had.
- The log is a JSON Lines file, one finished job per line, newest last. It keeps the newest
  JOBS jobs. `append` adds one and trims the file only once it holds JOBS + SLACK, so it is
  one short write almost every time. Call it holding the studio's files lock; no lock is
  held while an assistant runs, because a job is logged only after it ended.
- A job ends `finished`, `failed`, `stopped`, `timeout` (out of time) or `limit`, as
  `ending` reads an agents.Outcome. `WORDS` are those endings in plain words.
- `view` reads the log newest first, each job with its `steps` (how many lines it kept) but
  without the lines; `entry_lines` gives one job's lines when the page opens it. A project
  with no log, or with one that cannot be read, has no jobs, and `empty` says "No activity
  recorded yet."
"""
from __future__ import annotations

import json
import os
import secrets
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from .research_timing import account, stamp

FILE = 'activity-log.jsonl'
LINES = 200             # lines kept for one job, live and in the log
JOBS = 200              # finished jobs a project's log keeps
SLACK = 20              # jobs over JOBS before the file is trimmed
# Bytes under which the log is not re-read to be counted. The smallest entry is about 140
# bytes, so as many as about 215 can fit below this: the file stays bounded because it is
# trimmed to JOBS once it is over SMALL and holds more than JOBS + SLACK, and `read` gives at
# most JOBS whatever it holds.
SMALL = 30_000
LINE_LENGTH = 240       # characters in one line
DETAIL_LENGTH = 300     # characters in the sentence that says why a job did not finish
LABEL_LENGTH = 160
ENDINGS = ('finished', 'failed', 'stopped', 'timeout', 'limit')
WORDS = {'finished': 'Finished', 'failed': 'Failed', 'stopped': 'Stopped',
         'timeout': 'Out of time', 'limit': 'Reached a limit'}
EMPTY = 'No activity recorded yet.'
CHECKPOINTS = ('accepted', 'queued', 'working', 'output-saved', 'checking', 'ready', 'stopped', 'spending-warning')


def now() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def clip(text, length: int = LINE_LENGTH) -> str:
    text = ' '.join(str(text).split())
    return text if len(text) <= length else text[:length - 1] + '…'


def plain(text) -> str | None:
    """A line fit to keep: plain words, clipped. None for nothing, or for raw JSON."""
    if not isinstance(text, str):
        return None
    said = clip(text)
    if not said:
        return None
    if said[0] in '{[':
        try:
            json.loads(text)
        except ValueError:
            pass
        else:
            return None
    return said


class Lines:
    """The newest lines of one running job, each with the time it was said."""

    def __init__(self, limit: int = LINES, clock=now):
        self._kept: deque = deque(maxlen=limit)
        self._lock = threading.Lock()
        self._clock = clock
        self.count = 0

    def append(self, text) -> None:
        said = plain(text)
        if said is None:
            return
        with self._lock:
            self._kept.append({'at': self._clock(), 'text': said})
            self.count += 1

    def items(self) -> list[dict]:
        """Every line kept, oldest first."""
        with self._lock:
            return [dict(line) for line in self._kept]

    def since(self, start: int) -> tuple[list[dict], int]:
        """The lines kept from the `start`th said on, oldest first, and how many were said.
        Lines dropped for the cap are not given again."""
        with self._lock:
            first = self.count - len(self._kept)
            kept = list(self._kept)[max(0, start - first):] if start < self.count else []
            return [dict(line) for line in kept], self.count

    def latest(self) -> dict | None:
        with self._lock:
            return dict(self._kept[-1]) if self._kept else None

    def __len__(self) -> int:
        with self._lock:
            return len(self._kept)

    def __iter__(self):
        return iter(self.items())


def _lines(found) -> list[dict]:
    """Lines as `{'at', 'text'}`, from a Lines, or a list of those or of plain strings."""
    if isinstance(found, Lines):
        return found.items()
    kept = []
    for line in found or ():
        if isinstance(line, dict):
            said = plain(line.get('text'))
            at = line.get('at') if isinstance(line.get('at'), str) else None
        else:
            said, at = plain(line), None
        if said is not None:
            kept.append({'at': at, 'text': said})
    return kept


def live(workers) -> list[dict]:
    """The running jobs as a page polls them: `(ident, worker)` pairs, where a worker has
    `label`, `started_at` and `lines`. Each is {id, label, started_at, now, count}."""
    shown = []
    for ident, worker in workers:
        held = worker.get('lines')
        if isinstance(held, Lines):
            now, count = held.latest(), held.count
        else:
            lines = _lines(held)
            now, count = (lines[-1] if lines else None), len(lines)
        shown.append({'id': ident, 'label': worker.get('label'),
                      'started_at': worker.get('started_at'), 'now': now, 'count': count})
    return shown


def running_lines(workers, ident: str, since: int = 0) -> dict:
    """One running job's lines from the `since`th on, for its open Show activity:
    {lines, count, start}, where `start` is the number of the first line given. A job that has
    ended has no lines here: its lines are in the log."""
    for name, worker in workers:
        if name != ident:
            continue
        held = worker.get('lines')
        if isinstance(held, Lines):
            lines, count = held.since(max(0, int(since)))
        else:
            every = _lines(held)
            lines, count = every[max(0, int(since)):], len(every)
        return {'lines': lines, 'count': count, 'start': count - len(lines), 'running': True}
    return {'lines': [], 'count': 0, 'start': 0, 'running': False}


def ending(outcome) -> str:
    """How a job ended, from an agents.Outcome: one of ENDINGS."""
    if getattr(outcome, 'finished', False):
        return 'finished'
    reason = getattr(outcome, 'reason', None)
    return reason if reason in ('stopped', 'timeout', 'limit') else 'failed'


def entry(label: str, step: str, started_at: str | None, ended: str, lines,
          detail: str | None = None, ended_at: str | None = None) -> dict:
    """One finished job for the log. `detail` is kept only for a job that did not finish."""
    if ended not in ENDINGS:
        raise ValueError('A job ends one of: ' + ', '.join(ENDINGS) + '.')
    every = _lines(lines)
    kept = every[-LINES:]
    held = lines.count if isinstance(lines, Lines) else len(every)
    found = {'id': secrets.token_hex(6), 'label': clip(label or step or 'A job', LABEL_LENGTH),
             'step': clip(step or '', LABEL_LENGTH), 'started_at': started_at,
             'ended_at': ended_at or now(), 'outcome': ended, 'lines': kept,
             'dropped': max(0, held - len(kept))}
    said = plain(detail) if ended != 'finished' and detail else None
    if said:
        found['detail'] = clip(said, DETAIL_LENGTH)
    return found


def append(path, found: dict, jobs: int = JOBS) -> None:
    """Add one finished job to the log at `path`, keeping the newest `jobs`. Call it holding
    the studio's files lock."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(found, ensure_ascii=False, separators=(',', ':')) + '\n'
    with open(path, 'a', encoding='utf-8') as log:
        log.write(line)
    if path.stat().st_size < SMALL:
        return
    data = path.read_bytes()
    rows = [one for one in data.splitlines(keepends=True) if one.strip()]
    def event(row):
        try:
            item = json.loads(row)
            return item.get('checkpoint') if isinstance(item, dict) else None
        except ValueError:
            return None
    milestones = any(event(row) in CHECKPOINTS for row in rows)
    if len(rows) <= jobs * (2 if milestones else 1) + SLACK:
        return
    if milestones:
        ordinary = [i for i, row in enumerate(rows) if event(row) not in CHECKPOINTS][-jobs:]
        all_points = [i for i, row in enumerate(rows) if event(row) in CHECKPOINTS]
        accepted = next((i for i in reversed(all_points) if event(rows[i]) == 'accepted'), None)
        first_output = next((i for i in all_points if accepted is not None and i >= accepted
                             and event(rows[i]) == 'output-saved'), None)
        pins = {i for i in (accepted, first_output) if i is not None}
        points = sorted(pins | set([i for i in all_points if i not in pins][-(jobs - len(pins)):]))
        kept = [rows[i] for i in sorted(ordinary + points)]
    else:
        kept = rows[-jobs:]
    trimmed = path.with_name(f'.{path.name}.{secrets.token_hex(4)}')
    try:
        trimmed.write_bytes(b''.join(kept))
        os.replace(trimmed, path)
    finally:
        trimmed.unlink(missing_ok=True)


def read(path) -> list[dict]:
    """The jobs in a log, newest first. A line that cannot be read is passed over."""
    try:
        data = Path(path).read_text(encoding='utf-8', errors='replace')
    except OSError:
        return []
    found = []
    for line in data.splitlines():
        try:
            job = json.loads(line)
        except ValueError:
            continue
        if isinstance(job, dict) and job.get('outcome') in ENDINGS:
            found.append({**job, 'lines': _lines(job.get('lines')),
                          'words': WORDS[job['outcome']]})
    return found[::-1][:JOBS]


def view(path, running=()) -> dict:
    """The log as a page shows it: finished jobs newest first, each without its lines but with
    how many it kept (`steps`), the jobs running now, and a sentence for a project with none."""
    running = list(running)
    jobs = [{**{key: value for key, value in job.items() if key != 'lines'},
             'steps': len(job['lines'])} for job in read(path)]
    warnings = [event['unit'] for event in checkpoints(path) if event['checkpoint'] == 'spending-warning']
    return {**({'spending_warnings': warnings} if warnings else {}), 'jobs': jobs, 'running': live(running),
            'empty': None if jobs else EMPTY, 'limit': JOBS, 'lines': LINES,
            'timing': timing(path, jobs, running)}


def checkpoints(path):
    """Bounded, allowlisted milestones in the existing private activity journal."""
    try:
        lines = Path(path).read_text(encoding='utf-8').splitlines()
    except (OSError, UnicodeError):
        return []
    found = []
    for line in lines:
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict) and item.get('checkpoint') in CHECKPOINTS and stamp(item.get('at')) is not None:
            found.append(item)
    accepted = next((i for i in reversed(range(len(found)))
                     if found[i]['checkpoint'] == 'accepted'), None)
    first = next((i for i in range(accepted or 0, len(found))
                  if accepted is not None and found[i]['checkpoint'] == 'output-saved'), None)
    pins = {i for i in (accepted, first) if i is not None}
    kept = pins | set([i for i in range(len(found)) if i not in pins][-(JOBS - len(pins)):])
    return [found[i] for i in sorted(kept)]


def checkpoint(path, event, unit='', at=None):
    """Record a real boundary, under the caller's existing files lock, best effort.

    No raw model event, prompt, source or error belongs here. Browsing never calls this.
    Saved intermediate output is distinct from completed verification or user approval.
    """
    if event not in CHECKPOINTS:
        raise ValueError('Choose a supported activity checkpoint.')
    try:
        latest = checkpoints(path)
        if at is None and latest and (latest[-1]['checkpoint'], latest[-1].get('unit')) == (event, clip(unit, LABEL_LENGTH)):
            return
        append(path, {'checkpoint': event, 'unit': clip(unit, LABEL_LENGTH), 'at': at or now()})
    except Exception:
        pass


def observe(path, record):
    """Observe a just-saved native run, reusing its accepted/kept timestamps.

    Intake, gates and questions are not assistant output. Old records without the
    required times stay unknown. A watermark prevents saves/polls counting results twice.
    """
    try:
        held = checkpoints(path)
        accepted = record.get('started_at') or record.get('created')
        if not any(e['checkpoint'] == 'accepted' for e in held) and stamp(accepted) is not None:
            checkpoint(path, 'accepted', at=accepted)
        saved = {(e.get('unit'), e['at']) for e in held if e['checkpoint'] == 'output-saved'}
        seen = max((stamp(at) for _, at in saved), default=-1)
        outputs = []
        for unit, step in (record.get('steps') or {}).items():
            if unit == 'intake' or unit.startswith('gate:'):
                continue
            for attempt in step.get('attempts', step.get('tries', [])):
                ended = stamp(attempt.get('ended_at'))
                if attempt.get('outcome') == 'kept' and ended is not None and ended >= seen and (unit, attempt['ended_at']) not in saved:
                    outputs.append((ended, unit, attempt['ended_at']))
        for _, unit, at in sorted(outputs):
            checkpoint(path, 'output-saved', unit, at)
    except Exception:
        pass  # Timing must never make a successful save fail.


def timing(path, jobs=(), running=(), clock=None):
    """Measured operation timing; unknown boundaries are null, never guessed ETAs."""
    clock = clock or datetime.now(timezone.utc)
    events = [event for event in checkpoints(path) if event['checkpoint'] != 'spending-warning']
    accepted = next((e['at'] for e in reversed(events) if e['checkpoint'] == 'accepted'), None)
    began = stamp(accepted)
    if began is None:
        return None
    events = sorted((e for e in events if stamp(e['at']) >= began), key=lambda e: stamp(e['at']))
    attempts = [{'started_at': j.get('started_at'), 'ended_at': j.get('ended_at'),
                 'seconds': max(0, stamp(j['ended_at']) - stamp(j['started_at']))}
                for j in jobs if stamp(j.get('started_at')) is not None
                and stamp(j.get('ended_at')) is not None and stamp(j['started_at']) >= began]
    active = account(accepted, attempts, [w for _, w in running], now=clock)
    first = min((stamp(e['at']) for e in events if e['checkpoint'] == 'output-saved'), default=None)
    starts = [stamp(j['started_at']) for j in jobs if stamp(j.get('started_at')) is not None and stamp(j['started_at']) >= began]
    starts += [stamp(w['started_at']) for _, w in running if stamp(w.get('started_at')) is not None]
    waiting, queued = 0.0, 0.0
    for index, e in enumerate(events):
        if e['checkpoint'] not in ('ready', 'queued'):
            continue
        end = next((stamp(n['at']) for n in events[index + 1:]
                    if n['checkpoint'] in ('working', 'checking', 'stopped', 'ready', 'queued')), clock.timestamp())
        span = max(0, end - stamp(e['at']))
        if e['checkpoint'] == 'ready':
            waiting += span
        else:
            queued += span
    latest = events[-1] if events else {}
    check_intervals = []
    for i, e in enumerate(events):
        if e['checkpoint'] == 'checking':
            end = next((n['at'] for n in events[i + 1:] if n['checkpoint'] in
                        ('working', 'ready', 'stopped', 'queued')), clock.isoformat())
            check_intervals.append({'started_at': e['at'], 'ended_at': end})
    check_time = account(accepted, check_intervals, now=clock)['active_seconds'] if check_intervals else None
    return {'accepted_at': accepted, 'elapsed_seconds': active['elapsed_seconds'],
            'model_seconds': active['active_seconds'], 'assistant_seconds': active['assistant_seconds'],
            'check_seconds': check_time,
            'first_model_seconds': round(min(starts) - began, 1) if starts else None,
            'first_result_seconds': round(first - began, 1) if first is not None else None,
            'waiting_seconds': round(waiting, 1) if any(e['checkpoint'] == 'ready' for e in events) else None,
            'queue_seconds': round(queued, 1) if any(e['checkpoint'] == 'queued' for e in events) else None,
            'saved_units': len({e.get('unit') for e in events if e['checkpoint'] == 'output-saved'}),
            'phase': latest.get('checkpoint'), 'last_activity_at': latest.get('at'),
            'incomplete': active['incomplete']}


def entry_lines(path, ident: str) -> dict:
    """One finished job's lines, oldest first, for the page that opens it: {id, lines}."""
    for job in read(path):
        if job.get('id') == ident:
            return {'id': ident, 'lines': job['lines'], 'dropped': job.get('dropped', 0)}
    return {'id': ident, 'lines': [], 'dropped': 0, 'missing': True}
