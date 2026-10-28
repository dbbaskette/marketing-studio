"""What `studio saved-work` says: which saved items still need each older path, in the same
words in each deck studio. Each studio's engine finds what needs a path with its own
readers; this words and shapes the answer.

What a caller needs to know
---------------------------
    saved_work.PATHS                      # each path's id and the sentence about it
    saved_work.needs(path, title, why)    # one saved item that needs a path, and why
    saved_work.report(ids, found)         # {'paths': [{'id', 'about', 'needed_by'}], 'unused'}

- `found` maps path ids to dependencies; unresolved scope prevents claiming unused.
- Report formatting performs no I/O; enumeration helpers only read directory entries.
"""
from pathlib import Path

PATHS = {
    'gated-flow': 'The guided creation flow used by saved work that has not moved to the desk.',
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


def report(ids: tuple, found: dict, *, scope: dict | None = None,
           issues: list | None = None, unknown: dict | None = None) -> dict:
    """Report only what the declared local scope can establish."""
    scope = {'product': None, 'roots': [], **(scope or {}), 'local_only': True}
    issues = list(issues or ())
    if not scope.get('roots'):
        issues.append({'path': '', 'why': 'No local roots are configured.'})
    unknown = unknown or {}
    paths = []
    for ident in ids:
        needed = sorted(found.get(ident) or (), key=lambda item: item['path'])
        unresolved = sorted([*(unknown.get(ident) or ()), *issues],
                            key=lambda item: item.get('path', ''))
        paths.append({'id': ident, 'about': PATHS[ident], 'needed_by': needed,
                      'unknown_by': unresolved,
                      'status': 'needed' if needed else 'unknown' if unresolved else 'unused'})
    return {'schema': 2, 'scope': scope, 'complete': not issues and not any(unknown.values()),
            'issues': issues, 'paths': paths,
            'unused': [entry['id'] for entry in paths if entry['status'] == 'unused'],
            'limits': 'Local declared roots only; excludes unmounted workspaces, other clones, '
                      'other installations and recovery history.'}


def issue(issues: list, path: Path, why: str) -> None:
    issues.append({'path': str(path), 'why': why})


def children(root: Path, issues: list, *, optional=False) -> list[Path]:
    """Enumerate without glob's silent errors or following directory links."""
    try:
        # macOS exposes its system temporary directories through /var and /tmp.
        # These fixed OS aliases are not user workspace links.
        if root.is_symlink() or any(parent.is_symlink() for parent in root.parents if str(parent) not in ('/var', '/tmp')):
            raise ValueError('Symbolic link excluded.')
        return sorted(root.iterdir())
    except FileNotFoundError:
        if not optional:
            issue(issues, root, 'Declared root is missing.')
    except (OSError, ValueError) as exc:
        issue(issues, root, str(exc))
    return []


def checked_path(path: Path) -> None:
    if path.is_symlink() or any(parent.is_symlink() for parent in path.parents if str(parent) not in ('/var', '/tmp')):
        raise ValueError('Symbolic link excluded.')
    if not path.is_file():
        raise ValueError('Saved record is missing or is not a file.')


def workspace_roots(settings: Path, marker: str, issues: list) -> list[Path]:
    """Read remembered scope without current() silently discarding damaged settings."""
    import json

    try:
        settings.lstat()
    except FileNotFoundError:
        return []
    except OSError as exc:
        issue(issues, settings, str(exc))
        return []
    try:
        checked_path(settings)
        record = json.loads(settings.read_text(encoding='utf-8'))
        if not isinstance(record, dict) or record.get('schema') != 1 \
                or not isinstance(record.get('repo'), str) \
                or not isinstance(record.get('folder'), str) \
                or not isinstance(record.get('name'), str) \
                or not isinstance(record.get('branch'), str):
            raise ValueError('Unsupported workspace settings.')
        repo, folder = Path(record['repo']), Path(record['folder'])
        if not repo.is_absolute() or folder.is_absolute() or '..' in folder.parts:
            raise ValueError('Invalid saved workspace location.')
        root = repo / folder
    except (OSError, ValueError, TypeError) as exc:
        issue(issues, settings, str(exc))
        return []
    try:
        checked_path(root / marker)
    except (OSError, ValueError) as exc:
        issue(issues, root / marker, str(exc))
    return [root]


def registered_roots(registry: Path, key: str, issues: list) -> list[Path]:
    """Include remembered candidates without filtering missing records."""
    import json

    try:
        registry.lstat()
    except FileNotFoundError:
        return []
    except OSError as exc:
        issue(issues, registry, str(exc))
        return []
    try:
        checked_path(registry)
        record = json.loads(registry.read_text(encoding='utf-8'))
        if not isinstance(record, dict) or record.get('schema') != 1 \
                or not isinstance(record.get(key), dict):
            raise ValueError('Unsupported saved-work registry.')
        roots = [Path(path) for path in record[key]]
        if any(not root.is_absolute() for root in roots):
            raise ValueError('Registered workspace locations must be absolute.')
        return roots
    except (OSError, ValueError, TypeError) as exc:
        issue(issues, registry, str(exc))
        return []


def checked_tree(root: Path) -> None:
    """Refuse linked or unenumerable material before a broad saved-work reader runs.

    Callers validate a required record's ancestors first. Inspect directory entries only;
    never descend through a link, including a dangling link.
    """
    import stat

    pending = [root]
    while pending:
        path = pending.pop()
        mode = path.lstat().st_mode
        if stat.S_ISLNK(mode):
            raise ValueError(f'Symbolic link excluded: {path}')
        if stat.S_ISDIR(mode):
            pending.extend(path.iterdir())
