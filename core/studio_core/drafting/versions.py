"""A part's kept versions: `versions/<part>.jsonl` in the item's drafting folder.

One JSON line per version, newest last, at most `KEEP` per part. Saves from one editing
session (the page's session token) keep only the text before the first of them; every
rewrite, revision, selection edit and restore keeps one. A torn line never hides the others,
and a link or anything but a plain file on the way is refused. The kinds of change a version
may come from are the studio's: Blog Studio adds `chat` and `google` to these.
"""

import json

from .parts import MARKDOWN
from .store import require_held

KEEP = 20  # versions kept per part
SOURCES = (
    'save',
    'rewrite',
    'revise-all',
    'selection',
    'first-pass',
    'finishing',
    'restore',
    'draft',
)
NOT_PLAIN = 'A desk versions file is not a plain file. Nothing was changed.'


def entries(target):
    """The versions a file holds, oldest first; a line that is not a version is left out."""
    if not target.is_file():
        return []
    found = []
    for line in target.read_text(encoding='utf-8').splitlines():
        try:
            entry = json.loads(line)
        except ValueError:
            continue  # A torn line never hides the others.
        if isinstance(entry, dict) and isinstance(entry.get('text'), str):
            found.append(entry)
    return found


class Versions:
    def __init__(self, store, codec=MARKDOWN, sources=SOURCES, keep=KEEP):
        self.store, self.codec, self.sources, self.most = store, codec, tuple(sources), keep

    def path(self, ident, part):
        if not self.codec.known(part):
            raise ValueError('Choose a part of this ' + self.codec.thing + '.')
        target = self.store.path(ident, 'versions', part + '.jsonl')
        for path in (target.parent.parent, target.parent, target):
            if path.is_symlink() or (path.exists() and not (path.is_dir() or path.is_file())):
                raise ValueError(NOT_PLAIN)
        return target

    def keep(self, ident, part, text, source, session=None, extra=None):
        """Keep a part's text before it changes, newest last, at most `most` per part."""
        require_held(self.store)
        if source not in self.sources:
            raise ValueError('Choose a listed kind of change.')
        target = self.path(ident, part)
        found = entries(target)
        if (
            source == 'save'
            and session
            and found
            and found[-1].get('source') == 'save'
            and found[-1].get('session') == session
        ):
            return
        entry = {'at': self.store.now(), 'source': source, 'text': text, 'words': len(text.split())}
        if source == 'save' and session:
            entry['session'] = session
        entry.update(extra or {})
        lines = [json.dumps(item, ensure_ascii=False) for item in (found + [entry])[-self.most :]]
        self.store.atomic(target, ('\n'.join(lines) + '\n').encode())

    def kept(self, ident, part):
        """The kept versions of one part, newest first, as they were kept."""
        return list(reversed(entries(self.path(ident, part))))

    def versions(self, ident, part):
        """The kept versions of one part, newest first, each as the page shows it (the
        codec's `shown`)."""
        out = []
        for entry in self.kept(ident, part):
            shown = self.codec.shown(entry['text'])
            out.append(entry if shown == entry['text'] else {**entry, 'text': shown})
        return out

    def counts(self, ident):
        """How many versions each part keeps, for parts that keep any."""
        folder = self.store.path(ident, 'versions')
        if not folder.is_dir() or folder.is_symlink():
            return {}
        found = {}
        for path in sorted(folder.glob('*.jsonl')):
            part = path.stem
            if self.codec.known(part) and path.is_file() and not path.is_symlink():
                found[part] = len(entries(path))
        return {part: count for part, count in found.items() if count}
