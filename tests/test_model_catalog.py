"""Read-only catalogs and authenticated setup choices, without real providers."""
import concurrent.futures
from email.message import Message
import json
from pathlib import Path
import sys
from unittest import mock

from test_home import IsolatedHome
from studio_core import model_catalog, onboarding
from studio_core.bundles import inventory
from marketing_studio import shared

ROOT = Path(__file__).resolve().parents[1]
LISTED = {'models': [{'name': 'fixture-main', 'label': 'Fixture Main', 'levels': ['low', 'high']}],
          'levels': ['low', 'high'], 'source': 'Synthetic fixture'}


class CatalogTests(IsolatedHome):
    def test_codex_parser_filters_hidden_invalid_ids_and_unknown_efforts(self):
        parsed = model_catalog.codex_models(json.dumps({'models': [
            {'slug': 'fixture-main', 'display_name': 'Fixture Main',
             'supported_reasoning_levels': [{'effort': 'low'}, {'effort': 'high'}, {'effort': 'unknown'}],
             'default_reasoning_level': 'high'},
            {'slug': 'hidden', 'visibility': 'hidden'}, {'slug': '--unsafe'}, {'slug': None}]}))
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]['name'], 'fixture-main')
        self.assertEqual(parsed[0]['levels'], ['low', 'high'])
        self.assertEqual(parsed[0]['default_level'], 'high')
        for bad in ('not json', '{}', '{"models":3}'):
            with self.assertRaises(ValueError):
                model_catalog.codex_models(bad)

    def test_claude_choices_match_existing_studio_reference_and_alias_caps(self):
        result = model_catalog.claude_models()
        self.assertIn('cached', result['source'])
        by_name = {model['name']: model for model in result['models']}
        self.assertEqual(by_name['claude-haiku-4-5']['levels'], [])
        self.assertEqual(by_name['opus']['levels'], by_name['claude-opus-5-5']['levels'])
        self.assertEqual((ROOT/'core/studio_core/claude-code-models.json').resolve(),
                         ROOT/'studios/presentation/runner/claude-code-models.json')

    def test_cache_coalesces_requests_and_explicit_refresh_is_read_only(self):
        loader = mock.Mock(return_value=LISTED)
        catalog = model_catalog.Catalog(loader)
        with concurrent.futures.ThreadPoolExecutor(4) as pool:
            results = list(pool.map(catalog.get, ['codex'] * 8))
        self.assertEqual(loader.call_count, 1)
        results[0]['models'].clear()
        self.assertEqual(len(catalog.get('codex')['models']), 1)
        catalog.get('codex', refresh=True)
        self.assertEqual(loader.call_count, 2)
        self.assertFalse(shared.path().exists())

    def test_missing_cli_or_failed_catalog_keeps_settings_and_allows_retry(self):
        shared.update({'assistant': {'agent': 'codex', 'model': 'saved-custom'}})
        before = shared.path().read_bytes()
        loader = mock.Mock(side_effect=[ValueError('private provider diagnostic'), LISTED])
        catalog = model_catalog.Catalog(loader)
        first = catalog.get('codex')
        self.assertEqual(first['models'], [])
        self.assertNotIn('private provider diagnostic', first['problem'])
        self.assertEqual(catalog.get('codex'), first)
        self.assertIsNone(catalog.get('codex', refresh=True)['problem'])
        self.assertEqual(shared.path().read_bytes(), before)
        with self.assertRaises(ValueError):
            catalog.get('unknown')

    def test_specific_reason_is_kept_when_the_list_is_unavailable(self):
        with mock.patch.object(model_catalog.shutil, 'which', return_value=None), \
                mock.patch.object(model_catalog, 'BUNDLED_CODEX', self.root / 'no-chatgpt-app'):
            problem = model_catalog.Catalog().get('codex')['problem']
        self.assertIn('Codex was not found', problem)
        self.assertIn('Your choices are kept', problem)
        unreadable = model_catalog.Catalog(lambda _: {'models': model_catalog.codex_models('not json')})
        self.assertIn('cannot read', unreadable.get('codex')['problem'])
        empty = model_catalog.Catalog(lambda _: {**LISTED, 'models': []})
        self.assertIn('No models were listed', empty.get('codex')['problem'])

    def test_codex_command_is_catalog_only_in_disposable_directory(self):
        binary = self.root/'fixture-cli'
        capture = self.root/'capture.json'
        binary.write_text('#!' + sys.executable + '\nimport json,sys,os\nfrom pathlib import Path\n'
                          + 'Path(' + repr(str(capture)) + ').write_text(json.dumps({"args":sys.argv[1:],"cwd":os.getcwd()}))\n'
                          + 'print(\'{"models": []}\')\n')
        binary.chmod(0o700)
        with mock.patch.object(model_catalog.shutil, 'which', return_value=str(binary)):
            self.assertEqual(json.loads(model_catalog.codex_output()), {'models': []})
        captured = json.loads(capture.read_text())
        self.assertEqual(captured['args'], ['debug', 'models'])
        self.assertFalse(Path(captured['cwd']).exists())

    def test_timeout_terminates_the_fixture_cli_and_leaves_no_job(self):
        binary = self.root/'slow-fixture'
        binary.write_text('#!' + sys.executable + '\nimport time\ntime.sleep(60)\n')
        binary.chmod(0o700)
        with mock.patch.object(model_catalog.shutil, 'which', return_value=str(binary)), \
                mock.patch.object(model_catalog, 'SECONDS', .1):
            with self.assertRaisesRegex(ValueError, 'did not finish'):
                model_catalog.codex_output()

    def test_every_bundle_has_catalog_and_no_dependency_on_an_installed_other_studio(self):
        for product in ('blog', 'presentation', 'training'):
            payload = inventory(ROOT, [product])
            name = f'studios/{product}/skills/{product}-studio/scripts/studio_core/claude-code-models.json'
            self.assertIn(name, payload)
            self.assertEqual(payload[name].read_bytes(), (ROOT/'studios/presentation/runner/claude-code-models.json').read_bytes())

    def test_marketing_models_endpoint_validates_agent_and_keeps_settings(self):
        self.page.models = model_catalog.Catalog(lambda _: LISTED)
        status, _, body = self.page.read('/api/models', lambda _: 'codex')
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)['models'], LISTED['models'])
        status, _, body = self.page.write('/api/models', {'agent': 'codex'})
        self.assertEqual(status, 200)
        self.assertFalse(shared.path().exists())

    def test_standalone_model_endpoint_auth_origin_and_independence(self):
        controller = onboarding.Controller(8000, 'a'*40, 'Blog Studio', 'X-Test-Token', lambda _: None, shared)
        controller.models = model_catalog.Catalog(lambda _: LISTED)
        def headers(auth=True, origin='http://127.0.0.1:8000'):
            result = Message()
            for key, value in {'Host':'127.0.0.1:8000','Origin':origin,'Content-Type':'application/json',
                               **({'X-Test-Token':'a'*40} if auth else {})}.items():
                result[key] = value
            return result
        endpoint = '/onboarding/api/models?agent=codex'
        self.assertEqual(controller.answer(endpoint, headers())[0], 200)
        self.assertEqual(controller.answer(endpoint, headers(False))[0], 403)
        self.assertEqual(controller.answer('/onboarding/api/models', headers(origin='https://untrusted.example'),
                         'POST', b'{"agent":"codex"}')[0], 403)
        self.assertEqual(controller.answer('/onboarding/api/models?agent=invalid', headers())[0], 409)
        self.assertFalse(shared.path().exists())
