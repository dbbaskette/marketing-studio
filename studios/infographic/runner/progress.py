"""Where an infographic stands, in words, from its saved revision alone. Read-only."""
from __future__ import annotations


def _reviewed(project, review):
    """A passed review of exactly the current content, by the person or the assistant."""
    from .contracts import basis, digest
    return bool(review and review.get('status') == 'passed' and review.get('basis') == basis(project)
                and review.get('scene_digest') == digest(project['scene']))


def approved_words(approval):
    """Who approved which revision, and whether a rename carried that approval forward."""
    moved = approval.get('carried') or {}
    if moved.get('reason') == 'rename':
        return ('You approved revision ' + str(moved['from_revision']) + '. Renaming kept the '
                'approval for revision ' + str(approval['revision']) + '.')
    return 'You approved revision ' + str(approval['revision']) + '.'


STEPS = (('story', 'Story'), ('draft', 'Draft page'), ('review', 'Review and checks'),
         ('delivery', 'Approved delivery'))


def roadmap(project, deliveries, *, review=None, review_checked=False):
    """The four-step route, the one next stage, and what is complete, needed and downloadable.

    `deliveries` is the desk's delivery listing (each with current/draft/approved_current).
    Every statement comes from saved state; nothing here renders, checks or approves.
    """
    revision = project['revision']
    preview = next((d for d in deliveries if d['current']), None)
    approved_files = next((d for d in deliveries if d['approved_current']), None)
    earlier = next((d for d in deliveries if not d['draft'] and not d['approved_current']), None)
    checks = project['checks']
    passed = bool(checks) and all(c['status'] == 'passed' for c in checks) and review_checked
    story = project['selected_story'] is not None
    if not project['stories']:
        stage = 'story'
    elif not story:
        stage = 'choose'
    elif project['scene'] is None:
        stage = 'build'
    elif project['approval'] is not None:
        # An approval without a current preview was kept by a rename: the approved files
        # are prepared straight from the approved page, with no draft preview first.
        stage = 'deliver' if approved_files else 'export'
    elif preview is None:
        stage = 'preview'
    elif passed:
        stage = 'approve'
    elif _reviewed(project, review) and not review_checked:
        stage = 'check'
    else:
        stage = 'review'
    order = ('story', 'choose', 'build', 'preview', 'review', 'check', 'approve', 'export', 'deliver')
    position = order.index(stage)
    step_of = {'story': 0, 'choose': 0, 'build': 1, 'preview': 1, 'review': 2, 'check': 2,
               'approve': 3, 'export': 3, 'deliver': 4}[stage]
    steps = [{'id': key, 'label': label, 'state': 'done' if index < step_of else 'current' if index == step_of
              else 'upcoming'} for index, (key, label) in enumerate(STEPS)]
    complete = []
    if story:
        complete.append('Story chosen.')
    if preview is not None:
        complete.append(('Approved page' if not preview['draft'] else 'Draft page') + ' rendered for revision '
                        + str(preview['revision']) + '.')
    if passed or project['approval'] is not None:
        complete.append('Review recorded and checks passed.')
    if project['approval'] is not None:
        complete.append(approved_words(project['approval']))
    needs = {
        'story': 'Find the story: your assistant proposes source-backed explanations.',
        'choose': 'Choose one of the proposed stories.',
        'build': 'Build the page from the chosen story.',
        'preview': 'Update the preview so it shows revision ' + str(revision) + '.',
        'review': 'Review the actual page and record what you checked. Checks then run on this computer.',
        'check': 'Run the checks again for revision ' + str(revision) + '.' if checks else
                 'Run the checks for revision ' + str(revision) + '.',
        'approve': 'Approve revision ' + str(revision) + '. Only you can approve it.',
        'export': 'Prepare the approved files for revision ' + str(revision) + '. This runs on this computer only.',
        'deliver': 'Nothing. Download, deliver or share the approved files when you are ready.',
    }[stage]
    if checks and not passed and stage in ('review', 'check') and any(c['status'] != 'passed' for c in checks):
        needs = 'Resolve the findings in Checks for this page, then review the page and run the checks again.'
    if approved_files:
        downloads = 'Approved files for revision ' + str(approved_files['revision']) + ': PNG, PDF, SVG and text.'
    elif preview is not None:
        downloads = 'Draft files for revision ' + str(preview['revision']) + ', marked as drafts.'
    else:
        downloads = 'Nothing yet for the current revision.'
    if earlier is not None and approved_files is None:
        downloads += ' Earlier approved files for revision ' + str(earlier['revision']) + ' stay in Saved files.'
    return {'stage': stage, 'position': position, 'steps': steps, 'revision': revision,
            'complete': ' '.join(complete) or 'Your brief and information are saved.', 'needs': needs,
            'downloads': downloads}


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
