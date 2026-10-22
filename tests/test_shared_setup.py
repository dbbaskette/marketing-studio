"""Shared setup is completed once, regardless of which studio hosted the form."""
import json
import os
from email.message import Message
from pathlib import Path
from unittest import mock

from test_home import IsolatedHome
from marketing_studio import shared, state
from marketing_studio.page import Home
from studio_core import workspace_setup, onboarding, preferences


class SharedSetupTests(IsolatedHome):
    def test_repository_only_brand_save_is_shared_without_installing(self):
        for repository in ('https://example.com/team/brand-skill.git', 'git@example.com:team/brand-skill.git'):
            with self.subTest(repository=repository):
                shared.path().write_text('{"schema": 1, "unrelated": {"keep": true}}')
                with mock.patch('subprocess.Popen') as start, mock.patch('subprocess.run') as run:
                    self.write('/api/shared', {'changes': {'brand': {'repository': repository}}, 'seen': {}})
                    for product in ('Blog Studio', 'Presentation Studio', 'Training Studio'):
                        page = onboarding.Controller(8000, 'a' * 40, product, 'X-Test-Token', lambda _: None, shared)
                        brand = page.snapshot()['shared']['brand']
                        self.assertEqual(brand['repository'], repository)
                        self.assertFalse(brand.get('skill'))
                    start.assert_not_called()
                    run.assert_not_called()
                self.assertEqual(json.loads(shared.path().read_text())['unrelated'], {'keep': True})
                seen = shared.read()[0]
                shared.update({'brand': {'repository': 'https://example.com/new/brand.git'}})
                status, _ = self.request(self.controller(), 'shared', {
                    'changes': {'brand': {'repository': repository}}, 'seen': seen})
                self.assertEqual(status, 409)
                self.assertEqual(shared.read()[0]['brand']['repository'], 'https://example.com/new/brand.git')

    def headers(self, token='a' * 40):
        headers = Message()
        for key, value in {'Host': '127.0.0.1:8000', 'Origin': 'http://127.0.0.1:8000',
                           'Content-Type': 'application/json', 'X-Test-Token': token}.items():
            headers[key] = value
        return headers

    def controller(self, prepare=lambda _: None):
        return onboarding.Controller(8000, 'a' * 40, 'Training Studio', 'X-Test-Token',
                                     prepare, shared)

    def request(self, page, path, sent=None, headers=None):
        response = page.answer('/onboarding/api/' + path, headers or self.headers(),
                               'GET' if sent is None else 'POST',
                               None if sent is None else json.dumps(sent).encode())
        return response[0], json.loads(response[2])

    def test_installed_brand_lookup_requires_auth_and_never_saves_or_installs(self):
        expected = {'skills': [{'name': 'example-brand', 'path': str(self.root / 'brand'), 'brands': [{'brand': 'example', 'name': 'Example', 'variants': ['light']}]}], 'problem': None}
        for product in ('Blog Studio', 'Presentation Studio', 'Training Studio'):
            page = onboarding.Controller(8000, 'a' * 40, product, 'X-Test-Token', lambda _: None, shared)
            before = shared.read()[0]
            with mock.patch('studio_core.brand_catalog.choices', return_value=expected) as lookup:
                self.assertEqual(self.request(page, 'brands', {}, self.headers('wrong'))[0], 403)
                lookup.assert_not_called()
                self.assertEqual(self.request(page, 'brands', {})[1], expected)
                self.assertEqual(self.request(page, 'brands', {'skill': 'relative-folder'})[0], 409)
                self.assertEqual(self.request(page, 'brands', {'skill': str(self.root / 'brand')})[0], 200)
            self.assertEqual(shared.read()[0], before)

    def test_standalone_setup_completes_marketing_and_other_studios(self):
        for product in ('Blog Studio', 'Presentation Studio', 'Training Studio'):
            with self.subTest(product=product):
                shared.path().unlink(missing_ok=True)
                prepared = mock.Mock()
                page = onboarding.Controller(8000, 'a' * 40, product, 'X-Test-Token', prepared, shared)
                self.assertTrue(page.accepts('/'))
                status, body = self.request(page, 'shared', {
                    'changes': {'local': {'root': str(self.root / 'work')},
                                'assistant': {'agent': 'codex', 'model': 'gpt-6-luna', 'effort': 'high'},
                                'render': {'previews': 'local'}, 'output': 'pptx'}, 'seen': {}})
                self.assertEqual(status, 200)
                self.assertFalse(body['setup']['done'])
                status, body = self.request(page, 'setup', {'done': True})
                self.assertEqual(status, 200)
                prepared.assert_called_once()
                self.assertTrue(body['setup']['done'])
                self.assertTrue(self.page.snapshot()['setup']['done'])
                self.assertFalse(state.read()['done'], 'no Marketing Studio state was required')
                self.assertFalse(page.accepts('/'))

    def test_marketing_completion_is_visible_without_marketing_process_or_state(self):
        shared.update({'local': {'root': str(self.root / 'work')}})
        self.write('/api/setup', {'done': True})
        state.data_root().joinpath('home.json').unlink()
        self.assertTrue(self.controller().snapshot()['setup']['done'])
        self.assertTrue(Home(8000, self.launcher).snapshot()['setup']['done'])

    def test_partial_or_invalid_configuration_requires_setup(self):
        for values in ({'local': {'root': str(self.root)}},
                       {'setup': {'version': True}, 'local': {'root': str(self.root)}},
                       {'setup': {'version': 1}},
                       {'setup': {'version': 1}, 'local': {'root': 'relative'}},
                       {'setup': {'version': 1}, 'local': {'root': str(self.root)}, 'assistant': 23}):
            with self.subTest(values=values):
                shared.path().write_text(json.dumps(values))
                self.assertTrue(self.controller().accepts('/'))
        shared.path().write_text('not json')
        status, _ = self.request(self.controller(), 'setup', {'done': True})
        self.assertEqual(status, 409)
        self.assertEqual(shared.path().read_text(), 'not json')

    def test_failed_workspace_setup_does_not_mark_global_setup_complete(self):
        shared.update({'local': {'root': str(self.root)}})
        def fail(_):
            raise ValueError('Git needs an identity')
        status, body = self.request(self.controller(fail), 'setup', {'done': True})
        self.assertEqual(status, 409)
        self.assertIn('identity', body['error'])
        self.assertFalse(preferences.ready(shared.read()[0]))

    def test_concurrent_change_during_finish_requires_another_review(self):
        shared.update({'local': {'root': str(self.root)}, 'output': 'pptx'})
        page = self.controller(lambda _: shared.update({'output': 'google'}))
        status, body = self.request(page, 'setup', {'done': True})
        self.assertEqual(status, 409)
        self.assertIn('Another studio', body['error'])
        self.assertFalse(preferences.ready(shared.read()[0]))

    def test_saving_a_review_level_another_studio_changed_is_refused(self):
        from studio_core import review_policy
        shared.path().write_text('{"schema": 1, "review": {"level": "step_by_step"}}')
        with self.assertRaises(ValueError) as caught:
            preferences.save(shared, {'review': {'level': 'automatic'}},
                             seen={'review': {'level': 'balanced'}})
        self.assertEqual(str(caught.exception), review_policy.STALE)
        self.assertEqual(shared.read()[0]['review'], {'level': 'step_by_step'})
        # A form that read no level saw Balanced, and a file still without one takes the save.
        shared.path().write_text('{"schema": 1}')
        preferences.save(shared, {'review': {'level': 'automatic'}},
                         seen=preferences.visible({}))
        self.assertEqual(shared.read()[0]['review'], {'level': 'automatic'})

    def test_same_leaf_conflicts_and_unrelated_content_survives(self):
        shared.path().write_text('{"unknown": {"keep": [1, 2]}, "render": {"previews": "local"}}')
        page = self.controller()
        seen = shared.read()[0]
        shared.update({'render': {'previews': 'drive'}})
        status, _ = self.request(page, 'shared', {
            'changes': {'render': {'previews': None}}, 'seen': seen})
        self.assertEqual(status, 409)
        status, _ = self.request(page, 'shared', {'changes': {'output': 'pptx'}, 'seen': seen})
        self.assertEqual(status, 200)
        self.assertIn('"unknown": {"keep": [1, 2]}', shared.path().read_text())
        self.assertEqual(shared.read()[0]['render']['previews'], 'drive')

    def test_shared_setup_has_native_host_token_and_origin_protections(self):
        page = self.controller()
        for name, value in [('X-Test-Token', 'wrong'), ('Host', 'evil.invalid:8000'),
                            ('Origin', 'http://evil.invalid')]:
            headers = self.headers()
            headers.replace_header(name, value)
            status, _ = self.request(page, 'setup', {'done': True}, headers)
            self.assertEqual(status, 403)
        status, media, body = page.answer('/', self.headers())
        self.assertEqual(status, 200)
        self.assertIn(b'data-standalone="true"', body)
        self.assertIn(b'X-Test-Token', body)
        self.assertNotIn(b'a' * 40, body)

    def test_launch_adopts_local_defaults_once_and_preserves_existing_workspaces(self):
        gitstate = mock.Mock()
        gitstate.current.return_value = None
        shared.update({'local': {'root': str(self.root / 'work')}})
        workspace_setup.launch(gitstate, shared, 'training')
        gitstate.local.assert_not_called()
        preferences.finish(shared, lambda _: None)
        workspace_setup.launch(gitstate, shared, 'training')
        gitstate.local.assert_called_once_with(self.root / 'work/training-workspace', branch='main')
        existing = object()
        gitstate.current.return_value = existing
        shared.update({'local': {'root': str(self.root / 'different')}})
        self.assertIs(workspace_setup.launch(gitstate, shared, 'training'), existing)
        self.assertEqual(gitstate.local.call_count, 1)

    def test_remote_launch_uses_branch_and_sharing_without_local_folder_creation(self):
        gitstate = mock.Mock()
        gitstate.current.return_value = None
        shared.update({'team': {'repository': 'https://example.com/work.git', 'branch': 'drafts'},
                       'share': 'asked'})
        preferences.finish(shared, lambda _: None)
        workspace_setup.launch(gitstate, shared, 'presentation')
        gitstate.join.assert_called_once_with('https://example.com/work.git', branch='drafts', share='asked')
        gitstate.local.assert_not_called()

    def test_legacy_marketing_completion_is_promoted_on_open(self):
        shared.update({'local': {'root': str(self.root / 'work')}})
        state.save({'schema': 1, 'done': True, 'paths': {}})
        self.assertTrue(Home(8000, self.launcher).snapshot()['setup']['done'])
        self.assertTrue(self.controller().snapshot()['setup']['done'])

    def test_native_runners_consume_live_shared_model_brand_and_preview_choices(self):
        import subprocess
        import sys
        repo = Path(__file__).resolve().parents[1]
        shared.update({'assistant': {'agent': 'codex', 'model': 'gpt-6-luna', 'effort': 'high'},
                       'local': {'root': str(self.root / 'work')}, 'output': 'pptx',
                       'brand': {'skill': str(self.root / 'brand-runtime')}})
        preferences.finish(shared, lambda _: None)
        code = '''import sys
sys.path.insert(0, sys.argv[1])
from dataclasses import replace
from runner import settings, setup
from studio_core.onboarding import config
studios_config = config('Fixture Studio')
# Old private values must not replace even an automatic shared preview choice.
import json
settings.path().parent.mkdir(parents=True, exist_ok=True)
settings.path().write_text(json.dumps({'schema': 1, 'agent': 'claude', 'previews': 'drive',
                                     'brand_skill': '/old/private-brand', 'parallel': 4}))
initial = studios_config.path().read_bytes()
setup.migrate()
assert studios_config.path().read_bytes() == initial
assert not {'agent', 'previews', 'brand_skill'} & json.loads(settings.path().read_text()).keys()
chosen = settings.load()
assert (chosen.agent, chosen.model, chosen.effort) == ('codex', 'gpt-6-luna', 'high')
assert chosen.previews == 'local'
assert chosen.brand_skill == sys.argv[2]
# An unchanged automatic preview does not cause a false conflict on a native save.
shown = settings.seen(setup.shared()[0])
assert shown.previews == chosen.previews
settings.save(replace(chosen, parallel=3), shown)
assert settings.load().parallel == 3
assert not studios_config.read()[0].get('render'), 'an unchanged native form must keep automatic previews'
studios_config.update({'render': {'previews': 'drive'}, 'assistant': {'model': 'gpt-6-sol'}})
assert (settings.load().previews, settings.load().model) == ('drive', 'gpt-6-sol')
# A form kept open while another studio changes previews must not replace that choice.
settings.save(replace(chosen, previews='drive'), chosen)
studios_config.update({'render': {'previews': 'local'}})
before = settings.load()
studios_config.update({'render': {'previews': 'drive'}})
try:
    settings.save(replace(before, previews=None), before)
except Exception as failure:
    assert 'another studio' in str(failure)
else:
    raise AssertionError('a conflicting preview change was accepted')
'''
        initial = shared.path().read_text()
        for identifier in ('presentation', 'training'):
            with self.subTest(studio=identifier):
                shared.path().write_text(initial)
                env = {**os.environ, 'HOME': str(self.root / 'home'),
                       identifier.upper() + '_STUDIO_DATA': str(self.root / identifier)}
                done = subprocess.run([sys.executable, '-c', code,
                                       str(repo / 'studios' / identifier), str(self.root / 'brand-runtime')],
                                      env=env, text=True, capture_output=True, timeout=15)
                self.assertEqual(done.returncode, 0, done.stderr)

    def test_browser_finish_loads_native_page_even_when_setup_uses_root(self):
        import subprocess
        repo = Path(__file__).resolve().parents[1]
        script = r'''const fs = require('node:fs'), vm = require('node:vm'), assert = require('node:assert/strict');
const source = fs.readFileSync(process.argv[1], 'utf8');
const entry = /function openNative\(\) \{[\s\S]*?\n\}/.exec(source)[0];
for (const path of ['/', '/onboarding/']) {
  for (const product of ['Blog Studio', 'Presentation Studio', 'Training Studio']) {
    let nativePage = false, arrived;
    const location = {pathname: path, search: '',
      replace(url) { arrived = url; if (path !== '/') nativePage = true; },
      reload() { nativePage = true; }};
    vm.runInNewContext(entry + '; openNative();', {location, product, token: 'synthetic-session'});
    assert.equal(nativePage, true, product + ' must load its native HTML after setup');
    assert.equal(arrived, '/#' + (product === 'Blog Studio' ? '' : 'token=') + 'synthetic-session');
  }
}
'''
        done = subprocess.run(['node', '-e', script, str(repo / 'core/studio_core/setup_web/app.js')],
                              text=True, capture_output=True, timeout=10)
        self.assertEqual(done.returncode, 0, done.stderr)

    def test_workers_resume_only_after_completion_is_committed(self):
        shared.update({'local': {'root': str(self.root / 'work')}})
        observed = []
        page = onboarding.Controller(8000, 'a' * 40, 'Training Studio', 'X-Test-Token',
                                     lambda _: observed.append(('prepare', preferences.ready(shared.read()[0]))),
                                     shared, after=lambda: observed.append(('resume', preferences.ready(shared.read()[0]))))
        status, _ = self.request(page, 'setup', {'done': True})
        self.assertEqual(status, 200)
        self.assertEqual(observed, [('prepare', False), ('resume', True)])
