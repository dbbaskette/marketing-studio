"""A research run that has kept nothing moves to the installed Harness Research when it is newer."""
import copy
import json
from pathlib import Path
import tempfile
import threading
import unittest

import marketing_studio  # noqa: F401
from studio_core import research_contract as rc, research_session as parallel, research_transport as transport


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

    def test_a_run_that_has_kept_nothing_moves_to_the_newer_installed_helper(self):
        (self.root / rc.CASE / ('a' * 64) / 'inputs').mkdir(parents=True)   # captured inputs are the studio's own
        engine, record = self.move(self.new)
        self.assertEqual(record['research_contract'], rc.capability(self.new))
        self.assertEqual(record['research_execution']['capability'], parallel.capability(self.new))
        self.assertEqual((engine.record, engine.stored), (record, 1))
        self.assertEqual(rc.matching(engine.research(), record['research_contract']).runtime, self.new)

    def test_a_run_with_saved_research_stays_with_the_helper_that_wrote_it(self):
        for kept in ('a' * 64 + '/topic', 'current.json'):
            with self.subTest(kept=kept):
                path = self.root / rc.CASE / kept
                path.parent.mkdir(parents=True, exist_ok=True)
                path.mkdir() if kept.endswith('topic') else path.write_text('{}')
                engine, record = self.move(self.new)
                self.assertEqual((record, engine.stored), (self.record, 0))
                path.rmdir() if path.is_dir() else path.unlink()

    def test_an_installed_helper_that_is_not_a_newer_release_changes_nothing(self):
        self.record = {'research_contract': rc.capability(self.new), 'research_execution': parallel.execution(self.new)}
        for installed in (self.old, self.new, helper(self.root.parent / 'pre', '1.3.0-alpha.1')):
            engine, record = self.move(installed)
            self.assertEqual((record, engine.stored), (self.record, 0))


if __name__ == '__main__':
    unittest.main()
