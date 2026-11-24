"""The stored saved decks are what the earlier step-by-step flow writes.

PROOF OF FIDELITY, TO BE DELETED WITH THE SAVED FLOW (GitHub issue #542, phase C): each
test makes one state of `saved_fixtures.STATES` again by running the saved flow in a
disposable workspace, and compares it with the tree stored under tests/fixtures/saved/.
Only what differs between runs is put aside, each item named in saved_fixtures (TIMES,
DURATIONS, GOOGLE, TOKENS); digests and random names are matched consistently, not masked,
and nothing inside a file is re-ordered. The researched states need the pinned Harness
Research helper the suites name in STUDIO_TEST_RESEARCH_RUNTIME, and are compared only
where it is set. To capture a state again after a change to the flow:
`python3 tests/saved_fixtures.py --write STATE`.
"""
import hashlib
import json
import re
import unittest
from pathlib import PurePosixPath

import runner_support
import saved_fixtures

DIGEST = re.compile(r'^[0-9a-f]{64}$')
# A pin written in words, as a drawing's brief writes it: `outline.json`, SHA-256 `…`.
SAID = re.compile(r'`([^`]+)`, SHA-256 `([0-9a-f]{64})`')


def pins(files: dict) -> list:
    """Every pin in a stored deck that names one of its stored files: (pinning file, named
    file, digest). A JSON object pins a file by a SHA-256 beside its path; a brief pins one
    in words; an inventory pins the deck it read."""
    found = []

    def resolve(here, named):
        named = named.replace('@DECK@/', '')
        for candidate in (str(PurePosixPath(here).parent / named), named):
            if candidate in files:
                return candidate
        return None

    def walk(here, value):
        if isinstance(value, dict):
            digest = value.get('sha256') or value.get('digest')
            if isinstance(digest, str) and DIGEST.fullmatch(digest):
                for key in ('path', 'file', 'original', 'name', 'output'):
                    named = value.get(key)
                    target = resolve(here, named) if isinstance(named, str) else None
                    if target:
                        found.append((here, target, digest))
            for item in value.values():
                walk(here, item)
        elif isinstance(value, list):
            for item in value:
                walk(here, item)

    for here, data in files.items():
        if here.endswith('.json'):
            try:
                walk(here, json.loads(data))
            except ValueError:
                continue
        elif here.endswith('.md'):
            for named, digest in SAID.findall(data.decode('utf-8', 'replace')):
                target = resolve(here, named)
                if target:
                    found.append((here, target, digest))
    if 'classify.json' in files and 'sources/original.pptx' in files:
        try:
            digest = json.loads(files['classify.json']).get('sha256')
        except ValueError:
            digest = None
        if digest:
            found.append(('classify.json', 'sources/original.pptx', digest))
    return found


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
                if state in saved_fixtures.RESEARCHED and not saved_fixtures.RUNTIME:
                    self.skipTest('Set STUDIO_TEST_RESEARCH_RUNTIME to capture researched states.')
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

    def test_the_comparison_sees_a_broken_pin_and_a_changed_order(self):
        _, files = saved_fixtures.stored('build')
        kept = saved_fixtures.normal(files)
        self.assertEqual(saved_fixtures.normal(dict(files)), kept)
        # A pin that no longer names what the other records name: the brand contract's
        # revision, as the design guide states it.
        revision = json.loads(files['brand/brand-contract.json'])['revision'].encode()
        self.assertIn(revision, files['brand/DESIGN.md'])
        broken = {**files, 'brand/DESIGN.md': files['brand/DESIGN.md'].replace(revision, b'0' * 63 + b'a')}
        self.assertNotEqual(saved_fixtures.normal(broken), kept)
        # A pin that no longer names the bytes of the file it names: the comparison of two
        # captures cannot see it, as both name their own; the pin check over the stored
        # trees does (test_every_pin_in_a_stored_deck_names_its_stored_bytes).
        here, target, digest = next(pin for pin in pins(files)
                                    if pin[0] == 'work/build/start/presentation-brief.md')
        self.assertEqual(digest, hashlib.sha256(files[target]).hexdigest())
        # Two slides of the outline the other way round.
        outline = json.loads(files['outline.json'])
        outline['slides'][1], outline['slides'][2] = outline['slides'][2], outline['slides'][1]
        swapped = {**files, 'outline.json': (json.dumps(outline, indent=2) + '\n').encode()}
        self.assertNotEqual(saved_fixtures.normal(swapped), kept)
        # Only what varies between runs is put aside: a time and a measured duration.
        record = files['run.json'].decode()
        when = re.search(r'\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ', record).group()
        later = {**files, 'run.json': record.replace(when, '2030-01-01T00:00:00Z', 1).encode()}
        self.assertEqual(saved_fixtures.normal(later), kept)

    def test_every_pin_in_a_stored_deck_names_its_stored_bytes(self):
        counted = {}
        for state in saved_fixtures.STATES:
            _, files = saved_fixtures.stored(state)
            # A scrubbed file was pinned as it was written, before its places were scrubbed.
            written = {relative: digest for relative, digest in saved_fixtures.scrubbed(state).items()}
            found = pins(files)
            counted[state] = len(found)
            for here, target, digest in found:
                with self.subTest(state=state, pin=here, names=target):
                    self.assertEqual(digest, written.get(target)
                                     or hashlib.sha256(files[target]).hexdigest())
        # The check is not empty: drawn, read and researched decks pin their files.
        for state in ('build', 'delivered', 'selected', 'researched', 'researched-parallel'):
            self.assertGreater(counted[state], 0, state)
        self.assertGreater(sum(counted.values()), 50)

    def test_nothing_stored_names_this_computer_or_a_temporary_folder(self):
        for state in saved_fixtures.STATES:
            _, files = saved_fixtures.stored(state)
            for relative, data in files.items():
                with self.subTest(state=state, file=relative):
                    for said in (b'/Users/', b'/home/', b'/private/', b'/var/folders/', b'/tmp/',
                                 b'hr-epic'):
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
