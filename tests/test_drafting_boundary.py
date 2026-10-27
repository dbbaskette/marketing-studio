"""The shared desk parts import only the standard library and the shared core, never a studio."""

import ast
import sys
import unittest
from pathlib import Path

CORE = Path(__file__).resolve().parents[1] / 'core' / 'studio_core'
SHARED = sorted((CORE / 'drafting').glob('*.py')) + [CORE / 'text_checks.py', CORE / 'step_times.py']


class BoundaryTests(unittest.TestCase):
    def test_the_shared_desk_imports_no_studio_and_reads_no_settings(self):
        for path in SHARED:
            tree = ast.parse(path.read_text(encoding='utf-8'))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom):
                    if node.level:
                        continue  # Within studio_core.
                    names = [node.module]
                else:
                    continue
                for name in names:
                    top = name.split('.')[0]
                    with self.subTest(file=path.name, name=name):
                        self.assertTrue(
                            top in sys.stdlib_module_names or top == 'studio_core',
                            path.name + ' imports ' + name,
                        )
            text = path.read_text(encoding='utf-8')
            for word in ('studios_config', 'STUDIOS_CONFIG', 'environ'):
                with self.subTest(file=path.name, word=word):
                    self.assertNotIn(word, text)


if __name__ == '__main__':
    unittest.main()
