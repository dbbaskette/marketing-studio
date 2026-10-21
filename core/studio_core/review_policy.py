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


def capture():
    from studio_core import studios_config
    values, problem = studios_config.read()
    if problem:
        # Never increase autonomy when settings cannot be read.
        return {'schema': 1, 'level': 'step_by_step'}
    return snapshot(values)


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


def automatic(record, product, gate, last=None, holding=()):
    """Whether the saved level accepts `gate` without the person. Never while `holding`, what
    `held()` found still open, has anything in it. A Training Studio gate may carry its
    level, as `gate:deck@101`: the policy reads the gate without it."""
    chosen = level(record)
    if chosen == 'step_by_step' or holding:
        return False
    # A deck's checkpoints pause the same way in every studio: the brand's draft, look and
    # final, as deck_flow.PAUSES says for this level.
    deck = deck_flow.stops(product, chosen, gate)
    if deck is not None:
        return not deck
    if product == 'presentation':
        # Rehearsal is the person's own, and never comes up yet.
        return gate not in (('gate:outline', 'gate:build', 'rehearse') if chosen == 'balanced'
                            else ('gate:build', 'rehearse'))
    if product == 'blog':
        return gate not in (('outline', last) if chosen == 'balanced' else (last,))
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
