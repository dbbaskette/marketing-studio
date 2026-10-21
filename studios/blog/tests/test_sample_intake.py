"""Writing samples from a LinkedIn export, by its author."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import base64
import csv
import io
from unittest.mock import patch
import zipfile

from test_editorial_tools import Fixture
import blog_library
import management
import studio


def export(
    articles=(('A first article', '<p>One paragraph.</p>'),),
    headline='Platform engineer',
    summary='Writes about rollouts.',
    first='Synthetic',
):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        rows = io.StringIO()
        writer = csv.DictWriter(rows, fieldnames=['First Name', 'Last Name', 'Headline', 'Summary'])
        writer.writeheader()
        writer.writerow(
            {
                'First Name': first,
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

    def test_a_profile_name_that_is_not_an_author_name_is_dropped(self):
        result = self.upload([{'linkedin': export(first='S' * 250)}], operation='8' * 32)
        self.assertEqual([row['state'] for row in result['files']], ['ready', 'ready'])
        self.assertEqual({row['author'] or '' for row in result['files']}, {''})
        for row in result['files']:
            _, record = studio.item(self.root, 'sources', row['source']['id'])
            self.assertEqual(record.get('author') or '', '')

    def test_an_export_without_articles_says_so_and_a_bad_zip_is_refused(self):
        result = self.upload([{'linkedin': export(articles=())}], operation='b' * 32)
        self.assertEqual(len(result['files']), 1)
        self.assertIn('No article samples', result['files'][0]['note'])
        with self.assertRaisesRegex(ValueError, 'LinkedIn export'):
            self.upload([{'linkedin': base64.b64encode(b'not a zip').decode()}], operation='c' * 32)

    def test_an_export_is_not_material_for_one_blog_and_comes_alone(self):
        for purpose in ('material', 'style-sample', 'reference'):
            with self.assertRaisesRegex(ValueError, 'writing samples'):
                self.upload([{'linkedin': export()}], purpose=purpose, operation='d' * 32)
        with self.assertRaisesRegex(ValueError, 'one LinkedIn export at a time'):
            self.upload([{'linkedin': export()}, {'linkedin': export()}], operation='d' * 32)
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

    def test_an_unreadable_profile_gives_the_export_message(self):
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, 'w') as archive:
            archive.writestr(
                'Profile.csv', 'Headline,Summary\n\xff\xfe broken,text\n'.encode('latin-1')
            )
        with self.assertRaisesRegex(ValueError, 'not a LinkedIn export'):
            self.upload(
                [{'linkedin': base64.b64encode(buffer.getvalue()).decode()}], operation='1' * 32
            )
        self.assertEqual(list((self.root / 'sources').glob('*/record.json')), [])

    def test_long_articles_are_left_out_and_many_are_capped_with_a_note(self):
        long = '<p>' + 'word ' * 400 + '</p>'
        articles = (('Short', '<p>Short one.</p>'), ('Long', long))
        with patch.object(blog_library, 'MAX_TEXT', 1000):
            result = self.upload([{'linkedin': export(articles=articles)}], operation='2' * 32)
        self.assertEqual(
            [row['filename'] for row in result['files']], ['LinkedIn · About', 'LinkedIn · Short']
        )
        self.assertIn('1 articles were left out: too long to share.', result['files'][0]['note'])
        many = tuple(('Post %d' % n, '<p>Text %d.</p>' % n) for n in range(25))
        result = self.upload([{'linkedin': export(articles=many)}], operation='3' * 32)
        self.assertEqual(len(result['files']), management.MAX_UPLOAD_FILES)
        self.assertIn(
            'Only the first %d articles were read' % (management.MAX_UPLOAD_FILES - 1),
            result['files'][0]['note'],
        )
