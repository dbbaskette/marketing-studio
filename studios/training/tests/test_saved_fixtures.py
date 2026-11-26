"""The stored saved-flow fixtures (`saved_fixtures.py`) agree with themselves (GitHub issue
#542): every material, approval and input digest a stored record keeps is the hash of the
stored file it names, and every content-addressed file is named by its bytes. The trees were
captured from the earlier gated flow while it existed; that flow, and the capture that proved
each tree against it, went with phase C. The trees are never rewritten.
"""
import hashlib
import json
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
            self.assertEqual(stored_builders.key(tree['steps']), name)


class ConversationTreeTests(StudioCase):
    """The stored conversation-guided trainings (GitHub issue #547), captured with
    `capture_conversation.py`, agree with themselves and with this computer's helper."""

    PROFILE = 'skills/training-studio/assets/profiles/yoodli.json'

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

    def test_a_yoodli_scenario_was_built_from_the_installed_profile(self):
        """A stored Yoodli scenario records the digest of the profile it was built from. When
        the installed profile changes, the stored scenario reads as out of date, and the
        trees that hold one are captured again."""
        import helpers
        profile = hashlib.sha256((helpers.REPO / self.PROFILE).read_bytes()).hexdigest()
        checked = 0
        for state in saved_fixtures.conversation_names():
            files = saved_fixtures.conversation_tree(state)
            try:
                session = json.loads(files[saved_fixtures.SESSION])
            except ValueError:
                continue
            for name, entry in session['artifacts'].items():
                for digests in (entry['built_from'],
                                (entry.get('approved') or {}).get('inputs') or {}):
                    if 'profile' not in digests:
                        continue
                    checked += 1
                    self.assertEqual(digests['profile'], profile, (
                        f'{self.PROFILE} changed since {state} was captured, so its {name} '
                        'reads as out of date. Capture the trees that hold a Yoodli scenario '
                        'again: STUDIO_TEST_RESEARCH_RUNTIME=<a Harness Research test '
                        'runtime> python3 studios/training/tests/capture_conversation.py '
                        'scenario_gate finished'))
        self.assertTrue(checked)
