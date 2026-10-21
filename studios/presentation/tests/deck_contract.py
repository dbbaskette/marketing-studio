"""Presentation Studio's side of the shared deck contract, for the suite's own test that
compares it with Training Studio's.

One deck is run through the engine at each review level, with stand-ins only: a brand skill
that is the entry to slide building and offers looks, and a slides tool with the design
session. What is recorded: the input names the outline's writer and the first composer were
given, and the checkpoints the deck paused at for the person, named as studio_core.deck_flow
names them ('draft', 'look', 'final', or 'direction' for the combined stop). It is written
as JSON to the file DECK_CONTRACT_OUT names:

    {"outline": [...], "composer": [...], "pauses": {"step_by_step": [...], ...}}

Without DECK_CONTRACT_OUT the test is skipped. Nothing real is started and nothing leaves
this computer.
"""
import json
import os
import unittest
from pathlib import Path
from unittest import mock

import runner_support
from runner_support import StudioCase
from stand_ins import slides as slides_stand_in
from studio_core import deck_flow, review_policy

OUT = 'DECK_CONTRACT_OUT'
LEVELS = ('step_by_step', 'balanced', 'automatic')


def checkpoint(level: str, gate: str) -> str | None:
    """The checkpoint a Presentation Studio gate stood for at this level: the combined stop
    it hosts, else its own, else None for a gate that is not a deck's."""
    hosts = deck_flow.HOSTS['presentation'].get(level, {})
    return next((stop for stop, host in hosts.items() if host == gate),
                deck_flow.canonical('presentation', gate))


@unittest.skipUnless(os.environ.get(OUT), f'set {OUT} to write the deck contract')
class DeckContractTests(StudioCase):
    def setUp(self):
        super().setUp()
        self.slides = slides_stand_in.stand_in(design=True)
        self.brand.run.guides = True
        self.brand.run.offers_looks = True

    def through(self, level: str) -> list[str]:
        """Run one deck at `level` to its end, approving each stop as the person would,
        picking a look where one is asked for. Returns the checkpoints it paused at."""
        with mock.patch.object(review_policy, 'capture',
                               return_value={'schema': 1, 'level': level}):
            root = self.start(title=f'Contract {level}')
        paused = []
        for _ in range(12):
            shown = self.view(root)
            self.assertIsNone(shown['problem'], shown['problem'])
            gate = shown['gate']
            if gate is None:
                break
            paused.append(gate['name'])
            offered = gate.get('offered') or (gate.get('look') or {}).get('offered')
            pick = {'look': offered['looks'][0]['id']} \
                if offered and not offered['chosen'] and offered['looks'] else None
            self.decide(root, gate['name'], 'approve', None, pick)
        self.assertEqual(self.view(root)['state'], 'finished')
        return [found for found in (checkpoint(level, gate) for gate in paused) if found]

    def names(self, kind: str) -> list[str]:
        spec = next(spec for seen, job, spec in self.workers.jobs
                    if seen.partition(':')[0] == kind)
        return [entry['name'] for entry in spec['inputs']]

    def test_the_deck_contract(self):
        pauses = {}
        for level in LEVELS:
            pauses[level] = self.through(level)
            if level == LEVELS[0]:
                contract = {'outline': self.names('outline'),
                            'composer': self.names('section')}
        contract['pauses'] = pauses
        for level in LEVELS:
            self.assertEqual(tuple(pauses[level]), deck_flow.pauses(level), level)
        Path(os.environ[OUT]).write_text(json.dumps(contract, indent=2) + '\n',
                                         encoding='utf-8')


if __name__ == '__main__':
    runner_support  # noqa: B018  puts the runner on the import path
    unittest.main()
