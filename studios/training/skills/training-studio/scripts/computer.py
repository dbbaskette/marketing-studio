"""Whether this computer has what a training needs.

Training Studio's words for the check the studios that build slides share,
`studio_core.computer_check`: this module becomes that check, made for Training Studio.
"""
import sys

from studio_core.computer_check import for_product

sys.modules[__name__] = for_product(
    __name__, 'Training Studio',
    {'harness-research': 'Research cannot run without it.',
     'harness-slides': 'Without it everything is built except the slide deck.'},
    'Optional. Install pandoc if you want Word copies of guides and briefs.')
