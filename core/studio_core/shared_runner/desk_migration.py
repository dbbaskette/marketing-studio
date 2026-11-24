"""The parts of the runner's `desk_migration`, the explicit, recoverable migration of saved
work, both deck studios share: restoring and checking the workspace's staging index. A
studio binds them into its own module with `studio_core.modules.bind`; they read that
module's names (its WORKSPACE, `gitstate` and `_prepared_index` among them).

CHANGED stays in each studio: it is a value with the item's word in it. What is migrated,
and how it is previewed and applied, differ between the studios and stay in each.
"""
from __future__ import annotations

# ruff: noqa: F821  these definitions read the names of the studio module they are
# bound into; each studio's test_shared_runner_use checks every one resolves there.

import re


def _check_recovery_index(space, root, writes, before, prepared):
    _restore_index(space, root, writes, before, check=True)
    _restore_index(space, root, writes, prepared, check=True)
    if prepared != _prepared_index(space, root, writes):
        raise WorkspaceError('The prepared migration index changed. Keep its recovery record.')
    paths = [gitstate.inside(space, _path(space, root, name)) for name in writes]
    current = gitstate.hub.git(space.repo, 'ls-files', '--stage', '-z', '--', *paths)
    if current not in (before, prepared):
        raise WorkspaceError('The migration staging index changed. Nothing was replaced; keep its recovery record.')


def _path(space, root, name):
    return space.root / gitstate.MARKER if name == WORKSPACE else root / name


def _restore_index(space, root, writes, before, check=False):
    paths = [gitstate.inside(space, _path(space, root, name)) for name in writes]
    if not isinstance(before, str):
        raise WorkspaceError('The saved migration index cannot be verified.')
    entries = before.split('\0')
    if before and (entries[-1] != '' or any(not entry for entry in entries[:-1])
                   or entries[:-1] != sorted(entries[:-1], key=lambda entry: entry.partition('\t')[2])):
        raise WorkspaceError('The saved migration index has an unsupported entry.')
    seen = set()
    for entry in entries:
        if entry:
            header, _, name = entry.partition('\t')
            if name not in paths or name in seen or not re.fullmatch(r'100(?:644|755) [a-f0-9]{40,64} 0', header):
                raise WorkspaceError('The saved migration index has an unsupported entry.')
            seen.add(name)
    if check:
        return
    removed = gitstate.hub.run(space.repo, 'update-index', '--force-remove', '--', *paths)
    if removed.returncode:
        raise WorkspaceError('The migration index could not be restored; keep its recovery record.')
    if before and gitstate.hub.run(space.repo, 'update-index', '-z', '--index-info', input=before).returncode:
        raise WorkspaceError('The migration index could not be restored; keep its recovery record.')
    restored = gitstate.hub.git(space.repo, 'ls-files', '--stage', '-z', '--', *paths)
    if restored != before:
        raise WorkspaceError('The migration index could not be verified; keep its recovery record.')


NAMES = ('_check_recovery_index', '_path', '_restore_index')
METHODS = {}
