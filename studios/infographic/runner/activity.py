"""Private, process-local activity notices; observing never starts or repeats work.

While an operation runs, what its assistant is doing is kept with it as plain lines
(studio_core.activity_log), and the page is shown them. When an operation in which an assistant
worked ends, `keep(ident, entry)` is given its Activity log entry, after the work and outside
every lock held here.
"""
from contextlib import contextmanager
import secrets
import threading
import time

from studio_core import activity_log

from .validation import require
from .assistant_failure import AssistantFailure

LABELS = {
    'suggest': 'Finding the story', 'build': 'Building the page',
    'art-direct': 'Writing the art direction', 'image-start': 'Generating artwork',
    'inspect-images': 'Inspecting the page', 'revise-story': 'Revising the story',
    'revise-art': 'Revising the artwork', 'repair': 'Repairing the page',
    'preview': 'Rendering the preview', 'export': 'Preparing your files',
    'google-deliver': 'Delivering the Google Doc',
    'image-recover': 'Recovering saved artwork locally',
    'visual-layout': 'Building the visual diagram layout',
    'approve': 'Approving and preparing your files',
    'review': 'Recording your review and running checks',
}


# How an operation ended, in the Activity log's words. A failure says more: see `ending`.
ENDED = {'complete': 'finished', 'cancelled': 'stopped', 'unknown': 'timeout', 'outdated': 'failed'}


def ending(item):
    """How an operation ended, as studio_core.activity_log names an ending."""
    if item['state'] == 'failed':
        return {'timeout': 'timeout', 'cancelled': 'stopped', 'quota': 'limit'}.get(
            item.get('reason'), 'failed')
    return ENDED.get(item['state'], 'failed')


class Activity:
    def __init__(self, *, clock=time.monotonic, keep=None):
        self.clock = clock
        self.lock = threading.RLock()
        self.items = {}
        self.keep = keep        # keep(ident, entry): an operation's Activity log entry

    @contextmanager
    def track(self, ident, action):
        with self.lock:
            previous = self.items.get(ident)
            require(not previous or previous['state'] != 'running',
                    'This infographic is still working. Check its progress before starting another operation.')
            # Keep bounded terminal notices, without evicting an active operation.
            for key in list(self.items):
                if len(self.items) < 100:
                    break
                if self.items[key]['state'] != 'running':
                    del self.items[key]
            require(len(self.items) < 100, 'The studio is busy. Let an active operation finish first.')
            item = {'id': secrets.token_hex(16), 'action': action, 'label': LABELS[action],
                    'state': 'running', 'started': self.clock(), 'ended': None,
                    'started_at': activity_log.now(), 'lines': activity_log.Lines()}
            self.items[ident] = item

        def report(label):
            with self.lock:
                item['label'] = label
        # What the assistant is doing, line by line: give it to the author (author.watching).
        report.said = item['lines'].append

        assisted = False
        try:
            yield report
        except BaseException as failure:
            with self.lock:
                item.update(state='failed', ended=self.clock())
                if isinstance(failure, AssistantFailure):
                    item.update(reason=failure.reason, problem=str(failure))
                    assisted = True
            self._kept(ident, item, assisted)
            raise
        else:
            with self.lock:
                item.update(state=item.pop('outcome', 'complete'), ended=self.clock())
            self._kept(ident, item, assisted)

    def _kept(self, ident, item, assisted):
        """Give an operation in which an assistant worked to the Activity log. Best effort:
        a log that cannot be written never changes how the operation ended."""
        if self.keep is None or not (assisted or len(item['lines'])):
            return
        try:
            self.keep(ident, activity_log.entry(
                LABELS[item['action']], item['action'], item['started_at'], ending(item),
                item['lines'], detail=item.get('problem')))
        except Exception:
            pass

    def outcome(self, ident, result):
        """A returned uncertain provider outcome is not a completed delivery."""
        if isinstance(result, dict):
            state = result.get('state')
            if state in ('unknown', 'failed', 'cancelled', 'outdated', 'existing'):
                with self.lock:
                    self.items[ident]['outcome'] = 'unknown' if state == 'existing' else state

    def snapshot(self, ident):
        with self.lock:
            item = self.items.get(ident)
            if item is None:
                return None
            shown = {key: item[key] for key in ('id', 'action', 'label', 'state', 'reason', 'problem') if key in item} | {
                'elapsed_seconds': max(0, int((self.clock() if item['ended'] is None else item['ended']) - item['started']))}
            if item['state'] == 'running' and len(item['lines']):
                # What its assistant is doing now, as every studio shows a running job.
                shown['worker'], = activity_log.live([(item['id'], {
                    'label': LABELS[item['action']], 'started_at': item['started_at'],
                    'lines': item['lines']})])
            return shown
