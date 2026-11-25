"""The stored saved decks under tests/fixtures/saved/ agree with themselves: every pin names the
stored bytes, nothing names this computer or a temporary folder, and a loaded copy is the
stored deck. (The capture that compared each state with a fresh run of the earlier
step-by-step flow went with that flow: GitHub issue #542.)
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
        # Its saved stop is kept as the flow left it; the page shows it as a saved record.
        self.assertEqual(self.record(root)['gates']['gate:build']['state'], 'waiting')
        other = saved_fixtures.load(self, 'build', title='Another copy')
        self.assertEqual(other.name, 'another-copy')
        record = json.loads((other / 'run.json').read_text())
        self.assertEqual((record['id'], record['title'], record['form']['title']),
                         ('another-copy', 'Another copy', 'Another copy'))
        self.assertNotIn('@DECK@', (other / 'work/build/state.json').read_text())


if __name__ == '__main__':
    unittest.main()
