"""What may change a blog saved by the earlier step-by-step flow (saved_gate), walked.

Every page action and every command-line subcommand is run against stored saved blogs in four
states (one that opens on the desk, one read-only with nothing made, one finished, one whose
run record cannot be read). Each is on the allow-list for that state, or it refuses in plain
words and leaves every byte of the workspace (outside the runner's own records under
.blog-runs) as it was. An action read as reading only may run, and changes no saved blog.
An action or subcommand added without a decision fails here. Nothing reaches Google, a
provider or the network: sockets, programs other than git, Google tokens and the writing
worker are stubbed to refuse.
"""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import argparse
import base64
from contextlib import ExitStack, redirect_stderr, redirect_stdout
import inspect
import io
import json
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
from unittest.mock import patch

import advanced_tools
import blog_runner as runner
import desk
import desk_chat
import desk_migration
import import_jobs
import library_add
import management
import manuscript_editor
import saved_fixtures
import saved_gate
import shared_library
import studio
import team_workspace
from test_desk_team import TeamCase
from test_saved_states import SavedStateCase

SCRIPTS = Path(management.__file__).resolve().parent
REFUSALS = (saved_gate.SAVED_FLOW, saved_gate.NOT_RUNNING, saved_gate.NOTHING_TO_TAKE)

# The four states the walk takes: (fixture, what classify says of it).
STATES = {
    'opens-on-desk': ('draft-gate', 'migrates'),
    'nothing-made': ('brief-only', 'read-only'),
    'finished': ('finished-page', 'finished'),
    'unreadable': ('draft-gate-paused', 'read-only'),
}


def page_actions():
    """Every page action, read from the code that answers it."""
    source = (SCRIPTS / 'management.py').read_text()
    routes = set(re.findall(r"route == '([a-z0-9\-]+)'", source))
    for group in re.findall(r'route in \(([^)]*)\)', source):
        routes |= set(re.findall(r"'([a-z0-9\-]+)'", group))
    routes.discard('tool-action')
    editor = inspect.getsource(manuscript_editor.dispatch)
    routes |= {'editor-' + name for name in re.findall(r"action == '([a-z\-]+)'", editor)}
    for group in re.findall(r'action in \(([^)]*)\)', editor):
        routes |= {'editor-' + name for name in re.findall(r"'([a-z\-]+)'", group)}
    routes |= {'desk-' + name for name in desk.ROUTES}
    routes |= {'run-' + name for name in runner.PAGE_ACTIONS}
    team = inspect.getsource(team_workspace.action)
    named = set(re.findall(r"action == '([a-z]+)'", team))
    for group in re.findall(r'action in \(([^)]*)\)', team):
        named |= set(re.findall(r"'([a-z]+)'", group))
    routes |= {'team-' + name for name in named}
    routes |= set(shared_library.BROWSE) | {shared_library.TAKE} | set(import_jobs.ROUTES)
    routes |= set(re.findall(r"name == '([a-z\-]+)'", inspect.getsource(library_add.route)))
    tools = inspect.getsource(advanced_tools.dispatch)
    actions = set(re.findall(r"action == '([a-z\-]+)'", tools))
    for group in re.findall(r'action in \(\s*([^)]*)\)', tools):
        actions |= set(re.findall(r"'([a-z\-]+)'", group))
    return routes | {'tool-action:' + name for name in actions}


def subcommands():
    """Every command-line subcommand: key -> its parser."""

    def under(parser):
        for found in parser._actions:
            if isinstance(found, argparse._SubParsersAction):
                return found.choices
        return None

    found = {}
    for group, parser in under(studio.parser()).items():
        actions = under(parser)
        for action, sub in (actions or {None: parser}).items():
            found[group + (' ' + action if action else '')] = sub
    return found


def body(key, ident, ctx):
    """A request shaped as the page sends this action, about `ident`."""
    run, editor, record, moving = ctx['run'], ctx['editor'], ctx['record'], ctx['migration']
    operation = 'a' * 32
    doc = 'https://docs.google.com/document/d/synthetic-document/edit'
    if key.startswith('tool-action:'):
        action = key.split(':', 1)[1]
        extra = {
            'job-create': {'kind': 'repurpose', 'format': 'linkedin', 'words': 150},
            'job-apply': {'job': ctx['job'], 'confirmed': True},
            'job-control': {'job': ctx['job'], 'control': 'cancel'},
            'restore': {'confirmed': True, 'revision': 1},
            'variant-save': {'name': 'Shorter', 'content': '# T\n\nShorter.\n'},
            'interview-start': {'operation': operation},
            'interview-answer': {'answer': 'Yes.'},
            'voice-apply': {'profile': 'synthetic-voice', 'confirmed': True},
            'google-compare': {'url': doc},
            'google-accept': {'comparison': 'x', 'confirmed': True},
            'source-purpose': {'source': ident, 'purpose': 'material'},
            'profile-save': {'name': ident, 'guide': '# Guide'},
            'profile-retire': {'profile': ident, 'confirmed': True},
            'style-save': {'name': ident, 'guide': '# Kind'},
            'style-retire': {'style': ident, 'confirmed': True},
            'guide-discard': {'job': ident},
        }.get(action, {})
        shaped = {'action': action, 'id': ident, 'expected': editor, **extra}
        if action == 'guide-discard':
            shaped = {'action': action, 'job': ident}
        if action == 'job-discard':
            shaped = {'action': action, 'job': ctx['job']}
        return shaped
    if key.startswith('editor-'):
        return {
            'id': ident,
            'expected': editor,
            **{
                'editor-save': {'content': '# T\n\nNew text.\n'},
                'editor-proposals': {'proposals': []},
                'editor-apply-proposal': {'proposal': 'p1'},
                'editor-apply-selected': {'proposals': ['p1']},
                'editor-check': {'check': 'polish'},
                'editor-google-plan': {'url': doc},
                'editor-google-send': {'plan': 'x', 'confirmed': True},
            }.get(key, {}),
        }
    if key.startswith('run-'):
        return {'id': ident, 'expected': run, **({'request': 'x'} if key == 'run-changes' else {})}
    if key.startswith('team-') and key not in ('team-join', 'team-share-mode', 'team-sync'):
        return {'id': ident, 'expected': run, 'confirmed': True}
    if key == 'desk-migrate':
        return {'id': ident, 'expected': moving}
    if key == 'desk-open':
        return {'id': ident}
    if key == 'desk-create':
        return {'operation': operation, 'article': ident}
    if key.startswith('desk-'):
        return {'id': ident, 'seen': 1, 'part': 'title', 'text': 'Changed.', 'expected': run}
    if key.startswith('document-library'):
        if key == shared_library.TAKE:
            return {'operation': operation, 'picks': [{'id': ident, 'revision': 1}]}
        return {'id': ident}
    return {
        'analyze': {'id': ident, 'location': 'local', 'expected': 'x'},
        'curate': {'id': ident, 'location': 'local', 'expected': 'x', 'confirmed': True},
        'blog-delete': {'id': ident, 'expected': run, 'title': ctx['title']},
        'blog-restore': {'id': ident},
        'brand-configure': {'brand': ident},
        'brand-install': {'brand': ident},
        'files-intake': {
            'operation': operation,
            'folder': '/nonexistent',
            'local': False,
            'taken': [ident],
        },
        'geo-report-again': {'id': ident, 'operation': operation},
        'geo-report-desk': {'id': ident, 'operation': operation},
        'geo-report-google-plan': {'id': ident, 'operation': operation},
        'geo-report-google-send': {'id': ident, 'plan': 'x', 'confirmed': True},
        'geo-report-start': {'operation': operation, 'published': ident},
        'google-copy': {'url': doc, 'id': ident, 'confirmed': True},
        'google-open': {'id': ident, 'expected': run, 'confirmed': True},
        'google-preview': {'url': doc, 'operation': operation, 'article': ident},
        'google-start': {'url': doc, 'operation': operation, 'article': ident},
        'import-stop': {'job': ident},
        'intake-draft': {'patch': {'title': ident}},
        'library-add': {'operation': operation, 'links': [], 'article': ident},
        'library-add-author': {'id': ident, 'author': 'Avery'},
        'library-add-preview': {'operation': operation, 'article': ident},
        'library-add-samples': {'ids': [ident]},
        'library-author-different': {'id': ident},
        'library-author-same': {'id': ident},
        'library-import': {'preview': ident},
        'library-preview': {'collection': ident},
        'library-selection': {'action': 'blog', 'ids': [ident]},
        'library-voices': {'ids': [ident]},
        'memory': {'kind': 'note', 'title': 'x', 'body': 'y', 'scope': 'article', 'scope_key': ident},
        'published-find-text': {'operation': operation, 'published': ident},
        'published-find-text-stop': {'operation': ident},
        'published-preview': {'item': ident, 'location': 'local'},
        'refresh': {'id': ident},
        'research-site': {'site': ident},
        'research-sources': {'action': 'list', 'id': ident},
        'resume': {'item': ident},
        'retry-sync': {'id': ident},
        'run-settings': {'id': ident},
        'schedule': {'id': ident, 'expected': record, 'owner': 'Probe'},
        'source-role': {'id': ident, 'role': 'facts'},
        'team-join': {'repository': ident},
        'team-share-mode': {'share': 'decision', 'shared_before': {'share': ident}},
        'team-sync': {'id': ident},
        'upload': {
            'operation': operation,
            'files': [
                {
                    'filename': 'notes.md',
                    'content': base64.b64encode(b'Notes.').decode(),
                    'purpose': 'material',
                }
            ],
            'purpose': 'material',
            'keep': False,
        },
        'voice-links-import': {'operation': operation, 'links': ident},
        'voice-links-preview': {'links': ident},
    }[key]


def argv(sub, ident, file):
    """Arguments for one subcommand that name `ident` wherever a blog may be named."""
    words = []
    for found in sub._actions:
        if isinstance(found, (argparse._HelpAction, argparse._SubParsersAction)):
            continue
        if found.dest in ('root', 'compact', 'format'):
            continue
        if not found.option_strings:
            words.append('x')
            continue
        flag = found.option_strings[0]
        if found.dest in ('id', 'article'):
            words += [flag, ident]
        elif not found.required:
            continue
        elif found.nargs == 0:
            words.append(flag)
        elif found.choices:
            words += [flag, list(found.choices)[0]]
        elif found.dest in ('revision', 'expected_revision', 'limit', 'retry'):
            words += [flag, '1']
        else:
            words += [flag, str(file)]
    return words


def names_a_blog(sub):
    return any(found.dest in ('id', 'article') for found in sub._actions)


class Offline(ExitStack):
    """Nothing leaves this computer and nothing writes for real: no sockets, no programs but
    git, no Google token, no writing worker, no runner or desk job started."""

    def __enter__(self):
        super().__enter__()
        real_run, real_popen = subprocess.run, subprocess.Popen

        def only_git(real):
            def call(command, *args, **kwargs):
                program = command[0] if isinstance(command, (list, tuple)) else str(command)
                if Path(str(program)).name != 'git':
                    raise OSError('No program runs in this test.')
                return real(command, *args, **kwargs)

            return call

        def refused(*args, **kwargs):
            raise OSError('The network is off in this test.')

        for target in (
            patch.object(socket.socket, 'connect', refused),
            patch('socket.create_connection', refused),
            patch('subprocess.run', only_git(real_run)),
            patch('subprocess.Popen', only_git(real_popen)),
            patch('google_drive.token', side_effect=ValueError('No Google in this test.')),
            patch('blog_worker.generate', side_effect=ValueError('No assistant in this test.')),
            patch.object(runner.Engine, 'start', side_effect=ValueError('No runner here.')),
            patch('desk_jobs.begin', side_effect=ValueError('No desk job here.')),
        ):
            self.enter_context(target)
        return self


class WalkCase(SavedStateCase):
    def load_all(self):
        """The four saved blogs, loaded afresh: {state: ident}."""
        found = {}
        for name, (fixture, _) in STATES.items():
            found[name] = saved_fixtures.load(self.root, fixture)
        broken = studio.inside(self.root, 'articles', found['unreadable']) / runner.STATE
        broken.write_text('{not json')
        return found

    def outside_runner(self):
        """Every byte of the workspace but the runner's own records and the write lock."""
        return {
            key: value for key, value in self.tree().items() if not key.startswith('.blog-runs/')
        }

    def blog(self, ident):
        directory = studio.inside(self.root, 'articles', ident)
        return {
            str(path.relative_to(directory)): path.read_bytes()
            for path in directory.rglob('*')
            if path.is_file()
        }

    def contexts(self, shown):
        found = {}
        for name, ident in shown.items():
            ctx = {'run': 'x', 'editor': 'x', 'record': 'x', 'migration': 'x', 'title': 'x'}
            try:
                ctx['run'] = runner.survey(self.root, ident)['expected']
            except ValueError:
                pass
            try:
                ctx['editor'] = manuscript_editor.read(self.root, ident)['expected']
            except ValueError:
                pass
            directory = studio.inside(self.root, 'articles', ident)
            try:
                ctx['record'] = studio.digest(studio.record_bytes(directory, 'articles'))
                ctx['title'] = json.loads((directory / 'session.json').read_text())['title']
            except (ValueError, OSError):
                pass
            ctx['migration'] = desk_chat.migration_preview(self.root, ident)['expected'] or 'x'
            ctx['job'] = 'c' * 32
            found[name] = ctx
        return found

    def job(self, ident):
        """A ready repurpose task of this blog, as a finished tool job leaves it."""
        request = {'kind': 'repurpose', 'payload': {}, 'basis': 'synthetic'}
        studio.write_json(
            self.root / '.blog-runs/tools' / ('c' * 32 + '.json'),
            {
                'id': 'c' * 32,
                **request,
                'metadata': {'article': ident},
                'fingerprint': studio.digest(json.dumps(request, sort_keys=True).encode()),
                'guidance': '',
                'status': 'ready',
                'created_at': studio.now(),
                'attempts': 1,
                'engine': 'codex',
                'seconds': 60,
                'result': {'content': 'Synthetic channel copy.', 'notes': ''},
                'error': '',
            },
        )


class DecisionTests(WalkCase):
    def test_every_page_action_and_subcommand_has_a_decision(self):
        actions = page_actions()
        self.assertEqual(set(saved_gate.PAGE) - actions, set(), 'decisions for no action')
        self.assertEqual(actions - set(saved_gate.PAGE), set(), 'actions with no decision')
        commands = subcommands()
        self.assertEqual(set(commands) ^ set(saved_gate.COMMANDS), set())
        # A subcommand that cannot name a blog reads, or works on the workspace only.
        for key, sub in commands.items():
            if not names_a_blog(sub):
                self.assertIn(saved_gate.COMMANDS[key], (saved_gate.READS,), key)

    def test_the_states_walked(self):
        shown = self.load_all()
        for name, (_, outcome) in STATES.items():
            with self.subTest(state=name):
                self.assertEqual(desk_migration.classify(self.root, shown[name])['outcome'], outcome)
        self.assertEqual(saved_gate.SAVED_FLOW, runner.SAVED_FLOW)
        self.assertEqual(saved_gate.state(self.root, shown['finished']), 'finished')
        for name in ('opens-on-desk', 'nothing-made', 'unreadable'):
            self.assertEqual(saved_gate.state(self.root, shown[name]), 'unfinished')


class PageWalkTests(WalkCase):
    def test_every_page_action_against_saved_blogs(self):
        actions = sorted(page_actions())
        ctx = self.contexts(self.load_all())
        seen = []
        for key in actions:
            for name in STATES:
                shown = self.load_all()
                ident = shown[name]
                if key.startswith('tool-action:'):
                    self.job(ident)
                data = body(key, ident, ctx[name])
                said = saved_gate.state(self.root, ident)
                decision = saved_gate.PAGE[key]
                expected = saved_gate.refusal(self.root, decision, ident, said)
                before, blogs = self.outside_runner(), {i: self.blog(i) for i in shown.values()}
                outcome = None
                with self.subTest(action=key, state=name), Offline():
                    try:
                        route = 'tool-action' if key.startswith('tool-action:') else key
                        management.dispatch(self.root, route, data)
                    except Exception as error:  # noqa: BLE001  (each outcome is checked below)
                        outcome = error
                    if expected:
                        # Refused in plain words, and nothing outside the runner's records changed.
                        self.assertIsInstance(outcome, saved_gate.Refused, key)
                        self.assertEqual(str(outcome), expected)
                        self.assertEqual(management.failure(outcome, True), (400, {'error': expected}))
                        self.assertEqual(self.outside_runner(), before, key)
                    elif decision == saved_gate.READS:
                        # It reads, or makes new work: no saved blog changed.
                        self.assertEqual({i: self.blog(i) for i in shown.values()}, blogs, key)
                seen.append((key, name))
        self.assertEqual(len(seen), len(actions) * len(STATES))


class CommandWalkTests(WalkCase):
    def run_command(self, words):
        out, err = io.StringIO(), io.StringIO()
        with (
            patch.object(sys, 'argv', ['studio.py', '--root', str(self.root), *words]),
            redirect_stdout(out),
            redirect_stderr(err),
        ):
            code = studio.main()
        return code, out.getvalue(), err.getvalue()

    def test_every_subcommand_against_saved_blogs(self):
        file = self.base / 'walk-input.md'
        file.write_text('# Title\n\nA paragraph.\n')
        walked = 0
        for key, sub in sorted(subcommands().items()):
            if not names_a_blog(sub):
                continue
            decision = saved_gate.COMMANDS[key]
            for name in STATES:
                shown = self.load_all()
                ident = shown[name]
                expected = saved_gate.refusal(
                    self.root, decision, ident, saved_gate.state(self.root, ident)
                )
                before, blogs = self.outside_runner(), {i: self.blog(i) for i in shown.values()}
                with self.subTest(command=key, state=name), Offline():
                    code, _, err = self.run_command([*key.split(), *argv(sub, ident, file)])
                    if expected:
                        self.assertEqual((code, err), (1, 'Blog Studio: ' + expected + '\n'), key)
                        self.assertEqual(self.outside_runner(), before, key)
                    elif decision == saved_gate.READS:
                        self.assertEqual({i: self.blog(i) for i in shown.values()}, blogs, key)
                    self.assertNotIn('Traceback', err)
                walked += 1
        self.assertGreater(walked, 80)


class DefectTests(WalkCase):
    """The review's findings, each against the stored saved blogs."""

    def unchanged(self, call):
        before = self.outside_runner()
        with Offline(), self.assertRaises(saved_gate.Refused) as refused:
            call()
        self.assertEqual(self.outside_runner(), before)
        return str(refused.exception)

    def test_the_editor_and_article_commands_write_only_a_finished_saved_blog(self):
        shown = self.load_all()
        for name in ('opens-on-desk', 'nothing-made'):
            ident = shown[name]
            editor = manuscript_editor.read(self.root, ident)['expected']
            for action, extra in (
                ('editor-save', {'content': '# T\n\nNew.\n'}),
                ('editor-proposals', {'proposals': []}),
            ):
                with self.subTest(state=name, action=action):
                    said = self.unchanged(
                        lambda: management.dispatch(
                            self.root, action, {'id': ident, 'expected': editor, **extra}
                        )
                    )
                    self.assertEqual(said, saved_gate.SAVED_FLOW)
            file = self.base / 'draft.md'
            file.write_text('# T\n\nA draft.\n')
            for words in (
                ('save', '--kind', 'draft', '--file', str(file)),
                ('rename', '--title', 'Renamed'),
                ('note', '--kind', 'decision', '--text', 'A note.'),
            ):
                with self.subTest(state=name, command=words[0]):
                    self.unchanged(lambda: self.command('article', words[0], '--id', ident, *words[1:]))
        # A finished one is edited as before.
        ident = shown['finished']
        self.command('article', 'rename', '--id', ident, '--title', 'Renamed')
        editor = manuscript_editor.read(self.root, ident)
        management.dispatch(
            self.root,
            'editor-save',
            {'id': ident, 'expected': editor['expected'], 'content': editor['content'] + '\nMore.\n'},
        )

    def command(self, *words):
        args = studio.parser().parse_args(['--root', str(self.root), *words])
        return studio.article_command(self.root, args)

    def test_the_editorial_decision_changes_only_a_finished_saved_blog(self):
        shown = self.load_all()
        for name in ('opens-on-desk', 'nothing-made'):
            ident = shown[name]
            directory = studio.inside(self.root, 'articles', ident)
            record = studio.digest(studio.record_bytes(directory, 'articles'))
            for values in ({'owner': 'Probe'}, {'stage': 'published', 'confirm_stage': True}):
                with self.subTest(state=name, values=values):
                    self.unchanged(
                        lambda: management.dispatch(
                            self.root, 'schedule', {'id': ident, 'expected': record, **values}
                        )
                    )
        ident = shown['finished']
        directory = studio.inside(self.root, 'articles', ident)
        record = studio.digest(studio.record_bytes(directory, 'articles'))
        management.dispatch(self.root, 'schedule', {'id': ident, 'expected': record, 'owner': 'Probe'})

    def test_pause_and_stop_act_only_on_a_step_running_here(self):
        shown = self.load_all()
        research = saved_fixtures.load(self.root, 'research-findings')
        for ident in (shown['opens-on-desk'], shown['finished'], research, shown['unreadable']):
            expected = 'x'
            try:
                expected = runner.survey(self.root, ident)['expected']
            except ValueError:
                pass
            for action in ('run-pause', 'run-stop'):
                with self.subTest(ident=ident, action=action):
                    local = self.root / '.blog-runs' / (ident + '.json')
                    kept = local.read_bytes() if local.exists() else None
                    said = self.unchanged(
                        lambda: management.dispatch(
                            self.root, action, {'id': ident, 'expected': expected}
                        )
                    )
                    self.assertEqual(said, saved_gate.NOT_RUNNING)
                    self.assertEqual(local.read_bytes() if local.exists() else None, kept)
        # A step running now is stopped, as before.
        ident = shown['opens-on-desk']
        engine = runner.engine(self.root)
        engine.current = ident
        try:
            expected = runner.survey(self.root, ident)['expected']
            management.dispatch(self.root, 'run-stop', {'id': ident, 'expected': expected})
            self.assertTrue(engine.stop.is_set())
        finally:
            engine.current = None
            engine.stop.clear()

    def test_a_tool_job_of_an_unfinished_saved_blog_is_not_applied(self):
        shown = self.load_all()
        ident = shown['opens-on-desk']
        self.job(ident)
        said = self.unchanged(
            lambda: management.dispatch(
                self.root,
                'tool-action',
                {'action': 'job-apply', 'job': 'c' * 32, 'confirmed': True},
            )
        )
        self.assertEqual(said, saved_gate.SAVED_FLOW)

    def ready_task(self, ident, kind='repurpose', job='c' * 32):
        """A ready tool task of this blog, as a finished tool job saves it."""
        import tool_jobs

        request = {
            'kind': kind,
            'payload': {},
            'basis': 'synthetic',
            'metadata': {'article': ident},
        }
        tool_jobs.write(
            self.root,
            {
                'id': job,
                **request,
                'fingerprint': studio.digest(json.dumps(request, sort_keys=True).encode()),
                'guidance': '',
                'status': 'ready',
                'created_at': studio.now(),
                'finished_at': studio.now(),
                'attempts': 1,
                'engine': 'codex',
                'seconds': 60,
                'result': {'content': 'Synthetic channel copy.', 'notes': ''},
                'error': '',
            },
        )
        return self.root / '.blog-runs/tools' / (job + '.json')

    def test_a_ready_task_of_an_unfinished_saved_blog_can_be_discarded(self):
        import tool_jobs

        ident = self.load_all()['opens-on-desk']
        self.ready_task(ident)
        # It waits on its task, which can be neither applied nor cancelled.
        said = desk_migration.saved_record(self.root, ident)['saved_record']
        self.assertEqual((said['outcome'], said['clear']), ('wait', 'job'))
        self.assertEqual(said['job']['status'], 'ready')
        before, blog = self.outside_runner(), self.blog(ident)
        with Offline():
            found = management.dispatch(
                self.root, 'tool-action', {'action': 'job-discard', 'job': 'c' * 32}
            )
        self.assertEqual((found['status'], found['result']), ('cancelled', None))
        self.assertTrue(found['discarded_at'])
        # Only the task's own record changed; the saved blog is as it was, and opens on the desk.
        self.assertEqual(self.outside_runner(), before)
        self.assertEqual(self.blog(ident), blog)
        self.assertEqual(desk_migration.classify(self.root, ident)['outcome'], 'migrates')
        # A discarded result is gone for good: not tried again, not discarded again (the blog
        # no longer waits on it, so the guard refuses).
        with self.assertRaisesRegex(ValueError, 'cannot be retried'):
            tool_jobs.control(self.root, 'c' * 32, 'retry', runner.engine(self.root))
        with self.assertRaises(saved_gate.Refused):
            management.dispatch(
                self.root, 'tool-action', {'action': 'job-discard', 'job': 'c' * 32}
            )

    def test_a_ready_task_of_any_other_saved_blog_is_not_discarded(self):
        shown = self.load_all()
        for name in ('nothing-made', 'finished', 'unreadable'):
            with self.subTest(state=name):
                task = self.ready_task(shown[name])
                kept = task.read_bytes()
                said = self.unchanged(
                    lambda: management.dispatch(
                        self.root, 'tool-action', {'action': 'job-discard', 'job': 'c' * 32}
                    )
                )
                self.assertEqual(said, saved_gate.SAVED_FLOW)
                self.assertEqual(task.read_bytes(), kept)
                task.unlink()
        # The one allowance is for the blog that waits on that very task.
        self.assertTrue(saved_gate.waits_on_ready_task(self.root, shown['opens-on-desk']) is False)
        self.ready_task(shown['opens-on-desk'])
        self.assertTrue(saved_gate.waits_on_ready_task(self.root, shown['opens-on-desk']))
        self.assertEqual(
            saved_gate.refusal(
                self.root, saved_gate.WAITING, shown['opens-on-desk'], 'unfinished'
            ),
            None,
        )

    def test_start_up_settles_a_step_of_a_blog_unreadable_or_gone(self):
        from studio_core import sync_guard

        for damage in ('session', 'gone'):
            with self.subTest(damage=damage):
                ident = saved_fixtures.load(self.root, 'draft-gate-working')
                directory = studio.inside(self.root, 'articles', ident)
                if damage == 'session':
                    (directory / 'session.json').write_text('{not json')
                else:
                    shutil.rmtree(directory)
                self.assertTrue(sync_guard.worker_in_progress(self.root))
                engine = runner.Engine(self.root)
                engine.closed.set()
                with patch.object(runner.Engine, 'once', side_effect=AssertionError('work')):
                    engine.serve()
                self.assertFalse(sync_guard.worker_in_progress(self.root))
                local = studio.read_json(self.root / '.blog-runs' / (ident + '.json'))
                self.assertEqual((local['enabled'], local['status']), (False, 'stopped'))
                if damage == 'session':
                    self.assertEqual((directory / 'session.json').read_text(), '{not json')
                (self.root / '.blog-runs' / (ident + '.json')).unlink()


class TeamDefectTests(TeamCase):
    """Take, Hand over and publishing a saved blog in a team repository: the files, the git
    log and the tags before and after."""

    def load(self, state):
        tree = saved_fixtures.FIXTURES / state
        (ident,) = [path.name for path in (tree / 'articles').iterdir()]
        for path in sorted(tree.rglob('*')):
            if path.is_file():
                relative = path.relative_to(tree)
                if relative.parts[0] == 'articles':
                    relative = Path(*relative.parts[1:])
                target = self.root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
        from studio_sync import support

        support.git(self.found.repo, 'add', '-A')
        support.git(self.found.repo, 'commit', '-qm', 'load ' + state)
        support.git(self.found.repo, 'push', '-q', 'origin', 'HEAD:main')
        return ident

    def snap(self):
        from studio_sync import support

        repo = self.found.repo
        files = {
            str(path.relative_to(repo)): path.read_bytes()
            for path in repo.rglob('*')
            if path.is_file()
            and '.git' not in path.relative_to(repo).parts
            and path.name != '.studio.lock'
            and '.blog-runs' not in path.relative_to(repo).parts
        }
        return (
            files,
            support.git(repo, 'log', '--all', '--format=%H %s'),
            support.git(repo, 'tag'),
            support.git(self.remote, 'log', '--all', '--format=%H %s'),
            support.git(self.remote, 'tag'),
        )

    def act(self, ident, action):
        found = runner.survey(self.root, ident)
        return management.dispatch(
            self.root, 'team-' + action, {'id': ident, 'expected': found['expected'], 'confirmed': True}
        )

    def refused(self, ident, action, words):
        before = self.snap()
        with self.assertRaises(saved_gate.Refused) as raised:
            self.act(ident, action)
        self.assertEqual(str(raised.exception), words)
        self.assertEqual(self.snap(), before)

    def test_take_only_to_open_on_the_desk_never_hand_over_publish_only_finished(self):
        nothing = self.load('brief-only')
        moves = self.load('draft-gate')
        finished = self.load('finished-page')
        # Nothing to take a read-only blog for.
        self.refused(nothing, 'take', saved_gate.NOTHING_TO_TAKE)
        self.refused(nothing, 'takeover', saved_gate.NOTHING_TO_TAKE)
        # Never handed over, finished or not.
        for ident in (nothing, moves, finished):
            with self.subTest(handover=ident):
                self.refused(ident, 'handover', saved_gate.SAVED_FLOW)
        # Not published unless finished.
        for ident in (nothing, moves):
            with self.subTest(publish=ident):
                self.refused(ident, 'publish', saved_gate.SAVED_FLOW)
        # Taken where that opens it on the desk; a finished one is recorded as before.
        self.act(moves, 'take')
        self.act(finished, 'take')
        from studio_sync import support

        self.act(finished, 'publish')
        self.assertIn('blog-studio/blogs/' + finished + '/1', support.git(self.found.repo, 'tag'))
