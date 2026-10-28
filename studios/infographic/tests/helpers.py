"""Disposable Infographic Studio state and synthetic contract records."""
from copy import deepcopy
import hashlib
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

NATIVE = Path(__file__).resolve().parents[1]
ROOT = NATIVE.parents[1]
sys.path.insert(0, str(NATIVE))

from runner.contracts import PRESETS, basis, digest, new_project
from runner.validation import REQUIRED_CHECKS


class Isolated(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='infographic-studio-test-')
        self.addCleanup(self.temporary.cleanup)
        self.temp = Path(self.temporary.name).resolve()
        self.home, self.data, self.workspace = (self.temp / key for key in ('home', 'data', 'workspace'))
        self.home.mkdir()
        (self.home / 'gitconfig').write_text('[user]\n name = Disposable Test\n email = test@example.invalid\n')
        self.settings = self.temp / 'shared.json'
        self.environment = mock.patch.dict(os.environ, {
            'HOME': str(self.home), 'PATH': os.environ.get('PATH', ''),
            'INFOGRAPHIC_STUDIO_DATA': str(self.data), 'STUDIOS_CONFIG': str(self.settings),
            'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': str(self.home / 'gitconfig'),
        }, clear=True)
        self.environment.start()
        self.addCleanup(self.environment.stop)


def project():
    p = new_project('owner1', 'Synthetic contract test', ident='test1')
    raw = 'Synthetic counts: baseline 12; comparison 24.'
    p['sources'] = [{'id': 's1', 'kind': 'text', 'sha256': hashlib.sha256(raw.encode()).hexdigest(),
                     'file': 'sources/input.txt', 'bytes': len(raw), 'characters': len(raw)}]
    p['facts'] = [{'id': key, 'statement': 'Synthetic measurement', 'value': value, 'unit': 'count',
                   'status': 'supplied', 'evidence': [{'source_id': 's1', 'start': start, 'end': start + 2}]}
                  for key, value, start in [('f1', 12, 27), ('f2', 24, 42)]]
    # The actual string location is recorded, rather than a guessed fixture offset.
    for fact in p['facts']:
        start = raw.index(str(fact['value']))
        fact['evidence'] = [{'source_id': 's1', 'start': start, 'end': start + 2}]
    p['stories'] = [{'id': 'story1', 'headline': 'Synthetic comparison', 'takeaway': 'Compare two supplied counts.',
                     'blocks': [{'id': 'block1', 'kind': 'comparison', 'fact_ids': ['f1', 'f2'], 'required_ids': []}],
                     'omissions': []}]
    p['selected_story'] = 'story1'
    p['brand'] = {'revision': 'synthetic-v1', 'sha256': 'a' * 64}
    preset = PRESETS['a4']
    p['scene'] = {'id': 'scene1', **{k: preset[k] for k in ('width', 'height', 'unit')},
                  'elements': [{'id': 'label1', 'kind': 'text', 'bounds': [20, 20, 200, 30],
                                'text': 'Synthetic comparison', 'font': 'Arial', 'font_size': 18}]}
    p['image_briefs'] = [{'id': 'image1', 'story_id': 'story1', 'scene_id': 'scene1', 'basis': basis(p),
                         'prompt': 'Draw two flat shapes in the image region. Keep all reserved text regions empty.',
                         'goal': 'Compare the supplied counts.', 'reading_order': 'Title then bars then source.',
                         'style': 'Flat shapes; solid colors; no texture or perspective.',
                         'exclusions': 'No labels, numbers, shadows, or extra shapes.',
                         'acceptance': 'Two shapes; empty label area; no decorative objects.',
                         'canvas': {k: p['scene'][k] for k in ('width', 'height', 'unit')},
                         'regions': [{'id': 'art1', 'bounds': [.1, .2, .8, .5], 'owner': 'image'},
                                     {'id': 'words1', 'bounds': [.1, .05, .8, .1], 'owner': 'compositor'}],
                         'objects': [{'id': 'shapes1', 'region_id': 'art1', 'count': 2,
                                      'description': 'Two horizontal flat rectangles.'}],
                         'reference_assets': [], 'fact_ids': ['f1', 'f2'],
                         'compositor_text': ['Synthetic comparison']}]
    return p


def approved_project():
    p = project()
    p['checks'] = [{'id': 'check' + str(i), 'kind': kind, 'scene_digest': digest(p['scene']),
                     'basis': basis(p), 'status': 'passed', 'blocking': True}
                    for i, kind in enumerate(sorted(REQUIRED_CHECKS))]
    p['approval'] = {'revision': p['revision'], 'owner': p['owner'],
                     'basis': basis(p), 'scene_digest': digest(p['scene'])}
    return deepcopy(p)


def visual_answer():
    return {'capability': 'inspected', 'observations': [
        {'kind': kind, 'region_id': 'page', 'text': 'Synthetic fixture observer received the actual composed PNG; no live provider was used.'}
        for kind in ('counts', 'relationships', 'crop', 'resolution', 'label_clearance', 'brand', 'factual_implications')], 'findings': []}
