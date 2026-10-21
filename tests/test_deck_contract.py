"""Both studios make a slide deck the same way: the contract between them, run for real.

Each studio's tests hold a `deck_contract` module that takes one deck through its engine at
every review level, with stand-ins only (no provider, no network, a disposable home), and
writes what the deck's workers read and where it paused. They differ only in where an
outline's words come from, so what is compared is the deck's own guidance and the brand's,
and the brand's checkpoints.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'core'))
from studio_core import deck_flow  # noqa: E402

STUDIOS = {'training': ROOT / 'studios' / 'training' / 'tests',
           'presentation': ROOT / 'studios' / 'presentation' / 'tests'}


def contract(studio: str, out: Path) -> dict:
    folder = STUDIOS[studio]
    if not (folder / 'deck_contract.py').is_file():
        raise unittest.SkipTest(f'{studio} has no deck contract yet')
    env = {**os.environ, 'DECK_CONTRACT_OUT': str(out), 'PYTHONDONTWRITEBYTECODE': '1'}
    done = subprocess.run([sys.executable, '-m', 'unittest', 'deck_contract'], cwd=folder,
                          env=env, capture_output=True, text=True, timeout=600)
    if done.returncode or not out.is_file():
        raise AssertionError(f'{studio} deck contract failed:\n{done.stdout}\n{done.stderr}')
    return json.loads(out.read_text())


class DeckContractTests(unittest.TestCase):
    def test_both_studios_give_workers_the_same_guidance_and_pause_the_same_way(self):
        with tempfile.TemporaryDirectory() as folder:
            training = contract('training', Path(folder) / 'training.json')
            presentation = contract('presentation', Path(folder) / 'presentation.json')
        shared = lambda names: [name for name in names if name in deck_flow.SHARED_INPUTS]
        for side in (training, presentation):
            side['outline'], side['composer'] = shared(side['outline']), shared(side['composer'])
        self.assertEqual(training['composer'], presentation['composer'])
        # The one difference allowed, and only while deck_flow records it: a studio without a
        # design session gives its outline writer no design guidance.
        lacking = [studio for studio, has in deck_flow.DESIGN_SESSION.items() if not has]
        unlike = [name for name in deck_flow.DESIGN_READING if lacking]
        self.assertEqual([name for name in training['outline'] if name not in unlike],
                         [name for name in presentation['outline'] if name not in unlike])
        self.assertEqual(lacking, [studio for studio, side in (('training', training),
                                   ('presentation', presentation))
                                   if 'design guidance' not in side['outline']])
        self.assertEqual(training['pauses'], presentation['pauses'])
        self.assertEqual(training['pauses'], {level: list(stops) for level, stops
                                              in deck_flow.PAUSES.items()})
        self.assertIn(deck_flow.BRAND_WORKER, training['composer'])
