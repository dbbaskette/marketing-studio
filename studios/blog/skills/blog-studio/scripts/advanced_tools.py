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


def apply_voice(root, ident, selected, confirmed):
    """Switch a blog's voice as the chat `article voice` command does, so its reviews go
    stale. Once an outline or draft exists the person confirms it, and a guided run
    records it as a decision. The pinned style and any tone nudge stay as they are."""
    import blog_runner

    folder, record = studio.item(root, 'articles', ident)
    before = record.get('voice') or {}
    same = before.get('mode') == 'profile' and (before['profile_id'], before['revision']) == (
        selected['id'],
        selected['revision'],
    )
    written = any((folder / name).is_file() for name in ('OUTLINE.md', 'DRAFT.md', 'ORIGINAL.md'))
    if written and not confirmed and not same:
        raise ValueError(
            'This blog has a saved outline or draft. Confirm the change of voice: its reviews '
            'will need a new look; nothing is rewritten.'
        )
    if not same:
        studio.article_command(
            root,
            SimpleNamespace(
                action='voice',
                id=ident,
                profile=selected['id'],
                revision=selected['revision'],
                voice='preserve',
                tone=before.get('tone') or None,
            ),
        )
        if (folder / blog_runner.STATE).is_file():
            directory, _, run = blog_runner.load(root, ident)
            blog_runner.note_decision(
                directory,
                run,
                'Voice changed to '
                + selected['name']
                + ' (revision '
                + str(selected['revision'])
                + ')',
            )
    _, record = studio.item(root, 'articles', ident)
    result = {'id': ident, 'voice': record['voice'], 'status': 'voice-selected'}
    if (folder / blog_runner.STATE).is_file():
        result['run'] = blog_runner.engine(root).describe(ident)
    return result


SAMPLE_PURPOSES = ('voice-sample', 'style-sample')


def source_purpose(root, data):
    """Mark a ready reference as a voice or style sample, in a new source revision.

    A voice sample is a person's writing, so it needs whose it is: the author given here
    when the source names none. A style sample keeps whatever author the source has."""
    import blog_library
    import voice_links

    if set(data) - {'action', 'source', 'purpose', 'author'}:
        raise ValueError('Unknown sample field.')
    purpose = data.get('purpose')
    if purpose not in SAMPLE_PURPOSES:
        raise ValueError('Choose a voice sample or a style sample.')
    directory, record = studio.item(root, 'sources', data.get('source'))
    if studio.is_material(root, directory, record):
        raise ValueError(
            'This file was uploaded for one blog and stays with it. Upload it again as a '
            'sample to use it for a voice or a style.'
        )
    content = directory / 'content.md'
    if (
        record.get('status') != 'ready'
        or not content.is_file()
        or not studio.read_text(content).strip()
    ):
        raise ValueError(
            'This source has no readable text yet. Add its text before using it as a sample.'
        )
    given = data.get('author')
    author = studio.checked_author(given) if given not in (None, '') else None
    saved = (record.get('author') or '').strip()
    if purpose == 'voice-sample':
        if not saved and not author:
            raise ValueError('Say whose writing this is before using it as a voice sample.')
        if saved and author and not voice_links.same_author(saved, author):
            raise ValueError(
                'This source is by ' + saved + '. Use it as a sample of ' + saved + '’s voice.'
            )
    purposes = list(record.get('purposes') or [])
    changed = purpose not in purposes or bool(author and not saved)
    if changed:
        blog_library.save_revision(directory, record)
        if purpose not in purposes:
            purposes.append(purpose)
        record['purposes'] = purposes
        if author and not saved:
            record['author'] = author
        record['revision'] += 1
        studio.persist(directory, 'sources', record)
    return {
        'source': record['id'],
        'revision': record['revision'],
        'purposes': record['purposes'],
        'author': record.get('author') or '',
        'changed': changed,
    }


def dispatch(root, data):
    action = data.get('action')
    if action == 'source-purpose':
        return source_purpose(root, data)
    if action in (
        'job-create',
        'job-apply',
        'profile-save',
        'profile-retire',
        'style-save',
        'style-retire',
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
        if action == 'style-save':
            import styles

            return styles.save(root, data)
        if action == 'style-retire':
            import styles

            return styles.retire(root, data)
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
            return apply_voice(root, current['id'], selected, data.get('confirmed') is True)
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
