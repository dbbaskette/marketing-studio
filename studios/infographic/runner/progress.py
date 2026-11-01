"""Where an infographic stands, in words, from its saved revision alone. Read-only."""
from __future__ import annotations


def _reviewed(project, review):
    """A passed review of exactly the current content, by the person or the assistant."""
    from .contracts import basis, digest
    return bool(review and review.get('status') == 'passed' and review.get('basis') == basis(project)
                and review.get('scene_digest') == digest(project['scene']))


def approved_words(approval, page=lambda revision: revision):
    """Who approved which page revision, and whether a rename carried that approval forward.
    `page` maps a saved revision to its page revision (history.Pages.of)."""
    moved = approval.get('carried') or {}
    if moved.get('reason') == 'rename':
        return ('You approved revision ' + str(page(moved['from_revision'])) + '. Renaming kept the '
                'approval for revision ' + str(page(approval['revision'])) + '.')
    return 'You approved revision ' + str(page(approval['revision'])) + '.'


# The toolbar's primary action for each stage; `needs` names it. Approve adds the revision.
ACTIONS = {'story': 'Find the story', 'choose': 'Choose a story', 'build': 'Build page',
           'preview': 'Update preview', 'review': 'Review page', 'check': 'Run checks',
           'approve': 'Approve revision', 'export': 'Prepare approved files',
           'deliver': 'Deliver approved page'}

STEPS = (('story', 'Story'), ('draft', 'Draft page'), ('review', 'Review and checks'),
         ('delivery', 'Approved delivery'))


def roadmap(project, deliveries, *, review=None, review_checked=False, page=lambda revision: revision):
    """The four-step route, the one next stage, and what is complete, needed and downloadable.

    `deliveries` is the desk's delivery listing (each with current/draft/approved_current).
    Every revision named is a page revision (`page`, history.Pages.of): checks, reviews and
    approvals save revisions of their own, but the person is told the page's one number.
    `action` is the toolbar's primary action for the stage, and `needs` always names it.
    Every statement comes from saved state; nothing here renders, checks or approves.
    """
    revision = page(project['revision'])
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
                        + str(page(preview['revision'])) + '.')
    if passed or project['approval'] is not None:
        complete.append('Review recorded and checks passed.')
    if project['approval'] is not None:
        complete.append(approved_words(project['approval'], page))
    action = 'Create preview' if stage == 'preview' and not deliveries else ACTIONS[stage]
    if stage == 'approve':
        action += ' ' + str(revision)
    needs = {
        'story': 'Find the story: your assistant proposes source-backed explanations.',
        'choose': 'Choose a story from the proposals on this page.',
        'build': 'Build page: compose the chosen story with your brand.',
        'preview': 'Update preview so it shows revision ' + str(revision) + '.' if deliveries else
                   'Create preview: render the page on this computer.',
        'review': 'Review page: look at the actual page and record what you checked. Checks then run on this computer.',
        'check': 'Run checks again for revision ' + str(revision) + '.' if checks else
                 'Run checks for revision ' + str(revision) + '.',
        'approve': action + '. Only you can approve it.',
        'export': 'Prepare approved files for revision ' + str(revision) + '. This runs on this computer only.',
        'deliver': 'Nothing required. Deliver approved page, or download or share its files, when you are ready.',
    }[stage]
    if checks and not passed and stage in ('review', 'check') and any(c['status'] != 'passed' for c in checks):
        needs = 'Resolve the findings in Checks for this page, then Review page again. Checks run straight after.'
        action = ACTIONS['review']
    withdrawn = (approved_files is None and earlier is not None and project['approval'] is None
                 and page(earlier['revision']) == revision)
    if approved_files:
        downloads = 'Approved files for revision ' + str(page(approved_files['revision'])) + ': PNG, PDF, SVG and text.'
    elif withdrawn:
        # A new review or new checks of the same page withdrew its approval; its files stand.
        downloads = ('The files approved earlier for revision ' + str(revision) + ' stay unchanged in Saved '
                     'files. A new review withdrew the approval until you approve again.')
    elif preview is not None:
        downloads = 'Draft files for revision ' + str(page(preview['revision'])) + ', marked as drafts.'
    else:
        downloads = 'Nothing yet for the current revision.'
    if earlier is not None and approved_files is None and not withdrawn:
        downloads += ' Earlier approved files for revision ' + str(page(earlier['revision'])) + ' stay in Saved files.'
    return {'stage': stage, 'position': position, 'steps': steps, 'revision': revision, 'action': action,
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
