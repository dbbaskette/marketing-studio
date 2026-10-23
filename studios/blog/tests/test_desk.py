"""The desk record: a draft as title, opening and sections, with versions."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import desk
import studio

DRAFT = """# A synthetic title

An opening paragraph.

## First part

First text.

## Second part

Second text.
"""


class SplitJoinTests(unittest.TestCase):
    def test_split_reads_title_opening_and_sections(self):
        found = desk.split(DRAFT)
        self.assertEqual(found['title'], 'A synthetic title')
        self.assertEqual(found['opening'], 'An opening paragraph.')
        self.assertEqual([s['heading'] for s in found['sections']], ['First part', 'Second part'])
        self.assertEqual(found['sections'][1]['text'], 'Second text.')
        self.assertTrue(all(len(s['id']) == 8 for s in found['sections']))
        self.assertEqual(len({s['id'] for s in found['sections']}), 2)

    def test_join_round_trips(self):
        self.assertEqual(desk.join(desk.split(DRAFT)), DRAFT)

    def test_no_headings_is_one_opening(self):
        found = desk.split('Just prose.\n')
        self.assertEqual(found['sections'], [])
        self.assertEqual(found['opening'], 'Just prose.')

    def test_title_may_be_given_when_the_text_has_none(self):
        found = desk.split('## Only\n\nText.\n', title='Given')
        self.assertEqual(found['title'], 'Given')
        self.assertEqual(found['opening'], '')

    def test_a_heading_inside_a_code_block_stays_in_its_section(self):
        text = '# T\n\n## Setup\n\n```sh\n## not a heading\necho hi\n```\n\n## Next\n\nMore.\n'
        found = desk.split(text)
        self.assertEqual([s['heading'] for s in found['sections']], ['Setup', 'Next'])
        self.assertIn('## not a heading', found['sections'][0]['text'])
        self.assertEqual(desk.join(found), text)

    def test_deeper_headings_stay_in_their_section(self):
        found = desk.split('# T\n\n## Part\n\n### Detail\n\nText.\n')
        self.assertEqual(len(found['sections']), 1)
        self.assertEqual(found['sections'][0]['text'], '### Detail\n\nText.')

    def test_windows_line_endings_are_read(self):
        found = desk.split('# T\r\n\r\n## Part\r\n\r\nText.\r\n')
        self.assertEqual(found['sections'][0]['text'], 'Text.')


class DeskCase(unittest.TestCase):
    """A disposable workspace and shared settings; nothing on this computer is read."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        environment = patch.dict(
            os.environ,
            {
                'BLOG_STUDIO_DATA': str(self.base / 'data'),
                'STUDIOS_CONFIG': str(self.base / 'studios-config.json'),
                'BRAND_SKILL_RUNTIME': str(self.base / 'no-brand'),
                'HARNESS_RESEARCH_RUNTIME': str(self.base / 'no-research'),
            },
        )
        environment.start()
        self.addCleanup(environment.stop)
        self.root = self.base / 'workspace'
        studio.initialize(self.root)
        # These tests call the desk directly, as management's lock holder would.
        held = studio._HELD.set(True)
        self.addCleanup(studio._HELD.reset, held)

    def make(self, **extra):
        return desk.create(
            self.root, {'title': 'Synthetic', 'manuscript': DRAFT, 'tone': 'Plain', **extra}
        )

    def folder(self, ident):
        return studio.inside(self.root, 'articles', ident)

    def source(self, text='Synthetic reference text.', *purposes):
        path = self.base / 'source.md'
        path.write_text(text)
        args = studio.parser().parse_args(
            [
                '--root',
                str(self.root),
                'source',
                'add',
                '--name',
                'Synthetic source',
                '--file',
                str(path),
                *[
                    word
                    for purpose in purposes or ('reference',)
                    for word in ('--purpose', purpose)
                ],
            ]
        )
        return studio.source_command(self.root, args)['id']


class DeskRecordTests(DeskCase):
    def test_create_writes_the_record_the_draft_and_DRAFT_md(self):
        made = self.make()
        directory = self.folder(made['id'])
        self.assertEqual((directory / 'DRAFT.md').read_text(), DRAFT)
        self.assertEqual((directory / 'ORIGINAL.md').read_text(), DRAFT)
        record = studio.read_json(directory / 'session.json')
        self.assertEqual(record['flow'], 'desk')
        self.assertEqual(record['voice'], {'mode': 'tone', 'tone': 'Plain'})
        self.assertEqual(record['title'], 'A synthetic title')
        self.assertEqual(record['artifact_hashes']['draft'], studio.digest(DRAFT.encode()))
        saved = desk.read(self.root, made['id'])
        self.assertEqual(saved['revision'], 1)
        self.assertEqual(saved['id'], made['id'])
        self.assertEqual(saved['tone'], 'Plain')

    def test_a_default_voice_never_reaches_a_desk_blog(self):
        with patch('writing_defaults.for_create', return_value={'profile_id': 'x', 'revision': 1}):
            made = self.make()
        record = studio.read_json(self.folder(made['id']) / 'session.json')
        self.assertEqual(record['voice'], {'mode': 'tone', 'tone': 'Plain'})

    def test_a_draft_without_a_title_needs_one(self):
        with self.assertRaisesRegex(ValueError, 'Give the blog a title'):
            desk.create(self.root, {'manuscript': 'Just prose.'})
        made = desk.create(self.root, {'title': 'Named', 'manuscript': 'Just prose.'})
        self.assertEqual(desk.read(self.root, made['id'])['title'], 'Named')

    def test_an_empty_draft_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'Paste or upload a draft'):
            desk.create(self.root, {'title': 'T', 'manuscript': '  '})

    def test_a_kind_of_post_is_pinned_and_unknown_fields_are_refused(self):
        made = self.make(style='how-to')
        self.assertEqual(desk.read(self.root, made['id'])['style']['style_id'], 'how-to')
        with self.assertRaisesRegex(ValueError, 'does not take'):
            desk.create(self.root, {'title': 'T', 'manuscript': DRAFT, 'profile': 'x'})
        with self.assertRaisesRegex(ValueError, 'length'):
            self.make(length='enormous')

    def test_sources_are_attached_with_their_purposes(self):
        source = self.source()
        made = self.make(sources=[source])
        record = studio.read_json(self.folder(made['id']) / 'session.json')
        self.assertEqual(record['sources'][0]['source_id'], source)
        self.assertEqual(record['sources'][0]['purposes'], ['reference'])
        self.assertEqual(desk.read(self.root, made['id'])['sources'], record['sources'])

    def test_an_uploaded_draft_source_starts_the_desk(self):
        source = self.source(DRAFT, 'manuscript')
        made = desk.create(self.root, {'source': source})
        self.assertEqual(desk.read(self.root, made['id'])['sections'][0]['text'], 'First text.')

    def test_a_blog_started_from_a_google_doc_moves_onto_the_desk(self):
        args = studio.parser().parse_args(
            [
                '--root',
                str(self.root),
                'article',
                'create',
                '--title',
                'From a Doc',
                '--mode',
                'existing',
            ]
        )
        ident = studio.article_command(self.root, args)['id']
        directory, record = studio.item(self.root, 'articles', ident)
        studio.save_artifact(directory, 'draft', DRAFT, record, 'starting manuscript')
        studio.persist(directory, 'articles', record)
        made = desk.create(self.root, {'article': ident, 'tone': 'Warm'})
        self.assertEqual(made['id'], ident)
        record = studio.read_json(directory / 'session.json')
        self.assertEqual((record['flow'], record['voice']['mode']), ('desk', 'tone'))
        with self.assertRaisesRegex(ValueError, 'already on the desk'):
            desk.create(self.root, {'article': ident})

    def test_save_a_section_bumps_the_revision_and_DRAFT_md(self):
        made = self.make()
        part = made['sections'][0]['id']
        saved = desk.save(self.root, made['id'], 1, part, 'New first text.')
        self.assertEqual(saved['revision'], 2)
        directory = self.folder(made['id'])
        body = (directory / 'DRAFT.md').read_text()
        self.assertIn('New first text.', body)
        record = studio.read_json(directory / 'session.json')
        self.assertEqual(record['artifact_hashes']['draft'], studio.digest(body.encode()))

    def test_an_unchanged_save_writes_nothing(self):
        made = self.make()
        part = made['sections'][0]['id']
        self.assertEqual(desk.save(self.root, made['id'], 1, part, 'First text.')['revision'], 1)

    def test_an_outdated_form_is_refused_and_nothing_changes(self):
        made = self.make()
        part = made['sections'][0]['id']
        desk.save(self.root, made['id'], 1, part, 'Second.')
        with self.assertRaisesRegex(ValueError, 'changed since'):
            desk.save(self.root, made['id'], 1, part, 'Stale.')
        self.assertEqual(desk.read(self.root, made['id'])['sections'][0]['text'], 'Second.')

    def test_title_and_opening_are_parts_too(self):
        made = self.make()
        desk.save(self.root, made['id'], 1, 'title', 'Better title')
        self.assertEqual(desk.read(self.root, made['id'])['title'], 'Better title')
        record = studio.read_json(self.folder(made['id']) / 'session.json')
        self.assertEqual(record['title'], 'Better title')
        with self.assertRaisesRegex(ValueError, 'Choose a part'):
            desk.save(self.root, made['id'], 2, 'nope', 'x')
        with self.assertRaisesRegex(ValueError, 'one line'):
            desk.save(self.root, made['id'], 2, 'title', 'Two\nlines')

    def test_a_blog_not_on_the_desk_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'Unknown articles'):
            desk.read(self.root, 'no-such-blog')


class LockTests(DeskCase):
    def test_desk_writes_need_the_studio_lock(self):
        import contextvars

        made = self.make()
        part = made['sections'][0]['id']

        def unlocked(call):
            studio._HELD.set(False)
            return call()

        for call in (
            lambda: desk.save(self.root, made['id'], 1, part, 'Changed.'),
            lambda: desk.keep(self.root, made['id'], part, 'x', 'save'),
            lambda: desk.create(self.root, {'title': 'T', 'manuscript': DRAFT}),
        ):
            with self.assertRaisesRegex(RuntimeError, 'studio lock'):
                contextvars.copy_context().run(unlocked, call)
        self.assertEqual(desk.read(self.root, made['id'])['sections'][0]['text'], 'First text.')
        with studio.locked(self.root):
            self.assertTrue(studio.lock_held())


class VersionTests(DeskCase):
    def test_each_save_keeps_the_text_before_it(self):
        made = self.make()
        part = made['sections'][0]['id']
        desk.save(self.root, made['id'], 1, part, 'Two.')
        desk.save(self.root, made['id'], 2, part, 'Three.')
        found = desk.versions(self.root, made['id'], part)
        self.assertEqual([v['text'] for v in found], ['Two.', 'First text.'])  # newest first
        self.assertEqual(found[0]['source'], 'save')
        self.assertEqual(found[1]['words'], 2)

    def test_one_editing_session_keeps_one_version(self):
        made = self.make()
        part = made['sections'][0]['id']
        desk.save(self.root, made['id'], 1, part, 'Two.', session='a' * 16)
        desk.save(self.root, made['id'], 2, part, 'Three.', session='a' * 16)
        self.assertEqual(
            [v['text'] for v in desk.versions(self.root, made['id'], part)], ['First text.']
        )
        desk.save(self.root, made['id'], 3, part, 'Four.', session='b' * 16)
        self.assertEqual(
            [v['text'] for v in desk.versions(self.root, made['id'], part)],
            ['Three.', 'First text.'],
        )

    def test_only_twenty_are_kept(self):
        made = self.make()
        part = made['sections'][0]['id']
        for n in range(25):
            desk.save(self.root, made['id'], n + 1, part, 'Text %d.' % n)
        self.assertEqual(len(desk.versions(self.root, made['id'], part)), 20)

    def test_restore_is_itself_a_version(self):
        made = self.make()
        part = made['sections'][0]['id']
        desk.save(self.root, made['id'], 1, part, 'Two.')
        desk.restore(self.root, made['id'], 2, part, 0)  # index 0 = newest kept = 'First text.'
        draft = desk.read(self.root, made['id'])
        self.assertEqual(draft['sections'][0]['text'], 'First text.')
        self.assertEqual(desk.versions(self.root, made['id'], part)[0]['text'], 'Two.')
        self.assertEqual(desk.versions(self.root, made['id'], part)[0]['source'], 'restore')
        with self.assertRaisesRegex(ValueError, 'saved version'):
            desk.restore(self.root, made['id'], 3, part, 9)

    def test_counts_per_part(self):
        made = self.make()
        desk.save(self.root, made['id'], 1, 'title', 'Better')
        self.assertEqual(desk.counts(self.root, made['id']), {'title': 1})

    def test_a_part_name_never_leaves_the_versions_folder(self):
        made = self.make()
        for part in ('../draft', 'TITLE', 'a' * 9, '', None, '0123456g'):
            with self.assertRaisesRegex(ValueError, 'Choose a part'):
                desk.versions(self.root, made['id'], part)

    def test_a_linked_versions_file_is_refused(self):
        made = self.make()
        folder = self.folder(made['id']) / 'desk' / 'versions'
        folder.mkdir(parents=True)
        outside = self.base / 'outside.jsonl'
        outside.write_text('')
        (folder / 'title.jsonl').symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'escapes'):
            desk.save(self.root, made['id'], 1, 'title', 'Better')
        self.assertEqual(outside.read_text(), '')
        within = self.folder(made['id']) / 'within.jsonl'
        within.write_text('')
        (folder / 'opening.jsonl').symlink_to(within)
        with self.assertRaisesRegex(ValueError, 'not a plain file'):
            desk.save(self.root, made['id'], 1, 'opening', 'Changed')
        self.assertEqual(within.read_text(), '')
        self.assertEqual(desk.read(self.root, made['id'])['title'], 'A synthetic title')


class RouteCase(DeskCase):
    def setUp(self):
        super().setUp()
        import blog_runner

        self.addCleanup(lambda: blog_runner.ENGINES.pop(str(self.root), None))

    def post(self, route, data):
        import management

        return management.dispatch(self.root, route, data)

    def get(self, name, **query):
        import management

        return management.view(self.root, name, {key: [value] for key, value in query.items()})

    def start(self, **extra):
        return self.post(
            'desk-create',
            {'operation': 'a' * 32, 'title': 'Synthetic', 'manuscript': DRAFT, **extra},
        )


class RouteTests(RouteCase):
    def test_create_then_save_through_the_page_routes(self):
        made = self.start()
        self.assertEqual(made['revision'], 1)
        self.assertEqual(made['markdown'], DRAFT)
        self.assertIsNone(made['first_pass_problem'])
        part = made['sections'][0]['id']
        saved = self.post(
            'desk-save',
            {'id': made['id'], 'seen': 1, 'part': part, 'text': 'Typed.', 'session': 'b' * 16},
        )
        self.assertEqual(saved['revision'], 2)
        self.assertEqual(saved['versions'], {part: 1})
        shown = self.get('desk-versions', id=made['id'], part=part)
        self.assertEqual(shown['versions'][0]['text'], 'First text.')
        restored = self.post(
            'desk-restore', {'id': made['id'], 'seen': 2, 'part': part, 'index': 0}
        )
        self.assertEqual(restored['sections'][0]['text'], 'First text.')

    def test_the_same_create_returns_the_same_blog(self):
        first, again = self.start(), self.start()
        self.assertEqual(first['id'], again['id'])
        with self.assertRaisesRegex(ValueError, 'request changed'):
            self.start(tone='Other')

    def test_unknown_fields_are_refused(self):
        made = self.start()
        with self.assertRaisesRegex(ValueError, 'does not take'):
            self.post(
                'desk-save', {'id': made['id'], 'seen': 1, 'part': 'title', 'text': 'x', 'voice': 1}
            )
        with self.assertRaisesRegex(ValueError, 'does not take'):
            self.start(profile='someone')
        with self.assertRaisesRegex(ValueError, 'Unknown desk action'):
            self.post('desk-publish', {'id': made['id']})

    def test_a_first_pass_is_queued_on_create(self):
        made = self.start(first_pass='tighten')
        self.assertEqual(made['working']['kind'], 'desk-first-pass')
        with self.assertRaisesRegex(ValueError, 'already working'):
            self.post(
                'desk-note',
                {'id': made['id'], 'seen': 1, 'part': made['sections'][0]['id'], 'note': 'x'},
            )
        stopped = self.post('desk-stop', {'id': made['id'], 'job': made['working']['id']})
        self.assertIsNone(stopped['working'])
        self.assertEqual(stopped['jobs'][0]['status'], 'cancelled')

    def test_a_first_pass_that_cannot_run_still_opens_the_desk(self):
        made = self.post(
            'desk-create',
            {
                'operation': 'c' * 32,
                'title': 'Flat',
                'manuscript': 'Just prose.',
                'first_pass': 'tighten',
            },
        )
        self.assertRegex(made['first_pass_problem'], 'section by section')
        self.assertEqual(made['opening'], 'Just prose.')

    def finish(self, job_id, content):
        import tool_jobs

        job = tool_jobs.read(self.root, job_id)
        job.update(status='ready', result={'content': content, 'notes': '', 'gaps': []})
        tool_jobs.write(self.root, job)

    def test_reading_the_desk_never_writes_and_a_ready_result_reads_as_working(self):
        made = self.start()
        part = made['sections'][0]['id']
        queued = self.post(
            'desk-note', {'id': made['id'], 'seen': 1, 'part': part, 'note': 'More.'}
        )
        self.finish(queued['working']['id'], 'First text, more.')
        directory = self.folder(made['id'])
        before = (directory / 'desk' / 'draft.json').read_bytes()
        shown = self.get('desk', id=made['id'])
        self.assertEqual((directory / 'desk' / 'draft.json').read_bytes(), before)
        self.assertEqual(shown['working']['id'], queued['working']['id'])
        self.assertEqual(shown['sections'][0]['text'], 'First text.')

    def test_the_next_desk_request_settles_a_result_an_older_process_left(self):
        made = self.start()
        part = made['sections'][0]['id']
        queued = self.post(
            'desk-note', {'id': made['id'], 'seen': 1, 'part': part, 'note': 'More.'}
        )
        self.finish(queued['working']['id'], 'First text, more.')
        # The page still shows the job working, so typing goes to another part.
        saved = self.post(
            'desk-save',
            {'id': made['id'], 'seen': 1, 'part': 'title', 'text': 'Typed', 'session': 'a' * 16},
        )
        self.assertEqual(saved['sections'][0]['text'], 'First text, more.')
        self.assertIsNone(saved['working'])
        self.assertIs(saved['jobs'][-1]['applied'], True)
        self.assertEqual(saved['title'], 'Typed')

    def test_a_save_while_a_result_waits_does_not_lose_the_rewrite(self):
        made = self.start()
        part = made['sections'][0]['id']
        queued = self.post(
            'desk-note', {'id': made['id'], 'seen': 1, 'part': part, 'note': 'More.'}
        )
        self.finish(queued['working']['id'], 'First text, more.')
        # A form that saw the section before the rewrite cannot overwrite it.
        with self.assertRaisesRegex(ValueError, 'changed since'):
            self.post(
                'desk-save',
                {
                    'id': made['id'],
                    'seen': 1,
                    'part': part,
                    'text': 'Typed over.',
                    'session': 'a' * 16,
                },
            )
        self.assertEqual(
            self.get('desk', id=made['id'])['sections'][0]['text'], 'First text, more.'
        )

    def test_stop_sets_a_ready_result_aside(self):
        made = self.start()
        part = made['sections'][0]['id']
        queued = self.post(
            'desk-note', {'id': made['id'], 'seen': 1, 'part': part, 'note': 'More.'}
        )
        self.finish(queued['working']['id'], 'Landed anyway.')
        stopped = self.post('desk-stop', {'id': made['id'], 'job': queued['working']['id']})
        self.assertIsNone(stopped['working'])
        self.assertEqual(stopped['sections'][0]['text'], 'First text.')
        self.assertRegex(stopped['jobs'][-1]['error'], 'set aside')
        saved = self.post(
            'desk-save',
            {'id': made['id'], 'seen': 1, 'part': 'title', 'text': 'T2', 'session': 'a' * 16},
        )
        self.assertEqual(saved['sections'][0]['text'], 'First text.')

    def test_a_desk_job_is_not_retried_outside_the_desk(self):
        made = self.start()
        part = made['sections'][0]['id']
        one = self.post('desk-note', {'id': made['id'], 'seen': 1, 'part': part, 'note': 'One.'})
        self.post('desk-stop', {'id': made['id'], 'job': one['working']['id']})
        self.post('desk-note', {'id': made['id'], 'seen': 1, 'part': part, 'note': 'Two.'})
        with self.assertRaisesRegex(ValueError, 'from the desk'):
            self.post(
                'tool-action',
                {
                    'action': 'job-control',
                    'job': one['working']['id'],
                    'control': 'retry',
                    'id': made['id'],
                },
            )

    def test_a_selection_and_a_whole_draft_note_go_through_the_routes(self):
        made = self.start()
        part = made['sections'][0]['id']
        shown = self.post(
            'desk-selection',
            {'id': made['id'], 'seen': 1, 'part': part, 'text': 'First', 'action': 'shorten'},
        )
        self.assertEqual(shown['working']['kind'], 'desk-selection')
        self.post('desk-stop', {'id': made['id'], 'job': shown['working']['id']})
        shown = self.post('desk-revise', {'id': made['id'], 'seen': 1, 'note': 'Warmer.'})
        self.assertEqual(shown['working']['kind'], 'desk-revise-all')

    def test_a_job_on_another_blog_cannot_be_stopped_here(self):
        made, other = (
            self.start(),
            self.post(
                'desk-create',
                {
                    'operation': 'd' * 32,
                    'title': 'Other',
                    'manuscript': DRAFT,
                    'first_pass': 'tighten',
                },
            ),
        )
        with self.assertRaisesRegex(ValueError, 'Choose a job on this blog'):
            self.post('desk-stop', {'id': made['id'], 'job': other['working']['id']})

    def test_a_blog_not_on_the_desk_has_no_desk_view(self):
        with self.assertRaisesRegex(ValueError, 'Choose a blog'):
            self.get('desk')


class ListingTests(RouteCase):
    def test_a_desk_blog_is_listed_with_the_others(self):
        import blog_runner

        made = self.start(first_pass='tighten')
        rows = blog_runner.catalog(self.root)['items']
        row = next(row for row in rows if row['id'] == made['id'])
        self.assertEqual(
            (row['flow'], row['status'], row['jobs'], row['title']),
            ('desk', 'working', 1, 'A synthetic title'),
        )
        self.post('desk-stop', {'id': made['id'], 'job': made['working']['id']})
        row = blog_runner.catalog(self.root)['items'][0]
        self.assertEqual((row['status'], row['jobs']), ('desk', 0))

    def test_a_deleted_desk_blog_is_not_listed(self):
        import blog_runner

        made = self.start()
        self.post(
            'blog-delete', {'id': made['id'], 'expected': made['expected'], 'title': made['title']}
        )
        self.assertEqual(blog_runner.catalog(self.root)['items'], [])
        self.assertEqual(blog_runner.catalog(self.root)['deleted'][0]['id'], made['id'])


if __name__ == '__main__':
    unittest.main()
