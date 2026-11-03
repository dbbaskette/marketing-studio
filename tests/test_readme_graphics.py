"""The README illustrations and studio workflow diagrams match the scripts that draw them.

Both scripts are deterministic and use only the standard library. A check never changes
files, and a missing or hand-edited SVG fails until it is rebuilt from its source.
"""
import importlib.util
import re
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / 'scripts'
SVG = '{http://www.w3.org/2000/svg}'


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


diagrams = load('workflow_diagrams')


def check(script, *extra):
    return subprocess.run([sys.executable, str(SCRIPTS / script), '--check', *extra],
                          capture_output=True, text=True, check=False)


class ReadmeGraphicsTests(unittest.TestCase):
    def test_the_readme_illustrations_are_current(self):
        ran = check('readme_graphics.py')
        self.assertEqual(ran.returncode, 0, ran.stderr)

    def test_the_workflow_diagrams_are_current(self):
        ran = check('workflow_diagrams.py')
        self.assertEqual(ran.returncode, 0, ran.stderr)
        self.assertIn('9 workflow diagrams are current.', ran.stdout)

    def test_a_missing_or_changed_diagram_fails_the_check(self):
        with tempfile.TemporaryDirectory() as folder:
            ran = check('workflow_diagrams.py', '--root', folder)
            self.assertEqual(ran.returncode, 1)
            self.assertIn('training-studio-workflow-plan.svg', ran.stderr)
            self.assertEqual(sorted(diagrams.outdated(folder)), sorted(diagrams.built()))
            for path, content in diagrams.built().items():
                (Path(folder) / path).parent.mkdir(parents=True, exist_ok=True)
                (Path(folder) / path).write_text(content, encoding='utf-8')
            self.assertEqual(check('workflow_diagrams.py', '--root', folder).returncode, 0)
            changed = Path(folder) / 'studios/blog/docs/assets/blog-studio-workflow-write.svg'
            changed.write_text(changed.read_text().replace('New blog', 'New post'))
            ran = check('workflow_diagrams.py', '--root', folder)
            self.assertEqual(ran.returncode, 1)
            self.assertEqual(diagrams.outdated(folder),
                             ['studios/blog/docs/assets/blog-studio-workflow-write.svg'])

    def test_each_diagram_is_a_self_contained_accessible_svg(self):
        for path, content in diagrams.built().items():
            with self.subTest(path=path):
                svg = ET.fromstring(content)
                self.assertEqual(svg.get('role'), 'img')
                self.assertEqual(svg.get('aria-labelledby'), 'title desc')
                self.assertTrue(svg.find(f'{SVG}title').text.strip())
                self.assertTrue(svg.find(f'{SVG}desc').text.strip())
                tags = {element.tag.removeprefix(SVG) for element in svg.iter()}
                self.assertFalse(tags & {'script', 'image', 'foreignObject', 'use', 'a'})
                self.assertNotIn('href', content)
                self.assertNotRegex(content, r'url\(|@import|data:')
                self.assertEqual(re.findall(r'https?://', content), ['http://'])
                self.assertIn('@media (prefers-color-scheme:dark)', content)
                sizes = [int(size) for size in re.findall(r'font-size="(\d+)"', content)]
                self.assertTrue(sizes and min(sizes) >= 11, sizes)
                self.assertTrue(svg.find(f'{SVG}rect').get('class') == 'page')

    def test_no_line_crosses_a_box_and_no_label_overlaps_one(self):
        for studio, stem, _, _, heading, (nodes, edges) in diagrams.DIAGRAMS:
            with self.subTest(diagram=f'{studio} {stem}'):
                boxes, _, _ = diagrams.layout(nodes, edges)
                self.assertEqual(diagrams.problems(boxes, edges), [])

    def test_the_layout_guard_finds_a_line_through_a_box(self):
        nodes = [('a', 0, 0, 'you', 'First', 'One'), ('b', 0, 1, 'studio', 'Second', 'Two'),
                 ('c', 0, 2, 'assistant', 'Third', 'Three')]
        edges = [('a', 'c', 'down', '')]
        boxes, _, _ = diagrams.layout(nodes, edges)
        self.assertEqual(diagrams.problems(boxes, edges), ['a to c crosses b'])

    def test_every_diagram_appears_in_the_graphics_notes_and_a_studio_document(self):
        notes = (ROOT / 'docs/assets/readme-graphics.md').read_text(encoding='utf-8')
        for path in diagrams.built():
            name = Path(path).name
            with self.subTest(diagram=name):
                self.assertIn(path, notes)
                studio = ROOT / Path(path).parents[2]
                shown = [doc for doc in [studio / 'README.md', *studio.glob('docs/*.md')]
                         if f'docs/assets/{name})' in doc.read_text(encoding='utf-8')
                         or f'assets/{name})' in doc.read_text(encoding='utf-8')]
                self.assertTrue(shown, f'{name} is not shown in its studio documents')


if __name__ == '__main__':
    unittest.main()
