"""The store a studio passes to the shared desk parts.

Core never imports a studio, so every shared function that touches disk goes through a
store. A studio subclasses `Store` and fills in its own layout:

- `product`: the product name, in prompts ("Blog Studio");
- `word`: the item word, in sentences ("blog": "This blog is not on the desk.");
- `held()`: whether this thread holds the studio's lock; every desk write needs it;
- `folder(ident)`: the item's drafting folder, holding `draft.json`, `versions/` and
  `removed.json`; `path(ident, *names)` is a file in it;
- `local(ident, *names)`: this computer's folder for the item's waiting proposals, never
  shared with a team;
- `read(ident)`: the item's draft record;
- `write(ident, draft, parts)`: one revision on (`record.advance`), then the studio's own
  files;
- `read_json`, `write_json`, `atomic` and `now`: reads, atomic writes and the time, with
  standard-library defaults a studio may replace with its own guarded ones.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import secrets

HELD = 'Desk writes run under the studio lock.'


class Store:
    product = ''
    word = ''

    def held(self):
        raise NotImplementedError

    def folder(self, ident):
        raise NotImplementedError

    def path(self, ident, *names):
        """A file in the item's drafting folder."""
        return Path(self.folder(ident)).joinpath(*names)

    def local(self, ident, *names):
        raise NotImplementedError

    def write(self, ident, draft, parts):
        raise NotImplementedError

    def read(self, ident):
        """The item's draft record: `draft.json` in its drafting folder, never a link."""
        target = self.path(ident, 'draft.json')
        if not target.is_file() or target.is_symlink():
            raise ValueError('This ' + self.word + ' is not on the desk.')
        return self.read_json(target)

    def read_json(self, path):
        return json.loads(Path(path).read_text(encoding='utf-8'))

    def write_json(self, path, value):
        self.atomic(path, (json.dumps(value, indent=2, ensure_ascii=False) + '\n').encode())

    def atomic(self, path, data):
        """Write `data` whole or not at all: a hidden temporary file, then a rename."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name('.' + path.name + '.' + secrets.token_hex(8) + '.tmp')
        try:
            temp.write_bytes(data)
            os.replace(temp, path)
        finally:
            if temp.exists():
                temp.unlink()

    def now(self):
        return datetime.now(timezone.utc).isoformat()


def require_held(store):
    """Refuse a desk write made without the studio's lock."""
    if not store.held():
        raise RuntimeError(HELD)
