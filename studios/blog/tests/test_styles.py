"""Styles: starter copies, revisions, pins and the style-sample purpose."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
from pathlib import Path

from test_editorial_tools import Fixture
import studio
import styles


class StyleTests(Fixture):
    def guide(self, text):
        path = self.base / 'guide.md'
        path.write_text(text)
        return str(path)

    def test_starters_are_copied_once_and_edited_or_retired_ones_stay(self):
        found = styles.catalog(self.root)
        ids = [row['id'] for row in found['styles']]
        self.assertIn('product-announcement', ids)
        self.assertEqual(len(ids), len(list(styles.SEEDS.glob('*.md'))))
        self.assertTrue(
            all(row['kind'] == 'seed' and row['status'] == 'confirmed' for row in found['styles'])
        )
        self.assertTrue(all(row['summary'] for row in found['styles']))
        self.command(
            'style', 'save', '--id', 'product-announcement', '--guide-file', self.guide('Edited.')
        )
        self.command('style', 'retire', '--id', 'how-to', '--expected-revision', '1', '--confirmed')
        self.assertEqual(styles.seed(self.root), [], 'nothing is copied back')
        edited = self.command('style', 'show', '--id', 'product-announcement')
        self.assertEqual((edited['revision'], Path(edited['guide']).read_text()), (2, 'Edited.'))
        self.assertEqual(self.command('style', 'show', '--id', 'how-to')['status'], 'retired')
        starter = Path(styles.SEEDS / 'product-announcement.md').read_text()
        self.assertTrue(starter.startswith('---\nname: Product announcement\nsummary: '))

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
