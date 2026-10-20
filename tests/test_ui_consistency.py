"""One look across every page: page stylesheets lay out their own parts and nothing else.

`ui-kit/style.css` owns the tokens, the shell and the controls. A page's stylesheet may
place a shared control (its size, gaps, grid cell) but never redraw it, may not style bare
controls or headings for the whole page, and takes every colour from a token.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KIT = ROOT / 'ui-kit/style.css'
PAGE_STYLES = (
    ROOT / 'core/studio_core/setup_web/home.css',
    ROOT / 'studios/blog/skills/blog-studio/assets/management/blog.css',
    ROOT / 'studios/presentation/skills/presentation-studio/scripts/desk/deck.css',
)
APP_PAGES = (
    ROOT / 'core/studio_core/setup_web/index.html',
    ROOT / 'studios/blog/skills/blog-studio/assets/management/index.html',
    ROOT / 'studios/presentation/skills/presentation-studio/scripts/desk/index.html',
    ROOT / 'studios/training/skills/training-studio/scripts/desk/index.html',
)
STATIC_PAGES = (
    ROOT / 'studios/blog/preview/blog-studio.html',
    ROOT / 'docs/design/unified-settings-preview.html',
)
SHARED = frozenset({
    'window', 'sidebar', 'toolbar', 'nav-item', 'glass', 'sheet', 'card', 'paper', 'button',
    'button-filled', 'button-quiet', 'button-danger', 'button-round', 'input', 'segmented',
    'seg-option', 'chip', 'pick-card', 'dialog', 'toast', 'notice', 'workflow-step'})
ELEMENTS = frozenset({'a', 'button', 'dialog', 'h1', 'h2', 'h3', 'h4', 'input', 'label',
                      'select', 'summary', 'textarea'})
LAYOUT = re.compile(
    r'(display|flex(-[a-z]+)?|grid(-[a-z]+)*|gap|row-gap|column-gap|order|align-[a-z]+|'
    r'justify-[a-z]+|place-[a-z]+|(min-|max-)?(width|height)|(margin|padding)(-[a-z]+)*|'
    r'position|inset|top|right|bottom|left|z-index|overflow(-[a-z]+)?|white-space|'
    r'text-align|overflow-wrap|word-break|box-sizing|touch-action|aspect-ratio)')
COLOUR = re.compile(r'#[0-9a-fA-F]{3,8}\b|\b(rgba?|hsla?|hwb|lab|lch|oklch|oklab)\(')
COMPONENTS = ('.pick-card', '.pick-cards', '.workflow-steps', '.workflow-step', '.dialog',
              '.dialog-header', '.dialog-content', '.dialog-form', 'label.field',
              'label.seg-option', '.input-typed')


def rules(css: str):
    """Each style rule as (selector list, declarations), at any depth, in order."""
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    for match in re.finditer(r'([^{}]+)\{([^{}]*)\}', css):
        selector = match.group(1).strip()
        if selector.startswith('@') or re.fullmatch(r'(from|to|[\d.]+%)(\s*,\s*(from|to|[\d.]+%))*', selector):
            continue
        yield selector, match.group(2)


def selectors(listed: str):
    """Each selector in a list, and the compound it actually styles (its last one)."""
    flat = re.sub(r'\([^()]*\)', '()', re.sub(r'\[[^\]]*\]', '[]', listed))
    for one in flat.split(','):
        one = one.strip()
        yield one, re.split(r'\s*[>+~]\s*|\s+', one)[-1]


def properties(block: str):
    return [part.split(':', 1)[0].strip().lower() for part in block.split(';') if ':' in part]


def tag(compound: str):
    found = re.match(r'([a-z][a-z0-9]*)', compound)
    return found.group(1) if found else None


def problems(css: str) -> list[str]:
    found = []
    if COLOUR.search(re.sub(r'/\*.*?\*/', '', css, flags=re.S)):
        found.append('a literal colour: use a token from ui-kit/style.css')
    for listed, block in rules(css):
        for whole, last in selectors(listed):
            if tag(whole) in ELEMENTS:
                found.append(f'{whole}: styles every {tag(whole)} on the page')
                continue
            if set(re.findall(r'\.([A-Za-z0-9_-]+)', last)) & SHARED or tag(last) in ELEMENTS:
                drawn = [name for name in properties(block)
                         if not name.startswith('--') and not LAYOUT.fullmatch(name)]
                if drawn:
                    found.append(f'{whole}: redraws a shared control ({", ".join(drawn)})')
    return found


def inline_styles(html: str) -> str:
    return '\n'.join(re.findall(r'<style>(.*?)</style>', html, flags=re.S))


class SharedLookTests(unittest.TestCase):
    def test_kit_defines_every_shared_component(self):
        kit = KIT.read_text()
        for component in COMPONENTS:
            with self.subTest(component=component):
                self.assertRegex(kit, re.escape(component) + r'\s*[{,:\[]')

    def test_page_stylesheets_only_lay_out(self):
        for sheet in PAGE_STYLES:
            with self.subTest(sheet=sheet.relative_to(ROOT).as_posix()):
                self.assertEqual(problems(sheet.read_text()), [])

    def test_app_pages_share_the_shell(self):
        for page in APP_PAGES:
            html = page.read_text()
            with self.subTest(page=page.relative_to(ROOT).as_posix()):
                self.assertRegex(html, r'<link rel="stylesheet" href="/?style\.css">')
                for shell in ('class="window"', 'sidebar glass', 'toolbar glass', 'class="page"',
                              'class="backdrop"'):
                    self.assertIn(shell, html)

    def test_static_pages_use_the_kit(self):
        for page in STATIC_PAGES:
            html = page.read_text()
            with self.subTest(page=page.relative_to(ROOT).as_posix()):
                linked = re.findall(r'<link rel="stylesheet" href="([^"]+)">', html)
                self.assertIn(KIT.resolve(), [(page.parent / href).resolve() for href in linked])
                self.assertIn('toolbar glass', html)
                self.assertEqual(problems(inline_styles(html)), [])

    def test_blog_dialogs_take_the_shared_look(self):
        html = APP_PAGES[1].read_text()
        tags = re.findall(r'<dialog\b[^>]*>', html)
        self.assertTrue(tags)
        for found in tags:
            self.assertIn('class="dialog"', found)


if __name__ == '__main__':
    unittest.main()
