"""The stored saved decks are what the earlier step-by-step flow writes.

PROOF OF FIDELITY, TO BE DELETED WITH THE SAVED FLOW (GitHub issue #542, phase C): each
test makes one state of `saved_fixtures.STATES` again by running the saved flow in a
disposable workspace, and compares it with the tree stored under tests/fixtures/saved/.
Only what differs on every run is put aside (`saved_fixtures.VOLATILE`: times, durations
and the slides stand-in's random round folders). To capture a state again after a change
to the flow: `python3 tests/saved_fixtures.py --write STATE`.
"""
import json
import unittest

import runner_support
import saved_fixtures


class SavedFixtureFidelityTests(runner_support.DeskCase):

    def test_every_stored_state_is_what_the_saved_flow_writes(self):
        self.assertEqual(sorted(path.name for path in saved_fixtures.STORE.iterdir()),
                         sorted(saved_fixtures.STATES))
        for state in saved_fixtures.STATES:
            # What each scrubbed file held as written is a digest, nothing more.
            for relative, digest in saved_fixtures.scrubbed(state).items():
                self.assertRegex(digest, '^[0-9a-f]{64}$', f'{state}: {relative}')
        for state in saved_fixtures.STATES:
            with self.subTest(state):
                case = saved_fixtures._case()
                try:
                    name, made, _ = saved_fixtures.capture(case, state)
                finally:
                    case.doCleanups()
                kept_name, kept = saved_fixtures.stored(state)
                self.assertEqual(name, kept_name)
                made, kept = saved_fixtures.normal(made), saved_fixtures.normal(kept)
                self.assertEqual([name for name, _ in made], [name for name, _ in kept])
                for (relative, data), (_, stored) in zip(made, kept):
                    self.assertEqual(data, stored, f'{state}: {relative}')

    def test_nothing_stored_names_this_computer_or_a_temporary_folder(self):
        for state in saved_fixtures.STATES:
            _, files = saved_fixtures.stored(state)
            for relative, data in files.items():
                with self.subTest(state=state, file=relative):
                    for said in (b'/Users/', b'/home/', b'/private/', b'/var/folders/', b'/tmp/'):
                        self.assertNotIn(said, data)

    def test_a_loaded_state_is_the_stored_deck_committed_here(self):
        root = saved_fixtures.load(self, 'build')
        name, files = saved_fixtures.stored('build')
        self.assertEqual(root.name, name)
        self.assertEqual((root / 'run.json').read_bytes(), files['run.json'])
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertEqual(self.view(root)['gate']['name'], 'gate:build')
        other = saved_fixtures.load(self, 'build', title='Another copy')
        self.assertEqual(other.name, 'another-copy')
        record = json.loads((other / 'run.json').read_text())
        self.assertEqual((record['id'], record['title'], record['form']['title']),
                         ('another-copy', 'Another copy', 'Another copy'))
        self.assertNotIn('@DECK@', (other / 'work/build/state.json').read_text())


if __name__ == '__main__':
    unittest.main()
