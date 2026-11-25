"""The page, run for real: its shell and its files, markdown.js, and app.js driven screen by
screen in a document with no HTML parser (page_harness.js), against the server's own answers.

Every answer the scripted screens read is what the runner's page gives for a real deck run
over the tests' stand-ins (runner_support), so a gate the engine shows is a gate the page
draws. Nothing starts an agent, looks at the real computer or touches the network.
"""
import base64
import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path
from unittest import mock
from urllib.parse import urlencode

import helpers
import runner_support
from runner_support import LONG_OUTLINE, QUOTE, URL, read_word_for_word, unsettled
from test_runner_page import PageCase

import server
from runner import marks, worker_tools
from runner.steps import build

PAGE = helpers.SCRIPTS / 'desk'
HARNESS = Path(__file__).resolve().parent / 'page_harness.js'
NODE = shutil.which('node')
FORBIDDEN_WORDS = re.compile(r'\b(artifacts?|stale|lineage|trainings?)\b', re.IGNORECASE)
MARKUP = '<script>alert(1)</script>\n<img src=x onerror=alert(2)>\n'
PICTURE = {'status': 200, 'picture': base64.b64encode(runner_support.png()).decode('ascii')}
DECK = b'PK\x03\x04' + b'stand-in deck'
ADDRESS = 'https://github.com/acme/acme-brand.git'
MODELS = {'GET /api/models': [{'status': 200, 'body': {
    'agent': 'claude', 'source': 'Claude Code model list', 'problem': None, 'levels': [],
    'models': [{'name': 'opus', 'label': 'Opus', 'family': None, 'about': None,
                'default_level': None, 'levels': ['low', 'high']}]}}]}


def ok(body) -> dict:
    return {'status': 200, 'body': body}


class PageFileTests(unittest.TestCase):
    """What can be said about the page without a browser."""

    def read(self, name: str) -> str:
        return (PAGE / name).read_text(encoding='utf-8')

    def test_the_vendored_files_are_as_they_were_taken(self):
        vendor = json.loads((helpers.REPO / 'vendor.json').read_text(encoding='utf-8'))
        taken = {entry['path']: entry for entry in vendor['files']}
        for name in ('style.css', 'markdown.js', 'index.html', 'app.js'):
            with self.subTest(name):
                entry = taken[f'skills/presentation-studio/scripts/desk/{name}']
                self.assertEqual(entry['from'], f'skills/training-studio/scripts/desk/{name}')
                self.assertTrue(entry['revision'].startswith('b19c743'))
        self.assertIn('tests/page_harness.js', taken)

    def test_the_page_and_its_stylesheets_are_served_and_nothing_else(self):
        # The deck panels are the shared core's, served beside every studio page.
        # The deck desk is a script of its own, on piece 3's shared desk kit.
        self.assertEqual(set(server.PAGE), {'/', '/index.html', '/app.js', '/markdown.js',
                                            '/style.css', '/deck.css', '/deck-panels.js',
                                            '/deck-panels.css', '/lists.js', '/deck-desk.js',
                                            '/drafting.js', '/research.js', '/library.js',
                                            '/activity.js', '/shell.js', '/desk-base.js'})

    def test_the_page_has_nothing_its_own_policy_would_block(self):
        page = self.read('index.html')
        self.assertNotRegex(page, r'<style\b')
        self.assertNotRegex(page, r'\sstyle\s*=')
        self.assertNotRegex(page, r'\son[a-z]+\s*=')
        self.assertNotRegex(page, r'<svg\b')
        # markdown.js, the desk kit, the shared desk base, deck panels and library sheet, app.js
        # and the deck desk: each a file, none inline.
        self.assertEqual(re.findall(r'<script\b[^>]*>(.*?)</script>', page, re.DOTALL),
                         ['', '', '', '', '', '', '', '', '', '', ''])

    def test_the_shell_names_its_controls_and_its_regions(self):
        page = self.read('index.html')
        self.assertIn('<html lang="en">', page)
        for label in ('Home', 'Decks', 'Status', 'Settings'):
            self.assertRegex(page, rf'<button type="button" id="go-\w+" class="nav-item"[^>]*>'
                                   rf'<span class="nav-label">{label}</span>')
        self.assertIn('<nav id="sidebar" class="sidebar glass" aria-label="Screens">', page)
        self.assertIn('id="notice" class="notice" role="alert"', page)
        self.assertIn('id="toasts" class="toasts" role="status" aria-live="polite"', page)
        self.assertIn('id="sheet" class="sheet glass" role="dialog" aria-modal="true" '
                      'aria-labelledby="sheet-title"', page)
        self.assertEqual(len(re.findall(r'<h1\b', page)), 1)
        self.assertNotRegex(page, r'tabindex="[1-9]')
        self.assertNotRegex(self.read('app.js'), r'tabIndex = [1-9]')

    def test_every_state_has_a_shape_of_its_own(self):
        script = self.read('app.js')
        drawn = dict(re.findall(r"(\w+): '(\w+)'", re.search(
            r'const BEAD_ICONS = \{(.*?)\};', script, re.DOTALL)[1]))
        self.assertEqual(drawn, {'done': 'check', 'review': 'eye', 'late': 'warn',
                                 'out': 'minus', 'off': 'slash'})
        for icon in drawn.values():
            self.assertRegex(script, rf'\n  {icon}: \[')

    def test_only_the_shell_and_a_toast_are_glass_and_motion_can_be_calmed(self):
        script, page = self.read('app.js'), self.read('index.html')
        self.assertEqual(len(re.findall(r'class="[^"]*\bglass\b', page)), 3)
        self.assertEqual(re.findall(r"'([\w -]*\bglass\b[\w -]*)'", script), ['toast glass'])
        self.assertIn('if (document.startViewTransition && !calm())', script)
        self.assertNotIn('followPointer', script)

    def test_the_deck_stylesheet_uses_only_the_vendored_colours(self):
        styles = self.read('deck.css')
        self.assertNotRegex(styles, r'#[0-9a-fA-F]{3,6}\b|rgb\(')
        self.assertNotIn('backdrop-filter', styles)

    def test_a_sheet_heading_hides_what_scrolls_under_it(self):
        # #255: it reached only the sheet's content, was 96% opaque, and a segmented
        # control's options (z-index 1, later on the page) were drawn over it.
        rule = re.search(r'\.sheet > \.sheet-heading:first-child \{(.*?)\}',
                         self.read('style.css'), re.DOTALL)[1]
        self.assertIn('top: -1.1rem;', rule)
        self.assertIn('margin: -1.1rem -1.2rem 0;', rule)
        self.assertIn('z-index: 2;', rule)
        self.assertIn('var(--paper)', rule)
        sheet = re.search(r'\n\.sheet \{(.*?)\}', self.read('style.css'), re.DOTALL)[1]
        self.assertIn('padding: 1.1rem 1.2rem 1.2rem;', sheet)


def tags(tree, found=None) -> list:
    found = [] if found is None else found
    if isinstance(tree, dict):
        found.append(tree['tag'])
        for child in tree.get('children', []):
            tags(child, found)
    return found


def text_of(tree) -> str:
    if isinstance(tree, str):
        return tree
    return ''.join(text_of(child) for child in tree.get('children', []))


@unittest.skipUnless(NODE, 'Node is needed to run the page scripts without a browser')
class MarkdownTests(unittest.TestCase):
    """markdown.js, run for real against a document that has no HTML parser."""

    def render(self, text: str) -> dict:
        done = subprocess.run([NODE, str(HARNESS), 'markdown'], input=text, text=True,
                              capture_output=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        return json.loads(done.stdout)

    def test_an_outline_is_drawn_as_a_document(self):
        tree = self.render('# Rolling restarts\n\n## 1. What it does\n\n- **Batch**: one at a '
                           'time\n\nNotes: 6 min.\n')
        self.assertEqual(tags(tree)[:2], ['div', 'h2'])
        self.assertIn('strong', tags(tree))
        self.assertIn('Notes: 6 min.', text_of(tree))

    def test_markup_in_a_document_is_shown_as_the_text_it_is(self):
        tree = self.render(MARKUP + '\n[a link](javascript:alert(3)) [ok](https://example.com)\n')
        self.assertLessEqual(set(tags(tree)), {'div', 'p', 'br', 'a'})
        for kept in ('<script>alert(1)</script>', '<img src=x onerror=alert(2)>',
                     '[a link](javascript:alert(3))'):
            self.assertIn(kept, text_of(tree))


class ScriptedPage:
    """Runs app.js in the harness, and checks what every screen it shows must hold."""

    def run_page(self, answers: dict, steps: list, layout: bool = True,
                 **plan) -> dict:
        file = self.base / 'plan.json'
        file.write_text(json.dumps({'answers': answers, 'steps': steps, **plan}),
                        encoding='utf-8')
        done = subprocess.run([NODE, str(HARNESS), 'app', str(file)], text=True,
                              capture_output=True, timeout=120)
        self.assertEqual(done.returncode, 0, done.stderr)
        result = json.loads(done.stdout)
        self.assertEqual(result['errors'], [])
        self.assertEqual(result['strayListeners'], [],
                         'only a real control may answer a click, so the keyboard reaches it')
        for name, shot in result['snapshots'].items():
            with self.subTest(screen=name):
                self.assertEqual(shot['unnamed'], [], 'every control has a name')
                self.assertEqual(shot['foreign'], 0, 'nothing from a file became an element')
                self.assertEqual(shot['bareBeads'], 0, 'every bead has words beside it')
                self.assertLessEqual(len(shot['filled']), 1, 'one filled button on a screen')
                self.assertNotRegex(shot['text'] + shot['sheet'], FORBIDDEN_WORDS)
        if layout:
            for name, shot in result['snapshots'].items():
                with self.subTest(screen=name, rule='layout'):
                    self.assertLayout(shot)
        return result

    def assertLayout(self, shot: dict):
        """The layout rules every screen keeps: one lede at most, one heading level in a
        card, no card inside a card, and a toolbar's filled action first with the rest
        quiet."""
        self.assertLessEqual(len(shot['ledes']), 1, f"one lede on a screen: {shot['ledes']}")
        for tags in shot['cardHeadings']:
            self.assertLessEqual(len(tags), 1, f'one heading level in a card: {tags}')
        self.assertEqual(shot['nested'], 0, 'no card inside a card')
        bar = shot['toolbar']
        if any(control['filled'] for control in bar):
            self.assertTrue(bar[0]['filled'], f'the filled action comes first: {bar}')
            self.assertEqual([control['name'] for control in bar[1:] if not control['quiet']],
                             [], 'the rest of the toolbar is quiet')

    def posts(self, result: dict) -> list:
        # Intake autosaves are private bookkeeping; retain them in the raw request log.
        made = [request for request in result['requests'] if request['method'] == 'POST'
                and request['address'] != '/api/intake-draft']
        for post in made:
            self.assertEqual(post['headers'], {server.TOKEN_HEADER: 'the-test-key',
                                               'Content-Type': 'application/json'})
        return [(post['address'], post['body']) for post in made]


@unittest.skipUnless(NODE, 'Node is needed to run the page scripts without a browser')
class ScreenTests(ScriptedPage, PageCase):
    """Each screen, drawn from what the runner's page answers for real decks."""

    def test_home_discovers_private_intake_without_starting_work(self):
        result = self.run_page(self.answers(**{
            'GET /api/intake-draft': [{'status': 200, 'body': {'revision': 1, 'draft': {'title': 'Unfinished synthetic form', 'step': 1, 'intakeOpen': False}}}],
            'POST /api/intake-draft': [{'status': 200, 'body': {'revision': 2, 'draft': None}}]}),
            [{'snapshot': 'home'}, {'click': 'Discard draft'}, {'snapshot': 'confirm'},
             {'click': 'Confirm discard'}, {'snapshot': 'cleared'}])
        home = result['snapshots']['home']
        self.assertIn('Resume draft', home['buttons'])
        self.assertIn('Start new', home['buttons'])
        self.assertIn('Unfinished synthetic form', home['text'])
        self.assertIn('Step 2', home['text'])
        self.assertIn('Confirm discard', result['snapshots']['confirm']['buttons'])
        self.assertNotIn('Resume draft', result['snapshots']['cleared']['buttons'])

    def answers(self, **more) -> dict:
        return {'GET /api/setup': [ok(self.get('setup'))],
                'GET /api/decks': [ok(self.get('decks'))],
                'GET /api/computer': [ok(self.get('computer'))],
                'GET /api/agents': [ok(self.get('agents'))],
                'GET /api/slide': [PICTURE], **MODELS, **more}

    def test_set_up_comes_first_offers_what_the_studios_share_and_saves_the_defaults(self):
        described = self.get('setup')
        fresh = {**described, 'configured': False, 'workspace': None,
                 'suggested': {'repository': 'git@example.com:team/decks.git',
                               'branch': 'decks', 'share_when': 'when-asked'}}
        check = {'ok': True, 'found': {'name': 'decks', 'folder': 'presentations',
                                       'branch': 'decks', 'existing': False},
                 'checks': [{'what': 'the repository can be reached', 'ok': True, 'fix': None}]}
        answers = self.answers(**{'GET /api/setup': [ok(fresh), ok(described)],
                                  'POST /api/setup/check': [ok(check)],
                                  'POST /api/setup': [ok(described)]})
        result = self.run_page(answers, [
            {'snapshot': 'first'},
            {'fill': 'Your name', 'value': 'Alex Doe'},
            {'click': 'Check this computer'},
            {'click': 'Save and go on'}, {'snapshot': 'saved'}])
        first = result['snapshots']['first']
        self.assertEqual((first['heading'], first['sidebar']),
                         ('Set up Presentation Studio', False))
        self.assertEqual(first['filled'], ['Save and go on'])
        for shown in ('Check this computer', 'Workspace', 'Defaults',
                      'This is ready to use.', 'Delivered as',
                      'shared by every studio on this computer'):
            self.assertIn(shown, first['text'])
        self.assertEqual(first['fields']['The repository’s address'],
                         'git@example.com:team/decks.git')
        self.assertEqual(first['fields']['The branch'], 'decks')
        self.assertIn('Only when I ask', first['pressed'])
        sent = dict(self.posts(result))
        self.assertEqual(sent['/api/computer'], {})
        saved = sent['/api/setup']
        # Only a brand the brand skill on this computer has is offered, and so sent.
        brand = {'brand': described['brand']['brands'][0]['brand'],
                 'variant': described['brand']['brands'][0]['variants'][0]}
        self.assertEqual({key: saved[key] for key in ('repository', 'branch', 'folder', 'name',
                                                      'share_when', 'person', 'brand',
                                                      'variant', 'output')},
                         {'repository': 'git@example.com:team/decks.git', 'branch': 'decks',
                          'folder': 'presentations', 'name': 'decks',
                          'share_when': 'when-asked', 'person': 'Alex Doe',
                          'brand': brand['brand'], 'variant': brand['variant'],
                          'output': 'google'})
        # Shared values go to the studios config by the server's own rule, never by a switch.
        self.assertNotIn('for_all_studios', saved)
        # What the form was shown goes with it, so that a value another studio changes
        # meanwhile is never written over.
        self.assertEqual(saved['shared_seen'], fresh['shared'])
        self.assertEqual(sorted(saved['limits']), ['parallel', 'step_seconds'])
        self.assertEqual(result['snapshots']['saved']['heading'], 'Home')

    def test_home_puts_each_deck_where_it_stands_and_a_finished_one_with_its_link(self):
        waiting = self.started(title='Waiting deck')
        done = self.started(title='Finished deck')
        self.deliver_desk(Path(done))
        result = self.run_page(self.answers(), [{'see': 'Every slide of'},
                                                {'snapshot': 'home'}])
        home = result['snapshots']['home']
        self.assertEqual(home['heading'], 'Home')
        self.assertEqual(home['filled'], ['Review Waiting deck'])
        text = home['text']
        self.assertIn('Needs you\nWaiting deck', text)
        self.assertIn('Finished\nFinished deck', text)
        self.assertEqual(home['badge'], '1 thing needs you')
        links = [link for link in home['links'] if link['name'].startswith('Open Finished')]
        self.assertEqual(len(links), 1)
        self.assertTrue(links[0]['href'].startswith('https://'))
        self.assertEqual((links[0]['rel'], links[0]['target']), ('noopener noreferrer', '_blank'))
        self.assertIn('contact-sheet', ' '.join(picture['of'] for picture in home['pictures']))
        self.assertIn(waiting, json.dumps(self.get('decks')['needs']))

    def test_a_new_existing_deck_is_a_route_card_a_level_card_and_an_upload(self):
        answers = self.answers(**{'POST /api/decks': [ok({'path': '/nowhere', 'id': 'x'})],
                                  'GET /api/run': [{'status': 404,
                                                    'body': {'error': 'There is no deck there.'}}]})
        result = self.run_page(answers, [
            {'click': 'New deck'}, {'snapshot': 'routes'},
            {'click': 'An existing deck'}, {'fill': 'A short title', 'value': 'Old deck'}, {'click': 'Start'},
            {'snapshot': 'missing'},
            {'attach': 'The deck, as a .pptx',
             'files': [{'name': 'old.pptx', 'bytes': DECK.decode('latin-1')}]},
            {'click': 'Selected changes'}, {'click': 'Polish'}, {'snapshot': 'levels'},
            {'fill': 'A short title', 'value': 'Old deck'},
            {'intakePage': 2}, {'snapshot': 'last'}, {'click': 'Start'}])
        shots = result['snapshots']
        # The desk's start names the three kinds, and an existing deck's levels on its first
        # step (test_desk_page.StartTests).
        for route in ('An idea', 'A document', 'An existing deck'):
            self.assertTrue(any(name.startswith(route) for name in shots['routes']['buttons']))
        self.assertIn('Choose the file first.', shots['missing']['text'])
        self.assertIn('Choose how much changes.', shots['missing']['text'])
        self.assertEqual(shots['missing']['posts'], 0)
        for level in ('Brand only', 'Polish', 'Redesign, keep content', 'Full rework',
                      'Selected changes'):
            self.assertIn(level, shots['levels']['text'])
        self.assertIn('Chosen: old.pptx', shots['levels']['text'])
        self.assertIn('It runs on its own until the deck opens on the desk.',
                      shots['last']['text'])
        (address, body), = self.posts(result)
        self.assertEqual(address, '/api/decks')
        self.assertEqual(set(body), {'form', 'uploads'})
        form = body['form']
        self.assertEqual((form['route'], form['level'], form['source'], form['title'],
                          form['flow']),
                         ('existing', 'polish', {'kind': 'upload', 'name': 'old.pptx'},
                          'Old deck', 'desk'))
        self.assertEqual(base64.b64decode(body['uploads']['old.pptx']), DECK)
        # What the page sends is what the server takes: a deck on the desk.
        self.workers.queued['outline'] = [read_word_for_word(self)]
        made = self.post('decks', body)
        self.assertEqual(self.run_of(made['path'])['gate']['name'], 'gate:build')
        self.assertTrue(self.run_of(made['path'])['desk']['arrived'])

    def deck_screen(self, path: str, steps: list, narrow: bool = False, **more) -> dict:
        """The deck screen, opened from home, with the deck as the runner shows it now."""
        title = self.run_of(path)['title']
        needs = any(brief['path'] == path for brief in self.get('decks')['needs'])
        answers = self.answers(**{'GET /api/run': [ok(self.run_of(path))], **more})
        return self.run_page(answers, [{'click': ('Review ' if needs else 'Open ') + title},
                                       *steps], narrow=narrow)

    def setup_with(self, **more) -> dict:
        return ok({**self.get('setup'), **more})

    def test_a_scratch_brief_is_sent_with_the_form(self):
        answers = self.answers(**{'POST /api/decks': [ok({'path': '/nowhere', 'id': 'x'})],
                                  'GET /api/run': [{'status': 404, 'body': {'error': 'There is no deck there.'}}]})
        result = self.run_page(answers, [
            {'click': 'New deck'}, {'click': 'An idea'},
            {'fill': 'A short title', 'value': 'Synthetic deck'},
            {'fill': 'What should it cover? (optional)', 'value': ' Cover rollback first. '},
            {'click': 'Start'}])
        (_, body), = self.posts(result)
        self.assertEqual(body['form']['notes'], 'Cover rollback first.')

    SITES = ['blog.example.com/platform', 'docs.example.com']   # as the setup sends them

    ONLY_DOCUMENTS = 'With your documents only, nothing about them is searched for on the public web.'
    SEARCHED = ('Your sites are searched with your assistant’s own web search tool, and only '
                'pages from under them are saved.')

    def site_answer(self, typed: str):
        """What the runner itself answers when the form adds this site."""
        status, reply, _ = self.answer('POST', '/api/research-site',
                                       json.dumps({'site': typed}).encode(), origin=self.origin,
                                       kind='application/json')
        return {'status': status, 'body': reply}

    def test_research_from_a_document_offers_your_documents_your_sites_and_the_web(self):
        from runner import decks
        answers = self.answers(**{'GET /api/setup': [self.setup_with(research_sites=self.SITES)],
                                  'POST /api/research-site': [self.site_answer('learn.example.org/guide/')],
                                  'POST /api/decks': [ok({'path': '/nowhere', 'id': 'x'})],
                                  'GET /api/run': [{'status': 404, 'body': {'error': 'There is no deck there.'}}]})
        result = self.run_page(answers, [
            {'click': 'New deck'}, {'click': 'A document'},
            {'click': 'Paste the text'}, {'fill': 'The text', 'value': 'Synthetic notes.'},
            {'fill': 'A short title', 'value': 'Synthetic deck'},
            {'snapshot': 'off'}, {'tick': 'Research the approved story'}, {'snapshot': 'offered'},
            {'tick': 'your sites'}, {'snapshot': 'sites'},
            {'tick': 'the public web'}, {'tick': 'docs.example.com'},
            {'fill': 'Add a site for this piece of work', 'value': 'learn.example.org/guide/'},
            {'click': 'Add the site'}, {'snapshot': 'chosen'},
            {'fill': 'What should the research answer? (optional)', 'value': 'Why?\nWhat next?'},
            {'snapshot': 'last'}, {'click': 'Start'}])
        self.assertEqual(result['errors'], [])
        off, offered, sites, chosen, last = (result['snapshots'][name] for name in
                                             ('off', 'offered', 'sites', 'chosen', 'last'))
        self.assertNotIn('Research from', off['text'])
        self.assertNotIn('Research uses the public web', offered['text'])
        for shot in (offered, sites, chosen, last):
            self.assertEqual(shot['unnamed'], [])
            self.assertIsNone(FORBIDDEN_WORDS.search(shot['text']))
        # A document's research reads the documents alone until more is ticked: your sites
        # stay off, the shared list ready under them.
        # Research the approved story is a checkbox of its own, ticked first (#255).
        self.assertEqual(offered['chosen'], [])
        self.assertEqual(offered['ticked'], ['Research the approved story', 'your documents'])
        for button in ('your sites (2)', 'the public web'):
            self.assertIn(button, offered['buttons'])
        self.assertNotIn('Add a site for this piece of work', offered['fields'])
        self.assertIn('Research from your documents.', offered['text'])
        self.assertIn(self.ONLY_DOCUMENTS, offered['text'])
        self.assertNotIn(self.SEARCHED, offered['text'])
        self.assertEqual(sites['ticked'], ['Research the approved story', 'your documents', 'your sites (2)',
                                           'blog.example.com/platform', 'docs.example.com'])
        self.assertIn('Add a site for this piece of work', sites['fields'])
        self.assertIn('It is for this deck only; your shared list is changed in Shared settings.',
                      sites['text'])
        self.assertIn(self.SEARCHED, sites['text'])
        self.assertNotIn(self.ONLY_DOCUMENTS, sites['text'])
        self.assertIn('Research from your documents and 2 of your sites '
                      '(blog.example.com/platform, docs.example.com).', sites['text'])
        self.assertEqual(chosen['ticked'], ['Research the approved story', 'your documents', 'your sites (2)',
                                            'the public web', 'blog.example.com/platform',
                                            'learn.example.org/guide'])
        self.assertEqual(chosen['fields']['Add a site for this piece of work'], '')
        said = ('Research from your documents, 2 of your sites (blog.example.com/platform, '
                'learn.example.org/guide) and the public web.')
        self.assertIn(said, chosen['text'])
        # It is still said, sites named, where the deck is started. The desk's start has no
        # stops to name.
        self.assertIn(said, last['text'])
        self.assertNotIn('Where it stops', last['text'])
        # The added site is checked by the runner; only the deck is started, and nothing
        # changes the shared list.
        self.assertEqual([address for address, _ in self.posts(result)],
                         ['/api/research-site', '/api/decks'])
        self.assertEqual(self.posts(result)[0][1], {'site': 'learn.example.org/guide/'})
        form = self.posts(result)[1][1]['form']
        self.assertEqual(form['research_from'], {
            'documents': True, 'sites': ['blog.example.com/platform', 'learn.example.org/guide'],
            'web': True})
        self.assertNotIn('research_sources', form)
        self.assertEqual(form['research_questions'], ['Why?', 'What next?'])
        # What the page sends is what the runner takes.
        checked = decks.check_form({**form, 'source': {'kind': 'paste', 'text': 'Notes.'}}, None)
        self.assertEqual(checked['research_from'], {
            'documents': True, 'sites': ['https://blog.example.com/platform',
                                         'https://learn.example.org/guide'], 'web': True})

    def test_a_deck_from_an_idea_keeps_the_public_web_with_your_sites_off(self):
        answers = self.answers(**{'GET /api/setup': [self.setup_with(research_sites=self.SITES)]})
        shot = self.run_page(answers, [
            {'click': 'New deck'}, {'click': 'An idea'}, {'fill': 'A short title', 'value': 'Synthetic deck'},
            {'tick': 'Research the approved story'}, {'snapshot': 'web'}])['snapshots']['web']
        self.assertEqual(shot['ticked'], ['Research the approved story', 'the public web'])
        self.assertIn('your sites (2)', shot['buttons'])
        self.assertIn('Research from the public web.', shot['text'])
        self.assertNotIn(self.ONLY_DOCUMENTS, shot['text'])

    def test_research_must_look_somewhere_before_the_form_goes_on(self):
        from studio_core import research_sites
        refused = self.site_answer('http://docs.example.com')
        self.assertEqual(refused['status'], 400)
        answers = self.answers(**{'GET /api/setup': [self.setup_with(research_sites=[])],
                                  'POST /api/research-site': [
                                      refused, self.site_answer('docs.example.com/guide')]})
        result = self.run_page(answers, [
            {'click': 'New deck'}, {'click': 'An idea'},
            {'fill': 'A short title', 'value': 'Synthetic deck'},
            {'tick': 'Research the approved story'}, {'snapshot': 'web'},
            {'tick': 'the public web'}, {'click': 'Start'}, {'snapshot': 'nowhere'},
            {'tick': 'your sites'}, {'snapshot': 'none'}, {'click': 'Start'},
            {'snapshot': 'no-site'}, {'click': 'Add the site'}, {'snapshot': 'empty'},
            {'fill': 'Add a site for this piece of work', 'value': 'http://docs.example.com'},
            {'click': 'Add the site'}, {'snapshot': 'http'},
            {'fill': 'Add a site for this piece of work', 'value': 'docs.example.com/guide'},
            {'click': 'Add the site'}, {'snapshot': 'went-on'}])
        self.assertEqual(result['errors'], [])
        shots = result['snapshots']
        # A deck from an idea has no documents to offer; it reads the public web.
        self.assertNotIn('your documents', shots['web']['buttons'])
        self.assertEqual(shots['web']['ticked'], ['Research the approved story', 'the public web'])
        self.assertIn('Research from the public web.', shots['web']['text'])
        self.assertIn(research_sites.EMPTY, shots['nowhere']['sheet'])
        self.assertEqual(shots['nowhere']['focus'], 'research-sites')
        self.assertEqual(shots['nowhere']['posts'], 0)
        self.assertIn('Your shared list has no sites yet.', shots['none']['text'])
        self.assertIn(research_sites.NO_SITES, shots['no-site']['sheet'])
        self.assertIn('Complete this step before continuing.', shots['no-site']['sheet'])
        self.assertIn('Type the site first, such as docs.example.com/guide.', shots['empty']['text'])
        # The runner's own sentence, from the same check every site has.
        self.assertIn('research sites use https only', refused['body']['error'])
        self.assertIn(refused['body']['error'], shots['http']['text'])
        self.assertIn('Add a site for this piece of work', shots['http']['invalid'])
        self.assertNotIn(research_sites.NO_SITES, shots['went-on']['sheet'])
        self.assertIn('Research from 1 of your sites (docs.example.com/guide).',
                      shots['went-on']['text'])
        self.assertEqual([body for address, body in self.posts(result)
                          if address == '/api/research-site'],
                         [{'site': 'http://docs.example.com'}, {'site': 'docs.example.com/guide'}])

    def test_the_start_form_is_sent_your_shared_sites(self):
        import os
        config = Path(os.environ['STUDIOS_CONFIG'])
        before = config.read_bytes() if config.exists() else None
        self.addCleanup(lambda: config.write_bytes(before) if before is not None
                        else config.unlink(missing_ok=True))
        config.parent.mkdir(parents=True, exist_ok=True)
        config.write_text(json.dumps({'research': {'sites': ['blog.example.com/platform/',
                                                             'http://not-https.example.com']}}))
        self.assertEqual(self.get('setup')['research_sites'], ['blog.example.com/platform'])

    def test_the_start_has_no_stops_or_first_draft_and_folds_the_options(self):
        from studio_core import review_policy
        self.assertIn(self.get('setup')['review_level'], review_policy.LEVELS)
        answers = self.answers(**{'GET /api/setup': [self.setup_with(review_level='balanced')],
                                  'POST /api/decks': [ok({'path': '/nowhere', 'id': 'x'})],
                                  'GET /api/run': [{'status': 404,
                                                    'body': {'error': 'There is no deck there.'}}]})
        result = self.run_page(answers, [
            {'click': 'New deck'}, {'click': 'An idea'},
            {'fill': 'A short title', 'value': 'Rolling restarts'},
            {'fill': 'Who is it for?', 'value': 'Operators'},
            {'fill': 'What should they take away?', 'value': 'Skip AI review on the first build.'},
            {'intakePage': 2}, {'snapshot': 'about'},
            {'snapshot': 'last'}, {'click': 'Brand, output and assistant'},
            {'snapshot': 'opened'}, {'click': 'Start'}])
        last, opened = result['snapshots']['last'], result['snapshots']['opened']
        # A desk deck's start names no review level and no first-draft choice.
        self.assertNotIn('Balanced: it stops for', last['text'])
        self.assertNotIn('Review level', last['text'])
        self.assertNotIn('Change', [link['name'] for link in last['links']])
        self.assertNotIn('First native build', last['text'])
        self.assertIn('Brand, output and assistant', last['buttons'])
        for shot in (last, opened):
            self.assertNotIn('See the first draft before the deck is checked', shot['buttons'])
        self.assertIn('Its model', opened['fields'])
        for old in ('AI review', 'AI critique', 'Research it first'):
            self.assertNotIn(old, opened['text'])
        self.assertIn('Research the approved story', result['snapshots']['about']['buttons'])
        # The goal's words never flip the first draft: a desk deck sends no choice of it.
        self.assertEqual(result['errors'], [])
        posted = [body for address, body in self.posts(result) if address == '/api/decks']
        self.assertNotIn('initial_review', posted[0]['form'])

    def test_the_start_lists_what_an_existing_deck_waits_for_by_its_level(self):
        import route_stops
        titles = {'brand-only': 'Brand only', 'polish': 'Polish',
                  'redesign': 'Redesign, keep content', 'rework': 'Full rework',
                  'selected': 'Selected changes'}
        for case, form in route_stops.FORM.items():
            # What happens after Start follows the route's own steps: the slide text is
            # approved wherever an outline is drafted, and the look picked where looks are
            # drawn. No start chooses a review level.
            if form['route'] != 'existing':
                continue
            answers = self.answers(**{
                'GET /api/setup': [self.setup_with(review_level='balanced')],
                'GET /api/run': [{'status': 404, 'body': {'error': 'There is no deck there.'}}]})
            result = self.run_page(answers, [
                {'click': 'New deck'}, {'click': 'An existing deck'}, {'snapshot': 'unset'},
                {'click': titles[form['level']]}, {'fill': 'A short title', 'value': 'Synthetic deck'}, {'intakePage': 2},
                # The start uses the brand's default look unless the person chooses to pick.
                *([{'click': 'Pick it when the samples are drawn'}, {'intakePage': 2}]
                  if 'gate:look' in route_stops.STOPS[form['stops']]['step_by_step'] else []),
                {'snapshot': 'level'}])
            with self.subTest(case=case):
                self.assertEqual(result['errors'], [])
                shot = result['snapshots']['level']
                stops = route_stops.STOPS[form['stops']]['step_by_step']
                text, looks = 'gate:outline' in stops, 'gate:look' in stops
                said = {(True, True): 'Before the desk, it waits for you twice: to approve the '
                                      'slide text, then to pick the look.',
                        (False, True): 'Before the desk, it waits for you to pick the look.',
                        (False, False): 'It runs on its own until the deck opens on the '
                                        'desk.'}[(text, looks)]
                self.assertIn(said, shot['sheet'])
                self.assertEqual('Approve the slide text.' in shot['sheet'], text)
                self.assertEqual('The changes are made.' in shot['sheet'], not text)
                self.assertEqual('Pick the look.' in shot['sheet'], looks)
                self.assertEqual('Pick it when the samples are drawn' in shot['buttons'], looks)
                for always in ('Review the deck.', 'Deliver.'):
                    self.assertIn(always, shot['sheet'])
                for gone in ('Review level', 'Where it stops', 'It stops once',
                             'Use this for new work in every studio'):
                    self.assertNotIn(gone, shot['text'])
                self.assertIn('How much changes', result['snapshots']['unset']['sheet'])
                self.assertIn('Next', result['snapshots']['unset']['buttons'])
                self.assertEqual(result['snapshots']['unset']['posts'], 0)

    def test_the_route_card_says_how_a_document_is_read(self):
        result = self.run_page(self.answers(), [
            {'click': 'New deck'}, {'snapshot': 'routes'}, {'click': 'A document'},
            {'snapshot': 'document'}])
        said = 'It is read first, to tell a finished script from material to build from.'
        for shot in ('routes', 'document'):
            self.assertIn(said, result['snapshots'][shot]['text'])
            self.assertNotIn('you confirm whether it is a finished script',
                             result['snapshots'][shot]['text'])

    def test_the_research_chip_and_the_start_line_say_the_desk_runs_on_its_own(self):
        gated = (('You approve the research plan, then the findings, before the outline is '
                  'drafted.'), 'You see what it found with the outline.')
        words = ('One Quick scan proposes a story. Edit and approve it before targeted '
                 'research, which is independently checked and kept with the deck.')
        for level in ('step_by_step', 'balanced', 'automatic'):
            answers = self.answers(**{'GET /api/setup': [self.setup_with(review_level=level)]})
            result = self.run_page(answers, [
                {'click': 'New deck'}, {'click': 'An idea'},
                {'fill': 'A short title', 'value': 'Rolling restarts'},
                {'tick': 'Research the approved story'}, {'snapshot': 'about'},
                {'click': 'Pick it when the samples are drawn'},
                {'snapshot': 'last'}, {'click': 'Use the brand’s default look'},
                {'snapshot': 'default'}])
            with self.subTest(level=level):
                about, last = result['snapshots']['about'], result['snapshots']['last']
                self.assertIn(words, about['text'])
                for other in gated:
                    self.assertNotIn(other, about['text'])
                # What happens after Start is said from the choices: research, the slide
                # text to approve, then the look to pick, or the brand's default with no stop.
                plan = last['sheet'][last['sheet'].index('What happens after Start'):]
                self.assertIn('Before the desk, it waits for you three times: to approve the slide '
                              'story, then to approve the slide text, then to pick the look.', plan)
                self.assertLess(plan.index('Targeted research.'), plan.index('Approve the slide text.'))
                self.assertLess(plan.index('Approve the slide text.'),
                                plan.index('Pick the look.'))
                self.assertLess(plan.index('Pick the look.'), plan.index('Review the deck.'))
                self.assertLess(plan.index('Review the deck.'), plan.index('Deliver.'))
                self.assertIn('choose Approve text & design deck. Nothing is designed until you '
                              'approve.', plan)
                default = result['snapshots']['default']['sheet']
                self.assertIn('Before the desk, it waits for you twice: to approve the slide story, then to approve the slide text.',
                              default)
                self.assertIn('The brand’s default look. Once the text is approved, the slides '
                              'are designed in it, with no stop.', default)
                self.assertNotIn('Pick the look.', default)
                for gone in ('It stops once', 'with no stops'):
                    self.assertNotIn(gone, last['text'] + default)
                for old in ('At each stop you see what is made so far.',
                            'From the first decision on'):
                    self.assertNotIn(old, last['text'])

    def test_home_says_new_slide_text_is_approved_before_anything_is_designed(self):
        result = self.run_page(self.answers(), [{'snapshot': 'home'}])
        text = result['snapshots']['home']['text']
        self.assertIn('Where new slide text is drafted, you approve it before anything is '
                      'designed; then the deck is built and opens on the desk when it is '
                      'ready. The start lists what happens, from your choices, before you '
                      'begin.', text)
        for old in ('stops each time it needs your decision',
                    'It stops only if you chose to pick its look.',
                    'stops where its review level says',
                    'builds it on its own, and stops where its review level says',
                    'It takes two or three short steps'):
            self.assertNotIn(old, text)

    def test_the_set_up_says_what_each_stop_shows(self):
        described = self.get('setup')
        fresh = {**described, 'configured': False, 'workspace': None}
        result = self.run_page(self.answers(**{'GET /api/setup': [ok(fresh)]}),
                               [{'snapshot': 'first'}])
        text = result['snapshots']['first']['text']
        self.assertIn('The assistant that does the drafting', text)
        self.assertIn('The assistant drafts each stage for you to decide on.', text)
        for old in ('The agent that does the drafting', 'An agent is the AI',
                    'At every decision after the first'):
            self.assertNotIn(old, text)

    def test_settings_has_no_review_preference_control(self):
        answers = self.answers(**{'GET /api/setup': [self.setup_with(review_level='balanced')]})
        result = self.run_page(answers, [{'click': 'Settings'}, {'snapshot': 'settings'}])
        self.assertNotIn('Where new work stops', result['snapshots']['settings']['text'])
        self.assertFalse(any(address == '/api/review-level' for address, _ in self.posts(result)))

    def test_the_new_deck_form_asks_once_whether_it_is_a_talk_or_a_handout(self):
        answers = self.answers(**{'GET /api/run': [{'status': 404,
                                                    'body': {'error': 'There is no deck there.'}}]})
        result = self.run_page(answers, [
            {'click': 'New deck'}, {'click': 'An idea'},
            {'fill': 'A short title', 'value': 'Rolling restarts'},
            {'snapshot': 'about'}, {'click': 'A handout'},
            {'snapshot': 'last'}, {'click': 'Start'}])
        about = result['snapshots']['about']
        self.assertIn('Is this deck for a talk or a handout?', about['text'])
        self.assertIn('A talk', about['buttons'])
        self.assertEqual(result['snapshots']['last']['sheet'].count('talk or a handout'), 1,
                         'asked once, on the form')
        posted = [body for address, body in self.posts(result) if address == '/api/decks']
        self.assertEqual(posted[0]['form']['delivery'], 'reading')

    def test_a_working_deck_shows_what_the_assistant_is_doing_and_its_activity_log(self):
        # Its latest line as "Now:", Show activity with every line so far, and the deck's
        # Activity log, read only when it is opened (#294).
        path = self.started(flow='desk', look='default')   # re-based on a desk deck (GitHub issue #542)
        shown = self.run_of(path)
        lines = [{'at': '2030-01-02T03:04:00Z', 'text': 'Looking at what it was given'},
                 {'at': '2030-01-02T03:04:05Z', 'text': 'Reading brief'}]
        shown.update(state='working', gate=None, sentence='Drafting the outline.',
                     workers=[{'id': 'outline', 'label': 'Drafting the outline',
                               'started_at': '2030-01-02T03:04:00Z', 'now': lines[-1],
                               'count': 2}])
        logged = {'jobs': [{'id': 'j1', 'label': 'Classifying the request', 'step': 'classify',
                            'started_at': '2030-01-02T03:00:00Z',
                            'ended_at': '2030-01-02T03:02:00Z', 'outcome': 'failed',
                            'words': 'Failed', 'detail': 'It stopped without finishing.',
                            'lines': [lines[0]], 'dropped': 0}],
                  'running': [], 'empty': None, 'limit': 200, 'lines': 200}
        result = self.deck_screen(path, [
            {'snapshot': 'working'}, {'click': 'Show activity (2 steps)'},
            {'click': 'Activity logWhat the assistant did in each job, newest first'},
            {'snapshot': 'log'}], **{'GET /api/run': [ok(shown)],
                                     # Show activity reads the job's lines, then the log.
                                     'GET /api/activity': [ok({'lines': lines, 'count': 2,
                                                               'start': 0, 'running': True}),
                                                           ok(logged)]})
        working = result['snapshots']['working']
        for text in ('Assistant jobs now', 'Drafting the outline', 'Now: Reading brief'):
            self.assertIn(text, working['text'])
        self.assertIn('Show activity (2 steps)', working['buttons'])
        log = result['snapshots']['log']['text'].split('Activity log')[-1]
        for text in ('Classifying the request', 'Failed', 'It stopped without finishing.'):
            self.assertIn(text, log)
        asked = [request['address'] for request in result['requests']
                 if request['address'].startswith('/api/activity?')]
        self.assertEqual(len(asked), 2)
        self.assertIn('job=outline', asked[0])
        self.assertIn('since=0', asked[0])
        self.assertIn('Looking at what it was given', result['snapshots']['log']['text'])
        self.assertFalse([request for request in result['requests']
                          if request['method'] == 'POST'], 'reading activity starts nothing')

    def test_a_retry_says_what_it_re_runs_and_what_the_last_try_took(self):
        self.brand.run.offers_looks = True   # re-based on a desk deck (GitHub issue #542),
        path = self.started(flow='desk', look='pick')   # which waits for its look, unbuilt
        shown = self.run_of(path)
        row = next(row for row in shown['timeline'] if row['state'] != 'done')
        row.update(state='current', failed=True, seconds=120, dollars=0.3)
        shown.update(state='failed', gate=None, sentence='It has stopped.',
                     problem={'state': 'failed', 'why': 'The worker stopped.',
                              'kept': 'Everything made so far.', 'action': 'retry'})
        result = self.deck_screen(path, [{'snapshot': 'failed'}], **{'GET /api/run': [ok(shown)]})
        shot = result['snapshots']['failed']
        self.assertEqual(shot['filled'], ['Try again'])
        self.assertIn('Try again re-runs ' + row['label'] + ' from the start; the tries so far '
                      'took 2 minutes and $0.30.', shot['text'])

    def test_an_unusable_assistant_offers_open_status(self):
        path = self.started(flow='desk', look='default')   # re-based on a desk deck (GitHub issue #542)
        shown = self.run_of(path)
        row = next(row for row in shown['timeline'] if row['state'] != 'done')
        row.update(state='current', failed=True)
        said = ('Claude Code could not be used. It is not signed in. Check this computer, on '
                'the Status screen, says what it needs.')
        shown.update(state='failed', gate=None, sentence='It has stopped.',
                     problem={'state': 'failed', 'why': said,
                              'kept': 'Everything made so far.', 'action': 'status'})
        result = self.deck_screen(path, [{'snapshot': 'failed'}, {'click': 'Open Status'},
                                         {'snapshot': 'status'}],
                                  **{'GET /api/run': [ok(shown)]})
        shot = result['snapshots']['failed']
        self.assertEqual(shot['filled'], ['Open Status'])
        self.assertIn('Try again', shot['buttons'])
        self.assertEqual(result['snapshots']['status']['heading'], 'Status')

    def test_a_step_that_ran_out_of_time_offers_more_time(self):
        path = self.started(flow='desk', look='default')   # re-based on a desk deck (GitHub issue #542)
        shown = self.run_of(path)
        row = next(row for row in shown['timeline'] if row['state'] != 'done')
        row.update(state='current', failed=True, seconds=2700, dollars=0.9)
        said = ('Draft the outline ran out of the time a step may take: its last try was '
                'stopped after 15 minutes, and it did not work in 3 tries. That limit, 15 '
                'minutes a step, is in Settings, under Limits.')
        shown.update(state='failed', gate=None, sentence=said, problem={
            'state': 'failed', 'why': said, 'kept': 'Everything made so far.',
            'action': 'more-time', 'seconds': 900})
        result = self.deck_screen(path, [{'snapshot': 'failed'},
                                         {'click': 'Give it more time and try again'}],
                                  **{'GET /api/run': [ok(shown)], 'POST /api/run': [ok(shown)]})
        shot = result['snapshots']['failed']
        self.assertEqual(shot['filled'], ['Give it more time and try again'])
        self.assertIn('Give it more time and try again lets each step of this deck take up to '
                      '30 minutes, and runs this step again from the start. Raising the limit in '
                      'Settings, under Limits, is the other way on, for every deck.', shot['text'])
        self.assertEqual(self.posts(result), [('/api/run', {'path': path, 'action': 'more-time'})])

    def test_a_research_stop_opens_every_objection(self):
        path = self.started(flow='desk', look='default')   # re-based on a desk deck (GitHub issue #542)
        shown = self.run_of(path)
        row = next(row for row in shown['timeline'] if row['state'] != 'done')
        row.update(state='current', failed=True)
        shown.update(state='failed', gate=None, sentence='It has stopped.', problem={
            'state': 'failed', 'why': 'The check still objected.', 'action': 'retry',
            'kept': 'The draft report is kept.', 'objections': 'research/review.md',
            'research': {'rounds': 3, 'jobs': 6, 'seconds': 60, 'dollars': None, 'most': 3,
                         'drafted': True}})
        read = ok({'name': 'research/review.md', 'size': 40, 'truncated': False,
                   'text': '# Independent research check\n\n- f01: Too broad.\n'})
        result = self.deck_screen(path, [{'click': 'Read every objection'}, {'snapshot': 'read'}],
                                  **{'GET /api/run': [ok(shown)], 'GET /api/file': [read]})
        self.assertIn('f01: Too broad.', result['snapshots']['read']['text'])

    def test_a_research_retry_carries_on_from_the_draft_and_lists_what_was_kept(self):
        path = self.started(flow='desk', look='default')   # re-based on a desk deck (GitHub issue #542)
        shown = self.run_of(path)
        row = next(row for row in shown['timeline'] if row['state'] != 'done')
        row.update(state='current', failed=True, seconds=2880, dollars=9.8)
        shown.update(state='failed', gate=None, sentence='It has stopped.', problem={
            'state': 'failed', 'why': 'The check still objected.', 'action': 'retry',
            'kept': 'The draft report is kept.\n- 12 facts the check calls narrow (f01: Too '
                    'broad.)\n- coverage needs revision (Alternatives are missing.)',
            'research': {'rounds': 3, 'jobs': 6, 'seconds': 2880, 'dollars': 9.8, 'most': 3,
                         'drafted': True}})
        result = self.deck_screen(path, [{'snapshot': 'failed'}], **{'GET /api/run': [ok(shown)]})
        text = result['snapshots']['failed']['text']
        self.assertIn('Try again continues from the saved draft and runs up to 3 more rounds of '
                      'writing and checking; the last 3 rounds took 48 minutes and $9.80.', text)
        self.assertIn('What was kept: The draft report is kept.', text)
        self.assertIn('12 facts the check calls narrow (f01: Too broad.)', text)
        self.assertNotIn('- 12 facts', text, 'each group is an item of a list')
        self.assertNotIn('from the start', text)
        # With no draft saved, there is nothing to carry on from.
        shown['problem']['research'].update(drafted=False, rounds=1, seconds=50, dollars=None)
        result = self.deck_screen(path, [{'snapshot': 'failed'}], **{'GET /api/run': [ok(shown)]})
        self.assertIn('Try again runs the research again, up to 3 rounds of writing and checking; '
                      'the last round took 50 seconds.', result['snapshots']['failed']['text'])

    def test_a_build_retry_says_how_many_sections_are_kept(self):
        self.brand.run.offers_looks = True   # re-based on a desk deck (GitHub issue #542),
        path = self.started(flow='desk', look='pick')   # which waits for its look, unbuilt
        shown = self.run_of(path)
        self.assertIsNone(shown['build_sections'], 'nothing built yet')
        row = next(row for row in shown['timeline'] if row['stage'] == 'build')
        row.update(state='current', failed=True, seconds=300, dollars=1.1)
        for other in shown['timeline']:
            if other is not row and other['state'] == 'current':
                other['state'] = 'done'
        shown.update(state='failed', gate=None, sentence='It has stopped.',
                     build_sections={'total': 4, 'kept': 2},
                     problem={'state': 'failed', 'why': 'The renderer stopped.',
                              'kept': 'Two sections.', 'action': 'retry'})
        result = self.deck_screen(path, [{'snapshot': 'failed'}], **{'GET /api/run': [ok(shown)]})
        self.assertIn('Try again keeps 2 of 4 sections; the rest are drawn again; the tries so '
                      'far took 5 minutes and $1.10.', result['snapshots']['failed']['text'])

    def test_home_says_where_an_older_powerpoint_file_is(self):
        path = self.started(output='pptx')
        self.deliver_desk(Path(path))
        listed = self.get('decks')
        for where, said in (('maker', 'A .pptx on the computer that made it.'),
                            ('shared', 'A .pptx, to download from its own screen.')):
            changed = json.loads(json.dumps(listed))
            for group in changed.values():
                for brief in group if isinstance(group, list) else ():
                    if isinstance(brief, dict) and brief.get('path') == path:
                        brief['pptx_where'] = where
            result = self.run_page(self.answers(**{'GET /api/decks': [ok(changed)]}),
                                   [{'click': 'Decks'}, {'snapshot': 'decks'}])
            with self.subTest(where=where):
                self.assertIn(said, result['snapshots']['decks']['text'])

    def test_a_preview_pool_is_said_as_it_is(self):
        described = self.get('setup')
        pool = ('Google Drive: previews are drawn in a few shared presentations named '
                '“Preview: …” in your Drive, reused by every deck. Presentation Studio never '
                'deletes them.')
        for pooled, said in ((True, pool), (False, 'Google Drive: each deck keeps one '
                                                   'presentation named “Preview: …”')):
            fresh = {**described, 'configured': False, 'workspace': None,
                     'previews': {**described['previews'], 'pool': pooled,
                                  'drive': True, 'local': True}}
            result = self.run_page(self.answers(**{'GET /api/setup': [ok(fresh)]}),
                                   [{'snapshot': 'first'}])
            self.assertIn(said, result['snapshots']['first']['text'])

    def test_decks_status_settings_and_published_are_drawn_from_the_runners_answers(self):
        self.started(title='Rolling restarts')
        self.started(title='Capacity planning')
        answers = self.answers(**{'GET /api/status': [ok(self.get('status'))],
                                  'GET /api/published': [ok(self.get('published'))]})
        result = self.run_page(answers, [
            {'click': 'Decks'}, {'snapshot': 'decks'},
            {'fill': 'Search', 'value': 'capacity', 'stay': True}, {'click': 'Search'},
            {'snapshot': 'found'},
            {'click': 'Published'}, {'snapshot': 'published'},
            {'click': 'Status'}, {'snapshot': 'status'},
            {'click': 'Settings'}, {'snapshot': 'settings'}])
        shots = result['snapshots']
        self.assertIn('2 decks.', shots['decks']['text'])
        self.assertIn('1 of 2 decks match.', shots['found']['text'])
        self.assertNotIn('Open Rolling restarts', shots['found']['buttons'])
        self.assertIn('Open Capacity planning', shots['found']['buttons'])
        self.assertIn('Nothing is published yet', shots['published']['text'])
        for shown in ('Running on this computer', 'Rolling restarts', 'Cost so far',
                      'This computer'):
            self.assertIn(shown, shots['status']['text'])
        for shown in ('Workspace', 'Delivered as', 'When this page is closed',
                      'Updates'):
            self.assertIn(shown, shots['settings']['text'])
        self.assertEqual(self.posts(result), [])

    def test_search_and_jump_finds_a_deck_by_name_and_opens_it(self):
        path = self.started(title='Capacity planning')
        self.started(title='Rolling restarts')
        answers = self.answers(**{'GET /api/run': [ok(self.run_of(path))]})
        result = self.run_page(answers, [{'snapshot': 'home'}, {'command': 'Capacity planning'},
                                         {'snapshot': 'deck'}], shell=True)
        listed = result['commands']
        self.assertEqual(sorted(row[1] for row in listed if row[0] == 'Decks'),
                         ['Capacity planning', 'Rolling restarts'])
        self.assertIn(['Start', 'New deck', ''], listed)
        self.assertEqual(result['snapshots']['deck']['heading'], 'Capacity planning')
        self.assertNotEqual(result['snapshots']['home']['heading'], 'Capacity planning')

    def test_a_deck_is_deleted_from_the_decks_list_through_its_own_sheet(self):
        path = self.started(title='Rolling restarts')
        self.started(title='Capacity planning')
        before = self.get('decks')
        leaving = self.get('delete', path=path)
        deleted = self.post('delete', {'path': path, 'title': 'Rolling restarts'})
        after = self.get('decks')
        answers = self.answers(**{'GET /api/decks': [ok(before), ok(after)],
                                  'GET /api/delete': [ok(leaving)],
                                  'POST /api/delete': [ok(deleted)]})
        result = self.run_page(answers, [
            {'click': 'Decks'}, {'snapshot': 'decks'},
            {'click': 'Delete Rolling restarts'}, {'snapshot': 'asked'},
            {'click': 'Delete Rolling restarts'}, {'snapshot': 'deleted'}])
        shots = result['snapshots']
        for title in ('Rolling restarts', 'Capacity planning'):
            self.assertIn('Open ' + title, shots['decks']['buttons'])
            self.assertIn('Delete ' + title, shots['decks']['buttons'])
        # It is the deck screen's own sheet: what goes, what stays, and the button that
        # names the deck, which is never the filled one.
        asked = shots['asked']['sheet']
        for shown in ('Delete Rolling restarts?', 'What goes', 'What stays',
                      'Its folder in your workspace, with every file in it.',
                      'This cannot be undone from this page.'):
            self.assertIn(shown, asked)
        self.assertEqual(shots['asked']['filled'], [])
        # The list is drawn again without the card, and says so.
        gone = shots['deleted']
        self.assertEqual(gone['heading'], 'Decks')
        self.assertEqual(gone['sheet'], '')
        self.assertIn('Deleted Rolling restarts.', gone['text'])
        self.assertIn('1 deck.', gone['text'])
        self.assertNotIn('Open Rolling restarts', gone['buttons'])
        self.assertIn('Open Capacity planning', gone['buttons'])
        self.assertEqual(self.posts(result),
                         [('/api/delete', {'path': path, 'title': 'Rolling restarts'})])
        self.assertIn('GET /api/delete?' + urlencode({'path': path}),
                      [request['method'] + ' ' + request['address']
                       for request in result['requests']])

    def test_a_list_offers_delete_only_where_the_runner_would_allow_it_and_says_its_refusal(
            self):
        path = self.started(title='Rolling restarts')
        other = self.started(title='Capacity planning')
        listed = self.get('decks')
        theirs = next(brief for brief in listed['needs'] + listed['working']
                      if brief['path'] == other)
        for kind in ('needs', 'working'):
            listed[kind] = [brief for brief in listed[kind] if brief['path'] != other]
        listed['elsewhere'] = [{**theirs, 'mine': False, 'needs': False,
                                'driver': {'name': 'Sam Lee', 'here': False}}]
        refused = {'path': path, 'title': 'Rolling restarts', 'may': False,
                   'why': 'Nobody is running this deck, so it cannot be deleted from here '
                          'until someone takes it.'}
        answers = self.answers(**{'GET /api/decks': [ok(listed)],
                                  'GET /api/delete': [ok(refused)]})
        result = self.run_page(answers, [
            {'snapshot': 'home'}, {'click': 'Decks'}, {'snapshot': 'decks'},
            {'click': 'Delete Rolling restarts'}, {'snapshot': 'refused'},
            {'click': 'Cancel'}, {'snapshot': 'back'}])
        shots = result['snapshots']
        # Home's rows offer it too, beside the way in; a teammate's deck offers neither list it.
        for name in ('home', 'decks'):
            with self.subTest(name):
                self.assertIn('Delete Rolling restarts', shots[name]['buttons'])
                self.assertNotIn('Delete Capacity planning', shots[name]['buttons'])
        self.assertIn(refused['why'] + ' Nothing was deleted.', shots['refused']['sheet'])
        self.assertNotIn('What goes', shots['refused']['sheet'])
        self.assertEqual(shots['back']['sheet'], '')
        self.assertIn('Delete Rolling restarts', shots['back']['buttons'])
        self.assertEqual(self.posts(result), [])

    def test_status_says_what_the_shared_file_says_and_offers_to_join_its_team(self):
        described = self.get('setup')
        other = 'git@example.com:team/other-decks.git'
        moved = {**described, 'shared_problem': None,
                 'team_moved': {'repository': other, 'branch': 'main',
                                'says': 'The team repository your studios share is now '
                                        f'{other}.'},
                 'shared_notice': 'Presentation Studio now keeps the values every studio '
                                  'shares only in one file.'}
        seen = {**moved, 'shared_notice': None}
        answers = self.answers(**{'GET /api/setup': [ok(moved)],
                                  'GET /api/status': [ok(self.get('status'))],
                                  'POST /api/shared': [ok(seen)]})
        result = self.run_page(answers, [
            {'click': 'Status'}, {'snapshot': 'status'}, {'click': 'Got it'},
            {'snapshot': 'seen'}, {'click': 'Join it'}, {'snapshot': 'joining'}])
        shots = result['snapshots']
        for shown in ('Your other studios', moved['team_moved']['says'],
                      moved['shared_notice']):
            self.assertIn(shown, shots['status']['text'])
        self.assertNotIn(moved['shared_notice'], shots['seen']['text'])
        self.assertEqual(shots['joining']['fields']['The repository’s address'], other)
        self.assertEqual(self.posts(result)[0], ('/api/shared', {'seen': True}))
        # Joining is checked first, as any set-up is: nothing moves until it is saved.
        self.assertEqual([address for address, _ in self.posts(result)[1:]],
                         ['/api/setup/check'])


    def brand_upkeep(self) -> dict:
        """What the runner's own upkeep reports with a brand skill's repository named and no
        brand skill installed: the brand skill offered from its repository."""
        from dataclasses import replace
        from runner import settings, upkeep
        settings.save(replace(settings.load(), brand_repository=ADDRESS))
        keep = upkeep.Upkeep(home_dir=self.base / 'home', root=self.base / 'root',
                             installer=self.base / 'no-installer' / 'install.py')
        keep.remember_brand(ADDRESS, 'c3405eee0aad' + 'a' * 28)   # where its main branch is
        installed, self.brand = self.brand, None
        try:
            keep.check(repair=False)
        finally:
            self.brand = installed
        return keep.report()

    def test_a_suite_install_says_marketing_studio_updates_it(self):
        said = ('Marketing Studio installs and updates this studio. To update it, unpack a newer '
         'Marketing Studio release and run marketing-studio update --from <the '
         'unpacked folder> --yes.')
        self.started()
        found = self.brand_upkeep()
        found = {**found, 'update': {**found['update'], 'offered': False},
                 'versions': {**found['versions'], 'suite': 'marketing-studio'}}
        answers = self.answers(**{'GET /api/setup': [ok({**self.get('setup'), 'upkeep': found})]})
        result = self.run_page(answers, [{'snapshot': 'home'}, {'click': 'Status'},
                                         {'snapshot': 'status'}])
        for screen in ('home', 'status'):
            shot = result['snapshots'][screen]
            with self.subTest(screen=screen):
                self.assertIn(said, shot['text'])
                self.assertNotIn('Newer versions are ready for this computer:', shot['text'])
                for button in ('Update', 'Update the skills', 'Upgrade', 'Upgrade everything'):
                    self.assertNotIn(button, shot['buttons'])

    def test_home_offers_the_brand_skill_and_asks_before_it_is_installed(self):
        self.started()
        found = self.brand_upkeep()
        offer = found['versions']['brand']
        self.assertEqual((offer['offered'], offer['action'], offer['commit']),
                         (True, 'Install', 'c3405eee0aad'))
        self.assertNotIn('release', offer)
        running = f'Fetching main from {ADDRESS} and running its own installer. This can ' \
                  'take a few minutes.'
        busy = {**found, 'versions': {**found['versions'], 'brand': {
            **offer, 'offered': False, 'state': 'running', 'since': '2026-10-14T09:05:00Z',
            'says': running}}}
        down = ('A deck on this computer is working now, and a step in hand keeps using the '
                'brand skill it started with. Pause it, or wait until it stops for you, then '
                'install.')
        answers = self.answers(**{
            'GET /api/setup': [ok({**self.get('setup'), 'upkeep': found})],
            'POST /api/brand/install': [{'status': 409, 'body': {'error': down}},
                                        ok({'upkeep': busy})]})
        result = self.run_page(answers, [
            {'snapshot': 'home'},
            {'click': 'Install the brand skill'}, {'snapshot': 'asked'},
            {'click': 'Cancel'}, {'snapshot': 'cancelled'},
            {'click': 'Install the brand skill'}, {'click': 'Install it now'},
            {'snapshot': 'refused'},
            {'click': 'Install it now'}, {'snapshot': 'installing'}])
        shots = result['snapshots']
        for said in ('Newer versions are ready for this computer:',
                     'brand skill main, which is missing',
                     'No brand skill is installed, so a deck stops where it first needs '
                     'your brand.'):
            self.assertIn(said, shots['home']['text'])
        asked = shots['asked']['sheet']
        for said in ('Install the brand skill from its main branch?', 'What is installed',
                     'Its main branch, at revision c3405eee0aad.', f'From {ADDRESS}.',
                     'Its own installer is run, and told to leave harness-research alone.',
                     'Where it would put in its own harness-slides in place of the one '
                     'Presentation Studio uses, nothing is run, and you are told.',
                     'Install only from a repository you trust.'):
            self.assertIn(said, asked)
        self.assertIn(down + ' Nothing was changed.', shots['refused']['sheet'])
        done = shots['installing']
        self.assertEqual(done['sheet'], '')
        self.assertIn('Installing the brand skill. Home and the Status screen say how it goes.',
                      done['toasts'])
        self.assertIn(running, done['text'])
        self.assertNotIn('Install the brand skill', done['buttons'], 'one install at a time')
        self.assertEqual(self.posts(result), [('/api/brand/install', {'commit': 'c3405eee0aad'})]
                         * 2, 'nothing before the yes')

    def test_the_brand_skills_repository_is_checked_and_saved_in_settings(self):
        described = self.get('setup')
        saved = {**described, 'brand': {**described['brand'], 'repository': ADDRESS}}
        cannot = ("The brand skill's repository could not be read. git could not sign in to "
                  "it without asking (could not read Username for 'https://github.com': "
                  'terminal prompts disabled). Sign git in with an account that may read it, '
                  'through its credential helper for an https address or an ssh key for an '
                  'ssh one, then try again.')
        answers = self.answers(**{
            'GET /api/setup': [ok(described)] * 3 + [ok(saved)],
            'POST /api/brand': [{'status': 400, 'body': {'error': cannot}}, ok(saved)]})
        result = self.run_page(answers, [
            {'click': 'Settings'}, {'snapshot': 'empty'},
            {'fill': 'Its repository', 'value': ADDRESS},
            {'click': 'Check and save'}, {'snapshot': 'refused'},
            {'click': 'Check and save'}, {'snapshot': 'saved'}])
        shots = result['snapshots']
        for said in ('Brand skill', 'Your brand skill comes from a repository of its own.',
                     'installs and updates the brand skill from its main branch',
                     'A brand skill you installed yourself is still found and used.'):
            self.assertIn(said, shots['empty']['text'])
        # There is no release to choose: the brand skill is installed and updated from main.
        for gone in ('Which release', 'Empty for the newest'):
            self.assertNotIn(gone, shots['empty']['text'])
        self.assertIn(cannot + ' Nothing was changed.', shots['refused']['text'])
        self.assertIn(f'Installed and updated from the main branch of {ADDRESS}.',
                      shots['saved']['text'])
        self.assertIn('Saved. The Status screen shows its main branch, to install.',
                      shots['saved']['toasts'])
        self.assertEqual(self.posts(result), [('/api/brand', {
            'repository': ADDRESS, 'shared_seen': described['shared']})] * 2)

    def test_the_brand_skills_repository_is_one_every_studio_shares(self):
        described = self.get('setup')
        shared = {'brand': {'repository': ADDRESS}}
        stale = ("The brand skill's repository was changed in another studio while this was "
                 'open, so nothing was saved. Look again, then save.')
        now = {**described, 'shared': shared, 'shared_problem': None,
               'brand': {**described['brand'], 'repository': ADDRESS}}
        other = 'https://github.com/acme/other-brand.git'
        later = {**now, 'shared': {'brand': {'repository': ADDRESS, 'brand': 'acme'}}}
        answers = self.answers(**{'GET /api/setup': [ok(now), ok(later)],
                                  'POST /api/brand': [{'status': 400, 'body': {'error': stale}},
                                                      ok(later)]})
        result = self.run_page(answers, [
            {'click': 'Settings'}, {'snapshot': 'settings'},
            {'fill': 'Its repository', 'value': other},
            {'click': 'Check and save'}, {'snapshot': 'refused'},
            {'poll': True}, {'click': 'Check and save'}])
        shots = result['snapshots']
        self.assertIn('Every studio on this computer shares the repository named here, so '
                      'saving changes it for all of them.', shots['settings']['text'])
        self.assertIn(stale + ' Nothing was changed.', shots['refused']['text'])
        # What it was shown goes with it, and after a refusal, what it has been shown since.
        self.assertEqual(self.posts(result), [
            ('/api/brand', {'repository': other, 'shared_seen': shared}),
            ('/api/brand', {'repository': other, 'shared_seen': later['shared']})])

    def test_without_a_brand_skill_a_new_deck_can_still_be_started(self):
        self.brand = None
        self.engine.deck_needs(fresh=True)
        described = self.get('setup')
        self.assertEqual(described['brand']['default'], {'brand': None, 'variant': None})
        answers = self.answers(**{'POST /api/decks': [ok({'path': '/nowhere', 'id': 'x'})],
                                  'GET /api/run': [{'status': 404,
                                                    'body': {'error': 'There is no deck there.'}}]})
        result = self.run_page(answers, [
            {'click': 'New deck'}, {'click': 'An idea'},
            {'fill': 'A short title', 'value': 'Rolling restarts'},
            {'intakePage': 2}, {'snapshot': 'last'}, {'click': 'Start'}])
        self.assertIn('A deck can still be started: it is made up to the point it needs your '
                      'brand, and waits there.', result['snapshots']['last']['text'])
        (address, body), = self.posts(result)
        self.assertEqual((address, body['form']['brand'], body['form']['variant']),
                         ('/api/decks', '', None))
        # What the page sends is what the server takes, and the deck stops at its brand.
        made = self.post('decks', body)
        self.assertEqual(self.run_of(made['path'])['state'], 'stopped')

    # --- what a slide says, after the deck is built -----------------------------------------


class OneNameEachTests(unittest.TestCase):
    """Presentation Studio says each thing one way, true at every review level."""

    def test_old_names_are_gone(self):
        page = (helpers.REPO / 'skills' / 'presentation-studio' / 'scripts' / 'desk' /
                'app.js').read_text(encoding='utf-8')
        runner = ''.join((helpers.REPO / 'runner' / name).read_text(encoding='utf-8')
                         for name in ('stages.py', 'engine.py', 'jobs.py'))
        for old in ('Deliver to Google Slides', 'deliver it again', 'The agent that does',
                    'An agent is the AI', "'A worker'", 'What you gave us', 'Tell us which',
                    'We may tighten', 'this displayed revision', 'Published as revision',
                    'Send slide feedback', 'Request changes to the research',
                    'Ask about this finding', 'Keep this finding', 'Don’t research it again',
                    'The review has nothing left to raise', "card('Working now')",
                    'work folder', "notify('Deck copied", "notify('Slide feedback saved"):
            with self.subTest(old=old):
                self.assertNotIn(old, page + runner)
        # The new names that lived only on the earlier step-by-step flow's stop screens went
        # with them (GitHub issue #542); the old names stay gone everywhere.
        for new in ("card('Assistant jobs now')", 'Say which slides and what to fix.',
                    'It may tighten, split, merge or reorder content, then redesign.',
                    'Your assistant, workspace, brand and delivery choices apply across all studios.',
                    "toast('Deck copied into this workspace.')",
                    'Slide previews show what is made so far: each slide is turned'):
            with self.subTest(new=new):
                self.assertIn(new, page + runner)
        from runner import engine
        self.assertIn('send it to Google Slides again', engine.STILL_NOT_CONNECTED)


if __name__ == '__main__':
    unittest.main()
