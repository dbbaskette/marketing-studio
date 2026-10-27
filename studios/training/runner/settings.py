"""What the runner is set to: the agent to use by default, the limits, how a deck's previews
are rendered, and where the brand skill is installed from.

What a caller needs to know
---------------------------
    chosen = settings.load()                      # the defaults when nothing is saved
    settings.save(replace(chosen, agent='codex', training_dollars=10))

- Two places hold them. The values every studio on this computer shares are kept only in
  the studios config (`studios_config`), and read from it each time: the agent, its model
  and its level (`assistant.agent`, `.model`, `.effort`) and the brand skill's repository and
  release and installed folder (`brand.repository`, `.release`, `.skill`), plus
  slide previews (`render.previews`). SHARED names them. A value there that would be
  refused here is the default, and so is every one of them while the file cannot be read.
  The rest belong to Training Studio on this computer alone, and are kept in the per-user
  data folder as `runner.json`, beside the workspace `gitstate` remembers there. Nothing
  here is written into the repository: two people who share a workspace can use different
  agents and different limits.
- `save` writes into the studios config only the shared values that differ from what
  `load` reads there now, then `runner.json`. Where a shared value changed and the file
  cannot be read or written, it refuses before anything is kept, and the file is left as it
  is. A value in the file that Training Studio cannot use is never written over by a save
  that did not change it.
- An agent and its model and level are written as one, and so are the brand skill's
  repository and its release: where a save writes a model or a level and the file names
  another agent than the one saved, the agent, its model and its level are all written, as
  the form showed them. A model is never left beside another studio's agent. `writes` says
  what a save would write, from what the file holds, and refuses as `save` would; set-up
  asks it before it changes anything else.
- `own()` is what `runner.json` still holds of the shared values from before they were
  shared, and `forget_own()` takes them out of it. See `setup.migrate`.
- `model` is the model the agent is asked for and `effort` how hard it reasons, its
  reasoning level; None for each is the agent's own choice. A level is one of the words an
  agent takes (EFFORTS): which of them a model takes is what the agent lists. Claude Code
  lists nothing, so its models and their levels are kept in `claude-code-models.json`
  in the shared core, and a level its model does not take is refused (`takes`).
- `step_seconds` is how long one worker may run. `training_dollars` is what one training
  may spend, where the agent reports spending, before it stops and asks. `parallel` is how
  many trainings work at once.
- `previews` is how a deck's slides are rendered to look at: `local`, with LibreOffice on
  this computer, or `drive`, through Google Drive. Shared as `render.previews`;
  after shared setup, an empty choice follows the delivery format.
- `brand_skill` is where the brand skill to use is, when the person named one of those
  found, shared as `brand.skill`. None for the first that is found.
- `notify` is whether the runner tells the person, through the computer's own
  notifications, that a training needs a decision while no page is open. Off until they
  turn it on.
- `look_for_updates` is whether the runner asks, at most once a day, which releases of
  Training Studio, its companion skills and the brand skill exist. On until they turn it
  off. See `upkeep`.
- `brand_repository` is the address of the brand skill's own repository, https, ssh or a
  folder, from which the page installs and upgrades it; None until the person names one.
  `brand_release` is the release tag to install from it, None for the newest. Neither is
  needed to use a brand skill installed by hand. Whether the repository can be reached is
  `brand_source`'s to say; here only its shape is checked.
- A value that makes no sense is refused with a sentence, not corrected silently.
"""
from __future__ import annotations

import functools
import json  # noqa: F401  read by the shared parts
import re  # noqa: F401  read by the shared parts
from dataclasses import asdict, dataclass, replace  # noqa: F401  replace: read by the shared parts
from pathlib import Path

import runner  # noqa: F401  puts the core on the import path
import studio_core  # noqa: F401  read by the shared parts
import home
import hub  # noqa: F401  read by the shared parts
from workspace import WorkspaceError

from runner import studios_config

from studio_core import modules
from studio_core.shared_runner import settings as _shared
modules.bind(globals(), _shared, _shared.NAMES)

ADDRESS = 2000                  # characters in a repository's address
# The settings every studio shares, each with where the studios config keeps it.
SHARED = {'agent': ('assistant', 'agent'), 'model': ('assistant', 'model'),
          'effort': ('assistant', 'effort'), 'brand_repository': ('brand', 'repository'),
          'brand_release': ('brand', 'release'),
          'previews': ('render', 'previews'), 'brand_skill': ('brand', 'skill')}


@dataclass(frozen=True)
class Settings:
    """This computer's choices for the runner."""
    agent: str = 'claude'
    model: str | None = None
    effort: str | None = None
    step_seconds: int = 900
    training_dollars: float = 20.0
    parallel: int = 2
    previews: str | None = None
    brand_skill: str | None = None
    notify: bool = False
    look_for_updates: bool = True
    brand_repository: str | None = None
    brand_release: str | None = None

    @property
    def limits(self) -> dict:
        return {'step_seconds': self.step_seconds, 'training_dollars': self.training_dollars,
                'parallel': self.parallel}


@functools.lru_cache(maxsize=None)
def claude_models() -> dict:
    """Claude Code's models, read once from the file beside this one. See read_models."""
    return read_models(CLAUDE_MODELS)


def check(chosen: Settings) -> Settings:
    """The same settings, once every one of them makes sense."""
    agent = check_agent(chosen.agent)
    repository = check_repository(chosen.brand_repository)
    return Settings(
        agent=agent, model=check_model(chosen.model),
        effort=check_effort(chosen.effort, agent, chosen.model),
        step_seconds=number(chosen.step_seconds, 'The time for one step, in seconds,',
                            *SECONDS, True),
        training_dollars=number(chosen.training_dollars,
                                'What a training may spend, in dollars,', 0.01, DOLLARS, False),
        parallel=number(chosen.parallel, 'How many trainings run at once', *PARALLEL, True),
        previews=check_previews(chosen.previews), brand_skill=check_place(chosen.brand_skill),
        notify=check_notify(chosen.notify),
        look_for_updates=check_look(chosen.look_for_updates),
        brand_repository=repository,
        brand_release=check_release(chosen.brand_release, repository))


def _group(found, name):
    value = found.get(name)
    return value if isinstance(value, dict) else {}


def from_shared(found: dict) -> dict:
    """The shared settings the studios config holds, by name, each as Training Studio can
    use it and None where it cannot. A model or a level named for an agent Training Studio
    does not have is not for it."""
    assistant, brand = (found.get(name) if isinstance(found.get(name), dict) else {}
                        for name in ('assistant', 'brand'))
    named = assistant.get('agent')
    agent = None if named is None else passes(check_agent, named)
    usable = named is None or agent is not None
    model = passes(check_model, assistant.get('model')) if usable else None
    effort = passes(check_effort, assistant.get('effort'), agent or Settings().agent,
                     model) if usable else None
    repository = brand.get('repository')
    repository = passes(check_repository, repository) if isinstance(repository, str) else None
    release = brand.get('release')
    release = passes(check_release, release, repository) \
        if isinstance(release, str) and repository else None
    return {'agent': agent, 'model': model, 'effort': effort,
            'brand_repository': repository, 'brand_release': release,
            'previews': passes(check_previews, _group(found, 'render').get('previews')),
            'brand_skill': (str(Path(brand['skill']).expanduser())
                            if passes(check_place, brand.get('skill')) else None)}


def shared_now(found: dict) -> dict:
    """The shared settings as Training Studio uses them, from what the studios config holds:
    those it can use, and the default for the rest."""
    shared = from_shared(found)
    from studio_core.preferences import ready
    if shared['previews'] is None and ready(found):
        shared['previews'] = 'drive' if found.get('output') == 'google' else 'local'
    return {**shared, 'agent': shared['agent'] or Settings().agent}


def changes(before: Settings, after: Settings) -> dict:
    """The shared settings `after` changes from `before`, shaped as the studios config is."""
    found = {}
    for name, (group, key) in SHARED.items():
        if not _same(getattr(before, name), getattr(after, name)):
            found.setdefault(group, {})[key] = getattr(after, name)
    return found


# The shared settings that belong to another, which they are written beside.
OWNS = {'agent': ('model', 'effort'), 'brand_repository': ('brand_release',)}
# Each shared setting as a sentence names it.
NAMED = {'agent': 'The agent', 'model': 'The model', 'effort': 'The reasoning level',
         'brand_repository': "The brand skill's repository",
         'brand_release': "The brand skill's release",
         'previews': 'Slide previews', 'brand_skill': 'The installed brand skill'}


class Stale(WorkspaceError):
    """A change to a value another studio changed too, refused. `what` names the value as a
    sentence begins with it."""

    def __init__(self, what: str):
        super().__init__(STALE.format(what))
        self.what = what


def writes(chosen: Settings, before: Settings, found: dict) -> dict:
    """What saving `chosen` writes into the studios config while it holds `found`, shaped
    as the file is, when the form was shown `before`: each shared setting the person
    changed, with the agent beside its model and level, and the repository beside its
    release, where the file names another. Refuses, in a sentence, a change to a value
    another studio changed too."""
    changed = changes(before, chosen)
    for owner, owned in OWNS.items():
        group, key = SHARED[owner]
        held = found.get(group) if isinstance(found.get(group), dict) else {}
        if changed.get(group) and held.get(key) is not None \
                and not _same(held[key], getattr(chosen, owner)):
            for name in (owner, *owned):
                value = getattr(chosen, name)
                if value is not None or SHARED[name][1] in held:
                    changed[group][SHARED[name][1]] = value
    now = shared_now(found)
    for name, (group, key) in SHARED.items():
        if key in changed.get(group, {}) and not _same(now[name], getattr(before, name)) \
                and not _same(now[name], getattr(chosen, name)):
            raise Stale(NAMED[name])
    return changed


def save(chosen: Settings, shown: Settings | None = None) -> Settings:
    """Keep these settings: each shared one that changed in the studios config, the rest on
    this computer. A shared one that cannot be written is refused before anything is kept.

    `shown` is what the form that sent them was shown, where it says. Then only what the
    person changed from that is written, so a value another studio changed meanwhile is
    kept, and a change to a value that another studio changed too is refused. What is
    written is worked out from the file under its lock (see `writes`)."""
    chosen = check(chosen)
    before = shown if shown is not None else load()
    if changes(before, chosen):
        studios_config.update(lambda found: writes(chosen, before, found))
    home.write_json(path(), {'schema': SCHEMA, **{
        name: value for name, value in asdict(chosen).items() if name not in SHARED}})
    return chosen


def own() -> dict:
    """The shared settings runner.json still holds from before they were shared, by name,
    each that can be used. Nothing when it holds none."""
    kept = _kept()
    found = from_shared({
        'assistant': {'agent': kept.get('agent'), 'model': kept.get('model'),
                      'effort': kept.get('effort')},
        'brand': {'repository': kept.get('brand_repository'),
                  'release': kept.get('brand_release'), 'skill': kept.get('brand_skill')},
        'render': {'previews': kept.get('previews')}})
    return {name: value for name, value in found.items() if value is not None}


