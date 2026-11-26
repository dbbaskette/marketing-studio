"""The stored saved-flow fixtures (`saved_fixtures.py`) agree with themselves (GitHub issue
#542): every material, approval and input digest a stored record keeps is the hash of the
stored file it names, and every content-addressed file is named by its bytes. The trees were
captured from the earlier gated flow while it existed; that flow, and the capture that proved
each tree against it, went with phase C. The trees are never rewritten.
"""
import hashlib
import json
from pathlib import Path
import re

import saved_fixtures
from runner_support import StudioCase


class StoredTreeTests(StudioCase):
    """Each stored tree agrees with itself, so the approvals the migration tests rely on are
    approvals of the stored materials."""

    def test_material_and_approval_digests_are_the_stored_materials(self):
        for state in saved_fixtures.names():
            files = saved_fixtures.tree(state)
            session = json.loads(files[saved_fixtures.SESSION])
            checked = 0
            for name, entry in session['artifacts'].items():
                with self.subTest(state=state, artifact=name):
                    self.assertIn(entry['file'], files)
                    made = hashlib.sha256(files[entry['file']]).hexdigest()
                    self.assertEqual(entry['sha256'], made)
                    if entry.get('approved'):
                        self.assertEqual(entry['approved']['sha256'], made)
                        checked += 1
            # Every stored state past its intake holds at least one real approval.
            self.assertTrue(checked, state)

    def test_every_input_digest_is_the_stored_inputs(self):
        """Each digest a stored tree keeps of what a material was built from, and of what
        its approval was given for, is the digest of that input as stored: a tree whose
        approval inputs no longer match their files fails here."""
        import workspace
        checked = set()
        for state in saved_fixtures.names():
            root = saved_fixtures.load(self, state)
            session = workspace.load(root)
            for name, entry in session['artifacts'].items():
                current = workspace.inputs(root, session, name)
                for where, digests in (('built_from', entry.get('built_from') or {}),
                                       ('approved', (entry.get('approved') or {}).get('inputs') or {})):
                    for key, value in digests.items():
                        with self.subTest(state=state, artifact=name, where=where, input=key):
                            self.assertIn(key, current)
                            self.assertEqual(value, current[key])
                            checked.add(key)
            # A changed input is told apart: the check is not one that always holds.
            if 'blueprint' in session['artifacts']:
                report = root / '.harness-research' / 'research-report.md'
                before = workspace.inputs(root, session, 'blueprint')['research']
                report.write_text(report.read_text() + '\nChanged.\n')
                self.assertNotEqual(workspace.inputs(root, session, 'blueprint')['research'],
                                    before)
        self.assertLessEqual({'intake', 'research', 'blueprint'}, checked)

    def test_content_addressed_files_are_named_by_their_bytes(self):
        named = re.compile(r'(?:^|/)history/.+/([0-9a-f]{64})\.[a-z]+$')
        seen = 0
        for state in saved_fixtures.names():
            for name, data in saved_fixtures.tree(state).items():
                found = named.search(name)
                if found:
                    seen += 1
                    with self.subTest(state=state, file=name):
                        self.assertEqual(hashlib.sha256(data).hexdigest(), found.group(1))
        self.assertTrue(seen)


class StoredBuilderTreeTests(StudioCase):
    """The trees the conversation builders place (`stored_builders.py`, GitHub issue #547):
    every file a tree names is stored once under its own digest, and nothing else is."""

    def test_every_stored_file_is_named_by_its_bytes_and_used(self):
        import stored_builders
        stored = json.loads(stored_builders.TREES.read_text(encoding='utf-8'))
        named = {sha for tree in stored.values() for sha in tree['files'].values()}
        on_disk = {path.name for path in stored_builders.BLOBS.iterdir()}
        self.assertEqual(named, on_disk)
        for name in on_disk:
            data = (stored_builders.BLOBS / name).read_bytes()
            self.assertEqual(hashlib.sha256(data).hexdigest(), name)
            for mark in (b'/Users/', b'/home/', b'/var/folders/', b'/private/', b'/tmp/'):
                self.assertNotIn(mark, data, name)
        for name, tree in stored.items():
            # A builder's tree is keyed by its steps; a state a test's own helper command
            # reached, by what the training held and the command (`replay`).
            if 'steps' in tree:
                self.assertEqual(stored_builders.key(tree['steps']), name)
            else:
                self.assertTrue(name.startswith('t-') and tree['step'], name)


class ConversationTreeTests(StudioCase):
    """The stored conversation-guided trainings (GitHub issue #547) agree with themselves and
    with this computer's helper. They were captured by driving the helper's commands that
    continued such a training; those commands are gone, so the trees are the only record of
    what the helper wrote and cannot be captured again."""

    PROFILE = 'skills/training-studio/assets/profiles/yoodli.json'
    # The Yoodli profile the stored scenarios were built from.
    STORED_PROFILE = 'f676978ae778d231cadf41e0a99fe09da8d814cd522d52ebb08d40b1246192b8'
    # The installed profile whose effect on saved Yoodli scenarios was last decided.
    DECIDED_PROFILE = 'f676978ae778d231cadf41e0a99fe09da8d814cd522d52ebb08d40b1246192b8'

    def test_content_addressed_files_are_named_by_their_bytes(self):
        named = re.compile(r'(?:^|/)history/.+/([0-9a-f]{64})\.[a-z]+$')
        seen = 0
        for state in saved_fixtures.conversation_names():
            for name, data in saved_fixtures.conversation_tree(state).items():
                found = named.search(name)
                if found:
                    seen += 1
                    with self.subTest(state=state, file=name):
                        self.assertEqual(hashlib.sha256(data).hexdigest(), found.group(1))
        self.assertTrue(seen)

    def test_no_stored_byte_names_a_place_on_a_computer(self):
        for state in saved_fixtures.conversation_names():
            for name, data in saved_fixtures.conversation_tree(state).items():
                for mark in (b'/Users/', b'/home/', b'/var/folders/', b'/private/', b'/tmp/'):
                    with self.subTest(state=state, file=name, mark=mark):
                        self.assertNotIn(mark, data)

    def built_from(self) -> dict[str, set[str]]:
        """The Yoodli profile digest each stored state's scenarios were built from."""
        found: dict[str, set[str]] = {}
        for state in saved_fixtures.conversation_names():
            files = saved_fixtures.conversation_tree(state)
            try:
                session = json.loads(files[saved_fixtures.SESSION])
            except ValueError:
                continue
            for entry in session['artifacts'].values():
                for digests in (entry['built_from'],
                                (entry.get('approved') or {}).get('inputs') or {}):
                    if 'profile' in digests:
                        found.setdefault(state, set()).add(digests['profile'])
        return found

    def test_the_stored_yoodli_scenarios_were_built_from_one_profile(self):
        """The stored trees are history: what the retired helper wrote, which cannot be
        captured again. Their Yoodli scenarios were all built from the profile installed
        then, whose digest is STORED_PROFILE."""
        found = self.built_from()
        self.assertTrue(found)
        self.assertEqual({digest for digests in found.values() for digest in digests},
                         {self.STORED_PROFILE})

    def test_nothing_asks_for_the_stored_trees_to_be_captured_again(self):
        """The commands that made the stored trees are gone: no capture script is kept, no
        test asks for one, and a missing stored state says how to reach it instead."""
        import tempfile
        import stored_builders
        here = Path(__file__).resolve().parent
        old = ('capture' + '_conversation', 'TRAINING_STUDIO_RECORD' + '_BUILDERS')
        self.assertFalse((here / (old[0] + '.py')).exists())
        for path in here.rglob('*.py'):
            text = path.read_text(encoding='utf-8')
            for word in old:
                with self.subTest(file=path.name, word=word):
                    self.assertNotIn(word, text)
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(AssertionError) as missing:
                stored_builders.replay(folder, 'training.py', ['save', 'nothing-stored'])
        self.assertIn(stored_builders.CANNOT_RECORD, str(missing.exception))

    def test_a_changed_yoodli_profile_is_decided_for_saved_scenarios(self):
        """A Yoodli scenario a conversation saved records the profile it was built from. A
        changed profile makes every such scenario, saved by a person or stored here, read as
        out of date once it is brought in. That is a decision about saved work, so a changed
        profile fails here until it is made; the stored trees stay as they are."""
        import helpers
        today = hashlib.sha256((helpers.REPO / self.PROFILE).read_bytes()).hexdigest()
        held = sorted(self.built_from())
        self.assertEqual(today, self.DECIDED_PROFILE, (
            f'{self.PROFILE} has changed since its effect on saved work was last decided. '
            'A Yoodli scenario saved with an earlier profile now reads as out of date when it '
            f'is brought in, as do the stored states that hold one ({", ".join(held)}). The '
            'stored trees cannot be captured again and stay as they are. Decide whether saved '
            'Yoodli scenarios should read as out of date with this profile; run '
            'tests/test_conversation_states.py to see what that does to their outcomes; then '
            f'set DECIDED_PROFILE in this test to {today}.'))
