"""Native suggestions contract fixtures; no live credentials or external writes."""

import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from test_google_roundtrip import Provider, document
import google_drive as gd
import google_roundtrip as rt
import google_workflow as gw
import google_suggestions as gs
import studio
import author_workflow


class ReviewProvider(Provider):
    """Retain suggested deletions inline; project accepted/rejected views separately."""

    def __init__(self):
        super().__init__()
        self.comments = []
        self.anchors = []
        self.threads = []

    def native_read(self, file_id, inline=False, comments=False, accepted_preview=False):
        doc = copy.deepcopy(self.doc)
        doc['suggestionsViewMode'] = (
            'SUGGESTIONS_INLINE'
            if inline
            else 'PREVIEW_SUGGESTIONS_ACCEPTED'
            if accepted_preview
            else 'PREVIEW_WITHOUT_SUGGESTIONS'
        )
        if not inline:
            start = 1
            for block in doc['tabs'][0]['documentTab']['body']['content']:
                if 'paragraph' not in block:
                    continue
                block['startIndex'] = start
                elements = []
                for e in block['paragraph']['elements']:
                    run = e['textRun']
                    if (
                        run.get('suggestedDeletionIds')
                        if accepted_preview
                        else run.get('suggestedInsertionIds')
                    ):
                        continue
                    run.pop('suggestedInsertionIds', None)
                    run.pop('suggestedDeletionIds', None)
                    e['startIndex'] = start
                    start += rt.utf16(run['content'])
                    e['endIndex'] = start
                    elements.append(e)
                block['paragraph']['elements'] = elements
                block['endIndex'] = start
        if comments:
            doc.update(
                commentsViewMode='COMMENTS_VIEW_MODE_INCLUDED',
                comments=copy.deepcopy(self.comments),
                suggestions=copy.deepcopy(self.threads),
            )
            doc['tabs'][0]['documentTab']['commentAnchors'] = copy.deepcopy(self.anchors)
        return doc

    def native_review_update(self, file_id, revision, requests):
        if self.doc['revisionId'] != revision:
            raise gd.GoogleError('stale revision')
        self.writes += 1
        blocks = self.doc['tabs'][0]['documentTab']['body']['content']
        for b in blocks:
            if 'paragraph' in b:
                b['paragraph']['elements'] = [
                    {'textRun': dict(copy.deepcopy(e['textRun']), content=c)}
                    for e in b['paragraph']['elements']
                    for c in e['textRun']['content']
                ]

        def reindex():
            start = 1
            for b in blocks:
                if 'paragraph' not in b:
                    continue
                b['startIndex'] = start
                for e in b['paragraph']['elements']:
                    e['startIndex'] = start
                    start += rt.utf16(e['textRun']['content'])
                    e['endIndex'] = start
                b['endIndex'] = start

        reindex()
        for req in requests:
            if 'insertComment' in req:
                c = req['insertComment']
                r = c['range']
                cid = 'c' + str(len(self.comments))
                aid = 'a' + cid
                quote = ''.join(
                    e['textRun']['content']
                    for b in blocks
                    if 'paragraph' in b
                    for e in b['paragraph']['elements']
                    if r['startIndex'] <= e['startIndex'] < r['endIndex']
                )
                self.comments.append(
                    {
                        'commentId': cid,
                        'anchorId': aid,
                        'headPost': {'content': c['content']},
                        'status': 'OPEN',
                        'plainTextQuote': quote,
                    }
                )
                self.anchors.append({'anchorId': aid, 'ranges': [r]})
                continue
            if 'insertText' in req:
                x = req['insertText']
                index = x['location']['index']
                for b in blocks:
                    if 'paragraph' not in b:
                        continue
                    elements = b['paragraph']['elements']
                    found = next(
                        (i for i, e in enumerate(elements) if e['startIndex'] == index), None
                    )
                    if found is not None:
                        sid = 's' + str(len(self.threads))
                        self.threads.append({'suggestionId': sid, 'status': 'OPEN'})
                        elements[found:found] = [
                            {
                                'textRun': {
                                    'content': c,
                                    'textStyle': {},
                                    'suggestedInsertionIds': [sid],
                                }
                            }
                            for c in x['text']
                        ]
                        break
                else:
                    raise AssertionError(index)
                reindex()
                continue
            deletion = 'deleteContentRange' in req
            x = req['deleteContentRange' if deletion else 'updateTextStyle']
            r = x['range']
            if deletion:
                sid = 's' + str(len(self.threads))
                self.threads.append({'suggestionId': sid, 'status': 'OPEN'})
            for b in blocks:
                if 'paragraph' not in b:
                    continue
                for e in b['paragraph']['elements']:
                    if r['startIndex'] <= e['startIndex'] < r['endIndex']:
                        if deletion:
                            e['textRun']['suggestedDeletionIds'] = [sid]
                        else:
                            e['textRun']['textStyle'] = copy.deepcopy(x['textStyle'])
        self.doc['revisionId'] = 'r2'
        self.version = '2'
        return {'commentUpdateState': 'ALL_SAVED'}


def reindex(blocks):
    start = 1
    for block in blocks:
        if 'paragraph' not in block:
            continue
        block['startIndex'] = start
        for element in block['paragraph']['elements']:
            element['startIndex'] = start
            start += rt.utf16(element['textRun']['content'])
            element['endIndex'] = start
        block['endIndex'] = start


def add_teammate_suggestion(client):
    """A colleague's pending insertion in the second paragraph, as Google shows it inline."""
    blocks = client.doc['tabs'][0]['documentTab']['body']['content']
    paragraph = blocks[2]['paragraph']
    run = paragraph['elements'][0]['textRun']
    text = run['content']
    cut = text.index('slow')
    style = run.get('textStyle', {})
    paragraph['elements'] = [
        {'textRun': {'content': text[:cut], 'textStyle': style}},
        {
            'textRun': {
                'content': 'very ',
                'textStyle': style,
                'suggestedInsertionIds': ['teammate-1'],
            }
        },
        {'textRun': {'content': text[cut:], 'textStyle': style}},
    ]
    reindex(blocks)
    client.threads.append({'suggestionId': 'teammate-1', 'status': 'OPEN'})


def decide_suggestions(client, accept=()):
    """A reviewer accepts the suggestions whose inserted or deleted text is named, and rejects the rest."""
    blocks = client.doc['tabs'][0]['documentTab']['body']['content']
    texts = {}
    for block in blocks:
        for element in block.get('paragraph', {}).get('elements', []):
            run = element['textRun']
            for name in run.get('suggestedInsertionIds', []) + run.get('suggestedDeletionIds', []):
                texts[name] = texts.get(name, '') + run['content']
    accepted = {name for name, text in texts.items() if text in accept}
    for block in blocks:
        if 'paragraph' not in block:
            continue
        kept = []
        for element in block['paragraph']['elements']:
            run = element['textRun']
            inserted = run.pop('suggestedInsertionIds', None)
            deleted = run.pop('suggestedDeletionIds', None)
            if inserted and not set(inserted) & accepted:
                continue
            if deleted and set(deleted) & accepted:
                continue
            kept.append(element)
        block['paragraph']['elements'] = kept
    reindex(blocks)
    for thread in client.threads:
        thread['status'] = 'ACCEPTED' if thread['suggestionId'] in accepted else 'REJECTED'
    for comment in client.comments:
        comment['status'] = 'RESOLVED'
    client.doc['revisionId'] = 'r3'
    client.version = '3'


def paragraph_doc(*paragraphs, lists=None):
    """A one-tab accepted-text document from (runs, paragraph style, bullet) tuples."""
    blocks = [{'startIndex': 0, 'endIndex': 1, 'sectionBreak': {}}]
    for runs, style, bullet in paragraphs:
        paragraph = {
            'paragraphStyle': style,
            'elements': [
                {'textRun': {'content': text, 'textStyle': run_style}} for text, run_style in runs
            ],
        }
        if bullet:
            paragraph['bullet'] = bullet
        blocks.append({'paragraph': paragraph})
    reindex(blocks)
    native = {'body': {'content': blocks}}
    if lists:
        native['lists'] = lists
    return {
        'documentId': 'fixture-doc',
        'revisionId': 'r1',
        'title': 'Private blog',
        'tabs': [{'tabProperties': {'tabId': 't.0', 'title': 'Blog'}, 'documentTab': native}],
    }


class SuggestionsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'work'
        studio.initialize(self.root)
        self.client = ReviewProvider()
        args = studio.parser().parse_args(
            [
                '--root',
                str(self.root),
                'article',
                'create',
                '--title',
                'Review fixture',
                '--mode',
                'existing',
            ]
        )
        self.aid = studio.article_command(self.root, args)['id']
        self.directory, self.record = studio.item(self.root, 'articles', self.aid)
        (self.directory / 'DRAFT.md').write_text('Saved unchanged draft.\n')
        document = {
            'document_id': 'fixture-doc',
            'url': 'https://docs.google.com/document/d/fixture-doc/edit',
            'tab_ids': ['t.0'],
            'format_sha256': gs.signature(self.client.doc),
            'format_version': rt.FORMAT_VERSION,
        }
        self.record['google'] = {
            'schema': 1,
            'transfers': {},
            'baselines': {
                'draft': {
                    'local_sha256': gd.digest(b'Saved unchanged draft.\n'),
                    'document': document,
                }
            },
        }
        studio.persist(self.directory, 'articles', self.record)

    def findings(self):
        blocks = self.client.doc['tabs'][0]['documentTab']['body']['content']
        return [
            dict(
                id='proof-1',
                kind='edit',
                tab_id='t.0',
                start_index=5,
                before='delay',
                after='wait',
                reason='Use a plainer word.',
            ),
            dict(
                id='proof-2',
                kind='edit',
                tab_id='t.0',
                start_index=blocks[2]['startIndex'] + 8,
                before='isn’t',
                after='is not',
                reason='Requested formal voice.',
            ),
            dict(
                id='proof-3',
                kind='comment',
                tab_id='t.0',
                start_index=blocks[3]['startIndex'],
                before='Keep',
                reason='Check the cited source.',
            ),
        ]

    def plan(self, findings=None):
        path = self.root / 'review-plan.json'
        gs.plan(self.client, self.root, self.aid, 'draft', findings or self.findings(), path)
        return json.loads(path.read_text())

    def test_suggestions_keep_accepted_text_and_formatting_and_verify_anchors(self):
        old = gs.signature(self.client.doc)
        saved = self.plan()
        result = gs.apply(self.client, self.root, saved)
        self.assertEqual(result['status'], 'verified-pending')
        self.assertTrue(result['accepted_text_unchanged'])
        self.assertEqual(gs.signature(self.client.native_read('fixture-doc')), old)
        self.assertEqual(
            gs.signature(self.client.native_read('fixture-doc', accepted_preview=True)),
            saved['expected_sha256'],
        )
        self.assertEqual(len(result['comments']), 3)
        self.assertEqual(self.client.writes, 1)
        self.assertEqual((self.directory / 'DRAFT.md').read_text(), 'Saved unchanged draft.\n')
        with self.assertRaises(gd.GoogleError):
            gs.apply(self.client, self.root, saved)
        self.assertEqual(self.client.writes, 1)

    def test_changed_google_or_local_and_tampered_requests_block_writes(self):
        saved = self.plan()
        self.client.doc['revisionId'] = 'new'
        with self.assertRaises(gd.GoogleError):
            gs.apply(self.client, self.root, saved)
        self.client.doc['revisionId'] = 'r1'
        bad = copy.deepcopy(saved)
        bad['requests'].append({'deleteContentRange': {}})
        with self.assertRaises(gd.GoogleError):
            gs.apply(self.client, self.root, bad)
        (self.directory / 'DRAFT.md').write_text('Local changed')
        with self.assertRaises(gd.GoogleError):
            gs.apply(self.client, self.root, saved)
        self.assertEqual(self.client.writes, 0)

    def test_fresh_read_requires_pull_when_only_formatting_changes(self):
        self.client.doc['tabs'][0]['documentTab']['body']['content'][1]['paragraph'][
            'paragraphStyle'
        ]['lineSpacing'] = 222
        with self.assertRaisesRegex(gd.GoogleError, 'Pull the latest'):
            self.plan()
        self.assertEqual(self.client.writes, 0)

    def test_stale_quotes_overlaps_and_unicode_splits_are_refused(self):
        for changed in ({'before': 'missing'}, {'start_index': -1}, {'kind': 'wrong'}):
            f = self.findings()
            f[0].update(changed)
            with self.assertRaises(gd.GoogleError):
                gs.build(self.client.doc, f, ['t.0'])
        f = self.findings()
        f.append({**f[0], 'id': 'overlap'})
        with self.assertRaisesRegex(gd.GoogleError, 'Overlapping'):
            gs.build(self.client.doc, f, ['t.0'])
        f = self.findings()
        f[1].update(
            start_index=self.client.doc['tabs'][0]['documentTab']['body']['content'][2][
                'startIndex'
            ]
            + 1
        )
        with self.assertRaises(gd.GoogleError):
            gs.build(self.client.doc, f, ['t.0'])

    def test_uncertain_submission_reserves_attempt_and_never_retries(self):
        saved = self.plan()
        write = self.client.native_review_update

        def timeout(*args):
            write(*args)
            raise gd.GoogleError('timeout')

        self.client.native_review_update = timeout
        with self.assertRaises(gd.GoogleError):
            gs.apply(self.client, self.root, saved)
        with self.assertRaises(gd.GoogleError):
            gs.apply(self.client, self.root, saved)
        self.assertEqual(self.client.writes, 1)
        # The response was lost but the write landed. Complete readback settles it without another write.
        result = gs.verify(self.client, self.root, saved)
        self.assertEqual(result['status'], 'verified-pending')
        self.assertEqual(result['acknowledgement'], 'inferred-from-readback')
        self.assertEqual(self.client.writes, 1)
        with self.assertRaises(gd.GoogleError):
            gs.apply(self.client, self.root, saved)
        self.assertEqual(self.client.writes, 1)

    def test_lost_response_with_incomplete_readback_stays_unverified(self):
        saved = self.plan()
        write = self.client.native_review_update

        def timeout(*args):
            write(*args)
            self.client.comments.pop()
            raise gd.GoogleError('timeout')

        self.client.native_review_update = timeout
        with self.assertRaises(gd.GoogleError):
            gs.apply(self.client, self.root, saved)
        self.assertEqual(gs.verify(self.client, self.root, saved)['status'], 'needs-reconciliation')
        self.assertTrue(
            gs.contained(gs.ledger(self.root), gs.operation_key(saved) + '.json').is_file()
        )

    def test_definite_rejection_releases_the_reservation_and_its_findings(self):
        saved = self.plan()
        write = self.client.native_review_update
        refused = gd.GoogleError('Google rejected the write.', status=400)
        self.client.native_review_update = Mock(side_effect=refused)
        with self.assertRaisesRegex(gd.GoogleError, 'released') as caught:
            gs.apply(self.client, self.root, saved)
        self.assertEqual(caught.exception.status, 400)
        self.assertEqual(
            [p.name for p in gs.ledger(self.root).iterdir() if p.suffix in ('.json', '.finding')],
            [],
        )
        with self.assertRaisesRegex(gd.GoogleError, 'No recorded attempt'):
            gs.verify(self.client, self.root, saved)
        # Nothing was written, so the very same plan (and its finding IDs) can be sent.
        self.client.native_review_update = write
        self.assertEqual(gs.apply(self.client, self.root, saved)['status'], 'verified-pending')
        self.assertEqual(self.client.writes, 1)

    def test_lost_response_with_nothing_written_is_released_by_verify(self):
        saved = self.plan()
        write = self.client.native_review_update
        self.client.native_review_update = Mock(side_effect=gd.GoogleError('timeout'))
        with self.assertRaises(gd.GoogleError):
            gs.apply(self.client, self.root, saved)
        with self.assertRaisesRegex(gd.GoogleError, 'uncertain attempt'):
            gs.apply(self.client, self.root, saved)
        result = gs.verify(self.client, self.root, saved)
        self.assertEqual(result['status'], 'not-submitted')
        self.assertTrue(result['accepted_text_unchanged'])
        self.assertEqual(list(gs.ledger(self.root).glob('*.finding')), [])
        self.client.native_review_update = write
        self.assertEqual(gs.apply(self.client, self.root, saved)['status'], 'verified-pending')
        self.assertEqual(self.client.writes, 1)

    def test_server_error_on_a_write_is_not_treated_as_a_definite_refusal(self):
        saved = self.plan()
        self.client.native_review_update = Mock(
            side_effect=gd.GoogleError('Google request failed (HTTP 503).', status=503)
        )
        with self.assertRaises(gd.GoogleError) as caught:
            gs.apply(self.client, self.root, saved)
        self.assertFalse(caught.exception.definite)
        self.assertTrue(
            gs.contained(gs.ledger(self.root), gs.operation_key(saved) + '.json').is_file()
        )

    def test_teammate_suggestion_does_not_block_suggestions_in_other_paragraphs(self):
        add_teammate_suggestion(self.client)
        findings = [self.findings()[0], self.findings()[2]]
        saved = self.plan(findings)
        # With someone else's suggestion pending, an accept-all view would mix in their change.
        self.assertIsNone(saved['expected_sha256'])
        self.assertEqual(
            saved['targets'],
            [
                {
                    'tab_id': 't.0',
                    'start_index': 1,
                    'before': 'The delay is in handoffs.',
                    'after': 'The wait is in handoffs.',
                }
            ],
        )
        result = gs.apply(self.client, self.root, saved)
        self.assertEqual(result['status'], 'verified-pending')
        self.assertTrue(result['accepted_text_unchanged'])
        self.assertIn('teammate-1', json.dumps(self.client.native_read('fixture-doc', inline=True)))
        # Only the paragraph that already carries a pending suggestion is refused.
        with self.assertRaisesRegex(gd.GoogleError, 'pending suggestion'):
            gs.plan(
                self.client,
                self.root,
                self.aid,
                'draft',
                [self.findings()[1]],
                self.root / 'blocked.json',
            )
        # If the edited paragraph does not read back as proposed, verification fails closed.
        blocks = self.client.doc['tabs'][0]['documentTab']['body']['content']
        blocks[1]['paragraph']['elements'] = [
            e
            for e in blocks[1]['paragraph']['elements']
            if not e['textRun'].get('suggestedInsertionIds')
        ]
        reindex(blocks)
        self.assertEqual(gs.verify(self.client, self.root, saved)['status'], 'needs-reconciliation')

    def test_teammate_suggestion_and_nothing_written_is_released(self):
        add_teammate_suggestion(self.client)
        saved = self.plan([self.findings()[0]])
        self.client.native_review_update = Mock(side_effect=gd.GoogleError('timeout'))
        with self.assertRaises(gd.GoogleError):
            gs.apply(self.client, self.root, saved)
        self.assertEqual(gs.verify(self.client, self.root, saved)['status'], 'not-submitted')

    def test_findings_are_anchored_by_quote_and_the_saved_review_file_is_accepted(self):
        review = {
            'findings': [
                dict(id='proof-1', kind='edit', before='delay', after='wait', reason='Plainer.'),
                dict(
                    id='proof-2',
                    kind='comment',
                    before='Keep',
                    context='Keep this link.',
                    reason='Check it.',
                ),
            ]
        }
        path = self.root / 'quoted.json'
        result = gs.plan(self.client, self.root, self.aid, 'draft', review, path)
        self.assertEqual(result['findings'], 2)
        self.assertFalse(result['local_draft_has_unsent_edits'])
        saved = json.loads(path.read_text())
        blocks = self.client.doc['tabs'][0]['documentTab']['body']['content']
        self.assertEqual(
            [(f['tab_id'], f['start_index']) for f in saved['findings']],
            [('t.0', 5), ('t.0', blocks[3]['startIndex'])],
        )
        self.assertTrue(all('context' not in f for f in saved['findings']))
        self.assertEqual(gs.apply(self.client, self.root, saved)['status'], 'verified-pending')

    def test_repeated_or_missing_quotes_and_wrong_offsets_are_explained(self):
        doc = self.client.native_read('fixture-doc', inline=True, comments=True)
        finding = dict(id='q', kind='comment', before='is', reason='Which one?')
        with self.assertRaisesRegex(gd.GoogleError, 'appears 4 times'):
            gs.locate(doc, finding, ['t.0'])
        self.assertEqual(gs.locate(doc, {**finding, 'occurrence': 1}, ['t.0'])['start_index'], 11)
        self.assertEqual(
            gs.locate(doc, {**finding, 'context': 'delay is in'}, ['t.0'])['start_index'], 11
        )
        with self.assertRaisesRegex(gd.GoogleError, 'not in the current Google Doc'):
            gs.locate(doc, {**finding, 'before': 'absent words'}, ['t.0'])
        with self.assertRaisesRegex(gd.GoogleError, 'must be an exact snippet'):
            gs.locate(doc, {**finding, 'context': 'unrelated'}, ['t.0'])
        # A wrong offset is reported as a wrong offset, not as a change in Google.
        wrong = dict(
            id='w',
            kind='comment',
            tab_id='t.0',
            start_index=6,
            before='delay',
            reason='Off by one.',
        )
        with self.assertRaisesRegex(gd.GoogleError, 'not at the supplied start_index'):
            gs.build(doc, [wrong], ['t.0'])
        gone = dict(
            id='g',
            kind='comment',
            tab_id='t.0',
            start_index=5,
            before='vanished',
            reason='Really changed.',
        )
        with self.assertRaisesRegex(gd.GoogleError, 'wording changed'):
            gs.build(doc, [gone], ['t.0'])

    def test_partial_comments_and_wrong_anchors_fail_verification(self):
        saved = self.plan()
        gs.apply(self.client, self.root, saved)
        self.client.anchors[0]['ranges'][0] = {
            **self.client.anchors[0]['ranges'][0],
            'startIndex': 1,
        }
        self.assertEqual(gs.verify(self.client, self.root, saved)['status'], 'needs-reconciliation')
        self.client.comments = []
        self.assertEqual(gs.verify(self.client, self.root, saved)['status'], 'needs-reconciliation')

    def test_comment_only_needs_no_suggested_text_changes(self):
        saved = self.plan([self.findings()[2]])
        self.assertEqual(gs.apply(self.client, self.root, saved)['status'], 'verified-pending')
        self.assertEqual(self.client.threads, [])

    def test_review_pull_separates_pending_text_and_preserves_docx_and_threads(self):
        saved = self.plan()
        gs.apply(self.client, self.root, saved)
        output = self.root / 'snapshot'
        rt.capture(self.client, 'fixture-doc', 't.0', output, include_review=True)
        body = (output / 'document.md').read_text()
        obs = json.loads((output / 'observation.json').read_text())
        self.assertIn('isn’t', body)
        self.assertNotIn('is not', body)
        self.assertEqual(obs['suggestions'], 'excluded')
        self.assertGreater(obs['review_state']['pending'], 0)
        self.assertIn('accepted.json', gw.formatted_snapshot(output, obs, body))
        native = json.loads((output / 'native.json').read_text())
        self.assertEqual(len(native['comments']), 3)
        obs['review_state']['pending'] = 0
        with self.assertRaises(ValueError):
            gw.formatted_snapshot(output, obs, body)

    def test_review_pull_blocks_races_unsupported_structures_and_multiple_tabs(self):
        self.client.metadata = Mock(side_effect=[{'version': '1'}, {'version': '2'}])
        with self.assertRaises(gd.GoogleError):
            rt.capture(self.client, 'fixture-doc', 't.0', self.root / 'race', include_review=True)
        self.assertFalse((self.root / 'race').exists())
        doc = self.client.native_read('fixture-doc')
        doc['tabs'][0]['documentTab']['body']['content'].append({'table': {}})
        with self.assertRaises(gd.GoogleError):
            gs.accepted_markdown(doc)
        doc = self.client.native_read('fixture-doc')
        doc['tabs'].append(copy.deepcopy(doc['tabs'][0]))
        with self.assertRaises(gd.GoogleError):
            gs.accepted_markdown(doc)

    def test_pulled_pending_snapshot_enters_checkpoint_and_keeps_local_conflicts(self):
        from test_google_workflow import GoogleWorkflowTests

        fixture = GoogleWorkflowTests('runTest')
        fixture.setUp()
        self.addCleanup(fixture.temp.cleanup)
        body = gs.accepted_markdown(self.client.native_read('fixture-doc')).decode()
        fixture.save('draft', body)
        fixture.handoff()
        saved = self.plan()
        gs.apply(self.client, self.root, saved)
        out = self.root / 'pull'
        rt.capture(self.client, 'fixture-doc', 't.0', out, include_review=True)
        inputs = [
            '--observation',
            str(out / 'observation.json'),
            '--file',
            str(out / 'document.md'),
        ]
        compare = fixture.run_command('google', 'compare', '--id', fixture.aid, *inputs)
        self.assertEqual(compare['status'], 'unchanged')
        result = fixture.run_command(
            'google',
            'accept',
            '--id',
            fixture.aid,
            *inputs,
            '--snapshot',
            str(out),
            '--expected-comparison',
            compare['comparison'],
        )
        self.assertEqual(
            set(result['formatted_snapshot']), {'document.md', 'document.docx', 'snapshot.json'}
        )
        self.assertEqual(set(result['local_snapshot']), {'native.json', 'accepted.json'})
        self.assertEqual(fixture.body(), body)
        directory, record = studio.item(fixture.root, 'articles', fixture.aid)
        self.assertGreater(
            record['google']['baselines']['draft']['document']['review_state']['pending'], 0
        )
        # Raw Docs JSON, with the reviewers' comment threads, stays on this computer.
        native = directory / result['local_snapshot']['native.json']
        self.assertEqual(len(json.loads(native.read_text())['comments']), 3)
        self.assertEqual(native.stat().st_mode & 0o777, 0o600)
        from hub_workspace import Workspace

        shared = Workspace.__new__(Workspace).read_artifacts(directory, 'articles')
        self.assertFalse([name for name in shared if 'native' in name or 'accepted' in name])
        self.assertTrue(
            all(
                b'[Blog Studio' not in data and b'commentId' not in data
                for data, _ in shared.values()
            )
        )
        self.assertTrue(any(name.endswith('-document.docx') for name in shared))
        # Unsent local work is kept as it is; nothing from Google replaces it.
        fixture.save('draft', 'Unsent local work.')
        out = self.root / 'pull-again'
        rt.capture(self.client, 'fixture-doc', 't.0', out)
        compare = fixture.run_command(
            'google', 'compare', '--id', fixture.aid, '--snapshot', str(out)
        )
        self.assertEqual(compare['status'], 'local-only')
        kept = fixture.run_command(
            'google',
            'accept',
            '--id',
            fixture.aid,
            '--snapshot',
            str(out),
            '--expected-comparison',
            compare['comparison'],
        )
        self.assertEqual(kept['outcome'], 'local-only')
        self.assertIn('kept', kept['next_step'])
        self.assertEqual(fixture.body(), 'Unsent local work.')
        self.assertEqual(
            fixture.run_command('google', 'compare', '--id', fixture.aid, '--snapshot', str(out))[
                'status'
            ],
            'local-only',
        )
        # Only the current baseline's raw JSON is retained.
        self.assertEqual(
            {p.name[33:] for p in (directory / '.google-native').iterdir()},
            {'native.json', 'accepted.json'},
        )

    def test_deleted_text_and_multiple_same_paragraph_edits(self):
        f = self.findings()[:1]
        f[0]['after'] = ''
        f.append(
            dict(
                id='second',
                kind='edit',
                tab_id='t.0',
                start_index=17,
                before='handoffs',
                after='coordination',
                reason='Clarify.',
            )
        )
        saved = self.plan(f)
        self.assertEqual(gs.apply(self.client, self.root, saved)['status'], 'verified-pending')

    def test_existing_comment_prevents_duplicate_on_another_machine(self):
        self.client.comments = [
            {
                'headPost': {'content': '[Blog Studio proof-1] Earlier finding.'},
                'status': 'RESOLVED',
            }
        ]
        with self.assertRaisesRegex(gd.GoogleError, 'already has'):
            self.plan()
        self.assertEqual(self.client.writes, 0)

    def test_fragmented_runs_project_same_markdown_and_omit_pending(self):
        original = self.client.native_read('fixture-doc')
        before = gs.accepted_markdown(original)
        for b in original['tabs'][0]['documentTab']['body']['content']:
            if 'paragraph' not in b:
                continue
            b['paragraph']['elements'] = [
                {'textRun': {**e['textRun'], 'content': c}}
                for e in b['paragraph']['elements']
                for c in e['textRun']['content']
            ]
        self.assertEqual(gs.accepted_markdown(original), before)

    def test_partial_response_even_with_complete_readback_stays_unverified(self):
        saved = self.plan()
        write = self.client.native_review_update

        def partial(*args):
            write(*args)
            return {'commentUpdateState': 'ALL_FAILED_UNKNOWN_REASON'}

        self.client.native_review_update = partial
        self.assertEqual(gs.apply(self.client, self.root, saved)['status'], 'needs-reconciliation')
        self.assertEqual(self.client.writes, 1)

    def test_markdown_style_boundaries_preserve_whitespace_outside_delimiters(self):
        doc = self.client.native_read('fixture-doc')
        p = doc['tabs'][0]['documentTab']['body']['content'][1]['paragraph']
        p['elements'] = [{'textRun': {'content': '  Bold space \n', 'textStyle': {'bold': True}}}]
        self.assertTrue(gs.accepted_markdown(doc).decode().startswith('##   **Bold space** \n'))
        p['elements'][0]['textRun']['content'] = 'Line one\nLine two\n'
        with self.assertRaises(gd.GoogleError):
            gs.accepted_markdown(doc)

    def test_renderer_keeps_meaningful_styles_and_escapes_only_ambiguous_text(self):
        link = {'link': {'url': 'https://example.invalid/a_b'}, 'underline': True}
        mono = {'weightedFontFamily': {'fontFamily': 'Roboto Mono'}}
        doc = paragraph_doc(
            ([('Launch notes\n', {})], {'namedStyleType': 'TITLE'}, None),
            ([('For the field team\n', {})], {'namedStyleType': 'SUBTITLE'}, None),
            (
                [
                    ('Keep ', {}),
                    ('removed claim', {'strikethrough': True}),
                    (' and ', {}),
                    ('stress', {'underline': True}),
                    (', x', {}),
                    ('2', {'baselineOffset': 'SUPERSCRIPT'}),
                    (', H', {}),
                    ('2', {'baselineOffset': 'SUBSCRIPT'}),
                    ('O, ', {}),
                    ('run()', mono),
                    (' and ', {}),
                    ('our site', link),
                    ('.\n', {'fontSize': {'magnitude': 14, 'unit': 'PT'}}),
                ],
                {},
                None,
            ),
            ([("Wow! It's #1 in snake_case, C# and a > b. See [1] & more.\n", {})], {}, None),
        )
        self.assertEqual(
            gs.accepted_markdown(doc).decode(),
            '# Launch notes\n\n## For the field team\n\n'
            'Keep ~~removed claim~~ and <u>stress</u>, x<sup>2</sup>, H<sub>2</sub>O, `run()` and '
            '[our site](<https://example.invalid/a_b>).\n\n'
            "Wow! It's #1 in snake_case, C# and a > b. See [1] & more.\n",
        )
        ambiguous = paragraph_doc(
            (
                [
                    (
                        '*not emphasis* and _nor this_ but [a](b) and <b>tag</b> and ~~kept~~ and `tick` and &amp;\n',
                        {},
                    )
                ],
                {},
                None,
            ),
            ([('# not a heading\n', {})], {}, None),
            ([('1. not a list\n', {})], {}, None),
            ([('- not a bullet\n', {})], {}, None),
            ([('> not a quote\n', {})], {}, None),
            ([('---\n', {})], {}, None),
        )
        self.assertEqual(
            gs.accepted_markdown(ambiguous).decode(),
            '\\*not emphasis\\* and \\_nor this\\_ but [a\\](b) and \\<b>tag\\</b> and \\~\\~kept\\~\\~ and \\`tick\\` and \\&amp;\n\n'
            '\\# not a heading\n\n1\\. not a list\n\n\\- not a bullet\n\n\\> not a quote\n\n\\---\n',
        )

    def test_renderer_numbers_ordered_lists_and_fails_closed_on_unsupported_links(self):
        lists = {
            'steps': {
                'listProperties': {
                    'nestingLevels': [
                        {'glyphType': 'DECIMAL', 'startNumber': 3},
                        {'glyphType': 'ALPHA'},
                    ]
                }
            },
            'dots': {
                'listProperties': {'nestingLevels': [{'glyphSymbol': '●'}, {'glyphSymbol': '○'}]}
            },
        }
        item = lambda text, name, level=0: (
            [(text + '\n', {})],
            {},
            {'listId': name, 'nestingLevel': level},
        )
        doc = paragraph_doc(
            item('First', 'steps'),
            item('Detail', 'steps', 1),
            item('More detail', 'steps', 1),
            item('Second', 'steps'),
            item('Detail again', 'steps', 1),
            item('Point', 'dots'),
            item('Sub point', 'dots', 1),
            lists=lists,
        )
        self.assertEqual(
            gs.accepted_markdown(doc).decode(),
            '3. First\n\n   1. Detail\n\n   2. More detail\n\n4. Second\n\n   1. Detail again\n\n- Point\n\n  - Sub point\n',
        )
        rule = paragraph_doc(
            ([('Above\n', {})], {}, None), ([('\n', {})], {}, None), ([('Below\n', {})], {}, None)
        )
        rule['tabs'][0]['documentTab']['body']['content'][2]['paragraph']['elements'].insert(
            0, {'horizontalRule': {}}
        )
        self.assertEqual(gs.accepted_markdown(rule).decode(), 'Above\n\n---\n\nBelow\n')
        internal = paragraph_doc(
            ([('See heading', {'link': {'headingId': 'h.1'}}), ('\n', {})], {}, None)
        )
        with self.assertRaisesRegex(gd.GoogleError, 'unsupported link'):
            gs.accepted_markdown(internal)

    def test_same_accepted_text_renders_identically_with_or_without_pending_review(self):
        plain = self.root / 'plain'
        rt.capture(self.client, 'fixture-doc', None, plain)
        before = json.loads((plain / 'observation.json').read_text())
        self.assertEqual(before['projection'], rt.PROJECTION)
        self.assertEqual(before['suggestions'], 'none')
        self.assertNotIn('accepted.json', [p.name for p in plain.iterdir()])
        self.client.export = Mock(wraps=self.client.export)
        saved = self.plan()
        gs.apply(self.client, self.root, saved)
        # Suggestions are now pending. The capture needs no flag, and the accepted text reads exactly as before.
        pending = self.root / 'pending'
        result = rt.capture(self.client, 'fixture-doc', None, pending)
        after = json.loads((pending / 'observation.json').read_text())
        self.assertEqual(
            (pending / 'document.md').read_bytes(), (plain / 'document.md').read_bytes()
        )
        self.assertEqual(after['content_sha256'], before['content_sha256'])
        self.assertEqual(after['format_sha256'], before['format_sha256'])
        self.assertEqual(after['suggestions'], 'excluded')
        self.assertEqual(result['summary']['review_threads'], 'threads')
        self.assertGreater(result['summary']['pending_suggestions'], 0)
        self.assertEqual([call.args[1] for call in self.client.export.call_args_list], ['docx'])

    def test_unsupported_structure_uses_google_export_only_when_nothing_is_pending(self):
        blocks = self.client.doc['tabs'][0]['documentTab']['body']['content']
        blocks.append(
            {
                'startIndex': blocks[-1]['endIndex'],
                'endIndex': blocks[-1]['endIndex'] + 4,
                'table': {'rows': 1},
            }
        )
        out = self.root / 'table'
        result = rt.capture(self.client, 'fixture-doc', 't.0', out)
        obs = json.loads((out / 'observation.json').read_text())
        self.assertEqual(obs['projection'], rt.EXPORT_PROJECTION)
        self.assertEqual(result['summary']['structure']['tables'], 1)
        self.assertEqual(
            (out / 'document.md').read_bytes(), self.client.export('fixture-doc', 'md')
        )
        self.assertIn(
            'document.md', gw.formatted_snapshot(out, obs, (out / 'document.md').read_text())
        )
        add_teammate_suggestion(self.client)
        with self.assertRaisesRegex(gd.GoogleError, 'Suggestions are pending'):
            rt.capture(self.client, 'fixture-doc', 't.0', self.root / 'table-pending')
        self.assertFalse((self.root / 'table-pending').exists())

    def test_capture_and_status_need_no_comment_readback_for_a_teammates_suggestion(self):
        from test_google_review_comments import CommentProvider

        client = CommentProvider()  # Native review threads are unavailable for this account.
        add_teammate_suggestion(client)
        out = self.root / 'teammate'
        result = rt.capture(client, 'fixture-doc', None, out)
        obs = json.loads((out / 'observation.json').read_text())
        body = (out / 'document.md').read_text()
        self.assertNotIn('very', body)
        self.assertIn('isn’t slow', body)
        self.assertEqual(
            obs['review_state'],
            {'pending': 1, 'accepted': 0, 'rejected': 0, 'unresolved_comments': 0},
        )
        self.assertEqual(result['summary']['review_threads'], 'markers')
        self.assertEqual(
            obs['format_sha256'],
            self.record['google']['baselines']['draft']['document']['format_sha256'],
        )
        self.assertIn('accepted.json', gw.formatted_snapshot(out, obs, body))
        self.assertIn('teammate-1', json.dumps(client.doc))
        with patch('google_drive.Client', return_value=client):
            status = gw.sync_status(self.root, self.directory, self.record, online=True)
        self.assertEqual(status['status'], 'pending-review')
        self.assertEqual(status['review_state']['pending'], 1)

    def test_fingerprint_ignores_titles_and_older_baselines_still_compare_equal(self):
        doc = self.client.native_read('fixture-doc', inline=True)
        renamed = copy.deepcopy(doc)
        renamed['title'] = 'Renamed'
        renamed['tabs'][0]['tabProperties']['title'] = 'Renamed tab'
        self.assertEqual(rt.fingerprint(doc), rt.fingerprint(renamed))
        self.assertNotEqual(rt.fingerprint(doc, 1), rt.fingerprint(renamed, 1))
        restyled = copy.deepcopy(doc)
        restyled['tabs'][0]['documentTab']['body']['content'][1]['paragraph']['paragraphStyle'][
            'lineSpacing'
        ] = 200
        self.assertNotEqual(rt.fingerprint(doc), rt.fingerprint(restyled))
        with self.assertRaisesRegex(gd.GoogleError, 'newer'):
            rt.fingerprint(doc, 3)
        # A baseline saved before the upgrade has no version and used the older calculation.
        legacy = self.record['google']['baselines']['draft']['document']
        legacy.pop('format_version')
        legacy['format_sha256'] = gd.digest(gd.encoded(rt.semantic(doc)))
        studio.persist(self.directory, 'articles', self.record)
        with patch('google_drive.Client', return_value=self.client):
            self.assertEqual(
                gw.sync_status(self.root, self.directory, self.record, online=True)['status'],
                'in-sync',
            )
        self.assertEqual(self.plan()['mode'], 'auto')
        out = self.root / 'legacy'
        rt.capture(self.client, 'fixture-doc', None, out)
        obs = gw.observation(
            json.loads((out / 'observation.json').read_text()), (out / 'document.md').read_text()
        )
        self.assertEqual(
            gw.format_pair(legacy, obs), (legacy['format_sha256'], obs['legacy_format_sha256'])
        )
        self.assertEqual(obs['legacy_format_sha256'], legacy['format_sha256'])
        current = {'format_sha256': obs['format_sha256'], 'format_version': 2}
        self.assertEqual(gw.format_pair(current, obs), (obs['format_sha256'], obs['format_sha256']))

    def test_online_status_distinguishes_pending_review_from_in_sync(self):
        saved = self.plan()
        gs.apply(self.client, self.root, saved)
        with patch('google_drive.Client', return_value=self.client):
            result = gw.sync_status(self.root, self.directory, self.record, online=True)
        self.assertEqual(result['status'], 'pending-review')
        self.assertGreater(result['review_state']['pending'], 0)

    def test_provider_contract_uses_suggest_and_required_revision(self):
        client = gd.Client.__new__(gd.Client)
        client.request = Mock(return_value={})
        client.native_review_update('fixture-doc', 'r1', [{'insertComment': {}}])
        self.assertEqual(
            client.request.call_args.kwargs['body']['writeControl'],
            {'requiredRevisionId': 'r1', 'writeMode': 'SUGGEST'},
        )
        client.native_read('fixture-doc', inline=True, comments=True)
        self.assertIn(
            'commentsViewMode=COMMENTS_VIEW_MODE_INCLUDED', client.request.call_args.args[0]
        )
        self.assertIn('includeTabsContent=true', client.request.call_args.args[0])

    def test_short_command_routes_only_explicit_suggestions(self):
        route = author_workflow.route(
            self.root, 'Push these as suggestions to Google Docs', self.aid
        )
        self.assertEqual(route['actions'], ['google-suggest'])
        self.assertEqual(
            author_workflow.route(self.root, 'Push to Google Docs', self.aid)['actions'],
            ['google-push'],
        )


if __name__ == '__main__':
    unittest.main()
