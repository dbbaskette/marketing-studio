"""Each test file runs on its own as well as in the suite (GitHub issue #544).

`helpers` puts the skill's scripts on the import path and `runner_support` (or a file's own
`sys.path.insert`) puts the studio's folder there, so a file that imports `runner` before
either of them imports only when another file has already done it: in the suite, never
alone. Nothing here starts an agent or touches the network.
"""
import ast
import os
import subprocess
import sys
import unittest
from pathlib import Path

import helpers

TESTS = Path(__file__).resolve().parent


def _imported(node: ast.stmt) -> list[str]:
    """The top-level names a statement imports."""
    if isinstance(node, ast.Import):
        return [alias.name.split('.')[0] for alias in node.names]
    if isinstance(node, ast.ImportFrom) and not node.level:
        return [(node.module or '').split('.')[0]]
    return []


def _reads(name: str, known: dict) -> tuple[str, int | None]:
    """How a module of this folder reaches `runner`, read from its top-level statements in
    order: ('sets', None) once it has put the studio's folder on the import path, ('late',
    line) when it imports `runner` first, ('neither', None) when it does neither. A
    `sys.path` statement that names `REPO` puts the folder there, and so does importing a
    module of this folder that does so first (`runner_support`, or a test file that imports
    it)."""
    if name not in known:
        known[name] = ('neither', None)   # a module being read meanwhile sets nothing
        for node in ast.parse((TESTS / f'{name}.py').read_text(encoding='utf-8')).body:
            said = ast.unparse(node)
            if isinstance(node, ast.Expr) and 'sys.path' in said and 'REPO' in said:
                known[name] = ('sets', None)
                break
            names = _imported(node)
            if 'runner' in names:
                known[name] = ('late', node.lineno)
                break
            if any(one != name and (TESTS / f'{one}.py').is_file()
                   and _reads(one, known)[0] == 'sets' for one in names):
                known[name] = ('sets', None)
                break
    return known[name]


class RunAloneTests(unittest.TestCase):
    def test_no_test_file_imports_the_runner_before_its_folder_is_on_the_path(self):
        known: dict = {}
        late = [f'{file.name}:{_reads(file.stem, known)[1]}'
                for file in sorted(TESTS.glob('test_*.py'))
                if _reads(file.stem, known)[0] == 'late']
        self.assertEqual(late, [])

    def test_the_migration_tests_import_on_their_own_from_the_studio_folder(self):
        env = {key: value for key, value in os.environ.items() if key != 'PYTHONPATH'}
        done = subprocess.run(
            [sys.executable, '-c', 'import tests.test_desk_migration'],
            cwd=helpers.REPO, env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr[-2000:])


if __name__ == '__main__':
    unittest.main()
