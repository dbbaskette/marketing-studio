"""Admission for independently runnable Training Studio helper/page writes."""
from contextlib import contextmanager
from pathlib import Path

import home
import workspace
from studio_core.process_lock import ProcessRLock, workspace_lock_path
from studio_core.sync_guard import SYNC_WAIT, worker_in_progress


@contextmanager
def admitted(root, *, held=None):
    """Standalone helpers wait for workers; runner calls borrow their exact owned lock.

    The runner coordinates its own jobs before calling the helper. Ownership and
    conversation checks apply to both paths; a JSON request cannot supply `held`.
    """
    root = Path(root)
    repo = next((folder for folder in (root, *root.parents) if (folder / '.git').exists()), None)
    scope = workspace_lock_path(repo, home.data_root())
    if held is not None and not held.protects(scope):
        raise workspace.WorkspaceError('The held write lock belongs to another workspace. Reload before saving.')
    lock = held if held is not None else ProcessRLock(lambda: workspace_lock_path(repo, home.data_root()), refusal=workspace.WorkspaceError)
    with lock:
        if held is None and worker_in_progress(repo or root, refusal=workspace.WorkspaceError):
            raise workspace.WorkspaceError(SYNC_WAIT)
        saved_workspace = home.read_json(home.data_root() / 'workspace.json', {})
        if isinstance(saved_workspace, dict) and saved_workspace.get('repo') == str(repo):
            import sync_guidance
            folder = saved_workspace.get('folder')
            marker_path = repo / folder / 'hub.json' if isinstance(folder, str) else None
            marker = home.read_json(marker_path, None) if marker_path is not None and not marker_path.is_symlink() else None
            try:
                valid = isinstance(marker, dict) and type(marker.get('schema')) is int and marker['schema'] == 1 and marker.get('tool') == 'training-studio' and marker.get('folder') == folder and all(isinstance(marker.get(key), str) for key in ('name', 'branch')) and sync_guidance.as_tuple(marker['minimum_runtime']) <= sync_guidance.as_tuple(sync_guidance.runtime_version())
            except (KeyError, sync_guidance.SyncError):
                valid = False
            if not valid:
                raise workspace.WorkspaceError('The Training Studio workspace record is missing, unsupported or requires a newer runtime.')
        # Validate migration evidence even when the raw run was removed.
        workspace.read_run(root)
        path = root / workspace.STATE_DIR / 'run.json'
        if path.exists():
            record = workspace.read_run(root)
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
            if held is None and (any(job['status'] in ('queued', 'working') for job in jobs)
                    or chain.get('status') == 'working' or updates
                    or any(item.get('redrawing') or item.get('look_pending') for item in decks.values())):
                raise workspace.WorkspaceError(SYNC_WAIT)
            if record.get('execution', 'runner') not in ('runner', 'conversation'):
                raise workspace.WorkspaceError('The saved execution owner cannot be read.')
            for item in decks.values():
                notes = item.get('notes', [])
                if not isinstance(notes, list) or any(not isinstance(note, dict) or not isinstance(note.get('status'), str) for note in notes):
                    raise workspace.WorkspaceError('The saved deck work cannot be read.')
                if held is None and any(note['status'] in ('waiting', 'drawing') for note in notes):
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
