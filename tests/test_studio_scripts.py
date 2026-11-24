"""Presentation Studio and Training Studio take their computer check, home folder and
guidance sync from the core.

`computer.py` in each studio's scripts folder becomes `studio_core.computer_check`, made
for that product. `home.py` and `sync_guidance.py` keep their own modules and bind the
shared parts of `studio_core.studio_home` and `studio_core.guidance_sync` into them: every
name a bound function reads must be found there, the code must be the core's, and it must
read the studio's module. Each studio is looked at in a process of its own, as each runs
alone; nothing is run that reads or writes a data folder.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / 'core' / 'studio_core'
STUDIOS = {
    'Presentation Studio': ROOT / 'studios/presentation/skills/presentation-studio/scripts',
    'Training Studio': ROOT / 'studios/training/skills/training-studio/scripts',
}
SHARED = ('computer_check.py', 'studio_home.py', 'guidance_sync.py')
PRODUCT_WORDS = ('Presentation Studio', 'Training Studio', 'PRESENTATION_STUDIO',
                 'TRAINING_STUDIO', 'presentation-studio', 'training-studio')

LOOK = """
import json, sys
from types import FunctionType
sys.path.insert(0, sys.argv[1])
from studio_core import modules
import computer, home, sync_guidance

found = {'computer': {'file': computer.__file__, 'product': computer.PRODUCT,
                      'skills': list(computer.SKILLS), 'is_module': sys.modules['computer'] is computer}}
for module in (home, sync_guidance):
    names = vars(module)
    shared = [record['source'] for record in names.get('__shared_parts__', [])]
    wrong = []
    for record in names.get('__shared_parts__', []):
        source = vars(sys.modules[record['source']])
        for name in record['names']:
            held, origin = names[name], source[name]
            if isinstance(origin, FunctionType):
                if held.__code__ is not origin.__code__ or held.__globals__ is not names:
                    wrong.append(name)
            elif held is not origin:
                wrong.append(name)
    found[module.__name__] = {'shared': shared, 'unresolved': modules.unresolved(names),
                              'wrong': wrong}
print(json.dumps(found))
"""


class StudioScriptTests(unittest.TestCase):
    def look(self, scripts: Path) -> dict:
        with tempfile.TemporaryDirectory() as data:
            env = {key: value for key, value in os.environ.items()
                   if not key.startswith('PYTHON')}
            env.update(PRESENTATION_STUDIO_DATA=data, TRAINING_STUDIO_DATA=data)
            done = subprocess.run([sys.executable, '-B', '-c', LOOK, str(scripts)],
                                  cwd=data, env=env, capture_output=True, text=True,
                                  timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_each_studio_s_scripts_take_their_shared_parts_from_the_core(self):
        for product, scripts in STUDIOS.items():
            with self.subTest(studio=product):
                found = self.look(scripts)
                computer = found['computer']
                self.assertEqual(Path(computer['file']).resolve(),
                                 (CORE / 'computer_check.py').resolve())
                self.assertEqual(computer['product'], product)
                self.assertEqual(computer['skills'], ['harness-research', 'harness-slides'])
                self.assertTrue(computer['is_module'])
                for name, source in (('home', 'studio_core.studio_home'),
                                     ('sync_guidance', 'studio_core.guidance_sync')):
                    self.assertEqual(found[name]['shared'], [source], name)
                    self.assertEqual(found[name]['unresolved'], [], name)
                    self.assertEqual(found[name]['wrong'], [], name)

    def test_the_shared_scripts_name_no_product(self):
        for name in SHARED:
            text = (CORE / name).read_text(encoding='utf-8')
            for word in PRODUCT_WORDS:
                self.assertNotIn(word, text, name)


if __name__ == '__main__':
    unittest.main()
