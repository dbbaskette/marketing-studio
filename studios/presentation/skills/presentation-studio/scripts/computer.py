"""Whether this computer has what a deck needs.

Presentation Studio's words for the check the studios that build slides share,
`studio_core.computer_check`: this module becomes that check, made for Presentation Studio.
"""
import sys

from studio_core.computer_check import for_product

sys.modules[__name__] = for_product(
    __name__, 'Presentation Studio',
    {'harness-research': 'Research cannot run without it.',
     'harness-slides': 'Without it no slides can be made.'},
    'Optional. Install pandoc if you want Word copies.')
