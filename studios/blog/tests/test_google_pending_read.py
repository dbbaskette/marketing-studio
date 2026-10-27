"""A Google Doc with images, chips and other people's pending suggestions reads like a clean one,
and the desk's send stays exact on it. No live Google: a closer model of suggest mode."""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import blog_runner
import desk
import desk_finish
import google_drive
import google_intake
import google_model as gm
import google_roundtrip as rt
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
            'Read the [Harbour plan](https://docs.google.com/document/d/plan) with Ada Lovelace first.',
            'Line one  \nline two of one paragraph.',
            'A page ends here.\n',
            'Tides vary[^1] by season.',
            '[^1]: Measured at noon.',
        ):
            self.assertIn(expected, body)
        # The data comes last, as Google's export puts it; an image not read is named so.
        self.assertTrue(body.endswith('[image1]: <data:image/png;base64,AAAA>'))
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

    def test_a_date_chip_and_a_newer_chip_read_as_the_text_they_show(self):
        doc = gm.objects_doc()
        elements = doc['tabs'][0]['documentTab']['body']['content'][1]['paragraph']['elements']
        date = {'dateElement': {'dateElementProperties': {'displayText': 'Oct 27, 2026'}}}
        newer = {'placeChip': {'placeChipProperties': {'displayText': 'Pier 39'}}}
        elements[0:0] = [date, gm.run(' at '), newer, gm.run(' ')]
        body = gs.accepted_markdown(doc, images={}).decode()
        self.assertIn('Oct 27, 2026 at Pier 39 ', body)
        # Without its shown text a date still reads, by its day.
        self.assertEqual(
            rt.chip_text('dateElement', {'dateElementProperties': {'timestamp': '2026-10-27T15:00:00Z'}}),
            '2026-10-27',
        )
        # The send sees the same words where the chip sits, at one Doc index.
        text, positions = desk_finish._base_of(
            {'elements': [{**date, 'startIndex': 5}, {**gm.run(' ok\n'), 'startIndex': 6}]}, 5
        )
        self.assertEqual(text, 'Oct 27, 2026 ok')
        self.assertEqual(positions[:12], [5] * 12)
        self.assertEqual(positions[12:], [6, 7, 8])

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


def small_doc(*lines):
    """A synthetic Doc of plain paragraphs (runs of text and style)."""
    import test_google_suggestions as fixtures

    doc = fixtures.paragraph_doc(
        *[(runs, {'namedStyleType': 'NORMAL_TEXT'}, bullet) for runs, bullet in lines]
    )
    doc['title'] = 'Post'
    return doc


class ExportDialectTests(unittest.TestCase):
    """Read with suggestions pending, the Doc is the same Markdown Google's export writes, so
    a later read either way sees no change Google did not make."""

    LINK = {'link': {'url': 'https://example.com/guide'}}

    def doc(self):
        bullet = {'listId': 'l1'}
        doc = small_doc(
            ([('Read the ', {}), ('guide', self.LINK), (' first.\n', {})], None),
            ([('One ', {}), ('bold', {'bold': True}), (' item.\n', {})], bullet),
            ([('Two items.\n', {})], bullet),
            ([('The end.\n', {})], None),
        )
        doc['tabs'][0]['documentTab']['lists'] = {
            'l1': {'listProperties': {'nestingLevels': [{'glyphSymbol': '●'}]}}
        }
        return doc

    # As Google's Markdown export writes this Doc.
    EXPORT = (
        'Read the [guide](https://example.com/guide) first.\n\n'
        '* One **bold** item.  \n'
        '* Two items.\n\n'
        'The end.'
    )

    def test_the_reader_writes_the_exports_markdown(self):
        self.assertEqual(gs.accepted_markdown(self.doc(), images=[]).decode(), self.EXPORT)

    def test_a_blog_read_clean_then_with_suggestions_sees_no_change(self):
        import google_workflow as gw

        clean = gm.Model(self.doc(), self.EXPORT)
        with tempfile.TemporaryDirectory() as folder:
            rt.capture(clean, 'fixture-doc', 't.0', Path(folder) / 'clean')
            first = (Path(folder) / 'clean' / 'document.md').read_text()
            clean.teammate('really ', 'first.')
            rt.capture(clean, 'fixture-doc', 't.0', Path(folder) / 'pending')
            again = (Path(folder) / 'pending' / 'document.md').read_text()
        self.assertEqual(again, first)
        chunks = gw.text_chunks(first, first.replace('The end.', 'The finish.'), again)
        self.assertFalse([c for c in chunks if c[0] == 'theirs' and c[1]])

    def test_the_same_image_read_two_ways_is_no_change(self):
        doc = gm.objects_doc()
        one = gs.accepted_markdown(
            doc, images=['data:image/png;base64,ONE', 'data:image/png;base64,TWO']
        )
        two = gs.accepted_markdown(
            doc, images=['data:image/png;base64,AAA', 'data:image/png;base64,BBB']
        )
        found, left, _ = desk_finish.google_changes(
            one.decode(), '# Harbour notes\n\n' + two.decode(), 'Harbour notes'
        )
        self.assertEqual((found, left), ([], 0))


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


class PendingRecordTests(PendingDocCase):
    """Other people's pending suggestions, recorded beside the blog and placed on the desk."""

    def test_the_record_says_kind_place_and_words_and_leaves_out_ours(self):
        self.start()
        import google_pending

        found = google_pending.read(self.root, self.ident)
        self.assertEqual(
            [
                (f['kind'], f['text'], f['start'], f['end'], f['inserted'], f['removed'])
                for f in found
            ],
            [
                (
                    'replacement',
                    'We keep the plan simple and clear.',
                    17,
                    28,
                    'quite ',
                    'simple and ',
                ),
                ('insertion', 'The end.', 0, 0, 'Truly ', ''),
            ],
        )
        self.assertEqual(found[0]['ids'], ['teammate', 'teammate-d'])
        # Our own suggestions, once sent, are not recorded as the Doc's.
        self.edit([('An opening paragraph about harbours.', 'An opening paragraph about ports.')])
        plan = self.act('google-plan', mode='auto')
        self.act('google-send', plan=plan['plan'], confirmed=True)
        with self.assertRaisesRegex(ValueError, 'sent before'):
            self.act('google-plan', mode='auto')  # A re-read, with ours now waiting too.
        self.assertEqual(len(google_pending.read(self.root, self.ident)), 2)

    def test_marks_sit_where_the_words_still_read_so(self):
        self.start()
        import desk_jobs

        shown = desk_jobs.view(self.root, self.ident)['doc_suggestions']
        self.assertEqual(shown['count'], 2)
        text = {
            mark['part']: desk.text_of(desk.read(self.root, self.ident), mark['part'])
            for mark in shown['marks']
        }
        placed = [
            (m['kind'], text[m['part']][m['at'] : m['at'] + m['length']], m['inserted'])
            for m in shown['marks']
        ]
        self.assertEqual(
            placed, [('replacement', 'simple and ', 'quite '), ('insertion', '', 'Truly ')]
        )
        # Words reworded on the desk: that mark is left out, the other stays.
        self.edit([('simple and clear', 'short and clear')])
        shown = desk_jobs.view(self.root, self.ident)['doc_suggestions']
        self.assertEqual(shown['count'], 2, 'still pending in the Doc')
        self.assertEqual([m['kind'] for m in shown['marks']], ['insertion'])

    def test_a_re_read_drops_what_google_decided(self):
        self.start()
        import desk_jobs

        self.client.decide(accept_ids=set(), reject_ids={'teammate-2'})
        self.edit([('An opening paragraph about harbours.', 'An opening paragraph about ports.')])
        self.act('google-plan', mode='auto')
        shown = desk_jobs.view(self.root, self.ident)['doc_suggestions']
        self.assertEqual([m['kind'] for m in shown['marks']], ['replacement'])


class PendingReviewTests(PendingDocCase):
    """Copy edit and Humanize are told what the Doc already suggests."""

    def test_the_review_jobs_are_told_the_docs_pending_suggestions(self):
        self.start()
        draft = desk.read(self.root, self.ident)
        for tool, level in (('copyedit', None), ('humanize', 'light')):
            with self.subTest(tool=tool):
                _, payload, guidance, _ = desk_finish.request(
                    self.root, self.ident, draft, tool, level
                )
                self.assertIn(desk_finish.DOC_PENDING, guidance)
                self.assertIn('Do not suggest the same change again', guidance)
                self.assertEqual(
                    [(p['removes'], p['inserts']) for p in payload['doc_suggestions']],
                    [('simple and ', 'quite '), ('', 'Truly ')],
                )
        _, payload, guidance, _ = desk_finish.request(self.root, self.ident, draft, 'feedback')
        self.assertNotIn(desk_finish.DOC_PENDING, guidance)
        import google_pending

        google_pending.forget(self.root, self.ident)
        _, payload, guidance, _ = desk_finish.request(self.root, self.ident, draft, 'copyedit')
        self.assertNotIn('doc_suggestions', payload)


class MarkPlacementTests(unittest.TestCase):
    """A mark sits in its own paragraph at its place there, or not at all."""

    def bench(self, doc, prepare):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'workspace'
        studio.initialize(self.root)
        self.addCleanup(lambda: blog_runner.ENGINES.pop(str(self.root), None))
        self.client = gm.Model(doc)
        prepare(self.client)
        with patch.object(google_drive, 'Client', return_value=self.client):
            found = google_intake.preview(self.root, {'url': URL})
            made = google_intake.start(
                self.root,
                {
                    'preview': found['preview'],
                    'expected': found['expected'],
                    'title': 'Post',
                    'confirmed': True,
                },
            )
        held = studio._HELD.set(True)
        self.addCleanup(studio._HELD.reset, held)
        self.ident = desk.create(self.root, {'article': made['id']})['id']

    def marks(self):
        import google_pending

        draft = desk.read(self.root, self.ident)
        return [
            (m['part'], desk.text_of(draft, m['part'])[: m['at']], m['inserted'])
            for m in google_pending.on_desk(self.root, self.ident, draft)
        ]

    def test_a_mark_never_moves_to_the_same_words_elsewhere(self):
        self.bench(
            small_doc(
                ([('Earlier we study the core data model in detail, first.\n', {})], None),
                ([('Today we study the core data model in detail, later.\n', {})], None),
            ),
            lambda m: m.teammate('shared ', 'data model in detail, first'),
        )
        marks = self.marks()
        self.assertEqual(len(marks), 1)
        self.assertEqual(marks[0][2], 'shared ')
        self.assertTrue(marks[0][1].endswith('Earlier we study the core '), 'in its own paragraph')
        draft = desk.read(self.root, self.ident)
        text = desk.text_of(draft, 'opening').replace(
            'the core data model in detail, first', 'the main data model in detail, first'
        )
        desk.save(self.root, self.ident, draft['revision'], 'opening', text)
        self.assertEqual(self.marks(), [], 'its paragraph changed: not marked, never moved')

    def test_a_mark_beside_a_link_or_bold_is_placed_in_the_markdown(self):
        link = {'link': {'url': 'https://example.com/patterns'}}
        self.bench(
            small_doc(
                (
                    [('We rely on proven ', {}), ('data patterns', link), (' that work.\n', {})],
                    None,
                ),
                ([('Utilize', {'bold': True}), (' the logs.\n', {})], None),
            ),
            lambda m: (
                m.teammate('very ', 'proven'),
                m.teammate('', 'Utilize', ident='t2', delete='Utilize'),
            ),
        )
        draft = desk.read(self.root, self.ident)
        import google_pending

        placed = google_pending.on_desk(self.root, self.ident, draft)
        self.assertEqual(len(placed), 2, 'both marked')
        text = desk.text_of(draft, placed[0]['part'])
        self.assertTrue(text[: placed[0]['at']].endswith('We rely on '))
        removed = placed[1]
        self.assertEqual(
            desk.text_of(draft, removed['part'])[removed['at'] : removed['at'] + removed['length']],
            'Utilize',
        )


class OwnSuggestionsTests(PendingDocCase):
    """Only our waiting edits are ours: a note of ours holds nothing and hides nothing."""

    def test_a_note_of_ours_neither_holds_nor_hides_a_teammates_suggestion(self):
        self.start()
        import google_pending

        draft = desk.read(self.root, self.ident)
        desk.save(self.root, self.ident, draft['revision'], 'title', 'Harbour notes, renamed')
        plan = self.act('google-plan', mode='auto')
        self.assertEqual([p['kind'] for p in plan['proposals']], ['comment'])
        self.act('google-send', plan=plan['plan'], confirmed=True)
        self.client.teammate('very ', 'opening paragraph', ident='teammate-3')
        self.edit([('The end.', 'The finish.')])
        plan = self.act('google-plan', mode='auto')
        self.assertEqual(plan['waiting'], 0)
        self.assertIn('teammate-3', [e['id'] for e in google_pending.read(self.root, self.ident)])


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
        self.assertEqual(
            plan['doc_overlap'], 1, 'one change is over words a Doc suggestion changes'
        )
        result = self.act('google-send', plan=plan['plan'], confirmed=True)
        self.assertEqual(result['status'], 'verified-pending')
        edits = [(p['before'], p['after']) for p in plan['proposals'] if p['kind'] == 'edit']
        # Beside an image, a chip or someone else's suggestion, ours goes as a suggestion by
        # the Doc's own indexes; over their words, as a comment on the paragraph's own words.
        for edit in (('the', 'this'), ('with', 'beside'), ('Line one', 'First line')):
            self.assertIn(edit, edits)
        comments = [p for p in plan['proposals'] if p['kind'] == 'comment']
        self.assertEqual(len(comments), 1)
        self.assertIn('short and clear', comments[0]['reason'])
        self.assertEqual(comments[0]['before'], 'We keep the plan', 'on its own paragraph')
        objects = [line.count('￼') for line in self.accepted()]
        self.client.decide(accept_ids=self.ours())
        lines = self.accepted()
        self.assertIn('An opening paragraph about ports.', lines)
        self.assertIn('See this chart \ufffc for the trend.', lines)
        self.assertIn('Read the \ufffc beside \ufffc first.', lines)
        # A paragraph with a line break is one paragraph: the change lands in it exactly.
        self.assertIn('First line\x0bline two of one paragraph.', lines)
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

    def test_a_change_at_their_insertion_point_goes_and_is_counted(self):
        self.edit([('The end.', 'An end.')])
        plan = self.act('google-plan', mode='auto')
        self.assertEqual(
            [(p['kind'], p['before'], p['after']) for p in plan['proposals']],
            [('edit', 'The', 'An')],
        )
        self.assertEqual(plan['doc_overlap'], 1, 'it sits where their insertion goes')
        self.assertEqual(
            self.act('google-send', plan=plan['plan'], confirmed=True)['status'], 'verified-pending'
        )

    def test_a_teammates_suggestion_alone_holds_nothing(self):
        self.edit([('The end.', 'The finish.')])
        plan = self.act('google-plan', mode='auto')
        self.assertEqual(plan['waiting'], 0)
        self.assertEqual(len(plan['proposals']), 1)
        self.assertEqual(plan['proposals'][0]['kind'], 'edit', 'beside their insertion: ours')
        self.assertEqual(plan['doc_overlap'], 0, 'its words are not theirs')


if __name__ == '__main__':
    unittest.main()
