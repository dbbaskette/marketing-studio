"""Styles: starter copies, revisions, pins and the style-sample purpose."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from test_editorial_tools import Fixture
import studio
import styles
import team_workspace as teams
from studio_sync import gitstate, support


class StyleTests(Fixture):
    def guide(self, text):
        path = self.base / 'guide.md'
        path.write_text(text)
        return str(path)

    def starter_folders(self):
        folder = self.root / 'styles'
        return sorted(path.name for path in folder.iterdir()) if folder.exists() else []

    def test_starters_appear_without_being_written_and_stay_once_changed(self):
        found = styles.catalog(self.root)
        ids = [row['id'] for row in found['styles']]
        self.assertIn('product-announcement', ids)
        self.assertEqual(len(ids), len(list(styles.SEEDS.glob('*.md'))))
        self.assertTrue(
            all(row['kind'] == 'seed' and row['status'] == 'confirmed' for row in found['styles'])
        )
        self.assertTrue(all(row['summary'] for row in found['styles']))
        shown = self.command('style', 'show', '--id', 'how-to')
        self.assertEqual((shown['revision'], shown['guide']), (1, None))
        self.assertTrue(shown['guide_text'].startswith('# How-to and tutorial'))
        styles.detail(self.root, 'how-to')
        self.assertEqual(self.starter_folders(), [], 'reading writes nothing')
        self.command(
            'style', 'save', '--id', 'product-announcement', '--guide-file', self.guide('Edited.')
        )
        self.command('style', 'retire', '--id', 'how-to', '--expected-revision', '1', '--confirmed')
        self.assertEqual(self.starter_folders(), ['how-to', 'product-announcement'])
        self.assertFalse(styles.materialize(self.root, 'how-to'), 'nothing is copied back')
        edited = self.command('style', 'show', '--id', 'product-announcement')
        self.assertEqual((edited['revision'], Path(edited['guide']).read_text()), (2, 'Edited.'))
        self.assertEqual(self.command('style', 'show', '--id', 'how-to')['status'], 'retired')
        starter = Path(styles.SEEDS / 'product-announcement.md').read_text()
        self.assertTrue(starter.startswith('---\nname: Product announcement\nsummary: '))

    def test_a_starter_keeps_its_token_once_copied_and_the_page_can_save_with_it(self):
        before = styles.detail(self.root, 'comparison')
        self.assertTrue(styles.materialize(self.root, 'comparison'))
        self.assertEqual(styles.detail(self.root, 'comparison'), before)
        written = (self.root / 'styles' / 'comparison' / 'record.json').read_text()
        self.assertNotIn('updated_at', written)
        shown = styles.detail(self.root, 'release-notes')
        saved = styles.save(
            self.root,
            {'style': 'release-notes', 'expected': shown['expected'], 'guide': 'Mine.'},
        )
        self.assertEqual((saved['revision'], saved['status']), (2, 'provisional'))
        shown = styles.detail(self.root, 'release-notes')
        self.command(
            'style', 'retire', '--id', 'release-notes', '--expected-revision', '2', '--confirmed'
        )
        with self.assertRaisesRegex(ValueError, 'retired'):
            styles.save(
                self.root, {'style': 'release-notes', 'expected': shown['expected'], 'guide': 'x'}
            )

    def test_a_half_copied_starter_is_replaced_and_pinning_copies_it(self):
        stale = self.root / 'styles' / 'how-to'
        (stale / 'revisions').mkdir(parents=True)
        (stale / 'STYLE.md').write_text('half')
        self.assertEqual(styles.detail(self.root, 'how-to')['revision'], 1)
        self.assertEqual(self.command('style', 'show', '--id', 'how-to')['guide'], None)
        pin = studio.style_pin(self.root, 'how-to')
        self.assertEqual(pin, {'style_id': 'how-to', 'revision': 1})
        self.assertTrue((stale / 'record.json').is_file())
        self.assertNotEqual((stale / 'STYLE.md').read_text(), 'half')
        self.assertEqual(
            [path.name for path in (self.root / 'styles').iterdir()], ['how-to'], 'no leftovers'
        )

    def test_a_workspace_without_a_styles_folder_lists_the_starters(self):
        shutil.rmtree(self.root / 'styles')
        self.assertEqual(len(styles.catalog(self.root)['styles']), 8)
        with patch.object(sys, 'argv', ['studio.py', '--root', str(self.root), 'list', 'styles']):
            out = io.StringIO()
            with redirect_stdout(out):
                self.assertEqual(studio.main(), 0)
        self.assertEqual(
            [row['id'] for row in json.loads(out.getvalue())],
            [row['id'] for row in styles.catalog(self.root)['styles']],
        )
        self.assertFalse((self.root / 'styles').exists())

    def test_starter_files_read_with_a_byte_order_mark_crlf_and_no_trailing_text(self):
        self.assertEqual(
            styles.parse_seed('\ufeff---\r\nname: A\r\nsummary: B\r\n---\r\nBody\r\n'),
            ('A', 'B', 'Body\n'),
        )
        self.assertEqual(styles.parse_seed('---\nname: A\nsummary: B\n---')[2], '\n')

    def test_a_style_pins_a_revision_and_a_retired_style_is_refused_for_new_work(self):
        created = self.command(
            'style',
            'create',
            '--name',
            'Field notes',
            '--guide-file',
            self.guide('Short sections, one observation each.'),
        )
        self.assertEqual(
            (created['revision'], created['status'], created['kind']), (1, 'provisional', 'learned')
        )
        pin = studio.style_pin(self.root, created['id'])
        self.assertEqual(pin, {'style_id': created['id'], 'revision': 1})
        self.command(
            'style',
            'save',
            '--id',
            created['id'],
            '--guide-file',
            self.guide('Revised.'),
            '--status',
            'confirmed',
        )
        self.assertEqual(
            styles.pinned(self.root, pin),
            {'name': 'Field notes', 'guide': 'Short sections, one observation each.'},
        )
        detail = styles.detail(self.root, created['id'])
        self.assertEqual((detail['revision'], detail['guide']), (2, 'Revised.'))
        self.command(
            'style', 'retire', '--id', created['id'], '--expected-revision', '2', '--confirmed'
        )
        with self.assertRaisesRegex(ValueError, 'retired'):
            studio.style_pin(self.root, created['id'])
        self.assertEqual(studio.style_pin(self.root, created['id'], 1), pin)
        with self.assertRaisesRegex(ValueError, 'Unknown style revision'):
            studio.style_pin(self.root, created['id'], 9)

    def test_checking_a_style_validates_like_a_pin_and_writes_nothing(self):
        self.assertEqual(
            studio.style_check(self.root, 'how-to'), {'style_id': 'how-to', 'revision': 1}
        )
        self.assertEqual(
            styles.pinned(self.root, {'style_id': 'how-to', 'revision': 1}),
            {'name': 'How-to and tutorial', 'guide': styles.starters()['how-to'][1]},
        )
        with self.assertRaisesRegex(ValueError, 'Unknown style revision'):
            studio.style_check(self.root, 'how-to', 2)
        with self.assertRaisesRegex(ValueError, 'Unknown styles'):
            studio.style_check(self.root, 'no-such-style')
        self.assertEqual(self.starter_folders(), [], 'checking copies no starter')
        self.command('style', 'retire', '--id', 'how-to', '--expected-revision', '1', '--confirmed')
        with self.assertRaisesRegex(ValueError, 'retired'):
            studio.style_check(self.root, 'how-to')
        self.assertEqual(
            studio.style_check(self.root, 'how-to', 1), studio.style_pin(self.root, 'how-to', 1)
        )

    def test_style_samples_need_the_style_sample_purpose(self):
        reference = self.source()
        with self.assertRaisesRegex(ValueError, 'style-sample'):
            self.command(
                'style',
                'create',
                '--name',
                'Wrong',
                '--guide-file',
                self.guide('x'),
                '--sample',
                reference['id'],
            )
        self.file.write_text('An example announcement.')
        sample = self.command(
            'source',
            'add',
            '--name',
            'Example',
            '--file',
            str(self.file),
            '--purpose',
            'style-sample',
        )
        created = self.command(
            'style',
            'create',
            '--name',
            'Right',
            '--guide-file',
            self.guide('x'),
            '--sample',
            sample['id'],
        )
        self.assertEqual(created['sample_ids'], [sample['id']])
        self.assertEqual(
            [row['id'] for row in styles.catalog(self.root)['samples']], [sample['id']]
        )

    def test_a_team_workspace_keeps_styles_under_the_shared_folder(self):
        team = self.base / 'team' / 'blogs'
        team.mkdir(parents=True)
        (team / 'hub.json').write_text('{"schema":1,"tool":"blog-studio"}')
        self.assertEqual(studio.inside(team, 'styles', 'x'), team / '.shared' / 'styles' / 'x')


class TeamStyleTests(unittest.TestCase):
    """In a joined team workspace, reading styles must leave nothing for git to record."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='blog-styles-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        environment = patch.dict(
            os.environ,
            {
                'BLOG_STUDIO_DATA': str(self.base / 'one'),
                'STUDIOS_CONFIG': str(self.base / 'none.json'),
                'GIT_CONFIG_GLOBAL': '/dev/null',
                'GIT_CONFIG_NOSYSTEM': '1',
                'GIT_AUTHOR_NAME': 'Synthetic Author',
                'GIT_AUTHOR_EMAIL': 'author@example.invalid',
                'GIT_COMMITTER_NAME': 'Synthetic Author',
                'GIT_COMMITTER_EMAIL': 'author@example.invalid',
            },
        )
        environment.start()
        self.addCleanup(environment.stop)
        remote = self.base / 'team.git'
        subprocess.run(
            ['git', 'init', '--bare', '--initial-branch=main', str(remote)],
            check=True,
            capture_output=True,
        )
        seed = self.base / 'seed'
        subprocess.run(['git', 'clone', str(remote), str(seed)], check=True, capture_output=True)
        (seed / 'presentations').mkdir()
        (seed / 'presentations/hub.json').write_text('{"schema":1,"tool":"presentation-studio"}')
        support.git(seed, 'add', '.')
        support.git(seed, 'commit', '-m', 'Synthetic studios fixture')
        support.git(seed, 'push', 'origin', 'main')
        self.root = teams.join(str(remote))
        self.found = teams.space(self.root)

    def run_cli(self, *words):
        out = io.StringIO()
        with patch.object(sys, 'argv', ['studio.py', '--root', str(self.root), *words]):
            with redirect_stdout(out):
                self.assertEqual(studio.main(), 0, out.getvalue())
        return json.loads(out.getvalue())

    def test_reading_styles_writes_nothing_and_saving_a_starter_is_committed(self):
        self.assertEqual(gitstate.changed(self.found), [])
        shown = self.run_cli('style', 'show', '--id', 'how-to')
        self.assertEqual(shown['guide'], None)
        self.assertEqual(len(styles.catalog(self.root)['styles']), 8)
        self.assertEqual(len(self.run_cli('list', 'styles')), 8)
        self.assertEqual(gitstate.changed(self.found), [])
        guide = self.base / 'guide.md'
        guide.write_text('A profile guide.')
        created = self.run_cli(
            'profile', 'create', '--name', 'Fictional Author', '--guide-file', str(guide)
        )
        self.assertEqual(created['revision'], 1)
        guide.write_text('My how-to.')
        saved = self.run_cli('style', 'save', '--id', 'how-to', '--guide-file', str(guide))
        self.assertEqual(saved['revision'], 2)
        self.assertTrue((self.root / '.shared' / 'styles' / 'how-to' / 'record.json').is_file())
        self.assertEqual(gitstate.changed(self.found), [], 'the change was recorded')
