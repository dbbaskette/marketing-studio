"""Where an infographic stands, in words, from its saved revision alone. Read-only."""
from __future__ import annotations


def readiness(project):
    """A short working state for lists. Exact revision identity is reported beside it."""
    checks = project['checks']
    if project['approval'] is not None:
        return {'state': 'done', 'summary': 'Approved: ready to export and deliver'}
    if checks and all(c['status'] == 'passed' for c in checks):
        return {'state': 'review', 'summary': 'Checked: waiting for your approval'}
    if checks:
        return {'state': 'review', 'summary': 'Checks need attention'}
    if any(a['state'] in ('queued', 'running', 'unknown') for a in project['attempts']):
        return {'state': 'review', 'summary': 'Artwork request needs checking'}
    if project['scene'] is not None:
        return {'state': 'current', 'summary': 'Page built: review the preview'}
    if project['selected_story'] is not None:
        return {'state': 'current', 'summary': 'Story chosen: build the page'}
    if project['stories']:
        return {'state': 'review', 'summary': 'Stories proposed: choose one'}
    if project['sources']:
        return {'state': 'current', 'summary': 'Information added: find the story'}
    return {'state': 'current', 'summary': 'Brief saved: add information'}
