"""Adopt shared setup only on an explicit studio launch or setup submission."""
from pathlib import Path


def configure(gitstate, shared, identifier):
    current = gitstate.current()
    if current is not None:
        return current
    team = shared.get('team') or {}
    if team.get('repository'):
        return gitstate.join(team['repository'], branch=team.get('branch'), share=shared.get('share'))
    root = Path((shared.get('local') or {}).get('root') or '~/Studios').expanduser()
    return gitstate.local(root / (identifier + '-workspace'), branch=team.get('branch') or 'main')


def launch(gitstate, config, identifier):
    from studio_core.preferences import ready
    values, problem = config.read()
    if not problem and ready(values):
        return configure(gitstate, values, identifier)
    return gitstate.current()
