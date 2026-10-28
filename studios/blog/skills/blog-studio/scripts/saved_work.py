"""Read-only inventory of local Blog Studio saved work, including retained deletions."""
from pathlib import Path

import studio
from studio_core import saved_work as inventory

IDS = ('research-queue', 'review-layout-1', 'old-harness-slides', 'gated-flow')


def scan(root: Path, folders=()) -> dict:
    root = Path(root)
    issues, found = [], {}
    candidates = []
    # Enumerate directly: catalog expires deleted work and must never be used here.
    inventory.children(root, issues)
    for child in inventory.children(root / 'articles', issues, optional=True):
        candidates.append(child)
    deleted = root / '.blog-runs' / 'deleted'
    for child in inventory.children(deleted, issues, optional=True):
        if child.suffix == '.json':
            try:
                inventory.checked_path(child)
                entry = studio.read_json(child)
                if entry.get('schema') != 1:
                    raise ValueError('Unsupported deleted record schema.')
                retained = deleted / child.stem / 'blog'
                if not retained.is_dir():
                    raise ValueError('Deleted work requires recovery history unavailable to this scan.')
                candidates.append(retained)
            except (OSError, ValueError, TypeError, AttributeError) as exc:
                inventory.issue(issues, child, str(exc))
        elif child.is_dir() or child.is_symlink():
            candidates.append(child / 'blog')
    candidates.extend(map(Path, folders))
    seen = set()
    for directory in candidates:
        if directory.absolute() in seen:
            continue
        seen.add(directory.absolute())
        try:
            inventory.checked_path(directory / 'session.json')
            record = studio.read_json(directory / 'session.json')
            if record.get('schema', 1) != 1 or not record.get('id') or not record.get('title') or not record.get('mode'):
                raise ValueError('Unsupported blog record schema.')
            title = record.get('title') or directory.name
            draft = directory / 'desk' / 'draft.json'
            if draft.exists() or draft.is_symlink():
                inventory.checked_path(draft)
                if studio.read_json(draft).get('schema') != 1:
                    raise ValueError('Unsupported desk record schema.')
                continue
            run_path = directory / 'derived' / 'blog-run.json'
            if not run_path.exists() and not run_path.is_symlink():
                continue  # A conversation article has no guided run.
            inventory.checked_path(run_path)
            run = studio.read_json(run_path)
            if run.get('schema') not in (1, 2, 3) or run.get('approval') not in ('page', 'conversation'):
                raise ValueError('Unsupported run record schema.')
            if run.get('schema') == 2 and not run.get('review_policy'):
                raise ValueError('Saved review policy is missing.')
            if run.get('schema') == 3 and (run.get('research_contract') or {}).get('schema') != 2:
                raise ValueError('Saved research contract is missing.')
            found.setdefault('gated-flow', []).append(inventory.needs(
                directory, title, 'Saved guided creation flow.'))
            if not run.get('research_contract') and 'research' in (run.get('pipeline') or ()) \
                    and (run.get('stages') or {}).get('research', {}).get('status') != 'approved':
                found.setdefault('research-queue', []).append(inventory.needs(
                    directory, title, 'Saved research predates the current research contract.'))
        except (OSError, ValueError, TypeError, AttributeError, KeyError) as exc:
            inventory.issue(issues, directory, str(exc))
    return inventory.report(IDS, found, scope={
        'product': 'Blog Studio', 'roots': [str(root), *map(str, folders)], 'local_only': True},
        issues=issues)
