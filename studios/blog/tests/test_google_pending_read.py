"""A Google Doc with images, chips and other people's pending suggestions reads like a clean one,
and the desk's send stays exact on it. No live Google: a closer model of suggest mode."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import blog_runner
import desk
import google_drive
import google_intake
import google_model as gm
import google_suggestions as gs
import studio

URL = 'https://docs.google.com/document/d/fixture-doc/edit'


class LenientReadTests(unittest.TestCase):
    """The Doc without its suggestions, read as Google's own export writes it."""

    def test_images_chips_breaks_and_footnotes_read_as_the_export_writes_them(self):
        body = gs.accepted_markdown(
            gm.objects_doc(), images={'kix.one': 'data:image/png;base64,AAAA'}
        ).decode()
        for expected in (
            '![][image1]',
            'See the chart ![A trend chart][image2] for the trend.',
            '### **Key Patterns**',
            'Read the [Harbour plan](<https://docs.google.com/document/d/plan>) with Ada Lovelace first.',
            'Line one  \nline two of one paragraph.',
            'A page ends here.\n',
            'Tides vary[^1] by season.',
            '[^1]: Measured at noon.',
        ):
            self.assertIn(expected, body)
        # The data comes last, as Google's export puts it; an image not read is named so.
        self.assertTrue(body.endswith('[image1]: <data:image/png;base64,AAAA>\n'))
        self.assertNotIn('[image2]:', body)
        missing = gm.objects_doc()
        del missing['tabs'][0]['documentTab']['inlineObjects']['kix.two']
        self.assertIn(
            '![An image Blog Studio could not read from the Doc][image2]',
            gs.accepted_markdown(missing, images={}).decode(),
        )

    def test_numbering_follows_the_document_and_a_list_reads_back_the_same(self):
        doc = gm.objects_doc()
        images = {'kix.one': 'data:image/png;base64,ONE', 'kix.two': 'data:image/png;base64,TWO'}
        body = gs.accepted_markdown(doc, images=images)
        self.assertEqual(gs.images_in(body.decode()), [images['kix.one'], images['kix.two']])
        self.assertEqual(gs.accepted_markdown(doc, images=gs.images_in(body.decode())), body)

    def test_a_table_reads_as_a_pipe_table(self):
        doc = gm.objects_doc()
        cell = lambda text: {'content': [{'paragraph': {'elements': [gm.run(text + '\n')]}}]}  # noqa: E731
        table = {
            'tableRows': [
                {'tableCells': [cell('Port'), cell('Depth')]},
                {'tableCells': [cell('North'), cell('12 | m')]},
            ]
        }
        doc['tabs'][0]['documentTab']['body']['content'].insert(2, {'table': table})
        body = gs.accepted_markdown(doc, images={}).decode()
        self.assertIn('| Port | Depth |\n| --- | --- |\n| North | 12 \\| m |', body)

    def test_anything_else_is_named_plainly(self):
        doc = gm.objects_doc()
        doc['tabs'][0]['documentTab']['body']['content'][1]['paragraph']['elements'].insert(
            0, {'equation': {}}
        )
        with self.assertRaisesRegex(
            google_drive.GoogleError,
            '^This Google Doc holds an equation that Blog Studio cannot read yet. Replace it',
        ):
            gs.accepted_markdown(doc, images={})

    def test_the_strict_reader_still_leaves_objects_to_googles_export(self):
        with self.assertRaises(google_drive.GoogleError):
            gs.accepted_markdown(gm.objects_doc())


class PendingDocCase(unittest.TestCase):
    """A blog started from the objects Doc while a teammate's suggestions wait in it."""

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'workspace'
        studio.initialize(self.root)
        self.addCleanup(lambda: blog_runner.ENGINES.pop(str(self.root), None))
        self.client = gm.Model(gm.objects_doc())
        self.client.images = {
            'https://lh3.googleusercontent.com/one': gm.PNG,
            'https://lh3.googleusercontent.com/two': gm.PNG,
        }
        # A teammate suggests words in two paragraphs, one with a deletion too.
        self.client.teammate('quite ', 'simple and clear', delete='simple and ')
        self.client.teammate('Truly ', 'The end.', ident='teammate-2')

    def act(self, action, **data):
        with patch.object(google_drive, 'Client', return_value=self.client):
            return desk.dispatch(self.root, action, {'id': self.ident, **data})

    def read(self):
        with patch.object(google_drive, 'Client', return_value=self.client):
            return google_intake.preview(self.root, {'url': URL})

    def start(self):
        found = self.read()
        with patch.object(google_drive, 'Client', return_value=self.client):
            made = google_intake.start(
                self.root,
                {
                    'preview': found['preview'],
                    'expected': found['expected'],
                    'title': 'Harbour notes',
                    'confirmed': True,
                },
            )
        held = studio._HELD.set(True)
        self.addCleanup(studio._HELD.reset, held)
        self.ident = desk.create(self.root, {'article': made['id']})['id']
        return found

    def draft(self):
        return (studio.item(self.root, 'articles', self.ident)[0] / 'DRAFT.md').read_text()

    def edit(self, changes):
        draft = desk.read(self.root, self.ident)
        for part in ['opening'] + [section['id'] for section in draft['sections']]:
            text = desk.text_of(draft, part)
            changed = text
            for old, new in changes:
                changed = changed.replace(old, new)
            if changed != text:
                desk.save(self.root, self.ident, draft['revision'], part, changed)
                draft = desk.read(self.root, self.ident)

    def accepted(self):
        doc = self.client.native_read('x', accepted_preview=True)
        return [
            ''.join(
                e['textRun']['content'] if 'textRun' in e else '￼'
                for e in block['paragraph']['elements']
            ).rstrip('\n')
            for block in doc['tabs'][0]['documentTab']['body']['content']
            if 'paragraph' in block
        ]


class PendingReadTests(PendingDocCase):
    def test_a_doc_with_pending_suggestions_reads_as_it_is_without_them(self):
        found = self.start()
        self.assertIn('We keep the plan simple and clear.', found['content'])
        self.assertNotIn('quite', found['content'])
        self.assertNotIn('Truly', found['content'])
        draft = self.draft()
        self.assertIn('[image1]: <data:image/png;base64,', draft)
        self.assertIn('[image2]: <data:image/png;base64,', draft)
        self.assertEqual(self.client.writes, 0, 'reading writes nothing to the Doc')
        self.assertEqual(
            [t['status'] for t in self.client.threads], ['OPEN', 'OPEN', 'OPEN'], 'theirs untouched'
        )

    def test_an_image_google_does_not_send_is_kept_visible(self):
        del self.client.images['https://lh3.googleusercontent.com/one']
        found = self.start()
        self.assertIn('An opening paragraph about harbours.', found['content'])
        self.assertIn('![An image Blog Studio could not read from the Doc][image1]', self.draft())

    def test_a_read_that_fails_can_be_tried_again(self):
        doc = gm.objects_doc()
        doc['tabs'][0]['documentTab']['body']['content'][1]['paragraph']['elements'].insert(
            0, {'equation': {}}
        )
        good = self.client
        self.client = gm.Model(doc)
        self.client.teammate('x', 'The end.')
        for _ in range(2):
            with self.assertRaisesRegex(google_drive.GoogleError, 'holds an equation'):
                self.read()
        staging = (
            list((self.root / '.blog-runs').rglob('desk-*'))
            if (self.root / '.blog-runs').exists()
            else []
        )
        self.assertEqual(staging, [], 'a failed read leaves nothing behind')
        self.client = good
        self.assertEqual(self.read()['status'], 'preview')


class PendingSendTests(PendingDocCase):
    """Our changes beside theirs land exactly, or go as comments, and theirs stay theirs."""

    def setUp(self):
        super().setUp()
        self.start()

    def ours(self):
        return {
            t['suggestionId']
            for t in self.client.threads
            if not t['suggestionId'].startswith('teammate')
        }

    def test_accepting_ours_and_rejecting_theirs_gives_the_desk_and_keeps_the_images(self):
        self.edit(
            [
                ('An opening paragraph about harbours.', 'An opening paragraph about ports.'),
                ('See the chart', 'See this chart'),  # A paragraph with an image: a comment.
                ('with Ada Lovelace', 'beside Ada Lovelace'),  # A paragraph with chips: a comment.
                ('simple and clear', 'short and clear'),  # Words a teammate's suggestion changes.
                ('Line one', 'First line'),
            ]
        )
        plan = self.act('google-plan', mode='auto')
        self.assertEqual(plan['left'], 0)
        result = self.act('google-send', plan=plan['plan'], confirmed=True)
        self.assertEqual(result['status'], 'verified-pending')
        comments = [p for p in plan['proposals'] if p['kind'] == 'comment']
        said = ' '.join(p['reason'] for p in comments)
        for words in ('See this chart', 'beside Ada Lovelace', 'short and clear'):
            self.assertIn(words, said, 'where Google cannot take ours exactly, a comment')
        objects = [line.count('￼') for line in self.accepted()]
        self.client.decide(accept_ids=self.ours())
        lines = self.accepted()
        self.assertIn('An opening paragraph about ports.', lines)
        self.assertEqual([line.count('￼') for line in lines], objects, 'images untouched')
        self.assertIn('We keep the plan simple and clear.', lines, 'theirs rejected, the base kept')
        self.assertIn('The end.', lines)

    def test_accepting_both_corrupts_nothing(self):
        self.edit([('An opening paragraph about harbours.', 'An opening paragraph about ports.')])
        plan = self.act('google-plan', mode='auto')
        self.assertEqual(
            self.act('google-send', plan=plan['plan'], confirmed=True)['status'], 'verified-pending'
        )
        self.client.decide()
        lines = self.accepted()
        self.assertIn('An opening paragraph about ports.', lines)
        self.assertIn('We keep the plan quite clear.', lines)
        self.assertIn('Truly The end.', lines)

    def test_a_teammates_suggestion_alone_holds_nothing(self):
        self.edit([('The end.', 'The finish.')])
        plan = self.act('google-plan', mode='auto')
        self.assertEqual(plan['waiting'], 0)
        self.assertEqual(len(plan['proposals']), 1)
        self.assertEqual(plan['proposals'][0]['kind'], 'comment', 'their paragraph: a comment')


if __name__ == '__main__':
    unittest.main()
