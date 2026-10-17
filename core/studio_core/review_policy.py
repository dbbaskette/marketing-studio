"""Saved review preferences. Automation accepts intermediate work, never publishes it."""
from hashlib import sha256
import json

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


def automatic(record, product, gate, last=None):
    chosen = level(record)
    if chosen == 'step_by_step':
        return False
    if product == 'presentation':
        return gate not in (('gate:outline', 'gate:build') if chosen == 'balanced'
                            else ('gate:build',))
    if product == 'blog':
        return gate not in (('outline', last) if chosen == 'balanced' else (last,))
    if product == 'training':
        return not gate.startswith('review:') and gate not in ('documents', 'intake', 'deck')
    raise ValueError('Unknown studio review policy.')


def fingerprint(value):
    return sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def receipt(record, gate, evidence, at):
    record.setdefault('review_events', []).append({
        'gate': gate, 'by': 'review-policy', 'level': level(record),
        'evidence': fingerprint(evidence), 'at': at,
        'decision': 'continued-automatically'})
