"""Private, process-local activity notices; observing never starts or repeats work."""
from contextlib import contextmanager
import secrets
import threading
import time

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


class Activity:
    def __init__(self, *, clock=time.monotonic):
        self.clock = clock
        self.lock = threading.RLock()
        self.items = {}

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
                    'state': 'running', 'started': self.clock(), 'ended': None}
            self.items[ident] = item

        def report(label):
            with self.lock:
                item['label'] = label

        try:
            yield report
        except BaseException as failure:
            with self.lock:
                item.update(state='failed', ended=self.clock())
                if isinstance(failure, AssistantFailure):
                    item.update(reason=failure.reason, problem=str(failure))
            raise
        else:
            with self.lock:
                item.update(state=item.pop('outcome', 'complete'), ended=self.clock())

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
            return {key: item[key] for key in ('id', 'action', 'label', 'state', 'reason', 'problem') if key in item} | {
                'elapsed_seconds': max(0, int((self.clock() if item['ended'] is None else item['ended']) - item['started']))}
