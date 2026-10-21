"""Writing samples from a LinkedIn export, by its author."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import base64
import csv
import io
import zipfile

from test_editorial_tools import Fixture
import management
import studio


def export(
    articles=(('A first article', '<p>One paragraph.</p>'),),
    headline='Platform engineer',
    summary='Writes about rollouts.',
):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        rows = io.StringIO()
        writer = csv.DictWriter(rows, fieldnames=['First Name', 'Last Name', 'Headline', 'Summary'])
        writer.writeheader()
        writer.writerow(
            {
                'First Name': 'Synthetic',
                'Last Name': 'Author',
                'Headline': headline,
                'Summary': summary,
            }
        )
        archive.writestr('Profile.csv', rows.getvalue())
        for index, (title, body) in enumerate(articles, 1):
            archive.writestr(
                f'Articles/Articles/{index}.html',
                f'<html><head><title>{title}</title></head><body>{body}</body></html>',
            )
    return base64.b64encode(buffer.getvalue()).decode()


class LinkedInTests(Fixture):
    def upload(self, files, purpose='voice-sample', operation='a' * 32, **extra):
        return management.upload(
            self.root,
            {
                'operation': operation,
                'files': files,
                'purpose': purpose,
                'analyze': False,
                **extra,
            },
        )

    def test_a_linkedin_export_becomes_background_and_voice_samples_by_its_author(self):
        result = self.upload([{'linkedin': export()}])
        self.assertEqual(
            [
                (row['filename'], row['purpose'], row['state'], row['author'])
                for row in result['files']
            ],
            [
                ('LinkedIn · About', 'author-background', 'ready', 'Synthetic Author'),
                ('LinkedIn · A first article', 'voice-sample', 'ready', 'Synthetic Author'),
            ],
        )
        folder, about = studio.item(self.root, 'sources', result['files'][0]['source']['id'])
        self.assertEqual(
            (about['purposes'], about['author']), (['author-background'], 'Synthetic Author')
        )
        self.assertIn('Writes about rollouts.', (folder / 'content.md').read_text())
        folder, article = studio.item(self.root, 'sources', result['files'][1]['source']['id'])
        self.assertEqual(
            (article['purposes'], article['status'], article['author']),
            (['voice-sample'], 'ready', 'Synthetic Author'),
        )
        self.assertIn('One paragraph.', (folder / 'content.md').read_text())
        self.assertEqual(result['next_step'], 'Every file has text.')
        # A colleague's export: the name given for the request wins over the profile's.
        named = self.upload([{'linkedin': export()}], operation='9' * 32, author='Nick Example')
        self.assertEqual({row['author'] for row in named['files']}, {'Nick Example'})

    def test_an_export_without_articles_says_so_and_a_bad_zip_is_refused(self):
        result = self.upload([{'linkedin': export(articles=())}], operation='b' * 32)
        self.assertEqual(len(result['files']), 1)
        self.assertIn('No article samples', result['files'][0]['note'])
        with self.assertRaisesRegex(ValueError, 'LinkedIn export'):
            self.upload([{'linkedin': base64.b64encode(b'not a zip').decode()}], operation='c' * 32)

    def test_an_export_is_not_material_for_one_blog_and_comes_alone(self):
        with self.assertRaisesRegex(ValueError, 'writing samples'):
            self.upload([{'linkedin': export()}], purpose='material', operation='d' * 32)
        with self.assertRaisesRegex(ValueError, 'on its own'):
            self.upload([{'linkedin': export(), 'filename': 'export.zip'}], operation='e' * 32)
        self.assertEqual(list((self.root / 'sources').glob('*/record.json')), [])
        # Ordinary files beside an export keep the request's purpose and save no author.
        plain = {'filename': 'notes.md', 'content': base64.b64encode(b'# Notes\n\nText.').decode()}
        result = self.upload([plain, {'linkedin': export()}], operation='f' * 32)
        self.assertEqual(
            [(row['purpose'], row['author']) for row in result['files']],
            [
                ('voice-sample', None),
                ('author-background', 'Synthetic Author'),
                ('voice-sample', 'Synthetic Author'),
            ],
        )
