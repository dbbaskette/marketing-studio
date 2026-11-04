"""What Blog Studio's assistant is doing while it works, and the Activity log it keeps.

What a caller needs to know
---------------------------
- One assistant job is one call to the assistant (`blog_worker.generate`). While it runs,
  its plain lines ("Started on …", "Searching the web: …") are kept with it, as Training
  Studio's and Presentation Studio's are (studio_core.activity_log). Nothing else is kept:
  never an event, the job's instructions, the blog's text or a token count.
- `Running(root)` is the register of a workspace's running jobs, one per engine. A job
  belongs to a subject: a blog (`blog(ident)`), a GEO report (`report(ident)`) or, for work
  for no blog or report (finding a page's text, angles for a new blog, learning a voice or
  a kind of post), the workspace (`WORKSPACE`).
- `within(running, subject, label, step)` around work makes each assistant call inside it,
  on this thread or on one started with a copy of its context (research areas run so), a
  job of `subject` with `label`. `labelled(label, step)` names the calls inside it again
  and keeps the subject: a research phase, a correction. `blog_worker.generate` asks
  `job(stop)` for the job it runs as; outside `within` there is none, and nothing is shown
  or kept.
- A job that ends, however it ends, is added to its subject's Activity log,
  `.blog-runs/activity/<subject>.jsonl`, under the studio lock (or with it, when the caller
  already holds it). `.blog-runs` is this computer's own state, which Git ignores in every
  Blog Studio workspace: the log is never committed or shared, and a team workspace never
  sees it as a change or a conflict. Writing it is best effort: a log that cannot be
  written never changes how the job ended.
- The page reads `Running.live(subject)` with each poll, `Running.lines(subject, job,
  since)` while a job's Show activity is open, `view(running, subject)` for the Activity
  log, and `entry(root, subject, ident)` for one finished job's lines.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
import re
import secrets
import threading

import studio
from studio_core import activity_log

WORKSPACE = 'workspace'
SUBJECT = re.compile(r'(?:blog-[a-z0-9][a-z0-9-]{0,79}|geo-report-[a-f0-9]{32}|workspace)')
# A run's stages and the desk's jobs, as the page names what they are doing.
STAGES = {
    'angles': 'Proposing angles',
    'research-plan': 'Planning the research',
    'research': 'Researching',
    'claims-map': 'Listing the claims in your material',
    'outline': 'Writing the outline',
    'draft': 'Writing the draft',
    'review': 'Reviewing the draft',
    'package': 'Preparing the handoff',
}
KINDS = {
    'desk-section': 'Rewriting a section',
    'desk-revise-all': 'Revising the whole draft',
    'desk-selection': 'Editing a passage',
    'desk-first-pass': 'Working on the first pass',
    'desk-angles': 'Proposing angles',
    'desk-research': 'Researching',
    'desk-outline': 'Writing the outline',
    'desk-draft': 'Writing the draft',
    'finish-copyedit': 'Copy editing the draft',
    'finish-humanize': 'Finding sentences to humanize',
    'finish-facts': 'Checking facts against your sources',
    'finish-headline': 'Suggesting headlines and openings',
    'finish-feedback': 'Reading the draft for feedback',
    'finish-voice': 'Rewriting the draft in a voice guide',
    'finish-geo': 'Reviewing retrieval readiness (GEO)',
    'finish-faq': 'Writing FAQ questions',
    'finish-table': 'Looking for a comparison table',
    'finish-quotes': 'Finding quotations in your sources',
    'finish-takeaways': 'Gathering the key takeaways',
    'finish-alt': 'Writing image alt text',
    'finish-queries': 'Listing likely search questions',
    'finish-opener': 'Writing a definition-style opening',
    'geo-report': 'Writing the GEO report',
    'find-text': 'Finding where the page gets its text',
    'voice-learn': 'Learning a voice',
    'voice-audition': 'Writing a voice audition',
    'voice-guide': 'Writing a voice guide',
    'style-learn': 'Learning a kind of post',
    'repurpose': 'Repurposing the blog',
    'interview-question': 'Asking an interview question',
    'interview-outline': 'Outlining from the interview',
}

# The subject, label and step every assistant call in this context runs as, and its register.
_CONTEXT: ContextVar = ContextVar('blog_studio_activity', default=None)


def blog(ident) -> str:
    return 'blog-' + studio.identifier(ident)


def report(ident) -> str:
    if not isinstance(ident, str) or not re.fullmatch(r'[a-f0-9]{32}', ident):
        raise ValueError('Choose a saved GEO report.')
    return 'geo-report-' + ident


def of_job(job) -> str:
    """The subject a tool job works for: its blog, its GEO report, or the workspace."""
    meta = job.get('metadata') or {}
    if job.get('kind') == 'geo-report' and meta.get('report'):
        return report(meta['report'])
    return blog(meta['article']) if meta.get('article') else WORKSPACE


def path(root, subject):
    """Where a subject's Activity log is kept on this computer."""
    if not isinstance(subject, str) or not SUBJECT.fullmatch(subject):
        raise ValueError('Choose a blog, a GEO report or this workspace.')
    return studio.inside(root, '.blog-runs', 'activity', subject + '.jsonl')


class Job:
    """One running assistant call: what the page is shown of it."""

    def __init__(self, subject, label, step, owner=None):
        self.id = secrets.token_hex(8)
        self.subject, self.label, self.step, self.owner = subject, label, step, owner
        self.started_at = activity_log.now()
        self.lines = activity_log.Lines()
        self.limited = False  # The assistant said it reached an account or spending limit.
        self._last = None

    def say(self, text) -> None:
        """One plain line; the same line twice in a row is said once."""
        if text and text != self._last:
            self._last = text
            self.lines.append(text)

    def shown(self) -> dict:
        return {'label': self.label, 'started_at': self.started_at, 'lines': self.lines}


class Running:
    """A workspace's running assistant jobs, and where each is logged when it ends."""

    def __init__(self, root):
        self.root = root
        self._lock = threading.Lock()
        self._jobs: dict[str, Job] = {}

    def start(self, subject, label, step, owner=None) -> Job:
        found = Job(subject, label, step, owner)
        with self._lock:
            self._jobs[found.id] = found
        return found

    def end(self, found: Job, ended: str, detail: str | None = None) -> None:
        """Let the job go and add it to its log. Best effort, whatever goes wrong: it is called
        as an assistant call ends, and must never change that call's result or failure."""
        with self._lock:
            self._jobs.pop(found.id, None)
        try:
            entry = activity_log.entry(
                found.label, found.step, found.started_at, ended, found.lines, detail=detail
            )
            target = path(self.root, found.subject)
            if target.is_symlink():
                return
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            if studio.lock_held():
                activity_log.append(target, entry)
            else:
                with studio.locked(self.root):
                    activity_log.append(target, entry)
        except Exception:  # noqa: BLE001 - a busy, unwritable or unreadable workspace
            pass  # loses the entry, never the work; Training and Presentation Studio do so too.

    def items(self, subject, owner=None) -> list:
        """The subject's running jobs as (id, worker) pairs, oldest first; with `owner`, only
        those of that piece of work (a tool job's id)."""
        with self._lock:
            return [
                (ident, job.shown())
                for ident, job in self._jobs.items()
                if job.subject == subject and (owner is None or job.owner == owner)
            ]

    def live(self, subject, owner=None) -> list:
        return activity_log.live(self.items(subject, owner))

    def lines(self, subject, ident, since=0) -> dict:
        return activity_log.running_lines(self.items(subject), ident, since)


@contextmanager
def within(running, subject, label, step, owner=None):
    """Each assistant call inside is a job of `subject`, named `label`; `owner` is the piece
    of work it is for, such as a tool job's id, when a page shows only that work's jobs."""
    token = _CONTEXT.set((running, subject, label, step, owner))
    try:
        yield
    finally:
        _CONTEXT.reset(token)


@contextmanager
def labelled(label, step=None):
    """The calls inside are named `label` (and `step`), for the same subject."""
    found = _CONTEXT.get()
    if found is None:
        yield
        return
    token = _CONTEXT.set((found[0], found[1], label, step or found[3], found[4]))
    try:
        yield
    finally:
        _CONTEXT.reset(token)


@contextmanager
def job(stop=None):
    """The job one assistant call runs as, or None outside `within`. It ends finished when
    the block does, and otherwise stopped, out of time, at a limit or failed, with why."""
    found = _CONTEXT.get()
    if found is None:
        yield None
        return
    running, subject, label, step, owner = found
    held = running.start(subject, label, step, owner)
    try:
        yield held
    except BaseException as failure:
        if stop is not None and stop.is_set():
            running.end(held, 'stopped')
        elif getattr(failure, 'reason', None) == 'time-limit':
            running.end(held, 'timeout', str(failure))
        else:
            running.end(held, 'limit' if held.limited else 'failed', str(failure))
        raise
    else:
        running.end(held, 'finished')


def view(running, subject) -> dict:
    """A subject's Activity log for the page: finished jobs newest first, and those running."""
    return activity_log.view(path(running.root, subject), running.items(subject))


def entry(root, subject, ident) -> dict:
    return activity_log.entry_lines(path(root, subject), str(ident or ''))


def forget(root, subject) -> None:
    """Let a subject's Activity log go, as when its blog is deleted from this computer."""
    path(root, subject).unlink(missing_ok=True)
