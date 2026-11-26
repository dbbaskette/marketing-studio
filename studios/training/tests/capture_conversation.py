"""Capture the stored conversation-guided trainings (`saved_fixtures.conversation`, GitHub
issue #547) by driving the Training Studio helper `training.py` as a conversation did.

    STUDIO_TEST_RESEARCH_RUNTIME=<a Harness Research test runtime> \
        python3 studios/training/tests/capture_conversation.py [state function ...]

writes each state, or only those named (`finished`, `scenario_gate`, ...), to
`tests/fixtures/saved/conversation/<state>/`, replacing what is there. Everything happens in
a temporary folder with a disposable data folder, settings and git identity; nothing is
started and nothing reaches the network. Content is synthetic: the skill's examples and the
test helpers' research.

`training.py init` is retired, so each training is started as the earlier init started one
(`workspace.init` and the guidance pin, as `helpers.saved_init` does); every later change is
a real helper command (`training.main`) or a decision on the helper's page (`desk.decide`),
as the assistant and the person made them. It works only while those commands exist: they
go with the rest of the conversation-guided flow, after which the stored trees, like the
earlier flow's under `fixtures/saved/`, are never rewritten.

A tree made with Yoodli on records the digest of the installed Yoodli profile
(`skills/training-studio/assets/profiles/yoodli.json`). When that profile changes, capture
the trees that use it again (`scenario_gate finished`).
"""
import contextlib
import io
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS))
import helpers  # noqa: E402  isolates the data folder, settings and git
sys.path.insert(0, str(helpers.REPO))

os.environ['HARNESS_RESEARCH_RUNTIME'] = os.environ['STUDIO_TEST_RESEARCH_RUNTIME']

import desk  # noqa: E402
import sync_guidance  # noqa: E402
import training  # noqa: E402
import workspace  # noqa: E402
from runner import pipeline  # noqa: E402
from runner_support import FORM  # noqa: E402

OUT = TESTS / 'fixtures' / 'saved' / 'conversation'
EXAMPLE = {name: (helpers.EXAMPLES / name).read_text(encoding='utf-8')
           for name in ('blueprint.md', 'document.md', 'product-brief.md', 'scenario.md',
                        'yoodli.md', 'competitive-brief.md')}
WORK = Path(tempfile.mkdtemp(prefix='capture-')).resolve()


def cli(root, *args, expect=0):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        try:
            code = training.main(['--dir', str(root), *args])
        except SystemExit as stopped:
            code = stopped.code
    assert code == expect, (args, out.getvalue())
    return json.loads(out.getvalue())


class Training:
    def __init__(self, state, title, *, levels=(), yoodli=False, copies=(), brief_kind='product',
                 deck_target=None, brand=None, approval='chat', delivery='live'):
        self.state = state
        self.root = WORK / state / workspace.slugify(title)
        self.root.mkdir(parents=True)
        workspace.init(self.root, title, list(levels), brief_kind, deck_target, brand, yoodli,
                       list(copies), approval, delivery)
        sync_guidance.adopt(self.root)
        cli(self.root, 'status')   # remembered on this computer, as every command does
        self.levels = list(levels)

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')

    def make(self, artifact, relative, text, approve=True):
        self.write(relative, text)
        cli(self.root, 'save', artifact, '--built')
        if approve:
            cli(self.root, 'approve', artifact)

    def intake(self, approve=True):
        form = pipeline.check_form({**FORM, 'title': json.loads(
            (self.root / '.training-studio/session.json').read_text())['title'],
            'levels': self.levels, 'deck_target': None})
        self.make('intake', 'intake.md', pipeline.intake_text(form), approve)

    def plan(self, approve=True):
        self.make('research-plan', '.training-studio/research-plan.json',
                  json.dumps(helpers.PLAN, indent=2) + '\n', approve)

    def research(self, approve=True):
        self.write('.harness-research/research.json', json.dumps(helpers.RESEARCH, indent=2) + '\n')
        self.make('research', '.harness-research/research-report.md',
                  '# Research brief\n\nSynthetic findings about rolling restarts.\n', approve)

    def researched(self):
        self.intake()
        self.plan()
        self.research()

    def at(self, level):
        return (f'@{level}', f'{level}/') if level else ('', '')

    def blueprint(self, level=None, approve=True):
        at, folder = self.at(level)
        text = EXAMPLE['blueprint.md']
        if level:
            text = text.replace('Time: 25 min', f'Time: 25 min\nLevel: {level}')
        self.make(f'blueprint{at}', f'{folder}blueprint.md', text, approve)

    def document(self, level=None, approve=True):
        at, folder = self.at(level)
        self.make(f'document{at}', f'{folder}document.md', EXAMPLE['document.md'], approve)

    def brief(self, level=None, approve=True):
        at, folder = self.at(level)
        self.make(f'brief{at}', f'{folder}product-brief.md', EXAMPLE['product-brief.md'], approve)

    def deck(self, level=None, approve=True, objectives=('O1', 'O2', 'O3')):
        at, folder = self.at(level)
        self.write(f'{folder}deck.pptx', helpers.DECK)
        coverage = WORK / f'{self.state}-coverage.json'
        coverage.write_text(json.dumps({objective: [2] for objective in objectives}))
        cli(self.root, 'save', f'deck{at}', '--built', '--coverage', str(coverage))
        if approve:
            cli(self.root, 'approve', f'deck{at}')

    def scenario(self, level=None, approve=True, yoodli=True):
        at, folder = self.at(level)
        self.make(f'scenario:main{at}', f'{folder}scenario.md', EXAMPLE['scenario.md'], approve)
        if yoodli:
            self.make(f'yoodli:main{at}', f'{folder}yoodli/main.md', EXAMPLE['yoodli.md'], approve)

    def gate(self, artifact, stage, question=None, next_step=None):
        args = ['checkpoint', '--stage', stage, '--gate', artifact,
                '--next', next_step or f'Waiting for your review of {workspace.label(artifact)}']
        if question:
            args += ['--question', question]
        cli(self.root, *args)

    def page(self):
        cli(self.root, 'checkpoint', '--approval', 'page')

    def decide(self, artifact, decision, note=None):
        seen = workspace.sha256_file(self.root / workspace.artifact(
            self.root, workspace.load(self.root), artifact)['file'])
        return desk.decide(str(self.root), artifact, decision, note,
                           seen if decision in ('approve', 'accept') else None)

    def store(self):
        target = OUT / self.state
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(self.root, target)
        return target


def started():
    Training('conversation-started', 'Started in conversation').store()


def intake_approved():
    made = Training('conversation-intake', 'Intake in conversation')
    made.intake()
    cli(made.root, 'checkpoint', '--stage', 'research-plan', '--next', 'Draft the research questions')
    made.store()


def research_plan_gate():
    made = Training('conversation-research-plan-gate', 'Research plan in conversation')
    made.intake()
    made.plan(approve=False)
    made.gate('research-plan', 'research-plan', question='Are these the right questions?')
    made.store()


def research_gate():
    made = Training('conversation-research-gate', 'Research in conversation')
    made.intake()
    made.plan()
    cli(made.root, 'pin', 'harness-research', '--task', 'task-research-1', '--run', 'run-1')
    made.research(approve=False)
    made.gate('research', 'research')
    made.store()


def research_imported():
    """Research handed over from a reviewed Harness Research synthesis case."""
    import synthesis_fixture
    made = Training('conversation-research-imported', 'Imported research in conversation')
    made.intake()
    made.plan()
    case = WORK / 'synthesis-case'
    facts, manifest = synthesis_fixture.published_bundle(case / 'research')
    state = case / '.harness-research' / 'synthesis.json'
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(json.dumps({'owner': 'harness-research-synthesis',
                                 'digest': manifest['digest']}))
    cli(made.root, 'research-import', '--case', str(case))
    made.gate('research', 'research')
    made.store()


def blueprint_gate():
    made = Training('conversation-blueprint-gate', 'Blueprint in conversation')
    made.researched()
    made.blueprint(approve=False)
    made.gate('blueprint', 'blueprint')
    made.store()


def blueprint_gate_on_the_page():
    made = Training('conversation-blueprint-on-the-page', 'Blueprint on the page')
    made.researched()
    made.page()
    made.blueprint(approve=False)
    made.gate('blueprint', 'blueprint', question='Approve the blueprint?')
    made.store()


def question_after_plan():
    made = Training('conversation-question-after-plan', 'Question in conversation')
    made.researched()
    made.blueprint()
    cli(made.root, 'checkpoint', '--stage', 'document',
        '--question', 'Should the guide include the rollback example?',
        '--next', 'Draft the learner guide once the question is answered')
    made.store()


def document_gate():
    made = Training('conversation-document-gate', 'Guide in conversation')
    made.researched()
    made.blueprint()
    made.document(approve=False)
    made.gate('document', 'document')
    made.store()


def deck_gate():
    made = Training('conversation-deck-gate', 'Deck in conversation', deck_target='pptx',
                    brand='example-co')
    made.researched()
    made.blueprint()
    made.document()
    made.brief()
    cli(made.root, 'pin', 'harness-slides', '--task', 'task-slides-1')
    made.deck(approve=False)
    made.gate('deck', 'deck')
    made.store()


def google_deck():
    made = Training('conversation-google-deck', 'Google deck in conversation',
                    deck_target='google')
    made.researched()
    made.blueprint()
    made.document()
    made.brief()
    made.make('deck', 'deck-link.md',
              '# Slide deck\n\nhttps://docs.google.com/presentation/d/synthetic-deck-id/edit\n',
              approve=False)
    made.gate('deck', 'deck')
    made.store()


def scenario_gate():
    made = Training('conversation-scenario-gate', 'Practice in conversation', yoodli=True)
    made.researched()
    made.blueprint()
    made.document()
    made.brief()
    made.deck()
    made.scenario(approve=False)
    made.gate('scenario:main', 'scenario')
    made.store()


def finished():
    made = Training('conversation-finished', 'Finished in conversation', yoodli=True,
                    copies=('word',))
    made.researched()
    made.blueprint()
    made.document()
    made.brief()
    for name in ('document', 'product-brief'):
        made.write(f'{name}.docx', f'Word copy of {name}\n')
    cli(made.root, 'export', 'document', '--file', 'document.docx')
    cli(made.root, 'export', 'brief', '--file', 'product-brief.docx')
    made.deck()
    made.scenario()
    cli(made.root, 'check', '--complete', '--all')
    # The package stage: the assistant writes the index, which is derived and never saved.
    made.write('README.md', '# Finished in conversation\n\nSynthetic training for the stored '
               'fixtures.\n\n## What is here\n\n- [Blueprint](blueprint.md)\n'
               '- [Learner guide](document.md)\n- [Brief](product-brief.md)\n'
               '- [Slide deck](deck.pptx)\n- [Practice scenario](scenario.md)\n')
    cli(made.root, 'checkpoint', '--stage', 'done', '--next', 'Nothing pending',
        '--no-question')
    made.store()


def finished_with_nothing_left():
    """Finished in a conversation with nothing the runner would still make: no copies, no
    Yoodli, the index written."""
    made = Training('conversation-finished-complete', 'Finished with nothing left')
    made.researched()
    made.blueprint()
    made.document()
    made.brief()
    made.deck()
    made.scenario(yoodli=False)
    cli(made.root, 'check', '--complete')
    made.write('README.md', '# Finished with nothing left\n\nSynthetic training for the '
               'stored fixtures.\n')
    cli(made.root, 'checkpoint', '--stage', 'done', '--next', 'Nothing pending',
        '--no-question')
    made.store()


def ready_not_marked_done():
    made = Training('conversation-ready-at-package', 'Ready at the index')
    made.researched()
    made.blueprint()
    made.document()
    made.brief()
    made.deck()
    made.scenario(yoodli=False)
    cli(made.root, 'checkpoint', '--stage', 'package', '--next', 'Write the index')
    made.store()


def left_out():
    made = Training('conversation-left-out', 'Stages left out in conversation')
    made.researched()
    cli(made.root, 'skip', 'deck', '--unavailable', '--reason', 'harness-slides is not installed')
    cli(made.root, 'skip', 'brief', '--reason', 'Not needed for this team')
    made.blueprint()
    made.document(approve=False)
    made.gate('document', 'document')
    made.store()


def stale_and_accepted():
    made = Training('conversation-out-of-date', 'Out of date in conversation')
    made.researched()
    made.blueprint()
    made.document()
    made.brief()
    revised = WORK / 'revised-blueprint.md'
    revised.write_text(EXAMPLE['blueprint.md'] + '\nA note added after review.\n')
    cli(made.root, 'save', 'blueprint', '--from', str(revised))
    cli(made.root, 'approve', 'blueprint')
    cli(made.root, 'approve', 'document', '--accept-stale', '--reason', 'Only a note was added')
    made.gate('brief', 'brief', question='The brief is out of date. Rebuild it or keep it?')
    made.store()


def change_asked_on_the_page():
    made = Training('conversation-change-asked', 'Change asked on the page')
    made.researched()
    made.blueprint()
    made.page()
    made.document(approve=False)
    made.gate('document', 'document')
    made.decide('document', 'revise', 'Shorten the first section.')
    made.store()


def levelled():
    made = Training('conversation-levels', 'Levels in conversation', levels=('101', '301'))
    made.researched()
    made.blueprint('101')
    made.document('101')
    made.blueprint('301', approve=False)
    cli(made.root, 'checkpoint', '--stage', 'blueprint', '--level', '301', '--gate',
        'blueprint@301', '--next', 'Waiting for your review of the 301 blueprint')
    made.store()


def half_written_before_plan():
    """The blueprint was written, and the conversation ended before it was saved; a command
    that was stopped left its lock behind."""
    made = Training('conversation-unsaved-plan', 'Unsaved plan in conversation')
    made.researched()
    cli(made.root, 'checkpoint', '--stage', 'blueprint', '--next', 'Draft the blueprint')
    made.write('blueprint.md', EXAMPLE['blueprint.md'])
    made.write('.training-studio/lock', '4194304')
    made.store()


def half_written_after_plan():
    """The guide was written after the approved plan, and never saved."""
    made = Training('conversation-unsaved-guide', 'Unsaved guide in conversation')
    made.researched()
    made.blueprint()
    cli(made.root, 'checkpoint', '--stage', 'document', '--next', 'Draft the learner guide')
    made.write('document.md', EXAMPLE['document.md'])
    made.store()


def edited_after_save():
    made = Training('conversation-edited-after-save', 'Edited after saving')
    made.researched()
    made.blueprint()
    made.document(approve=False)
    made.write('document.md', EXAMPLE['document.md'] + '\nA line typed after it was saved.\n')
    made.gate('document', 'document')
    made.store()


def unreadable_session():
    made = Training('conversation-unreadable-session', 'Unreadable record')
    made.researched()
    made.blueprint()
    made.write('.training-studio/session.json', '{"schema": 1, "title": "Unreadable rec')
    made.store()


def unreadable_plan():
    made = Training('conversation-unreadable-plan', 'Unreadable plan')
    made.researched()
    made.blueprint()
    made.write('blueprint.md', '# Blueprint\n\nThe plan was cut short.\n')
    made.store()


STATES = [started, intake_approved, research_plan_gate, research_gate, research_imported,
          blueprint_gate, blueprint_gate_on_the_page, question_after_plan, document_gate,
          deck_gate, google_deck, scenario_gate, finished, finished_with_nothing_left,
          ready_not_marked_done, left_out,
          stale_and_accepted, change_asked_on_the_page, levelled, half_written_before_plan,
          half_written_after_plan, edited_after_save, unreadable_session, unreadable_plan]

if __name__ == '__main__':
    OUT.mkdir(parents=True, exist_ok=True)
    wanted = sys.argv[1:]
    for make in STATES:
        if not wanted or make.__name__ in wanted:
            make()
            print('captured', make.__name__)
    shutil.rmtree(WORK)
