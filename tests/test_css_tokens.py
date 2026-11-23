"""Every custom property a stylesheet reads is one some stylesheet, or the shell, defines.

A `var(--name)` that nothing defines draws its fallback, or nothing, in both appearances:
a light border in the dark appearance, a hover in Marketing Studio blue on another studio's
card. This reads `ui-kit/style.css` and each page stylesheet, and fails on any name read
but never set. A name a script sets on an element (`style.setProperty('--name', ...)`)
counts as set.

It also keeps the appearance one setting: the dark tokens that follow this computer and the
ones a chosen Dark appearance applies are the same tokens, and no script rewrites a
stylesheet to switch them.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / 'ui-kit/style.css'
STYLESHEETS = (
    KIT,
    ROOT / 'core/studio_core/setup_web/home.css',
    ROOT / 'core/studio_core/deck_web/deck-panels.css',
    ROOT / 'studios/blog/skills/blog-studio/assets/management/blog.css',
    ROOT / 'studios/presentation/skills/presentation-studio/scripts/desk/deck.css',
    ROOT / 'studios/infographic/runner/web/infographic.css',
)
SHELL = ROOT / 'core/studio_core/deck_web/shell.js'
# Scripts that set a custom property on an element for a stylesheet to read.
SETTERS = (SHELL, *sorted(ROOT.glob('ui-kit/*.js')), *sorted(ROOT.glob('core/studio_core/*/*.js')),
           *sorted(ROOT.glob('studios/*/skills/*/scripts/desk/*.js')),
           *sorted(ROOT.glob('studios/blog/skills/blog-studio/assets/management/*.js')),
           *sorted(ROOT.glob('studios/infographic/runner/web/*.js')))


def uncommented(css: str) -> str:
    return re.sub(r'/\*.*?\*/', '', css, flags=re.S)


def block(text: str, start: str) -> str:
    """What the braces opened after `start` hold."""
    at = text.index('{', text.index(start))
    depth, end = 1, at + 1
    while depth:
        depth += {'{': 1, '}': -1}.get(text[end], 0)
        end += 1
    return text[at + 1:end - 1]


def tokens(body: str) -> dict:
    return dict(re.findall(r'(--[\w-]+)\s*:\s*([^;]+);', body))


class DefinedTokenTests(unittest.TestCase):
    maxDiff = None

    def test_every_custom_property_read_is_defined(self):
        defined, read = set(), {}
        for sheet in STYLESHEETS:
            css = uncommented(sheet.read_text(encoding='utf-8'))
            defined |= set(re.findall(r'(--[\w-]+)\s*:', css))
            for name in re.findall(r'var\(\s*(--[\w-]+)', css):
                read.setdefault(name, set()).add(sheet.relative_to(ROOT).as_posix())
        for script in SETTERS:
            text = script.read_text(encoding='utf-8')
            defined |= set(re.findall(r"""setProperty\(\s*['"](--[\w-]+)['"]""", text))
        missing = {name: sorted(where) for name, where in read.items() if name not in defined}
        self.assertEqual(missing, {}, 'read with var() but never defined')

    def test_a_chosen_dark_appearance_is_the_dark_that_follows_this_computer(self):
        kit = uncommented(KIT.read_text(encoding='utf-8'))
        light = tokens(block(kit, ':root {'))
        system = block(kit, '@media (prefers-color-scheme: dark) {')
        followed = tokens(block(system, ':root'))
        chosen = tokens(block(kit, ':root:where(:has(> body[data-appearance="dark"])) {'))
        self.assertEqual(followed, chosen)
        self.assertEqual(set(followed) - set(light), set(), 'the dark tokens are the light ones, redefined')
        # System dark stands aside once Light is chosen; a choice is read from <body>, which the
        # server writes as the page is served, so the page opens already looking as chosen.
        self.assertIn(':root:where(:not(:has(> body[data-appearance="light"])))', system)
        # The liquid pilot's own dark tokens follow the same choice.
        pilot = block(kit, '@media (prefers-color-scheme: dark) {\n  body[data-pilot="liquid"]')
        chosen_pilot = block(kit, 'body[data-pilot="liquid"]:where([data-appearance="dark"]) {')
        self.assertEqual(tokens(pilot), tokens(chosen_pilot))
        self.assertIn('body[data-pilot="liquid"]:where(:not([data-appearance="light"]))', pilot_head(kit))

    def test_switching_the_appearance_never_rewrites_a_stylesheet(self):
        script = SHELL.read_text(encoding='utf-8')
        for walk in ('styleSheets', 'cssRules', 'mediaText'):
            self.assertFalse(walk in script, f'shell.js reads {walk}')
        self.assertIn('document.body.dataset.appearance = chosen', script)
        # These are the only colour-scheme conditions; a page stylesheet adds none of its own.
        for sheet in STYLESHEETS[1:]:
            self.assertNotIn('prefers-color-scheme', sheet.read_text(encoding='utf-8'), sheet.name)


class ReadingAloneTests(unittest.TestCase):
    def test_reading_alone_works_at_every_width_and_shows_its_way_out(self):
        kit = uncommented(KIT.read_text(encoding='utf-8'))
        hidden = re.search(r'\n(body\[data-focus="reading"\][^{]*)\{\s*display:\s*none', kit)
        self.assertIsNotNone(hidden, 'the parts and the rail step aside outside any width query')
        self.assertIn('[data-zone="rail"]', hidden.group(1))
        self.assertIn('[data-zone="parts"]', hidden.group(1))
        self.assertIn('.reading-exit', kit)
        phone = kit[kit.index('.reading-exit {'):]
        self.assertIn('bottom: calc(var(--tab-bar-room) + 0.6rem)', phone)
        script = SHELL.read_text(encoding='utf-8')
        self.assertIn("'button glass reading-exit'", script)
        self.assertIn("'Show everything'", script)


def pilot_head(kit: str) -> str:
    at = kit.index('@media (prefers-color-scheme: dark) {\n  body[data-pilot="liquid"]')
    return kit[at:kit.index('{', at + 40)]


if __name__ == '__main__':
    unittest.main()
