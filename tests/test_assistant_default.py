"""The assistant chosen when none is saved follows the installation, then this computer."""
import json
from unittest import mock

from test_home import IsolatedHome
from marketing_studio import computer, shared
from studio_core import model_profiles, onboarding, preferences, runtime


class AssistantDefaultTests(IsolatedHome):
    def installed(self, *names):
        """Only the named commands are found; the ChatGPT app's Codex is not."""
        found = lambda name: f'/synthetic/{name}' if name in names else None
        return mock.patch.multiple(runtime, BUNDLED_CODEX=self.root / 'no-chatgpt-app',
                                   shutil=mock.Mock(which=mock.Mock(side_effect=found)))

    def record(self, target):
        data = self.root / 'data'
        data.mkdir(exist_ok=True)
        (data / 'installation.json').write_text(json.dumps({'schema': 1, 'target': target}))

    def test_installation_target_comes_first(self):
        self.record('codex')
        with self.installed('claude'):
            self.assertEqual(runtime.assistant_default(), 'codex')
        self.record('claude')
        with self.installed('codex'):
            self.assertEqual(runtime.assistant_default(), 'claude')

    def test_installed_assistant_is_used_without_a_single_target(self):
        for target in (None, 'both'):
            if target:
                self.record(target)
            for names, expected in ((('codex',), 'codex'), (('claude',), 'claude'),
                                    ((), 'claude'), (('claude', 'codex'), 'codex')):
                with self.subTest(target=target, installed=names), self.installed(*names):
                    self.assertEqual(runtime.assistant_default(), expected)

    def test_unreadable_installation_record_falls_back_to_this_computer(self):
        data = self.root / 'data'
        data.mkdir()
        (data / 'installation.json').write_text('not json')
        with self.installed('codex'):
            self.assertEqual(runtime.assistant_default(), 'codex')

    def test_finish_saves_the_default_and_home_snapshots_offer_it(self):
        self.record('codex')
        shared.update({'local': {'root': str(self.root / 'work')}})
        with self.installed('claude'):
            self.assertEqual(self.page.snapshot()['assistant_default'], 'codex')
            controller = onboarding.Controller(8000, 'a' * 40, 'Blog Studio', 'X-Test-Token',
                                               lambda _: None, shared)
            self.assertEqual(controller.snapshot()['assistant_default'], 'codex')
            preferences.finish(shared, lambda _: None)
        self.assertEqual(shared.read()[0]['assistant']['agent'], 'codex')

    def test_finish_keeps_a_saved_assistant(self):
        self.record('codex')
        shared.update({'local': {'root': str(self.root / 'work')}, 'assistant': {'agent': 'claude'}})
        with self.installed('codex'):
            preferences.finish(shared, lambda _: None)
        self.assertEqual(shared.read()[0]['assistant']['agent'], 'claude')

    def test_profiles_without_a_saved_assistant_use_the_default(self):
        values = {'models': {'schema': 1, 'mode': 'by_task', 'agent': 'codex', 'profiles': {}}}
        self.record('codex')
        with self.installed():
            model_profiles.check(values)
            preferences.check({}, values)
        self.record('claude')
        with self.installed(), self.assertRaisesRegex(ValueError, 'Review the model profiles'):
            model_profiles.check(values)


class DoctorAssistantTests(IsolatedHome):
    def inventory(self, *names):
        found = lambda name: f'/synthetic/{name}' if name in names else None
        with mock.patch('shutil.which', side_effect=found), \
                mock.patch.object(runtime, 'BUNDLED_CODEX', self.root / 'no-chatgpt-app'), \
                mock.patch.object(computer, 'git_value', return_value='Fixture'):
            report = computer.check()
        return report, {item['name']: item for item in report['items']}

    def test_no_assistant_is_a_problem(self):
        report, items = self.inventory('git', 'node')
        self.assertFalse(report['ready'])
        self.assertFalse(items['Assistant']['ready'])
        self.assertFalse(items['Assistant']['optional'])
        self.assertIn('Claude Code or Codex', items['Assistant']['detail'])

    def test_saved_assistant_must_be_installed(self):
        shared.update({'assistant': {'agent': 'codex'}})
        report, items = self.inventory('git', 'node', 'claude')
        self.assertFalse(report['ready'])
        self.assertFalse(items['Assistant']['ready'])
        self.assertIn('Codex', items['Assistant']['detail'])
        shared.update({'assistant': {'agent': 'claude'}})
        report, items = self.inventory('git', 'node', 'claude')
        self.assertTrue(report['ready'])
        self.assertIn('Claude Code', items['Assistant']['detail'])

    def test_unknown_saved_assistant_is_a_problem(self):
        shared.path().write_text('{"schema": 1, "assistant": {"agent": "unknown"}}')
        report, items = self.inventory('git', 'node', 'claude', 'codex')
        self.assertFalse(report['ready'])
        self.assertFalse(items['Assistant']['ready'])
        self.assertIn('Choose Claude Code or Codex', items['Assistant']['detail'])

    def test_one_installed_assistant_is_enough_without_a_saved_choice(self):
        report, items = self.inventory('git', 'node', 'codex')
        self.assertTrue(report['ready'])
        self.assertTrue(items['Assistant']['ready'])
        self.assertTrue(items['Claude Code']['optional'])
