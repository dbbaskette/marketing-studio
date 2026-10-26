"""Saved review preferences. Automation accepts intermediate work, never publishes it."""
from hashlib import sha256
import json

from studio_core import deck_flow

LEVELS = ('balanced', 'automatic', 'step_by_step')
LABELS = {'balanced': 'Balanced', 'automatic': 'Automatic draft',
          'step_by_step': 'Step by step'}


def check(value):
    if not isinstance(value, dict) or set(value) - {'level'} \
            or value.get('level') not in LEVELS:
        raise ValueError('Choose Balanced, Automatic draft, or Step by step.')


def snapshot(values):
    value = values.get('review', {'level': 'balanced'})
    check(value)
    return {'schema': 1, 'level': value['level']}


STALE = 'Another studio changed where new work stops. Reload the page and try again.'


def effective(values, problem=None):
    """The level a form shows from what the studios config holds: Balanced when it names
    none, Step by step when what it names cannot be used or the file cannot be read."""
    if problem:
        return 'step_by_step'
    if 'review' not in (values or {}):
        return 'balanced'
    value = values['review']
    try:
        check(value)
    except ValueError:
        return 'step_by_step'
    return value['level']


def change(update, level, seen):
    """Write `level` as the one new work starts at in every studio, under the file's lock,
    through `update` (a studio's studios_config.update). Refused, with nothing written,
    when the file no longer holds `seen`, the level the form read, unless it already holds
    `level`: a start that wrote it and then failed is tried again from the same form."""
    check({'level': level})

    def guard(current):
        if effective(current) not in (seen, level):
            raise ValueError(STALE)
    return update({'review': {'level': level}}, guard=guard)


def ahead(record, product, gates, last=None, first='outline', run_gates=None):
    """The gates of `gates`, in order, that the run's level always stops at: those the
    policy does not accept with nothing holding them. A gate a grave finding may still
    keep is not among them. `run_gates`, every gate the run has, says where a combined
    stop is held, as deck_flow.stops does; `gates` may be only those still to come."""
    return [gate for gate in gates
            if not automatic(record, product, gate, last=last, holding=(), first=first,
                             run_gates=run_gates)]


def capture():
    from studio_core import studios_config
    values, problem = studios_config.read()
    # Unusable stored defaults must not break setup or increase autonomy. Saved run
    # policies still use level()'s strict schema validation.
    return {'schema': 1, 'level': effective(values, problem)}


def level(record):
    value = record.get('review_policy')
    if value is None:
        return 'step_by_step'  # old work keeps its original contract
    if not isinstance(value, dict) or type(value.get('schema')) is not int \
            or value.get('schema') != 1 or value.get('level') not in LEVELS:
        raise ValueError('This run has an unsupported review policy. Restore its saved settings.')
    return value['level']


# What a reviewer or an audit may still find when a gate comes up: a finding this grave, or
# an audit blocker, keeps the gate for the person whatever the saved level.
GRAVE = ('critical', 'major')
# Training Studio gates the policy never accepts: the person's own steps (adding documents,
# the form, a deck made in a conversation). A deck's own gates follow studio_core.deck_flow.
TRAINING_KEPT = ('documents', 'intake', 'deck')


def held(findings=(), blockers=()):
    """What keeps a gate for the person, a sentence each: every critical or major finding
    still open, and every blocker an audit found. Empty when nothing does."""
    kept = []
    for finding in findings or ():
        if isinstance(finding, dict) and finding.get('severity') in GRAVE:
            where = finding.get('slide') or finding.get('number')
            kept.append(f"{finding['severity'].capitalize()}"
                        + (f' on {where}' if where else '') + ': '
                        + str(finding.get('note') or finding.get('detail') or '').strip())
    for blocker in blockers or ():
        if isinstance(blocker, dict):
            kept.append('Audit blocker: ' + str(blocker.get('says') or blocker.get('code')
                                                or '').strip())
        elif blocker:
            kept.append('Audit blocker: ' + str(blocker))
    return kept


def automatic(record, product, gate, last=None, holding=(), first='outline',
              run_gates=None):
    """Whether the saved level accepts `gate` without the person. Never while `holding`, what
    `held()` found still open, has anything in it. A Training Studio gate may carry its
    level, as `gate:deck@101`: the policy reads the gate without it. A blog under Balanced
    stops at `first`, its first writing stage (the outline when it has one, else the draft),
    and at `last`. `run_gates`, every gate the run has, lets a combined deck stop be held
    where the run has a stop (deck_flow.stops)."""
    chosen = level(record)
    if chosen == 'step_by_step' or holding:
        return False
    # A deck's checkpoints pause the same way in every studio: the brand's draft, look and
    # final, as deck_flow.PAUSES says for this level.
    deck = deck_flow.stops(product, chosen, gate, gates=run_gates)
    if deck is not None:
        return not deck
    if product == 'presentation':
        # Rehearsal is the person's own, and never comes up yet.
        return gate not in (('gate:outline', 'gate:build', 'rehearse') if chosen == 'balanced'
                            else ('gate:build', 'rehearse'))
    if product == 'blog':
        return gate not in ((first, last) if chosen == 'balanced' else (last,))
    if product == 'training':
        base = gate.partition('@')[0]
        # Balanced reads the research plan: a short read, and the cheapest decision there is.
        return not base.startswith('review:') and base not in TRAINING_KEPT \
            and not (chosen == 'balanced' and base == 'gate:research-plan')
    raise ValueError('Unknown studio review policy.')


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def receipt(record, gate, evidence, at, note=None):
    """Record that the policy continued `gate`, bound to its evidence. `note` says, in words
    kept as they are, anything the person should know of how, such as a look chosen from
    samples that could not be rendered, and why."""
    record.setdefault('review_events', []).append({
        'gate': gate, 'by': 'review-policy', 'level': level(record),
        'evidence': fingerprint(evidence), 'at': at,
        'decision': 'continued-automatically', **({'note': str(note)} if note else {})})
