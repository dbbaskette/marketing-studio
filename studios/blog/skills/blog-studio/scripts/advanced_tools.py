"""Contextual tasks over existing article operations; no parallel storage engine."""

from types import SimpleNamespace

import author_workflow
import manuscript_editor
import studio


def overview(root, ident=None, offset=0):
    if type(offset) is not int or offset < 0:
        raise ValueError('Choose a valid history page.')
    import tool_jobs

    jobs = tool_jobs.listing(root, ident)
    if not ident:
        return {'id': None, 'history': [], 'history_total': 0, 'jobs': jobs}
    directory, record = studio.item(root, 'articles', ident)
    current = manuscript_editor.read(root, ident)
    history = list(reversed(author_workflow.histories(directory, 'draft')))
    events = {
        event.get('before'): event
        for event in record.get('artifact_events', [])
        if event.get('kind') == 'draft'
    }
    return {
        'id': ident,
        'title': record['title'],
        'expected': current['expected'],
        'has_manuscript': bool(current['content']),
        'jobs': jobs,
        'google': current['google'],
        'working': current['working'],
        'offset': offset,
        'history_total': len(history),
        'history': [
            {
                'revision': path.name,
                'at': events.get(path.name, {}).get('at'),
                'action': events.get(path.name, {}).get('label', 'Earlier saved manuscript'),
                'scope': 'local checkpoint; shared delivery not established',
            }
            for path in history[offset : offset + 20]
        ],
        'next_offset': offset + 20 if offset + 20 < len(history) else None,
    }


def history_preview(root, ident, revision):
    return author_workflow.restore(
        root, SimpleNamespace(id=ident, kind='draft', revision=revision, apply=False, expected=None)
    )


def dispatch(root, data):
    action = data.get('action')
    if action in (
        'job-create',
        'job-apply',
        'profile-save',
        'profile-retire',
        'interview-answer',
        'interview-start',
        'voice-apply',
        'job-control',
    ):
        import article_tools
        import blog_runner
        import tool_jobs
        from team_workspace import guard as team_guard

        if data.get('id'):
            team_guard(root, data['id'])
        if action == 'job-create':
            return article_tools.request(root, data)
        if action == 'job-apply':
            return article_tools.apply(root, data)
        if action == 'job-control':
            return tool_jobs.control(
                root, data.get('job'), data.get('control'), blog_runner.engine(root)
            )
        if action == 'profile-save':
            return article_tools.save_profile(root, data)
        if action == 'profile-retire':
            return article_tools.retire_profile(root, data)
        if action == 'interview-start':
            return article_tools.start_interview(root, data)
        if action == 'interview-answer':
            return article_tools.answer(root, data)
        if action == 'voice-apply':
            current = manuscript_editor.guard(
                root, {'id': data.get('id'), 'expected': data.get('expected')}
            )
            selected = article_tools.profile(root, data.get('profile'))
            if selected['status'] == 'retired':
                raise ValueError(
                    'Choose an active profile; existing pinned work remains unchanged.'
                )
            folder, record = studio.item(root, 'articles', current['id'])
            record['voice'] = {
                'mode': 'profile',
                **studio.voice_pin(root, selected['id'], selected['revision']),
            }
            studio.persist(folder, 'articles', record)
            return {'id': current['id'], 'voice': record['voice'], 'status': 'voice-selected'}
    if action == 'variant-save':
        import article_tools

        return article_tools.save_variant(root, data)
    if action in ('google-compare', 'google-accept'):
        import google_reconcile

        return (
            google_reconcile.preview if action == 'google-compare' else google_reconcile.accept
        )(root, data)
    if action == 'restore':
        current = manuscript_editor.guard(
            root, {'id': data.get('id'), 'expected': data.get('expected')}
        )
        if current['working']:
            raise ValueError('Pause the current writing job before restoring a revision.')
        if data.get('confirmed') is not True:
            raise ValueError('Preview and confirm the revision before restoring it.')
        result = author_workflow.restore(
            root,
            SimpleNamespace(
                id=current['id'],
                kind='draft',
                revision=data.get('revision'),
                apply=True,
                expected=data.get('restore_expected'),
            ),
        )
        return {
            'id': result['id'],
            'status': 'restored',
            'saved': True,
            'google_written': False,
            'next_step': 'Read the restored manuscript. Existing sources, voice and Google Doc remain unchanged.',
        }
    raise ValueError('Choose a supported contextual tool.')
