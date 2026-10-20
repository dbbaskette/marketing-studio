"""Profiles resolve without provider calls and respect the shared settings lock."""
import copy
import json
from unittest import mock

from test_home import IsolatedHome
from marketing_studio import shared
from studio_core import model_profiles as models, preferences, runtime


def configuration(agent='codex'):
    return {'schema': 1, 'assistant': {'agent': agent, 'model': 'shared-model', 'effort': 'medium'},
            'models': {'schema': 1, 'agent': agent, 'mode': 'by_task', 'profiles': {
                'quick': {'selection': 'explicit', 'model': 'quick-model', 'effort': 'low'},
                'main': {'selection': 'inherit'},
                'complex': {'selection': 'explicit', 'model': 'complex-model', 'effort': 'high'}}}}


class ProfileTests(IsolatedHome):
    def test_shared_setup_saves_nested_choices_for_all_hosts(self):
        values = configuration()
        response = self.write('/api/shared', {'changes': {k: v for k, v in values.items() if k != 'schema'}, 'seen': {}})
        self.assertEqual(response['shared']['models'], values['models'])
        from studio_core.onboarding import Controller
        page = Controller(8000, 'a' * 40, 'Training Studio', 'X-Test', lambda _: None, shared)
        self.assertEqual(page.snapshot()['shared']['models'], values['models'])

    def test_nested_edit_preserves_unknown_fields_and_bytes(self):
        values = configuration()
        values['models']['profiles']['quick']['future'] = ['untouched']
        values['unrelated'] = {'spacing': [1, 2]}
        raw = json.dumps(values, indent=4) + '\n'
        shared.path().write_text(raw)
        preferences.save(shared, {'models': {'profiles': {'quick': {'model': 'new-model'}}}}, values)
        self.assertEqual(shared.path().read_text(), raw.replace('quick-model', 'new-model'))

    def test_stale_same_profile_edit_is_rejected_but_other_profile_merges(self):
        shared.update({k: v for k, v in configuration().items() if k != 'schema'})
        seen = shared.read()[0]
        preferences.save(shared, {'models': {'profiles': {'quick': {'model': 'other'}}}}, seen)
        with self.assertRaisesRegex(ValueError, 'Another studio'):
            preferences.save(shared, {'models': {'profiles': {'quick': {'model': 'mine'}}}}, seen)
        preferences.save(shared, {'models': {'profiles': {'complex': {'effort': 'max'}}}}, seen)
        self.assertEqual(shared.read()[0]['models']['profiles']['quick']['model'], 'other')

    def test_profile_edit_rejects_concurrent_inherited_model_change(self):
        shared.update({k: v for k, v in configuration().items() if k != 'schema'})
        seen = shared.read()[0]
        shared.update({'assistant': {'model': 'changed'}})
        with self.assertRaisesRegex(ValueError, 'Another studio'):
            preferences.save(shared, {'models': {'profiles': {'quick': {'model': 'mine'}}}}, seen)

    def test_assistant_change_requires_profile_review(self):
        values = configuration()
        with self.assertRaisesRegex(ValueError, 'Review'):
            preferences.check({'assistant': {'agent': 'claude'}}, values)
        result = preferences.check({'assistant': {'agent': 'claude'},
                                    'models': {'agent': 'claude'}}, values)
        self.assertEqual(result['models']['agent'], 'claude')

    def test_invalid_profiles_do_not_write(self):
        for changes in ({'models': {'schema': True}}, {'models': {'mode': 'random'}},
                        {'models': {'profiles': {'quick': {'selection': 'explicit'}}}},
                        {'models': {'profiles': {'quick': {'model': '--unsafe'}}}},
                        {'models': {'profiles': {'quick': {'effort': 'ultra'}}}},
                        {'models': {'profiles': {'unknown': {}}}},
                        {'models': {'profiles': {'quick': {'model': ['bad']}}}}):
            with self.subTest(changes=changes):
                before = shared.path().read_bytes() if shared.path().exists() else None
                # Unsaved, the assistant is the computer's default; Claude Code has no 'ultra'.
                with self.assertRaises(ValueError), \
                        mock.patch.object(runtime, 'assistant_default', return_value='claude'):
                    preferences.save(shared, changes, {})
                self.assertEqual(shared.path().read_bytes() if shared.path().exists() else None, before)

    def test_routes_use_structured_ids_for_both_assistants(self):
        for agent in ('claude', 'codex'):
            record = {'agent': agent, 'model_profiles': models.snapshot(
                configuration(agent), agent, 'shared-model', 'medium')}
            for product, step, profile in (
                ('Blog Studio', 'source-classification', 'quick'),
                ('Blog Studio', 'research', 'main'), ('Blog Studio', 'review', 'main'),
                ('Presentation Studio', 'classify', 'quick'),
                ('Presentation Studio', 'extract', 'quick'),
                ('Presentation Studio', 'build-review:1', 'main'),
                ('Presentation Studio', 'build-repair:2', 'main'),
                ('Presentation Studio', 'outline', 'quick'),
                ('Training Studio', 'research:question-2', 'main'),
                ('Training Studio', 'deck-review@301', 'main'),
                ('Training Studio', 'deck-repair@301:2', 'complex')):
                with self.subTest(agent=agent, step=step):
                    choice = models.route(record, product, step)
                    self.assertEqual(choice['profile'], profile)
                    self.assertEqual(choice['model'], {'quick': 'quick-model',
                        'main': 'shared-model', 'complex': 'complex-model'}[profile])
                    self.assertIsNone(choice['actual_model'])
            self.assertEqual(models.route(record, 'Blog Studio', 'draft', purpose='repair')['profile'], 'complex')
            self.assertEqual(models.route(record, 'Presentation Studio', 'build-repair:section-1', purpose='repair-escalated')['profile'], 'complex')
            record['model_profiles']['policy'] = 1
            self.assertEqual(models.route(record, 'Presentation Studio', 'build-repair:section-1')['profile'], 'complex')

    def test_snapshot_is_immutable_and_work_override_stays_single(self):
        values = configuration()
        saved = models.snapshot(values, 'codex', 'shared-model', 'medium')
        values['models']['profiles']['quick']['model'] = 'later'
        self.assertEqual(saved['profiles']['quick']['model'], 'quick-model')
        overridden = models.snapshot(values, 'codex', 'work-model', 'high')
        self.assertEqual(overridden['mode'], 'single')
        self.assertEqual({p['model'] for p in overridden['profiles'].values()}, {'work-model'})
        self.assertEqual(models.snapshot(values, 'claude')['mode'], 'single')

    def test_provider_default_does_not_inherit_flags(self):
        values = configuration()
        values['models']['profiles']['complex'] = {'selection': 'provider_default',
                                                   'model': 'dormant', 'effort': 'high'}
        saved = models.snapshot(values, 'codex', 'shared-model', 'medium')
        self.assertEqual(saved['profiles']['complex'], {'model': None, 'effort': None,
                                                       'source': 'provider_default'})

    def test_legacy_runs_ignore_new_global_profiles(self):
        shared.update({k: v for k, v in configuration().items() if k != 'schema'})
        for product in ('Blog Studio', 'Presentation Studio', 'Training Studio'):
            choice = models.route({'model': 'old', 'effort': 'low'}, product, 'deck-repair')
            self.assertEqual((choice['profile'], choice['model'], choice['effort']), ('main', 'old', 'low'))
        self.assertEqual(models.snapshot({}, 'claude')['mode'], 'single')

    def test_malformed_assistant_binding_is_a_clear_validation_error(self):
        for values in ({'assistant': 'bad'}, {'assistant': {'agent': []}},
                       {'models': {'agent': ['bad']}}):
            with self.subTest(values=values), self.assertRaises(ValueError):
                models.check(values)

    def test_unreadable_shared_file_keeps_validated_defaults_without_writing(self):
        shared.path().write_text('not json')
        saved = models.capture('codex', 'kept-model', 'high')
        self.assertEqual(saved['mode'], 'single')
        self.assertEqual(saved['profiles']['main']['model'], 'kept-model')
        self.assertEqual(shared.path().read_text(), 'not json')

    def test_future_policy_and_agent_mismatch_stop_before_provider(self):
        record = {'agent': 'codex', 'model_profiles': models.snapshot(configuration(), 'codex', 'shared-model', 'medium')}
        for changed in ({'policy': 99}, {'agent': 'claude'}):
            altered = copy.deepcopy(record)
            altered['model_profiles'].update(changed)
            with self.assertRaises(ValueError):
                models.route(altered, 'Training Studio', 'blueprint')
