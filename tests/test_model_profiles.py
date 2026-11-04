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


def older(agent, policy=2):
    """A run record whose choices were saved under routing policy 1 or 2 (Quick, Main, Complex)."""
    return {'agent': agent, 'model_profiles': {
        'schema': 1, 'policy': policy, 'agent': agent, 'mode': 'by_task', 'profiles': {
            'quick': {'model': 'quick-model', 'effort': 'low', 'source': 'explicit'},
            'main': {'model': 'shared-model', 'effort': 'medium', 'source': 'inherit'},
            'complex': {'model': 'complex-model', 'effort': 'high', 'source': 'explicit'}}}}


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
        with self.assertRaisesRegex(ValueError, '“Quick model” was changed in another tab or studio'):
            preferences.save(shared, {'models': {'profiles': {'quick': {'model': 'mine'}}}}, seen)
        preferences.save(shared, {'models': {'profiles': {'complex': {'effort': 'max'}}}}, seen)
        self.assertEqual(shared.read()[0]['models']['profiles']['quick']['model'], 'other')

    def test_profile_edit_rejects_concurrent_inherited_model_change(self):
        shared.update({k: v for k, v in configuration().items() if k != 'schema'})
        seen = shared.read()[0]
        shared.update({'assistant': {'model': 'changed'}})
        with self.assertRaisesRegex(ValueError, '“Model” was changed in another tab or studio'):
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

    def test_older_policies_route_exactly_as_before(self):
        for agent in ('claude', 'codex'):
            record = older(agent)
            for product, step, profile in (
                ('Blog Studio', 'source-classification', 'quick'),
                ('Blog Studio', 'research', 'main'), ('Blog Studio', 'review', 'main'),
                ('Presentation Studio', 'classify', 'quick'),
                ('Presentation Studio', 'extract', 'quick'),
                ('Presentation Studio', 'build-review:1', 'main'),
                ('Presentation Studio', 'build-repair:2', 'main'),
                ('Presentation Studio', 'outline', 'quick'),
                ('Training Studio', 'scan', 'quick'),
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
            self.assertEqual(models.route(record, 'Training Studio', 'scan')['profile'], 'quick')
            self.assertEqual(models.route(record, 'Presentation Studio', 'build-repair:section-1')['profile'], 'complex')

    def test_a_research_job_s_receipt_names_its_phase(self):
        record = older('codex')
        for product in ('Presentation Studio', 'Training Studio'):
            for step, purpose in (('research:author-2', 'research-author'),
                                  ('research:review-1', 'research-review'),
                                  ('research:instance-min', 'research')):
                with self.subTest(product=product, step=step):
                    choice = models.route(record, product, step)
                    self.assertEqual((choice['purpose'], choice['profile']), (purpose, 'main'))
        self.assertEqual(models.route(record, 'Presentation Studio', 'research:review-1',
                                      purpose='review')['purpose'], 'review')

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
        # Fixing takes Complex's choice while the settings name no Fixing of their own.
        self.assertEqual(saved['profiles']['fixing'], {'model': None, 'effort': None,
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
        self.assertEqual({p['model'] for p in saved['profiles'].values()}, {'kept-model'})
        self.assertEqual(shared.path().read_text(), 'not json')

    def test_future_policy_and_agent_mismatch_stop_before_provider(self):
        record = {'agent': 'codex', 'model_profiles': models.snapshot(configuration(), 'codex', 'shared-model', 'medium')}
        for changed in ({'policy': 99}, {'agent': 'claude'}):
            altered = copy.deepcopy(record)
            altered['model_profiles'].update(changed)
            with self.assertRaises(ValueError):
                models.route(altered, 'Training Studio', 'blueprint')


def earlier(agent='claude'):
    """Settings saved before the kinds of work existed: Quick, Main and Complex only."""
    return {'schema': 1, 'assistant': {'agent': agent, 'model': 'big-model', 'effort': 'high'},
            'models': {'schema': 1, 'agent': agent, 'mode': 'by_task', 'profiles': {
                'quick': {'selection': 'explicit', 'model': 'big-model', 'effort': 'low'},
                'main': {'selection': 'explicit', 'model': 'big-model', 'effort': 'high'},
                'complex': {'selection': 'explicit', 'model': 'big-model', 'effort': 'max'}}}}


class KindTests(IsolatedHome):
    def test_earlier_settings_carry_over_with_lighter_research(self):
        shown = models.visible(earlier())
        self.assertEqual(shown['new'], ['research', 'combining', 'checking', 'writing', 'fixing'])
        profiles = shown['profiles']
        self.assertEqual(profiles['quick'], {'selection': 'explicit', 'model': 'big-model', 'effort': 'low'})
        for kind in ('research', 'combining', 'checking'):
            self.assertEqual(profiles[kind], {'selection': 'explicit', 'model': 'big-model', 'effort': 'medium'})
        self.assertEqual(profiles['writing'], {'selection': 'explicit', 'model': 'big-model', 'effort': 'high'})
        self.assertEqual(profiles['fixing'], {'selection': 'explicit', 'model': 'big-model', 'effort': 'max'})

    def test_reading_never_writes_and_older_names_are_kept(self):
        values = earlier()
        raw = json.dumps(values, indent=2) + '\n'
        shared.path().write_text(raw)
        models.capture('claude', 'big-model', 'high')
        models.visible(shared.read()[0])
        self.assertEqual(shared.path().read_text(), raw)
        # Saving one kind keeps Main and Complex as they were, for studios not yet updated.
        preferences.save(shared, {'models': {'profiles': {'research': {
            'selection': 'explicit', 'model': 'big-model', 'effort': 'low'}}}}, values)
        saved = shared.read()[0]['models']['profiles']
        self.assertEqual(saved['main'], values['models']['profiles']['main'])
        self.assertEqual(saved['research']['effort'], 'low')
        self.assertNotIn('research', models.visible(shared.read()[0])['new'])

    def test_a_kind_s_own_choice_wins_over_the_older_ones(self):
        values = earlier()
        values['models']['profiles']['combining'] = {'selection': 'explicit', 'model': 'fast-model', 'effort': 'low'}
        saved = models.snapshot(values, 'claude', 'big-model', 'high')
        self.assertEqual(saved['policy'], 3)
        self.assertEqual(set(saved['profiles']), set(models.KINDS))
        self.assertEqual(saved['profiles']['combining'], {'model': 'fast-model', 'effort': 'low', 'source': 'explicit'})
        self.assertEqual(saved['profiles']['research']['effort'], 'medium')

    def test_the_shared_model_at_a_kind_s_own_reasoning(self):
        values = earlier()
        values['models']['profiles'] = {'research': {'selection': 'inherit', 'effort': 'low'},
                                        'main': {'selection': 'inherit', 'effort': 'max'}}
        saved = models.snapshot(values, 'claude', 'big-model', 'high')
        self.assertEqual(saved['profiles']['research'], {'model': 'big-model', 'effort': 'low', 'source': 'inherit'})
        # Main's hidden reasoning was never used for a shared-model profile, so Writing
        # keeps the shared reasoning; Combining starts at medium on the shared model.
        self.assertEqual(saved['profiles']['writing'], {'model': 'big-model', 'effort': 'high', 'source': 'inherit'})
        self.assertEqual(saved['profiles']['combining'], {'model': 'big-model', 'effort': 'medium', 'source': 'inherit'})

    def test_one_model_mode_uses_the_shared_choice_for_every_kind(self):
        values = earlier()
        values['models']['mode'] = 'single'
        saved = models.snapshot(values, 'claude', 'big-model', 'high')
        self.assertEqual({(p['model'], p['effort']) for p in saved['profiles'].values()}, {('big-model', 'high')})

    def test_every_studio_s_jobs_route_to_their_kind(self):
        values = earlier()
        for kind, effort in (('quick', 'low'), ('research', 'medium'), ('combining', 'low'),
                             ('checking', 'medium'), ('writing', 'high'), ('fixing', 'xhigh')):
            values['models']['profiles'][kind] = {'selection': 'explicit', 'model': kind + '-model', 'effort': effort}
        record = {'agent': 'claude', 'model_profiles': models.snapshot(values, 'claude', 'big-model', 'high')}
        for product, step, purpose, kind in (
                ('Training Studio', 'scan', None, 'quick'),
                ('Training Studio', 'research-plan', None, 'research'),
                ('Training Studio', 'research:question-2', None, 'research'),
                ('Training Studio', 'research:investigate-1-area2', None, 'research'),
                ('Training Studio', 'research:author-2', None, 'combining'),
                ('Training Studio', 'research:synthesize-1', None, 'combining'),
                ('Training Studio', 'research:review-1', None, 'checking'),
                ('Training Studio', 'blueprint@201', None, 'writing'),
                ('Training Studio', 'deck-sections@201:3', None, 'writing'),
                ('Training Studio', 'deck-review@201', 'review', 'checking'),
                ('Training Studio', 'deck-repair@201:2', None, 'fixing'),
                ('Training Studio', 'draft:0a1b', None, 'writing'),
                ('Presentation Studio', 'classify', None, 'quick'),
                ('Presentation Studio', 'extract', None, 'quick'),
                ('Presentation Studio', 'outline', None, 'quick'),
                ('Presentation Studio', 'research:author-1', None, 'combining'),
                ('Presentation Studio', 'build-sections:section-1', 'construction', 'writing'),
                ('Presentation Studio', 'build-repair:section-1', 'construction', 'writing'),
                ('Presentation Studio', 'build-sections:section-1', 'repair-escalated', 'fixing'),
                ('Presentation Studio', 'build-review', 'review', 'checking'),
                ('Presentation Studio', 'build-repair:review', 'review', 'checking'),
                ('Presentation Studio', 'desk-notes', None, 'writing'),
                ('Blog Studio', 'source-classification', None, 'quick'),
                ('Blog Studio', 'research', 'research', 'research'),
                ('Blog Studio', 'research-discovery', 'research', 'research'),
                ('Blog Studio', 'research-author', 'research', 'combining'),
                ('Blog Studio', 'research-synthesize', 'research', 'combining'),
                ('Blog Studio', 'research-review', 'review', 'checking'),
                ('Blog Studio', 'claims-map', 'claims-map', 'research'),
                ('Blog Studio', 'outline', 'outline', 'writing'),
                ('Blog Studio', 'draft', 'draft', 'writing'),
                ('Blog Studio', 'draft', 'repair', 'fixing'),
                ('Blog Studio', 'review', 'review', 'checking'),
                ('Blog Studio', 'draft', 'desk-section', 'writing'),
                ('Blog Studio', 'draft', 'finish-facts', 'checking'),
                ('Blog Studio', 'draft', 'geo-report', 'checking'),
                ('Blog Studio', 'draft', 'find-text', 'research')):
            with self.subTest(product=product, step=step, purpose=purpose):
                choice = models.route(record, product, step, purpose=purpose)
                self.assertEqual((choice['profile'], choice['model']), (kind, kind + '-model'))

    def test_a_stopped_run_s_changes_name_each_kind(self):
        values = earlier()
        record = {'agent': 'claude', 'model': 'big-model', 'effort': 'high', **older('claude')}
        record['model_profiles']['profiles'] = {
            'quick': {'model': 'big-model', 'effort': 'low', 'source': 'explicit'},
            'main': {'model': 'big-model', 'effort': 'high', 'source': 'explicit'},
            'complex': {'model': 'big-model', 'effort': 'max', 'source': 'explicit'}}
        shared.update({k: v for k, v in values.items() if k != 'schema'})
        fresh = models.refreshed(record, 'claude', 'big-model', 'high')
        changes = models.differences(record, fresh)
        self.assertEqual([c['kind'] for c in changes], ['research', 'combining', 'checking'])
        self.assertEqual(changes[0]['before'], {'model': 'big-model', 'effort': 'high'})
        self.assertEqual(changes[0]['after'], {'model': 'big-model', 'effort': 'medium'})
        self.assertEqual(models.differences({**record, 'model_profiles': fresh}, fresh), [])
        # A run without saved choices ran everything on its own model and reasoning.
        plain = {'agent': 'claude', 'model': 'big-model', 'effort': 'high'}
        self.assertEqual([c["kind"] for c in models.differences(plain, fresh)],
                         ["quick", "research", "combining", "checking", "fixing"])

    def test_kind_changes_are_checked_and_stale_edits_refused(self):
        with self.assertRaisesRegex(ValueError, 'Quick, Research, Combining'):
            models.check_changes({'profiles': {'thinking': {}}})
        shared.update({k: v for k, v in earlier().items() if k != 'schema'})
        seen = shared.read()[0]
        preferences.save(shared, {'models': {'profiles': {'research': {'effort': 'low'}}}}, seen)
        with self.assertRaisesRegex(ValueError, '“Research reasoning” was changed in another tab or studio'):
            preferences.save(shared, {'models': {'profiles': {'research': {'effort': 'high'}}}}, seen)
        with self.assertRaisesRegex(ValueError, 'Give a model ID for the Checking profile'):
            preferences.save(shared, {'models': {'profiles': {'checking': {'selection': 'explicit', 'model': None}}}},
                             shared.read()[0])

    def test_the_settings_page_is_given_the_kinds_beside_the_saved_file(self):
        shared.update({k: v for k, v in earlier().items() if k != 'schema'})
        found = self.page.snapshot()
        # The saved file stays as it is, for the form to compare its changes with.
        self.assertNotIn('research', found['shared']['models']['profiles'])
        self.assertEqual(found['models_shown']['profiles']['research']['effort'], 'medium')
        self.assertIn('research', found['models_shown']['new'])
        from studio_core.onboarding import Controller
        studio = Controller(8000, 'a' * 40, 'Training Studio', 'X-Test', lambda _: None, shared)
        self.assertEqual(studio.snapshot()['models_shown'], found['models_shown'])
