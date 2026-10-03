"""Existing-Doc intake, retained formatting and original-target review; no live Google."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'skills/blog-studio/scripts'))
import studio
import google_workflow as gw
import google_roundtrip as rt
import google_suggestions as gs
import author_workflow as aw
import test_google_suggestions as fixtures


class GoogleStartTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base/'workspace'; studio.initialize(self.root)
        self.client = fixtures.ReviewProvider()
        self.capture = self.base/'capture'
        rt.capture(self.client, 'fixture-doc', 't.0', self.capture)
        self.observation = self.capture/'observation.json'
        obs = json.loads(self.observation.read_text()); obs['structure_verified'] = True
        self.observation.write_text(json.dumps(obs))
        self.words = ['--root', str(self.root), 'google', 'start', '--title', 'Imported blog',
            '--observation', str(self.observation), '--file', str(self.capture/'document.md'), '--snapshot', str(self.capture)]

    def start(self):
        with studio.locked(self.root):
            return gw.command(self.root, studio.parser().parse_args(self.words))

    def test_import_preserves_original_formatted_snapshot_and_baseline_without_google_write(self):
        with patch.object(subprocess, 'run', side_effect=AssertionError('No provider calls during local adoption')):
            result = self.start()
        directory, record = studio.item(self.root, 'articles', result['id'])
        body = (self.capture/'document.md').read_bytes()
        self.assertEqual((directory/'ORIGINAL.md').read_bytes(), body)
        self.assertEqual((directory/'DRAFT.md').read_bytes(), body)
        self.assertEqual(record['mode'], 'existing'); self.assertEqual(record['voice']['mode'], 'preserve')
        self.assertEqual(record['stop_point'], 'review')
        base = record['google']['baselines']['draft']
        self.assertEqual(base['document']['document_id'], 'fixture-doc')
        self.assertEqual(base['document']['tab_ids'], ['t.0'])
        self.assertEqual(base['document']['format_sha256'], gs.signature(self.client.doc))
        transfer = record['google']['transfers'][base['transfer']]
        self.assertEqual(transfer['direction'], 'from-google')
        for name, relative in transfer['formatted_snapshot'].items():
            self.assertEqual((directory/relative).read_bytes(), (self.capture/name).read_bytes())
        self.assertEqual(studio.read_json(self.root/'.active-article.json')['id'], result['id'])
        self.assertEqual(self.client.writes, 0)
        self.assertEqual(gw.compare(directory, record, 'draft', base['document'], body.decode())['status'], 'unchanged')

    def test_proofread_then_suggestions_target_the_imported_doc(self):
        result = self.start(); aid = result['id']
        self.assertEqual(aw.route(self.root, 'proofread')['id'], aid)
        routed = aw.route(self.root, 'Push as suggestions')
        self.assertEqual(routed['linked_document'], 'https://docs.google.com/document/d/fixture-doc/edit')
        findings = [dict(id='proof-1', kind='edit', tab_id='t.0', start_index=5,
            before='delay', after='wait', reason='Use plainer wording.')]
        output = self.base/'plan.json'
        gs.plan(self.client, self.root, aid, 'draft', findings, output)
        plan = json.loads(output.read_text())
        actual = self.client.native_review_update
        calls = []
        def write(doc, *args):
            calls.append(doc); return actual(doc, *args)
        self.client.native_review_update = write
        self.assertEqual(gs.apply(self.client, self.root, plan)['status'], 'verified-pending')
        self.assertEqual(calls, ['fixture-doc'])
        directory, _ = studio.item(self.root, 'articles', aid)
        self.assertEqual((directory/'ORIGINAL.md').read_bytes(), (directory/'DRAFT.md').read_bytes())

    def test_repeated_start_selects_existing_without_overwriting_draft_or_baseline(self):
        first = self.start(); directory, record = studio.item(self.root, 'articles', first['id'])
        baseline = copy.deepcopy(record['google'])
        studio.save_artifact(directory, 'draft', 'Local unsent edits.', record)
        studio.persist(directory, 'articles', record)
        again = self.start()
        self.assertEqual(again['status'], 'already-linked'); self.assertEqual(again['id'], first['id'])
        self.assertEqual(len(list((self.root/'articles').iterdir())), 1)
        self.assertEqual((directory/'DRAFT.md').read_text(), 'Local unsent edits.')
        self.assertEqual(studio.item(self.root, 'articles', first['id'])[1]['google'], baseline)

    def test_unverified_missing_revision_bad_identity_and_tampering_leave_no_article(self):
        original = json.loads(self.observation.read_text())
        for change in ({'structure_verified': False}, {'revision_id': None}, {'format_sha256': None},
                       {'url': 'https://docs.google.com/document/d/another/edit'}, {'content_sha256': 'a'*64}):
            self.observation.write_text(json.dumps({**original, **change}))
            with self.assertRaises(ValueError): self.start()
            self.assertEqual(list((self.root/'articles').iterdir()), [])
        self.observation.write_text(json.dumps(original))
        (self.capture/'document.docx').write_bytes(b'corrupt')
        with self.assertRaises(ValueError): self.start()
        self.assertFalse((self.root/'.active-article.json').exists())

    def test_interrupted_snapshot_save_does_not_publish_partial_article(self):
        with patch.object(gw, 'save_formatted_snapshot', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.start()
        self.assertEqual(list((self.root/'articles').iterdir()), [])
        self.assertEqual(list(self.root.glob('.google-start-*')), [])
        self.assertFalse((self.root/'.active-article.json').exists())
        self.assertEqual(self.start()['status'], 'started-from-google')

    def test_google_change_after_import_requires_refresh_before_suggestion_plan(self):
        aid = self.start()['id']
        self.client.doc['title'] = 'Changed in Google'
        findings = [dict(id='proof-1', kind='edit', tab_id='t.0', start_index=5,
            before='delay', after='wait', reason='Plainer wording.')]
        with self.assertRaisesRegex(Exception, 'Pull the latest'):
            gs.plan(self.client, self.root, aid, 'draft', findings, self.base/'plan.json')
        self.assertEqual(self.client.writes, 0)

    def test_pending_suggestions_import_only_accepted_manuscript(self):
        findings = [dict(id='pending-1', kind='edit', tab_id='t.0', start_index=5,
            before='delay', after='wait', reason='Plainer wording.')]
        built = gs.build(self.client.native_read('fixture-doc', inline=True, comments=True), findings, ['t.0'])
        self.client.native_review_update('fixture-doc', 'r1', built['requests'])
        self.capture = self.base/'review-capture'
        rt.capture(self.client, 'fixture-doc', 't.0', self.capture, include_review=True)
        self.observation = self.capture/'observation.json'
        obs = json.loads(self.observation.read_text()); obs['structure_verified'] = True
        self.observation.write_text(json.dumps(obs))
        self.words = ['--root', str(self.root), 'google', 'start', '--title', 'Pending',
            '--observation', str(self.observation), '--file', str(self.capture/'document.md'), '--snapshot', str(self.capture)]
        result = self.start(); directory, record = studio.item(self.root, 'articles', result['id'])
        self.assertIn('delay', (directory/'DRAFT.md').read_text())
        self.assertNotIn('wait', (directory/'DRAFT.md').read_text())
        self.assertEqual(record['google']['baselines']['draft']['document']['review_state']['pending'], len(self.client.threads))
        self.assertIn('accepted.json', result['formatted_snapshot'])

    def test_intake_routing_does_not_need_a_selected_article_and_preserves_url_case(self):
        url = 'https://docs.google.com/document/d/CaseSensitiveDoc/edit'
        for phrase in ('Start from this Google Doc', 'Start a blog from this Google Doc', 'Use this Google Doc as my draft'):
            route = aw.route(self.root, phrase+': '+url)
            self.assertEqual(route['actions'], ['google-start']); self.assertEqual(route['document_input'], url)
        self.assertEqual(aw.route(self.root, 'Start from this Google Doc')['actions'], ['google-start'])
        self.assertEqual(aw.route(self.root, 'Use this Google Doc as a source: '+url)['status'], 'interpret-request')

    def test_real_cli_import_and_resume_route(self):
        process = subprocess.run([sys.executable, studio.__file__, *self.words], capture_output=True, text=True)
        self.assertEqual(process.returncode, 0, process.stderr)
        aid = json.loads(process.stdout)['id']
        self.assertEqual(aw.route(self.root, 'Push to Google Docs')['id'], aid)
        self.assertEqual(aw.route(self.root, 'Pull from Google Docs')['linked_document'], 'https://docs.google.com/document/d/fixture-doc/edit')

    def test_imported_link_and_formatted_history_survive_team_hub_checkout(self):
        from hub_fixtures import FakeProvider
        from hub import Registry
        from hub_workspace import Workspace
        result = self.start()
        provider = FakeProvider(self.base/'remotes')
        registry = Registry(self.base/'hub-a', provider)
        hub_id = registry.create('fixture/import-hub', 'Import fixture')['hub']
        adapter = Workspace(self.root, registry.hub(hub_id))
        reference = adapter.publish_selected({'articles': [result['id']]})['items'][0]
        other_registry = Registry(self.base/'hub-b', provider); other_registry.join('fixture/import-hub')
        other = self.base/'other'; studio.initialize(other)
        reader = Workspace(other, other_registry.hub(hub_id))
        aid = reader.checkout_selected({'articles': [reference['item']]})['items'][0]['local_id']
        directory, record = studio.item(other, 'articles', aid)
        self.assertEqual(record['google']['baselines']['draft']['document']['document_id'], 'fixture-doc')
        self.assertEqual((directory/'ORIGINAL.md').read_bytes(), (self.capture/'document.md').read_bytes())
        for name, relative in result['formatted_snapshot'].items():
            self.assertEqual((directory/relative).read_bytes(), (self.capture/name).read_bytes())
