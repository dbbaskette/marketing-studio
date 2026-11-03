"""What an assistant does while it works: the lines a page shows live, and a log per project.

What a caller needs to know
---------------------------
    lines = activity_log.Lines()                 # give lines.append as agents' activity=
    run.workers[ident] = {'label': ..., 'started_at': ..., 'lines': lines}
    activity_log.live(run.workers.items())       # running jobs, as the page shows them
    entry = activity_log.entry('Investigating research area 1', 'research:investigate-1-a',
                               started_at, activity_log.ending(outcome), lines,
                               detail=outcome.detail)
    with engine.files:                           # the studio's existing files lock
        activity_log.append(project / 'work' / activity_log.FILE, entry)
    activity_log.view(project / 'work' / activity_log.FILE)   # newest first, for the page

- A line is the plain sentence `agents` makes of one thing an assistant did ("Searching the
  web: …", "Reading saved source S3"), with the time it was said. Nothing else is kept:
  never a raw event, a prompt, a task, source text, a token count or a credential. A line
  that is itself JSON is dropped, and every line is clipped to LINE_LENGTH characters.
- `Lines` keeps the newest LINES lines of a running job, the oldest dropped first, and how
  many were said in all. It is safe to append to from the worker's thread while the page
  reads it from another.
- `live` is what a page is sent for each running job: its label, when it started, its latest
  line as `now`, and its lines so far, oldest first, each `{'at', 'text'}`.
- The log is a JSON Lines file, one finished job per line, newest last. It keeps the newest
  JOBS jobs. `append` adds one and trims the file only once it holds JOBS + SLACK, so it is
  one short write almost every time. Call it holding the studio's files lock; no lock is
  held while an assistant runs, because a job is logged only after it ended.
- A job ends `finished`, `failed`, `stopped`, `timeout` (out of time) or `limit`, as
  `ending` reads an agents.Outcome. `WORDS` are those endings in plain words.
- `view` reads the log newest first. A project with no log, or with one that cannot be read,
  has no jobs, and `empty` says "No activity recorded yet."
"""
from __future__ import annotations

import json
import os
import secrets
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

FILE = 'activity-log.jsonl'
LINES = 200             # lines kept for one job, live and in the log
JOBS = 200              # finished jobs a project's log keeps
SLACK = 20              # jobs over JOBS before the file is trimmed
LINE_LENGTH = 240       # characters in one line
DETAIL_LENGTH = 300     # characters in the sentence that says why a job did not finish
LABEL_LENGTH = 160
ENDINGS = ('finished', 'failed', 'stopped', 'timeout', 'limit')
WORDS = {'finished': 'Finished', 'failed': 'Failed', 'stopped': 'Stopped',
         'timeout': 'Out of time', 'limit': 'Reached a limit'}
EMPTY = 'No activity recorded yet.'


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
    """The running jobs as a page shows them: `(ident, worker)` pairs, where a worker has
    `label`, `started_at` and `lines`."""
    shown = []
    for ident, worker in workers:
        lines = _lines(worker.get('lines'))
        held = worker.get('lines')
        shown.append({'id': ident, 'label': worker.get('label'),
                      'started_at': worker.get('started_at'),
                      'now': lines[-1] if lines else None, 'lines': lines,
                      'count': held.count if isinstance(held, Lines) else len(lines)})
    return shown


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
    data = path.read_bytes()
    if data.count(b'\n') <= jobs + SLACK:
        return
    kept = [one for one in data.splitlines(keepends=True) if one.strip()][-jobs:]
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
    """The log as a page shows it: finished jobs newest first, the jobs running now, and a
    sentence for a project with none."""
    jobs = read(path)
    return {'jobs': jobs, 'running': live(running),
            'empty': None if jobs else EMPTY, 'limit': JOBS, 'lines': LINES}
