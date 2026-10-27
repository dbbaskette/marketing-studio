"""What the runner is set to: the agent to use by default, the defaults a new deck starts
with, the limits, how a deck's previews are rendered, and where the brand skill is installed
from.

What a caller needs to know
---------------------------
    chosen = settings.load()                      # the defaults when nothing is saved
    settings.save(replace(chosen, agent='codex', deck_dollars=10))

- Two places hold them. The values every studio on this computer shares are kept only in
  the studios config (`studios_config`), and read from it each time: the agent, its model
  and its level (`assistant.agent`, `.model`, `.effort`), the person's name (`person.name`),
  the brand skill's repository and release, the brand and its variant (`brand.repository`,
  `.release`, `.brand`, `.variant`, `.skill`), the output (`output`) and slide
  previews (`render.previews`). SHARED names them. A value
  there that would be refused here is the default, and so is every one of them while the
  file cannot be read. The rest belong to Presentation Studio on this computer alone, and
  are kept in the per-user data folder as `runner.json`, beside the workspace `gitstate`
  remembers there. Nothing here is written into the repository: two people who share a
  workspace can use different agents and different limits.
- `save` writes into the studios config only the shared values that differ from what
  `load` reads there now, then `runner.json`. Where a shared value changed and the file
  cannot be read or written, it refuses before anything is kept, and the file is left as it
  is. A value in the file that Presentation Studio cannot use is never written over by a
  save that did not change it.
- `own()` is what `runner.json` still holds of the shared values from before they were
  shared, and `forget_own()` takes them out of it. See `setup.migrate`.
- `model` is the model the agent is asked for and `effort` how hard it reasons, its
  reasoning level; None for each is the agent's own choice. A level is one of the words an
  agent takes (EFFORTS): which of them a model takes is what the agent lists. Claude Code
  lists nothing, so its models and their levels are kept in `claude-code-models.json`
  in the shared core, and a level its model does not take is refused (`takes`).
- `step_seconds` is how long one worker may run. `deck_dollars` is what one deck
  may spend, where the agent reports spending, before it stops and asks. `parallel` is how
  many decks work at once.
- `previews` is how a deck's slides are rendered to look at: `local`, with LibreOffice on
  this computer, or `drive`, through Google Drive. Shared as `render.previews`;
  after shared setup, an empty choice follows the delivery format.
- `brand_skill` is where the brand skill to use is, when the person named one of those
  found, shared as `brand.skill`. None for the first that is found.
- `notify` is whether the runner tells the person, through the computer's own
  notifications, that a deck needs a decision while no page is open. Off until they
  turn it on.
- `look_for_updates` is whether the runner asks, at most once a day, which releases of
  Presentation Studio, its companion skills and the brand skill exist. On until they turn it
  off. See `upkeep`.
- `brand_repository` is the address of the brand skill's own repository, https, ssh or a
  folder, from which the page installs and upgrades it; None until the person names one.
  `brand_release` is the release tag to install from it, None for the newest. Neither is
  needed to use a brand skill installed by hand. Whether the repository can be reached is
  `brand_source`'s to say; here only its shape is checked. `brand_source()` gives both, and
  is how every other part reads them.
- `name` is the person's own name, as set-up shows it; None until they give it. git's own
  identity still signs each commit and each claim.
- `brand` and `variant` are the brand a new deck is offered first, as the brand skill names
  them, and `output` what it is made as: `google` (Google Slides) or `pptx`. None for
  either brand or variant is the first the installed brand skill lists: no brand is named
  here. A deck's own form says what it is made with.
- A value that makes no sense is refused with a sentence, not corrected silently.
"""
from __future__ import annotations

import functools
import json  # noqa: F401  read by the shared parts
import re
from dataclasses import asdict, dataclass, replace  # noqa: F401  replace: read by the shared parts
from pathlib import Path

import runner  # noqa: F401  puts the core on the import path
import studio_core  # noqa: F401  read by the shared parts
import home
import hub  # noqa: F401  read by the shared parts
import studios_config
from workspace import WorkspaceError

from studio_core import modules
from studio_core.shared_runner import settings as _shared
modules.bind(globals(), _shared, _shared.NAMES)

OUTPUTS = ('google', 'pptx')    # what a new deck is made as
WORD = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$')   # a brand's or a variant's name
NAME = 100                  # characters in a person's name
ADDRESS = 2000              # characters in a repository's address
# The settings every studio shares, each with where the studios config keeps it: (group,
# key), or (None, key) for a word at the top of the file.
SHARED = {'agent': ('assistant', 'agent'), 'model': ('assistant', 'model'),
          'effort': ('assistant', 'effort'), 'name': ('person', 'name'),
          'brand': ('brand', 'brand'), 'variant': ('brand', 'variant'),
          'output': (None, 'output'), 'brand_repository': ('brand', 'repository'),
          'brand_release': ('brand', 'release'),
          'previews': ('render', 'previews'), 'brand_skill': ('brand', 'skill')}


@dataclass(frozen=True)
class Settings:
    """This computer's choices for the runner."""
    agent: str = 'claude'
    model: str | None = None
    effort: str | None = None
    step_seconds: int = 900
    deck_dollars: float = 20.0
    parallel: int = 2
    previews: str | None = None
    brand_skill: str | None = None
    notify: bool = False
    look_for_updates: bool = True
    name: str | None = None
    brand: str | None = None
    variant: str | None = None
    output: str = 'google'
    brand_repository: str | None = None
    brand_release: str | None = None

    @property
    def limits(self) -> dict:
        return {'step_seconds': self.step_seconds, 'deck_dollars': self.deck_dollars,
                'parallel': self.parallel}


@functools.lru_cache(maxsize=None)
def claude_models() -> dict:
    """Claude Code's models, read once from the file beside this one. See read_models."""
    return read_models(CLAUDE_MODELS)


def check_name(name) -> str | None:
    """A person's name as they gave it, or None for none."""
    if name is None or name == '':
        return None
    if not isinstance(name, str) or not name.strip() or len(name) > NAME \
            or any(ord(mark) < 32 for mark in name):
        raise WorkspaceError(f'Give your name as text of at most {NAME} characters.')
    return name.strip()


def check_word(value, label: str) -> str:
    """A brand's or a variant's short name, as the brand skill lists it."""
    if not isinstance(value, str) or not WORD.match(value):
        raise WorkspaceError(f'The {label} is a short name, as your brand skill lists it.')
    return value


def check_choice(value, label: str) -> str | None:
    """A brand or a variant as `check_word` takes it, or None for the brand skill's first."""
    return None if value is None or value == '' else check_word(value, label)


def brand_source() -> tuple[str | None, str | None]:
    """Where the brand skill is installed from: (its repository, the release chosen), each
    None until the person names it."""
    chosen = load()
    return chosen.brand_repository, chosen.brand_release


def check_output(output) -> str:
    if output not in OUTPUTS:
        raise WorkspaceError('A deck is made as one of: ' + ', '.join(OUTPUTS) + '.')
    return output


def check(chosen: Settings) -> Settings:
    """The same settings, once every one of them makes sense."""
    agent = check_agent(chosen.agent)
    repository = check_repository(chosen.brand_repository)
    return Settings(
        agent=agent, model=check_model(chosen.model),
        effort=check_effort(chosen.effort, agent, chosen.model),
        step_seconds=number(chosen.step_seconds, 'The time for one step, in seconds,',
                            *SECONDS, True),
        deck_dollars=number(chosen.deck_dollars,
                            'What a deck may spend, in dollars,', 0.01, DOLLARS, False),
        parallel=number(chosen.parallel, 'How many decks run at once', *PARALLEL, True),
        previews=check_previews(chosen.previews), brand_skill=check_place(chosen.brand_skill),
        notify=check_notify(chosen.notify),
        look_for_updates=check_look(chosen.look_for_updates),
        name=check_name(chosen.name), brand=check_choice(chosen.brand, 'brand'),
        variant=check_choice(chosen.variant, 'variant'), output=check_output(chosen.output),
        brand_repository=repository,
        brand_release=check_release(chosen.brand_release, repository))


def _group(found: dict, name: str) -> dict:
    value = found.get(name)
    return value if isinstance(value, dict) else {}


def from_shared(found: dict) -> dict:
    """The shared settings the studios config holds, by name, each as Presentation Studio
    can use it and None where it cannot. A model or a level named for an agent Presentation
    Studio does not have is not for it."""
    assistant, person, brand = (_group(found, name)
                                for name in ('assistant', 'person', 'brand'))
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
            'name': passes(check_name, person.get('name')),
            'brand': passes(check_word, brand.get('brand'), 'brand'),
            'variant': passes(check_word, brand.get('variant'), 'variant'),
            'output': found.get('output') if found.get('output') in OUTPUTS else None,
            'brand_repository': repository, 'brand_release': release,
            'previews': passes(check_previews, _group(found, 'render').get('previews')),
            'brand_skill': (str(Path(brand['skill']).expanduser())
                            if passes(check_place, brand.get('skill')) else None)}


def shared_now(found: dict) -> dict:
    """The shared settings as Presentation Studio uses them, from what the studios config
    holds: those it can use, and the default for the rest."""
    shared = from_shared(found)
    from studio_core.preferences import ready
    if shared['previews'] is None and ready(found):
        shared['previews'] = 'drive' if found.get('output') == 'google' else 'local'
    return {**shared, 'agent': shared['agent'] or Settings().agent,
            'output': shared['output'] or Settings().output}


def _member(changed: dict, group: str | None, key: str) -> bool:
    return key in (changed if group is None else changed.get(group, {}))


def changes(before: Settings, after: Settings) -> dict:
    """The shared settings `after` changes from `before`, shaped as the studios config is."""
    found = {}
    for name, (group, key) in SHARED.items():
        if _same(getattr(before, name), getattr(after, name)):
            continue
        if group is None:
            found[key] = getattr(after, name)
        else:
            found.setdefault(group, {})[key] = getattr(after, name)
    return found


# Each shared setting as a sentence names it.
NAMED = {'agent': 'The agent', 'model': 'The model', 'effort': 'The reasoning level',
         'name': 'Your name', 'brand': 'The brand', 'variant': 'The variant',
         'output': 'The output', 'brand_repository': "The brand skill's repository",
         'brand_release': "The brand skill's release",
         'previews': 'Slide previews', 'brand_skill': 'The installed brand skill'}


def save(chosen: Settings, shown: Settings | None = None) -> Settings:
    """Keep these settings: each shared one that changed in the studios config, the rest on
    this computer. A shared one that cannot be written is refused before anything is kept.

    `shown` is what the form that sent them was shown, where it says. Then only what the
    person changed from that is written, so a value another studio changed meanwhile is
    kept, and a change to a value that another studio changed too is refused."""
    chosen = check(chosen)
    before = shown if shown is not None else load()
    changed = changes(before, chosen)

    def guard(found: dict) -> None:
        now = shared_now(found)
        for name, (group, key) in SHARED.items():
            if _member(changed, group, key) and not _same(now[name], getattr(before, name)) \
                    and not _same(now[name], getattr(chosen, name)):
                raise WorkspaceError(STALE.format(NAMED[name]))

    if changed:
        studios_config.update(changed, guard)
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
        'person': {'name': kept.get('name')},
        'brand': {'repository': kept.get('brand_repository'),
                  'release': kept.get('brand_release'),
                  'brand': kept.get('brand'), 'variant': kept.get('variant'),
                  'skill': kept.get('brand_skill')},
        'render': {'previews': kept.get('previews')},
        'output': kept.get('output')})
    return {name: value for name, value in found.items() if value is not None}


