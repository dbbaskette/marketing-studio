"""Shared model choices and deterministic routing, independent of worker permissions."""
from copy import deepcopy
from contextvars import ContextVar

from studio_core import runtime

NAMES = ('quick', 'main', 'complex')
EFFORTS = {'claude': ('low', 'medium', 'high', 'xhigh', 'max'),
           'codex': ('none', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max', 'ultra')}
POLICY = 2
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
            raise ValueError(f'Give a model ID for the {name.title()} profile.')
    return models


def visible(values):
    models = values.get('models', {})
    if not isinstance(models, dict):
        return models
    result = {key: models.get(key) for key in ('schema', 'agent', 'mode')}
    result['profiles'] = {name: {key: (models.get('profiles', {}).get(name) or {}).get(key)
                               for key in ('selection', 'model', 'effort')} for name in NAMES}
    return result


def check_changes(changes):
    if not isinstance(changes, dict) or set(changes) - {'schema', 'agent', 'mode', 'profiles'}:
        raise ValueError('That model setting is not recognized.')
    for key in ('schema', 'agent', 'mode'):
        if key in changes and (isinstance(changes[key], (dict, list))):
            raise ValueError('Use plain values for model settings.')
    profiles = changes.get('profiles', {})
    if not isinstance(profiles, dict) or set(profiles) - set(NAMES):
        raise ValueError('Choose Quick, Main, or Complex model profiles.')
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
    profiles = {}
    for name in NAMES:
        profile = (models.get('profiles') or {}).get(name, {}) if mode == 'by_task' else {}
        selection = profile.get('selection', 'inherit')
        selected = {'model': model or None, 'effort': effort or None}
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


def route(record, product, step, *, purpose=None, effort_key='effort'):
    """Only structured task IDs choose a tier. Retries keep their tier and permissions."""
    base = step.split('@', 1)[0].split(':', 1)[0]
    profile = 'main'
    if base in ('classify', 'extract', 'source-classification'):
        profile = 'quick'
    elif purpose != 'review' and (base in ('build-repair', 'deck-repair') or purpose == 'repair'):
        profile = 'complex'
    saved = record.get('model_profiles')
    if product == 'Presentation Studio' and isinstance(saved, dict) and saved.get('policy') == 2:
        if base in ('outline', 'classify', 'extract'):
            profile = 'quick'
        elif purpose == 'repair-escalated':
            profile = 'complex'
        else:
            profile = 'main'
    if saved:
        if not isinstance(saved, dict) or type(saved.get('schema')) is not int \
                or saved.get('schema') != 1 or type(saved.get('policy')) is not int \
                or saved.get('policy') not in (1, POLICY):
            raise ValueError('This run uses a newer model routing policy. Update the studio to continue.')
        agent = record.get('agent') or record.get('engine')
        if saved.get('agent') != agent:
            raise ValueError('The saved model profiles belong to a different assistant.')
        if saved.get('mode') not in ('single', 'by_task') \
                or not isinstance(saved.get('profiles'), dict) \
                or any(not isinstance(saved['profiles'].get(name), dict) for name in NAMES):
            raise ValueError('The saved model profiles are incomplete. Restore the run record before continuing.')
        if saved['mode'] == 'single':
            profile = 'main'
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
