"""A training's History: every part of its guide, brief and plan has the versions Training
already keeps, read from its content-addressed history files and its save events, with no
second store. A training saved before the desk has History as far back as its files go, and
reading it writes nothing. A disposable training folder and data folder, a stand-in for the
engine's files lock and a pretend Drive; nothing real is started and nothing reaches Google."""
import sys  # noqa: I001  the path-setting imports must come before runner
import threading
import unittest
from unittest import mock
from pathlib import Path

import helpers
from helpers import EXAMPLES, TrainingCase
import runner_support
import gdocs
import workspace

sys.path.insert(0, str(helpers.REPO))

from runner import drafts
from studio_core.drafting import versions as core_versions

WHY = ('A customer restarts an app during business hours, sees dropped requests, and says, '
       '"You told us this could not happen." What you say next decides whether they trust '
       'the platform. This guide gives you the facts to answer well.')


def example(file: str) -> str:
    return (EXAMPLES / file).read_bytes().decode('utf-8')


def headed(draft: dict, heading: str) -> dict:
    return next(section for section in draft['sections'] if section['heading'] == heading)


def summary(text: str, words: str) -> str:
    """The guide with its Summary section's words replaced."""
    start = text.index('## Summary\n\n') + len('## Summary\n\n')
    return text[:start] + words + '\n\n' + text[text.index('## Check your understanding'):]


def tree(folder: Path) -> dict:
    """Every path under a folder, with each file's bytes."""
    return {path.relative_to(folder).as_posix(): path.read_bytes() if path.is_file() else None
            for path in sorted(folder.rglob('*'))}


class Engine:
    """What the store asks of the engine: the lock its desk writes run under."""

    def __init__(self):
        self.files = threading.RLock()


class HistoryCase(TrainingCase):
    """A training with its plan written, made with the core helper (`flow=None`) or on the
    desk, whose guide is saved by each test."""

    flow = None

    def setUp(self):
        super().setUp()
        approval = 'page' if self.flow else 'chat'
        workspace.init(self.root, 'Topic', approval=approval, flow=self.flow)
        for name in ('intake', 'research-plan', 'research'):
            self.build(name)
            workspace.approve(self.root, name, by=approval)
        self.write('blueprint.md', example('blueprint.md'))
        workspace.save(self.root, 'blueprint', built=True)
        if self.flow:
            workspace.accept_desk(self.root, 'blueprint')
        self.engine = Engine()
        self.store = drafts.TrainingStore(self.engine, self.root)
        self.codec = drafts.CODECS['document']
        self.history = drafts.HistoryVersions(self.store, self.codec)

    def saved(self, text: str, **options) -> None:
        self.write('document.md', text)
        workspace.save(self.root, 'document', **({'built': True} if not options else options))

    def current(self) -> dict:
        return drafts.current(self.store, self.codec, 'document')

    def part(self, heading: str) -> str:
        return headed(self.current(), heading)['id']

    def shown(self, part: str) -> list[tuple]:
        return [(version['source'], version['text'])
                for version in self.history.versions('document', part)]


class SavedTrainingTests(HistoryCase):
    """A training saved before the desk, by the core helper."""

    def test_history_comes_from_the_history_files(self):
        text = example('document.md')
        first = headed(self.codec.split(text), 'Summary')['text']
        self.saved(text)
        self.saved(summary(text, 'Second summary.'))
        self.saved(summary(text, 'Third summary.'))
        # A hand edit, then a file saved over it: the edit is kept, but no event names it.
        self.write('document.md', summary(text, 'Typed by hand.'))
        incoming = self.write('incoming/document.md', summary(text, 'Fifth summary.'))
        workspace.save(self.root, 'document', source=incoming)
        state = self.root / workspace.STATE_DIR
        before, everything = tree(state), tree(self.root)

        part = self.part('Summary')
        found = self.history.versions('document', part)
        self.assertEqual([(version['source'], version['text']) for version in found],
                         [('save', 'Third summary.'), ('save', 'Second summary.'),
                          ('save', first), ('earlier', 'Typed by hand.')])
        self.assertTrue(all(version['at'] for version in found[:3]), 'saves have their time')
        self.assertIsNone(found[-1]['at'], 'the hand edit has no time')
        self.assertEqual([version['words'] for version in found],
                         [2, 2, len(first.split()), 3])
        saves = [event for event in workspace.load(self.root)['events']
                 if event['event'] == 'save' and event['artifact'] == 'document']
        self.assertEqual([version['at'] for version in found[:3]],
                         [saves[-1]['at'], saves[-2]['at'], saves[-3]['at']],
                         'each is labelled by the change that came after it')
        self.assertEqual(self.history.kept('document', part), found)
        self.assertEqual(self.shown(self.part('Glossary')), [], 'a part never changed has none')
        self.assertEqual(self.history.counts('document'), {part: 4})
        self.assertEqual(state.joinpath('history', 'document').is_dir(), True)

        self.assertEqual(tree(state), before, 'reading History writes nothing in the training')
        self.assertEqual(tree(self.root), everything, 'nothing at all is migrated or written')
        self.assertFalse(self.store.folder('document').exists(), 'no second store')

    def test_a_section_is_followed_across_a_renamed_heading(self):
        text = example('document.md')
        self.saved(text)
        moved = text.replace('## Why this matters\n\n', '## Why it matters\n\n').replace(
            'decides whether they trust', 'decides if they trust')
        # The renamed section moves too, so neither its heading nor its place finds it.
        first, _, rest = moved.partition('## Why it matters')
        why, _, after = rest.partition('## What a rolling restart does')
        moved = first + '## What a rolling restart does' + after.replace(
            '## Summary', '## Why it matters' + why + '## Summary')
        self.saved(moved)
        self.assertEqual(self.shown(self.part('Why it matters')), [('save', WHY)])
        self.assertEqual(self.shown(self.part('Summary')), [], 'moved, not changed')

    def test_row_156_a_google_pull_lands_as_a_version(self):
        text = example('document.md')
        self.saved(text)
        stand_in = runner_support.Copies()
        drive = stand_in.drive
        ident = gdocs.push(self.root, 'document', drive)['file_id']
        drive.docs[ident] = summary(drive.docs[ident], 'Written in Google.')
        self.assertEqual(stand_in.pull(self.root, 'document')['result'], 'pulled')
        event = [event for event in workspace.load(self.root)['events']
                 if event['event'] == 'save'][-1]
        self.assertEqual((event['artifact'], event['via']), ('document', 'google'))
        part = self.part('Summary')
        newest = self.history.versions('document', part)[0]
        first = headed(self.codec.split(text), 'Summary')['text']
        self.assertEqual((newest['source'], newest['text']), ('google', first))
        self.assertEqual(drafts.SOURCE_WORDS[newest['source']], "Before Google's text")
        self.assertEqual(workspace.statuses(self.root, workspace.load(self.root))['document'],
                         'draft', 'an edit made in Google is an edit, as before')
        # Both sides changed, and the Doc's version chosen: Google's text too.
        local = self.root / 'document.md'
        local.write_text(summary(local.read_text(encoding='utf-8'), 'Changed here.'),
                         encoding='utf-8')
        drive.docs[ident] = summary(drive.docs[ident], 'Changed in Google again.')
        self.assertEqual(stand_in.pull(self.root, 'document')['result'], 'both-changed')
        self.assertEqual(stand_in.pull(self.root, 'document', choose='theirs')['result'],
                         'pulled')
        event = [event for event in workspace.load(self.root)['events']
                 if event['event'] == 'save'][-1]
        self.assertEqual(event['via'], 'google')
        # What was typed here was kept beside it, with no event: an earlier version.
        self.assertEqual(self.shown(self.part('Summary')),
                         [('google', 'Written in Google.'), ('google', first),
                          ('earlier', 'Changed here.')])

    def test_every_kind_of_change_has_its_words(self):
        self.assertEqual(drafts.SOURCE_WORDS, {
            'save': 'Saved', 'rewrite': 'Rewritten', 'revise-all': 'Revised with the whole note',
            'selection': 'Selection', 'restore': 'Restored', 'google': "Before Google's text",
            'finishing': 'Finishing', 'update': 'Updated', 'earlier': 'An earlier version'})
        self.assertEqual(set(drafts.SOURCE_WORDS), {*workspace.VIA, 'earlier'})

    def test_at_most_piece_3_s_cap_are_listed(self):
        text = example('document.md')
        for number in range(core_versions.KEEP + 3):
            self.saved(summary(text, f'Summary number {number}.'))
        found = self.history.versions('document', self.part('Summary'))
        self.assertEqual(len(found), core_versions.KEEP)
        self.assertEqual(found[0]['text'], f'Summary number {core_versions.KEEP + 1}.')

    def test_a_part_s_current_text_is_never_an_earlier_version(self):
        text = example('document.md')
        first = self.codec.split(text)
        self.saved(text)
        # A hand edit of the Summary, then a file saved over it that keeps the edit and
        # changes the Glossary: the hand edit's file has no event, and its Summary is now.
        typed = summary(text, 'Typed by hand.')
        self.write('document.md', typed)
        glossary = headed(first, 'Glossary')['text']
        incoming = self.write('incoming/document.md',
                              typed.replace(glossary, 'A shorter glossary.'))
        workspace.save(self.root, 'document', source=incoming)
        part = self.part('Summary')
        self.assertEqual(headed(self.current(), 'Summary')['text'], 'Typed by hand.')
        self.assertEqual(self.shown(part), [('save', headed(first, 'Summary')['text'])])
        self.assertEqual(self.shown(self.part('Glossary')), [('save', glossary)],
                         'a text History already lists is not listed again')
        self.assertEqual(self.history.counts('document'),
                         {part: 1, self.part('Glossary'): 1})

    def test_restore_reads_only_as_far_as_the_part_needs(self):
        text = example('document.md')
        for number in range(core_versions.KEEP + 5):
            self.saved(summary(text, f'Summary number {number}.'))
        part, read = self.part('Summary'), []
        split = self.codec.split
        with mock.patch.object(self.codec, 'split',
                               side_effect=lambda markdown: read.append(1) or split(markdown)):
            found = self.history.kept('document', part)
        self.assertEqual(len(found), core_versions.KEEP)
        self.assertEqual(len(read), core_versions.KEEP + 1,
                         'the file now, then one file a version: the walk stops at the cap')

    def test_a_version_whose_file_is_missing_is_left_out(self):
        text = example('document.md')
        self.saved(summary(text, 'One.'))
        self.saved(summary(text, 'Two.'))
        self.saved(summary(text, 'Three.'))
        gone = workspace.history_file(self.root, 'document', workspace.sha256_file(
            self.root / 'document.md'), '.md')
        self.saved(summary(text, 'Four.'))
        gone.unlink()   # the file Three. was in
        self.assertEqual(self.shown(self.part('Summary')), [('save', 'Two.'), ('save', 'One.')])

    def test_an_unknown_part_is_refused_and_an_unwritten_material_has_none(self):
        self.assertEqual(self.history.counts('document'), {})
        self.saved(example('document.md'))
        with self.assertRaisesRegex(ValueError, '^Choose a part of this draft.$'):
            self.history.versions('document', '../escape')
        self.assertEqual(self.history.versions('document', 'abcdef12'), [])


class DeskHistoryTests(HistoryCase):
    """A training on the desk: saves name their kind of change and the page's session."""

    flow = 'desk'

    def setUp(self):
        super().setUp()
        self.saved(example('document.md'))
        workspace.accept_desk(self.root, 'document')
        self.desk = drafts.TrainingDesk(self.store, self.codec)
        self.first = headed(self.codec.split(example('document.md')), 'Summary')['text']

    def type(self, part: str, text: str, **options) -> dict:
        with self.engine.files:
            return self.desk.save('document', self.desk.read('document')['revision'], part,
                                  text, **options)

    def test_the_desk_keeps_its_versions_in_the_history_files(self):
        self.assertIsInstance(self.desk.versions, drafts.HistoryVersions)
        part = self.part('Summary')
        self.type(part, 'Typed.', session='ab12')
        self.assertFalse(self.store.path('document', 'versions').exists(), 'no second store')

    def test_one_editing_session_is_one_version(self):
        part = self.part('Summary')
        for words in ('One.', 'Two.', 'Three.'):
            self.type(part, words, source='save', session='ab12')
        events = [event for event in workspace.load(self.root)['events']
                  if event['event'] == 'save'][-3:]
        self.assertEqual({(event['via'], event['session']) for event in events},
                         {('save', 'ab12')})
        self.assertEqual(self.shown(part), [('save', self.first)])
        self.type(part, 'Four.', session='cd34')
        self.assertEqual(self.shown(part), [('save', 'Three.'), ('save', self.first)])
        self.assertEqual(self.desk.versions.counts('document'), {part: 2})

    def test_row_143_a_restore_is_a_version(self):
        part = self.part('Summary')
        self.type(part, 'One.', session='ab12')
        self.type(part, 'Two.', session='cd34')
        self.assertEqual(self.shown(part), [('save', 'One.'), ('save', self.first)])
        with self.engine.files:
            self.desk.restore('document', self.desk.read('document')['revision'], part, 1)
        event = [event for event in workspace.load(self.root)['events']
                 if event['event'] == 'save'][-1]
        self.assertEqual(event['via'], 'restore')
        self.assertEqual(headed(self.current(), 'Summary')['text'], self.first)
        found = self.history.versions('document', part)
        self.assertEqual((found[0]['source'], found[0]['text']), ('restore', 'Two.'))
        self.assertEqual(drafts.SOURCE_WORDS[found[0]['source']], 'Restored')
        self.assertEqual(self.shown(part), [('restore', 'Two.'), ('save', 'One.'),
                                            ('save', self.first)])


if __name__ == '__main__':
    unittest.main()
