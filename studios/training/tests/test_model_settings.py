"""Use the current model settings on a stopped Training Studio training, with disposable
workspaces and settings, the scripted agent and the research stand-in: nothing here reaches a
provider or the network."""
import subprocess
import unittest

from test_settings_change import SettingsCase
from test_runner_deck import PageCase
import test_desk  # its screen tests' helpers, borrowed by name so its tests are not run here
from test_desk import NODE, ScriptedPage, a_desk, a_desk_run, ok
from test_desk import PageCase as DeskPageCase
from runner import model_settings
from studio_core import studios_config
from workspace import WorkspaceError


def earlier(effort='high'):
    """Shared settings as they were before the kinds of work: Quick, Main and Complex."""
    studios_config.update({'assistant': {'agent': 'claude', 'model': None, 'effort': None},
                           'models': {'schema': 1, 'agent': 'claude', 'mode': 'by_task', 'profiles': {
                               'quick': {'selection': 'explicit', 'model': 'big-model', 'effort': 'low'},
                               'main': {'selection': 'explicit', 'model': 'big-model', 'effort': effort},
                               'complex': {'selection': 'explicit', 'model': 'big-model', 'effort': 'max'}}}})


class ModelsCase(SettingsCase):
    def setUp(self):
        super().setUp()
        earlier()

    def older(self, root):
        """Saved as a training started before the kinds of work existed saves its choices."""
        with self.engine.files:
            record = self.engine._load(root)
            record['model_profiles'] = {
                'schema': 1, 'policy': 2, 'agent': record['agent'], 'mode': 'by_task', 'profiles': {
                    'quick': {'model': 'big-model', 'effort': 'low', 'source': 'explicit'},
                    'main': {'model': 'big-model', 'effort': 'high', 'source': 'explicit'},
                    'complex': {'model': 'big-model', 'effort': 'max', 'source': 'explicit'}}}
            self.engine._store(root, record)
        return root

    def last_commit(self, root) -> str:
        return subprocess.run(['git', '-C', str(root), 'log', '-1', '--format=%s'], check=True,
                              capture_output=True, text=True).stdout.strip()


class UseTests(ModelsCase):
    def test_a_stopped_training_takes_up_the_lighter_research_kinds(self):
        root = self.older(self.supplied())
        before = self.view(root)
        self.assertEqual(before['state'], 'failed')
        self.assertTrue(before['current_models']['may'], before['current_models'])
        shown = model_settings.preview(self.engine, root)
        self.assertEqual([c['kind'] for c in shown['changes']], ['research', 'combining', 'checking'])
        self.assertEqual(shown['changes'][0]['before'], {'model': 'big-model', 'effort': 'high'})
        self.assertEqual(shown['changes'][0]['after'], {'model': 'big-model', 'effort': 'medium'})
        made = model_settings.save(self.engine, root, {'expected': shown['expected']})
        record = self.engine._load(root)
        self.assertEqual(record['model_profiles']['policy'], 3)
        self.assertEqual(record['model_profiles']['profiles']['research']['effort'], 'medium')
        self.assertEqual(record['model_changes'][-1]['changes'], shown['changes'])
        # What stopped it stays, with its own action.
        self.assertEqual(made['problem'], before['problem'])
        self.assertTrue(self.last_commit(root).endswith(
            ': use the current model settings: Research, Combining and Checking'))
        self.assertEqual(model_settings.preview(self.engine, root)['changes'], [])
        with self.assertRaisesRegex(WorkspaceError, 'already uses the current model settings'):
            model_settings.save(self.engine, root,
                                {'expected': model_settings.preview(self.engine, root)['expected']})

    def test_a_later_settings_change_is_offered_again(self):
        root = self.supplied()
        self.assertEqual(model_settings.preview(self.engine, root)['changes'], [])
        studios_config.update({'models': {'profiles': {'combining': {
            'selection': 'explicit', 'model': 'fast-model', 'effort': 'low'}}}})
        shown = model_settings.preview(self.engine, root)
        self.assertEqual([c['kind'] for c in shown['changes']], ['combining'])
        model_settings.save(self.engine, root, {'expected': shown['expected']})
        combining = self.engine._load(root)['model_profiles']['profiles']['combining']
        self.assertEqual((combining['model'], combining['effort']), ('fast-model', 'low'))


class RefusalTests(ModelsCase):
    def test_settings_changed_after_the_preview_are_refused(self):
        root = self.older(self.supplied())
        shown = model_settings.preview(self.engine, root)
        studios_config.update({'models': {'profiles': {'research': {
            'selection': 'explicit', 'model': 'big-model', 'effort': 'low'}}}})
        with self.assertRaisesRegex(WorkspaceError, 'changed since this was opened'):
            model_settings.save(self.engine, root, {'expected': shown['expected']})
        self.assertEqual(self.engine._load(root)['model_profiles']['policy'], 2)

    def test_a_working_run_is_refused(self):
        root = self.older(self.supplied())
        shown = model_settings.preview(self.engine, root)
        run = self.engine._run(root)
        run.busy = True
        try:
            self.assertFalse(self.view(root)['current_models']['may'])
            with self.assertRaisesRegex(WorkspaceError, 'working now'):
                model_settings.save(self.engine, root, {'expected': shown['expected']})
        finally:
            run.busy = False

    def test_a_training_started_before_change_settings_may_still_use_them(self):
        root = self.older(self.saved_start())
        self.assertFalse(self.view(root)['settings']['may'])
        self.assertTrue(model_settings.preview(self.engine, root)['changes'])


class RouteTests(ModelsCase, PageCase):
    def test_the_preview_and_its_save_through_the_page(self):
        root = self.older(self.supplied())
        shown = self.get('training-models', path=str(root))
        self.assertTrue(shown['may'])
        self.post('training-models', {'path': str(root)}, expect=400)
        made = self.post('training-models', {'path': str(root), 'expected': shown['expected']})
        self.assertEqual([c['kind'] for c in made['changed_models']['changes']],
                         ['research', 'combining', 'checking'])
        refused = self.post('training-models', {'path': str(root), 'expected': shown['expected']},
                            expect=409)
        self.assertIn('changed since this was opened', refused['error'])


CHANGES = [{'kind': 'research', 'title': 'Research', 'before': {'model': 'big-model', 'effort': 'high'},
            'after': {'model': 'big-model', 'effort': 'medium'}}]


@unittest.skipUnless(NODE, 'Node is needed to run the page scripts without a browser')
class SheetTests(ScriptedPage, DeskPageCase):
    """The sheet, run in the page harness: opened from the stop's card, then saved."""

    answers = test_desk.TrainingDeskScreenTests.answers
    posts = test_desk.TrainingDeskScreenTests.posts
    started = test_desk.TrainingDeskScreenTests.started
    listed = test_desk.TrainingDeskScreenTests.listed
    detail = test_desk.TrainingDeskScreenTests.detail
    on_desk = test_desk.TrainingDeskScreenTests.on_desk
    open_desk = test_desk.TrainingDeskScreenTests.open_desk

    def stopped(self) -> dict:
        run = a_desk_run('failed', 'Research stopped.')
        run['body'].update(problem={'what': 'Research did not finish.', 'kept': 'Saved work is kept.',
                                    'action': 'retry', 'label': 'Try again'},
                           settings={'may': True, 'why': None},
                           current_models={'may': True, 'why': None})
        return self.on_desk(a_desk(running=False), run, **{
            'GET /api/training-models': [ok({'may': True, 'why': None, 'changes': CHANGES,
                                             'expected': 'e1', 'mode': 'by_task',
                                             'kept': model_settings.KEPT})],
            'POST /api/training-models': [ok(run['body'])]})

    def test_a_stop_offers_the_current_models_and_saves_them(self):
        result = self.open_desk(self.stopped(), [
            {'snapshot': 'stopped'},
            {'click': 'Use the current model settings'}, {'snapshot': 'sheet'},
            {'click': 'Use these models'}, {'snapshot': 'saved'}])
        shots = result['snapshots']
        self.assertIn('Use the current model settings', shots['stopped']['buttons'])
        self.assertIn('Try again', shots['stopped']['buttons'])
        self.assertIn('Research: big-model · high reasoning → big-model · medium reasoning',
                      shots['sheet']['text'])
        self.assertIn('Everything finished is kept', shots['sheet']['text'])
        posted = [body for address, body in self.posts(result) if address == '/api/training-models']
        self.assertEqual(posted, [{'path': str(self.root), 'expected': 'e1'}])
        self.assertNotIn('Use these models', shots['saved']['buttons'], 'The sheet is put away')


if __name__ == '__main__':
    unittest.main()
