"""Shared model choices and deterministic routing, independent of worker permissions.

What a caller needs to know
---------------------------
- The shared settings choose a model and reasoning level for each kind of work (`KINDS`):
  Quick (sorting, classifying, extracting, and the first scan that drafts an outline), Research (searching and reading), Combining
  (turning findings into a research report), Checking (independent checks and reviews),
  Writing (outlines, plans, drafts, materials) and Fixing (escalated repairs).
- Settings saved before the kinds existed name Quick, Main and Complex (`LEGACY`). They are
  read, never rewritten: `profiles_of` gives each kind its choice, from the kind's own entry
  when there is one, and otherwise from the older ones (Writing from Main, Fixing from
  Complex) or from the lighter starting level (`STARTING`) for Research, Combining and
  Checking. `visible` shows that to the settings page, with which kinds are new.
- `capture` resolves the choices once, when work starts, as routing policy 3. Work saved
  under policies 1 and 2 keeps its Quick, Main and Complex choices and routes as it did.
- `route(record, product, step)` names the kind of one assistant job from its structured
  step ID and purpose (`kind_of`), and gives its model and reasoning.
- `refreshed(record, ...)` and `differences(before, after)` let a stopped run take up the
  current settings: what each kind runs on before and after, for the person to confirm.
"""
from copy import deepcopy
from contextvars import ContextVar

from studio_core import runtime

KINDS = ('quick', 'research', 'combining', 'checking', 'writing', 'fixing')
LEGACY = ('quick', 'main', 'complex')
NAMES = KINDS + ('main', 'complex')   # every profile name a settings file may hold
# Where a kind's choice comes from while the settings have no entry of their own for it, and
# which profile it ran on under policies 1 and 2.
OLDER = {'quick': 'quick', 'research': 'main', 'combining': 'main', 'checking': 'main',
         'writing': 'main', 'fixing': 'complex'}
# The reasoning a kind starts at, on its older profile's model, until it is chosen.
STARTING = {'research': 'medium', 'combining': 'medium', 'checking': 'medium'}
TITLES = {'quick': 'Quick', 'research': 'Research', 'combining': 'Combining',
          'checking': 'Checking', 'writing': 'Writing', 'fixing': 'Fixing',
          'main': 'Main', 'complex': 'Complex'}
EFFORTS = {'claude': ('low', 'medium', 'high', 'xhigh', 'max'),
           'codex': ('none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra')}
POLICY = 3
_PENDING = ContextVar('studio_model_job', default=None)


def merge(current, changes):
    result = deepcopy(current) if isinstance(current, dict) else {}
    for key, value in changes.items():
        result[key] = merge(result.get(key, {}), value) if isinstance(value, dict) else value
    return result


def leaves(values, prefix=()):
    for key, value in values.items():
        if isinstance(value, dict):
            yield from leaves(value, (*prefix, key))
        else:
            yield (*prefix, key), value


def get(values, path):
    for key in path:
        values = values.get(key) if isinstance(values, dict) else None
    return values


def check_choice(model, effort, agent):
    if not isinstance(agent, str) or agent not in EFFORTS:
        raise ValueError('Choose Claude Code or Codex.')
    if model is not None and (not isinstance(model, str) or len(model) > 100
            or model.startswith('-') or any(c.isspace() or ord(c) < 32 for c in model)):
        raise ValueError('Give a model ID available to your assistant, without spaces.')
    if effort and effort not in EFFORTS[agent]:
        raise ValueError('Choose a reasoning level supported by that assistant.')


def check(values):
    if not isinstance(values.get('assistant', {}), dict):
        raise ValueError('The assistant settings must be an object.')
    models = values.get('models', {})
    if not isinstance(models, dict) or type(models.get('schema', 1)) is not int \
            or models.get('schema', 1) != 1:
        raise ValueError('Model profiles need settings schema 1.')
    mode = models.get('mode', 'single')
    if mode not in ('single', 'by_task'):
        raise ValueError('Choose one model or models by task.')
    raw_agent = (values.get('assistant') or {}).get('agent')
    agent = runtime.assistant_default() if raw_agent in (None, '') else raw_agent
    if not isinstance(agent, str) or agent not in EFFORTS:
        raise ValueError('Choose Claude Code or Codex.')
    profiles = models.get('profiles', {})
    if not isinstance(profiles, dict):
        raise ValueError('Model profiles must be an object.')
    if mode == 'by_task' and models.get('agent') != agent:
        raise ValueError('Review the model profiles for the selected assistant before saving.')
    for name in NAMES:
        profile = profiles.get(name, {})
        if not isinstance(profile, dict):
            raise ValueError('Each model profile must be an object.')
        selection = profile.get('selection', 'inherit')
        if selection not in ('inherit', 'provider_default', 'explicit'):
            raise ValueError('Choose the shared model, assistant default, or a model ID.')
        # Dormant explicit choices still belong to their recorded assistant.
        bound = models.get('agent', agent)
        if not isinstance(bound, str) or bound not in EFFORTS:
            raise ValueError('Model profiles must name a supported assistant.')
        check_choice(profile.get('model'), profile.get('effort'), bound)
        if selection == 'explicit' and not profile.get('model'):
            raise ValueError(f'Give a model ID for the {TITLES[name]} profile.')
    return models


def profiles_of(models):
    """Each kind's saved choice, and the kinds the settings do not name yet (see the module
    notes). Choices are selection, model and effort, as saved."""
    saved = (models.get('profiles') if isinstance(models, dict) else None) or {}
    saved = saved if isinstance(saved, dict) else {}
    chosen, new = {}, []
    for kind in KINDS:
        own = saved.get(kind)
        if isinstance(own, dict):
            chosen[kind] = {key: own.get(key) for key in ('selection', 'model', 'effort')}
            continue
        new.append(kind)
        older = saved.get(OLDER[kind])
        older = older if isinstance(older, dict) else {}
        selection = older.get('selection') or 'inherit'
        found = {'selection': selection, 'model': older.get('model'), 'effort': older.get('effort')}
        if selection == 'inherit':
            # A shared-model profile's reasoning was never shown or used; it stays unused.
            found['effort'] = None
        if kind in STARTING and selection != 'provider_default':
            found['effort'] = STARTING[kind]
        chosen[kind] = found
    return chosen, new


def visible(values):
    models = values.get('models', {})
    if not isinstance(models, dict):
        return models
    result = {key: models.get(key) for key in ('schema', 'agent', 'mode')}
    result['profiles'], result['new'] = profiles_of(models)
    return result


def check_changes(changes):
    if not isinstance(changes, dict) or set(changes) - {'schema', 'agent', 'mode', 'profiles'}:
        raise ValueError('That model setting is not recognized.')
    for key in ('schema', 'agent', 'mode'):
        if key in changes and (isinstance(changes[key], (dict, list))):
            raise ValueError('Use plain values for model settings.')
    profiles = changes.get('profiles', {})
    if not isinstance(profiles, dict) or set(profiles) - set(NAMES):
        raise ValueError('Choose a model for Quick, Research, Combining, Checking, Writing '
                         'or Fixing work.')
    for profile in profiles.values():
        if not isinstance(profile, dict) or set(profile) - {'selection', 'model', 'effort'}:
            raise ValueError('That model profile setting is not recognized.')
        if any(value is not None and not isinstance(value, str) for value in profile.values()):
            raise ValueError('Use text for model profile choices.')


def snapshot(values, agent, model=None, effort=None):
    """Resolve defaults once. A different work-level choice takes precedence as one model."""
    models = check(values)
    assistant = values.get('assistant') or {}
    shared = (assistant.get('agent') or agent, assistant.get('model') or None,
              assistant.get('effort') or None)
    override = (agent, model or None, effort or None) != shared
    mode = 'single' if override else models.get('mode', 'single')
    chosen = profiles_of(models)[0]
    profiles = {}
    for name in KINDS:
        profile = chosen[name] if mode == 'by_task' else {}
        selection = profile.get('selection') or 'inherit'
        # The shared model, at the kind's own reasoning when it has one.
        selected = {'model': model or None, 'effort': profile.get('effort') or effort or None}
        if selection == 'provider_default':
            selected = {'model': None, 'effort': None}
        elif selection == 'explicit':
            selected = {'model': profile['model'], 'effort': profile.get('effort') or None}
        check_choice(selected['model'], selected['effort'], agent)
        profiles[name] = {**selected, 'source': 'work' if override else selection}
    return {'schema': 1, 'policy': POLICY, 'agent': agent, 'mode': mode, 'profiles': profiles}


def capture(agent, model=None, effort=None, validate=None):
    from studio_core import studios_config
    values, problem = studios_config.read()
    # Existing workspaces may still use their validated defaults when the shared
    # file is unreadable. Never write that file or enable task routing from it.
    saved = snapshot({} if problem else values, agent, model, effort)
    if validate:
        for profile in saved['profiles'].values():
            validate(profile['effort'], agent, profile['model'])
    return saved


# Which kind of work a job is (policy 3), from its structured step ID and purpose. Bases are
# the step ID before any `@level` or `:part`; Blog Studio's tool jobs name their kind as the
# purpose of a `draft` step.
# Training Studio's scan drafts the training outline in a few minutes, for the person to
# shape before research starts (#297): it is quick on purpose.
QUICK_BASES = ('classify', 'extract', 'source-classification', 'scan')
CHECKING_PURPOSES = ('review', 'research-review', 'finish-facts', 'finish-feedback',
                     'finish-geo', 'geo-report')
COMBINING_STEPS = ('research-author', 'research-synthesize')
RESEARCH_STEPS = ('research', 'research-plan', 'research-discovery', 'research-investigate',
                  'claims-map')
RESEARCH_PURPOSES = ('research', 'find-text', 'desk-research')


def kind_of(product, step, purpose=None):
    """The kind of work one assistant job is: Quick, Research, Combining, Checking, Writing
    or Fixing. Anything not named here is Writing."""
    plain = step.split('@', 1)[0]
    base, _, part = plain.partition(':')
    phase = part.split('-', 1)[0]
    if purpose in CHECKING_PURPOSES or plain == 'research-review' \
            or (base == 'research' and phase == 'review'):
        return 'checking'
    if purpose == 'repair-escalated' or base == 'deck-repair' or purpose == 'repair':
        return 'fixing'
    if base in QUICK_BASES or (product == 'Presentation Studio' and base == 'outline'):
        return 'quick'
    if plain in COMBINING_STEPS or (base == 'research' and phase in ('author', 'synthesize')):
        return 'combining'
    if base in RESEARCH_STEPS or purpose in RESEARCH_PURPOSES:
        return 'research'
    return 'writing'


def chosen_by_kind(record, effort_key='effort'):
    """What each kind of work in a run runs on, as {kind: (model, effort)}, whichever policy
    its choices were saved under."""
    saved = record.get('model_profiles')
    if not isinstance(saved, dict) or not isinstance(saved.get('profiles'), dict):
        held = (record.get('model') or None, record.get(effort_key) or None)
        return {kind: held for kind in KINDS}
    found = {}
    for kind in KINDS:
        name = kind if saved.get('policy') == POLICY else (
            'main' if saved.get('mode') == 'single' else OLDER[kind])
        profile = saved['profiles'].get(name) or {}
        found[kind] = (profile.get('model') or None, profile.get('effort') or None)
    return found


def differences(record, refreshed, effort_key='effort'):
    """The kinds whose model or reasoning a refresh changes, each with before and after."""
    before = chosen_by_kind(record, effort_key)
    after = chosen_by_kind({**record, 'model_profiles': refreshed}, effort_key)
    return [{'kind': kind, 'title': TITLES[kind],
             'before': {'model': before[kind][0], 'effort': before[kind][1]},
             'after': {'model': after[kind][0], 'effort': after[kind][1]}}
            for kind in KINDS if before[kind] != after[kind]]


def refreshed(record, agent, model=None, effort=None, validate=None):
    """A stopped run's choices, made again from the current settings (policy 3). The run's
    own assistant, model and reasoning stay its starting choice, as when it began."""
    return capture(agent, model, effort, validate)


def _legacy(product, base, purpose, policy):
    """The Quick, Main or Complex profile a job ran on under policies 1 and 2, unchanged."""
    profile = 'main'
    if base in ('classify', 'extract', 'source-classification'):
        profile = 'quick'
    elif purpose != 'review' and (base in ('build-repair', 'deck-repair') or purpose == 'repair'):
        profile = 'complex'
    if product == 'Presentation Studio' and policy == 2:
        if base in ('outline', 'classify', 'extract'):
            profile = 'quick'
        elif purpose == 'repair-escalated':
            profile = 'complex'
        else:
            profile = 'main'
    return profile


def route(record, product, step, *, purpose=None, effort_key='effort'):
    """Only structured task IDs choose a profile. Retries keep their profile and permissions."""
    base = step.split('@', 1)[0].split(':', 1)[0]
    # A research job's receipt names its phase: research:author-2 is research-author.
    phase, _, number = step.split('@', 1)[0].partition(':')[2].rpartition('-')
    if purpose is None and base == 'research' and phase in ('author', 'review') and number.isdigit():
        purpose = 'research-' + phase
    saved = record.get('model_profiles')
    if saved:
        if not isinstance(saved, dict) or type(saved.get('schema')) is not int \
                or saved.get('schema') != 1 or type(saved.get('policy')) is not int \
                or saved.get('policy') not in (1, 2, POLICY):
            raise ValueError('This run uses a newer model routing policy. Update the studio to continue.')
        agent = record.get('agent') or record.get('engine')
        if saved.get('agent') != agent:
            raise ValueError('The saved model profiles belong to a different assistant.')
        names = KINDS if saved['policy'] == POLICY else LEGACY
        if saved.get('mode') not in ('single', 'by_task') \
                or not isinstance(saved.get('profiles'), dict) \
                or any(not isinstance(saved['profiles'].get(name), dict) for name in names):
            raise ValueError('The saved model profiles are incomplete. Restore the run record before continuing.')
        if saved['policy'] == POLICY:
            profile = kind_of(product, step, purpose)
        else:
            profile = 'main' if saved['mode'] == 'single' else _legacy(
                product, base, purpose, saved['policy'])
        selected = {key: saved['profiles'][profile].get(key) for key in ('model', 'effort', 'source')}
        check_choice(selected.get('model'), selected.get('effort'), agent)
    else:
        profile = 'main'
        selected = {'model': record.get('model'), 'effort': record.get(effort_key),
                    'source': 'legacy'}
    return {**selected, 'profile': profile, 'purpose': purpose or base,
            'step': step, 'product': product, 'policy': saved.get('policy') if saved else None,
            'actual_model': None, 'actual_effort': None}


def audit(record, choice, attempt, permission):
    record.setdefault('model_jobs', []).append({**choice, 'attempt': attempt,
                                               'permission': permission})


def staged(owner, choice, attempt, permission, started_at):
    """Keep a completed worker's receipt private until its normal attempt is saved."""
    _PENDING.set((owner, choice, attempt, permission, started_at))


def complete(owner, record, step, started_at):
    pending = _PENDING.get()
    if pending and pending[0] is owner and pending[1]['step'] == step and pending[4] == started_at:
        _, choice, attempt, permission, _ = pending
        audit(record, choice, attempt, permission)
        _PENDING.set(None)
