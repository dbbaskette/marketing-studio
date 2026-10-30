"""The runner's server: every address the appendices of the milestone 2 and milestone 3
specifications name, each thing it refuses, and what the desk's own answers gain.

Most classes ask the page without a socket, so they run where a port cannot be opened.
WireTests talks to a real server on a local port and is skipped where that is not allowed.
Nothing starts an agent, looks at the real computer or touches the network.
"""
import base64
import contextlib
import io
import json
import os
import shutil
import stat
import subprocess
import threading
import time
import unittest
import urllib.error
import urllib.request
from dataclasses import replace
from email.message import Message
from pathlib import Path
from unittest import mock
from urllib.parse import urlencode

import helpers
from runner_support import (CHOSEN, FORM, NO_BRAND_SKILL, QUOTE, SCENARIO, Brand, Slides, StudioCase,
                            TeamCase, asks, fails, left)

import computer
import desk
import home
import workspace
from runner import agents, drafts, gitstate, page, pipeline, settings, setup, studios_config
from runner import engine as engines
from studio_core import step_times
from workspace import WorkspaceError

VERSION = (helpers.SKILL / 'VERSION').read_text().strip()
LISTED = [{'name': 'gpt-6-sol', 'label': 'GPT-6-Sol (gpt-6-sol)', 'family': None,
           'about': 'Previous generation workhorse model.', 'default_level': 'medium',
           'levels': ['low', 'medium', 'high', 'xhigh']},
          {'name': 'gpt-6-luna', 'label': 'GPT-6-Luna (gpt-6-luna)', 'family': None,
           'about': None, 'default_level': None, 'levels': ['low', 'medium', 'high']}]
GETS = ('/api/capabilities', '/api/setup', '/api/agents', '/api/models', '/api/run')
POSTS = ('/api/training-plan', '/api/research-sources', '/api/setup/check', '/api/setup', '/api/trainings', '/api/run', '/api/answer',
         '/api/documents', '/api/copies', '/api/share', '/api/companions', '/api/asset',
         '/api/upgrade', '/api/restart', '/api/versions', '/api/brand', '/api/brand/install', '/api/review',
         '/api/note', '/api/research-site')
BOTH =('/api/setup', '/api/run', '/api/trainings')
RUN_KEYS = ['agent', 'ahead', 'can_migrate_desk', 'can_open_desk', 'clash', 'controls', 'copies', 'decided', 'deck', 'deck_left', 'documents', 'driver', 'effort',
            'finished', 'flow', 'kept', 'last_shared', 'look', 'mine', 'model', 'model_mode', 'note', 'notice', 'outline', 'problem',
            'question', 'queue', 'redesign', 'research_from', 'research_progress', 'review', 'review_level', 'sentence', 'spent', 'state', 'steps', 'taken', 'timing',
            'workers']
STEP_KEYS = ['attempts', 'dollars', 'error', 'id', 'kind', 'label', 'seconds', 'status']
DIRECT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


@contextlib.contextmanager
def meanwhile(write):
    """Another studio writes the studios config once, just before this one takes the lock:
    after whatever this one looked at outside the lock, and before it writes."""
    taking, waiting = studios_config._locked, [write]

    @contextlib.contextmanager
    def locked():
        while waiting:
            waiting.pop()()
        with taking():
            yield

    with mock.patch.object(studios_config, '_locked', locked):
        yield


def never(*args, **kwargs):
    raise AssertionError('A test must never look at the real computer.')


class PageCase(StudioCase):
    """The runner's page, asked without a socket."""

    PORT = 8765

    def setUp(self):
        super().setUp()
        for patcher in (mock.patch.object(computer, 'run', never),
                        mock.patch.object(computer, 'reach', never)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.page = page.RunnerPage(self.PORT, self.engine)
        self.origin = f'http://127.0.0.1:{self.PORT}'

    def headers(self, token=True, host=None, origin=None, kind=None) -> Message:
        made = Message()
        made['Host'] = host or f'127.0.0.1:{self.PORT}'
        if token:
            made[desk.TOKEN_HEADER] = self.page.token if token is True else token
        for name, value in (('Origin', origin), ('Content-Type', kind)):
            if value:
                made[name] = value
        return made

    def answer(self, method: str, target: str, body: bytes | None = None, **options):
        """One request, answered as the server would: the status, the JSON, and `Allow`."""
        try:
            status, _, data = self.page.answer(target, self.headers(**options), method, body)
        except desk.Refusal as refusal:
            return int(refusal.status), {'error': str(refusal)}, refusal.allow
        except WorkspaceError as refusal:
            return 409, {'error': str(refusal)}, None
        self.assertNotIn(b'<', data)
        return int(status), json.loads(data) if data else None, None

    def get(self, endpoint: str, expect: int = 200, **params):
        target = f'/api/{endpoint}' + (f'?{urlencode(params)}' if params else '')
        status, reply, _ = self.answer('GET', target)
        self.assertEqual(status, expect, reply)
        return reply

    def post(self, endpoint: str, sent, expect: int = 200, **options):
        """POST as the page does, unless `options` say otherwise."""
        options.setdefault('origin', self.origin)
        options.setdefault('kind', 'application/json')
        body = sent if isinstance(sent, (bytes, type(None))) else json.dumps(sent).encode()
        status, reply, _ = self.answer('POST', f'/api/{endpoint}', body, **options)
        self.assertEqual(status, expect, reply)
        return reply

    def started(self, **changes) -> str:
        return self.post('trainings', {**FORM, 'flow': 'desk', **changes})['path']

    def saved_started(self, **changes) -> str:
        """A saved fixture enters the page through its actual run reader."""
        return str(self.saved_start(**changes))

    def on_disk(self) -> dict:
        return {path.relative_to(self.base).as_posix(): path.read_bytes()
                for path in sorted(self.base.rglob('*'))
                if path.is_file() and '.git' not in path.parts}


class FirstTimeCase(PageCase):
    """A computer where nothing is set up yet."""

    def set_up(self):
        return None

    def bare(self, name: str = 'team-repo.git') -> Path:
        remote = self.base / name
        remote.mkdir()
        self.git('init', '--quiet', '--bare', repo=remote)
        self.git('symbolic-ref', 'HEAD', 'refs/heads/main', repo=remote)
        return remote

    def someone_else(self, remote: Path, **named) -> None:
        """A teammate sets the workspace up in the shared repository and shares it."""
        with mock.patch.dict(os.environ, {'TRAINING_STUDIO_DATA': str(self.base / 'theirs'),
                                          'STUDIOS_CONFIG': str(self.base / 'theirs.json')}):
            self.assertTrue(gitstate.sync(gitstate.join(str(remote), **named))['shared'])


class CapabilityTests(PageCase):
    def test_the_runner_says_it_is_here(self):
        self.assertEqual(self.get('capabilities'), {'runner': True, 'version': VERSION})

    def test_the_plain_desk_answers_404_and_knows_none_of_the_runners_addresses(self):
        plain = desk.Page(self.PORT)
        headers = self.headers()
        headers.replace_header(desk.TOKEN_HEADER, plain.token)
        for target in GETS:
            with self.subTest(target):
                with self.assertRaises(desk.Refusal) as refused:
                    plain.answer(target, headers)
                self.assertEqual(refused.exception.status, 404)
        self.assertEqual((plain.reads, plain.writes), (desk.READS, desk.WRITES))
        self.assertEqual(plain.allowed('/api/trainings'), 'GET')
        listed = json.loads(plain.answer('/api/trainings', headers)[2])
        self.assertEqual(listed, {'trainings': [], 'needs': 0})

    def test_it_serves_the_desks_own_page(self):
        status, kind, body = self.page.answer('/', self.headers(token=False))
        self.assertEqual((status, kind), (200, 'text/html; charset=utf-8'))
        self.assertEqual(body, (desk.PAGE_DIR / 'index.html').read_bytes())


class ResearchSiteTests(PageCase):
    def test_a_site_added_on_the_form_is_checked_here_and_saved_nowhere(self):
        studios_config.update({'research': {'sites': ['https://docs.example.com']}})
        before = studios_config.read()[0]
        self.assertEqual(self.post('research-site', {'site': ' Blogs.VMware.com/tanzu/ '}),
                         {'site': 'https://blogs.vmware.com/tanzu',
                          'shown': 'blogs.vmware.com/tanzu'})
        for sent, said in (
                ({'site': 'http://blogs.vmware.com/tanzu'},
                 '"http://blogs.vmware.com/tanzu": research sites use https only.'),
                ({'site': 'localhost/docs'}, '"localhost/docs" is not a public site. Research '
                 'never reads this computer or a private network.'),
                ({'site': 'docs.example.com', 'more': 1}, 'Give one site to check.'),
                ({}, 'Give one site to check.')):
            with self.subTest(sent):
                self.assertEqual(self.post('research-site', sent, expect=400)['error'], said)
        self.assertEqual(studios_config.read()[0], before)


class RuleTests(PageCase):
    """Milestone 1's safety rules, on every address the runner adds."""

    def setUp(self):
        super().setUp()
        self.path = self.saved_started()
        self.bodies = {'/api/training-plan': {'path':'nowhere', 'expected':'none', 'decision':'approve'}, '/api/research-sources': {'action':'create'}, '/api/setup/check': {'path': str(self.base / 'elsewhere')},
                       '/api/setup': {'limits': {'parallel': 4}},
                       '/api/trainings': {**FORM, 'title': 'Health checks'},
                       '/api/run': {'path': self.path, 'action': 'stop'},
                       '/api/answer': {'path': self.path, 'id': 'x', 'answer': 'Yes.'},
                       '/api/note': {'path': self.path, 'expected': '0', 'text': 'Keep it short.'},
                       '/api/research-site': {'site': 'docs.example.com'},
                       '/api/documents': {'path': self.path, 'action': 'add',
                                          'name': 'handbook.txt', 'content': 'V29yZHMu'},
                       '/api/copies': {'path': self.path},
                       '/api/review': {'path': self.path, 'expected': 'old-version', 'decision': 'approve'},
                       '/api/share': {}, '/api/companions': {}, '/api/restart': {},
                       '/api/upgrade': {'version': '99.0.0'},
                       '/api/versions': {'dismiss': 'training-studio 99.0.0'},
                       '/api/brand': {'repository': str(self.base / 'brand.git')},
                       '/api/brand/install': {'release': 'v1.2.0'},
                       '/api/asset':{'path': self.path, 'asset': 'console_view',
                                      'content': 'iVBORw0KGgo=', 'alt': 'A console',
                                      'source': 'Course author'}}
        self.before = self.on_disk()

    def refused(self, method: str, target: str, expect: int, **options) -> dict:
        body = json.dumps(self.bodies[target]).encode() if method == 'POST' else None
        if method == 'POST':
            options.setdefault('origin', self.origin)
            options.setdefault('kind', 'application/json')
        status, reply, _ = self.answer(method, target, body, **options)
        self.assertEqual(status, expect, (target, reply))
        self.assertEqual(self.on_disk(), self.before, target)
        return reply

    def test_every_call_needs_the_key(self):
        for method, targets in (('GET', GETS), ('POST', POSTS)):
            for target in targets:
                with self.subTest(target=target, method=method):
                    for token in (False, 'not-the-key'):
                        said = self.refused(method, target, 403, token=token)
                        self.assertIn('needs the key', said['error'])

    def test_it_answers_only_at_its_own_local_address(self):
        for method, targets in (('GET', GETS), ('POST', POSTS)):
            for target in targets:
                with self.subTest(target=target, method=method):
                    said = self.refused(method, target, 403, host='example.com')
                    self.assertIn('only at its own local address', said['error'])

    def test_a_change_is_taken_only_from_the_page_itself(self):
        for target in POSTS:
            with self.subTest(target):
                for origin in (None, 'http://example.com', 'http://127.0.0.1:9999'):
                    options = {'origin': origin} if origin else {'origin': ''}
                    said = self.refused('POST', target, 403, **options)
                    self.assertIn('only from the page itself', said['error'])

    def test_a_change_is_taken_only_as_json(self):
        for target in POSTS:
            with self.subTest(target):
                self.refused('POST', target, 415, kind='application/x-www-form-urlencoded')
                status, said, _ = self.answer('POST', target, b'["a", "list"]',
                                              origin=self.origin, kind='application/json')
                self.assertEqual((status, said['error']),
                                 (400, 'Send the change as one JSON object.'))
                status, _, _ = self.answer('POST', target, None, origin=self.origin,
                                           kind='application/json')
                self.assertEqual(status, 413)
                status, _, _ = self.answer('POST', f'{target}?path=x', b'{}',
                                           origin=self.origin, kind='application/json')
                self.assertEqual(status, 400)
        self.assertEqual(self.on_disk(), self.before)

    def test_each_address_answers_only_its_own_methods(self):
        for target in GETS:
            expect = 'GET, POST' if target in BOTH else 'GET'
            self.assertEqual(self.page.allowed(target), expect)
        for target in POSTS:
            expect = 'GET, POST' if target in BOTH else 'POST'
            self.assertEqual(self.page.allowed(f'{target}?x=1'), expect)
        for target in set(GETS) - set(BOTH):
            status, _, allow = self.answer('POST', target, b'{}', origin=self.origin,
                                           kind='application/json')
            self.assertEqual((status, allow), (405, 'GET'))
        for target in set(POSTS) - set(BOTH):
            status, _, allow = self.answer('GET', target)
            self.assertEqual((status, allow), (405, 'POST'))
        for method in ('PUT', 'PATCH', 'DELETE'):
            status, _, allow = self.answer(method, '/api/run')
            self.assertEqual((status, allow), (405, 'GET, POST'))
        self.assertEqual(self.on_disk(), self.before)

    def test_the_desks_own_addresses_are_still_refused_as_before(self):
        self.assertEqual(self.answer('GET', '/api/decide')[::2], (405, 'POST'))
        self.assertEqual(self.answer('GET', '/api/nothing')[0], 404)
        status, said, _ = self.answer('GET', '/api/training?path=' + str(self.base))
        self.assertEqual((status, said['error']),
                         (403, 'That folder is not a training this computer knows.'))


class SetUpTests(FirstTimeCase):
    def test_nothing_is_set_up_at_first(self):
        self.assertEqual(self.get('setup'), {
            'configured': False, 'review_level': 'step_by_step',
            'workspace': None, 'shared': {}, 'shared_problem': None,
            'team_moved': None, 'shared_notice': None,
            'agent': {'default': 'claude', 'model': None, 'effort': None},
            'limits': {'step_seconds': 900, 'training_dollars': 20.0, 'parallel': 2},
            'previews': {'how': None, 'pool': False, 'drive': False, 'local': False, 'left': []},
            'notify': {'on': False, 'can': True, 'problem': None},
            'updates': {'look': True}, 'upkeep': None,
            'brand': {'found': False, 'name': None, 'brands': [], 'skills': [],
                      'problem': NO_BRAND_SKILL, 'repository': None, 'release': None}})
        said = self.post('trainings', {**FORM, 'flow': 'desk'}, 409)
        self.assertIn('No workspace is set up on this computer yet', said['error'])
        self.assertIn('No workspace is set up', self.post('share', {}, 409)['error'])
        self.assertEqual(self.get('trainings'), {'trainings': [], 'needs': 0})

    def test_a_folder_on_this_computer_becomes_the_workspace(self):
        folder = self.base / 'my-trainings'
        made = self.post('setup', {
            'path': str(folder), 'folder': 'courses', 'branch': 'main', 'name': 'my-work',
            'share_when': 'when-asked', 'agent': 'codex', 'model': 'a-model',
            'effort': 'ultra',
            'limits': {'step_seconds': 600, 'training_dollars': 7.5, 'parallel': 3}})
        self.assertEqual(made, {
            'configured': True, 'review_level': 'step_by_step',
            # A folder on this computer has nowhere to share to, so when to share, a value
            # every studio shares, is not set from it.
            'workspace': {'name': 'my-work', 'repository': None, 'path': str(folder),
                          'folder': 'courses', 'branch': 'main',
                          'share_when': 'each-decision', 'shared': False, 'notice': None},
            'shared': {'assistant': {'agent': 'codex', 'model': 'a-model', 'effort': 'ultra'}},
            'shared_problem': None, 'team_moved': None, 'shared_notice': None,
            'agent': {'default': 'codex', 'model': 'a-model', 'effort': 'ultra'},
            'limits': {'step_seconds': 600, 'training_dollars': 7.5, 'parallel': 3},
            'previews': {'how': None, 'pool': False, 'drive': False, 'local': False, 'left': []},
            'notify': {'on': False, 'can': True, 'problem': None},
            'updates': {'look': True}, 'upkeep': None,
            'brand': {'found': False, 'name': None, 'brands': [], 'skills': [],
                      'problem': NO_BRAND_SKILL, 'repository': None, 'release': None}})
        self.assertEqual(self.get('setup'), made)
        marker = json.loads((folder / 'courses' / 'hub.json').read_text())
        self.assertEqual((marker['tool'], marker['name'], marker['folder'], marker['branch']),
                         ('training-studio', 'my-work', 'courses', 'main'))
        self.assertEqual(settings.load(), settings.Settings(
            agent='codex', model='a-model', effort='ultra', step_seconds=600,
            training_dollars=7.5, parallel=3))
        # The agent is kept only in the file every studio shares; the limits only here.
        self.assertEqual(json.loads(Path(os.environ['STUDIOS_CONFIG']).read_text()), {
            'schema': 1, 'assistant': {'agent': 'codex', 'model': 'a-model', 'effort': 'ultra'}})
        self.assertEqual(sorted(json.loads(settings.path().read_text())), [
            'look_for_updates', 'notify', 'parallel', 'schema', 'step_seconds', 'training_dollars'])
        path = self.started()
        self.assertEqual(Path(path), folder / 'courses' / 'rolling-restarts')
        self.assertEqual(self.get('run', path=path)['agent'], 'codex')

    def test_a_repository_becomes_the_workspace_in_a_copy_of_the_runners_own(self):
        remote = self.bare()
        made = self.post('setup', {'repository': str(remote), 'folder': None, 'branch': None,
                                   'name': None, 'share_when': 'each-decision',
                                   'agent': 'claude', 'model': None, 'limits': {}})
        space = made['workspace']
        self.assertEqual((space['name'], space['repository'], space['folder'],
                          space['branch'], space['share_when'], space['shared']),
                         ('team-repo', str(remote), 'trainings', 'main', 'each-decision',
                          False))
        self.assertEqual(Path(space['path']), gitstate.clones() / 'team-repo')
        # The repository joined is the one every studio shares now. Sharing after each
        # decision is the default, so nothing says it.
        self.assertEqual(json.loads(Path(os.environ['STUDIOS_CONFIG']).read_text()), {
            'schema': 1, 'team': {'repository': str(remote), 'branch': 'main'}})
        self.assertEqual(self.post('share', {}), {'shared': True, 'notice': None})
        self.assertEqual(self.get('setup')['workspace']['shared'], True)

    def test_set_up_asked_again_starts_nothing_when_nothing_has_changed(self):
        remote = self.bare()
        self.post('setup', {'repository': str(remote), 'folder': None, 'branch': None,
                            'name': None, 'share_when': 'when-asked', 'agent': 'claude',
                            'model': None, 'limits': {}})
        first = self.get('setup')
        started, looked, real = [], [], subprocess.Popen

        def counted(*given, **named):
            started.append(given[0] if given else named.get('args'))
            return real(*given, **named)

        def found():
            looked.append('found')
            return []

        with mock.patch.object(subprocess, 'Popen', counted), \
                mock.patch.object(self.engines.brand_skill, 'found', found):
            again = [self.get('setup') for _ in range(3)]
        self.assertEqual((again, started, looked), ([first] * 3, [], []))
        # Something changed: what was committed here is shared, and set-up says so.
        self.assertEqual(self.post('share', {}), {'shared': True, 'notice': None})
        self.assertEqual(self.get('setup')['workspace']['shared'], True)

    def test_a_second_person_is_asked_for_nothing_the_repository_already_says(self):
        remote = self.bare()
        self.someone_else(remote, folder='courses', name='field-team')
        made = self.post('setup', {'repository': str(remote)})
        space = made['workspace']
        self.assertEqual((space['name'], space['folder'], space['branch']),
                         ('field-team', 'courses', 'main'))

    def test_the_settings_can_change_without_moving_the_workspace(self):
        folder = self.base / 'my-trainings'
        self.post('setup', {'path': str(folder)})
        changed = self.post('setup', {'share_when': 'when-asked', 'model': 'a-model',
                                      'effort': 'max', 'limits': {'parallel': 4}})
        self.assertEqual((changed['workspace']['path'], changed['workspace']['share_when'],
                          changed['agent'], changed['limits']),
                         (str(folder), 'each-decision',
                          {'default': 'claude', 'model': 'a-model', 'effort': 'max'},
                          {'step_seconds': 900, 'training_dollars': 20.0, 'parallel': 4}))
        # The model and the level are kept while the agent is, and are the new agent's own
        # once it changes.
        self.assertEqual(self.post('setup', {'limits': {'parallel': 3}})['agent'],
                         {'default': 'claude', 'model': 'a-model', 'effort': 'max'})
        self.assertEqual(self.post('setup', {'agent': 'codex'})['agent'],
                         {'default': 'codex', 'model': None, 'effort': None})

    def test_set_up_that_makes_no_sense_changes_nothing(self):
        folder = str(self.base / 'my-trainings')
        for sent, said in (
                ({}, "Give the repository's address, or a folder on this computer."),
                ({'path': folder, 'repository': 'https://example.com/team/team-repo.git'},
                 "Give the repository's address or a folder on this computer, not both."),
                ({'path': 'my-trainings'}, "Give the folder's whole path"),
                ({'path': folder, 'folder': '../outside'}, 'A workspace folder is letters'),
                ({'path': folder, 'branch': 'not a branch'}, 'cannot be the name of a branch'),
                ({'path': folder, 'name': 'two words'}, 'A workspace name is letters'),
                ({'path': folder, 'share_when': 'never'}, 'Sharing is one of: each-decision, '
                 'when-asked.'),
                ({'path': folder, 'agent': 'another'}, 'The agent is one of: claude, codex.'),
                ({'path': folder, 'model': 'two words'}, 'The model is the short name'),
                ({'path': folder, 'effort': 'warp'}, 'The reasoning level is one of: low, '
                 'medium, high, xhigh, max, or nothing for the agent\'s own choice.'),
                ({'path': folder, 'agent': 'codex', 'effort': ['high']}, 'The reasoning level '
                 'is one of: none, minimal, low, medium, high, xhigh, max, ultra,'),
                ({'path': folder, 'model': 'claude-haiku-4-5', 'effort': 'low'},
                 'Haiku 4.5 takes no reasoning level: leave it to the agent.'),
                ({'path': folder, 'limits': [900]}, 'Give the limits as'),
                ({'path': folder, 'limits': {'step_seconds': 5}},
                 'The time for one step, in seconds, is a whole number from 60 to 7200.'),
                ({'path': folder, 'limits': {'training_dollars': 0}},
                 'What a training may spend, in dollars, is a number from 0.01 to 1000.'),
                ({'path': folder, 'limits': {'parallel': 2.5}},
                 'How many trainings run at once is a whole number from 1 to 8.'),
                ({'path': 7}, 'Give the path as text.')):
            with self.subTest(sent=sent):
                self.assertIn(said, self.post('setup', sent, 400)['error'])
        self.assertFalse(Path(folder).exists())
        self.assertEqual((self.get('setup')['configured'], settings.path().exists()),
                         (False, False))

    def test_set_up_needs_a_git_identity_and_says_how_to_give_one(self):
        helpers.gitconfig(self.base / 'nobody.gitconfig', '[user]\n\tuseConfigOnly = true\n')
        with mock.patch.dict(os.environ, {'GIT_CONFIG_GLOBAL':
                                          str(self.base / 'nobody.gitconfig')}):
            said = self.post('setup', {'path': str(self.base / 'my-trainings')}, 409)
            self.assertIn('git does not know who you are', said['error'])
            self.assertIn('git config --global user.name', said['error'])
            checked = self.post('setup/check', {'path': str(self.base / 'my-trainings')})
        self.assertEqual(self.get('setup')['configured'], False)
        who = checked['checks'][2]
        self.assertEqual((checked['ok'], who['what'], who['ok']),
                         (False, 'git knows who you are', False))
        self.assertIn('git config --global user.name "Your Name"', who['fix'])

    def test_setting_up_picks_up_the_trainings_already_in_the_workspace(self):
        remote = self.bare()
        with mock.patch.dict(os.environ, {'TRAINING_STUDIO_DATA': str(self.base / 'theirs'),
                                          'STUDIOS_CONFIG': str(self.base / 'theirs.json')}):
            theirs = self.make()
            gitstate.join(str(remote))
            made = theirs.start(pipeline.check_form({**FORM, 'flow': 'desk'}))
            self.assertTrue(theirs.share()['shared'])
        self.assertEqual(self.get('trainings')['trainings'], [])
        self.post('setup', {'repository': str(remote)})
        listed = self.get('trainings')['trainings']
        # It is the other computer's: all that is known here is what was last shared.
        self.assertEqual([(item['title'], item['run']['state'], item['mine'], item['state'])
                          for item in listed],
                         [('Rolling restarts', 'elsewhere', False, 'in-progress')])
        self.assertNotEqual(listed[0]['path'], made['path'])


class SharedTests(FirstTimeCase):
    """The studios config every *-studio reads is the only place the values they share are
    kept: Training Studio reads them from it each time, and saving one writes it there."""

    # Another studio's file: its own layout, and keys Training Studio does not know.
    THEIRS = ('{\n'
              '  "schema": 1,\n'
              '  "team": { "repository": "@REMOTE@", "branch": "main", "lead": "sam" },\n'
              '  "person": { "name": "Dan Baskette" },\n'
              '  "assistant": { "agent": "claude", "model": "opus", "effort": "high" },\n'
              '  "brand": { "repository": "https://github.com/example/brand-skill.git",\n'
              '             "release": "v1.4.0", "brand": "tanzu", "variant": "light" },\n'
              '  "output": "google",\n'
              '  "share": "decision",\n'
              '  "blog": {"tone": "plain", "drafts": [1, 2, {"x": null}]}\n'
              '}\n')
    BRAND = 'https://github.com/example/brand-skill.git'

    def setUp(self):
        super().setUp()
        self.file = Path(os.environ['STUDIOS_CONFIG'])

    def theirs(self, remote: Path) -> str:
        text = self.THEIRS.replace('@REMOTE@', str(remote))
        self.file.write_text(text, encoding='utf-8')
        return text

    def unreadable(self, why: str = 'it is not valid JSON') -> tuple[str, str]:
        """What set-up says of a file that cannot be read, and what a save that would
        change a shared value is refused with."""
        return (f'{self.file} could not be read ({why}), so Training Studio uses its built-in '
                'defaults for the values every studio shares, and saves none of them, until '
                'it can be read.',
                f'{self.file} could not be read ({why}), so no value every studio shares can '
                'be saved until it can, and the file was left as it is.')

    def test_with_no_file_nothing_is_written_until_a_shared_value_changes(self):
        self.assertFalse(self.file.exists())
        found = self.get('setup')
        self.assertEqual((found['shared'], found['shared_problem']), ({}, None))
        self.post('setup', {'path': str(self.base / 'mine'), 'limits': {'parallel': 3}})
        self.assertFalse(self.file.exists())

    def test_the_shared_values_are_read_from_the_file_and_nowhere_else(self):
        remote = self.bare()
        text = self.theirs(remote)
        found = self.get('setup')
        self.assertIsNone(found['shared_problem'])
        self.assertEqual(found['shared'], {
            'team': {'repository': str(remote), 'branch': 'main'},
            'assistant': {'agent': 'claude', 'model': 'opus', 'effort': 'high'},
            'brand': {'repository': self.BRAND, 'release': 'v1.4.0', 'brand': 'tanzu',
                      'variant': 'light'},
            'output': 'google', 'share': 'decision'})
        # They are the settings, before anything is set up here, and the file is untouched.
        self.assertEqual((found['configured'], found['agent'], found['brand']['repository'],
                          found['brand']['release']),
                         (False, {'default': 'claude', 'model': 'opus', 'effort': 'high'},
                          self.BRAND, 'v1.4.0'))
        self.assertEqual(self.file.read_text(), text)
        self.assertFalse(settings.path().exists())

    def test_one_changed_in_another_studio_is_what_this_one_uses(self):
        self.post('setup', {'path': str(self.base / 'mine')})
        self.file.write_text('{"schema": 1, "assistant": {"agent": "codex", "model": '
                             '"gpt-6-sol"}}')
        self.assertEqual(self.get('setup')['agent'],
                         {'default': 'codex', 'model': 'gpt-6-sol', 'effort': None})
        self.assertEqual(settings.load().agent, 'codex')
        self.assertEqual(self.get('run', path=self.started())['agent'], 'codex')

    def test_a_value_training_studio_would_refuse_is_left_out(self):
        for written, shared in (
                ({'team': {'repository': 'https://dan:hunter2@github.com/acme/team.git',
                           'branch': 'main'}}, {'team': {'branch': 'main'}}),
                ({'team': {'repository': 'two words', 'branch': '-x'}}, {}),
                ({'team': {'branch': 'a..b'}, 'share': 'sometimes', 'output': 'pdf'}, {}),
                ({'assistant': {'agent': 'gemini', 'model': 'pro', 'effort': 'high'}}, {}),
                ({'assistant': {'model': 'claude-haiku-4-5', 'effort': 'high'}},
                 {'assistant': {'model': 'claude-haiku-4-5'}}),
                ({'assistant': {'agent': 'codex', 'effort': 'ultra'}},
                 {'assistant': {'agent': 'codex', 'effort': 'ultra'}}),
                ({'brand': {'repository': 'https://pat:secret@github.com/acme/brand.git',
                            'release': 'v1.4.0'}}, {}),
                ({'brand': {'release': 'v1.4.0'}}, {}),
                ({'brand': {'repository': 'git@github.com:acme/brand.git', 'release': '-x'}},
                 {'brand': {'repository': 'git@github.com:acme/brand.git'}}),
                ({'assistant': ['claude'], 'brand': {'brand': 7, 'variant': 'dark'},
                  'person': {'name': 'Dan'}}, {'brand': {'variant': 'dark'}})):
            with self.subTest(written=written):
                self.file.write_text(json.dumps({'schema': 1, **written}))
                found = self.get('setup')
                self.assertEqual(found['shared'], shared)
                self.assertEqual(found['agent']['default'],
                                 shared.get('assistant', {}).get('agent', 'claude'))

    def test_saving_writes_only_what_changed_and_keeps_every_other_byte(self):
        remote = self.bare()
        text = self.theirs(remote)
        # The first set-up, as the page fills it in from the file, with the agent changed.
        made = self.post('setup', {'repository': str(remote), 'branch': 'main',
                                   'share_when': 'each-decision', 'agent': 'codex',
                                   'model': 'gpt-6-sol', 'effort': None})
        self.assertNotIn('for_all_studios', made)
        text = text.replace('"agent": "claude", "model": "opus", "effort": "high"',
                            '"agent": "codex", "model": "gpt-6-sol", "effort": null')
        self.assertEqual(self.file.read_text(encoding='utf-8'), text)
        self.assertEqual(made['agent'], {'default': 'codex', 'model': 'gpt-6-sol',
                                         'effort': None})
        # A second read, and a fresh one of the file, see it; this computer keeps no copy.
        self.assertEqual(self.get('setup')['agent'], made['agent'])
        self.assertEqual((settings.load().agent, settings.load().model), ('codex', 'gpt-6-sol'))
        self.assertEqual(studios_config.read()[0]['assistant']['agent'], 'codex')
        self.assertFalse({'agent', 'model', 'effort', 'brand_repository', 'brand_release'}
                         & set(json.loads(settings.path().read_text())))
        # Later, only when to share changes, and only it is written.
        self.assertEqual(self.post('setup', {'share_when': 'when-asked'})['workspace'][
            'share_when'], 'when-asked')
        text = text.replace('"share": "decision"', '"share": "asked"')
        self.assertEqual(self.file.read_text(encoding='utf-8'), text)
        self.post('setup', {'model': 'gpt-6-luna'})
        text = text.replace('"gpt-6-sol"', '"gpt-6-luna"')
        self.assertEqual(self.file.read_text(encoding='utf-8'), text)
        # Saved again with nothing changed, nothing is written at all.
        before = self.file.stat().st_mtime_ns
        self.post('setup', {'limits': {'parallel': 3}})
        self.assertEqual((self.file.read_text(encoding='utf-8'), self.file.stat().st_mtime_ns),
                         (text, before))

    def test_a_first_write_makes_the_file_with_what_was_set_up(self):
        remote = self.bare()
        self.post('setup', {'repository': str(remote), 'share_when': 'when-asked',
                            'agent': 'claude', 'model': 'opus', 'effort': 'high'})
        # The agent is Claude Code already, so only what differs from that is written.
        self.assertEqual(json.loads(self.file.read_text()), {
            'schema': 1, 'team': {'repository': str(remote), 'branch': 'main'},
            'share': 'asked', 'assistant': {'model': 'opus', 'effort': 'high'}})

    def test_a_folder_on_this_computer_is_no_team_repository_to_share(self):
        self.post('setup', {'path': str(self.base / 'mine'), 'share_when': 'when-asked'})
        self.assertFalse(self.file.exists())
        self.post('setup', {'share_when': 'when-asked', 'agent': 'codex'})
        self.assertEqual(json.loads(self.file.read_text()),
                         {'schema': 1, 'assistant': {'agent': 'codex'}})

    def test_an_address_with_a_password_is_refused_and_the_file_is_untouched(self):
        remote = self.bare()
        text = self.theirs(remote)
        said = self.post('setup', {'repository': 'https://dan:hunter2@example.com/team.git'},
                         409)
        self.assertIn('carries a password or token', said['error'])
        self.assertEqual(self.file.read_text(encoding='utf-8'), text)

    def test_a_file_that_cannot_be_read_holds_nothing_up_and_is_never_written(self):
        broken = '{"schema": 1, "team": '
        self.file.write_text(broken, encoding='utf-8')
        says, refused = self.unreadable()
        found = self.get('setup')
        self.assertEqual((found['shared'], found['shared_problem'], found['agent']),
                         ({}, says, {'default': 'claude', 'model': None, 'effort': None}))
        # A save that would change a shared value is refused before anything changes.
        mine = str(self.base / 'mine')
        self.assertEqual(self.post('setup', {'path': mine, 'agent': 'codex'}, 409)['error'],
                         refused)
        self.assertEqual(self.post('setup', {'repository': str(self.bare())}, 409)['error'],
                         refused)
        self.assertEqual((self.get('setup')['configured'], Path(mine).exists(),
                          list(gitstate.clones().glob('*'))), (False, False, []))
        # One that changes none of them goes through, and work carries on.
        made = self.post('setup', {'path': mine, 'share_when': 'when-asked',
                                   'limits': {'parallel': 3}})
        self.assertEqual((made['configured'], made['limits']['parallel'],
                          made['shared_problem']), (True, 3, says))
        self.assertTrue(self.started())
        self.assertEqual(self.file.read_text(encoding='utf-8'), broken)

    def test_the_brand_skills_repository_is_shared_and_refused_while_the_file_is_unreadable(
            self):
        self.post('setup', {'path': str(self.base / 'mine')})
        self.file.write_text('[1, 2]')
        keeper = self.engine.upkeep = Keeper()
        said = self.post('brand', {'repository': 'git@github.com:acme/brand.git'}, 400)
        self.assertEqual(said['error'], self.unreadable('it does not hold a JSON object')[1])
        self.assertEqual((keeper.asked, self.file.read_text()), ([], '[1, 2]'),
                         'git was asked nothing, and the file is as it was')
        # Forgetting a repository that was never named changes nothing, so it goes through.
        self.assertIsNone(self.post('brand', {'repository': ''})['brand']['repository'])

    def test_a_team_repository_changed_in_another_studio_is_said_and_never_followed(self):
        remote, other = self.bare(), self.bare('other-repo.git')
        self.post('setup', {'repository': str(remote)})
        self.assertIsNone(self.get('setup')['team_moved'])
        self.file.write_text(json.dumps({'schema': 1, 'team': {'repository': str(other),
                                                               'branch': 'main'}}))
        found = self.get('setup')
        self.assertEqual(found['team_moved'], {
            'repository': str(other), 'branch': 'main',
            'says': f'The team repository your studios share is now {other}, and Training Studio '
                    f'still works in its copy of {remote}. Marketing Studio can connect this '
                    'studio: open Marketing Studio and choose Connect on its card, or join the '
                    'new repository from here.'})
        self.assertEqual(found['workspace']['repository'], str(remote), 'nothing moved')
        # The same repository written another way is the same one.
        self.file.write_text(json.dumps({'schema': 1, 'team': {'repository': f'{remote}/'}}))
        self.assertIsNone(self.get('setup')['team_moved'])
        # Joining it, as the page offers, settles it, and the file's branch is kept.
        self.file.write_text(json.dumps({'schema': 1, 'team': {'repository': str(other),
                                                               'branch': 'trunk'}}))
        joined = self.post('setup', {'repository': str(other)})
        self.assertEqual((joined['workspace']['repository'], joined['team_moved']),
                         (str(other), None))
        self.assertEqual(json.loads(self.file.read_text())['team'],
                         {'repository': str(other), 'branch': 'trunk'})

    def test_a_folder_on_this_computer_is_never_compared(self):
        self.post('setup', {'path': str(self.base / 'mine')})
        self.theirs(self.bare())
        self.assertIsNone(self.get('setup')['team_moved'])

    def test_a_set_up_opened_before_another_studio_changed_a_value_never_writes_over_it(self):
        remote = self.bare()
        self.post('setup', {'repository': str(remote)})
        shown = self.get('setup')['shared']
        # Meanwhile, another studio changes the agent, its model and when to share.
        text = json.dumps({'schema': 1, 'team': {'repository': str(remote), 'branch': 'main'},
                           'assistant': {'agent': 'codex', 'model': 'gpt-6-sol'},
                           'share': 'asked'})
        self.file.write_text(text)
        # The page sends what its form shows, which is what it was shown. What the person
        # left alone stays as the other studio has it.
        sent = {'share_when': 'each-decision', 'agent': 'claude', 'model': None,
                'effort': None, 'limits': {'parallel': 4}, 'shared_seen': shown}
        made = self.post('setup', sent)
        self.assertEqual((made['agent'], made['workspace']['share_when'],
                          made['limits']['parallel']),
                         ({'default': 'codex', 'model': 'gpt-6-sol', 'effort': None},
                          'when-asked', 4))
        self.assertEqual(self.file.read_text(), text)
        # A change to the same value is refused, before anything changes.
        refused = self.post('setup', {**sent, 'agent': 'codex', 'model': 'gpt-6-luna',
                                      'limits': {'parallel': 5}}, 409)
        self.assertEqual(refused['error'], 'The model was changed in another studio while '
                         'this was open, so nothing was saved. Look again, then save.')
        self.assertEqual((self.file.read_text(), settings.load().parallel), (text, 4))
        # Changed to what the other studio chose, there is nothing to refuse.
        self.post('setup', {**sent, 'share_when': 'when-asked'})
        self.assertEqual(self.file.read_text(), text)
        # The team repository changed there, and another one is joined here.
        other, third = self.bare('other-repo.git'), self.bare('third-repo.git')
        self.file.write_text(json.dumps({'schema': 1, 'team': {'repository': str(other)}}))
        refused = self.post('setup', {'repository': str(third), 'shared_seen': shown}, 409)
        self.assertTrue(refused['error'].startswith('The team repository was changed in '
                                                    'another studio'))
        self.assertEqual(self.get('setup')['workspace']['repository'], str(remote))
        self.assertEqual(self.post('setup', {'shared_seen': ['x']}, 400)['error'],
                         'Give shared_seen as the shared values the page was shown.')

    def test_a_refused_set_up_joins_nothing_and_saves_once_it_has_looked_again(self):
        remote, other = self.bare(), self.bare('other-repo.git')
        self.post('setup', {'repository': str(remote), 'limits': {'parallel': 3}})
        shown = self.get('setup')['shared']
        record = gitstate.settings_path().read_text()
        clones = sorted(path.name for path in gitstate.clones().iterdir())
        # Meanwhile, another studio changes the model.
        text = json.dumps({'schema': 1, 'team': {'repository': str(remote), 'branch': 'main'},
                           'assistant': {'agent': 'claude', 'model': 'sonnet'}})
        self.file.write_text(text)
        # Here, another team repository is joined, with another model.
        sent = {'repository': str(other), 'share_when': 'when-asked', 'agent': 'claude',
                'model': 'opus', 'effort': None, 'limits': {'parallel': 5},
                'shared_seen': shown}
        refused = self.post('setup', sent, 409)
        # Nothing changed: not the workspace, its clones, the file or this computer's limits.
        self.assertEqual((gitstate.settings_path().read_text(),
                          sorted(path.name for path in gitstate.clones().iterdir()),
                          self.file.read_text(), settings.load().parallel),
                         (record, clones, text, 3))
        self.assertEqual(refused['error'], 'The model was changed in another studio while '
                         'this was open, so nothing was saved. Look again, then save.')
        # Looked at again, the same choice is the person's, over what the other studio chose.
        again = self.get('setup')['shared']
        self.assertEqual(again['assistant'], {'agent': 'claude', 'model': 'sonnet'})
        made = self.post('setup', {**sent, 'shared_seen': again})
        self.assertEqual((made['workspace']['repository'], made['workspace']['share_when'],
                          made['agent'], made['limits']['parallel']),
                         (str(other), 'when-asked',
                          {'default': 'claude', 'model': 'opus', 'effort': None}, 5))
        self.assertEqual(json.loads(self.file.read_text()), {
            'schema': 1, 'team': {'repository': str(other), 'branch': 'main'},
            'assistant': {'agent': 'claude', 'model': 'opus'}, 'share': 'asked'})

    def test_a_value_another_studio_changes_while_joining_is_said_beside_the_join(self):
        remote = self.bare()
        self.file.write_text(json.dumps({'schema': 1, 'assistant': {'agent': 'claude'}}))
        shown = self.get('setup')['shared']
        theirs = {'schema': 1, 'assistant': {'agent': 'claude', 'model': 'sonnet'}}
        sent = {'repository': str(remote), 'agent': 'claude', 'model': 'opus',
                'limits': {'parallel': 5}, 'shared_seen': shown}
        # Another studio changes the model while this one joins, after set-up has looked.
        with meanwhile(lambda: self.file.write_text(json.dumps(theirs))):
            refused = self.post('setup', sent, 409)
        self.assertEqual(refused['error'], f'Training Studio joined {remote}, but the model was '
                         'changed in another studio meanwhile, so your other settings were not '
                         'saved. Set-up shows them as they are now: look again, then save.')
        # The workspace joined is the one every studio shares now, and nothing else was kept.
        found = self.get('setup')
        self.assertEqual((found['workspace']['repository'], found['team_moved'],
                          found['limits']['parallel'], found['agent']['model']),
                         (str(remote), None, 2, 'sonnet'))
        self.assertEqual(json.loads(self.file.read_text()), {
            **theirs, 'team': {'repository': str(remote), 'branch': 'main'}})
        # Saved again from what set-up shows now, the person's choice is kept.
        made = self.post('setup', {**sent, 'shared_seen': found['shared']})
        self.assertEqual((made['agent']['model'], made['limits']['parallel']), ('opus', 5))

    def test_a_team_branch_another_studio_writes_while_joining_is_kept(self):
        remote = self.bare()
        theirs = {'schema': 1, 'team': {'repository': str(remote), 'branch': 'trunk'}}
        with meanwhile(lambda: self.file.write_text(json.dumps(theirs))):
            made = self.post('setup', {'repository': str(remote)})
        self.assertEqual(json.loads(self.file.read_text()), theirs)
        self.assertEqual((made['workspace']['branch'], made['team_moved']), ('main', None))

    def test_a_team_repository_another_studio_writes_while_joining_is_kept_and_said(self):
        remote, other = self.bare(), self.bare('other-repo.git')
        theirs = {'schema': 1, 'team': {'repository': str(other), 'branch': 'trunk'}}
        with meanwhile(lambda: self.file.write_text(json.dumps(theirs))):
            made = self.post('setup', {'repository': str(remote)})
        self.assertEqual(json.loads(self.file.read_text()), theirs)
        self.assertEqual((made['workspace']['repository'], made['team_moved']['repository']),
                         (str(remote), str(other)))

    def test_when_to_share_is_compared_with_the_file_as_it_is_written(self):
        remote = self.bare()
        self.post('setup', {'repository': str(remote)})
        theirs = json.dumps({'schema': 1, 'person': {'name': 'Alex'}, 'share': 'asked'})
        with meanwhile(lambda: self.file.write_text(theirs)):
            self.post('setup', {'share_when': 'when-asked'})
        self.assertEqual(self.file.read_text(), theirs, 'already so, and not written again')

    def test_the_brand_skills_repository_saved_from_a_stale_form_keeps_what_changed(self):
        self.post('setup', {'path': str(self.base / 'mine')})
        self.file.write_text('{"schema": 1, "brand": {"repository": '
                             '"git@github.com:acme/brand.git"}}')
        shown = self.get('setup')['shared']
        text = ('{"schema": 1, "brand": {"repository": "git@github.com:acme/other.git", '
                '"release": "v2.0.0"}}')
        self.file.write_text(text)
        # Forgetting the repository the form showed, when another studio has named another
        # meanwhile, is refused.
        refused = self.post('brand', {'repository': '', 'shared_seen': shown}, 400)
        self.assertEqual(refused['error'], "The brand skill's repository was changed in "
                         'another studio while this was open, so nothing was saved. Look '
                         'again, then save.')
        self.assertEqual(self.file.read_text(), text)
        # A form that showed none, and still names none, changes nothing.
        self.post('brand', {'repository': '', 'shared_seen': {}})
        self.assertEqual(self.file.read_text(), text)

    def test_sending_for_all_studios_changes_nothing(self):
        made = self.post('setup', {'path': str(self.base / 'mine'), 'for_all_studios': True})
        self.assertNotIn('for_all_studios', made)
        self.assertFalse(self.file.exists())


class MigrationTests(FirstTimeCase):
    """On start, the shared values an earlier version kept on this computer move into the
    studios config, where it has none of them, and out of this computer's own files."""

    def setUp(self):
        super().setUp()
        self.file = Path(os.environ['STUDIOS_CONFIG'])
        self.remote = self.bare()
        self.post('setup', {'repository': str(self.remote)})
        self.file.unlink()      # as it was before the values were shared
        self.mine = json.loads(settings.path().read_text())
        self.record = json.loads(gitstate.settings_path().read_text())
        settings.path().write_text(json.dumps({
            **self.mine, 'agent': 'codex', 'model': 'gpt-6-sol', 'effort': 'high',
            'brand_repository': 'git@github.com:acme/brand.git', 'brand_release': 'v2.0.0'}))
        gitstate.settings_path().write_text(json.dumps({**self.record, 'share': 'asked'}))

    def kept_here(self) -> tuple[dict, dict]:
        return (json.loads(settings.path().read_text()),
                json.loads(gitstate.settings_path().read_text()))

    def test_they_move_into_a_file_that_has_none_and_are_used_from_there(self):
        self.assertEqual(self.get('setup')['agent']['default'], 'claude',
                         'what this computer kept is no longer read')
        self.assertEqual(setup.migrate(), [
            'assistant.agent', 'assistant.model', 'assistant.effort', 'brand.repository',
            'brand.release', 'share', 'team.repository', 'team.branch'])
        self.assertEqual(json.loads(self.file.read_text()), {
            'schema': 1, 'assistant': {'agent': 'codex', 'model': 'gpt-6-sol',
                                       'effort': 'high'},
            'brand': {'repository': 'git@github.com:acme/brand.git', 'release': 'v2.0.0'},
            'share': 'asked', 'team': {'repository': str(self.remote), 'branch': 'main'}})
        self.assertEqual(self.kept_here(), (self.mine, self.record))
        found = self.get('setup')
        self.assertEqual((found['agent'], found['workspace']['share_when'],
                          found['brand']['release'], found['shared_notice']),
                         ({'default': 'codex', 'model': 'gpt-6-sol', 'effort': 'high'},
                          'when-asked', 'v2.0.0', None))
        self.assertEqual(setup.migrate(), [], 'once moved, there is nothing left to move')

    def test_a_value_the_file_holds_already_stays_and_the_person_is_told_once(self):
        text = ('{"schema": 1, "share": "decision", "person": {"name": "Dan"},\n'
                f' "team": {{"repository": "{self.remote}", "branch": "main"}},\n'
                ' "assistant": {"agent": "claude", "model": "opus", "effort": "high"},\n'
                ' "brand": {"repository": "git@github.com:acme/brand.git", '
                '"release": "v1.4.0"}}\n')
        self.file.write_text(text)
        self.assertEqual(setup.migrate(), [])
        self.assertEqual(self.file.read_text(), text, 'nothing in it was written over')
        self.assertEqual(self.kept_here(), (self.mine, self.record))
        told = (f'Training Studio now keeps the values every studio shares only in '
                f'{self.file}, which said otherwise for the agent, the model, the brand '
                "skill's release and when to share, so what this computer had chosen for "
                'those is no longer used.')
        found = self.get('setup')
        self.assertEqual((found['shared_notice'], found['agent']['default']), (told, 'claude'))
        self.assertEqual(self.get('setup')['shared_notice'], told, 'until it is read')
        self.assertEqual(self.post('shared', {}, 400)['error'],
                         'Send {"seen": true} once the notice about the shared values has '
                         'been read.')
        self.assertIsNone(self.post('shared', {'seen': True})['shared_notice'])
        self.assertIsNone(self.get('setup')['shared_notice'])
        self.assertEqual(setup.migrate(), [])
        self.assertIsNone(self.get('setup')['shared_notice'], 'it is told once')

    def test_a_model_moves_only_beside_its_agent_and_a_release_beside_its_repository(self):
        self.file.write_text(json.dumps({'schema': 1, 'assistant': {'agent': 'claude'},
                                         'brand': {'repository': 'git@github.com:acme/x.git'}}))
        self.assertEqual(setup.migrate(), ['share', 'team.repository', 'team.branch'])
        self.assertEqual(json.loads(self.file.read_text())['assistant'], {'agent': 'claude'})
        self.assertEqual(json.loads(self.file.read_text())['brand'],
                         {'repository': 'git@github.com:acme/x.git'})
        self.assertIn("otherwise for the agent, the model, the reasoning level, the brand "
                      "skill's repository and the brand skill's release, so",
                      self.get('setup')['shared_notice'])
        self.assertEqual(self.kept_here(), (self.mine, self.record))

    def test_nothing_moves_while_the_file_cannot_be_read(self):
        self.file.write_text('{"schema": 7}')
        before = self.kept_here()
        self.assertEqual(setup.migrate(), [])
        self.assertEqual((self.file.read_text(), self.kept_here()), ('{"schema": 7}', before))
        self.assertIsNone(self.get('setup')['shared_notice'])
        # Once it can be read, they move at the next start.
        self.file.write_text('{"schema": 1}')
        self.assertEqual(len(setup.migrate()), 8)

    def test_a_branch_is_not_moved_beside_another_teams_repository(self):
        self.file.write_text(json.dumps({'schema': 1, 'team': {
            'repository': 'https://github.com/acme/elsewhere.git'}}))
        self.assertNotIn('team.branch', setup.migrate())
        self.assertEqual(json.loads(self.file.read_text())['team'],
                         {'repository': 'https://github.com/acme/elsewhere.git'})
        # That is said by the workspace itself, with a way to join the new one.
        self.assertIsNotNone(self.get('setup')['team_moved'])
        self.assertIsNone(self.get('setup')['shared_notice'])

    def test_a_value_another_studio_writes_while_they_move_is_kept(self):
        theirs = {'schema': 1, 'assistant': {'agent': 'claude', 'model': 'opus'}}
        with meanwhile(lambda: self.file.write_text(json.dumps(theirs))):
            moved = setup.migrate()
        self.assertEqual(moved, ['brand.repository', 'brand.release', 'share',
                                 'team.repository', 'team.branch'])
        self.assertEqual(json.loads(self.file.read_text())['assistant'], theirs['assistant'])
        self.assertIn('otherwise for the agent, the model and the reasoning level, so',
                      self.get('setup')['shared_notice'])
        self.assertEqual(self.kept_here(), (self.mine, self.record))

    def test_when_to_share_moves_where_the_workspaces_clone_is_gone(self):
        shutil.rmtree(Path(self.record['repo']))
        self.when_to_share_moves_from_a_record_that_is_not_whole()

    def test_when_to_share_moves_where_the_workspaces_marker_is_gone(self):
        (Path(self.record['repo']) / self.record['folder'] / gitstate.MARKER).unlink()
        self.when_to_share_moves_from_a_record_that_is_not_whole()

    def when_to_share_moves_from_a_record_that_is_not_whole(self):
        self.assertIsNone(gitstate.current())
        # While it cannot be written, it stays in the record.
        self.file.write_text('{"schema": 1, "share": ')
        self.assertEqual(setup.migrate(), [])
        self.assertEqual(gitstate.own_share(), 'asked')
        self.file.write_text('{"schema": 1}')
        self.assertIn('share', setup.migrate())
        self.assertEqual(json.loads(self.file.read_text())['share'], 'asked')
        self.assertEqual(self.kept_here(), (self.mine, self.record))


class CheckTests(FirstTimeCase):
    """`POST /api/setup/check` looks, and changes nothing."""

    WHATS = ['can be reached', 'can be written to', 'git knows who you are',
             'The folder for trainings can be used']

    def check(self, expect: int = 200, **sent) -> dict:
        sent = {'repository': None, 'path': None, 'folder': None, 'branch': None, **sent}
        before = self.on_disk()
        found = self.post('setup/check', sent, expect)
        self.assertEqual(self.on_disk(), before, 'a check changes nothing')
        self.assertEqual(self.get('setup')['configured'], False)
        if gitstate.clones().exists():
            self.assertEqual(list(gitstate.clones().iterdir()), [])
        return found

    def shape(self, found: dict) -> None:
        self.assertEqual(sorted(found), ['checks', 'found', 'ok'])
        self.assertEqual(sorted(found['found']), ['branch', 'existing', 'folder', 'name'])
        for item, what in zip(found['checks'], self.WHATS, strict=True):
            self.assertEqual(sorted(item), ['fix', 'ok', 'what'])
            self.assertIn(what, item['what'])
            self.assertEqual(item['fix'] is None, item['ok'])
        self.assertEqual(found['ok'], all(item['ok'] for item in found['checks']))

    def test_a_new_folder_on_this_computer_can_be_used(self):
        found = self.check(path=str(self.base / 'my-trainings'))
        self.shape(found)
        self.assertEqual((found['ok'], found['found']), (True, {
            'name': 'my-trainings', 'folder': 'trainings', 'branch': 'main',
            'existing': False}))
        self.assertEqual([item['what'] for item in found['checks']], [
            'The folder can be reached', 'The folder can be written to',
            'git knows who you are', 'The folder for trainings can be used'])
        named = self.check(path=str(self.base / 'my-trainings'), folder='courses',
                           branch='trainings')
        self.assertEqual((named['found']['folder'], named['found']['branch']),
                         ('courses', 'trainings'))

    def test_an_unchosen_branch_is_the_one_git_would_give_the_repository(self):
        helpers.gitconfig(
            self.base / 'trunk.gitconfig',
            '[user]\n\tname = Alex\n\temail = alex@example.com\n[init]\n\tdefaultBranch = '
            'trunk\n')
        with mock.patch.dict(os.environ, {'GIT_CONFIG_GLOBAL':
                                          str(self.base / 'trunk.gitconfig')}):
            found = self.check(path=str(self.base / 'my-trainings'))
            self.assertEqual(found['found']['branch'], 'trunk')
            made = self.post('setup', {'path': str(self.base / 'my-trainings'),
                                       'folder': None, 'branch': None})
        self.assertEqual(made['workspace']['branch'], 'trunk')
        remote = self.bare('other-repo.git')
        self.git('symbolic-ref', 'HEAD', 'refs/heads/develop', repo=remote)
        self.assertEqual(self.post('setup/check', {'repository': str(remote)})['found'][
            'branch'], 'develop')

    def test_a_folder_that_already_holds_a_workspace_says_what_it_holds(self):
        with mock.patch.dict(os.environ, {'TRAINING_STUDIO_DATA': str(self.base / 'theirs')}):
            gitstate.local(self.base / 'my-trainings', folder='courses', name='field-team')
        found = self.check(path=str(self.base / 'my-trainings'))
        self.shape(found)
        self.assertEqual((found['ok'], found['found']), (True, {
            'name': 'field-team', 'folder': 'courses', 'branch': 'main', 'existing': True}))

    def test_a_folder_that_cannot_be_the_workspace_says_why(self):
        (self.base / 'a-file').write_text('Not a folder.\n')
        clone = self.base / 'their-clone'
        self.git('clone', '--quiet', str(self.bare()), str(clone), repo=self.base)
        for path, said in ((self.base / 'a-file', 'is a file. Name a folder'),
                           (clone, 'is a copy of a shared repository that someone works in'),
                           (helpers.SKILL, 'holds Training Studio itself')):
            with self.subTest(path=path):
                found = self.check(path=str(path))
                self.shape(found)
                self.assertEqual((found['ok'], found['checks'][0]['ok']), (False, False))
                self.assertIn(said, found['checks'][0]['fix'])
                self.assertEqual(found['checks'][1]['fix'],
                                 'This is looked at once the folder can be reached.')

    @unittest.skipIf(os.geteuid() == 0, 'the superuser can write anywhere')
    def test_a_folder_that_cannot_be_written_to_says_so(self):
        locked = self.base / 'locked'
        locked.mkdir()
        locked.chmod(stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(locked.chmod, stat.S_IRWXU)
        found = self.check(path=str(locked / 'my-trainings'))
        self.assertEqual([item['ok'] for item in found['checks']], [True, False, True, True])
        self.assertIn('cannot be written to by you', found['checks'][1]['fix'])

    def test_a_repository_nobody_has_set_up_can_be_used(self):
        remote = self.bare()
        found = self.check(repository=str(remote))
        self.shape(found)
        self.assertEqual((found['ok'], found['found']), (True, {
            'name': 'team-repo', 'folder': 'trainings', 'branch': 'main', 'existing': False}))
        self.assertEqual([item['what'] for item in found['checks']], [
            'The repository can be reached', 'The repository can be written to',
            'git knows who you are', 'The folder for trainings can be used'])
        self.assertEqual(self.git('for-each-ref', repo=remote), '', 'nothing was pushed')

    def test_a_repository_a_teammate_set_up_says_what_it_holds(self):
        remote = self.bare()
        self.someone_else(remote, folder='courses', name='field-team')
        before = self.git('for-each-ref', repo=remote)
        found = self.check(repository=str(remote))
        self.shape(found)
        self.assertEqual((found['ok'], found['found']), (True, {
            'name': 'field-team', 'folder': 'courses', 'branch': 'main', 'existing': True}))
        self.assertEqual(self.git('for-each-ref', repo=remote), before)
        other = self.check(repository=str(remote), branch='another')
        self.assertEqual((other['ok'], other['checks'][3]['ok']), (False, False))
        self.assertIn("says this workspace's work is on the branch main, not another",
                      other['checks'][3]['fix'])

    def test_a_folder_that_belongs_to_another_tool_is_not_taken(self):
        remote = self.bare()
        clone = self.base / 'their-clone'
        self.git('clone', '--quiet', str(remote), str(clone), repo=self.base)
        (clone / 'decks').mkdir()
        (clone / 'decks' / 'hub.json').write_text('{"tool": "another-tool", "schema": 1}\n')
        self.git('add', '-A', repo=clone)
        self.git('commit', '--quiet', '-m', 'Another tool', repo=clone)
        self.git('push', '--quiet', 'origin', 'HEAD:main', repo=clone)
        found = self.check(repository=str(remote), folder='decks')
        self.assertEqual([item['ok'] for item in found['checks']], [True, True, True, False])
        self.assertIn('belongs to another tool', found['checks'][3]['fix'])
        self.assertEqual(self.check(repository=str(remote))['found']['existing'], False)

    def test_a_repository_that_cannot_be_reached_says_how_to_put_it_right(self):
        found = self.check(repository=str(self.base / 'nowhere.git'))
        self.shape(found)
        self.assertEqual([item['ok'] for item in found['checks']], [False, False, True, False])
        self.assertIn('The repository could not be reached (', found['checks'][0]['fix'])
        self.assertIn('Check the address, and that git can sign in to it without asking',
                      found['checks'][0]['fix'])
        self.assertEqual(found['found'], {'name': 'nowhere', 'folder': 'trainings',
                                          'branch': 'main', 'existing': False})

    def test_an_address_that_carries_a_secret_is_never_used(self):
        from runner import setup
        real = setup.hub.run

        def local_only(repo, *args):
            self.assertNotIn(args[0], ('ls-remote', 'clone', 'push', 'fetch'))
            return real(repo, *args)

        with mock.patch.object(setup.hub, 'run', local_only):
            found = self.check(repository='https://someone:a-token@example.com/team/repo.git')
        self.assertEqual(found['ok'], False)
        self.assertIn('carries a password or token', found['checks'][0]['fix'])

    @unittest.skipIf(os.geteuid() == 0, 'the superuser can write anywhere')
    def test_a_repository_that_can_only_be_read_says_so(self):
        remote = self.bare()
        remote.chmod(stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(remote.chmod, stat.S_IRWXU)
        found = self.check(repository=str(remote))
        self.assertEqual([item['ok'] for item in found['checks']], [True, False, True, True])
        self.assertIn('may read that repository but not write to it',
                      found['checks'][1]['fix'])

    def test_a_check_that_makes_no_sense_is_refused(self):
        folder = str(self.base / 'my-trainings')
        for sent, said in (
                ({}, "Give the repository's address, or a folder on this computer."),
                ({'path': folder, 'repository': str(self.base / 'team-repo.git')},
                 'not both'),
                ({'path': 'my-trainings'}, "Give the folder's whole path"),
                ({'path': folder, 'folder': 'two words'}, 'A workspace folder is letters'),
                ({'path': folder, 'branch': '-b'}, 'cannot be the name of a branch'),
                ({'repository': ['a', 'list']}, 'Give the repository as text.')):
            with self.subTest(sent=sent):
                self.assertIn(said, self.check(400, **sent)['error'])


class AgentTests(PageCase):
    def test_each_agent_says_whether_it_can_be_used_now(self):
        away = agents.Readiness('codex', True, None, False, '0.162', 'Codex is signed in but '
                                'cannot be used from this network. Try another network.')
        with mock.patch.object(self.engine.adapters['codex'], 'ready',
                               return_value=away) as looked:
            first = self.get('agents')
            self.assertEqual(self.get('agents'), first, 'a look is reused for a while')
            looked.assert_called_once_with()
        self.assertEqual(first, {'agents': [
            {'agent': 'claude', 'installed': True, 'signed_in': True, 'reachable': True,
             'version': 'scripted', 'problem': None},
            {'agent': 'codex', 'installed': True, 'signed_in': None, 'reachable': False,
             'version': '0.162', 'problem': away.problem}]})
        self.assertEqual(self.workers.jobs, [], 'looking starts no agent')

    def models(self, **given):
        """Codex's models, listed as `given` says, and counted."""
        return mock.patch.object(self.engine.adapters['codex'], 'models', create=True,
                                 **given)

    def test_each_agents_models_are_listed_when_asked_and_kept(self):
        with self.models(return_value=agents.offered(LISTED)) as listed:
            first = self.get('models', agent='codex')
            self.assertEqual(self.get('models', agent='codex'), first, 'a list is kept')
            listed.assert_called_once_with()
            with mock.patch.object(self.engines, 'MODELS_FOR', 0):
                self.assertEqual(self.get('models', agent='codex'), first)
            self.assertEqual(listed.call_count, 2, 'and asked for again once it is old')
        self.assertEqual(first, {'agent': 'codex', 'models': LISTED,
                                 'levels': ['low', 'medium', 'high'], 'source': None,
                                 'problem': None})
        self.assertEqual(self.workers.jobs, [], 'listing starts no agent')

    def test_a_list_that_cannot_be_made_says_why_and_is_asked_for_again_soon(self):
        late = WorkspaceError('Codex did not answer in 30 seconds.')
        with self.models(side_effect=late) as listed:
            said = self.get('models', agent='codex')
            self.assertEqual(self.get('models', agent='codex'), said)
            listed.assert_called_once_with()
        self.assertEqual(said, {'agent': 'codex', 'models': [], 'levels': [], 'source': None,
                                'problem': 'Codex did not answer in 30 seconds.'})
        with self.models(return_value=agents.offered(LISTED)), \
                mock.patch.object(self.engines, 'MODELS_MISSED', 0):
            self.assertEqual(self.get('models', agent='codex')['models'], LISTED)
        # An agent with no way to list them says so, as a list that could not be made.
        self.assertEqual(self.get('models', agent='claude')['problem'],
                         'scripted cannot list its models.')

    def test_listing_never_holds_up_the_rest_of_the_page(self):
        asked, release = [], threading.Event()

        def slow():
            asked.append(1)
            self.assertTrue(release.wait(20))
            return agents.offered(LISTED)

        found = []
        with self.models(side_effect=slow):
            waiting = [threading.Thread(target=lambda: found.append(
                self.get('models', agent='codex'))) for _ in range(2)]
            for thread in waiting:
                thread.start()
            while not asked:
                time.sleep(0.01)
            # While Codex is still listing, everything the page reads is answered.
            self.assertEqual(self.get('trainings'), {'trainings': [], 'needs': 0})
            self.assertTrue(self.get('setup')['configured'])
            self.assertEqual(self.get('models', agent='claude')['agent'], 'claude')
            release.set()
            for thread in waiting:
                thread.join(20)
        self.assertEqual((len(asked), len(found)), (1, 2), 'one listing, for both who asked')
        self.assertEqual(found[0], found[1])

    def test_models_are_asked_for_one_agent_this_runner_has(self):
        self.assertEqual(self.get('models', 400, agent='another')['error'],
                         'This runner has no agent called another.')
        self.assertEqual(self.get('models', 400)['error'], 'Give one agent.')

    def test_a_training_is_not_started_on_an_agent_that_cannot_be_used(self):
        away = agents.Readiness('claude', False, problem='Claude Code is not installed. '
                                'Install it and sign in, then try again.')
        with mock.patch.object(self.engine.adapters['claude'], 'ready', return_value=away):
            said = self.post('trainings', {**FORM, 'flow': 'desk'}, 409)
        self.assertEqual(said['error'], away.problem)
        self.assertEqual(self.get('trainings')['trainings'], [])


class StartTests(PageCase):
    def test_the_form_starts_a_desk_training(self):
        made = self.post('trainings', {**FORM, 'flow': 'desk', 'levels': ['101'],
                                       'materials': ['document']})
        root = self.space.training('rolling-restarts')
        self.assertEqual((made['path'], made['id'], made['gates']),
                         (str(root), 'rolling-restarts', 0))
        self.assertEqual(self.get('run', path=made['path'])['flow'], 'desk')
        self.assertNotIn('review_policy', self.record(root))

    def test_the_form_says_where_research_may_look(self):
        for scope, title in (('supplied-only', 'From documents'), ('both', 'From both')):
            with self.subTest(scope):
                path = self.saved_started(source_scope=scope, title=title)
                run = self.get('run', path=path)
                self.assertEqual((run['state'], run['documents']['waiting']),
                                 ('waiting', True))
        self.assertIsNone(self.get('run', path=self.saved_started())['documents'])
        self.assertEqual(len(self.workers.jobs), 1, 'only the last has started drafting')

    def test_a_form_with_no_deck_leaves_the_deck_out(self):
        without = Path(self.saved_started(deck_target=None))
        wanted = Path(self.saved_started(deck_target='pptx', title='Health checks'))
        self.assertEqual(('deck' in workspace.status(without)['settings']['stages'],
                          'deck' in workspace.status(wanted)['settings']['stages']),
                         (False, True))

    def test_a_form_that_makes_no_sense_starts_nothing(self):
        for changes, said in (
                ({'title': ''}, 'A training needs a title.'),
                ({'title': None}, 'A training needs a title.'),
                ({'topic': '  '}, 'A training needs a topic.'),
                ({'audience': None}, 'A training needs an audience.'),
                ({'purpose': None}, 'A training needs a purpose.'),
                ({'title': 'x' * 121}, 'Give the title as text of at most 120 characters.'),
                ({'time_limit': 30}, 'Give the time limit as text'),
                ({'levels': ['999']}, 'Levels are chosen from: 101, 201, 301, 401'),
                ({'levels': '101'}, 'Give levels as a list.'),
                ({'brief_kind': 'other'}, 'The brief kind is one of: product, competitive'),
                ({'deck_target': 'keynote'}, 'The deck target is one of: pptx, google'),
                ({'copies': ['pdf']}, 'Copies are any of: google, word; or none.'),
                ({'yoodli': 'yes'}, 'Say whether Yoodli scenarios are wanted'),
                ({'source_scope': 'everything'}, 'The source scope is one of: public-web, '
                 'supplied-only, both'),
                ({'agent': 'another'}, 'The agent is one of: claude, codex.'),
                ({'model': '--flag'}, 'The model is the short name'),
                ({'agent': 'claude', 'effort': 'ultra'}, 'The reasoning level is one of: low, '
                 'medium, high, xhigh, max,'),
                ({'effort': 'warp'}, 'The reasoning level is one of: none, minimal,'),
                ({'agent': 'claude', 'model': 'claude-opus-4-6', 'effort': 'xhigh'},
                 'Opus 4.6 takes one of these reasoning levels: low, medium, high, max,')):
            with self.subTest(changes=changes):
                self.assertIn(said, self.post('trainings', {**FORM, 'flow': 'desk', **changes}, 400)['error'])
        self.assertEqual((self.get('trainings')['trainings'], self.workers.jobs), ([], []))
        self.assertFalse(self.space.training('rolling-restarts').exists())

    def test_the_workspace_cannot_be_moved_while_a_training_is_working_in_it(self):
        seen = []

        def looks(tools, job):
            seen.append(self.post('setup', {'path': str(self.base / 'elsewhere')}, 409))
            seen.append(self.post('setup', {'limits': {'parallel': 3}}))
            self.workers.research_plan(tools, job)

        self.workers.then('research-plan', looks)
        path = self.saved_started()
        self.assertEqual(seen[0]['error'], 'Trainings are working in the workspace this '
                         'computer uses now. Pause or stop them before moving to another.')
        self.assertEqual((seen[1]['limits']['parallel'], seen[1]['workspace']['path']),
                         (3, str(self.space.repo)))
        self.assertFalse((self.base / 'elsewhere').exists())
        self.assertEqual((self.get('run', path=path)['state'], len(self.workers.jobs)),
                         ('waiting', 1))

    def test_a_second_training_with_the_same_title_is_refused(self):
        self.saved_started()
        said = self.post('trainings', {**FORM, 'flow': 'desk'}, 409)
        self.assertIn('already has a training in trainings/rolling-restarts', said['error'])


class Keeper:
    """A stand-in for what looks after the skills here: it records what it is asked."""

    def __init__(self):
        self.asked, self.refuse = [], None

    def report(self) -> dict:
        return {'stand_in': True}

    def again(self) -> None:
        self.asked.append('again')

    def close(self) -> None:
        pass

    def update(self, working: bool) -> dict:
        self.asked.append(('update', working))
        if self.refuse:
            raise WorkspaceError(self.refuse)
        return {'stand_in': True, 'update': {'state': 'running'}}

    def upgrade(self, working: bool, version: str) -> dict:
        self.asked.append(('upgrade', working, version))
        if self.refuse:
            raise WorkspaceError(self.refuse)
        return {'stand_in': True}

    def restart(self, working: bool) -> dict:
        self.asked.append(('restart', working))
        return {'stand_in': True}

    def dismiss(self, key: str) -> dict:
        self.asked.append(('dismiss', key))
        return {'stand_in': True}

    def install_brand(self, working: bool, release: str) -> dict:
        self.asked.append(('install_brand', working, release))
        if self.refuse:
            raise WorkspaceError(self.refuse)
        return {'stand_in': True}

    def remember_brand(self, repository: str, listed: dict) -> None:
        self.asked.append(('remember_brand', repository, sorted(listed)))


class UpkeepTests(PageCase):
    """What the runner found of Training Studio and its skills, and the update of the
    companions, which the page asks for only once the person has said yes."""

    def test_set_up_and_status_say_what_was_found_of_the_skills(self):
        self.assertEqual((self.get('setup')['upkeep'], self.get('setup')['updates'],
                          self.get('status')['upkeep']), (None, {'look': True}, None))
        self.engine.upkeep = Keeper()
        self.assertEqual((self.get('setup')['upkeep'], self.get('status')['upkeep']),
                         ({'stand_in': True}, {'stand_in': True}))

    def test_looking_for_updates_is_switched_in_set_up(self):
        self.assertEqual(self.post('setup', {'look_for_updates': False})['updates'],
                         {'look': False})
        self.assertFalse(settings.load().look_for_updates)
        self.assertEqual(self.post('setup', {'limits': {'parallel': 3}})['updates'],
                         {'look': False}, 'a change to anything else leaves it as it was')
        said = self.post('setup', {'look_for_updates': 'yes'}, 400)
        self.assertEqual(said['error'], 'Looking for updates is on or off: give '
                         'look_for_updates as true or false.')
        self.assertTrue(self.post('setup', {'look_for_updates': True})['updates']['look'])

    def test_the_companions_are_brought_only_when_asked_and_not_under_a_working_training(self):
        said = self.post('companions', {}, 409)
        self.assertIn('does not look after the skills on this computer', said['error'])
        keeper = self.engine.upkeep = Keeper()
        self.assertEqual(self.post('companions', {}),
                         {'upkeep': {'stand_in': True, 'update': {'state': 'running'}}})
        keeper.refuse = 'Every companion skill is already as new as this Training Studio ' \
                        'was made with.'
        self.assertEqual(self.post('companions', {}, 409)['error'], keeper.refuse)
        keeper.refuse, seen = None, []

        def looks(tools, job):
            seen.append(self.post('companions', {}))
            self.workers.research_plan(tools, job)

        self.workers.then('research-plan', looks)
        self.saved_started()
        self.assertEqual(keeper.asked, [('update', False), ('update', False),
                                        ('update', True)],
                         'a training working in the background is said to be working')

    def test_upgrading_restarting_and_dismissing_are_asked_of_what_looks_after_the_skills(self):
        for endpoint, sent in (('upgrade', {'version': '99.0.0'}), ('restart', {}),
                               ('versions', {'dismiss': 'training-studio 99.0.0'})):
            self.assertIn('does not look after the skills on this computer',
                          self.post(endpoint, sent, 409)['error'])
        keeper = self.engine.upkeep = Keeper()
        self.assertEqual(self.post('upgrade', {}, 400)['error'], 'Give version as text.')
        self.assertEqual(self.post('versions', {'dismiss': 3}, 400)['error'],
                         'Give dismiss as text.')
        for endpoint, sent in (('upgrade', {'version': '99.0.0'}), ('restart', {}),
                               ('versions', {'dismiss': 'training-studio 99.0.0'})):
            self.assertEqual(self.post(endpoint, sent), {'upkeep': {'stand_in': True}})
        keeper.refuse = 'A training on this computer is working now.'
        self.assertEqual(self.post('upgrade', {'version': '99.0.0'}, 409)['error'],
                         keeper.refuse)
        keeper.refuse, seen = None, []

        def looks(tools, job):
            seen.append(self.post('upgrade', {'version': '99.0.0'}))
            seen.append(self.post('restart', {}))
            self.workers.research_plan(tools, job)

        self.workers.then('research-plan', looks)
        self.saved_started()
        self.assertEqual(keeper.asked, [
            ('upgrade', False, '99.0.0'), ('restart', False),
            ('dismiss', 'training-studio 99.0.0'), ('upgrade', False, '99.0.0'),
            ('upgrade', True, '99.0.0'), ('restart', True)],
            'a training working in the background is said to be working')

    def test_the_brand_skills_repository_is_kept_once_it_can_be_read(self):
        work, bare = self.base / 'brand-work', self.base / 'brand.git'
        for args in (('init', '-q', str(work)), ('init', '-q', '--bare', str(bare))):
            subprocess.run(['git', *args], cwd=self.base, check=True, capture_output=True)
        (work / 'SKILL.md').write_text('---\nname: acme-brand\n---\n')
        for args in (('add', '-A'), ('commit', '-q', '-m', 'Release'), ('tag', 'v1.2.0'),
                     ('tag', 'v2026.1.0'), ('push', '-q', '--tags', str(bare), 'HEAD:main')):
            subprocess.run(['git', '-c', 'user.name=A Test', '-c', 'user.email=t@example.com',
                            *args], cwd=work, check=True, capture_output=True)
        keeper = self.engine.upkeep = Keeper()
        said = self.post('brand', {'repository': str(self.base / 'nowhere.git')}, 400)
        self.assertTrue(said['error'].startswith("The brand skill's repository could not be "
                                                 'read. It was not found ('), said['error'])
        self.assertEqual(self.post('brand', {'repository': str(bare), 'release': 'v9.0.0'},
                                   400)['error'],
                         f'{bare} has no release v9.0.0. Its newest is v1.2.0. Leave the '
                         'release empty for the newest.')
        self.assertEqual(self.post('brand', {'release': 'v1.2.0'}, 400)['error'],
                         "A release is chosen from the brand skill's repository: give the "
                         'repository too.')
        self.assertIsNone(settings.load().brand_repository, 'nothing was kept')
        made = self.post('brand', {'repository': str(bare), 'release': '1.2.0'})
        self.assertEqual((made['brand']['repository'], made['brand']['release']),
                         (str(bare), 'v1.2.0'))
        self.assertEqual((settings.load().brand_repository, settings.load().brand_release),
                         (str(bare), 'v1.2.0'))
        # It is kept for every studio, in the file they share, and nowhere else.
        self.assertEqual(json.loads(Path(os.environ['STUDIOS_CONFIG']).read_text())['brand'],
                         {'repository': str(bare), 'release': 'v1.2.0'})
        self.assertNotIn('brand_repository', json.loads(settings.path().read_text()))
        self.assertEqual(keeper.asked, [('remember_brand', str(bare), ['v1.2.0',
                                                                       'v2026.1.0'])])
        self.assertEqual(self.post('setup', {'limits': {'parallel': 3}})['brand']['repository'],
                         str(bare), 'a change to anything else leaves it as it was')
        cleared = self.post('brand', {'repository': ''})
        self.assertEqual((cleared['brand']['repository'], cleared['brand']['release']),
                         (None, None))

    def test_the_brand_skill_is_installed_only_when_asked_and_not_under_a_working_training(self):
        self.assertIn('does not look after the skills on this computer',
                      self.post('brand/install', {'release': 'v1.2.0'}, 409)['error'])
        keeper = self.engine.upkeep = Keeper()
        self.assertEqual(self.post('brand/install', {}, 400)['error'],
                         'Give release as text.')
        self.assertEqual(self.post('brand/install', {'release': 'v1.2.0'}),
                         {'upkeep': {'stand_in': True}})
        keeper.refuse = 'The brand skill is being installed already.'
        self.assertEqual(self.post('brand/install', {'release': 'v1.2.0'}, 409)['error'],
                         keeper.refuse)
        keeper.refuse, seen = None, []

        def looks(tools, job):
            seen.append(self.post('brand/install', {'release': 'v1.2.0'}))
            self.workers.research_plan(tools, job)

        self.workers.then('research-plan', looks)
        self.saved_started()
        self.assertEqual(keeper.asked, [('install_brand', False, 'v1.2.0'),
                                        ('install_brand', False, 'v1.2.0'),
                                        ('install_brand', True, 'v1.2.0')],
                         'a training working in the background is said to be working')

    def test_checking_this_computer_again_looks_at_the_skills_again(self):
        keeper = self.engine.upkeep = Keeper()
        seen = {'checked_at': '2026-10-14T09:00:00Z', 'ready': True, 'assistants': ['Codex'],
                'wrong': [], 'items': []}
        with mock.patch.object(computer, 'check', lambda google=False: seen):
            self.get('computer')
            self.assertEqual(keeper.asked, [], 'reading the last look looks at nothing')
            self.post('computer', {})
        self.assertEqual(keeper.asked, ['again'])


class WholeUpgradeTests(PageCase):
    """An older Training Studio, installed into a temporary home, upgraded through the page
    to the newer one its repository has. The repository is a local bare one holding the
    parts of this checkout an install needs, at a higher version. Nothing is fetched from
    anywhere else, and the home is the test's own."""

    PARTS = ('skills/training-studio', 'runner', 'installer', 'bootstrap', 'guidance')

    def git(self, cwd: Path, *args: str) -> str:
        return subprocess.run(['git', '-c', 'user.name=A Test', '-c',
                               'user.email=test@example.com', *args], cwd=cwd, check=True,
                              capture_output=True, text=True).stdout.strip()

    def repository(self, version: str) -> Path:
        """Training Studio's repository, released at `version`, with a tag and on main."""
        work, bare = self.base / 'training-studio-work', self.base / 'training-studio.git'
        for part in self.PARTS:
            shutil.copytree(helpers.REPO / part, work / part,
                            ignore=shutil.ignore_patterns('__pycache__'))
        (work / 'skills' / 'training-studio' / 'VERSION').write_text(f'{version}\n')
        self.git(self.base, 'init', '-q', '-b', 'main', str(work))
        self.git(work, 'add', '-A')
        self.git(work, 'commit', '-q', '-m', f'Release {version}')
        self.git(work, 'tag', f'v{version}')
        self.git(self.base, 'init', '-q', '--bare', str(bare))
        self.git(work, 'push', '-q', '--tags', str(bare), 'main')
        return bare

    def test_an_older_install_is_upgraded_from_the_page_and_asks_for_a_restart(self):
        from test_installer import install
        from runner import upkeep
        home_dir = self.base / 'home'
        (home_dir / '.claude' / 'skills').mkdir(parents=True)
        root = home_dir / '.local' / 'share' / 'training-studio'
        older = self.base / 'older'
        shutil.copytree(helpers.SKILL, older, ignore=shutil.ignore_patterns('__pycache__'))
        (older / 'VERSION').write_text('0.1.0\n')
        printed = io.StringIO()
        with mock.patch.object(install, 'PLATFORM', 'linux'), \
                mock.patch.object(install, 'prerequisites', lambda *a, **k: {'notes': []}), \
                contextlib.redirect_stdout(printed):
            self.assertEqual(install.main(['install', '--yes', '--companions', 'skip', '--json',
                                           '--home', str(home_dir), '--source', str(older)]),
                             0, printed.getvalue())
        first = json.loads(printed.getvalue())['version']
        running = root / 'versions' / first
        source = self.repository('99.0.0')
        with mock.patch.dict(os.environ, {'TRAINING_STUDIO_SOURCE': str(source),
                                          'HOME': str(home_dir), 'PATH': '/usr/bin:/bin'}):
            keep = self.engine.upkeep = upkeep.Upkeep(
                home_dir=home_dir, root=root, installer=running / 'installer' / 'install.py')
            keep.check()
            # The installed copy pins its companions to their public repositories: only
            # Training Studio's own, the local one, is asked, so nothing leaves this computer.
            own = {upkeep.SELF: keep.repositories()[upkeep.SELF]}
            with mock.patch.object(keep, 'repositories', return_value=own):
                self.assertTrue(keep.look())
            versions = self.get('setup')['upkeep']['versions']
            own = versions['rows'][0]
            self.assertEqual((own['installed'], own['newest'], own['state']),
                             ('0.1.0', '99.0.0', 'update'))
            self.assertTrue(versions['upgrade']['offered'])
            self.assertEqual(self.post('upgrade', {'version': '98.0.0'}, 409)['error'],
                             'The newest Training Studio is now 99.0.0, not 98.0.0. Look at it '
                             'again before you upgrade.')
            shown = self.post('upgrade', {'version': '99.0.0'})['upkeep']['versions']
            # Running, unless it was quick enough to have finished already.
            self.assertIn(shown['upgrade']['state'], ('running', 'restart'))
            for thread in list(keep._threads):
                thread.join(300)
            upgrade = self.get('setup')['upkeep']['versions']['upgrade']
            self.assertEqual((upgrade['state'], upgrade['restart']), ('restart', True),
                             upgrade['says'])
            self.assertEqual(upgrade['says'], 'Training Studio 99.0.0 is installed, checked '
                             'and in place. Restart to use it. This page comes back by itself.')
            current = Path(os.readlink(root / 'current'))
            self.assertTrue(current.name.startswith('99.0.0-'))
            self.assertEqual((current / 'VERSION').read_text().strip(), '99.0.0')
            self.assertTrue((running / 'runner' / 'studio.py').is_file(),
                            'the version this runner runs from is left whole')
            state = install.read_state(root)
            self.assertEqual(state['history'], [first, current.name])
            self.assertEqual(os.readlink(home_dir / '.claude' / 'skills' / 'training-studio'),
                             str(root / 'current'))
            self.assertFalse((home_dir / '.agents').exists(), 'only the assistant it had')
            self.assertTrue(install.ours(root / 'studio'))
            self.assertEqual(list(root.glob('*.pending*')), [])

            left = []
            keep.leave = lambda: left.append('left')
            restarted = self.post('restart', {})['upkeep']['versions']['upgrade']
        self.assertEqual(restarted['state'], 'restarting')
        self.assertEqual((keep.restarting, left),
                         (['/bin/sh', str(root / 'studio'), 'serve'], ['left']))


class CombinedReviewTests(PageCase):
    def test_combined_reviews_have_beads(self):
        path = self.saved_started(review_level='balanced')
        self.decide(Path(path), 'research-plan')
        stages = self.get('training', path=path)['stages']
        by_name = {item['stage']: item for item in stages}
        names = list(by_name)
        self.assertEqual(by_name['review:direction']['state'], 'review')
        self.assertEqual(by_name['review:final']['state'], 'not-started')
        self.assertEqual(names[names.index('brief') + 1], 'review:direction')
        self.assertEqual(names[names.index('package') - 1], 'review:final')
        plain = self.saved_started(title='Plain', review_level='step_by_step')
        self.assertFalse(any(item['stage'].startswith('review:')
                             for item in self.get('training', path=plain)['stages']))

    def test_grouped_reviews_are_revision_bound_over_the_authenticated_page(self):
        from studio_core import review_policy
        with mock.patch.object(review_policy, 'capture', return_value={'schema': 1, 'level': 'balanced'}):
            path = self.saved_started()
        run = self.get('run', path=path)
        self.assertEqual((run['state'], run['review'], run['review_level']), ('waiting', None, 'balanced'))
        shown = self.get('gate', path=path, artifact='research-plan')
        self.assertEqual((shown['waiting'], shown['decisions'][0]), (True, 'approve'))
        self.post('decide', {'path': path, 'artifact': 'research-plan', 'decision': 'approve',
                             'seen': shown['sha256']})
        run = self.get('run', path=path)
        self.assertEqual(run['review']['phase'], 'direction')
        self.post('review', {'path': path, 'expected': 'old-version', 'decision': 'approve'}, expect=409)
        run = self.post('review', {'path': path, 'expected': run['review']['expected'], 'decision': 'approve'})
        self.assertEqual(run['review']['phase'], 'final')
        run = self.post('review', {'path': path, 'expected': run['review']['expected'], 'decision': 'approve'})
        self.assertEqual(run['state'], 'done')


class RunTests(PageCase):
    def test_a_run_is_described_field_for_field(self):
        self.workers.cost = 0.5
        run = self.get('run', path=self.saved_started())
        self.assertEqual(sorted(run), RUN_KEYS)
        self.assertEqual((run['state'], run['agent'], run['model'], run['effort'],
                          run['workers'], run['question'], run['problem']),
                         ('waiting', 'claude', None, None, [], None, None))
        self.assertEqual(run['spent'], {'dollars': 0.5, 'tokens': 1200, 'stops_at': 20.0})
        self.assertIsInstance(run['sentence'], str)
        for step in run['steps']:
            self.assertEqual(sorted(step), STEP_KEYS)
            self.assertIn(step['kind'], ('code', 'agent', 'gate'))
            self.assertIn(step['status'], ('done', 'working', 'waiting', 'failed', 'to-do'))
            self.assertIsInstance(step['attempts'], int)
        self.assertEqual(run['steps'][1], {
            'id': 'research-plan', 'label': 'Draft the research plan', 'kind': 'agent',
            'status': 'done', 'attempts': 1, 'seconds': 1.5, 'dollars': 0.5, 'error': None})

    def test_a_question_and_a_problem_are_described_field_for_field(self):
        self.workers.then('research-plan', asks('Which platform is this about?'))
        asking = self.get('run', path=self.saved_started())
        self.assertEqual(sorted(asking['question']), ['from', 'id', 'text'])
        self.workers.then('research-plan', fails(), fails(), fails())
        failing = self.get('run', path=self.saved_started(title='Health checks'))
        self.assertEqual(sorted(failing['problem']), ['action', 'kept', 'label', 'what'])
        self.assertEqual((failing['state'], failing['problem']['action'],
                          failing['problem']['label']), ('failed', 'retry', 'Try again'))

    def test_a_run_is_shown_only_for_a_training_a_run_is_driving(self):
        said = self.get('run', 400)
        self.assertEqual(said['error'], 'Give one path.')
        said = self.get('run', 403, path=str(self.base / 'elsewhere'))
        self.assertEqual(said['error'], 'That folder is not a training this computer knows.')
        chat = self.base / 'started-in-a-chat'
        chat.mkdir()
        workspace.init(chat, 'Started in a chat')
        home.remember(chat, 'Started in a chat', [])
        said = self.get('run', 404, path=str(chat))
        self.assertEqual(said['error'], 'No run is driving this training.')
        for sent in ({'path': str(chat), 'action': 'pause'},):
            self.assertEqual(self.post('run', sent, 404)['error'],
                             'No run is driving this training.')
        self.assertEqual(self.post('answer', {'path': str(chat), 'id': 'x', 'answer': 'Yes.'},
                                   404)['error'], 'No run is driving this training.')

    def test_a_run_can_be_paused_resumed_stopped_and_tried_again(self):
        path, paused = str(self.space.training('rolling-restarts')), []

        def pauses(tools, job):
            paused.append(self.post('run', {'path': path, 'action': 'pause'}))
            self.workers.research_plan(tools, job)

        self.workers.then('research-plan', pauses)
        self.assertEqual(self.saved_started(), path)
        self.assertEqual((sorted(paused[0]), paused[0]['state'], paused[0]['workers'][0]['id']),
                         (RUN_KEYS, 'paused', 'research-plan'))
        self.assertEqual(self.get('run', path=path)['state'], 'paused')
        self.assertEqual(self.post('run', {'path': path, 'action': 'resume'})['state'],
                         'waiting')
        self.assertEqual(self.post('run', {'path': path, 'action': 'stop'})['state'],
                         'stopped')
        self.assertEqual(self.post('run', {'path': path, 'action': 'resume'})['state'],
                         'waiting')
        self.workers.then('research-plan', fails(), fails(), fails())
        failed = self.saved_started(title='Health checks')
        self.assertEqual(self.get('run', path=failed)['state'], 'failed')
        again = self.post('run', {'path': failed, 'action': 'retry'})
        self.assertEqual((again['state'], again['problem']), ('waiting', None))

    def test_what_a_run_cannot_be_asked_is_refused_in_a_sentence(self):
        path = self.saved_started()
        for sent, expect, said in (
                ({'path': path, 'action': 'restart'}, 400,
                 'A run can be asked to: pause, resume, stop, retry, finish-level, more-time.'),
                ({'path': path}, 400, 'Give action as text.'),
                ({'action': 'pause'}, 400, 'Give path as text.'),
                ({'path': path, 'action': 'pause'}, 409, 'Only a training that is working '
                 'can be paused. This one is waiting for you.'),
                ({'path': path, 'action': 'resume'}, 409, 'This training is not paused or '
                 'stopped, so there is nothing to resume.'),
                ({'path': path, 'action': 'retry'}, 409, 'Nothing here failed, so there is '
                 'nothing to try again.'),
                ({'path': str(self.base / 'elsewhere'), 'action': 'pause'}, 403,
                 'That folder is not a training this computer knows.')):
            with self.subTest(sent=sent):
                self.assertEqual(self.post('run', sent, expect)['error'], said)
        self.assertEqual(self.get('run', path=path)['state'], 'waiting')

    def test_a_workers_question_is_answered_on_the_page(self):
        self.workers.then('research-plan', asks('Which platform is this about?'))
        path = self.saved_started()
        asked = self.get('run', path=path)['question']
        for sent, expect, said in (
                ({'path': path, 'id': asked['id'], 'answer': ''}, 400, 'Give answer as text.'),
                ({'path': path, 'id': asked['id'], 'answer': '  \n'}, 400,
                 'Write an answer first.'),
                ({'path': path, 'answer': 'The public one.'}, 400, 'Give id as text.'),
                ({'path': path, 'id': 'another', 'answer': 'The public one.'}, 409,
                 'That question is not waiting for an answer any more.')):
            with self.subTest(sent=sent):
                self.assertEqual(self.post('answer', sent, expect)['error'], said)
        self.assertEqual(len(self.workers.jobs), 1)
        after = self.post('answer', {'path': path, 'id': asked['id'],
                                     'answer': 'The public one.'})
        self.assertEqual((sorted(after), after['state'], after['question']),
                         (RUN_KEYS, 'waiting', None))
        self.assertIn('Answer: The public one.', self.workers.jobs[-1][1].task)

    def test_a_note_for_the_next_step_is_sent_on_the_page(self):
        path = self.saved_started()
        self.assertEqual(self.get('run', path=path)['note'],
                         {'pending': None, 'used': [], 'expected': '0'})
        self.assertEqual(self.post('note', {'path': path, 'text': 'Keep it short.'}, 400)['error'],
                         'Give expected as text.')
        self.assertEqual(self.post('note', {'path': path, 'expected': '0', 'text': ' '}, 409)['error'],
                         'Write the note first.')
        noted = self.post('note', {'path': path, 'expected': '0', 'text': 'Keep it short.'})
        self.assertEqual((sorted(noted), noted['note']['pending']['text'], noted['note']['expected']),
                         (RUN_KEYS, 'Keep it short.', '1'))
        self.assertIn('The note changed', self.post('note', {
            'path': path, 'expected': '0', 'text': 'Lead with the risks.'}, 409)['error'])
        self.assertEqual(self.post('note', {'path': path, 'expected': '1',
                                            'text': 'Lead with the risks.'})['note']['pending']['text'],
                         'Lead with the risks.')

    def test_sharing_says_whether_the_work_is_shared(self):
        said = self.post('share', {})
        self.assertEqual((sorted(said), said['shared']), (['notice', 'shared'], False))
        self.assertIn('no shared repository', said['notice'])


STOPPED = ('Stopped. Everything finished before it is kept; the step that was in hand '
           'starts over on resume.')


class ListTests(PageCase):
    """What milestone 1's lists gain."""

    def chat(self) -> Path:
        root = self.base / 'started-in-a-chat'
        root.mkdir()
        workspace.init(root, 'Started in a chat')
        home.remember(root, 'Started in a chat', [])
        return root

    def listed(self) -> dict:
        return {item['title']: item for item in self.get('trainings')['trainings']}

    def test_each_training_carries_its_run_or_none(self):
        path, chat = self.saved_started(), self.chat()
        listed = self.listed()
        self.assertEqual(listed['Rolling restarts']['run'], {
            'state': 'waiting', 'sentence': 'The research plan is waiting for your review.',
            'can_migrate_desk': True})
        self.assertIsNone(listed['Started in a chat']['run'])
        self.assertEqual(self.get('training', path=path)['run'],
                         listed['Rolling restarts']['run'])
        self.assertIsNone(self.get('training', path=str(chat))['run'])
        gate = listed['Rolling restarts']
        self.assertEqual((gate['state'], gate['waiting']['artifact'], gate['approval']),
                         ('needs-you', 'research-plan', 'page'))
        self.assertEqual(self.get('trainings')['needs'], 1)

    def test_list_and_detail_keep_desk_navigation_for_finished_and_desk_runs(self):
        path = self.saved_started()
        brief = self.engine.brief(path)
        for state, flow, can_open in (('done', None, True), ('done', None, False),
                                      ('working', 'desk', False)):
            with self.subTest(state=state, flow=flow, can_open=can_open):
                changed = {**brief, 'state': state, 'flow': flow, 'can_open_desk': can_open}
                with mock.patch.object(self.engine, 'brief', return_value=changed):
                    listed = self.listed()['Rolling restarts']['run']
                    detail = self.get('training', path=path)['run']
                self.assertEqual(listed, {'state': state, 'sentence': brief['sentence'],
                                          'flow': flow, 'can_open_desk': can_open})
                self.assertEqual(detail, listed)

    def test_a_run_with_a_question_counts_as_needing_the_person(self):
        self.workers.then('research-plan', asks('Which platform is this about?'))
        path = self.saved_started()
        found = self.get('trainings')
        item = found['trainings'][0]
        self.assertEqual((found['needs'], item['state'], item['sentence']), (
            1, 'needs-you', 'A question is waiting for you: Which platform is this about?'))
        self.assertEqual(item['waiting'], {'artifact': None, 'label': None, 'recorded': False,
                                           'question': 'Which platform is this about?'})
        self.assertEqual(item['run']['state'], 'waiting')
        detail = self.get('training', path=path)
        self.assertEqual((detail['state'], detail['run']), ('needs-you', item['run']))
        self.assertEqual(desk.next_up(self.page.trainings()), {
            'path': path, 'title': 'Rolling restarts', 'artifact': None,
            'sentence': item['sentence']})

    def test_a_run_with_a_problem_counts_as_needing_the_person(self):
        self.workers.then('research-plan', fails(), fails(), fails())
        self.saved_started()
        found = self.get('trainings')
        item = found['trainings'][0]
        self.assertEqual((found['needs'], item['state'], item['run']['state']),
                         (1, 'needs-you', 'failed'))
        self.assertTrue(item['sentence'].startswith('This step did not work in 3 tries'))
        self.assertEqual(item['waiting']['question'], None)

    def test_a_run_that_is_only_halted_does_not_need_the_person(self):
        path = self.saved_started()
        self.post('run', {'path': path, 'action': 'stop'})
        self.post('decide', {'path': path, 'artifact': 'research-plan', 'decision': 'approve',
                             'seen': workspace.sha256_file(Path(path) / pipeline.PLAN)})
        found = self.get('trainings')
        item = found['trainings'][0]
        self.assertEqual((found['needs'], item['state'], item['run'], item['sentence']), (
            0, 'in-progress', {'state': 'stopped', 'sentence': STOPPED, 'can_migrate_desk': True}, STOPPED))

    def test_reading_never_starts_or_wakes_a_run(self):
        self.workers.then('research-plan', fails(), fails(), fails(), asks('Which platform?'))
        failed = self.saved_started()
        asking = self.saved_started(title='Health checks')
        chat = self.chat()
        before, jobs = self.on_disk(), len(self.workers.jobs)
        for _ in range(3):
            self.get('trainings')
            for path in (failed, asking):
                self.get('run', path=path)
                self.get('training', path=path)
            self.get('training', path=str(chat))
            self.get('setup')
            self.get('capabilities')
        self.assertEqual((self.on_disk(), len(self.workers.jobs)), (before, jobs))
        self.assertEqual([self.get('run', path=path)['state'] for path in (failed, asking)],
                         ['failed', 'waiting'])


class DecideTests(PageCase):
    def approve(self, path: str, name: str, expect: int = 200) -> dict:
        root = Path(path)
        file = root / workspace.artifact(root, workspace.load(root), name)['file']
        return self.post('decide', {'path': path, 'artifact': name, 'decision': 'approve',
                                    'seen': workspace.sha256_file(file)}, expect)

    def test_the_last_approval_says_the_training_is_finished_and_says_approved_once(self):
        path = self.saved_started()
        for name in ('research-plan', 'research', 'blueprint', 'document', 'brief'):
            self.approve(path, name)
        said = self.approve(path, 'scenario:main')
        self.assertEqual(said['said'], 'Approved. This training is finished, with 1 thing '
                         'left out or limited.')
        self.assertIsNone(said['next'])
        self.assertEqual(self.get('run', path=path)['state'], 'done')

    def test_the_last_approval_before_the_deck_says_the_deck_is_all_that_is_left(self):
        path = self.saved_started(deck_target='pptx')
        for name in ('research-plan', 'research', 'blueprint', 'document', 'brief'):
            self.approve(path, name)
        said = self.approve(path, 'scenario:main')
        self.assertEqual(said['said'], f'Approved. {left(pipeline.DECK_LEFT)}')
        run = self.get('run', path=path)
        self.assertEqual((run['state'], run['deck_left']), (
            'done', {'says': left(pipeline.DECK_LEFT), 'artifact': 'deck'}))
        item = self.get('trainings')['trainings'][0]
        self.assertEqual((item['state'], item['run']['state'], item['sentence']),
                         ('in-progress', 'done', left(pipeline.DECK_LEFT)))
        open_stages = [stage['stage'] for stage in item['stages']
                       if stage['state'] not in ('done', 'left-out')]
        self.assertEqual(open_stages, ['deck', 'package'],
                         'the deck is the only stage left besides the wrap-up')
        said = self.post('decide', {'path': path, 'artifact': run['deck_left']['artifact'],
                                    'decision': 'skip', 'note': 'No slides for this one.'})
        self.assertEqual(said['said'], 'This stage is left out. You can bring it back from '
                         'the training at any time. This training is finished, with 1 thing '
                         'left out or limited.')
        item = self.get('trainings')['trainings'][0]
        self.assertEqual((item['state'], item['run']['state']), ('finished', 'done'))
        self.assertEqual(self.get('run', path=path)['finished']['index'], 'README.md')

    def test_a_decision_made_through_the_desks_own_address_wakes_the_run(self):
        path = self.saved_started()
        gate = self.get('gate', path=path, artifact='research-plan')
        self.assertEqual((gate['waiting'], gate['decisions'][0], gate['question']),
                         (True, 'approve', 'Approve the research plan?'))
        self.assertIn('Checked for you: 1 check passed.', gate['review'])
        said = self.approve(path, 'research-plan')
        self.assertEqual(said['decided']['by'], 'page')
        self.assertEqual(said['said'],
                         'Approved. The research report is waiting for your review.')
        for word in ('assistant', 'conversation'):
            self.assertNotIn(word, said['said'])
        self.assertEqual(said['next'], {
            'path': path, 'title': 'Rolling restarts', 'artifact': 'research',
            'sentence': 'The research report is waiting for your review.'})
        self.assertEqual(len(self.workers.of('question')), 4)
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertIn('Rolling restarts: The research plan was approved on the page.',
                      self.log())

    def test_a_decision_the_desk_refuses_changes_nothing_and_wakes_nothing(self):
        path = self.saved_started()
        before = self.on_disk()
        said = self.post('decide', {'path': path, 'artifact': 'research-plan',
                                    'decision': 'approve', 'seen': 'another-version'}, 409)
        self.assertIn('has changed since it was opened', said['error'])
        self.post('decide', {'path': path, 'artifact': 'research-plan',
                             'decision': 'revise'}, 409)
        self.assertEqual((self.on_disk(), len(self.workers.jobs)), (before, 1))

    def test_a_training_no_run_is_driving_is_decided_as_the_desk_always_did(self):
        chat = self.base / 'started-in-a-chat'
        chat.mkdir()
        workspace.init(chat, 'Started in a chat', approval='page')
        home.remember(chat, 'Started in a chat', [])
        said = self.post('decide', {'path': str(chat), 'artifact': 'deck', 'decision': 'skip',
                                    'note': 'No slides.'})
        self.assertEqual(said['said'], f"{desk.SAID['skip']} {desk.BACK_TO_CHAT}")
        self.assertEqual(self.post('approval', {'path': str(chat), 'mode': 'chat'}),
                         {'approval': 'chat'})

    def test_decisions_cannot_be_moved_to_a_conversation_while_a_run_is_driving(self):
        path = self.saved_started()
        said = self.post('approval', {'path': path, 'mode': 'chat'}, 409)
        self.assertEqual(said['error'], 'The runner is driving this training, so its '
                         'decisions are made on the page.')
        self.assertEqual(workspace.status(Path(path))['approval'], 'page')
        self.assertEqual(self.post('approval', {'path': path, 'mode': 'page'}),
                         {'approval': 'page'})
        self.to_end(Path(path))
        self.assertEqual(self.get('run', path=path)['state'], 'done')
        self.assertEqual(self.post('approval', {'path': path, 'mode': 'chat'}),
                         {'approval': 'chat'})
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertEqual(self.log()[-1],
                         'Rolling restarts: decisions are now made in the conversation')


class LaterTests(PageCase):
    """What milestone 3 adds: the person's documents, the copies, what a gate gains, and
    the index read as a file."""

    def sent(self, text: str = 'Capacity holds only when more than one instance is '
             'running.\n') -> str:
        return base64.b64encode(text.encode('utf-8')).decode('ascii')

    def test_documents_are_added_removed_and_settled_on_the_page(self):
        path = self.saved_started(source_scope='supplied-only')
        run = self.post('documents', {'path': path, 'action': 'add', 'name': 'handbook.txt',
                                      'content': self.sent()})
        self.assertEqual(sorted(run), RUN_KEYS)
        self.assertEqual(sorted(run['documents']),
                         ['added', 'limits', 'note', 'types', 'waiting'])
        self.assertEqual(run['documents']['added'], [
            {'name': 'handbook.txt', 'bytes': 60, 'readable': True, 'problem': None}])
        self.assertEqual((run['documents']['types'][1], run['documents']['limits']),
                         ('.md', {'bytes': 8_000_000, 'files': 40}))
        self.post('documents', {'path': path, 'action': 'add', 'name': 'notes.md',
                                'content': self.sent('Notes.\n')})
        run = self.post('documents', {'path': path, 'action': 'remove', 'name': 'notes.md'})
        self.assertEqual([entry['name'] for entry in run['documents']['added']],
                         ['handbook.txt'])
        item = self.get('trainings')['trainings'][0]
        self.assertEqual((item['state'], item['run']['state'], self.get('trainings')['needs']),
                         ('needs-you', 'waiting', 1),
                         'a run that waits for documents needs its person')
        self.assertEqual(self.workers.jobs, [])
        run = self.post('documents', {'path': path, 'action': 'done'})
        self.assertEqual((run['documents']['waiting'], run['documents']['added'][0]['name'],
                          len(self.workers.jobs)), (False, 'handbook.txt', 1))
        self.assertEqual(self.get('run', path=path)['documents']['waiting'], False,
                         'the documents stay shown once they are settled')

    def test_what_makes_no_sense_about_a_document_is_refused_in_a_sentence(self):
        path = self.saved_started(source_scope='both')
        web = self.saved_started(title='Health checks')
        add = {'path': path, 'action': 'add', 'name': 'handbook.txt', 'content': self.sent()}
        for sent, expect, said in (
                ({**add, 'action': 'replace'}, 400,
                 'A document can be: add, remove, done, update.'),
                ({'path': path}, 400, 'Give action as text.'),
                ({'action': 'done'}, 400, 'Give path as text.'),
                ({**add, 'name': None}, 400, 'Give name as text.'),
                ({**add, 'content': None}, 400, 'Give content as text.'),
                ({**add, 'content': ['V29yZHMu']}, 400, 'Give content as text.'),
                ({'path': path, 'action': 'remove'}, 400, 'Give name as text.'),
                ({**add, 'content': 'not base64!'}, 400, 'That document did not arrive '
                 'whole. Add it again.'),
                ({**add, 'name': 'notes.pdf'}, 409, 'notes.pdf is not a kind of document '
                 'that can be read here. Save it as text or as a Word file.'),
                ({'path': path, 'action': 'remove', 'name': 'missing.txt'}, 409,
                 'missing.txt is not one of the documents added.'),
                ({**add, 'path': web}, 409, self.engines.NO_DOCUMENTS),
                ({**add, 'path': str(self.base / 'elsewhere')}, 403,
                 'That folder is not a training this computer knows.')):
            with self.subTest(sent=sent):
                self.assertEqual(self.post('documents', sent, expect)['error'], said)
        self.assertEqual(self.get('run', path=path)['documents']['added'], [])
        chat = self.base / 'started-in-a-chat'
        chat.mkdir()
        workspace.init(chat, 'Started in a chat')
        home.remember(chat, 'Started in a chat', [])
        for endpoint, sent in (('documents', {**add, 'path': str(chat)}),
                               ('copies', {'path': str(chat)})):
            self.assertEqual(self.post(endpoint, sent, 404)['error'],
                             'No run is driving this training.')

    def test_only_a_document_or_a_picture_sent_with_the_key_may_be_large(self):
        headers = self.headers()
        self.assertEqual(page.DOCUMENT_LIMIT, 12_000_000)
        self.assertGreater(page.DOCUMENT_LIMIT, 8_000_000 * 4 // 3,
                           'the largest document fits once it is in base64')
        self.assertEqual(self.page.body_limit('/api/documents', headers), 12_000_000)
        self.assertEqual(self.page.body_limit('/api/documents?x=1', headers), 12_000_000)
        self.assertEqual(self.page.body_limit('/api/asset', headers), 12_000_000)
        self.assertEqual(self.page.body_limit('/api/research-sources', headers), 12_000_000)
        for token in (False, 'not-the-key'):
            for target in ('/api/documents', '/api/asset', '/api/research-sources'):
                self.assertEqual(self.page.body_limit(target, self.headers(token=token)),
                                 desk.BODY_LIMIT, 'a stranger is never read at length')
        for target in (*desk.WRITES, *(path for path in POSTS
                                       if path not in ('/api/documents', '/api/asset', '/api/research-sources')),
                       '/api/documents/more', '/api/nothing', '/', '//[', ''):
            self.assertEqual(self.page.body_limit(target, headers), 64_000, target)
        self.assertEqual(desk.Page(self.PORT).body_limit('/api/documents', headers), 64_000,
                         'the plain desk takes nothing larger at any address')
        status, said, _ = self.answer('POST', '/api/documents', None, origin=self.origin,
                                      kind='application/json')
        self.assertEqual((status, said['error']), (413, 'A change is at most 12,000,000 '
                         'bytes, with its length stated.'))
        status, said, _ = self.answer('POST', '/api/copies', None, origin=self.origin,
                                      kind='application/json')
        self.assertEqual((status, said['error']), (413, 'A change is at most 64,000 bytes, '
                         'with its length stated.'))

    def test_a_document_of_the_largest_size_is_taken(self):
        path = self.saved_started(source_scope='both')
        large = 'A line of a long handbook.\n' * 280_000
        self.assertGreater(len(large), 7_500_000)
        run = self.post('documents', {'path': path, 'action': 'add', 'name': 'handbook.txt',
                                      'content': self.sent(large)})
        self.assertEqual(run['documents']['added'][0]['bytes'], len(large))

    def test_the_page_updates_the_research_with_a_later_document(self):
        path = self.saved_started(source_scope='supplied-only')
        root = Path(path)
        self.engine.supply(root, 'add', 'handbook.txt', b'Capacity holds only when more than '
                           b'one instance is running.\n')
        self.engine.supply(root, 'done')
        self.to_gate(root, 'research')
        self.engine.supply(root, 'add', 'more.txt', b'More.\n')
        with mock.patch.object(self.engine, 'carry_on'):   # the request, before it runs
            run = self.post('documents', {'path': path, 'action': 'update'})
        self.assertEqual(run['documents']['later'], [])
        self.assertEqual(workspace.load(root)['requests'][-1]['added'], ['more.txt'])

    def test_the_copies_are_made_again_on_the_page(self):
        self.copies.refuse['google'] = 'Google access is not set up on this computer.'
        path = self.saved_started(copies=['google'])
        self.to_gate(Path(path), 'brief')
        shown = self.get('run', path=path)['copies']
        self.assertEqual(shown[0], {
            'artifact': 'document', 'label': 'the learner guide', 'kind': 'google',
            'state': 'not-made', 'link': None,
            'problem': 'Google access is not set up on this computer.'})
        self.copies.refuse.clear()
        run = self.post('copies', {'path': path})
        self.assertEqual(sorted(run), RUN_KEYS)
        self.assertEqual([(entry['artifact'], entry['state'], entry['link'], entry['problem'])
                          for entry in run['copies']], [
            ('document', 'made', 'https://docs.example.com/d/doc1/edit', None)],
            'the brief is not approved yet, so there is no copy of it to show')
        self.assertEqual(self.post('copies', {}, 400)['error'], 'Give path as text.')

    def test_a_scenarios_gate_says_whose_file_it_is(self):
        path = self.saved_started()
        root = Path(path)
        self.to_gate(root, 'blueprint')
        (root / 'scenarios').mkdir()
        (root / 'scenarios' / 'objection.md').write_text(SCENARIO)
        self.to_gate(root, 'scenario:main')
        self.assertEqual(self.get('gate', path=path, artifact='scenario:main')['whose'],
                         'runner')
        theirs = self.get('gate', path=path, artifact='scenario:objection')
        self.assertEqual((theirs['whose'], theirs['label']),
                         ('you', 'The practice scenario "objection"'))
        self.assertNotIn('whose', self.get('gate', path=path, artifact='document'))
        chat = self.base / 'started-in-a-chat'
        chat.mkdir()
        workspace.init(chat, 'Started in a chat')
        home.remember(chat, 'Started in a chat', [])
        (chat / 'scenario.md').write_text(SCENARIO)
        self.assertIsNone(self.get('gate', path=str(chat), artifact='scenario:main')['whose'],
                          'with no run, nobody recorded who wrote it')

    def test_a_yoodli_scenarios_gate_names_the_scenario_to_show_beside_it(self):
        path = self.saved_started(yoodli=True, levels=['101'])
        self.to_gate(Path(path), 'yoodli:main@101')
        shown = self.get('gate', path=path, artifact='yoodli:main@101')
        self.assertEqual(shown['beside'], {'artifact': 'scenario:main@101',
                                           'label': 'The level 101 practice scenario'})
        self.assertNotIn('whose', shown)
        beside = self.get('file', path=path, artifact=shown['beside']['artifact'])
        self.assertEqual((beside['file'], beside['text']), ('101/scenario.md', SCENARIO))
        self.assertIn('Which goal carries each success criterion', shown['review'])

    def test_the_index_is_read_as_a_file_once_it_is_written(self):
        path = self.saved_started()
        said = self.get('file', 404, path=path, artifact='README.md')
        self.assertEqual(said['error'], 'The index has not been written yet.')
        self.to_end(Path(path))
        run = self.get('run', path=path)
        shown = self.get('file', path=path, artifact=run['finished']['index'])
        self.assertEqual(sorted(shown), ['artifact', 'binary', 'file', 'size', 'text',
                                         'truncated'])
        self.assertEqual((shown['artifact'], shown['file'], shown['binary'],
                          shown['truncated'], shown['text']),
                         ('README.md', 'README.md', False, False,
                          (Path(path) / 'README.md').read_text()))
        for artifact, expect in (('notes.md', 403), ('../README.md', 403),
                                 ('reviews/document.md', 403)):
            self.get('file', expect, path=path, artifact=artifact)
        said = self.get('file', 403, path=str(self.base / 'elsewhere'), artifact='README.md')
        self.assertEqual(said['error'], 'That folder is not a training this computer knows.')
        (Path(path) / 'README.md').unlink()
        (Path(path) / 'README.md').symlink_to(self.base / 'gitconfig')
        self.get('file', 403, path=path, artifact='README.md')


class WireCase(StudioCase):
    """The runner's server on a port the system chose."""

    def setUp(self):
        super().setUp()
        for patcher in (mock.patch.object(computer, 'run', never),
                        mock.patch.object(computer, 'reach', never)):
            patcher.start()
            self.addCleanup(patcher.stop)
        try:
            self.server = page.Studio(self.engine)
        except PermissionError as refused:
            self.skipTest(f'This environment does not allow listening on a local port: {refused}')
        self.addCleanup(self.server.stop)
        self.server.start()
        self.origin = f'http://127.0.0.1:{self.server.port}'

    def ask(self, target: str, sent=None, method: str | None = None, token: bool = True,
            **headers):
        headers = {name.replace('_', '-'): value for name, value in headers.items()}
        if token:
            headers[desk.TOKEN_HEADER] = self.server.token
        body = None
        if sent is not None:
            body = json.dumps(sent).encode()
            headers = {'Origin': self.origin, 'Content-Type': 'application/json', **headers}
        request = urllib.request.Request(self.origin + target, data=body, headers=headers,
                                         method=method or ('POST' if body else 'GET'))
        try:
            with DIRECT.open(request, timeout=20) as response:
                return response.status, response.headers, response.read()
        except urllib.error.HTTPError as refused:
            with refused:
                return refused.code, refused.headers, refused.read()


class WireTests(WireCase):
    def test_the_page_and_the_runner_are_served_together(self):
        status, headers, body = self.ask('/', token=False)
        self.assertEqual((status, headers.get_content_type()), (200, 'text/html'))
        self.assertEqual(body, (desk.PAGE_DIR / 'index.html').read_bytes())
        status, headers, body = self.ask('/api/capabilities')
        self.assertEqual((status, json.loads(body)),
                         (200, {'runner': True, 'version': VERSION}))
        self.assertEqual(headers['Content-Security-Policy'],
                         "default-src 'self'; img-src 'self' blob:")
        self.assertEqual(self.ask('/api/capabilities', token=False)[0], 403)
        self.assertTrue(self.server.url.endswith(f'#token={self.server.token}'))
        self.assertNotIn(self.server.token, self.server.address)

    def test_a_training_is_started_decided_and_watched_over_the_wire(self):
        path = str(self.saved_start())
        run = json.loads(self.ask('/api/run?' + urlencode({'path': path}))[2])
        self.assertEqual((run['state'], sorted(run)), ('waiting', RUN_KEYS))
        seen = workspace.sha256_file(Path(path) / pipeline.PLAN)
        status, _, body = self.ask('/api/decide', {
            'path': path, 'artifact': 'research-plan', 'decision': 'approve', 'seen': seen})
        self.assertEqual(status, 200, body)
        self.assertEqual(workspace.status(Path(path))['gate'], 'research')
        listed = json.loads(self.ask('/api/trainings')[2])
        self.assertEqual((listed['needs'], listed['trainings'][0]['run']['state']),
                         (1, 'waiting'))

    def test_a_change_without_the_key_the_origin_or_json_is_refused_over_the_wire(self):
        before = len(self.engine.trainings())
        for label, expect, options in (
                ('no key', 403, {'token': False}),
                ('another origin', 403, {'Origin': 'http://example.com'}),
                ('a form', 415, {'Content_Type': 'application/x-www-form-urlencoded'}),
                ('another host', 403, {'Host': 'example.com'})):
            with self.subTest(label):
                status, headers, body = self.ask('/api/trainings', FORM, **options)
                self.assertEqual(status, expect, body)
                self.assertEqual(headers.get_content_type(), 'application/json')
                self.assertEqual(headers['X-Frame-Options'], 'DENY')
                self.assertIn('error', json.loads(body))
        for method in ('PUT', 'DELETE', 'PATCH'):
            status, headers, _ = self.ask('/api/run', FORM, method=method)
            self.assertEqual((status, headers['Allow']), (405, 'GET, POST'))
        status, headers, _ = self.ask('/api/share', method='GET')
        self.assertEqual((status, headers['Allow']), (405, 'POST'))
        self.assertEqual((len(self.engine.trainings()), self.workers.jobs), (before, []))

    def test_something_that_cannot_be_done_is_answered_with_a_sentence_and_409(self):
        path = str(self.saved_start())
        status, _, body = self.ask('/api/run', {'path': path, 'action': 'retry'})
        self.assertEqual((status, json.loads(body)), (409, {
            'error': 'Nothing here failed, so there is nothing to try again.'}))
        status, _, body = self.ask('/api/trainings', {**FORM, 'flow': 'desk', 'source_scope': 'the-moon'})
        self.assertEqual((status, json.loads(body)['error']), (400, 'The source scope is one '
                         'of: public-web, supplied-only, both'))
        # Where research may look: something that applies, and sites that are sites.
        for chosen, said in (({'documents': False, 'sites': [], 'web': False},
                              'Choose where research may look: your documents, your sites or '
                              'the public web.'),
                             ({'sites': ['localhost/docs']}, '"localhost/docs" is not a public '
                              'site. Research never reads this computer or a private network.')):
            status, _, body = self.ask('/api/trainings', {**FORM, 'flow': 'desk', 'research_from': chosen})
            self.assertEqual((status, json.loads(body)['error']), (400, said))

    def test_a_document_is_the_only_long_body_and_only_with_the_key(self):
        path = json.loads(self.ask('/api/trainings', {**FORM, 'flow': 'desk', 'source_scope': 'both'})[2])[
            'path']
        # Just over what any other change may carry. A body refused unread has to fit in
        # what the connection holds, or the sender never gets to read the refusal.
        over = base64.b64encode(b'A line of a long handbook.\n' * 2_000).decode('ascii')
        self.assertGreater(len(over), desk.BODY_LIMIT)
        sent = {'path': path, 'action': 'add', 'name': 'handbook.txt', 'content': over}
        for label, expect, options in (
                ('no key', 403, {'token': False}),
                ('another origin', 403, {'Origin': 'http://example.com'}),
                ('a form', 415, {'Content_Type': 'application/x-www-form-urlencoded'}),
                ('another host', 403, {'Host': 'example.com'})):
            with self.subTest(label):
                # Refused unread too, so the line may be reset before the refusal is read.
                try:
                    status, _, body = self.ask('/api/documents', sent, **options)
                except urllib.error.URLError as reset:
                    self.assertIsInstance(reset.reason, (ConnectionResetError, BrokenPipeError))
                    continue
                self.assertEqual(status, expect, body)
        self.assertEqual(self.documents.listed(Path(path)), [])
        status, _, body = self.ask('/api/documents', sent)
        self.assertEqual(status, 200, body)
        self.assertEqual(json.loads(body)['documents']['added'][0]['bytes'], 27 * 2_000)
        for target in ('/api/answer', '/api/copies', '/api/decide', '/api/run'):
            # An over-long body is never read: the server refuses and closes the line. A
            # client still sending may see the line reset before it reads the refusal.
            try:
                status, _, body = self.ask(target, {'path': path, 'id': over, 'answer': over})
            except urllib.error.URLError as reset:
                self.assertIsInstance(reset.reason, (ConnectionResetError, BrokenPipeError),
                                      target)
                continue
            self.assertEqual((status, json.loads(body)['error']), (413, 'A change is at most '
                             '64,000 bytes, with its length stated.'), target)
        large = base64.b64encode(b'A line of a long handbook.\n' * 150_000).decode('ascii')
        status, _, body = self.ask('/api/documents', {**sent, 'name': 'longer.txt',
                                                      'content': large})
        self.assertEqual((status, json.loads(body)['documents']['added'][1]['bytes']),
                         (200, 27 * 150_000), body[:200])

    def test_stopping_the_server_ends_the_engine(self):
        self.server.stop()
        self.assertTrue(self.engine._closing)


class LiveWireTests(WireCase):
    """The whole of it as the runner serves it: threads of its own, and a real connection."""

    BACKGROUND = True

    def run_of(self, path: str) -> dict:
        return json.loads(self.ask('/api/run?' + urlencode({'path': path}))[2])

    def until(self, path: str, check, seconds: float = 60) -> dict:
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            run = self.run_of(path)
            if check(run):
                return run
            time.sleep(0.05)
        self.fail(f'It did not happen in time: {run}')

    def test_a_training_goes_from_the_form_to_finished_on_the_page(self):
        root = self.saved_start(levels=['101', '201'])
        path, decided = str(root), 0
        for gate in ('research-plan', 'research', 'blueprint@101', 'blueprint@201',
                     'document@101', 'brief@101', 'scenario:main@101', 'document@201',
                     'brief@201', 'scenario:main@201'):
            self.until(path, lambda run: run['state'] == 'waiting'
                       and workspace.status(root)['gate'] == gate)
            shown = json.loads(self.ask('/api/gate?' + urlencode(
                {'path': path, 'artifact': gate}))[2])
            self.assertEqual((shown['waiting'], shown['decisions'][0]), (True, 'approve'))
            status, _, body = self.ask('/api/decide', {
                'path': path, 'artifact': gate, 'decision': 'approve',
                'seen': shown['sha256']})
            self.assertEqual(status, 200, body)
            decided += 1
        done = self.until(path, lambda run: run['state'] == 'done')
        self.assertEqual(decided, 10)
        self.assertEqual({step['status'] for step in done['steps']}, {'done'})
        self.assertEqual((done['workers'], done['finished']['ready']), ([], True))
        self.assertEqual(len(self.workers.jobs), 13)
        self.until(path, lambda run: self.git('status', '--porcelain') == '')
        approved = [line for line in self.log() if line.endswith('approved on the page.')]
        self.assertEqual(len(approved), 10)
        status, _, body = self.ask('/api/file?' + urlencode(
            {'path': path, 'artifact': done['finished']['index']}))
        self.assertEqual((status, json.loads(body)['text'].splitlines()[0]),
                         (200, '# Rolling restarts'))


class PlainDeskTests(unittest.TestCase):
    def test_the_desk_still_serves_without_the_runner(self):
        try:
            plain = desk.Desk()
        except PermissionError as refused:
            self.skipTest(f'This environment does not allow listening on a local port: {refused}')
        self.addCleanup(plain.stop)
        plain.start()
        self.assertIs(type(plain.page), desk.Page)
        request = urllib.request.Request(f'http://127.0.0.1:{plain.port}/api/capabilities',
                                         headers={desk.TOKEN_HEADER: plain.token})
        with self.assertRaises(urllib.error.HTTPError) as refused:
            DIRECT.open(request, timeout=20)
        with refused.exception:
            self.assertEqual(refused.exception.code, 404)


class SettingsTests(StudioCase):
    """What this computer remembers for the runner."""

    def test_the_defaults_are_used_until_something_is_saved(self):
        self.assertEqual(settings.load(), settings.Settings(
            agent='claude', step_seconds=900, training_dollars=20.0, parallel=2))
        kept = settings.save(replace(settings.load(), agent='codex', parallel=4))
        self.assertEqual((settings.load(), kept.limits), (kept, {
            'step_seconds': 900, 'training_dollars': 20.0, 'parallel': 4}))
        self.assertEqual(settings.path().parent, home.data_root())
        self.assertNotIn(self.space.repo, settings.path().parents)

    def test_a_file_that_cannot_be_used_reads_as_the_defaults(self):
        for text in ('not json', '{"schema": 2, "parallel": 4}',
                     '{"schema": 1, "previews": "another"}', '{"schema": 1, "parallel": 99}'):
            settings.path().write_text(text)
            self.assertEqual(settings.load(), settings.Settings())
        settings.path().write_text('{"schema": 1, "parallel": 4, "extra": true}')
        self.assertEqual(settings.load().parallel, 4)

    def test_the_shared_settings_are_read_from_the_studios_config_only(self):
        studios = Path(os.environ['STUDIOS_CONFIG'])
        # What an earlier version kept here is not read: the file every studio shares is.
        settings.path().write_text('{"schema": 1, "agent": "codex", "model": "gpt-6-sol", '
                                   '"brand_repository": "git@github.com:acme/brand.git", '
                                   '"parallel": 4}')
        self.assertEqual(settings.load(), settings.Settings(parallel=4))
        studios.write_text('{"schema": 1, "assistant": {"agent": "codex", "effort": "low"}, '
                           '"brand": {"repository": "git@github.com:acme/brand.git", '
                           '"release": "v1.4.0"}, "person": {"name": "Alex"}}')
        self.assertEqual(settings.load(), settings.Settings(
            agent='codex', effort='low', parallel=4,
            brand_repository='git@github.com:acme/brand.git', brand_release='v1.4.0'))

    def test_saving_writes_a_shared_setting_to_the_studios_config_and_the_rest_here(self):
        studios = Path(os.environ['STUDIOS_CONFIG'])
        text = '{"schema": 1, "person": {"name": "Alex"}, "assistant": {"agent": "claude"}}\n'
        studios.write_text(text)
        kept = settings.save(replace(settings.load(), agent='codex', parallel=4))
        text = text.replace('"claude"', '"codex"')
        self.assertEqual(studios.read_text(), text)
        self.assertEqual(settings.load(), kept)
        self.assertEqual(studios_config.read()[0]['assistant'], {'agent': 'codex'})
        self.assertEqual(json.loads(settings.path().read_text())['parallel'], 4)
        self.assertNotIn('agent', json.loads(settings.path().read_text()))
        # A per-studio setting alone leaves the file as it was, not even written again.
        before = studios.stat().st_mtime_ns
        settings.save(replace(settings.load(), parallel=3, look_for_updates=False))
        self.assertEqual((studios.read_text(), studios.stat().st_mtime_ns), (text, before))
        # A value the file holds that Training Studio cannot use is not written over by a
        # save that did not change it.
        other = '{"schema": 1, "assistant": {"agent": "gemini", "model": "pro"}}'
        studios.write_text(other)
        settings.save(replace(settings.load(), parallel=2))
        self.assertEqual(studios.read_text(), other)

    def test_a_form_opened_before_another_studio_changed_a_value_never_writes_over_it(self):
        studios = Path(os.environ['STUDIOS_CONFIG'])
        studios.write_text('{"schema": 1, "assistant": {"agent": "claude", "model": "opus"}}')
        shown = settings.load()
        # Meanwhile, another studio changes the model.
        studios.write_text('{"schema": 1, "assistant": {"agent": "claude", "model": "sonnet"}}')
        # A save that left the model alone keeps theirs, and writes only what it changed.
        settings.save(replace(shown, effort='high', parallel=4), shown)
        self.assertEqual(json.loads(studios.read_text())['assistant'],
                         {'agent': 'claude', 'model': 'sonnet', 'effort': 'high'})
        # One that changed the model too is refused, and nothing at all is kept.
        kept = settings.path().read_text()
        before = studios.read_text()
        with self.assertRaises(WorkspaceError) as refused:
            settings.save(replace(shown, model='haiku', parallel=5), shown)
        self.assertEqual(str(refused.exception), 'The model was changed in another studio '
                         'while this was open, so nothing was saved. Look again, then save.')
        self.assertEqual((studios.read_text(), settings.path().read_text()), (before, kept))
        # Changed to what the other studio chose, there is nothing to refuse.
        settings.save(replace(shown, model='sonnet'), shown)
        self.assertEqual(settings.load().model, 'sonnet')

    def test_a_model_and_a_level_are_written_only_beside_the_agent_the_form_shows(self):
        studios = Path(os.environ['STUDIOS_CONFIG'])
        theirs = '{"schema": 1, "assistant": {"agent": "gemini", "model": "pro", "effort": "deep"}}'
        for changed, written in (
                ({'model': 'opus'}, {'agent': 'claude', 'model': 'opus', 'effort': None}),
                ({'effort': 'high'}, {'agent': 'claude', 'model': None, 'effort': 'high'})):
            with self.subTest(changed=changed):
                studios.write_text(theirs)
                shown = settings.load()
                self.assertEqual((shown.agent, shown.model, shown.effort),
                                 ('claude', None, None))
                settings.save(replace(shown, **changed), shown)
                self.assertEqual(json.loads(studios.read_text())['assistant'], written)
        # So is a release beside the brand skill's repository: another one goes with it.
        studios.write_text('{"schema": 1, "brand": {"repository": '
                           '"https://pat:secret@github.com/acme/brand.git", "release": "v1"}}')
        shown = settings.load()
        settings.save(replace(shown, brand_repository='git@github.com:acme/brand.git'), shown)
        self.assertEqual(json.loads(studios.read_text())['brand'],
                         {'repository': 'git@github.com:acme/brand.git', 'release': None})

    def test_a_level_is_not_saved_beside_an_agent_another_studio_chose_meanwhile(self):
        studios = Path(os.environ['STUDIOS_CONFIG'])
        studios.write_text('{"schema": 1, "assistant": {"agent": "claude"}}')
        shown = settings.load()
        text = '{"schema": 1, "assistant": {"agent": "codex"}}'
        studios.write_text(text)
        with self.assertRaises(WorkspaceError) as refused:
            settings.save(replace(shown, effort='high'), shown)
        self.assertEqual(str(refused.exception), 'The agent was changed in another studio '
                         'while this was open, so nothing was saved. Look again, then save.')
        self.assertEqual(studios.read_text(), text)

    def test_while_the_studios_config_cannot_be_read_a_shared_setting_is_not_saved(self):
        studios = Path(os.environ['STUDIOS_CONFIG'])
        studios.write_text('{"schema": 1, "assistant": ')
        settings.save(replace(settings.load(), parallel=4))
        kept = settings.path().read_text()
        self.assertEqual(settings.load(), settings.Settings(parallel=4))
        with self.assertRaisesRegex(WorkspaceError, 'no value every studio shares can be '
                                                    'saved until it can'):
            settings.save(replace(settings.load(), agent='codex', parallel=5))
        self.assertEqual((studios.read_text(), settings.path().read_text()),
                         ('{"schema": 1, "assistant": ', kept), 'nothing at all was kept')

    def test_the_brand_skills_repository_is_kept_only_in_a_shape_git_takes(self):
        studios = Path(os.environ['STUDIOS_CONFIG'])
        studios.write_text('{"schema": 1, "brand": {"brand": "acme", "variant": "dark"}}')
        kept = settings.save(replace(settings.load(),
                                     brand_repository=' git@github.com:acme/brand.git ',
                                     brand_release='v1.4.0'))
        self.assertEqual((kept.brand_repository, kept.brand_release),
                         ('git@github.com:acme/brand.git', 'v1.4.0'))
        self.assertEqual(settings.load(), kept)
        self.assertEqual(studios.read_text(), '{"schema": 1, "brand": {"brand": "acme", '
                         '"variant": "dark", "repository": "git@github.com:acme/brand.git", '
                         '"release": "v1.4.0"}}')
        for repository, release, says in (
                ('-oProxyCommand=touch', None, 'as one address'),
                ('https://github.com/acme/my brand', None, 'as one address'),
                ('https://pat:secret@github.com/acme/brand.git', None, 'password or token'),
                ('https://github.com/acme/brand.git', '-v1', 'as its tag'),
                ('https://github.com/acme/brand.git', 'v1..2', 'as its tag'),
                (None, 'v1.4.0', 'give the repository too')):
            with self.subTest(repository=repository, release=release), \
                    self.assertRaises(WorkspaceError) as refused:
                settings.save(replace(settings.load(), brand_repository=repository,
                                      brand_release=release))
            self.assertIn(says, str(refused.exception))
        self.assertEqual(settings.load(), kept, 'nothing that was refused was kept')


class GoogleSignInTests(unittest.TestCase):
    """Status says whether Google is signed in, from this computer's own gcloud settings."""

    def checked(self, account: str | None) -> dict:
        def run(command):
            if command[0] == 'gcloud':
                if account is None:
                    return {'found': False, 'ok': False, 'output': ''}
                if command == computer.COMMANDS['gcloud-account']:
                    return {'found': True, 'ok': True, 'output': account}
                return {'found': True, 'ok': True, 'output': 'Google Cloud SDK 500.0.0'}
            return {'found': True, 'ok': True, 'output': '1.0.0'}
        with mock.patch.object(computer, 'run', run), \
                mock.patch.object(computer, 'reach', lambda host: None):
            found = computer.check(google=True)
        return next(entry for entry in found['items'] if entry['id'] == 'gcloud')

    def test_the_account_is_asked_of_this_computer_only(self):
        self.assertEqual(computer.COMMANDS['gcloud-account'],
                         ('gcloud', 'auth', 'list', '--filter=status:ACTIVE',
                          '--format=value(account)'))

    def test_a_signed_in_account_is_named(self):
        gcloud = self.checked('ana@example.com')
        self.assertEqual(gcloud['state'], 'ok')
        self.assertIn(computer.fact('Signed in', 'ok', 'ana@example.com'), gcloud['facts'])

    def test_no_account_says_how_to_sign_in(self):
        gcloud = self.checked('')
        self.assertEqual(gcloud['state'], 'problem')
        self.assertIn(computer.fact('Signed in', 'problem', 'not signed in'), gcloud['facts'])
        self.assertEqual(gcloud['fix'], 'Not signed in. In a terminal, run `gcloud auth login '
                         '--enable-gdrive-access`, then check this computer again.')

    def test_no_gcloud_asks_nothing_more(self):
        gcloud = self.checked(None)
        self.assertEqual(gcloud['state'], 'missing')
        self.assertEqual([entry['label'] for entry in gcloud['facts']], ['Installed'])


if __name__ == '__main__':
    unittest.main()


class ResearchFileTests(PageCase):
    def test_research_objections_are_read_as_a_confined_saved_file(self):
        root = self.start()
        (root / 'reviews').mkdir(exist_ok=True)
        (root / 'reviews/research.md').write_text('# Independent check\n\n- Too broad.\n')
        found = self.get('file', path=str(root), artifact='reviews/research.md')
        self.assertEqual(found['text'], '# Independent check\n\n- Too broad.\n')
        self.get('file', path=str(root), artifact='reviews/../intake.md', expect=403)


class DownloadTests(PageCase):
    """Managed deliverables leave the authenticated page only as attachments."""

    def setUp(self):
        super().setUp()
        self.path = self.saved_started(levels=['101'], stages=['document', 'brief', 'deck'], copies=['word'])
        self.root = Path(self.path)
        (self.root / '101').mkdir(exist_ok=True)

    def download(self, artifact, **params):
        target = '/api/download?' + urlencode({'path': self.path, 'artifact': artifact, **params})
        return self.page.answer(target, self.headers(), 'GET')

    def test_a_deck_downloads_as_an_attachment(self):
        (self.root / '101/deck.pptx').write_bytes(b'PK\x03\x04deck')
        status, kind, data, headers = self.download('deck@101')
        self.assertEqual((status, kind, data), (200,
            'application/vnd.openxmlformats-officedocument.presentationml.presentation',
            b'PK\x03\x04deck'))
        self.assertEqual(headers['Content-Disposition'],
                         f'attachment; filename="{self.root.name}-101-deck.pptx"')

    def test_a_word_copy_downloads(self):
        (self.root / '101/document.md').write_text('A guide.')
        (self.root / '101/document.docx').write_bytes(b'PK word')
        workspace.export(self.root, 'document@101')
        status, kind, data, _ = self.download('document@101', copy='word')
        self.assertEqual((status, kind, data), (200,
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document', b'PK word'))

    def test_the_index_downloads(self):
        (self.root / 'README.md').write_text('# Made\n')
        status, kind, data, _ = self.download('README.md')
        self.assertEqual((status, kind, data), (200, 'text/markdown; charset=utf-8', b'# Made\n'))

    def test_refusals(self):
        for artifact, params, expected in (
                ('unknown', {}, 403), ('../README.md', {}, 403), ('/etc/hosts', {}, 403),
                ('deck@999', {}, 403), ('deck@101', {'copy': 'pdf'}, 400),
                ('deck@101', {}, 404), ('document@101', {'copy': 'word'}, 404)):
            with self.subTest(artifact=artifact, params=params):
                with self.assertRaises(desk.Refusal) as refused:
                    self.download(artifact, **params)
                self.assertEqual(refused.exception.status, expected)
        target = '/api/download?' + urlencode({'path': self.path, 'artifact': 'README.md'})
        with self.assertRaises(desk.Refusal) as refused:
            self.page.answer(target, self.headers(token=False), 'GET')
        self.assertEqual(refused.exception.status, 403)
        outside = self.base / 'outside.pptx'
        outside.write_bytes(b'private')
        (self.root / '101/deck.pptx').symlink_to(outside)
        with self.assertRaisesRegex(desk.Refusal, 'leads outside the training folder') as refused:
            self.download('deck@101')
        self.assertEqual(refused.exception.status, 403)
        self.assertEqual(self.get('download', 403, path=str(self.base / 'unknown'),
                                  artifact='README.md')['error'],
                         'That folder is not a training this computer knows.')


class PullCopyTests(PageCase):
    def test_the_page_brings_in_a_doc_and_reopens_its_review(self):
        import gdocs
        path = self.saved_started(levels=['101'], copies=['google'])
        root = Path(path)
        self.to_gate(root, 'document@101')
        self.decide(root, 'document@101')
        ident = gdocs.read_links(root)['docs']['document@101']['file_id']
        self.copies.drive.docs[ident] += '\nFrom a teammate.\n'
        run = self.post('copies', {'path': path, 'pull': 'document@101'})
        self.assertIn('From a teammate.', (root / '101/document.md').read_text())
        self.assertIn("The Doc's changes are in.", run['said'])
        self.assertEqual(workspace.status(root)['gate'], 'document@101')

    def test_the_page_looks_for_doc_changes_when_asked(self):
        import gdocs
        path = self.saved_started(levels=['101'], copies=['google'])
        root = Path(path)
        self.to_gate(root, 'document@101')
        self.decide(root, 'document@101')
        before = list(self.copies.drive.calls)
        shown = self.get('run', path=path)
        self.assertEqual(self.copies.drive.calls, before, 'reading the page asks Google nothing')
        self.assertNotIn('remote', shown['copies'][0])
        ident = gdocs.read_links(root)['docs']['document@101']['file_id']
        self.copies.drive.docs[ident] += '\nFrom a teammate.\n'
        run = self.post('copies', {'path': path, 'action': 'check'})
        self.assertEqual(sorted(set(run) - {'said'}), RUN_KEYS)
        self.assertEqual(run['said'], '1 Google Doc was changed there.')
        entry = next(one for one in run['copies'] if one['artifact'] == 'document@101')
        self.assertEqual(entry['remote'], 'remote changed')
        self.assertEqual(self.post('copies', {'path': path, 'action': 'nonsense'}, 400)['error'],
                         'Ask to check the copies, make a Doc again, or make them again.')
        run = self.post('copies', {'path': path, 'pull': 'document@101'})
        entry = next(one for one in run['copies'] if one['artifact'] == 'document@101')
        self.assertNotIn('remote', entry, 'brought in, so nothing is said of it any more')

    def test_a_doc_check_that_cannot_reach_google_says_so(self):
        import gdocs
        path = self.saved_started(levels=['101'], copies=['google'])
        root = Path(path)
        self.to_gate(root, 'document@101')
        self.decide(root, 'document@101')
        ident = gdocs.read_links(root)['docs']['document@101']['file_id']

        def refused(file_id):
            raise WorkspaceError('Google access is not set up on this computer.')
        with mock.patch.object(self.copies.drive, 'export', refused):
            run = self.post('copies', {'path': path, 'action': 'check'})
        self.assertIn('could not be checked', run['said'])
        self.assertIn('Google access is not set up on this computer.', run['said'])
        self.assertTrue(ident)

    def test_pulling_is_refused_while_a_dependent_worker_builds(self):
        refused = []
        path = self.saved_started(levels=['101'], copies=['google'])
        root = Path(path)
        self.to_gate(root, 'blueprint@101')

        def building(tools, job):
            refused.append(self.post('copies', {'path': path, 'pull': 'document@101'}, 409))
            self.workers.document(tools, job)

        self.workers.then('document', building)
        self.decide(root, 'blueprint@101')
        self.assertEqual(refused, [{'error': 'It is being worked on. Bring the Doc\'s changes in once it stops.'}])


class DecisionMessageTests(PageCase):
    def test_row_125_reaching_the_next_stop_keeps_the_existing_audit_commit(self):
        path = self.saved_started()
        root = Path(path)
        self.to_gate(root, 'document')
        self.decide(root, 'document')
        self.assertIsNone(self.get('run', path=path)['decided'])
        self.assertTrue(self.engine._load(root)['last_decision_stop'])
        self.assertEqual(self.log()[-1], 'Rolling restarts: ask for a review of the brief')
        self.assertEqual(self.git('status', '--porcelain'), '')

    def test_combined_approval_persists_the_next_step_and_done_yoodli_fields(self):
        path = self.saved_started(review_level='balanced', yoodli=True)
        root = Path(path)
        self.decide(root, 'research-plan')
        working = []

        def build(tools, job):
            working.append(self.get('run', path=path)['decided'])
            self.workers.brief(tools, job)

        self.workers.then('brief', build)
        run = self.get('run', path=path)
        run = self.post('review', {'path': path, 'expected': run['review']['expected'], 'decision': 'approve'})
        self.assertEqual(working[0]['label'], 'the first drafts')
        self.assertIsNone(run['decided'])
        run = self.post('review', {'path': path, 'expected': run['review']['expected'], 'decision': 'approve'})
        self.assertEqual(run['finished']['yoodli'][0]['artifact'], 'yoodli:main')
        self.assertIn('Roleplay name', run['finished']['yoodli'][0]['text'])

    def test_a_decision_is_said_until_the_next_stop(self):
        path = self.saved_started()
        root = Path(path)
        self.to_gate(root, 'document')
        working = []

        def build(tools, job):
            working.append(self.get('run', path=path)['decided'])
            self.workers.brief(tools, job)

        self.workers.then('brief', build)
        self.decide(root, 'document')
        self.assertEqual(working[0]['label'], 'the learner guide')
        self.assertEqual(working[0]['decision'], 'approve')
        self.assertIn('brief', working[0]['next'])
        self.assertIsNone(self.get('run', path=path)['decided'])
        record = self.engine._load(root)
        self.assertEqual(record['last_decision']['label'], 'the learner guide')


FORBIDDEN = ('artifact', 'stale', 'lineage', 'your review')
CARD_KEYS = ['actions', 'checks', 'held', 'kind', 'label', 'level', 'name', 'needs', 'says',
             'seen', 'state']


def hashed(root: Path, name: str) -> str | None:
    """The hash of a material's file as it is on disk now."""
    session = workspace.load(root)
    return workspace.sha256_file(root / workspace.artifact(root, session, name)['file'])


class DeskPageTests(PageCase):
    """The desk's view and its decisions on the runner's page: GET /api/drafts and the
    POSTs under /api/drafts/. A desk training refuses the review routes, and a saved one
    refuses the desk's. Tests named row_159 cover that row of the state-transition matrix
    in docs/superpowers/plans/2026-10-12-training-studio-core-pipeline.md."""

    def setUp(self):
        super().setUp()
        self.slides, self.brand = Slides(), Brand()
        settings.save(replace(settings.load(), previews='drive'))

    def desk(self, **changes) -> str:
        return self.started(**{'flow': 'desk', **changes})

    @staticmethod
    def said(view: dict) -> list[str]:
        """Every sentence the desk's view says, to look for words it must never use."""
        return [*(card['says'] for card in view['cards']), *view['needs'],
                view['progress']['line'], view['progress']['doing']]

    def test_finishing_routes_are_authenticated_and_saved_runs_refuse_them(self):
        path = self.desk(materials=['document', 'brief'], levels=['101'])
        name = 'document@101'
        card = self.get('drafts/card', path=path, name=name)
        sent = {'path': path, 'name': name, 'tool': 'coverage', 'seen': card['revision']}
        self.post('drafts/finish', sent, expect=403, token=False)
        checked = self.post('drafts/finish', sent)
        self.assertIn('coverage', checked['finishing'])
        for tool in ('sources', 'time', 'answers', 'humanize', 'level'):
            self.post('drafts/finish', {**sent, 'tool': tool}, expect=403, token=False)
        for route in ('apply', 'skip'):
            self.post('drafts/' + route, {**sent, 'job': 'a' * 32, 'items': []},
                      expect=403, token=False)
        proof = self.get('drafts/proofread', path=path, name=name)
        self.assertIn('findings', proof)
        saved = self.saved_started(title='Saved training')
        for route in ('finish', 'apply', 'skip'):
            refused = self.post('drafts/' + route, {**sent, 'path': saved}, expect=409)
            self.assertEqual(refused['error'], drafts.NOT_ON_DESK)
        self.get('drafts/proofread', path=saved, name=name, expect=409)
        for tool in ('sources', 'time', 'answers', 'humanize', 'level'):
            refused = self.post('drafts/finish', {**sent, 'path': saved, 'tool': tool}, expect=409)
            self.assertEqual(refused['error'], drafts.NOT_ON_DESK)

    def test_added_sources_have_a_read_only_price_and_authenticated_batch_route(self):
        path = self.desk(materials=['document', 'brief'])
        before = self.on_disk()
        price = self.get('drafts/source-price', path=path)
        self.assertEqual(price['afterwards'], drafts.AFTERWARDS)
        self.assertEqual(self.on_disk(), before)
        sent = {'path': path, 'files': [{'name': 'notes.txt', 'content': base64.b64encode(
            b'Capacity holds only when more than one instance is running.').decode()}]}
        self.post('drafts/source', sent, expect=403, token=False)
        self.assertEqual(self.on_disk(), before)
        malformed = {**sent, 'files': [sent['files'][0], {'name': 'bad.txt', 'content': '%%%'}]}
        self.post('drafts/source', malformed, expect=400)
        self.assertEqual(self.on_disk(), before)
        added = self.post('drafts/source', sent)
        self.assertEqual(added['sources']['documents'][0]['name'], 'notes.txt')
        self.assertTrue(any(card['held'] for card in added['cards']))
        saved = self.saved_started(title='Saved training')
        refused = self.post('drafts/source', {**sent, 'path': saved}, expect=409)
        self.assertEqual(refused['error'], drafts.NOT_ON_DESK)
        self.get('drafts/source-price', path=saved, expect=409)
        self.assertEqual(self.page.body_limit('/api/drafts/source', self.headers()), 12_000_000)
        self.assertEqual(self.page.body_limit('/api/drafts/source', self.headers(token=False)), 64_000)

    def test_bulk_updates_and_stop_are_authenticated_desk_actions(self):
        path = self.desk(materials=['document', 'brief'], levels=['101', '201'])
        root = Path(path)
        self.engine.add_source(root, [{'name': 'notes.txt', 'data': QUOTE.encode()}])
        before = self.on_disk()
        self.post('drafts/update-all', {'path': path}, expect=403, token=False)
        self.assertEqual(self.on_disk(), before)
        self.post('drafts/update-all', {'path': path, 'level': '999'}, expect=409)
        self.post('drafts/update-all', {'path': path, 'level': []}, expect=400)
        with mock.patch.object(self.engine, 'carry_on'):
            result = self.post('drafts/update-all', {'path': path, 'level': '101'})
        chain = result['sources']['updates']['chain']['id']
        self.post('drafts/stop-updates', {'path': path, 'chain': chain}, expect=403, token=False)
        stopped = self.post('drafts/stop-updates', {'path': path, 'chain': chain})
        self.assertEqual(stopped['sources']['updates']['chain']['status'], 'stopped')
        self.assertFalse(drafts.updates(self.record(root)))
        saved = self.saved_started(title='Saved training')
        for route, extra in [('update-all', {}), ('stop-updates', {'chain': chain})]:
            result = self.post('drafts/' + route, {'path': saved, **extra}, expect=409)
            self.assertEqual(result['error'], drafts.NOT_ON_DESK)

    def test_row_159_desk_and_review_routes_refuse_each_other(self):
        path = self.desk(materials=['document', 'brief'])
        root = Path(path)
        saved = self.saved_started(title='Saved restarts')
        before, commits = self.on_disk(), self.log()
        name = 'blueprint'
        for target, sent in (
                ('decide', {'artifact': name, 'decision': 'approve',
                            'seen': hashed(root, name)}),
                ('review', {'expected': 'x', 'decision': 'approve'}),
                ('outline', {'decision': 'approve'}),
                ('look', {'choice': 'first'})):
            with self.subTest(route=target):
                said = self.post(target, {'path': path, **sent}, 409)
                self.assertEqual(said['error'], drafts.ON_DESK)
        said = self.get('gate', 409, path=path, artifact=name)
        self.assertEqual(said['error'], drafts.ON_DESK)
        self.assertEqual(self.get('drafts', 409, path=saved)['error'], drafts.NOT_ON_DESK)
        for route, sent in (('ready', {'name': 'research-plan', 'seen': 'x'}),
                            ('level-ready', {'level': '', 'seen': {}}),
                            ('update', {'name': 'research-plan'}),
                            ('keep', {'name': 'research-plan', 'reason': 'Fine.',
                                      'seen': 'x'}),
                            ('send', {'name': 'research-plan'}),
                            ('save', {'name': 'blueprint', 'part': 'opening', 'seen': 1,
                                      'text': 'Typed.', 'session': 'ab12'}),
                            ('restore', {'name': 'blueprint', 'part': 'opening', 'seen': 1,
                                         'index': 0}),
                            ('share', {}),
                            ('note', {'name': 'blueprint', 'seen': 1, 'note': 'Change.'}),
                            ('revise', {'name': 'document', 'seen': 1, 'note': 'Change.'}),
                            ('selection', {'name': 'document', 'part': 'opening', 'seen': 1,
                                           'text': 'word', 'start': 0, 'action': 'shorten'}),
                            ('stop', {'job': 'unknown'}), ('retry', {'job': 'unknown'})):
            with self.subTest(route=route):
                said = self.post(f'drafts/{route}', {'path': saved, **sent}, 409)
                self.assertEqual(said['error'], drafts.NOT_ON_DESK)
        said = self.get('drafts/versions', 409, path=saved, name='blueprint', part='opening')
        self.assertEqual(said['error'], drafts.NOT_ON_DESK)
        said = self.get('drafts/card', 409, path=saved, name='blueprint')
        self.assertEqual(said['error'], drafts.NOT_ON_DESK)
        self.assertEqual((self.on_disk(), self.log()), (before, commits),
                         'nothing was changed or committed')
        # Each still answers what is its own as it always did.
        self.assertTrue(self.get('gate', path=saved, artifact='research-plan')['waiting'])
        self.assertEqual(sorted(self.get('drafts', path=path)),
                         ['cards', 'flow', 'job', 'levels', 'needs', 'progress', 'sources',
                          'team', 'title'])

    def test_reading_the_desk_changes_nothing(self):
        path = self.desk(levels=['101'], materials=['document', 'brief'])
        root = Path(path)
        saved = (root / '.training-studio' / 'run.json', workspace.session_path(root))
        before = [file.read_bytes() for file in saved]
        head = self.git('rev-parse', 'HEAD').strip()
        for _ in range(2):
            self.assertEqual(self.get('drafts', path=path)['flow'], 'desk')
        self.assertEqual([file.read_bytes() for file in saved], before)
        self.assertEqual(self.git('rev-parse', 'HEAD').strip(), head)

    def test_a_desk_training_takes_no_document_after_its_research(self):
        sent = base64.b64encode(b'Capacity holds only when more than one instance is '
                                b'running.\n').decode('ascii')
        path = self.desk(source_scope='supplied-only', materials=['document'])
        self.post('documents', {'path': path, 'action': 'add', 'name': 'handbook.txt',
                                'content': sent})
        self.post('documents', {'path': path, 'action': 'done'})
        commits = self.log()
        said = self.post('documents', {'path': path, 'action': 'add', 'name': 'later.txt',
                                       'content': sent}, 409)
        self.assertEqual(said['error'], engines.SETTLED)
        self.assertEqual(self.log(), commits)

    def test_the_desk_view_lists_each_level_s_cards_in_order(self):
        path = self.desk(levels=['101', '201'], deck_target='pptx', brand=CHOSEN,
                         walkthrough=False)
        root = Path(path)
        view = self.get('drafts', path=path)
        self.assertEqual((view['flow'], view['title'], view['levels']),
                         ('desk', 'Rolling restarts', ['101', '201']))
        first = [card for card in view['cards'] if card['level'] == '101']
        self.assertEqual([card['name'] for card in first],
                         ['blueprint@101', 'document@101', 'brief@101', 'deck@101',
                          'scenario:main@101'])
        self.assertEqual([card['kind'] for card in first],
                         ['blueprint', 'document', 'brief', 'deck', 'scenario'])
        for card in view['cards']:
            with self.subTest(card=card['name']):
                self.assertEqual(sorted(card), sorted(CARD_KEYS + ([
                    'change', 'local', 'look', 'look_price', 'outline', 'outline_delivery',
                    'proposals', 'selection', 'slides'] if card['kind'] == 'deck' else [])))
                self.assertEqual(card['seen'], hashed(root, card['name']))
                self.assertEqual((card['state'], card['held'], card['needs']),
                                 ('draft', False, []))
                self.assertEqual(card['actions'], ['ready', 'download'])
                self.assertEqual(card['label'], workspace.label(card['name']))
        for line in self.said(view):
            for word in FORBIDDEN:
                self.assertNotIn(word, line.lower())
        self.assertEqual(view['progress']['running'], False)
        self.assertEqual((view['progress']['line'], view['progress']['minutes']), ('', None))
        self.assertEqual(view['needs'], [], 'a draft never needs the person')
        self.assertTrue(view['team']['ours'])
        self.assertEqual(sorted(view['sources']), ['account', 'documents', 'marked', 'plan', 'updates'])
        self.assertEqual(len(view['sources']['plan']), 4)
        self.assertIsNone(view['job'])
        # Each deck's whole time is kept here, for the next start's estimate.
        self.assertEqual(len(json.loads(drafts.times().read_text(encoding='utf-8'))['deck']),
                         2)
        # The desk's list says each material is a draft, not approved.
        item = self.get('training', path=path)
        files = {file['artifact']: file for file in item['view']['files']}
        self.assertEqual((files['document@101']['status'], files['document@101']['words']),
                         ('draft', 'not marked ready yet'))

    def test_a_card_is_marked_ready_on_the_page(self):
        path = self.desk(levels=['101'], materials=['document', 'brief'])
        root = Path(path)
        name = 'document@101'
        view = self.post('drafts/ready', {'path': path, 'name': name,
                                          'seen': hashed(root, name)})
        card = next(card for card in view['cards'] if card['name'] == name)
        self.assertEqual((card['state'], card['actions']), ('ready', ['download']))
        said = self.post('drafts/ready', {'path': path, 'name': 'brief@101', 'seen': 'x'}, 409)
        self.assertTrue(said['error'].endswith('has changed since it was opened. Read the new '
                                               'version before deciding.'))
        marked = self.post('drafts/level-ready', {
            'path': path, 'level': '101',
            'seen': {card['name']: card['seen'] for card in view['cards']}})
        self.assertEqual((marked['marked'], marked['stopped']),
                         (['blueprint@101', 'brief@101'], None))
        self.assertEqual({card['state'] for card in marked['cards']}, {'ready'})

    def test_a_held_card_offers_update_and_keep(self):
        path = self.desk(levels=['101'], materials=['document', 'brief'])
        root = Path(path)
        plan = root / '101' / 'blueprint.md'
        typed = self.base / 'blueprint.md'
        typed.write_text(plan.read_text(encoding='utf-8') + '\nOne line more.\n',
                         encoding='utf-8')
        workspace.save(root, 'blueprint@101', source=typed, edit=True, via='save')
        workspace.accept_desk(root, 'blueprint@101')
        view = self.get('drafts', path=path)
        cards = {card['name']: card for card in view['cards']}
        guide = cards['document@101']
        self.assertEqual((guide['state'], guide['held'], guide['says'], guide['actions']),
                         ('held', True, 'Built from an earlier plan.',
                          ['update', 'keep', 'download']))
        self.assertEqual(view['needs'], ['the level 101 learner guide', 'the level 101 brief'])
        kept = self.post('drafts/keep', {'path': path, 'name': 'document@101',
                                         'reason': 'It still reads right.',
                                         'seen': guide['seen']})
        guide = next(card for card in kept['cards'] if card['name'] == 'document@101')
        self.assertEqual((guide['state'], guide['held']), ('draft', False))

    def test_progress_says_nothing_is_needed(self):
        root = self.space.training(workspace.slugify(FORM['title']))
        seen = []

        def writing(tools, job):
            with mock.patch.object(drafts, 'start_minutes', side_effect=AssertionError('Live status must not estimate completion')):
                seen.append(self.get('drafts', path=str(root)))
            return self.workers.document(tools, job)

        self.workers.then('document', writing)
        self.desk(levels=['101'], materials=['document', 'brief'])
        progress = seen[0]['progress']
        self.assertTrue(progress['running'])
        self.assertEqual(progress['line'], 'Nothing needed from you. Each material opens '
                         'here as it is ready.')
        self.assertIsNone(progress['minutes'], 'Live progress must not manufacture a countdown')
        self.assertEqual(progress['started_at'], self.record(root)['started_at'])
        self.assertTrue(progress['doing'])
        cards = {card['name']: card for card in seen[0]['cards']}
        self.assertEqual((cards['document@101']['state'], cards['document@101']['seen'],
                          cards['document@101']['actions']), ('writing', None, []))
        self.assertEqual(cards['blueprint@101']['state'], 'draft')
        for line in self.said(seen[0]):
            for word in FORBIDDEN:
                self.assertNotIn(word, line.lower())
        self.assertEqual(self.get('drafts', path=str(root))['progress']['line'], '')

    def test_the_start_s_minutes_use_this_computer_s_times(self):
        self.assertEqual(drafts.GUESSES, {'research': 6, 'blueprint': 1, 'document': 3,
                                          'brief': 2, 'scenario': 1, 'yoodli': 1})
        root = Path(self.desk(levels=['101'], materials=['document', 'brief'],
                              source_scope='supplied-only'))
        record = self.engine._load(root)

        def minutes() -> int:
            return drafts.start_minutes(root, record, self.engine._survey(root, record))

        self.assertEqual(minutes(), 6 + 1 + 3 + 2)
        for _ in range(3):
            step_times.note(drafts.Times(), drafts.times(), 'document', 120)
        self.assertEqual(drafts.times(), home.data_root() / 'draft-step-times.json')
        self.assertEqual(minutes(), 6 + 1 + 2 + 2)

    def test_a_deck_s_guess_is_its_slides(self):
        root = Path(self.desk(levels=['101'], materials=['document'], deck_target='pptx',
                              brand=CHOSEN, walkthrough=False, source_scope='supplied-only'))
        record = self.engine._load(root)
        found = self.engine._survey(root, record)
        self.assertEqual(drafts.start_minutes(root, record, found),
                         round(6 + 1 + 3 + 8 * 1.25))

    def test_a_desk_run_keeps_how_long_its_steps_took_here(self):
        self.saved_started(title='Saved restarts', levels=['101'])
        self.assertFalse(drafts.times().exists(), 'a saved training keeps no times')
        self.desk(levels=['101'], materials=['document', 'brief'])
        kept = json.loads(drafts.times().read_text(encoding='utf-8'))
        self.assertEqual(sorted(kept), ['blueprint', 'brief', 'document', 'research'])

    def test_what_keeps_a_ready_training_from_its_index_is_named(self):
        path = self.desk(levels=['101'], materials=['brief'])
        root = Path(path)
        # The brief typed over and accepted on the desk: its check fails.
        typed = self.base / 'brief.md'
        typed.write_text('# Brief\n\nNot a brief yet.\n', encoding='utf-8')
        workspace.save(root, 'brief@101', source=typed, edit=True, via='save')
        workspace.accept_desk(root, 'brief@101')
        view = self.get('drafts', path=path)
        brief = next(card for card in view['cards'] if card['name'] == 'brief@101')
        self.assertTrue(brief['checks']['problems'])
        self.assertEqual(view['needs'], [])
        marked = self.post('drafts/level-ready', {
            'path': path, 'level': '101',
            'seen': {card['name']: card['seen'] for card in view['cards']}})
        self.assertIsNone(marked['stopped'])
        self.assertFalse((Path(path) / pipeline.INDEX).is_file())
        self.assertEqual({card['state'] for card in marked['cards']}, {'ready'})
        # Nothing is a draft, and still no index: why is said.
        self.assertEqual(marked['needs'], ["The level 101 brief's sections need fixing."])
        for line in marked['needs']:
            for word in FORBIDDEN:
                self.assertNotIn(word, line.lower())

    def test_a_part_is_typed_restored_and_shared_on_the_page(self):
        path = self.desk(levels=['101'], materials=['document'])
        name = 'document@101'
        card = self.get('drafts/card', path=path, name=name)
        self.assertEqual((card['name'], card['state'], card['label']),
                         (name, 'draft', 'the level 101 learner guide'))
        self.assertIsInstance(card['revision'], int)
        self.assertEqual(sorted(card['sections'][0]), ['covers', 'heading', 'id', 'locked',
                                                       'text'])
        sources = next(part for part in card['sections'] if part['heading'] == 'Sources')
        self.assertTrue(sources['locked'])
        summary = next(part for part in card['sections'] if part['heading'] == 'Summary')
        first, commits = summary['text'], self.log()
        sent = {'path': path, 'name': name, 'part': summary['id'], 'session': 'ab12'}
        saved = self.post('drafts/save', {**sent, 'seen': card['revision'], 'text': 'One.'})
        self.assertEqual(saved['revision'], card['revision'] + 1)
        self.assertEqual(next(part for part in saved['sections']
                              if part['id'] == summary['id'])['text'], 'One.')
        self.assertTrue(saved['desk']['cards'])
        # A form opened before the change is told to reload; Sources is never typed in.
        said = self.post('drafts/save', {**sent, 'seen': card['revision'], 'text': 'Two.',
                                         'session': 'cd34'}, 409)
        self.assertEqual(said['error'], 'This draft changed since you opened it. Reload to '
                                        'see the latest.')
        said = self.post('drafts/save', {**sent, 'part': sources['id'],
                                         'seen': saved['revision'], 'text': '1. Nothing.'}, 409)
        self.assertEqual(said['error'], drafts.LOCKED)
        self.assertEqual(self.post('drafts/save', {**sent, 'seen': saved['revision'],
                                                   'text': 7}, 400)['error'],
                         'Give text as text.')
        found = self.get('drafts/versions', path=path, name=name, part=summary['id'])
        self.assertEqual([(one['source'], one['label'], one['text'])
                          for one in found['versions']], [('save', 'Saved', first)])
        self.assertEqual(found['sources'], drafts.SOURCE_WORDS)
        restored = self.post('drafts/restore', {**sent, 'seen': saved['revision'],
                                                'index': 0})
        self.assertEqual(next(part for part in restored['sections']
                              if part['id'] == summary['id'])['text'], first)
        self.assertEqual(self.log(), commits, 'typing and restoring wait to be committed')
        self.assertEqual(self.post('drafts/share', {'path': path}), {'committed': True})
        self.assertEqual(self.log(), [
            *commits, 'Rolling restarts: edit the level 101 learner guide on the desk'])
        self.assertEqual(self.post('drafts/share', {'path': path}), {'committed': False})
        # A long part is one save, beyond what other changes may carry.
        long = ' '.join(['Capacity'] * 12_000)
        self.post('drafts/save', {**sent, 'seen': restored['revision'], 'text': long})

    def test_a_save_the_desk_cannot_accept_is_still_saved(self):
        path = self.desk(levels=['101'], materials=['document'])
        name = 'document@101'
        card = self.get('drafts/card', path=path, name=name)
        summary = next(part for part in card['sections'] if part['heading'] == 'Summary')
        with mock.patch.object(workspace, 'accept_desk',
                               side_effect=WorkspaceError('Approve the plan first.')):
            saved = self.post('drafts/save', {'path': path, 'name': name,
                                              'part': summary['id'], 'seen': card['revision'],
                                              'text': 'Typed.', 'session': 'ab12'})
        self.assertEqual(saved['said'], 'Approve the plan first.')
        self.assertEqual(next(part for part in saved['sections']
                              if part['id'] == summary['id'])['text'], 'Typed.')
        self.assertIn('\n## Summary\n\nTyped.\n', (Path(path) / '101' / 'document.md')
                      .read_text(encoding='utf-8'))
        self.assertIn(Path(path), self.engine.pending_commit)


class DeskTeamTests(TeamCase):
    """A teammate reads the desk of a training someone else runs, and changes nothing."""

    PORT = 8765

    def ask(self, person, endpoint: str, sent=None, expect: int = 200, **params):
        made = getattr(person, 'page', None)
        if made is None:
            made = person.page = page.RunnerPage(self.PORT, person.engine)
        headers = Message()
        headers['Host'] = f'127.0.0.1:{self.PORT}'
        headers[desk.TOKEN_HEADER] = made.token
        target = f'/api/{endpoint}' + (f'?{urlencode(params)}' if params else '')
        body = None
        if sent is not None:
            headers['Origin'] = f'http://127.0.0.1:{self.PORT}'
            headers['Content-Type'] = 'application/json'
            body = json.dumps(sent).encode()
        with self.be(person):
            try:
                status, _, data = made.answer(target, headers, 'POST' if body else 'GET', body)
                reply = json.loads(data)
            except desk.Refusal as refusal:
                status, reply = int(refusal.status), {'error': str(refusal)}
            except WorkspaceError as refusal:
                status, reply = 409, {'error': str(refusal)}
        self.assertEqual(int(status), expect, reply)
        return reply

    def test_a_teammate_reads_the_desk(self):
        with self.be(self.alex):
            root = self.start(flow='desk', levels=['101'], materials=['document'])
            self.engine.share()
        self.as_(self.blake, self.blake.engine.fetch)
        theirs = self.theirs(self.blake, root)
        view = self.ask(self.blake, 'drafts', path=str(theirs))
        self.assertFalse(view['team']['ours'])
        self.assertTrue(view['cards'])
        for card in view['cards']:
            with self.subTest(card=card['name']):
                self.assertEqual(card['actions'], ['download'])
        with self.be(self.blake), self.assertRaises(engines.Elsewhere) as caught:
            self.blake.engine.hold(theirs)
        name = 'document@101'
        for route, sent in (('source', {'files': [{'name': 'notes.txt', 'content': 'Tm90ZXM='}]}),
                            ('finish', {'name': name, 'tool': 'coverage'}),
                            *(("finish", {'name': name, 'tool': tool}) for tool in
                              ('sources', 'time', 'answers', 'humanize', 'level')),
                            ('apply', {'name': name, 'job': 'a' * 32, 'items': []}),
                            ('skip', {'name': name, 'job': 'a' * 32, 'items': []}),
                            ('update-all', {'level': '101'}),
                            ('stop-updates', {'chain': 'some-chain'}),
                            ('ready', {'name': name, 'seen': hashed(theirs, name)}),
                            ('level-ready', {'level': '101', 'seen': {}}),
                            ('update', {'name': name}),
                            ('keep', {'name': name, 'reason': 'Fine.', 'seen': 'x'}),
                            ('send', {'name': name}),
                            ('save', {'name': name, 'part': 'opening', 'seen': 1,
                                      'text': 'Typed.', 'session': 'ab12'}),
                            ('restore', {'name': name, 'part': 'opening', 'seen': 1,
                                         'index': 0}),
                            ('note', {'name': name, 'seen': 1, 'note': 'Change.'}),
                            ('revise', {'name': name, 'seen': 1, 'note': 'Change.'}),
                            ('selection', {'name': name, 'part': 'opening', 'seen': 1,
                                           'text': 'word', 'start': 0, 'action': 'shorten'}),
                            ('stop', {'job': 'unknown'}), ('retry', {'job': 'unknown'})):
            with self.subTest(route=route):
                said = self.ask(self.blake, f'drafts/{route}', {'path': str(theirs), **sent},
                                409)
                self.assertEqual(said['error'], str(caught.exception))
        session = workspace.load(theirs)
        self.assertEqual(workspace.person_statuses(theirs, session)[name], 'draft',
                         {key: ((session['artifacts'].get(key) or {}).get('built_from'),
                                workspace.inputs(theirs, session, key))
                          for key, status in workspace.statuses(theirs, session).items()
                          if status == 'stale'})

    def test_a_finished_desk_training_is_still_its_person_s(self):
        name = 'document@101'
        with self.be(self.alex):
            root = self.start(flow='desk', levels=['101'], materials=['document'])
            view = self.ask(self.alex, 'drafts', path=str(root))
            marked = self.ask(self.alex, 'drafts/level-ready', {
                'path': str(root), 'level': '101',
                'seen': {card['name']: card['seen'] for card in view['cards']}})
            self.assertIsNone(marked['stopped'])
            self.assertTrue((root / pipeline.INDEX).is_file())
            record = self.record(root)
            # A finished training has no driver, as always; its desk is still Alex's.
            self.assertIsNone(record['driver'])
            self.assertEqual(record['drafts']['finished_by']['name'], 'Alex')
            self.assertEqual(self.engine.view(root)['mine'], True)
            self.assertTrue(self.ask(self.alex, 'drafts', path=str(root))['team']['ours'])
            card = self.ask(self.alex, 'drafts/card', path=str(root), name=name)
            summary = next(part for part in card['sections'] if part['heading'] == 'Summary')
            saved = self.ask(self.alex, 'drafts/save', {
                'path': str(root), 'name': name, 'part': summary['id'],
                'seen': card['revision'], 'text': 'Typed after the end.', 'session': 'ab12'})
            self.assertEqual(saved['state'], 'draft')
            self.assertEqual(self.ask(self.alex, 'drafts/share', {'path': str(root)}),
                             {'committed': True})
            self.assertEqual(self.shared()[0],
                             'Rolling restarts: edit the level 101 learner guide on the desk')
            self.assertIsNone(self.record(root)['driver'])
        self.as_(self.blake, self.blake.engine.fetch)
        theirs = self.theirs(self.blake, root)
        self.assertFalse(self.ask(self.blake, 'drafts', path=str(theirs))['team']['ours'])
        card = self.ask(self.blake, 'drafts/card', path=str(theirs), name=name)
        said = self.ask(self.blake, 'drafts/save', {
            'path': str(theirs), 'name': name, 'part': card['sections'][0]['id'],
            'seen': card['revision'], 'text': 'Typed by a teammate.'}, 409)
        self.assertTrue(said['error'].startswith(
            'Alex has been running this training from another computer since '), said)
        said = self.ask(self.blake, 'drafts/ready', {'path': str(theirs), 'name': name,
                                                     'seen': hashed(theirs, name)}, 409)
        self.assertTrue(said['error'].startswith('Alex has been running this training'))
        # Nor may a teammate delete it while it is still its person's.
        leaving = self.as_(self.blake, self.blake.engine.leaving, theirs)
        self.assertEqual((leaving['may'], leaving['why']), (False, engines.NOT_YOURS.format(
            name='Alex')))
        # Handed over, it is nobody's, and says who handed it over.
        with self.be(self.alex):
            self.engine.drive(root, 'hand-over')
        self.assertEqual(self.shared()[0], 'Rolling restarts: Alex hands this training over')
        self.assertNotIn('finished_by', self.record(root)['drafts'])

    def finished(self, title='Rolling restarts', materials=None) -> Path:
        """A desk training of Alex's, every material marked ready and its index written,
        shared with the team."""
        with self.be(self.alex):
            root = self.start(flow='desk', levels=['101'], materials=materials or ['document'],
                              title=title)
            view = self.ask(self.alex, 'drafts', path=str(root))
            self.ask(self.alex, 'drafts/level-ready', {
                'path': str(root), 'level': '101',
                'seen': {card['name']: card['seen'] for card in view['cards']}})
            self.assertTrue((root / pipeline.INDEX).is_file())
            self.engine.share()
        return root

    def test_a_finished_desk_training_taken_by_a_teammate_stops_here(self):
        root, name = self.finished(), 'document@101'
        with self.be(self.alex):
            card = self.ask(self.alex, 'drafts/card', path=str(root), name=name)
            self.ask(self.alex, 'drafts/save', {
                'path': str(root), 'name': name, 'part': card['sections'][0]['id'],
                'seen': card['revision'], 'text': 'Typed and never shared.'})
            self.engine.commit_typing(closing=True)   # committed here, not shared
            mine = self.git('rev-parse', 'HEAD')
        self.assertNotEqual(self.shared()[0],
                            'Rolling restarts: edit the level 101 learner guide on the desk')
        self.as_(self.blake, self.blake.engine.fetch)
        with self.be(self.blake):
            self.assertTrue(self.blake.engine.drive(self.theirs(self.blake, root),
                                                    'take')['mine'])
        self.assertEqual(self.shared()[0], 'Rolling restarts: Blake takes this training')
        self.as_(self.alex, self.engine.fetch)
        view = self.as_(self.alex, self.engine.view, root)
        self.assertEqual((view['mine'], view['taken']['by']), (False, 'Blake'))
        self.assertIn('Blake took this training over', view['notice'])
        self.assertEqual([self.git('rev-parse', ref) for ref in view['kept']], [mine],
                         "Alex's unshared work is set aside, not put on top of Blake's")
        self.assertEqual(self.git('rev-parse', 'HEAD'),
                         self.git('rev-parse', 'main', repo=self.remote))

    def test_a_card_is_read_by_its_own_route(self):
        root, name = self.finished(), 'document@101'
        with self.be(self.alex):
            self.assertEqual(self.ask(self.alex, 'drafts/card', path=str(root), name=name,
                                      expect=200)['name'], name)
            self.assertEqual(self.ask(self.alex, 'drafts/card', path=str(root), name='',
                                      expect=400)['error'], 'Give one name.')
            self.assertEqual(self.ask(self.alex, 'drafts/card', path=str(root),
                                      expect=400)['error'], 'Give one name.')
            self.assertNotIn('sections', self.ask(self.alex, 'drafts', path=str(root),
                                                  name=name))

    def test_takeover_sets_aside_uncommitted_typing_with_its_history(self):
        for earlier_commit in (False, True):
            with self.subTest(earlier_commit=earlier_commit):
                root, name = self.finished(title=f'Pending {earlier_commit}'), 'document@101'
                with self.be(self.alex):
                    card = self.engine.draft_card(root, name)
                    part = card['sections'][0]['id']
                    if earlier_commit:
                        card = self.engine.draft_save(root, name, part, card['revision'],
                                                      'An earlier local edit.', 'earlier')
                        self.engine.commit_typing(closing=True)
                    self.engine.draft_save(root, name, part, card['revision'],
                                           'Pending typing belongs to Alex.', 'pending')
                    session = workspace.load(root)
                    event = next(event for event in reversed(session['events'])
                                 if event['event'] == 'save' and event['artifact'] == name)
                    file = workspace.artifact(root, session, name)['file']
                self.as_(self.blake, self.blake.engine.fetch)
                self.as_(self.blake, self.blake.engine.drive, self.theirs(self.blake, root),
                         'take')
                with self.be(self.alex):
                    report = self.engine.fetch()
                    self.assertTrue(report['reached'], report)
                    self.engine.commit_typing(closing=True)
                    view = self.engine.view(root)
                    self.assertFalse(view['mine'])
                    self.assertNotIn('Pending typing belongs to Alex.',
                                     (root / file).read_text(encoding='utf-8'))
                    self.assertTrue(view['kept'], 'the local edit is recoverable')
                    kept = view['kept'][-1]
                    prefix = root.relative_to(self.space.repo)
                    self.assertIn('Pending typing belongs to Alex.',
                                  self.git('show', f'{kept}:{prefix / file}'))
                    saved = json.loads(self.git('show', f'{kept}:{prefix}/.training-studio/session.json'))
                    self.assertIn(event, saved['events'])
                # The next fixture starts under Alex again; leave this training Blake's.

    def test_a_finished_saved_training_must_be_claimed_before_opening(self):
        from stand_ins.research import saved_queue
        self.research = saved_queue()
        with self.be(self.alex):
            root = self.saved_start(levels=['101'], materials=['document'])
            self.to_end(root)
            self.assertEqual(self.engine.view(root)['state'], 'done')
            self.engine.share()
        self.as_(self.blake, self.blake.engine.fetch)
        theirs = self.theirs(self.blake, root)
        detail = self.ask(self.blake, 'training', path=str(theirs))
        run = self.ask(self.blake, 'run', path=str(theirs))
        self.assertFalse(detail['run']['can_open_desk'])
        self.assertFalse(run['can_open_desk'])
        self.ask(self.blake, 'drafts/open', {'path': str(theirs)}, expect=409)
        claimed = self.ask(self.blake, 'drive', {'path': str(theirs), 'action': 'take'})
        self.assertTrue(claimed['can_open_desk'])
        opened = self.ask(self.blake, 'drafts/open', {'path': str(theirs)})
        self.assertEqual(opened['flow'], 'desk')
        self.assertEqual(self.ask(self.blake, 'run', path=str(theirs))['flow'], 'desk')

    def test_a_pr1_finished_training_requires_an_explicit_claim_and_keeps_local_edits(self):
        root, name = self.finished(), 'document@101'
        with self.be(self.alex):
            record = self.record(root)
            record['drafts'].pop('finished_by')
            self.engine._store(root, record)
            self.engine._commit(root, 'a finished training saved before desk ownership')
            self.engine.share()
            card = self.engine.draft_card(root, name)
            with self.assertRaises(WorkspaceError):
                self.engine.draft_save(root, name, card['sections'][0]['id'],
                                       card['revision'], 'Unclaimed edit.')
            self.assertFalse(self.engine.leaving(root)['may'],
                             'an unclaimed legacy desk also requires a claim before deletion')
            file = root / workspace.artifact(root, workspace.load(root), name)['file']
            source = self.base / 'legacy-edit.md'
            source.write_text(file.read_text(encoding='utf-8') + '\nA saved local edit.\n',
                              encoding='utf-8')
            workspace.save(root, name, source=source, edit=True, via='save',
                           session_token='legacy')
            event = workspace.load(root)['events'][-1]
            self.engine.drive(root, 'take')
            self.assertTrue(self.engine.mine(root))
            kept = self.engine.view(root)['kept']
            self.assertTrue(kept, 'the explicit claim preserves earlier local work separately')
            prefix = root.relative_to(self.space.repo)
            saved = json.loads(self.git('show', f'{kept[-1]}:{prefix}/.training-studio/session.json'))
            self.assertIn(event, saved['events'])
            card = self.engine.draft_card(root, name)
            self.engine.draft_save(root, name, card['sections'][0]['id'], card['revision'],
                                   'Explicitly claimed edit.', 'claimed')
            self.engine.draft_share(root)
            self.assertIn('Explicitly claimed edit.',
                          (root / workspace.artifact(root, workspace.load(root), name)['file'])
                          .read_text(encoding='utf-8'))

    def test_takeover_waits_for_a_step_then_keeps_typing_and_discards_only_worker_output(self):
        root, name = self.finished(), 'document@101'
        with self.be(self.alex):
            (root / engines.IN_HAND).write_text('brief@101\n', encoding='utf-8')
            partial = root / 'half-made.md'
            partial.write_text('Half-made worker output.\n', encoding='utf-8')
            card = self.engine.draft_card(root, name)
            self.engine.draft_save(root, name, card['sections'][0]['id'], card['revision'],
                                   'Typing kept apart from the worker.', 'in-hand')
            file = workspace.artifact(root, workspace.load(root), name)['file']
        self.as_(self.blake, self.blake.engine.fetch)
        self.as_(self.blake, self.blake.engine.drive, self.theirs(self.blake, root), 'take')
        with self.be(self.alex):
            report = self.engine.fetch()
            self.assertFalse(report['reached'], report)
            self.assertTrue(partial.is_file(), 'Sync cannot replace an active worker output tree.')
            # The fixture has no live worker. Recover its validated typing, then
            # remove the known synthetic half-made output as that worker stops.
            self.engine._tidy()
            partial.unlink()
            report = self.engine.fetch()
            self.assertTrue(report['reached'], report)
            view = self.engine.view(root)
            self.assertEqual(view['taken']['by'], 'Blake')
            self.assertTrue(view['kept'])
            prefix = root.relative_to(self.space.repo)
            self.assertIn('Typing kept apart from the worker.',
                          self.git('show', f"{view['kept'][-1]}:{prefix / file}"))
            # A worker returning after the takeover may keep nothing over Blake's files.
            partial.write_text('Late worker output.\n', encoding='utf-8')
            with self.assertRaises(engines._Gone):
                self.engine._commit(root, 'a worker returned after takeover')
            self.assertFalse(partial.exists())
            self.assertNotIn('Typing kept apart from the worker.',
                             (root / file).read_text(encoding='utf-8'))
            self.assertEqual(self.git('status', '--porcelain'), '')

    def test_takeover_after_interleaved_saves_keeps_the_entire_audit(self):
        root = self.finished(materials=['document', 'brief'])
        with self.be(self.alex):
            for name, text in (('brief@101', 'First brief edit.'),
                               ('document@101', 'Guide edit.'),
                               ('brief@101', 'Second brief edit.')):
                card = self.engine.draft_card(root, name)
                self.engine.draft_save(root, name, card['sections'][0]['id'],
                                       card['revision'], text, text)
            events = workspace.load(root)['events']
        self.as_(self.blake, self.blake.engine.fetch)
        self.as_(self.blake, self.blake.engine.drive, self.theirs(self.blake, root), 'take')
        with self.be(self.alex):
            report = self.engine.fetch()
            self.assertTrue(report['reached'], report)
            kept = self.engine.view(root)['kept']
            self.assertTrue(kept)
            prefix = root.relative_to(self.space.repo)
            saved = json.loads(self.git('show', f'{kept[-1]}:{prefix}/.training-studio/session.json'))
            self.assertEqual(saved['events'], events)
            self.assertEqual(self.git('status', '--porcelain'), '')
