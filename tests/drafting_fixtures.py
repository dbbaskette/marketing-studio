"""A disposable store for the shared desk parts' tests: plain folders, and a lock flag."""

import json
import re
from pathlib import Path

import marketing_studio  # noqa: F401  Puts core/ on the path.
from studio_core.drafting import record
from studio_core.drafting.store import Store

IDENT = re.compile(r'[a-z0-9-]{1,40}')


class FolderStore(Store):
    product = 'Test Studio'
    word = 'item'

    def __init__(self, root, lock=True):
        self.root = Path(root)
        self.lock = lock
        self.written = []

    def held(self):
        return self.lock

    def folder(self, ident):
        if not isinstance(ident, str) or not IDENT.fullmatch(ident):
            raise ValueError('Choose an item on the desk.')
        return self.root / 'items' / ident / 'drafting'

    def local(self, ident, *names):
        self.folder(ident)
        return self.root.joinpath('local', 'proposals', ident, *names)

    def write(self, ident, draft, parts):
        draft = record.advance(draft, parts, self.now())
        self.write_json(self.path(ident, 'draft.json'), draft)
        self.written.append((ident, list(parts)))
        return draft


def draft(**extra):
    """A two-section draft at revision 1."""
    return {
        'title': 'A synthetic title',
        'opening': 'An opening paragraph.',
        'sections': [
            {'id': 'aaaaaaaa', 'heading': 'First', 'brief': '', 'text': 'First text.'},
            {'id': 'bbbbbbbb', 'heading': 'Second', 'brief': '', 'text': 'Second text.'},
        ],
        'revision': 1,
        **extra,
    }


def make(store, ident, value):
    target = store.path(ident, 'draft.json')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(value))
    return value
