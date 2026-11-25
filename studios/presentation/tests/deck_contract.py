"""Presentation Studio's side of the shared deck contract, for the suite's own test that
compares it with Training Studio's.

One deck is started on the desk and run to it, with stand-ins only: a brand skill that is
the entry to slide building and offers looks, and a slides tool with the design session.
What is recorded: the input names the outline's writer and the first composer were given.
It is written as JSON to the file DECK_CONTRACT_OUT names:

    {"outline": [...], "composer": [...]}

A desk deck reads no review level, so it has no review-level pauses to compare: those were
the earlier step-by-step flow's, which went with GitHub issue #542.

Without DECK_CONTRACT_OUT the test is skipped. Nothing real is started and nothing leaves
this computer.
"""
import json
import os
import unittest
from pathlib import Path

import runner_support
from runner_support import DeskCase
from stand_ins import slides as slides_stand_in

OUT = 'DECK_CONTRACT_OUT'


@unittest.skipUnless(os.environ.get(OUT), f'set {OUT} to write the deck contract')
class DeckContractTests(DeskCase):
    def setUp(self):
        super().setUp()
        self.slides = slides_stand_in.stand_in(design=True)
        self.brand.run.guides = True
        self.brand.run.offers_looks = True

    def names(self, kind: str) -> list[str]:
        spec = next(spec for seen, job, spec in self.workers.jobs
                    if seen.partition(':')[0] == kind)
        return [entry['name'] for entry in spec['inputs']]

    def test_the_deck_contract(self):
        root = self.start_desk(title='Contract', look='pick')
        self.pick_look(root)
        self.on_desk(root)
        contract = {'outline': self.names('outline'), 'composer': self.names('section')}
        Path(os.environ[OUT]).write_text(json.dumps(contract, indent=2) + '\n',
                                         encoding='utf-8')


if __name__ == '__main__':
    runner_support  # noqa: B018  puts the runner on the import path
    unittest.main()
