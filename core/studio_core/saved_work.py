"""What `studio saved-work` says: which saved items still need each older path, in the same
words in each deck studio. Each studio's engine finds what needs a path with its own
readers; this words and shapes the answer.

What a caller needs to know
---------------------------
    saved_work.PATHS                      # each path's id and the sentence about it
    saved_work.needs(path, title, why)    # one saved item that needs a path, and why
    saved_work.report(ids, found)         # {'paths': [{'id', 'about', 'needed_by'}], 'unused'}

- `found` maps a path's id to the items that need it; an id with none is in `unused`.
- Nothing here reads or writes anything.
"""
from pathlib import Path

PATHS = {
    'research-queue': ('The legacy research question queue, for a run begun before Harness '
                       'Research could synthesize its research.'),
    'cover-sample': ('The cover drawn to show a brand skill that offers no looks. Only this '
                     'computer is looked at: what it needs is kept in work/, which is never '
                     'shared.'),
    'review-layout-1': ('The first layout of combined reviews, which writes the briefs before '
                        'the first review.'),
    'old-harness-slides': ('Branches for a Harness Slides that lists no capabilities. No saved '
                           'work needs these. They are reached only by a Harness Slides that '
                           'lists no capabilities.'),
}


def needs(path: Path, title: str, why: str) -> dict:
    """One saved item that needs a path: where it is, what it is called, and why."""
    return {'path': str(path), 'title': title, 'why': why}


def report(ids: tuple, found: dict) -> dict:
    """The paths `ids` names, in that order, each with the items that need it sorted by
    where they are, and the ids no item needs."""
    paths = [{'id': ident, 'about': PATHS[ident],
              'needed_by': sorted(found.get(ident) or (), key=lambda item: item['path'])}
             for ident in ids]
    return {'paths': paths, 'unused': [entry['id'] for entry in paths if not entry['needed_by']]}
