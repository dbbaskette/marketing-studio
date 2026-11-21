"""Every research run moves to the installed Harness Research, and what it saved stays its own.

Row 242 of the Training Studio state-transition matrix: an update of Harness Research never
makes finished research, its sections or its review run again.
"""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock

import marketing_studio  # noqa: F401
from studio_core import research_contract as rc, research_session as parallel, research_transport as transport
from studio_core import research_impact, research_sections


def helper(folder, version):
    """A synthetic helper with the files a capability is read from."""
    folder = Path(folder)
    for name, text in {'package.json': json.dumps({'version': version}),
                       'scripts/lib/synthesis-cli.mjs': '// synthetic ' + version,
                       'scripts/lib/collection.mjs': '// synthetic', 'scripts/lib/topic-assets.mjs': '// synthetic',
                       'references/collection.schema.json': json.dumps({'$schema': 'synthetic'}),
                       'references/investigation-packet.md': 'Synthetic.', 'references/parallel-research.md': 'Synthetic.'}.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_text(text)
    return folder


class Tool:
    def __init__(self, runtime): self.runtime = runtime


class Engine:
    def __init__(self, record, runtime):
        self.files, self.record, self.tool, self.stored = threading.RLock(), record, Tool(runtime), 0
    def research(self): return self.tool
    def _load(self, root): return copy.deepcopy(self.record)
    def _store(self, root, record): self.record, self.stored = copy.deepcopy(record), self.stored + 1


class MoveTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        base = Path(temp.name).resolve()
        self.old, self.new = helper(base / 'old', '1.1.0'), helper(base / 'new', '1.2.0')
        self.root = base / 'work'; self.root.mkdir()
        self.record = {'research_contract': rc.capability(self.old),
                       'research_execution': parallel.execution(self.old)}

    def move(self, installed):
        engine = Engine(self.record, installed)
        return engine, transport.move_to_installed(engine, self.root, engine._load(self.root), 'presentation')

    def test_a_run_that_has_kept_nothing_moves_to_the_installed_helper(self):
        (self.root / rc.CASE / ('a' * 64) / 'inputs').mkdir(parents=True)   # captured inputs are the studio's own
        engine, record = self.move(self.new)
        self.assertEqual(record['research_contract'], rc.capability(self.new))
        self.assertEqual(record['research_execution']['capability'], parallel.capability(self.new))
        self.assertEqual((engine.record, engine.stored), (record, 1))
        self.assertIs(rc.matching(engine.research(), record['research_contract']), engine.research())

    def test_a_run_with_saved_research_moves_too_and_keeps_what_it_held(self):
        for kept in ('a' * 64 + '/topic', 'current.json'):
            with self.subTest(kept=kept):
                path = self.root / rc.CASE / kept
                path.parent.mkdir(parents=True, exist_ok=True)
                path.mkdir() if kept.endswith('topic') else path.write_text('{}')
                engine, record = self.move(self.new)
                self.assertEqual(engine.stored, 1)
                self.assertEqual(record['research_contract'], rc.capability(self.new))
                self.assertEqual(record['research_execution']['earlier'], {
                    'research_contract': rc.capability(self.old),
                    'capability': parallel.capability(self.old), 'reuse': None})
                path.rmdir() if path.is_dir() else path.unlink()

    def test_any_installed_version_is_moved_to_and_the_first_earlier_is_kept(self):
        engine, record = self.move(self.new)
        engine.tool = Tool(helper(self.root.parent / 'pre', '1.0.0-alpha.1'))
        again = transport.move_to_installed(engine, self.root, record, 'presentation')
        self.assertEqual(again['research_contract']['version'], '1.0.0-alpha.1')
        self.assertEqual(again['research_execution']['earlier']['research_contract'], rc.capability(self.old))

    def test_the_same_installed_helper_changes_nothing(self):
        engine, record = self.move(self.old)
        self.assertEqual((record, engine.stored), (self.record, 0))

    def test_a_contract_run_without_collection_moves_its_label_only(self):
        self.record = {'research_contract': rc.capability(self.old)}
        engine, record = self.move(self.new)
        self.assertEqual(record, {'research_contract': rc.capability(self.new)})


class StableIdentityTests(unittest.TestCase):
    """Row 242: what decides whether research is still current names the helper's protocol,
    never its version or digest; and what an older Marketing Studio kept, digest and all, is
    the same research."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        base = Path(temp.name).resolve()
        self.old, self.new = helper(base / 'old', '1.1.0'), helper(base / 'new', '1.3.1')
        self.root = base / 'work'; self.root.mkdir()
        self.record = {'form': {'topic': 'Synthetic'}, 'research_contract': rc.capability(self.old),
                       'research_execution': parallel.execution(self.old)}

    def moved(self):
        engine = Engine(self.record, self.new)
        return transport.move_to_installed(engine, self.root, engine._load(self.root), 'presentation')

    def test_the_case_keeps_its_name_across_an_update(self):
        task, inputs, areas = {'topic': 'Synthetic'}, [['a.txt', None, 'selected', 'x', None]], [{'id': 'area-1'}]
        before = parallel.case_basis(self.root, task, inputs, parallel.capability(self.old), areas)
        after = parallel.case_basis(self.root, task, inputs, parallel.capability(self.new), areas)
        self.assertEqual(before, after)

    def test_a_case_an_older_studio_named_by_its_digest_is_still_found(self):
        task, inputs, areas = {'topic': 'Synthetic'}, [], [{'id': 'area-1'}]
        old_capability = parallel.capability(self.old)
        legacy = parallel.digest([task, inputs, old_capability, areas])
        (self.root / rc.CASE / legacy / 'topic').mkdir(parents=True)
        found = parallel.case_basis(self.root, task, inputs, parallel.capability(self.new), areas, old_capability)
        self.assertEqual(found, legacy)
        # A case of the stable name, once there, is the one used.
        stable = parallel.case_basis(self.root, task, inputs, parallel.capability(self.new), areas)
        (self.root / rc.CASE / stable / 'topic').mkdir(parents=True)
        self.assertEqual(parallel.case_basis(self.root, task, inputs, parallel.capability(self.new), areas,
                                             old_capability), stable)

    def test_the_global_identity_survives_an_update_and_an_older_one_is_recognised(self):
        before = research_impact.global_identity(self.record)
        older = research_impact.global_identity(self.record, older=True)   # as an older studio kept it
        record = self.moved()
        self.assertEqual(research_impact.global_identity(record), before)
        self.assertTrue(research_impact.same_global(before, record))
        self.assertTrue(research_impact.same_global(older, record))
        self.assertFalse(research_impact.same_global('0' * 64, record))
        current = {'schema': 1, 'global': research_impact.global_identity(record), 'sources': [], 'questions': []}
        self.assertTrue(research_impact.same_input({**current, 'global': older}, current, record))
        self.assertFalse(research_impact.same_input({**current, 'sources': [{'name': 'a'}]}, current, record))

    def test_a_section_kept_under_an_older_key_is_kept_and_keyed_anew(self):
        case = self.root / 'case'
        (case / '.harness-research').mkdir(parents=True)
        (case / 'source.txt').write_text('Synthetic source.')
        area = {'id': 'area-1', 'questions': [{'id': 'q1', 'question': 'Why?'}]}
        task = {key: 'Synthetic' for key in rc.TASK_FIELDS}
        task['planning_questions'] = area['questions']
        base = {'schema': 2, **{key: task[key] for key in rc.TASK_FIELDS},
                'sources': [{'id': 's1', 'file': 'source.txt', 'permission': 'public', 'origin': 'https://example.invalid'}],
                'facts': [{'id': 'f1', 'statement': 'A synthetic fact.', 'author': 'w',
                           'citations': [{'source': 's1', 'quote': 'Synthetic source.'}]}]}
        registry = {'mappings': [{'workstream': 'area-1', 'facts': {'f1': 'f1'}}], 'gaps': []}
        offered = [{'file': 'source.txt'}]
        stable = {'recipe': research_sections.PROTOCOL, 'helper': rc.stable(parallel.capability(self.new))}
        earlier = {'recipe': research_sections.PROTOCOL, 'helper': parallel.capability(self.old)}
        content = {'findings': [{'id': 'q1', 'statement': 'Kept.', 'support': ['f1']}],
                   'sections': [{'id': 'q1', 'title': 'Kept', 'blocks': [{'text': 'Kept prose.'}]}]}
        calls = []

        def invoke(phase, guidance, payload, sources, fetch):
            calls.append(payload['_execution']['section'])
            return json.dumps({'schema': 2, 'sections': [{'id': 'intro', 'title': 'Intro', 'blocks': [{'text': 'Intro.'}]}],
                               'brief': [{'text': 'Brief.'}]}), []

        def combine(context, earlier_context=None):
            return research_sections.combine(case, task, [area], registry, base, offered, invoke, round=1,
                guidance='', policy={'seconds': 60, 'more_time': {}, 'workers': 1}, require=lambda: None,
                notify=lambda rows: None, context=context, earlier=earlier_context)

        # Keyed as an older Marketing Studio keyed it, with the helper's digest in its context.
        with mock.patch.object(research_sections.research_quality, 'prose', lambda value, policy=None: None):
            path = case / '.harness-research/studio-combining.json'
            first = []
            def capture(phase, guidance, payload, sources, fetch):
                first.append(payload['_execution']['section'])
                if payload['_execution']['section'] == 'final':
                    return invoke(phase, guidance, payload, sources, fetch)
                # The job hands back its section over the evidence it was given, as the tool does.
                return json.dumps({**payload['_execution']['evidence_base'], **content}), []
            research_sections.combine(case, task, [area], registry, base, offered, capture, round=1,
                guidance='', policy={'seconds': 60, 'more_time': {}, 'workers': 1}, require=lambda: None,
                notify=lambda rows: None, context=earlier)
            self.assertEqual(first, ['area-1', 'final'])
            older_key = json.loads(path.read_text())['sections']['area-1']['basis']
            calls.clear()
            combine(stable, earlier)
            self.assertEqual(calls, [])   # neither the section nor the final is written again
            saved = json.loads(path.read_text())
            self.assertNotEqual(saved['sections']['area-1']['basis'], older_key)
            combine(stable)
            self.assertEqual(calls, [])   # and it is kept under its new key


if __name__ == '__main__':
    unittest.main()
