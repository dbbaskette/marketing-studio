"""Training Studio's half of the contract that both studios make a deck the same way.

Run with DECK_CONTRACT_OUT naming a file: one deck is started on the desk and drawn, with
stand-ins (a brand that is the entry to slide building and draws looks, and a slides tool
with a design session), and the input names the outline's writer and the first composer were
given are written there as JSON: {"outline": [...], "composer": [...]}. Without the variable
the test is skipped. The root suite's test_deck_contract runs this and Presentation Studio's
twin and compares them.

A desk deck reads no review level, so it has no review-level pauses to compare: those were
the earlier step-by-step flow's, which went with GitHub issue #542.
"""
import json
import os
import unittest
from pathlib import Path

import helpers  # noqa: F401
from test_runner_deck import DeckCase

OUT = os.environ.get('DECK_CONTRACT_OUT')


@unittest.skipUnless(OUT, 'Run by the root suite, with DECK_CONTRACT_OUT set.')
class DeckContract(DeckCase):
    # Its decks walk through each slide's design, the session Training Studio keeps and
    # Presentation Studio has not, which deck_flow.DESIGN_SESSION records.
    WALKTHROUGH = True

    def setUp(self):
        super().setUp()
        self.brand.entry, self.brand.offers_looks = 'brand', True
        self.slides.design = True

    def names(self, kind: str) -> list[str]:
        """What the first job of `kind` was given, by name: the outline's writer is the first
        `outline` job (the desk's check of the slide text comes after it)."""
        spec = next(spec for seen, _, spec in self.workers.jobs if seen == kind)
        return [entry['name'] for entry in spec['inputs']]

    def test_the_contract(self):
        root = self.begin(title='Contract')
        self.assertIsNone(self.view(root)['problem'])
        Path(OUT).write_text(json.dumps({'outline': self.names('outline'),
                                         'composer': self.names('section')}, indent=2))
