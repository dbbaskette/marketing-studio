"""Saved step-by-step Blog Studio work in its original format, as static fixtures.

Each folder under fixtures/saved/ holds the files the earlier saved flow wrote for one stop,
as a workspace holds them (articles/<id>/..., sources/<id>/..., .blog-runs/<id>.json).
`load` copies one into a test's disposable workspace, byte for byte, so the migration,
saved-state and finished-blog tests read original-format work. The stored bytes stay as
that flow wrote them (Blog Studio 4.19.0, Harness Research stand-in 1.5.1): the flow and the
capture that made them were retired with it (GitHub issue #542), so they are never written
again.
"""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
from pathlib import Path
import shutil
import tempfile

FIXTURES = Path(__file__).resolve().parent / 'fixtures' / 'saved'

# Text the fixtures hold, as the tests that read them check it.
MANUSCRIPT = (
    '# Synthetic draft\n\nAn opening.\n\n## First\n\nSaved words.\n\n## Second\n\nMore words.\n'
)
NOTES = 'Unstructured notes only, no headings.'


def load(root, state):
    """Copy one saved stop into a disposable workspace and return its blog's ID. A blog of
    the same fixture loaded earlier is replaced, with its worker record; nothing else in the
    workspace changes."""
    root = Path(root)
    temporary, place = Path(tempfile.gettempdir()).resolve(), Path(isolation.PLACE).resolve()
    real = root.resolve()
    if (
        not real.is_relative_to(temporary)
        or real == temporary
        or real.is_relative_to(place)
        or not (root / 'articles').is_dir()
    ):
        # Only a disposable Blog Studio workspace a test made in the temporary folder.
        raise RuntimeError('Load saved fixtures only into a disposable workspace.')
    tree = FIXTURES / state
    if not tree.is_dir():
        raise ValueError('No saved fixture named ' + state)
    (ident,) = [path.name for path in (tree / 'articles').iterdir()]
    if (root / 'articles' / ident).exists():
        shutil.rmtree(root / 'articles' / ident)
    (root / '.blog-runs' / (ident + '.json')).unlink(missing_ok=True)  # Its worker record.
    for path in sorted(tree.rglob('*')):
        if path.is_file():
            target = root / path.relative_to(tree)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())
    return ident


def stored(state):
    tree = FIXTURES / state
    return {str(p.relative_to(tree)): p.read_bytes() for p in tree.rglob('*') if p.is_file()}
