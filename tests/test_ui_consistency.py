"""One look across every page: page stylesheets lay out their own parts and nothing else.

`ui-kit/style.css` owns the tokens, the shell and the controls. A page's stylesheet may
place a shared control (its size, gaps, grid cell) but never redraw it, may not style bare
controls or headings for the whole page, and takes every colour from a token.

The guard reads selectors. It cannot see a page class that sits on the same element as a
shared one (`class="card studio-card"`), and it does not read nested CSS rules; review
those by hand.
"""
import os
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
# Each static page and the folder it is served from. Its stylesheet must be inside that folder.
STATIC_PAGES = {
    ROOT / 'studios/blog/preview/blog-studio.html': ROOT / 'studios/blog',
    ROOT / 'docs/design/unified-settings-preview.html': ROOT,
}
SHELL = (('backdrop',), ('window',), ('sidebar', 'glass'), ('toolbar', 'glass'), ('page',))
COMPONENTS = ('.pick-card', '.pick-cards', '.workflow-steps', '.workflow-step', '.dialog',
              '.dialog-header', '.dialog-content', '.dialog-form', 'label.field',
              'label.seg-option', '.input-typed')
SHARED = frozenset({
    'backdrop', 'window', 'sidebar', 'nav-item', 'glass', 'content', 'toolbar-wrap', 'toolbar',
    'page', 'button', 'button-filled', 'button-quiet', 'button-danger', 'button-round', 'field',
    'field-label', 'input', 'input-typed', 'field-hint', 'segmented', 'seg-option', 'chips',
    'chip', 'pick-cards', 'pick-card', 'pick-title', 'pick-says', 'workflow-steps',
    'workflow-step', 'card', 'paper', 'table', 'callout', 'large-title', 'lede', 'card-title',
    'sheet-part', 'state', 'bead', 'tag', 'toasts', 'toast', 'notice', 'sheet', 'dialog',
    'dialog-header', 'dialog-content', 'dialog-form', 'menu'})
ELEMENTS = frozenset({'a', 'button', 'dialog', 'h1', 'h2', 'h3', 'h4', 'input', 'label',
                      'select', 'summary', 'textarea', 'table', 'thead', 'tbody', 'tr', 'th',
                      'td'})
ROOTS = frozenset({'html', 'body'})
LAYOUT = re.compile(
    r'(display|flex(-[a-z]+)?|grid(-[a-z]+)*|gap|row-gap|column-gap|order|align-[a-z]+|'
    r'justify-[a-z]+|place-[a-z]+|(min-|max-)?(width|height|inline-size|block-size)|'
    r'(margin|padding|inset)(-[a-z]+)*|'
    r'position|top|right|bottom|left|z-index|overflow(-[a-z]+)?|white-space|'
    r'text-align|overflow-wrap|word-break|box-sizing|touch-action|aspect-ratio)')
COLOUR = re.compile(r'#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?|hwb|lab|lch|oklch|oklab|color)\(|'
                    r'(?<![\w-])(?:white|black|red|green|blue|yellow|orange|purple|pink|gray|grey|'
                    r'silver|navy|teal)(?![\w-])', re.I)


def uncommented(css: str) -> str:
    return re.sub(r'/\*.*?\*/', '', css, flags=re.S)


def rules(css: str):
    """Each style rule as (selector list, declarations), at any depth, in order."""
    for match in re.finditer(r'([^{}]+)\{([^{}]*)\}', uncommented(css)):
        # Text before the last ';' is a statement such as @import or @layer, not the selector.
        selector = match.group(1).rsplit(';', 1)[-1].strip()
        if selector.startswith('@') or re.fullmatch(r'(from|to|[\d.]+%)(\s*,\s*(from|to|[\d.]+%))*', selector):
            continue
        yield selector, match.group(2)


def split_top(text: str, marks: str):
    """Split at any of marks outside brackets and quotes."""
    parts, depth, quote, start = [], 0, '', 0
    for at, char in enumerate(text):
        if quote:
            quote = '' if char == quote else quote
        elif char in '"\'':
            quote = char
        elif char in '([':
            depth += 1
        elif char in ')]':
            depth -= 1
        elif depth == 0 and char in marks:
            parts.append(text[start:at])
            start = at + 1
    return [part for part in parts + [text[start:]] if part.strip()]


def styled(compound: str):
    """The classes and element names a compound styles. :not() and :has() arguments and
    attribute values do not count; :is() and :where() arguments do."""
    text = re.sub(r'\[[^\]]*\]', '', compound)
    text = re.sub(r':(not|has)\((?:[^()]|\([^()]*\))*\)', '', text)
    classes = set(re.findall(r'\.([A-Za-z0-9_-]+)', text))
    tags = set(re.findall(r'(?:^|[(,]\s*)([a-z][a-z0-9]*)', text))
    return classes, tags, text


def selectors(listed: str):
    """Each selector in a list, with what its last compound styles and whether anything
    narrower than an element or the page root scopes it."""
    for one in split_top(listed, ','):
        one = ' '.join(one.split())
        last = split_top(one, ' >+~')[-1]
        classes, tags, _ = styled(last)
        scoped = re.search(r'[.#]', styled(one)[2]) is not None
        yield one, classes, tags | ({'*'} if last.startswith(('*', ':root')) else set()), scoped


def properties(block: str):
    return [part.split(':', 1)[0].strip().lower() for part in block.split(';') if ':' in part]


def colours(css: str):
    """Literal colours in declarations. Selectors such as #add-source are not colours."""
    values = ' '.join(block for _, block in re.findall(r'([^{}]*)\{([^{}]*)\}', uncommented(css)))
    values = re.sub(r'url\([^)]*\)', '', values)
    return sorted({match.group(0) for match in COLOUR.finditer(values)})


def problems(css: str) -> list[str]:
    found = []
    literal = colours(css)
    if literal:
        found.append(f'literal colours {", ".join(literal)}: use a token from ui-kit/style.css')
    for listed, block in rules(css):
        for whole, classes, tags, scoped in selectors(listed):
            if not scoped and tags & ELEMENTS:
                found.append(f'{whole}: styles every {"/".join(sorted(tags & ELEMENTS))} on the page')
                continue
            if classes & SHARED or tags & (ELEMENTS | ROOTS) or (not scoped and '*' in tags):
                drawn = [name for name in properties(block) if not LAYOUT.fullmatch(name)]
                if drawn:
                    found.append(f'{whole}: redraws a shared control ({", ".join(drawn)})')
    return found


def inline_styles(html: str) -> str:
    return '\n'.join(re.findall(r'<style\b[^>]*>(.*?)</style>', html, flags=re.S))


def stylesheets(html: str) -> list[str]:
    return re.findall(r'<link\b[^>]*\brel="stylesheet"[^>]*\bhref="([^"]+)"', html)


def missing_classes(html: str, wanted) -> list[str]:
    """Each wanted set of classes that no single element carries."""
    present = [set(found.split()) for found in re.findall(r'\bclass="([^"]*)"', html)]
    return [' '.join(names) for names in wanted if not any(set(names) <= found for found in present)]


class SharedLookTests(unittest.TestCase):
    maxDiff = None

    def test_kit_defines_every_shared_component(self):
        kit = KIT.read_text()
        missing = [name for name in COMPONENTS if not re.search(re.escape(name) + r'\s*[{,:\[]', kit)]
        self.assertEqual(missing, [], 'ui-kit/style.css does not define these')

    def test_page_stylesheets_only_lay_out(self):
        for sheet in PAGE_STYLES:
            with self.subTest(sheet=sheet.relative_to(ROOT).as_posix()):
                self.assertEqual(problems(sheet.read_text()), [])

    def test_app_pages_share_the_shell(self):
        for page in APP_PAGES:
            html = page.read_text()
            with self.subTest(page=page.relative_to(ROOT).as_posix()):
                self.assertEqual([href.lstrip('/') for href in stylesheets(html)][:1], ['style.css'])
                self.assertEqual((page.parent / 'style.css').resolve(), KIT.resolve())
                self.assertEqual(missing_classes(html, SHELL), [])

    def test_static_pages_use_the_kit(self):
        for page, served in STATIC_PAGES.items():
            html = page.read_text()
            with self.subTest(page=page.relative_to(ROOT).as_posix()):
                linked = [Path(os.path.normpath(page.parent / href)) for href in stylesheets(html)]
                self.assertIn(KIT.resolve(), [path.resolve() for path in linked])
                outside = [str(path) for path in linked if not path.is_relative_to(served)]
                self.assertEqual(outside, [], f'served from {served.relative_to(ROOT)}')
                self.assertEqual(missing_classes(html, (('toolbar', 'glass'),)), [])
                self.assertEqual(problems(inline_styles(html)), [])

    def test_blog_dialogs_take_the_shared_look(self):
        tags = re.findall(r'<dialog\b[^>]*>', APP_PAGES[1].read_text())
        self.assertTrue(tags)
        self.assertEqual([tag for tag in tags if missing_classes(tag, (('dialog',),))], [])

    def test_the_desk_draws_from_ui_kit(self):
        # The desk's parts are drawn by ui-kit/drafting.js, so their styles are the kit's too,
        # last in it, after the fallbacks, where they sat when Blog Studio's stylesheet drew
        # them. Blog Studio's stylesheet keeps only Review mode's placements of desk parts.
        desk = ('.desk-layout', '.desk-column', '.desk-aside', '.desk-part-head', '.desk-text',
                '.desk-note', '.desk-note-text', '.desk-working', '.desk-working-note',
                '.desk-problem', '.desk-stale', '.desk-save-state', '.desk-selection',
                '.desk-versions', '.desk-version', '.desk-compare-area', '.desk-compare',
                '.desk-plain', '.desk-steps', '.desk-clock', '.desk-finishing', '.desk-finish',
                '.desk-finish-head', '.desk-finish-title', '.desk-finish-body',
                '.desk-finish-sheet', '.desk-finish-tools', '.desk-proposal', '.desk-sides',
                '.desk-side', '.desk-quote', '.desk-edit', '.desk-comments', '.desk-comment',
                '.diff-add', '.diff-remove')
        placements = {'.review-checking>.desk-working-note', '.review-fix>.desk-sides',
                      '.review-quick-list .desk-quote'}

        def named(css):
            found = {}
            for listed, block in rules(css):
                for one in split_top(listed, ','):
                    one = ' '.join(one.split())
                    for name in re.findall(r'\.([A-Za-z0-9_-]+)', one):
                        found.setdefault('.' + name, []).append((one, block))
            return found

        kit = KIT.read_text()
        drawn = named(kit)
        self.assertEqual([name for name in desk if name not in drawn], [], 'ui-kit/style.css')
        start = kit.index('/* --- the desk (drafting.js)')
        self.assertGreater(start, kit.index('/* --- fallbacks'))
        self.assertNotIn('/* ---', kit[start + 1:], 'the desk is the last section of the kit')
        blog = named(PAGE_STYLES[1].read_text())
        left = sorted({one for name in desk for one, _ in blog.get(name, [])} - placements)
        self.assertEqual(left, [], 'blog.css still draws these desk parts')
        for name in desk:
            for one, block in blog.get(name, []):
                with self.subTest(placement=one):
                    self.assertEqual([p for p in properties(block) if not LAYOUT.fullmatch(p)], [])
        # The desk parts only Blog Studio has stay in its stylesheet. So does the aside's gap
        # list, which Blog Studio's own tests read there (test_blog_runner).
        for name in ('.desk-angles', '.desk-angle', '.desk-angle-picked', '.desk-outline-part',
                     '.desk-images', '.desk-thumb', '.desk-fold', '.gap-items'):
            self.assertIn(name, blog)
            self.assertNotIn(name, drawn)

    def test_a_choice_set_straight_in_a_card_fits_it_at_phone_width(self):
        # Training Studio's "Where this training stops" puts its three levels straight in a
        # card; at 390px they spilled 24px past the screen. They now fit as a field's do.
        kit = uncommented(KIT.read_text())
        wide = {selector.strip(): block for selector, block in rules(kit)}
        fitted = next((block for selector, block in wide.items()
                       if '.card > .segmented' in selector and 'max-width' in block), '')
        self.assertIn('max-width: 100%', fitted)
        wrapped = next((block for selector, block in wide.items()
                        if '.card > .segmented > .seg-option' in selector
                        and 'white-space' in block), '')
        self.assertIn('white-space: normal', wrapped)
        phone = re.search(r'@media \(max-width: 52rem\) \{(.*?)\n\}', kit, flags=re.S)
        narrow = {selector.strip(): block for selector, block in rules(phone.group(1))}
        self.assertTrue(any('.card > .segmented' in selector and 'display: grid' in block
                            for selector, block in narrow.items()), narrow.keys())


if __name__ == '__main__':
    unittest.main()
