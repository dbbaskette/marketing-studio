"""Infographic Studio's long actions as background jobs, one at a time per infographic.

Finding the story, building the page, writing art direction, generating or revising artwork,
inspecting the page, revising a story and repairing findings can each take many minutes. The
request that starts one returns at once; the work runs in a thread of this server, says what it
is doing through the activity panel (activity.Activity) and ends early when the person chooses
Stop. Stopping ends a running assistant or image worker's whole process group straight away
(author.stopping, images.codex.stop_owned) and cancels an image request on this computer, so a
late result can never land.

Every check the action makes today still runs, in the same order, inside the job: the expected
revision, the build lock, image intents and approval rules live in api.action and the engine.

What runs is also written beside the workspace, in `.action-runs/<id>.json` (never a revision,
never shared). A server that stops while a job runs leaves that record saying it was running:
the next server reads it as interrupted, says so with what to do next, and never shows it as
still running.
"""
from __future__ import annotations

import json
import threading
import time

from studio_core import activity_log

from . import author
from .activity import LABELS, STOPPED, Stopped
from .contracts import Invalid, canonical
from .validation import identifier, require
from .workspace import _atomic

# The actions that run in the background. Every other action still answers in its request.
BACKGROUND = ('suggest', 'build', 'art-direct', 'image-start', 'inspect-images', 'revise-story',
              'revise-art', 'repair', 'refresh-page', 'approve', 'review', 'export', 'google-deliver')
# Stop is offered only where stopping leaves nothing half-done. Approval with its files, a review
# with its checks, preparing approved files and a Google delivery each finish once started (a
# delivery says exactly what was sent); their progress is shown all the same.
STOPPABLE = ('suggest', 'build', 'art-direct', 'image-start', 'inspect-images', 'revise-story',
             'revise-art', 'repair', 'refresh-page')
FOLDER = '.action-runs'
GENERIC = ('Infographic Studio could not complete this action. Saved sources, history and '
           'earlier deliveries are kept.')
INTERRUPTED = ('{label} was interrupted: Infographic Studio stopped while it ran. Nothing is '
               'running for it now, and your saved work is kept.')
# What to do after an interrupted job, in the page's own words.
NEXT = {
    'suggest': 'Choose Find the story again when you are ready. Your sources are kept.',
    'build': ('Build the page again when you are ready. Saved artwork is reused; an image request '
              'that did not finish is shown under Image work needs attention.'),
    'art-direct': 'Ask for the art direction again when you are ready.',
    'image-start': ('Check Image work needs attention before starting new image work. '
                    'Nothing was resent.'),
    'inspect-images': 'Inspect the page again, or record your own review.',
    'revise-story': 'Ask for the story revision again when you are ready.',
    'revise-art': ('Check Image work needs attention before revising the artwork again. '
                   'Nothing was resent.'),
    'repair': ('Check Image work needs attention, then repair the findings again. '
               'Nothing was resent.'),
    'refresh-page': 'Choose Update the page again when you are ready.',
    'approve': ('Check whether this revision is approved and its files are ready under Deliver; '
                'approve it again, or prepare the approved files, if not.'),
    'review': 'Record your review again; nothing was approved.',
    'export': 'Prepare the approved files again; nothing was sent anywhere.',
    'google-deliver': ('Reconcile the Google delivery: it checks, read-only, what was sent, and '
                       'never sends again.'),
}


class Actions:
    def __init__(self, store, activity):
        self.store, self.activity = store, activity
        self.lock = threading.RLock()
        self.active = {}    # ident -> (job id, stop event, thread)

    # -- the saved record of what runs -------------------------------------------------------
    def _path(self, ident):
        require(identifier(ident), 'Choose a saved infographic.')
        return self.store.root / FOLDER / (ident + '.json')

    def _save(self, ident, record):
        folder = self.store.root / FOLDER
        if not (folder / '.gitignore').exists():
            _atomic(folder / '.gitignore', b'*\n')
        _atomic(self._path(ident), canonical(record))

    def _saved(self, ident):
        path = self._path(ident)
        if path.is_symlink() or not path.is_file():
            return None
        try:
            value = json.loads(path.read_bytes()[:20_000])
        except (OSError, ValueError):
            return None
        if not isinstance(value, dict) or value.get('schema') != 1 or value.get('action') not in BACKGROUND \
                or value.get('owner') != self.store.owner or value.get('project') != ident:
            return None
        return value

    def interrupted(self, ident):
        """A job an earlier server left running, as the activity panel shows it, or None."""
        with self.lock:
            if ident in self.active:
                return None
        try:
            saved = self._saved(ident)
        except Invalid:
            return None
        if saved is None or saved.get('state') not in ('running', 'stopping'):
            return None
        label = LABELS[saved['action']]
        return {'id': saved['job'], 'action': saved['action'], 'label': label, 'state': 'interrupted',
                'problem': INTERRUPTED.format(label=label), 'next': NEXT[saved['action']],
                'started_at': saved.get('started_at'), 'elapsed_seconds': 0, 'stoppable': False}

    def current(self, ident):
        """What the activity panel shows for one infographic: this server's operation, or an
        interrupted one an earlier server left."""
        return self.activity.snapshot(ident) or self.interrupted(ident)

    # -- starting, stopping ------------------------------------------------------------------
    def start(self, sent, make_engine, run):
        """Start one background action and return what the activity panel shows of it.

        `make_engine()` gives the engine it runs with; `run(engine, sent)` is api.action."""
        require(isinstance(sent, dict) and sent.get('action') in BACKGROUND, 'Choose a long action.')
        ident, verb = sent.get('id'), sent['action']
        require(isinstance(ident, str), 'Every action needs an infographic ID and expected revision.')
        project = self.store.read(ident)
        if verb not in ('image-start', 'google-deliver'):
            # A saved image request or delivery is looked up by its own identity (api.action).
            self.store.expect(project, sent.get('expected_revision'))
        stop = threading.Event()
        with self.lock:
            require(ident not in self.active,
                    'This infographic is still working. Check its progress before starting another operation.')
            item, report = self.activity.begin(ident, verb, stop=stop, stoppable=verb in STOPPABLE)
            record = {'schema': 1, 'owner': self.store.owner, 'project': ident, 'job': item['id'],
                      'action': verb, 'state': 'running', 'started_at': item['started_at'], 'ended_at': None}
            try:
                self._save(ident, record)
            except (Invalid, OSError) as failure:
                self.activity.end(ident, item, failure, problem='The job record could not be saved. Nothing was started.')
                raise Invalid('The job record could not be saved on this computer. Nothing was started.') from None
            thread = threading.Thread(target=self._run, name='infographic-' + verb,
                                      args=(ident, sent, item, report, stop, record, make_engine, run), daemon=True)
            self.active[ident] = (item['id'], stop, thread)
            thread.start()
        return self.activity.snapshot(ident)

    def _run(self, ident, sent, item, report, stop, record, make_engine, run):
        result, failure, shown = None, None, {}
        try:
            # An unstoppable action still ends at shutdown; only Stop on the page is refused.
            with author.watching(report.said), author.stopping(stop):
                found = make_engine()
                found.progress = report
                result = run(found, sent)
                self.activity.outcome(ident, result)
        except BaseException as caught:     # every ending is said, never raised into the thread
            failure = caught
            shown = self._problem(ident, caught, stop)
        # Work that finishes once started has no Stop: if it ended because the server stopped,
        # it was interrupted, and is shown so here and by the next server, with what to do next.
        interrupted = failure is not None and stop.is_set() and sent['action'] not in STOPPABLE
        if interrupted:
            label = LABELS[sent['action']]
            shown = {'problem': INTERRUPTED.format(label=label) + ' ' + NEXT[sent['action']]}
        try:
            self.activity.end(ident, item, failure, interrupted=interrupted,
                              result=_shown(result) if failure is None else None, **shown)
        finally:
            with self.lock:
                if self.active.get(ident, (None,))[0] == item['id']:
                    self.active.pop(ident, None)
                # An interrupted job's record is left saying it was running: interrupted() reads it.
                state = 'running' if interrupted else {'complete': 'complete', 'stopped': 'stopped'}.get(item['state'], 'failed')
                try:
                    self._save(ident, {**record, 'state': state,
                                       'ended_at': None if interrupted else activity_log.now()})
                except (Invalid, OSError):
                    pass

    def _problem(self, ident, failure, stop):
        if isinstance(failure, Stopped) or stop.is_set():
            return {'problem': STOPPED}
        from . import build_recovery
        try:
            recovery = build_recovery.read(self.store, ident)
        except (Invalid, OSError):
            recovery = None
        if getattr(failure, 'workflow_recovery', None) and recovery and recovery.get('current') \
                and recovery.get('state') == 'failed':
            return {'problem': recovery['label'] + ' could not finish. Completed work is kept.',
                    'recovery': recovery}
        if isinstance(failure, Invalid):
            return {'problem': str(failure)}
        return {'problem': GENERIC}

    def stop(self, ident):
        """Stop the running job of one infographic: its assistant or image worker ends now, a
        pending image request is cancelled on this computer, and the job ends at once."""
        with self.lock:
            running = self.active.get(ident)
            require(running is not None, 'Nothing is running for this infographic now.')
            require(self.activity.snapshot(ident).get('stoppable'),
                    'This work finishes once started, so it has no Stop. Its progress is shown.')
            job = running[0]
            try:
                # Said first: the job's own ending, written under this lock, comes after.
                self._save(ident, {**(self._saved(ident) or {}), 'state': 'stopping'})
            except (Invalid, OSError):
                pass
            self.activity.stop(ident)
        self._end_workers(ident)
        return {'stopping': True, 'job': job, 'activity': self.activity.snapshot(ident)}

    def _end_workers(self, ident):
        from .image_jobs import Jobs
        from .images.codex import stop_owned
        try:
            jobs = Jobs(self.store, {})
            for pending in jobs.recovery(ident):
                if pending['state'] in ('queued', 'running'):
                    current = self.store.read(ident)
                    jobs.cancel(ident, pending['attempt_id'], expected_revision=current['revision'])
        except (Invalid, OSError, KeyError):
            pass    # what cannot be cancelled here stays under Image work needs attention
        stop_owned(self.store._project(ident) / 'jobs')

    def dismiss(self, ident):
        """Clear the notice of an interrupted job once the person has read it."""
        with self.lock:
            require(self.interrupted(ident) is not None, 'There is no interrupted work to clear.')
            self._save(ident, {**self._saved(ident), 'state': 'interrupted', 'ended_at': activity_log.now()})
        return {'dismissed': True}

    def running(self):
        with self.lock:
            return list(self.active)

    def shutdown(self, wait=2.0):
        """Ask every job to stop as the server stops; a job still running when it exits is
        read as interrupted by the next server."""
        with self.lock:
            running = list(self.active.items())
        for ident, (_, stop, _) in running:
            self.activity.stop(ident, force=True)
            stop.set()
        deadline = time.monotonic() + wait
        for _, (_, _, thread) in running:
            thread.join(max(0, deadline - time.monotonic()))


def _shown(result):
    """What the page reads of a finished action: a bounded JSON value."""
    try:
        raw = canonical(result)
    except Invalid:
        return None
    return result if len(raw) <= 400_000 else {'state': (result or {}).get('state')} if isinstance(result, dict) else None
