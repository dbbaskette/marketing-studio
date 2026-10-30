"""Shared content-before-design checkpoint for newly started studio desks.

The marker is saved with the run. Old runs and explicitly requested design
walkthroughs keep their existing decisions; restarting never migrates approval.
"""
PROTOCOL = 'slide-text-first-v1'


def enabled(record):
    return record.get('deck_content') == PROTOCOL


def checkpoint(record, gate):
    return enabled(record) and gate.partition('@')[0] in (
        'gate:deck-outline', 'gate:outline')
