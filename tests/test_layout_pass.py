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
        for view, lede in (('home', 'Start with an idea, a draft or a source document.'),
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
        # The four everyday choices first, each a setup step; then the named Advanced parts,
        # which only Shared settings shows, after its Advanced heading.
        self.assertEqual(cards, [
            ('0', 'You and your assistant'), ('1', 'Your workspace'), ('2', 'Brand'),
            ('2', 'Delivery and previews'), ('settings', 'Models and reasoning'),
            ('settings', 'Brand skill release'), ('settings', 'Research sites'),
            ('settings', 'Studio installations')])
        order = [node.attrs.get('id') for node in form.children if node.attrs.get('id')]
        self.assertLess(order.index('delivery-part'), order.index('advanced-head'))
        self.assertLess(order.index('advanced-head'), order.index('models-part'))
        self.assertNotIn('setup-part', (WEB / 'index.html').read_text())

    def test_first_run_steps_name_their_first_card(self):
        html = page()
        steps = [node.words() for node in html.find('setup-progress').all() if node.tag == 'li']
        self.assertEqual(steps, ['1. You and your assistant', '2. Your workspace', '3. Brand and delivery'])
        script = (WEB / 'app.js').read_text()
        self.assertIn("const labels = ['You and your assistant', 'Your workspace', 'Brand and delivery'];", script)

    def test_moved_setup_controls_are_in_their_new_cards(self):
        html = page()
        for control, title, step in (('model-profiles', 'Models and reasoning', 'settings'),
                                     ('assistant-model', 'Models and reasoning', 'settings'),
                                     ('brand-release', 'Brand skill release', 'settings'),
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
        self.assertEqual(cards['blog']['plain'], ['Open'])
        self.assertEqual(cards['blog']['actions'], ['Connect', 'Open'])
        self.assertEqual(cards['presentation']['filled'], ['Return'])
        self.assertEqual(cards['presentation']['plain'], [])

    def test_the_studio_status_is_a_state_with_a_bead(self):
        cards = self.page([{'home': self.SHOWN}, {'snapshot': 'home'}])['home']['cards']
        self.assertEqual(len(cards), 3)
        for card in cards:
            with self.subTest(studio=card['studio']):
                self.assertEqual(card['order'][0], 'studio-symbol')
                self.assertIn('studio-readiness', card['order'])
                self.assertIsNotNone(card['status'])
                self.assertFalse(any('studio-status' in name or 'studio-icon' in name for name in card['order']))
        # A card that the server said nothing about is not called ready.
        self.assertEqual({card['studio']: card['status'] for card in cards},
                         {'blog': ['none', 'Not checked'], 'presentation': ['none', 'Not checked'],
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


@unittest.skipUnless(shutil.which('node'), 'The page journey needs Node.js.')
class SharedSetupJourneyTests(PageLayoutTests):
    """Issue 215: a short everyday setup, named Advanced parts that show their overrides while
    closed, a visible saved state, and launch readiness explained on the card itself."""
    OVERRIDES = {
        'person': {'name': 'Ana'}, 'assistant': {'agent': 'claude', 'model': None, 'effort': None},
        'local': {'root': '/tmp/studios'}, 'team': {'branch': 'main'}, 'share': 'decision',
        'output': 'pptx', 'kept': {'by': 'another tool'},
        'brand': {'repository': 'https://example.com/brand.git', 'release': 'v1.4.0'},
        'models': {'schema': 1, 'agent': 'claude', 'mode': 'by_task', 'profiles': {
            'quick': {'selection': 'explicit', 'model': 'synthetic-small', 'effort': 'low'},
            'main': {'selection': 'inherit'}, 'complex': {'selection': 'provider_default'}}},
        'research': {'sites': ['https://docs.example.com/guide']}}
    STATE = ['save-state', 'models-owner', 'models-state', 'release-owner', 'release-state',
             'research-state', 'installations-owner', 'settings-nav', 'advanced-head', 'models-part',
             'release-part', 'research-sites', 'installations', 'done-settings']

    def shown(self, **changes):
        return {**self.SHOWN, 'shared': {**self.OVERRIDES, **changes}, 'computer': None}

    def test_overrides_stay_visible_and_an_everyday_save_sends_only_what_changed(self):
        saved = {**self.shown(), 'shared': {**self.OVERRIDES, 'person': {'name': 'Bea'}}}
        shots = self.page([
            {'run': 'snapshot = ' + json.dumps(self.shown()) + '; setup = false; fill(); renderHome(); markSaved();'},
            {'show': 'settings'}, {'snapshot': 'shown', 'ids': self.STATE},
            {'run': "form.elements['person.name'].value = 'Bea'; form.fire('input');"
                    " $('#probe').textContent = JSON.stringify(changesForStep());"},
            {'snapshot': 'typed', 'ids': ['save-state'], 'read': ['#probe']},
            {'show': 'home'}, {'snapshot': 'left'}, {'show': 'settings'},
            {'responses': {'shared': saved}}, {'submit': True},
            {'snapshot': 'saved', 'ids': ['save-state', 'problem'], 'read': ['#problem']}])
        shown = shots['shown']
        self.assertEqual(shown['words']['save-state'], 'All changes saved')
        self.assertEqual(shown['words']['models-owner'], 'Override')
        self.assertIn('By task: 2 of 3 tasks have their own model', shown['words']['models-state'])
        self.assertEqual((shown['words']['release-owner'], shown['words']['release-state']),
                         ('Override', 'Pinned to v1.4.0'))
        self.assertEqual(shown['words']['research-state'], '1 site')
        self.assertEqual(shown['words']['installations-owner'], 'Found automatically')
        self.assertFalse(any(shown['hidden'][part] for part in (
            'settings-nav', 'advanced-head', 'models-part', 'release-part', 'research-sites',
            'installations', 'done-settings')))
        self.assertEqual(shots['typed']['words']['save-state'], 'Unsaved changes')
        # Only the leaf that was typed is sent; every override and unknown value is left alone.
        self.assertEqual(json.loads(shots['typed']['read']['#probe']['text']), {'person': {'name': 'Bea'}})
        self.assertIn('not saved yet', ' '.join(shots['left']['toasts']))
        sent = [request['sent'] for request in shots['saved']['requests'] if request['url'].endswith('/api/shared')]
        self.assertEqual(sent, [{'changes': {'person': {'name': 'Bea'}}, 'seen': self.shown()['shared']}])
        self.assertTrue(shots['saved']['words']['save-state'].startswith('Saved at'))
        self.assertTrue(shots['saved']['hidden']['problem'])

    def test_a_refused_save_keeps_the_typed_change_unsaved(self):
        shots = self.page([
            {'run': 'snapshot = ' + json.dumps(self.shown()) + '; setup = false; fill(); renderHome(); markSaved();'},
            {'show': 'settings'},
            {'run': "form.elements['person.name'].value = 'Bea'; form.fire('input');"},
            {'responses': {'shared': {'error': 'Another studio changed this setting. Reload the page and try again.'}}},
            {'submit': True}, {'snapshot': 'refused', 'ids': ['save-state'], 'read': ['#problem']}])
        refused = shots['refused']
        self.assertEqual(refused['words']['save-state'], 'Unsaved changes')
        self.assertIn('Another studio changed', refused['read']['#problem']['text'])

    def test_first_run_setup_asks_only_the_everyday_choices(self):
        shots = self.page([
            {'run': 'snapshot = ' + json.dumps({**self.shown(), 'setup': {'done': False}})
                    + '; setup = true; step = 0; fill(); renderHome(); show("settings");'},
            {'snapshot': 'first', 'ids': self.STATE + ['assistant-part', 'models-pointer']}])
        first = shots['first']
        self.assertFalse(first['hidden']['assistant-part'])
        for part in ('settings-nav', 'advanced-head', 'models-part', 'release-part', 'research-sites',
                     'installations', 'save-state', 'done-settings'):
            with self.subTest(part=part):
                self.assertTrue(first['hidden'][part])
        self.assertIn('after setup', first['words']['models-pointer'])

    def test_buttons_that_change_the_form_update_the_save_state(self):
        load = 'snapshot = ' + json.dumps(self.shown()) + '; setup = false; fill(); renderHome(); markSaved();'
        walk = "const walk = node => [node, ...(node.children || []).flatMap(walk)];"
        brands = {'skills': [{'name': 'Synthetic brand skill', 'path': '/opt/brand-skill', 'brands': [
            {'name': 'Example', 'brand': 'example', 'variants': ['light']}]}]}
        shots = self.page([
            {'run': load}, {'show': 'settings'}, {'snapshot': 'shown', 'ids': ['save-state', 'research-state']},
            {'type': 'docs.other.com'}, {'click': 'add'},
            {'snapshot': 'added', 'ids': ['save-state', 'research-state']},
            {'click': 'remove', 'index': 1}, {'snapshot': 'removed', 'ids': ['save-state', 'research-state']},
            {'responses': {'brands': brands}},
            {'run': "(async () => { $('#find-brands').fire('click'); for (let i = 0; i < 20; i += 1) await null;"
                    + walk + " walk($('#brand-choices')).find(node => node.tagName === 'BUTTON').fire('click'); })()"},
            {'snapshot': 'brand', 'ids': ['save-state']},
            {'run': load + " show('settings'); form.elements['assistant.agent'].value = 'codex';"
                    " $('#confirm-profiles').fire('click');"},
            {'snapshot': 'profiles', 'ids': ['save-state']}],
            answers={'docs.other.com': {'site': 'https://docs.other.com'}})
        self.assertEqual(shots['shown']['words'], {'save-state': 'All changes saved', 'research-state': '1 site'})
        self.assertEqual(shots['added']['words'], {'save-state': 'Unsaved changes', 'research-state': '2 sites'})
        self.assertEqual(shots['removed']['words'], {'save-state': 'All changes saved', 'research-state': '1 site'})
        self.assertEqual(shots['brand']['words']['save-state'], 'Unsaved changes')
        self.assertEqual(shots['profiles']['words']['save-state'], 'Unsaved changes')

    def test_an_unchanged_group_sends_none_of_the_defaults_the_form_filled_in(self):
        # A config without team, share, output, render, brand or models: the form shows their
        # defaults, and saving another value must not write those defaults unasked.
        sparse = {**self.SHOWN, 'computer': None, 'shared': {
            'person': {'name': 'Ana'}, 'assistant': {'agent': 'claude'}, 'local': {'root': '/tmp/studios'}}}
        probe = "$('#probe').textContent = JSON.stringify(changesForStep());"
        shots = self.page([
            {'run': 'snapshot = ' + json.dumps(sparse) + '; setup = false; fill(); renderHome(); markSaved();'},
            {'run': "form.elements['person.name'].value = 'Bea'; " + probe},
            {'snapshot': 'name', 'read': ['#probe']},
            {'run': "form.elements['models.mode'].value = 'by_task'; " + probe},
            {'snapshot': 'models', 'read': ['#probe']}])
        self.assertEqual(json.loads(shots['name']['read']['#probe']['text']), {'person': {'name': 'Bea'}})
        # A group the person did change is sent whole, as the config needs it.
        models = json.loads(shots['models']['read']['#probe']['text'])['models']
        self.assertEqual((models['schema'], models['agent'], models['mode']), (1, 'claude', 'by_task'))

    def test_a_card_says_what_is_missing_and_recovers_without_launching(self):
        home = {**self.shown(), 'studios': [
            {'id': 'blog', 'name': 'Blog Studio', 'installed': True, 'running': False, 'configured_path': '',
             'path': '/opt/blog', 'readiness': {'state': 'review', 'label': 'Needs setup',
                                                'detail': 'Git was not found on this computer.',
                                                'action': {'view': 'computer', 'label': 'Check this computer'}}},
            {'id': 'presentation', 'name': 'Presentation Studio', 'installed': True, 'running': False,
             'configured_path': '', 'path': '/opt/p', 'readiness': {
                 'state': 'done', 'label': 'Can open', 'detail': 'Setup, Claude Code and Git found.', 'action': None}}]}
        look = {'checked_at': '2026-10-30T12:00:00+00:00', 'ready': False, 'items': [
            {'name': 'Git identity', 'ready': False, 'optional': False, 'detail': 'Set it.'},
            {'name': 'Codex', 'ready': False, 'optional': True, 'detail': 'Not found'}]}
        walk = "const walk = node => [node, ...(node.children || []).flatMap(walk)];"
        shots = self.page([
            {'home': home}, {'snapshot': 'cards', 'ids': ['ready-computer', 'computer-summary', 'go-check']},
            {'responses': {'computer': {'computer': look}}},
            {'run': '(async () => {' + walk + " walk($('#studio-list')).find(node => /studio-recover/"
                    ".test(node.className || '')).fire('click');"
                    " for (let i = 0; i < 20; i += 1) await null; })()"},
            {'snapshot': 'checked', 'ids': ['computer-summary', 'check'], 'read': []}])
        cards = {card['studio']: card for card in shots['cards']['cards']}
        self.assertEqual(cards['blog']['status'], ['review', 'Needs setup'])
        self.assertEqual(cards['blog']['detail'], 'Git was not found on this computer.')
        self.assertEqual(cards['blog']['recover'], 'Check this computer')
        self.assertEqual((cards['presentation']['status'], cards['presentation']['recover']),
                         (['done', 'Can open'], None))
        self.assertIn('checked only when you ask', shots['cards']['words']['computer-summary'])
        self.assertEqual(shots['cards']['words']['go-check'], 'Check this computer')
        # The recovery is a local look at this computer, and the summary then says what it found.
        urls = [request['url'] for request in shots['checked']['requests']]
        self.assertEqual([url.split('/api/')[1] for url in urls], ['computer'])
        self.assertFalse(shots['checked']['hidden']['check'])
        self.assertEqual(shots['checked']['words']['computer-summary'],
                         'Missing: Git identity. This computer says how to fix it.')


if __name__ == '__main__':
    unittest.main()
