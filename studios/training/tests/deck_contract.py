"""Training Studio's half of the contract that both studios make a deck the same way.

Run with DECK_CONTRACT_OUT naming a file: one deck is taken through the engine at each review
level, with stand-ins (a brand that is the entry to slide building and draws looks, and a
slides tool with a design session), and what the deck's workers read and where it paused for
the person are written there as JSON. Without the variable the test is skipped. The root
suite's test_deck_contract runs this and Presentation Studio's twin and compares them.
"""
import json
import os
import unittest
from pathlib import Path
from unittest import mock

import helpers  # noqa: F401
import workspace
from studio_core import deck_flow, review_policy
from test_runner_deck import DeckCase

OUT = os.environ.get('DECK_CONTRACT_OUT')


def shared(names) -> list[str]:
    return [name for name in names if name in deck_flow.SHARED_INPUTS]


@unittest.skipUnless(OUT, 'Run by the root suite, with DECK_CONTRACT_OUT set.')
class DeckContract(DeckCase):
    def setUp(self):
        super().setUp()
        self.brand.entry, self.brand.offers_looks = 'brand', True
        self.slides.design = True

    def through(self, level: str) -> list[str]:
        """Take one deck to its final checkpoint at `level`, answering every stop, and say
        which of the brand's checkpoints it paused at."""
        with mock.patch.object(review_policy, 'capture',
                               return_value={'schema': 1, 'level': level}):
            root = self.begin(title=f'Contract {level}')
        paused = []
        for _ in range(40):
            view = self.view(root)
            self.assertIsNone(view['problem'], view)
            gate = workspace.status(root)['gate']
            if view['review'] and view['review']['phase'] == 'direction':
                paused.append(deck_flow.canonical('training', 'review:direction') or 'direction')
                self.engine.review_decide(root, view['review']['expected'], 'approve',
                                          looks={'': {'choice': 'example-contrast',
                                                      'words': 'For the contract.'}})
            elif view['outline'] and view['outline']['waiting']:
                paused.append(deck_flow.canonical('training', 'gate:deck-outline'))
                self.engine.outline(root, None, 'approve')
            elif view['look'] and view['look']['waiting']:
                paused.append(deck_flow.canonical('training', 'gate:deck-look'))
                self.engine.look(root, None, 'example-contrast', 'For the contract.')
            elif gate == 'deck':
                paused.append(deck_flow.canonical('training', 'gate:deck'))
                return paused
            elif gate:
                self.decide(root, gate)    # not a deck's: the research plan, its review
            else:
                self.fail(f'The deck never reached its final checkpoint at {level}: {view}')
        self.fail('Too many stops.')

    def test_the_contract(self):
        pauses = {level: self.through(level) for level in ('step_by_step', 'balanced',
                                                           'automatic')}
        jobs = [(kind, spec) for kind, _, spec in self.workers.jobs]
        outline = next(spec for kind, spec in jobs if kind == 'outline')
        composer = next(spec for kind, spec in jobs if kind == 'section')
        Path(OUT).write_text(json.dumps({
            'outline': shared(entry['name'] for entry in outline['inputs']),
            'composer': shared(entry['name'] for entry in composer['inputs']),
            'pauses': pauses}, indent=2))
