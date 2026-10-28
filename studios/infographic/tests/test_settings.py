"""Shared/native preference ownership and honest non-billable readiness."""
from copy import deepcopy
import json
import threading
from unittest import mock

from helpers import Isolated
from runner import computer, settings
from runner.contracts import Invalid
from runner.workspace import Store


class SettingsTests(Isolated):
    def shared(self, agent='codex', model='fixture-model', effort='high'):
        value = {'schema': 1, 'assistant': {'agent': agent, 'model': model, 'effort': effort},
                 'person': {'name': 'Synthetic Author'}, 'local': {'root': str(self.temp / 'shared-work')},
                 'output': 'pptx', 'unrelated': {'preserve': True}}
        self.settings.write_text(json.dumps(value))
        return value

    def test_new_snapshot_sees_defaults_without_mutating_existing_choices_or_workspace(self):
        old = self.shared()
        store = Store.setup(self.workspace)
        chosen = settings.snapshot()
        new = self.shared('claude', 'other-fixture-model')
        new['local']['root'] = str(self.temp / 'different-root')
        self.settings.write_text(json.dumps(new))
        self.assertEqual(chosen['assistant'], old['assistant'])
        self.assertEqual(settings.snapshot()['assistant'], new['assistant'])
        self.assertEqual(Store.current().root, store.root)
        self.assertFalse((self.temp / 'different-root').exists())
        self.assertEqual(json.loads(self.settings.read_text())['unrelated'], {'preserve': True})

    def test_stale_native_forms_preserve_unrelated_values_and_reject_credentials(self):
        self.shared()
        first = settings.snapshot()
        second = settings.save({'gemini_model': 'fixture-image-model'}, expected=first['native_revision'])
        with self.assertRaises(Invalid): settings.save({'renderer': str(self.temp / 'renderer')}, expected=first['native_revision'])
        with self.assertRaises(Invalid): settings.save({'gemini_api_key': 'synthetic-sentinel'}, expected=second['native_revision'])
        last = settings.save({'renderer': '~/explicit-renderer'}, expected=second['native_revision'])
        self.assertEqual(last['native']['gemini_model'], 'fixture-image-model')
        self.assertEqual(last['native']['renderer'], str(self.home / 'explicit-renderer'))
        self.assertNotIn('synthetic-sentinel', (self.data / 'preferences.json').read_text())

    def test_concurrent_native_forms_cannot_lose_a_conflicting_edit(self):
        self.shared(); revision = settings.snapshot()['native_revision']
        barrier = threading.Barrier(2); outcomes = []
        def save(model):
            barrier.wait()
            try:
                settings.save({'gemini_model': model}, expected=revision)
                outcomes.append('saved')
            except Invalid: outcomes.append('conflict')
        threads = [threading.Thread(target=save, args=(name,)) for name in ('fixture-one', 'fixture-two')]
        for thread in threads: thread.start()
        for thread in threads: thread.join(timeout=5)
        self.assertCountEqual(outcomes, ['saved', 'conflict'])
        self.assertIn(settings.native()['gemini_model'], ('fixture-one', 'fixture-two'))

    def test_readiness_exposes_missing_model_renderer_and_presence_without_secrets_or_jobs(self):
        self.shared('claude')
        chosen = settings.snapshot()
        missing = computer.inspect(chosen=chosen, command=lambda _: '/synthetic/claude', environ={})
        self.assertEqual(missing['state'], 'unavailable')
        self.assertIn('gemini-key-required', missing['problems'])
        self.assertIn('gemini-model-required', missing['problems'])
        self.assertFalse(missing['renderer_available'])
        configured = settings.save({'gemini_model': 'fixture-image'}, expected=chosen['native_revision'])
        report = computer.inspect(chosen=configured, command=lambda _: '/synthetic/claude', environ={'GEMINI_API_KEY': 'synthetic-sentinel'})
        self.assertEqual(report['state'], 'unverified')
        self.assertNotIn('synthetic-sentinel', json.dumps(report))
        self.assertFalse(report['generation_started'])
        self.shared('codex')
        report = computer.inspect(chosen=settings.snapshot(), command=lambda _: '/synthetic/codex', environ={})
        self.assertFalse(report['credential_required'])
        self.assertNotIn('gemini-key-required', report['problems'])
