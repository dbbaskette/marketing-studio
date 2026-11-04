"""Private queued concerns; saving never changes evidence, scope or approvals."""
from . import intake_drafts


def dispatch(data, project, section, sent):
    if not isinstance(section, str) or not 1 <= len(section) <= 160:
        raise ValueError('Choose a section from the research preview.')
    if sent.get('action') == 'save':
        patch = sent.get('patch')
        if not isinstance(patch, dict) or set(patch) - {'basis', 'note'}:
            raise ValueError('Queue only a note and its section revision.')
        if 'basis' in patch and (not isinstance(patch['basis'], str) or not 1 <= len(patch['basis']) <= 256):
            raise ValueError('Keep the section revision with this note.')
        if 'note' in patch and (not isinstance(patch['note'], str) or len(patch['note']) > 4000):
            raise ValueError('Keep the queued note within four thousand characters.')
    held = intake_drafts.dispatch(data, {'kind':'research-note', 'project':str(project), 'section':section}, sent)
    return {'revision':held['revision']} if sent.get('action') == 'save' else held
