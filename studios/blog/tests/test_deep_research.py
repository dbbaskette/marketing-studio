"""Research plans, automatic reports and exact evidence; no live searches or accounts."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from hub_fixtures import SCRIPTS, FakeProvider
from hub import Registry
from hub_workspace import Workspace
import studio
import deep_research as research
import author_workflow


class DeepResearchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve();self.root = self.base / 'workspace';studio.initialize(self.root)
        self.ident = self.article(self.root);self.directory = self.root / 'articles' / self.ident
        self.draft = 'ExampleDB 2.0 supports predicate pruning. Performance depends on the workload.'
        self.save_draft(self.root, self.ident, self.draft)

    def cli(self, root, *words):
        result = subprocess.run([sys.executable, str(SCRIPTS / 'studio.py'), '--root', str(root), *words], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr);return json.loads(result.stdout)

    def article(self, root, policy='web-allowed', mode='first-draft'):
        return self.cli(root, 'article', 'create', '--title', 'Synthetic blog', '--mode', mode, '--research', policy)['id']

    def file(self, name, value):
        p = self.base / name;p.write_text(json.dumps(value) if not isinstance(value, str) else value);return str(p)

    def save_draft(self, root, ident, text):
        return self.cli(root, 'article', 'save', '--id', ident, '--kind', 'draft', '--file', self.file('draft.md', text))

    def plan(self, ident=None, scope='public-web', purpose='fact-check'):
        items = [{'id': 'availability', 'question': 'Verify predicate pruning availability.',
                  'public_query': 'ExampleDB 2.0 predicate pruning release notes' if scope == 'public-web' else None,
                  'claim': {'quote': 'ExampleDB 2.0 supports predicate pruning.', 'start': 0} if purpose == 'fact-check' else None}]
        self.cli(self.root, 'research', 'plan', '--id', ident or self.ident,
                 '--file', self.file('plan.json', {'purpose': purpose, 'scope': scope, 'items': items}))
        return research.status(self.root, ident or self.ident)['run']

    def source(self, role='reference', text='Release 2.0 adds predicate pruning to column scans.', origin='https://example.org/release-2.0'):
        src = self.cli(self.root, 'source', 'add', '--name', 'Synthetic release notes', '--origin', origin,
                       '--text-file', self.file('source.md', text), '--purpose', role)
        self.cli(self.root, 'article', 'attach', '--id', self.ident, '--source', src['id'], '--purpose', role)
        return src, text

    def result(self, run, citations=None, status='supported'):
        return research.record_result(self.root, self.ident, run, 'availability',
                  {'status': status, 'summary': 'The inspected release notes establish the selected capability.',
                   'limits': 'This establishes capability, not a particular speedup.', 'evidence': citations or []})

    def cite(self, src, text):
        return {'source_id': src['id'], 'revision': src['revision'], 'quote': text, 'start': 0, 'locator': 'Release 2.0 notes'}

    def test_complete_report_is_automatic_sources_retained_and_review_separate(self):
        run = self.plan();src, text = self.source();self.result(run, [self.cite(src, text)])
        value = research.status(self.root, self.ident);self.assertEqual(value['status'], 'complete')
        report = Path(value['report']).read_text();self.assertIn('https://example.org/release-2.0', report)
        self.assertIn(text, report);self.assertIn('not a particular speedup', report)
        self.assertEqual((self.directory / 'DRAFT.md').read_text(), self.draft)
        self.assertEqual(self.cli(self.root, 'article', 'show', '--id', self.ident)['reviews']['factual-support']['status'], 'not-run')
        self.assertTrue((self.root / 'sources' / src['id'] / 'content.md').exists())
        self.assertEqual(self.plan(), run);self.assertEqual(research.status(self.root, self.ident)['completed'], 1)

    def test_planning_needs_no_draft_and_unresolved_items_stay_in_report(self):
        ident = self.article(self.root, mode='outline-only');run = self.plan(ident, scope='supplied-only', purpose='planning')
        research.record_result(self.root, ident, run, 'availability', {'status': 'unavailable', 'summary': 'No readable sources.',
                               'limits': 'Browsing unavailable.', 'evidence': []})
        value = research.status(self.root, ident);self.assertEqual(value['unresolved'], ['availability'])
        self.assertIn('unavailable', Path(value['report']).read_text());self.assertFalse((self.root / 'articles' / ident / 'DRAFT.md').exists())

    def test_claim_spans_policy_evidence_roles_and_missing_passages_are_enforced(self):
        restricted = self.article(self.root, policy='supplied-only')
        with self.assertRaisesRegex(ValueError, 'limited to supplied'):
            research.plan(self.root, restricted, {'purpose': 'planning', 'scope': 'public-web', 'items': []})
        run = self.plan()
        with self.assertRaisesRegex(ValueError, 'traceable passage'):self.result(run)
        src, text = self.source(role='inspiration')
        with self.assertRaisesRegex(ValueError, 'factual reference'):self.result(run, [self.cite(src, text)])
        src, text = self.source();citation = self.cite(src, text);citation['quote'] = 'Invented support.'
        with self.assertRaisesRegex(ValueError, 'exactly'):self.result(run, [citation])
        with self.assertRaisesRegex(ValueError, 'does not match'):
            research.plan(self.root, self.ident, {'purpose': 'fact-check', 'scope': 'supplied-only',
                'items': [{'id': 'bad', 'question': 'Verify.', 'public_query': None, 'claim': {'quote': 'Invented claim.', 'start': 0}}]})
        with self.assertRaisesRegex(ValueError, 'URLs'):
            research.plan(self.root, self.ident, {'purpose': 'planning', 'scope': 'public-web',
                'items': [{'id': 'bad', 'question': 'Verify.', 'public_query': 'https://internal.example/private', 'claim': None}]})
        self.assertEqual(research.status(self.root, self.ident)['pending'], ['availability'])

    def test_uploaded_source_document_supplied_only_research_retains_and_cites_original(self):
        self.cli(self.root, 'article', 'research-policy', '--id', self.ident, '--policy', 'supplied-only')
        text = 'Internal test document: ExampleDB 2.0 supports predicate pruning.'
        uploaded = self.file('Uploaded product notes.md', text)
        src = self.cli(self.root, 'source', 'add', '--name', 'Uploaded product notes', '--file', uploaded, '--purpose', 'reference')
        self.cli(self.root, 'article', 'attach', '--id', self.ident, '--source', src['id'], '--purpose', 'reference')
        run = self.plan(scope='supplied-only');self.result(run, [self.cite(src, text)])
        value = research.status(self.root, self.ident);self.assertEqual(value['status'], 'complete')
        report = Path(value['report']).read_text();self.assertIn('Uploaded product notes', report);self.assertIn(text, report)
        self.assertEqual((self.root / 'sources' / src['id'] / src['original_path']).read_text(), text)
        plan = studio.read_json(Path(value['file']));self.assertIsNone(plan['items'][0]['public_query'])
        self.assertEqual(plan['scope'], 'supplied-only');self.assertEqual((self.directory / 'DRAFT.md').read_text(), self.draft)

    def test_source_scope_can_be_changed_explicitly_and_reports_escape_embeds(self):
        self.cli(self.root, 'article', 'research-policy', '--id', self.ident, '--policy', 'supplied-only')
        with self.assertRaisesRegex(ValueError, 'limited to supplied'):
            research.plan(self.root, self.ident, {'purpose': 'planning', 'scope': 'public-web', 'items': []})
        self.cli(self.root, 'article', 'research-policy', '--id', self.ident, '--policy', 'web-allowed')
        run = self.plan();src, text = self.source(text='Evidence ![tracking](https://example.org/image) <script>bad</script>',
                                                origin='Notes ![tracking](https://example.org/image) <script>bad</script>')
        self.result(run, [self.cite(src, text)])
        report = Path(research.status(self.root, self.ident)['report']).read_text()
        self.assertNotIn('![tracking]', report);self.assertNotIn('<script>', report)
        self.assertEqual(studio.read_json(self.directory / 'derived/research.json')['results']['availability']['evidence'][0]['quote'], text)

    def test_uploaded_plus_external_research_cites_both_sources_and_retains_choice(self):
        text = 'Uploaded notes describe predicate pruning in ExampleDB 2.0.'
        src = self.cli(self.root, 'source', 'add', '--name', 'Uploaded specification',
                       '--file', self.file('specification.md', text), '--purpose', 'reference')
        self.cli(self.root, 'article', 'attach', '--id', self.ident, '--source', src['id'], '--purpose', 'reference')
        public, public_text = self.source()
        run = self.plan();self.result(run, [self.cite(src, text), self.cite(public, public_text)])
        value = research.status(self.root, self.ident);report = Path(value['report']).read_text()
        self.assertEqual(value['scope_label'], 'Uploaded sources plus external research')
        self.assertIn('Uploaded specification', report);self.assertIn('https://example.org/release-2.0', report)
        self.assertEqual(len(studio.read_json(Path(value['file']))['results']['availability']['evidence']), 2)
        self.assertEqual(author_workflow.route(self.root, 'Fact-check')['research_scope'], 'public-web')
        self.assertEqual((self.directory / 'DRAFT.md').read_text(), self.draft)

    def test_scope_choice_is_required_for_external_lookup_and_narrowing_stales_existing_run(self):
        undecided = self.article(self.root, policy='unspecified')
        route = author_workflow.route(self.root, 'Research this topic', article_id=undecided)
        self.assertEqual([c['label'] for c in route['research_scope_choices']],
                         ['Uploaded sources only', 'Uploaded sources plus external research'])
        with self.assertRaisesRegex(ValueError, 'before public lookup'):
            research.plan(self.root, undecided, {'purpose': 'planning', 'scope': 'public-web', 'items': []})
        self.cli(self.root, 'article', 'research-policy', '--id', undecided, '--policy', 'supplied-only')
        route = author_workflow.route(self.root, 'Fact-check', article_id=undecided)
        self.assertEqual(route['research_scope'], 'supplied-only');self.assertEqual(route['research_scope_choices'], [])
        run = self.plan();self.result(run, status='insufficient')
        self.cli(self.root, 'article', 'research-policy', '--id', self.ident, '--policy', 'supplied-only')
        self.assertEqual(research.status(self.root, self.ident)['status'], 'stale')
        with self.assertRaisesRegex(ValueError, 'now limited to supplied'):self.result(run, status='insufficient')
        self.assertNotEqual(self.plan(scope='supplied-only'), run)

    def test_changed_manuscript_and_changed_source_stale_results(self):
        run = self.plan();src, text = self.source();self.result(run, [self.cite(src, text)])
        self.cli(self.root, 'source', 'update', '--id', src['id'], '--text-file', self.file('updated.md', 'Release 2.1 behavior changed.'))
        self.assertEqual(research.status(self.root, self.ident)['status'], 'stale')
        self.save_draft(self.root, self.ident, self.draft + ' New claim.')
        with self.assertRaisesRegex(ValueError, 'stale'):self.result(run, status='insufficient')
        new = self.plan();self.assertNotEqual(new, run)
        self.assertTrue(list((self.directory / 'history').glob('editorial-research-*.json')))

    def test_short_routes_select_research_fact_check_and_do_not_expand_proofreading(self):
        self.assertEqual(author_workflow.route(self.root, 'Research this topic')['actions'], ['deep-research'])
        self.assertEqual(author_workflow.route(self.root, 'Fact-check')['actions'], ['research-evidence', 'factual-support'])
        self.assertEqual(author_workflow.route(self.root, 'Show research')['actions'], ['research-status'])
        self.assertEqual(author_workflow.route(self.root, 'Proofread')['actions'], ['proofread'])
        local = author_workflow.route(self.root, 'Research uploaded sources only')
        self.assertEqual(local['actions'], ['research-policy-supplied-only', 'deep-research'])
        self.assertEqual(local['research_scope'], 'supplied-only')
        external = author_workflow.route(self.root, 'Research uploaded sources plus external research')
        self.assertEqual(external['actions'], ['research-policy-web-allowed', 'deep-research'])
        self.assertEqual(external['research_scope'], 'public-web')

    def test_synthetic_hub_offline_queue_cross_clone_resumes_report_and_sources(self):
        run = self.plan();src, text = self.source();self.result(run, [self.cite(src, text)])
        provider = FakeProvider(self.base / 'remotes');ra = Registry(self.base / 'registry-a', provider)
        shared = ra.create('fixture/research-hub', 'Research Hub')['hub'];ha = ra.hub(shared)
        wa = Workspace(self.root, ha)
        self.assertEqual(wa.publish_selected({'articles': [self.ident]}, offline=True)['status'], 'queued-offline')
        exported = wa.publish_selected({'articles': [self.ident]})['items'][0]
        rb = Registry(self.base / 'registry-b', provider);rb.join('fixture/research-hub')
        other = self.base / 'other';studio.initialize(other);wb = Workspace(other, rb.hub(shared))
        ident = wb.checkout_selected({'articles': [exported['item']]})['items'][0]['local_id']
        status = research.status(other, ident);self.assertEqual(status['status'], 'complete')
        self.assertIn(text, Path(status['report']).read_text());self.assertEqual(status['run'], run)
        self.assertEqual(status['pending'], []);self.assertEqual(status['completed'], 1)


if __name__ == '__main__':unittest.main()
