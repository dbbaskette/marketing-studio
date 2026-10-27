"""The parts of the runner's `settings` both deck studios share. A studio binds them
into its own module with `studio_core.modules.bind`; they read that module's names.

`claude_models` stays in each studio: its cache would keep the shared module's globals.
"""
from __future__ import annotations

# ruff: noqa: F821  these definitions read the names of the studio module they are
# bound into; each studio's test_shared_runner_use checks every one resolves there.

import re
from pathlib import Path

import studio_core


SCHEMA = 1


AGENTS = ('claude', 'codex')


SECONDS = (60, 7200)        # the shortest and longest time one worker may be given


DOLLARS = 1000              # the most one item may be allowed to spend


PARALLEL = (1, 8)           # the fewest and most items that work at once


MODEL = 100                 # characters in a model's name


# The reasoning levels each agent takes: Claude Code's `--effort`, and the words Codex's
# catalog and its service use.
LEVELS = ('none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra')


EFFORTS = {'claude': ('low', 'medium', 'high', 'xhigh', 'max'), 'codex': LEVELS}


# Claude Code has no list of its models, so the runner keeps one, with its source and date.
CLAUDE_MODELS = Path(studio_core.__file__).resolve().with_name('claude-code-models.json')


PREVIEWS = ('drive', 'local')   # how previews are rendered


RELEASE = re.compile(r'^[\w][\w.+-]{0,99}$')   # a release tag's name, as git takes it


def path():
    return home.data_root() / 'runner.json'


def check_agent(agent) -> str:
    if agent not in AGENTS:
        raise WorkspaceError('The agent is one of: ' + ', '.join(AGENTS) + '.')
    return agent


def check_model(model) -> str | None:
    """A model's name as an agent takes it, or None for the agent's own default."""
    if model is None or model == '':
        return None
    if not isinstance(model, str) or len(model) > MODEL or not model.strip() \
            or model.startswith('-') or any(mark.isspace() for mark in model):
        raise WorkspaceError('The model is the short name the agent knows it by, with no '
                             'spaces, or nothing for the agent\'s own choice.')
    return model


def check_effort(effort, agent: str | None = None, model: str | None = None) -> str | None:
    """A reasoning level the agent and its model take, or None for the agent's own. With
    no agent, any level one of them takes."""
    if effort is None or effort == '':
        return None
    known = takes(agent, model)
    if not isinstance(effort, str) or effort not in known:
        named = claude_models()['named'].get(model) if agent == 'claude' else None
        if named and not known:
            raise WorkspaceError(f'{named} takes no reasoning level: leave it to the agent.')
        raise WorkspaceError((f'{named} takes one of these reasoning levels: ' if named
                              else 'The reasoning level is one of: ') + ', '.join(known)
                             + ', or nothing for the agent\'s own choice.')
    return effort


def takes(agent: str | None, model: str | None = None) -> tuple:
    """The reasoning levels a model takes: those the list of Claude Code's models gives
    it, or for a model that is not listed, every level its agent takes."""
    if agent == 'claude' and model:
        for listed in claude_models()['models']:
            if listed['name'] == model:
                return tuple(listed['levels'])
    return EFFORTS.get(agent, LEVELS)


def read_models(path: Path) -> dict:
    """A list of Claude Code's models: {'source', 'date', 'models', 'named'}. Each model is
    {'name', 'label', 'family', 'about', 'levels', 'default_level'}, in the file's order,
    and `named` gives each model's short name ("Opus 4.6") by its ID. An alias takes its
    label and its levels from the model it names. A list that is not whole is refused."""
    try:
        kept = json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        raise WorkspaceError(f'The list of Claude Code\'s models in {path} cannot be read.')
    entries = kept.get('models') if isinstance(kept, dict) else None
    if not isinstance(entries, list):
        raise WorkspaceError(f'{path} has no list of models.')
    found: dict[str, dict] = {}
    for entry in entries:
        entry = entry if isinstance(entry, dict) else {}
        name = entry.get('id')
        try:
            check_model(name)
        except WorkspaceError:
            name = None
        if not name:
            raise WorkspaceError(f'{entry.get("id")} is not a model\'s name, in {path}.')
        if name in found:
            raise WorkspaceError(f'{name} is listed twice, in {path}.')
        for part in ('family',) if 'alias' in entry else ('family', 'label'):
            if not isinstance(entry.get(part), str) or not entry[part].strip():
                raise WorkspaceError(f'{name} has no {part}, in {path}.')
        levels = entry.get('levels', [])
        if 'alias' not in entry and (not isinstance(levels, list) or any(
                level not in EFFORTS['claude'] for level in levels)):
            raise WorkspaceError(f'{name} takes a level Claude Code does not, in {path}.')
        found[name] = entry
    models, named = [], {}
    for name, entry in found.items():
        meant = found.get(entry.get('alias')) if 'alias' in entry else entry
        if meant is None or 'alias' in meant:
            raise WorkspaceError(f'{name} names {entry.get("alias")}, which is not a version '
                                 f'listed in {path}.')
        named[name] = meant['label']
        label = (f'{entry["family"]}, always the newest (now {meant["label"]})'
                 if meant is not entry else f'{entry["label"]} ({name})')
        models.append({'name': name, 'label': label, 'family': entry['family'],
                       'about': None, 'levels': list(meant['levels']), 'default_level': None})
    return {'source': kept.get('source'), 'date': kept.get('date'), 'models': models,
            'named': named}


def check_previews(how) -> str | None:
    if how is not None and how not in PREVIEWS:
        raise WorkspaceError('Previews are rendered one of these ways: '
                             + ', '.join(PREVIEWS) + '.')
    return how


def check_place(place) -> str | None:
    if place is not None and (not isinstance(place, str) or not place.strip()
                              or len(place) > 2000 or '\0' in place):
        raise WorkspaceError('Give the brand skill as one of those found on this computer.')
    return place


def check_notify(wanted) -> bool:
    if not isinstance(wanted, bool):
        raise WorkspaceError('Notifications are on or off: give notify as true or false.')
    return wanted


def check_look(wanted) -> bool:
    if not isinstance(wanted, bool):
        raise WorkspaceError('Looking for updates is on or off: give look_for_updates as true '
                             'or false.')
    return wanted


def check_repository(address) -> str | None:
    """The brand skill's repository as an address git takes, or None for none."""
    if address is None or address == '':
        return None
    if not isinstance(address, str) or not address.strip() or len(address) > ADDRESS \
            or any(mark.isspace() or ord(mark) < 32 for mark in address.strip()) \
            or address.strip().startswith('-'):
        raise WorkspaceError("Give the brand skill's repository as one address, such as "
                             'https://github.com/your-org/your-brand.git.')
    if hub.ADDRESS_WITH_SECRET.match(address.strip()):
        raise WorkspaceError('That address carries a password or token. Give the address '
                             'without it; git signs in with your own credentials.')
    return address.strip()


def check_release(release, repository: str | None = None) -> str | None:
    """A release tag's name, or None for the newest. A release needs a repository."""
    if release is None or release == '':
        return None
    if not isinstance(release, str) or not RELEASE.match(release) or '..' in release:
        raise WorkspaceError('Give the release as its tag, such as v1.4.0, or nothing for '
                             'the newest.')
    if repository is None:
        raise WorkspaceError("A release is chosen from the brand skill's repository: give "
                             'the repository too.')
    return release


def number(value, label: str, least: float, most: float, whole: bool):
    """A limit a person typed, which must be a number in a sensible range."""
    plain = isinstance(value, (int, float)) and not isinstance(value, bool)
    if not plain or (whole and int(value) != value) or not least <= value <= most:
        kind = 'a whole number' if whole else 'a number'
        raise WorkspaceError(f'{label} is {kind} from {least:g} to {most:g}.')
    return int(value) if whole else float(value)


def passes(check, *args):
    """What a check makes of a value, or None where it refuses it."""
    try:
        return check(*args)
    except WorkspaceError:
        return None


def _kept() -> dict:
    """What runner.json holds, or nothing when it cannot be used."""
    kept = home.read_json(path(), None)
    return kept if isinstance(kept, dict) and kept.get('schema') == SCHEMA else {}


def load() -> Settings:
    """The settings now: the shared ones from the studios config, the rest from this
    computer. Anything missing or unusable is the default."""
    kept = _kept()
    known = {name: kept[name] for name in asdict(Settings())
             if name in kept and name not in SHARED}
    try:
        mine = check(Settings(**known))
    except WorkspaceError:
        mine = Settings()
    return replace(mine, **shared_now(studios_config.read()[0]))


def seen(found: dict) -> Settings:
    """The settings a form was shown, from the shared values it was given, in the shape of
    the studios config. Only the shared ones mean anything."""
    return replace(Settings(), **shared_now(found if isinstance(found, dict) else {}))


def _same(one, other) -> bool:
    return type(one) is type(other) and one == other


STALE = ('{} was changed in another studio while this was open, so nothing was saved. Look '
         'again, then save.')


def forget_own() -> None:
    """Take the shared settings out of runner.json, and leave the rest as it is."""
    kept = _kept()
    if any(name in kept for name in SHARED):
        home.write_json(path(), {name: value for name, value in kept.items()
                                 if name not in SHARED})


NAMES = ('SCHEMA', 'AGENTS', 'SECONDS', 'DOLLARS', 'PARALLEL', 'MODEL', 'LEVELS', 'EFFORTS',
         'CLAUDE_MODELS', 'PREVIEWS', 'RELEASE', 'path', 'check_agent', 'check_model',
         'check_effort', 'takes', 'read_models', 'check_previews', 'check_place', 'check_notify',
         'check_look', 'check_repository', 'check_release', 'number', 'passes', '_kept', 'load',
         'seen', '_same', 'STALE', 'forget_own')
METHODS = {}
