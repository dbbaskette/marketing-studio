"""What the deck studios' shared `caller.shown` gives a phone on the private link (GitHub issue
#539): no folder of this computer, whether a value is the folder or a sentence names one."""
import unittest
from email.message import Message

import marketing_studio  # noqa: F401  (puts core/ on the path)
from studio_core.brand_data import names_a_folder
from studio_core.shared_runner import caller

LINK = '/Users/someone/.claude/skills/presentation-studio'
TARGET = '/Users/someone/.local/share/presentation-studio/current'
# The shared upkeep report's sentences for a broken skill link (shared_runner/upkeep.py).
BROKEN = (f'The link for Claude Code points at {TARGET}, which is not there any more. '
          'Run the installer again.',
          f'{LINK} is not the link the installer placed, so it was left alone. Run the '
          'installer again to link Presentation Studio there.',
          "Claude Code's skill folder, /Users/someone/.claude/skills, is gone, so "
          'Presentation Studio was not linked into it again.',
          f'The link for Codex was missing, and was put back: {LINK}.')
PLAIN = 'The link for Codex is missing. It is put back when Presentation Studio starts.'


def description() -> dict:
    return {'upkeep': {'links': [{'assistant': 'Claude Code', 'name': 'presentation-studio',
                                  'path': LINK, 'state': 'missing', 'says': said}
                                 for said in BROKEN]
                       + [{'assistant': 'Codex', 'path': LINK, 'state': 'missing',
                           'says': PLAIN}],
                       'versions': {'brand': {'repository': '/srv/brand.git',
                                              'says': 'Up to date.'}},
                       'notes': [['nested', BROKEN[0]], [PLAIN]]},
            'workspace': {'name': 'Decks', 'path': '/Users/someone/decks'}}


def strings(value):
    if isinstance(value, dict):
        return [found for one in value.values() for found in strings(one)]
    if isinstance(value, list):
        return [found for one in value for found in strings(one)]
    return [value] if isinstance(value, str) else []


class ShownTests(unittest.TestCase):
    def phone(self):
        made = Message()
        made[caller.VIA_HEADER] = caller.NETWORK
        return caller.answering(made)

    def test_a_phone_is_given_no_sentence_that_names_a_folder_here(self):
        with self.phone():
            shown = caller.shown(description())
        self.assertEqual([one for one in strings(shown) if names_a_folder(one)], [])
        self.assertNotIn('/Users/someone', repr(shown))
        links = shown['upkeep']['links']
        self.assertEqual([link['says'] for link in links[:4]], [caller.FOLDER_SAID] * 4)
        self.assertFalse(names_a_folder(caller.FOLDER_SAID))
        # A sentence that names no folder, and everything else, is as it was.
        self.assertEqual(links[4]['says'], PLAIN)
        self.assertEqual([link['state'] for link in links], ['missing'] * 5)
        self.assertEqual(shown['upkeep']['notes'], [['nested', caller.FOLDER_SAID], [PLAIN]])
        self.assertEqual(shown['upkeep']['versions']['brand'],
                         {'repository': caller.FOLDER_HERE, 'says': 'Up to date.'})
        self.assertEqual(shown['workspace'], {'name': 'Decks', 'path': None})

    def test_a_caller_on_this_computer_is_shown_everything_as_before(self):
        self.assertEqual(caller.shown(description()), description())
        with caller.answering(Message()):
            self.assertEqual(caller.shown(description()), description())


if __name__ == '__main__':
    unittest.main()
