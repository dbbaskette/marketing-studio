import unittest

import helpers  # noqa: F401
from runner import decks, stages


def run(route, level=None, research=False, classified=None):
    form = {'route': route, 'research': research}
    if level:
        form['level'] = level
    return {'route': route, 'form': form, 'classified': classified, 'gates': {}, 'steps': {}}


def names(r):
    return [s.name for s in stages.steps(r)]


def delivered(route, level=None):
    """A deck with every step done and every gate approved."""
    record = run(route, level)
    for s in stages.steps(record):
        if s.kind == 'gate':
            record['gates'][s.name] = {'state': 'approved'}
        else:
            record['steps'][s.name] = {'done': True}
    return record


class SavedRehearseTests(unittest.TestCase):
    def test_no_deck_has_a_rehearse_step(self):
        for route in ('scratch', 'document', 'existing'):
            with self.subTest(route=route):
                self.assertNotIn('rehearse', names(run(route)))

    def test_a_saved_deck_with_a_rehearse_gate_reads_as_before(self):
        # A deck delivered before the placeholder went holds its gate and its step.
        for route, level in (('scratch', None), ('existing', 'selected')):
            with self.subTest(route=route):
                before = delivered(route, level)
                saved = delivered(route, level)
                saved['gates']['rehearse'] = {'state': 'absent'}
                saved['steps']['rehearse'] = {}
                self.assertIsNone(stages.survey(saved).next)
                rows = stages.timeline(saved)
                self.assertNotIn('rehearse', [row['name'] for row in rows])
                self.assertTrue(all(row['state'] == 'done' for row in rows), rows)
                self.assertEqual(rows, stages.timeline(before))
                self.assertEqual(decks.state(saved), decks.state(before))
                # Still on its way, it goes on to the same next step.
                going = run(route, level)
                going['gates']['rehearse'] = {'state': 'absent'}
                going['steps']['rehearse'] = {}
                self.assertEqual(stages.survey(going).next.name, 'intake-source')
                self.assertEqual(decks.state(going), decks.state(run(route, level)))


class NameTests(unittest.TestCase):
    def test_balanced_puts_the_direction_review_under_the_look(self):
        balanced = run('scratch')
        balanced['review_policy'] = {'schema': 1, 'level': 'balanced'}
        found = next(s for s in stages.steps(balanced) if s.name == 'gate:outline')
        self.assertEqual((found.stage, found.label), ('look', 'Review the direction'))
        stepped = next(s for s in stages.steps(run('scratch')) if s.name == 'gate:outline')
        self.assertEqual(stepped.stage, 'outline')

    def test_the_classify_stop_says_what_you_gave(self):
        self.assertEqual(stages.BY_NAME['gate:classify'].label, 'Confirm what you gave')

    def test_the_look_stop_is_named_choose_the_look(self):
        self.assertEqual(stages.BY_NAME['gate:look'].label, 'Choose the look')
        self.assertEqual(stages.BY_NAME['gate:look'].doing, 'Waiting for you to choose the look')


class SkipMapTests(unittest.TestCase):
    CASES = [
        (run('scratch'), ['intake-source', 'outline', 'gate:outline', 'brand',
                          'look-preview', 'gate:look', 'build-start', 'build-sections',
                          'build-whole', 'build-review', 'build-repair', 'build-render',
                          'gate:build', 'deliver']),
        (run('existing', 'brand-only'), ['intake-source', 'inventory', 'gate:classify',
                                         'extract', 'brand', 'build-start', 'build-sections',
                                         'build-whole', 'build-review', 'build-repair',
                                         'build-render', 'gate:build', 'deliver']),
        (run('existing', 'selected'), ['intake-source', 'inventory', 'gate:classify', 'brand',
                                       'patch', 'build-render', 'gate:build', 'deliver']),
        (run('existing', 'rework'), ['intake-source', 'inventory', 'gate:classify', 'extract',
                                     'outline', 'gate:outline', 'brand', 'look-preview',
                                     'gate:look', 'build-start', 'build-sections', 'build-whole',
                                     'build-review', 'build-repair', 'build-render',
                                     'gate:build', 'deliver']),
    ]

    def test_cases(self):
        for r, expected in self.CASES:
            with self.subTest(route=r['route'], level=r['form'].get('level')):
                self.assertEqual(names(r), expected)

    def test_research_only_when_asked(self):
        self.assertIn('research-plan', names(run('scratch', research=True)))
        self.assertNotIn('research-plan', names(run('scratch')))

    def test_document_research_only_for_material(self):
        self.assertNotIn('research', names(run('document', research=True, classified='spec')))
        self.assertIn('research', names(run('document', research=True, classified='material')))

    def test_polish_and_brand_only_skip_look(self):
        for level in ('brand-only', 'polish'):
            self.assertNotIn('gate:look', names(run('existing', level)))
        self.assertIn('gate:look', names(run('existing', 'redesign')))


class SurveyTests(unittest.TestCase):
    def test_first_step_is_next(self):
        self.assertEqual(stages.survey(run('scratch')).next.name, 'intake-source')

    def test_waiting_gate(self):
        r = run('scratch')
        r['steps'] = {'intake-source': {'done': True}, 'outline': {'done': True}}
        r['gates'] = {'gate:outline': {'state': 'waiting'}}
        found = stages.survey(r)
        self.assertEqual(found.waiting, 'gate:outline')

    def test_changes_go_back_to_the_feeding_step(self):
        r = run('scratch')
        r['steps'] = {'intake-source': {'done': True}, 'outline': {'done': True}}
        r['gates'] = {'gate:outline': {'state': 'changes', 'note': 'shorter'}}
        r = stages.reopen(r, 'gate:outline')
        self.assertEqual(stages.survey(r).next.name, 'outline')

    def test_finished_deck_has_no_next(self):
        r = run('existing', 'selected')
        for s in stages.steps(r):
            if s.kind == 'gate':
                r['gates'][s.name] = {'state': 'approved'}
            else:
                r['steps'][s.name] = {'done': True}
        self.assertIsNone(stages.survey(r).next)

    def test_the_last_row_of_the_timeline_is_the_delivery(self):
        rows = stages.timeline(run('scratch'))
        self.assertEqual((rows[-1]['name'], rows[-1]['state']), ('deliver', 'upcoming'))


class FeedAndReopenTests(unittest.TestCase):
    def test_feeders(self):
        self.assertEqual(stages.feeder(run('existing', 'polish'), 'gate:classify'), 'inventory')
        self.assertEqual(stages.feeder(run('document'), 'gate:classify'), 'classify')
        self.assertEqual(stages.feeder(run('existing', 'selected'), 'gate:build'), 'patch')
        r = run('scratch')
        self.assertEqual(stages.feeder(r, 'gate:build'), 'build-sections')
        r['gates'] = {'gate:build': {'state': 'changes', 'slides': [3]}}
        self.assertEqual(stages.feeder(r, 'gate:build'), 'build-repair')
        # Another brand is chosen at the brand's gate: its cover is drawn again, by the runner.
        self.assertEqual(stages.feeder(r, 'gate:look'), 'look-preview')
        self.assertEqual(stages.BY_NAME['look-preview'].kind, 'code')

    def test_reopen_clears_later_work_and_approvals(self):
        r = run('scratch')
        r['steps'] = {s.name: {'done': True} for s in stages.steps(r) if s.kind != 'gate'}
        r['gates'] = {n: {'state': 'approved'} for n in ('gate:outline', 'gate:look', 'gate:build')}
        r['gates']['gate:outline'] = {'state': 'changes', 'note': 'shorter'}
        out = stages.reopen(r, 'gate:outline')
        self.assertTrue(r['steps']['outline']['done'])  # the original is untouched
        self.assertFalse(out['steps']['outline']['done'])
        self.assertFalse(out['steps']['build-render']['done'])
        self.assertTrue(out['steps']['intake-source']['done'])
        self.assertEqual(out['gates']['gate:look']['state'], 'absent')
        self.assertEqual(out['gates']['gate:outline'], {'state': 'changes', 'note': 'shorter'})

    def test_halted_and_wording(self):
        r = run('scratch')
        r['halted'] = {'why': 'out of credit'}
        self.assertEqual(stages.survey(r).halted, 'out of credit')
        for s in stages.PIPELINE:
            for word in ('artifact', 'stale', 'lineage', '{'):
                self.assertNotIn(word, (s.label + s.doing).lower())
