"""Admission for independently runnable Training Studio helper/page writes."""
from contextlib import contextmanager
from pathlib import Path

import home
import workspace
from studio_core.process_lock import ProcessRLock, workspace_lock_path
from studio_core.sync_guard import SYNC_WAIT, worker_in_progress


@contextmanager
def admitted(root, *, held=None):
    root = Path(root)
    repo = next((folder for folder in (root, *root.parents) if (folder / '.git').exists()), None)
    scope = workspace_lock_path(repo, home.data_root())
    if held is not None and not held.protects(scope):
        raise workspace.WorkspaceError('The held write lock belongs to another workspace. Reload before saving.')
    lock = held if held is not None else ProcessRLock(lambda: workspace_lock_path(repo, home.data_root()), refusal=workspace.WorkspaceError)
    with lock:
        if worker_in_progress(repo or root, refusal=workspace.WorkspaceError):
            raise workspace.WorkspaceError(SYNC_WAIT)
        path = root / workspace.STATE_DIR / 'run.json'
        if path.exists():
            record = home.read_json(path, None)
            if not isinstance(record, dict):
                raise workspace.WorkspaceError('The saved execution owner cannot be read.')
            drafts = record.get('drafts', {})
            if not isinstance(drafts, dict) or not isinstance(drafts.get('jobs', []), list):
                raise workspace.WorkspaceError('The saved jobs cannot be read.')
            jobs = drafts.get('jobs', [])
            if any(not isinstance(job, dict) or job.get('status') not in ('queued', 'working', 'done', 'stopped', 'failed', 'cancelled') for job in jobs):
                raise workspace.WorkspaceError('The saved jobs cannot be read.')
            chain, updates, decks = drafts.get('update_chain', {}), drafts.get('updates', {}), record.get('deck', {})
            if not isinstance(chain, dict) or not isinstance(updates, dict) or not isinstance(decks, dict) or any(not isinstance(item, dict) for item in decks.values()):
                raise workspace.WorkspaceError('The saved work in progress cannot be read.')
            if (any(job['status'] in ('queued', 'working') for job in jobs)
                    or chain.get('status') == 'working' or updates
                    or any(item.get('redrawing') or item.get('look_pending') for item in decks.values())):
                raise workspace.WorkspaceError(SYNC_WAIT)
            if record.get('execution', 'runner') not in ('runner', 'conversation'):
                raise workspace.WorkspaceError('The saved execution owner cannot be read.')
            for item in decks.values():
                notes = item.get('notes', [])
                if not isinstance(notes, list) or any(not isinstance(note, dict) or not isinstance(note.get('status'), str) for note in notes):
                    raise workspace.WorkspaceError('The saved deck work cannot be read.')
                if any(note['status'] in ('waiting', 'drawing') for note in notes):
                    raise workspace.WorkspaceError(SYNC_WAIT)
            driver = record.get('driver')
            if driver is None:
                driver = drafts.get('finished_by')
            if driver is not None and (not isinstance(driver, dict) or not isinstance(driver.get('computer'), str) or not driver.get('computer')):
                raise workspace.WorkspaceError('The saved execution owner cannot be read.')
            saved = home.read_json(home.data_root() / 'workspace.json', {})
            shared = isinstance(saved, dict) and saved.get('address') and saved.get('repo') == str(repo)
            if driver is not None or shared:
                computer = home.read_json(home.data_root() / 'computer.json', {})
                if not isinstance(driver, dict) or not isinstance(driver.get('computer'), str) or not driver.get('computer') or not isinstance(computer, dict) or driver['computer'] != computer.get('id'):
                    raise workspace.WorkspaceError('This training is not driven by this computer. Take it over before changing it.')
            if record.get('flow') == 'desk' and record.get('execution') == 'conversation':
                raise workspace.WorkspaceError('This training is being worked on in conversation. Use the checked desk operation; Mark ready remains available there.')
        yield
