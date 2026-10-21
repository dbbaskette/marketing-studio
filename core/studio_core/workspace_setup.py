"""Adopt shared setup only on an explicit studio launch, setup submission or Connect action.

What a caller needs to know
---------------------------
    configure(gitstate, shared, identifier)   # a missing workspace, set up as the settings say
    target(shared, identifier)                # where the settings say a studio's work lives
    matches(address, branch, shared, identifier)   # whether a workspace already is that place
    prepare(gitstate, shared, identifier, carry)   # what Marketing Studio shows for a studio

- The shared settings name one storage for every studio: a team repository (`team`), or a
  folder of local Git under `local.root`, one workspace per studio. A studio that has no
  workspace yet gets one there. A studio that already has one is never moved by itself:
  `prepare` reports `connect`, and Marketing Studio offers the Connect action, which runs
  the studio's own join with the work carried over.
- A team branch left blank in the settings means whatever branch the studio's folder names.
"""
from pathlib import Path

DEFAULT_ROOT = '~/Studios'


def same_address(one, other):
    """Whether two addresses name one repository, as a person would write it either way."""
    def plain(address):
        return str(address).strip().rstrip('/').removesuffix('.git')
    return bool(one and other) and plain(one) == plain(other)


def target(shared, identifier):
    """Where the shared settings say a studio's work lives: {'repository', 'branch', 'share'}
    for a team repository, or {'root', 'branch'} for a folder of local Git."""
    team = shared.get('team') or {}
    if team.get('repository'):
        return {'repository': team['repository'], 'branch': team.get('branch') or None,
                'share': shared.get('share') if shared.get('share') in ('decision', 'asked') else None}
    root = Path((shared.get('local') or {}).get('root') or DEFAULT_ROOT).expanduser()
    return {'root': str(root / (identifier + '-workspace')), 'branch': team.get('branch') or 'main'}


def matches(address, branch, shared, identifier):
    """Whether a workspace with this remote address and branch is the storage the shared
    settings name. A folder of local Git matches any local root: a studio's folder is never
    moved between local folders."""
    wanted = target(shared, identifier)
    if 'repository' in wanted:
        return same_address(address, wanted['repository']) and (
            wanted['branch'] is None or wanted['branch'] == branch)
    return not address


def describe(workspace):
    """A studio's workspace as Marketing Studio shows it."""
    return {'root': str(workspace.root), 'repository': workspace.address or None,
            'branch': workspace.branch}


def configure(gitstate, shared, identifier):
    return set_up(gitstate, shared, identifier)[0]


def set_up(gitstate, shared, identifier):
    """The studio's workspace, set up as the shared settings say when it has none, and the
    studio's notice when the layout of a fresh join could not be pushed, else None."""
    current = gitstate.current()
    if current is not None:
        return current, None
    team = shared.get('team') or {}
    if team.get('repository'):
        joined = gitstate.join(team['repository'], branch=team.get('branch'), share=shared.get('share'))
        # Share the folder's layout at once, never forced, so an empty repository has the
        # branch the next studio clones and adds its own folder to.
        sync = getattr(gitstate, 'sync', None)
        report = sync(joined) if sync is not None else None
        notice = report.get('notice') if isinstance(report, dict) else None
        return joined, notice if isinstance(notice, str) and notice else None
    root = Path((shared.get('local') or {}).get('root') or DEFAULT_ROOT).expanduser()
    return gitstate.local(root / (identifier + '-workspace'), branch=team.get('branch') or 'main'), None


def prepare(gitstate, shared, identifier, carry=None):
    """Set a missing workspace up as the shared settings say, and never move one that exists.

    Returns {'prepared': True, 'workspace': {...}}, with 'notice' when a fresh join could not
    push its layout, and, when the workspace is not the storage the settings name,
    'connect': {'from', 'to', 'carry'}, where `carry(workspace)` counts the work the
    Connect action would carry over."""
    current = gitstate.current()
    if current is None:
        made, notice = set_up(gitstate, shared, identifier)
        return {'prepared': True, 'workspace': describe(made), **({'notice': notice} if notice else {})}
    result = {'prepared': True, 'workspace': describe(current)}
    if not matches(current.address, current.branch, shared, identifier):
        wanted = target(shared, identifier)
        result['connect'] = {'from': describe(current),
                             'to': {key: wanted.get(key) for key in ('repository', 'root', 'branch')},
                             'carry': carry(current) if carry else {}}
    return result


def launch(gitstate, config, identifier):
    from studio_core.preferences import ready
    values, problem = config.read()
    if not problem and ready(values):
        return configure(gitstate, values, identifier)
    return gitstate.current()
