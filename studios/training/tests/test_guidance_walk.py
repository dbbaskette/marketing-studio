"""The stage references, walked as written (GitHub issue #547). The reader of SKILL.md and the
references is an assistant doing desk work in a conversation. Each step a stage reference
teaches is run here, in its order, against a disposable conversation-owned desk training
(workers faked, nothing real started), and what happens is what the reference says happens.

Then every reference is scanned: no helper command that refuses desk work is named, however
it is named, and nothing it tells the person to mark Ready is a material `ready` refuses."""
import contextlib
import io
import json
import re
from pathlib import Path

import helpers  # noqa: F401
import training
import workspace
from runner_support import BLUEPRINT, BRIEF, CHOSEN, DOCUMENT, OUTLINE, SCENARIO, YOODLI, drawn
from runner import desk_chat
import test_desk_chat
from test_runner_deck import DeckCase
from workspace import WorkspaceError

SKILL = Path(training.__file__).resolve().parents[1]
GUIDANCE = [SKILL / 'SKILL.md', *sorted((SKILL / 'references').rglob('*.md'))]
# Every way the guidance names a helper command: `training.py save`, training.py save,
# `<helper> save`, and the helper's `save`, `checkpoint` and `export`.
NAMED = (re.compile(r'training\.py`?\s+`?([a-z][a-z-]*)'),
         re.compile(r'<helper>`?\s+`?([a-z][a-z-]*)'))
LISTED = re.compile(r"helper's\s+((?:`[a-z][a-z-]*`(?:,\s*|\s+and\s+|\s+or\s+)?)+)")
# What a reference tells the person to mark Ready, and what it says is not marked so.
MARKED = re.compile(r'\bReady only when\b|\bmarks? (?:it|them|each) (?:so|ready|Ready)\b')
NOT_MARKED = re.compile(r'not\s+marked\s+Ready')
TARGET = re.compile(r'--target ([a-z][a-z:<>-]*)|context for `([a-z][a-z:-]*)`|'
                    r'target `([a-z][a-z:-]*)`')


def named_commands() -> dict[str, set[str]]:
    found: dict[str, set[str]] = {}
    for path in GUIDANCE:
        text = path.read_text(encoding='utf-8')
        names = [match.group(1) for pattern in NAMED for match in pattern.finditer(text)]
        for match in LISTED.finditer(text):
            names += re.findall(r'`([a-z][a-z-]*)`', match.group(1))
        for name in names:
            found.setdefault(name, set()).add(path.name)
    return found


def marking(path: Path) -> list[tuple[str, bool]]:
    """Each (target, whether it is to be marked Ready) a reference says, the target being the
    last one it named before the sentence."""
    text, said, last = path.read_text(encoding='utf-8'), [], None
    events = [(match.start(), 'target', next(group for group in match.groups() if group))
              for match in TARGET.finditer(text)]
    events += [(match.start(), 'marked', True) for match in MARKED.finditer(text)]
    events += [(match.start(), 'marked', False) for match in NOT_MARKED.finditer(text)]
    for _, kind, value in sorted(events, key=lambda event: event[0]):
        if kind == 'target':
            last = value.replace('<id>', 'main')
        elif last:
            said.append((last, value))
    return said


class GuidanceWalkTests(DeckCase):
    create = test_desk_chat.ConversationTests.create
    submit = test_desk_chat.ConversationTests.submit
    supply_research = test_desk_chat.ConversationTests.supply_research

    def ready_context(self, root, target):
        return desk_chat.context(self.engine, root, 'ready/' + target)

    def ready(self, root, target):
        context = self.ready_context(root, target)
        return desk_chat.ready(self.engine, root, {
            'target': target, 'expected_basis': context['expected_basis'],
            'seen': context['requirements']['seen'],
            'response': 'The person read it and said it is ready.'})

    def status(self, root):
        return workspace.person_statuses(root, workspace.load(root))

    def helper(self, root, *argv):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = training.main(['--dir', str(root), *argv])
        return code, json.loads(out.getvalue())

    def walked(self, walk):
        """The stage references' steps, in order, each checked as the reference says it."""
        root = self.create(materials=['document', 'brief', 'scenario'], deck_target='pptx',
                           brand=CHOSEN, scope=list(desk_chat.KINDS))
        # research-plan, research-handoff: submitting accepts each on the desk; neither is
        # marked Ready.
        self.supply_research(root)
        status = self.status(root)
        walk.append(('research-plan, research', 'submit each',
                     (status['research-plan'], status['research'])))
        self.assertEqual((status['research-plan'], status['research']), ('approved', 'approved'))
        for target in ('research-plan', 'research'):
            with self.assertRaises(WorkspaceError) as refused:
                self.ready(root, target)
            walk.append((target, 'mark ready', 'refused: ' + str(refused.exception)))
        # blueprint, document, brief, scenario: a draft until the person marks it ready.
        for target, kind, text in (('blueprint', 'outline', BLUEPRINT),
                                   ('document', 'text', DOCUMENT), ('brief', 'text', BRIEF),
                                   ('scenario:main', 'text', SCENARIO)):
            self.submit(root, target, kind, {'text': text})
            submitted = self.status(root)[target]
            self.ready(root, target)
            walk.append((target, 'submit, then the person marks it ready',
                         (submitted, self.status(root)[target])))
            self.assertEqual((submitted, self.status(root)[target]), ('draft', 'approved'))
        code, checked = self.helper(root, 'check')
        walk.append(('check', '`training.py check`', (code, checked['checks_passed'])))
        self.assertEqual((code, checked['checks_passed']), (0, True))
        # deck: outline, the person's look answer, the drawing, then Ready.
        self.submit(root, 'deck-outline', 'outline', {'outline': OUTLINE})
        self.brand.offers_looks = True
        context = desk_chat.context(self.engine, root, 'look')
        desk_chat.answer(self.engine, root, {
            'target': 'look', 'expected_basis': context['expected_basis'],
            'answer': {'questionId': context['requirements']['questionId'],
                       'choice': 'default', 'response': 'Use the displayed default.'}})
        context = desk_chat.context(self.engine, root, 'deck')
        sections = {ident: drawn(spec['artifacts']['section'])
                    for ident, spec in context['requirements']['sections'].items()}
        desk_chat.submit(self.engine, root, {'kind': 'drawing', 'target': 'deck',
                         'expected_basis': context['expected_basis'],
                         'payload': {'sections': sections}})
        submitted = self.status(root)['deck']
        self.ready(root, 'deck')
        walk.append(('deck', 'outline, look answer, drawing, then Ready',
                     (submitted, self.status(root)['deck'])))
        self.assertEqual((submitted, self.status(root)['deck']), ('draft', 'approved'))
        # yoodli: turned on with scope, then a draft until marked ready.
        context = desk_chat.context(self.engine, root, 'scope')
        desk_chat.set_scope(self.engine, root, context['expected_basis'], context['scope'],
                            yoodli=True)
        self.assertIn('yoodli', workspace.load(root)['settings']['stages'])
        self.submit(root, 'yoodli:main', 'text', {'text': YOODLI})
        submitted = self.status(root)['yoodli:main']
        self.ready(root, 'yoodli:main')
        walk.append(('yoodli', 'scope yoodli on, submit, then Ready',
                     (submitted, self.status(root)['yoodli:main'])))
        self.assertEqual((submitted, self.status(root)['yoodli:main']), ('draft', 'approved'))
        # package: not ready, for the deck's coverage and the copies; no index; no handoff
        # without a runner research contract.
        code, checked = self.helper(root, 'check', '--complete', '--all')
        walk.append(('package', '`training.py check --complete --all`',
                     (code, checked['ready'], checked['blocking'])))
        self.assertEqual((code, checked['ready']), (1, False))
        self.assertTrue(any('coverage' in reason for reason in checked['blocking']))
        self.assertTrue(any('export' in reason for reason in checked['blocking']))
        self.assertFalse((root / 'README.md').exists())
        walk.append(('package', 'index', 'not written'))
        context = desk_chat.context(self.engine, root, 'handoff')
        with self.assertRaises(WorkspaceError) as refused:
            desk_chat.handoff(self.engine, root, context['expected_basis'], context['scope'])
        self.assertIn('no saved runner research contract', str(refused.exception))
        walk.append(('package', '`studio desk handoff`', 'refused: ' + str(refused.exception)))
        self.assertFalse((root / 'README.md').exists())
        return root

    def test_every_stage_reference_does_what_it_says_in_a_conversation(self):
        self.walked([])
        # The package reference says what the walk found: no index and no readiness for desk
        # work in a conversation, and why.
        package = (SKILL / 'references/stages/package.md').read_text(encoding='utf-8')
        self.assertIn('Desk work in a conversation gets no index', package)
        self.assertIn('does not reach `ready` either', package)
        self.assertNotIn('itself once every requested material is Ready', package)

    def test_nothing_is_marked_ready_that_ready_refuses(self):
        """Every material a reference tells the person to mark Ready can be, and what it
        says is not marked Ready cannot be."""
        root = self.walked([])
        said = [(path.name, target, marked) for path in GUIDANCE
                for target, marked in marking(path)]
        self.assertTrue(any(marked for _, _, marked in said))
        self.assertTrue(any(not marked for _, _, marked in said))
        for name, target, marked in said:
            with self.subTest(reference=name, target=target, marked=marked):
                if marked:
                    self.ready_context(root, target)
                else:
                    with self.assertRaises(WorkspaceError):
                        self.ready_context(root, target)


class GuidanceScanTests(DeckCase):
    def test_no_helper_command_named_any_way_is_refused_for_desk_work(self):
        named = named_commands()
        known = set(training.parser()._subparsers._group_actions[0].choices)
        self.assertLessEqual({'save', 'checkpoint', 'export', 'check', 'status'}, set(named))
        for command, files in sorted(named.items()):
            with self.subTest(command=command, files=sorted(files)):
                self.assertIn(command, known)
                self.assertNotIn(command, (*training.ENDED_COMMANDS, 'init'))

    def test_the_scan_finds_the_helper_however_it_is_named(self):
        """The scan is not fooled by another spelling of the same instruction."""
        import tempfile
        global GUIDANCE
        kept = GUIDANCE
        with tempfile.TemporaryDirectory() as folder:
            for text in ('Run `training.py approve blueprint`.', 'Then training.py skip deck.',
                         'Use `<helper> pin harness-slides`.',
                         "Record it with the helper's `research-import`.",
                         "The helper's `save` and `approve` record it."):
                with self.subTest(text=text):
                    probe = Path(folder) / 'probe.md'
                    probe.write_text(text)
                    GUIDANCE = [probe]
                    try:
                        self.assertTrue(set(named_commands()) & set(training.ENDED_COMMANDS))
                    finally:
                        GUIDANCE = kept
