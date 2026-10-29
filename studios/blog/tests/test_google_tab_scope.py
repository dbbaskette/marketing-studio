"""Selected Google tabs through intake, local editing and native/comment delivery."""

import isolation  # noqa: F401
import copy
import unittest

import test_google_intake as intake_tests
from test_google_suggestions import ReviewProvider
import google_drive as drive
import google_intake
import google_reconcile
import google_roundtrip as rt
import google_suggestions as gs
import google_workflow as workflow
import manuscript_editor
import studio


class TabsProvider(ReviewProvider):
    def __init__(self):
        super().__init__()
        target = copy.deepcopy(self.doc['tabs'][0])
        target['tabProperties'] = {'tabId': 't.focus', 'title': 'Blog draft'}
        other = copy.deepcopy(target)
        other['tabProperties'] = {'tabId': 't.other', 'title': 'Private notes'}
        other['documentTab']['body']['content'][1]['paragraph']['elements'][0]['textRun'][
            'content'
        ] = 'Keep delay in PRIVATE OTHER TAB.\n'
        target['childTabs'] = [copy.deepcopy(other)]
        target['childTabs'][0]['tabProperties'] = {'tabId': 't.child', 'title': 'Nested notes'}
        self.doc['tabs'] = [other, target]
        self.export_calls = []
        self.requests = []
        self.native_available = True
        self.drive_threads = []

    def export(self, file_id, format):
        self.export_calls.append(format)
        raise AssertionError('A tab-only snapshot must never export the whole Doc.')

    def native_read(self, file_id, inline=False, comments=False, accepted_preview=False):
        if comments and not self.native_available:
            raise drive.ReviewUnavailable('No native review surface')

        def project(tab):
            helper = ReviewProvider()
            helper.doc = {
                **self.doc,
                'tabs': [{k: copy.deepcopy(v) for k, v in tab.items() if k != 'childTabs'}],
            }
            helper.comments, helper.threads = self.comments, self.threads
            helper.anchors = [
                a
                for a in self.anchors
                if all(r['tabId'] == tab['tabProperties']['tabId'] for r in a['ranges'])
            ]
            found = ReviewProvider.native_read(helper, file_id, inline, comments, accepted_preview)
            result = found['tabs'][0]
            if tab.get('childTabs'):
                result['childTabs'] = [project(child) for child in tab['childTabs']]
            return result

        result = ReviewProvider.native_read(self, file_id, inline, comments, accepted_preview)
        result['tabs'] = [project(tab) for tab in self.doc['tabs']]
        return result

    def native_review_update(self, file_id, revision, requests):
        chosen = set()
        for request in requests:
            value = next(iter(request.values()))
            chosen.add((value.get('range') or value.get('location'))['tabId'])
        assert len(chosen) == 1
        ident = chosen.pop()
        full = self.doc
        tab = next(t for t in rt.tabs(full) if t['tabProperties']['tabId'] == ident)
        self.doc = {**full, 'tabs': [{k: v for k, v in tab.items() if k != 'childTabs'}]}
        try:
            answer = ReviewProvider.native_review_update(self, file_id, revision, requests)
            tab['documentTab'] = self.doc['tabs'][0]['documentTab']
            full['revisionId'] = self.doc['revisionId']
            self.requests.extend(copy.deepcopy(requests))
            return answer
        finally:
            self.doc = full

    def metadata(self, file_id):
        return {'version': self.version, 'capabilities': {'canComment': True}}

    def review_comments(self, file_id):
        return copy.deepcopy(self.drive_threads)

    def create_review_comment(self, file_id, content, quote):
        found = {
            'id': 'comment' + str(len(self.drive_threads)),
            'content': content,
            'quotedFileContent': {'value': quote},
            'resolved': False,
            'author': {'me': True},
        }
        self.drive_threads.append(found)
        return copy.deepcopy(found)


class GoogleTabScopeTests(unittest.TestCase):
    start = intake_tests.GoogleIntakeTests.start
    snapshot = intake_tests.GoogleIntakeTests.snapshot

    def setUp(self):
        intake_tests.GoogleIntakeTests.setUp(self)
        self.client = TabsProvider()
        self.factory.return_value = self.client

    def preview(self, tab='t.focus'):
        return google_intake.preview(
            self.root,
            {
                'url': 'https://docs.google.com/document/d/fixture-doc'
                + ('?tab=' + tab if tab is not None else '')
            },
        )

    def test_selected_tab_is_imported_without_other_tabs_or_document_exports(self):
        found = self.preview()
        self.assertEqual(found['summary']['selected_tab'], {'id': 't.focus', 'title': 'Blog draft'})
        folder = self.snapshot(found)
        self.assertEqual(studio.read_json(folder / 'snapshot.json')['schema'], 4)
        self.assertFalse((folder / 'document.docx').exists())
        for path in folder.iterdir():
            self.assertNotIn('PRIVATE OTHER TAB', path.read_text())
            self.assertNotIn('t.child', path.read_text())
        result = self.start(found)
        directory, record = studio.item(self.root, 'articles', result['id'])
        baseline = record['google']['baselines']['draft']['document']
        self.assertEqual(baseline['tab_ids'], ['t.focus'])
        self.assertTrue(baseline['url'].endswith('?tab=t.focus'))
        self.assertEqual(
            (directory / 'ORIGINAL.md').read_bytes(), (directory / 'DRAFT.md').read_bytes()
        )
        self.assertEqual(self.client.export_calls, [])
        self.assertEqual(self.client.writes, 0)

    def test_missing_ambiguous_and_unselected_tab_links_save_nothing(self):
        for tab in (None, 't.missing'):
            with self.assertRaises(drive.GoogleError):
                self.preview(tab)
        self.client.doc['tabs'].append(copy.deepcopy(self.client.doc['tabs'][1]))
        with self.assertRaisesRegex(drive.GoogleError, 'ambiguous'):
            self.preview()
        self.assertEqual(list((self.root / 'articles').iterdir()), [])
        self.assertEqual(self.client.export_calls, [])

    def test_nested_tab_is_isolated_without_parent_or_siblings(self):
        found = self.preview('t.child')
        native = studio.read_json(self.snapshot(found) / 'native.json')
        self.assertEqual([t['tabProperties']['tabId'] for t in rt.tabs(native)], ['t.child'])
        self.assertNotIn('childTabs', native['tabs'][0])

    def test_an_invalid_reference_tab_never_falls_back_to_all_tabs(self):
        for tail in ('?tab=', '?tab=t.focus&tab=t.other', '?tab=bad/identity'):
            with self.assertRaisesRegex(ValueError, 'invalid or ambiguous'):
                google_intake.material(
                    self.root, 'https://docs.google.com/document/d/fixture-doc' + tail
                )
        self.assertEqual(self.client.export_calls, [])

    def test_reference_material_reads_all_tabs_unless_the_link_names_one(self):
        url = 'https://docs.google.com/document/d/fixture-doc'
        whole = google_intake.material(self.root, url)
        self.assertEqual(whole['tabs']['read'], ['Private notes', 'Blog draft', 'Nested notes'])
        self.assertIn('PRIVATE OTHER TAB', whole['text'])
        selected = google_intake.material(self.root, url + '?tab=t.focus')
        self.assertEqual(selected['tabs']['read'], ['Blog draft'])
        self.assertNotIn('PRIVATE OTHER TAB', selected['text'])

    def test_another_tab_cannot_retarget_a_linked_blog_and_reopening_keeps_edits(self):
        one = self.start(self.preview())
        directory, record = studio.item(self.root, 'articles', one['id'])
        studio.save_artifact(directory, 'draft', 'Keep local unsent edits.', record)
        studio.persist(directory, 'articles', record)
        with self.assertRaisesRegex(ValueError, 'different tabs'):
            self.start(self.preview('t.child'))
        self.assertEqual(self.preview()['id'], one['id'])
        self.assertEqual((directory / 'DRAFT.md').read_text(), 'Keep local unsent edits.')

    def test_suggestions_only_target_the_selected_nonfirst_tab(self):
        imported = self.start(self.preview())
        untouched = copy.deepcopy(self.client.doc['tabs'][0])
        nested = copy.deepcopy(self.client.doc['tabs'][1]['childTabs'])
        path = self.base / 'plan.json'
        gs.plan(
            self.client,
            self.root,
            imported['id'],
            'draft',
            [
                {
                    'id': 'synthetic-edit',
                    'kind': 'edit',
                    'before': 'delay',
                    'after': 'wait',
                    'reason': 'Plainer wording.',
                }
            ],
            path,
        )
        saved = studio.read_json(path)
        self.assertEqual(saved['tab_ids'], ['t.focus'])
        self.assertEqual(gs.apply(self.client, self.root, saved)['status'], 'verified-pending')
        for request in self.client.requests:
            value = next(iter(request.values()))
            self.assertEqual((value.get('range') or value.get('location'))['tabId'], 't.focus')
        self.assertEqual(self.client.doc['tabs'][0], untouched)
        self.assertEqual(self.client.doc['tabs'][1]['childTabs'], nested)

    def test_drive_comments_fallback_keeps_other_tabs_and_accepted_text(self):
        self.client.native_available = False
        imported = self.start(self.preview())
        before = gs.signature(self.client.doc)
        path = self.base / 'comments.json'
        gs.plan(
            self.client,
            self.root,
            imported['id'],
            'draft',
            [
                {
                    'id': 'synthetic-comment',
                    'kind': 'edit',
                    'before': 'delay',
                    'after': 'wait',
                    'reason': 'Plainer wording.',
                }
            ],
            path,
        )
        result = gs.apply(self.client, self.root, studio.read_json(path))
        self.assertEqual(result['status'], 'verified-comments')
        self.assertEqual(gs.signature(self.client.doc), before)
        self.assertEqual(self.client.writes, 0)
        self.assertEqual(len(self.client.drive_threads), 1)
        self.assertIn('Blog draft', self.client.drive_threads[0]['content'])
        self.assertNotIn('PRIVATE OTHER TAB', self.client.drive_threads[0]['content'])

    def test_online_status_and_reconcile_keep_the_selected_scope(self):
        imported = self.start(self.preview())
        directory, record = studio.item(self.root, 'articles', imported['id'])
        self.assertEqual(
            workflow.sync_status(self.root, directory, record, online=True)['status'], 'in-sync'
        )
        self.client.doc['tabs'][0]['tabProperties']['title'] = 'Other tab renamed'
        self.client.doc['revisionId'] = 'r9'
        self.client.version = '9'
        self.assertEqual(
            workflow.sync_status(self.root, directory, record, online=True)['status'], 'in-sync'
        )
        current = manuscript_editor.read(self.root, imported['id'])
        found = google_reconcile.preview(
            self.root, {'id': imported['id'], 'expected': current['expected']}
        )
        self.assertNotIn('PRIVATE OTHER TAB', found['remote'])
        self.assertEqual(found['summary']['selected_tab']['id'], 't.focus')
        with studio.locked(self.root):
            accepted = google_reconcile.accept(
                self.root,
                {
                    'id': imported['id'],
                    'expected': current['expected'],
                    'preview': found['preview'],
                    'comparison': found['comparison'],
                    'confirmed': True,
                },
            )
        self.assertEqual(accepted['status'], 'accepted')
        self.assertNotIn('document.docx', accepted['formatted_snapshot'])
        _, record = studio.item(self.root, 'articles', imported['id'])
        self.assertEqual(record['google']['baselines']['draft']['document']['tab_ids'], ['t.focus'])
        self.assertEqual(self.client.export_calls, [])
