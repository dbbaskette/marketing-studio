"""Marketing Studio's home and shared setup follow the Layout rules in docs/design/golden-gate.md.

One lede a view, one heading a card, the card titles the only titles of a setup step, This
computer's check in its toolbar, and launch cards drawn with the shared tile and status line.
Read from index.html and app.js, and through tests/settings_page_harness.js.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEB = ROOT / 'core/studio_core/setup_web'
HARNESS = ROOT / 'tests/settings_page_harness.js'
VOID = {'meta', 'link', 'input', 'br', 'img', 'hr', 'source', 'area', 'base', 'col', 'wbr'}
HEADINGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'}


class Node:
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent, self.children, self.text = tag, dict(attrs), parent, [], []

    @property
    def classes(self):
        return (self.attrs.get('class') or '').split()

    def all(self):
        for child in self.children:
            yield child
            yield from child.all()

    def words(self):
        return ' '.join(' '.join([*self.text, *(child.words() for child in self.children)]).split())

    def inside(self, other):
        at = self.parent
        while at:
            if at is other:
                return True
            at = at.parent
        return False


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.root = self.at = Node('#root', {}, None)
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.at)
        self.at.children.append(node)
        if tag not in VOID:
            self.at = node

    def handle_endtag(self, tag):
        at = self.at
        while at.parent and at.tag != tag:
            at = at.parent
        if at.parent:
            self.at = at.parent

    def handle_data(self, data):
        self.at.text.append(data)

    def find(self, id_):
        return next(node for node in self.root.all() if node.attrs.get('id') == id_)


def page():
    return Page((WEB / 'index.html').read_text())


def headings(card):
    """The heading elements of a card, outside any card inside it."""
    nested = [node for node in card.all() if 'card' in node.classes]
    return [node for node in card.all() if node.tag in HEADINGS
            and not any(node.inside(inner) for inner in nested)]


class StaticLayoutTests(unittest.TestCase):
    def test_each_view_has_one_lede(self):
        html = page()
        for view, lede in (('home', 'Open a studio to start or continue your work.'),
                           ('settings', 'New work in every studio starts with these choices.'),
                           ('computer', 'Check the tools your studios need on this computer.')):
            with self.subTest(view=view):
                found = [node for node in html.find(view).all() if 'lede' in node.classes]
                self.assertEqual([node.words() for node in found], [lede])

    def test_no_sheet_heading_inside_a_card(self):
        self.assertNotIn('sheet-part', (WEB / 'index.html').read_text())
        self.assertNotIn('sheet-part', (WEB / 'app.js').read_text())
        cards = [node for node in page().root.all() if node.tag == 'section' and 'card' in node.classes]
        self.assertGreaterEqual(len(cards), 10)
        for card in cards:
            with self.subTest(card=card.attrs.get('id') or card.words()[:40]):
                self.assertEqual(len(headings(card)), 1)
                self.assertIn('card-title', headings(card)[0].classes)

    def test_check_computer_sits_in_the_toolbar(self):
        html = page()
        check = html.find('check')
        bar = next(node for node in html.root.all() if 'toolbar-actions' in node.classes)
        self.assertTrue(check.inside(bar))
        self.assertIn('button-filled', check.classes)
        self.assertEqual(check.words(), 'Check computer')

    def test_installations_are_saved_by_the_one_save(self):
        # Piece 1 put the installation folders in the settings form, so one Save writes both
        # (test_research_sites.SettingsPageJourneyTests.test_one_save_writes_settings_and_folders).
        html = page()
        form = html.find('settings-form')
        self.assertTrue(html.find('installations').inside(form))
        submits = [node for node in form.all() if node.tag == 'button' and node.attrs.get('type') == 'submit']
        self.assertEqual([node.attrs.get('id') for node in submits], ['save'])
        self.assertTrue(html.find('save').inside(form))

    def test_each_setup_part_is_a_card_of_its_own(self):
        html = page()
        form = html.find('settings-form')
        cards = [(node.attrs.get('data-step'), headings(node)[0].words()) for node in form.children
                 if node.tag == 'section' and 'card' in node.classes]
        self.assertEqual(cards, [
            ('0', 'You and your assistant'), ('0', 'Models for your work'),
            ('1', 'Your workspace'), ('2', 'Brand'),
            ('2', 'Delivery and previews'), ('settings', 'Research sites'),
            ('settings', 'Studio installations')])
        self.assertNotIn('setup-part', (WEB / 'index.html').read_text())

    def test_first_run_steps_name_their_first_card(self):
        html = page()
        steps = [node.words() for node in html.find('setup-progress').all() if node.tag == 'li']
        self.assertEqual(steps, ['1. You and your assistant', '2. Your workspace', '3. Brand and delivery'])
        script = (WEB / 'app.js').read_text()
        self.assertIn("const labels = ['You and your assistant', 'Your workspace', 'Brand and delivery'];", script)

    def test_moved_setup_controls_are_in_their_new_cards(self):
        html = page()
        for control, title, step in (('model-profiles', 'Models for your work', '0'),
                                     ('output', 'Delivery and previews', '2')):
            with self.subTest(control=control):
                node = html.find(control)
                card = node.parent
                while 'card' not in card.classes:
                    card = card.parent
                self.assertEqual(headings(card)[0].words(), title)
                self.assertEqual(card.attrs.get('data-step'), step)

    def test_research_sites_are_a_table(self):
        html = page()
        listed = html.find('research-site-list')
        self.assertEqual(listed.tag, 'tbody')
        self.assertIn('table', listed.parent.classes)
        script = (WEB / 'app.js').read_text()
        self.assertIn("element('tr', '', 'site-row')", script)
        self.assertIn("shown.dataset.label = 'Site'", script)


@unittest.skipUnless(shutil.which('node'), 'The page journey needs Node.js.')
class PageLayoutTests(unittest.TestCase):
    SHOWN = {'shared': {'person': {'name': 'Ana'}, 'research': {'sites': []},
                        'review': {'level': 'balanced'}, 'output': 'pptx', 'render': {'previews': None},
                        'team': {'repository': 'https://example.com/team/work.git'}},
             'efforts': {'claude': [], '': []}, 'setup': {'done': True}, 'network': None,
             'studios': [
                 {'id': 'blog', 'name': 'Blog Studio', 'description': 'Write posts.', 'installed': True,
                  'running': False, 'version': '1.0', 'configured_path': '', 'path': '/opt/blog',
                  'workspace': {'state': 'disconnected', 'summary': 'Local Git', 'connect': True}},
                 {'id': 'presentation', 'name': 'Presentation Studio', 'description': 'Make decks.',
                  'installed': True, 'running': True, 'configured_path': '', 'path': '/opt/p',
                  'workspace': {'state': 'connected', 'summary': 'Shared repository'}},
                 {'id': 'training', 'name': 'Training Studio', 'description': 'Make trainings.',
                  'installed': False, 'running': False, 'configured_path': '', 'path': '',
                  'repository': 'https://example.com/training'}]}

    def page(self, steps, **plan):
        with tempfile.TemporaryDirectory() as temp:
            file = Path(temp) / 'steps.json'
            file.write_text(json.dumps({'steps': steps, **plan}))
            done = subprocess.run(['node', str(HARNESS), str(file)], capture_output=True, text=True,
                                  timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_check_computer_shows_only_on_this_computer(self):
        shots = self.page([{'home': self.SHOWN},
                           {'show': 'computer'}, {'snapshot': 'computer', 'ids': ['check']},
                           {'show': 'home'}, {'snapshot': 'home', 'ids': ['check']},
                           {'show': 'settings'}, {'snapshot': 'settings', 'ids': ['check']}])
        self.assertEqual([shots[name]['hidden']['check'] for name in ('computer', 'home', 'settings')],
                         [False, True, True])

    def test_first_run_setup_has_one_title_per_step(self):
        shots = self.page([{'home': {**self.SHOWN, 'setup': {'done': False}}},
                           {'run': "setup = true; step = 0; show('settings');"},
                           {'snapshot': 'first', 'ids': ['step-label', 'settings-title', 'settings-intro',
                                                         'view-title', 'check']}])
        first = shots['first']
        self.assertTrue(first['hidden']['step-label'])
        self.assertTrue(first['hidden']['settings-title'])
        self.assertTrue(first['hidden']['check'])
        self.assertEqual(first['words']['settings-intro'], 'Set up once, and every studio starts with these choices.')
        self.assertEqual(first['words']['view-title'], 'Welcome to Marketing Studio')

    def test_a_card_that_needs_connect_fills_connect(self):
        cards = {card['studio']: card for card in self.page([{'home': self.SHOWN}, {'snapshot': 'home'}])['home']['cards']}
        self.assertEqual(cards['blog']['filled'], ['Connect'])
        self.assertEqual(cards['blog']['plain'], ['Open Blog Studio'])
        order = cards['blog']['order']
        self.assertLess(order.index('button studio-connect button-filled'), order.index('button studio-open'))
        self.assertEqual(cards['presentation']['filled'], ['Return to Presentation Studio'])
        self.assertEqual(cards['presentation']['plain'], [])

    def test_the_studio_status_is_a_state_with_a_bead(self):
        cards = self.page([{'home': self.SHOWN}, {'snapshot': 'home'}])['home']['cards']
        self.assertEqual(len(cards), 3)
        for card in cards:
            with self.subTest(studio=card['studio']):
                self.assertEqual(card['order'][0], 'studio-symbol')
                self.assertIn('state', card['order'])
                self.assertFalse(any('studio-status' in name or 'studio-icon' in name for name in card['order']))
        self.assertEqual({card['studio']: card['status'] for card in cards},
                         {'blog': ['done', 'Ready to open'], 'presentation': ['done', 'Ready to open'],
                          'training': ['off', 'Not installed']})
        running = {card['studio']: card['running'] for card in cards}
        self.assertIn('Running', running['presentation'])
        self.assertNotIn('Running', running['blog'])

    def test_moved_setup_controls_are_reachable(self):
        shots = self.page([{'home': self.SHOWN}, {'show': 'settings'},
                           {'snapshot': 'settings', 'ids': ['delivery-part', 'installations', 'save']},
                           {'show': 'computer'}, {'snapshot': 'computer', 'ids': ['check']}])
        settings = shots['settings']['hidden']
        self.assertEqual(settings, {'delivery-part': False, 'installations': False,
                                    'save': False})
        self.assertFalse(shots['computer']['hidden']['check'])
        self.assertEqual(shots['settings']['words']['save'], 'Save settings')


if __name__ == '__main__':
    unittest.main()
