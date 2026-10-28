"""A training's guide, brief and plan as piece 3's parts: Training Studio's codecs split each
file into an opening and sections that join back to the same file byte for byte, and its
store writes a saved part back to the material's file, accepted on the desk. A disposable
training folder and data folder, and a stand-in for the engine's files lock; nothing real
is started."""
import sys  # noqa: I001  the path-setting imports must come before runner
import threading
import unittest

import helpers
from helpers import EXAMPLES, TrainingCase
import checks
import workspace
from workspace import WorkspaceError

sys.path.insert(0, str(helpers.REPO))

from runner import drafts
from studio_core.drafting.store import HELD

SHAPE = 'A brief keeps its eight numbered sections, in order.'
UNCLOSED = 'Close the code block in this part.'
LOCKED = 'Sources is kept from the findings cited. Change the references in the text instead.'
EXAMPLE_FILES = (('document', 'document.md'), ('brief', 'product-brief.md'),
                 ('brief', 'competitive-brief.md'), ('blueprint', 'blueprint.md'))


def example(file: str) -> str:
    return (EXAMPLES / file).read_bytes().decode('utf-8')


def headed(draft: dict, heading: str) -> dict:
    return next(section for section in draft['sections'] if section['heading'] == heading)


class Engine:
    """What the store asks of the engine: the lock its desk writes run under."""

    def __init__(self):
        self.files = threading.RLock()


class CodecTests(unittest.TestCase):
    def test_every_example_splits_and_joins_back_byte_for_byte(self):
        for name, file in EXAMPLE_FILES:
            with self.subTest(file=file):
                codec, text = drafts.CODECS[name], example(file)
                draft = codec.split(text)
                self.assertEqual(codec.join(draft), text)
                self.assertEqual(codec.fixed, ('opening',))
                self.assertTrue(draft['opening'].startswith('# '), 'the title is the opening')
                self.assertNotIn('## ', draft['opening'])
                self.assertTrue(all(codec.part.fullmatch(section['id'])
                                    for section in draft['sections']))
                self.assertEqual(codec.thing, 'draft', 'the stale sentence says "draft"')

    def test_odd_spacing_joins_back_byte_for_byte(self):
        texts = {
            'document': ('# T\r\n\r\nIntro\r\n\r\n## A\r\n<!--covers:O1-->\r\nOne.\r\n\r\n'
                         '## B   \n\n\n\n```\n## not a heading\n```\n\n\n## Sources\n1. x'),
            'blueprint': '## Frame\nAudience: me\n## Empty\n## Last\n\ntext\n\n\n',
            'brief': example('product-brief.md').replace('\n## 2.', '\n\n\n## 2.')
                                                .rstrip('\n'),
        }
        for name, text in texts.items():
            with self.subTest(name=name):
                codec = drafts.CODECS[name]
                self.assertEqual(codec.join(codec.split(text)), text)
        draft = drafts.CODECS['document'].split(texts['document'])
        self.assertEqual([section['heading'] for section in draft['sections']],
                         ['A', 'B', 'Sources'], 'a ## line in fenced code is text')
        self.assertEqual(headed(draft, 'A')['covers'], ['O1'])

    def test_a_changed_part_joins_with_the_rest_as_it_was(self):
        codec, text = drafts.CODECS['document'], example('document.md')
        draft = codec.split(text)
        part = headed(draft, 'Why this matters')['id']
        codec.set_text(draft, part, '  New words.\n\n')
        joined = codec.join(draft)
        self.assertEqual(joined, text.replace(
            'A customer restarts an app during business hours, sees dropped requests, and '
            'says, "You told us this could not happen." What you say next decides whether '
            'they trust the platform. This guide gives you the facts to answer well.',
            'New words.'))
        again = codec.split(joined)
        self.assertEqual(headed(again, 'Why this matters')['text'], 'New words.')
        self.assertEqual(headed(again, 'Why this matters')['covers'], ['O3'])
        # A part emptied, then written again, still makes a file that reads the same way.
        codec.set_text(draft, part, '')
        emptied = codec.split(codec.join(draft))
        self.assertEqual(headed(emptied, 'Why this matters')['text'], '')
        self.assertEqual(len(emptied['sections']), len(draft['sections']))
        blueprint = drafts.CODECS['blueprint']
        plan = blueprint.split('## Empty\n## Last\n')
        blueprint.set_text(plan, plan['sections'][0]['id'], 'Now words.')
        blueprint.set_text(plan, 'opening', '# Blueprint: T')
        self.assertEqual(blueprint.join(plan), '# Blueprint: T\n\n## Empty\n\nNow words.\n\n'
                                               '## Last\n')

    def test_a_guide_section_keeps_its_covers_note(self):
        codec = drafts.CODECS['document']
        draft = codec.split(example('document.md'))
        section = headed(draft, 'What a rolling restart does')
        self.assertEqual(section['covers'], ['O1', 'K1.1', 'K1.3'])
        self.assertNotIn('<!--', section['text'])
        self.assertTrue(section['text'].startswith('A rolling restart replaces'))
        self.assertEqual(headed(draft, 'Summary')['covers'], [])
        self.assertTrue(headed(draft, 'Sources')['locked'])
        self.assertFalse(any(section['locked'] for section in draft['sections']
                             if section['heading'] != 'Sources'))
        # A changed covers list is written back as a note under the heading.
        section['covers'] = ['O1', 'K1.1']
        self.assertIn('## What a rolling restart does\n\n<!-- covers: O1 K1.1 -->\n\nA rolling',
                      codec.join(draft))
        self.assertTrue(codec.breaks('Words\n## A new section'))
        self.assertFalse(codec.breaks('Words\n### A heading inside'))

    def test_a_brief_keeps_its_eight_sections(self):
        codec, text = drafts.CODECS['brief'], example('product-brief.md')
        draft = codec.split(text)
        self.assertEqual(len(draft['sections']), 8)
        self.assertEqual(draft['kind'], 'product')
        self.assertEqual(headed(draft, '3. Capabilities')['findings'],
                         ['availability', 'health-checks'])
        self.assertNotIn('<!--', headed(draft, '3. Capabilities')['text'])
        self.assertTrue(headed(draft, '8. Sources')['locked'])
        self.assertEqual([section['heading'] for section in draft['sections']
                          if section['locked']], ['8. Sources'])
        self.assertEqual(codec.split(example('competitive-brief.md'))['kind'], 'competitive')
        removed = text.replace('## 7. Unknowns', 'Unknowns').replace('## 8.', '## 7.')
        renamed = text.replace('## 3. Capabilities', '## 3. What it does')
        moved = text.replace('## 3. Capabilities', '## 3. Limitations', 1).replace(
            '## 4. Limitations', '## 4. Capabilities', 1)
        for wrong in (removed, renamed, moved):
            with self.assertRaisesRegex(ValueError, f'^{SHAPE}$'):
                codec.split(wrong)
        # A draft record whose sections were changed is refused as it is joined.
        draft['sections'].pop(6)
        with self.assertRaisesRegex(ValueError, f'^{SHAPE}$'):
            codec.join(draft)

    def test_a_brief_part_holds_no_numbered_heading(self):
        codec = drafts.CODECS['brief']
        self.assertTrue(codec.breaks('Words.\n## 9. More'))
        self.assertTrue(codec.breaks('```\n## 2. Fenced, still read as a section\n```'),
                        "the brief's check reads every ## line as a section")
        self.assertFalse(codec.breaks('Words.\n### A heading inside'))

    def test_a_brief_that_passes_its_check_splits_and_joins(self):
        codec = drafts.CODECS['brief']
        text = example('product-brief.md').replace(
            '\n## 4. Limitations', '\n## Notes\n\nMore.\n\n## 4. Limitations').replace(
            '\n## 8. Sources', '\n## 7b. Unknowns\n\nNone.\n\n## 8. Sources').replace(
            '## 5. Qualification', '## 6. Qualification') + '\n## 9. Appendix\n\nExtra.\n'
        self.assertEqual(checks.check_brief(text, 'product', None)[0]['status'], 'passed')
        draft = codec.split(text)
        self.assertEqual(codec.join(draft), text)
        self.assertIn('## Notes\n\nMore.', headed(draft, '3. Capabilities')['text'],
                      'a ## line the check does not read stays in its section')
        self.assertTrue(headed(draft, '8. Sources')['locked'])
        fenced = example('product-brief.md').replace(
            '\n## 4. Limitations', '\n```\n## 4. Limitations\n```\n\n## 4. Limitations', 1)
        self.assertEqual(codec.join(codec.split(fenced)), fenced)

    def test_a_section_line_in_a_part_is_refused(self):
        for name in ('document', 'blueprint'):
            codec = drafts.CODECS[name]
            self.assertTrue(codec.breaks('Words.\n## #tag'), name)
            self.assertFalse(codec.breaks('```\n## #tag\n```'), name)

    def test_a_job_never_lands_in_sources(self):
        from studio_core.drafting import basis
        codec = drafts.CODECS['document']
        draft = codec.split(example('document.md'))
        sources = headed(draft, 'Sources')
        with self.assertRaisesRegex(ValueError, f'^{LOCKED}$'):
            basis.land_part(draft, {'part': sources['id'],
                                    'basis': basis.fingerprint(sources['text'])},
                            '1. A source of its own', codec)
        summary = headed(draft, 'Summary')
        landed = basis.land_part(draft, {'part': summary['id'],
                                         'basis': basis.fingerprint(summary['text'])},
                                 'A new summary.', codec)
        self.assertEqual(landed[2], 'A new summary.')

    def test_every_codec_refuses_an_unclosed_code_block(self):
        for name, codec in drafts.CODECS.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex(ValueError, f'^{UNCLOSED}$'):
                    codec.vet('opening', 'Words.\n~~~\ncode')
                codec.vet('opening', 'Words.\n~~~\ncode\n~~~\n')

    def test_the_plan_has_nothing_locked(self):
        draft = drafts.CODECS['blueprint'].split(example('blueprint.md'))
        self.assertIn('Objectives', [section['heading'] for section in draft['sections']])
        self.assertIn('### O1', headed(draft, 'Objectives')['text'])
        self.assertFalse(any(section['locked'] for section in draft['sections']))

    def test_the_same_file_splits_to_the_same_ids(self):
        codec, text = drafts.CODECS['document'], example('document.md')
        self.assertEqual(codec.split(text), codec.split(text))


class DeskCase(TrainingCase):
    """A training on the desk with its plan and guide written and accepted on the desk."""

    def setUp(self):
        super().setUp()
        workspace.init(self.root, 'Topic', approval='page', flow='desk')
        for name in ('intake', 'research-plan', 'research'):
            self.build(name)
            workspace.approve(self.root, name, by='page')
        self.write('blueprint.md', example('blueprint.md'))
        workspace.save(self.root, 'blueprint', built=True)
        workspace.accept_desk(self.root, 'blueprint')
        self.write('document.md', example('document.md'))
        workspace.save(self.root, 'document', built=True)
        workspace.accept_desk(self.root, 'document')
        self.engine = Engine()
        self.store = drafts.TrainingStore(self.engine, self.root)
        self.codec = drafts.CODECS['document']

    def current(self) -> dict:
        with self.engine.files:
            return drafts.current(self.store, self.codec, 'document')


class StoreTests(DeskCase):
    def test_the_store_is_training_studio_s(self):
        self.assertEqual((self.store.product, self.store.word), ('Training Studio', 'training'))
        self.assertEqual(self.store.folder('document@101'),
                         self.root / '101' / 'work' / 'drafts' / 'document-101')
        self.assertEqual(self.store.folder('scenario:main'),
                         self.root / 'work' / 'drafts' / 'scenario-main')
        self.assertEqual(self.store.local('document@101', 'latest.json'),
                         helpers.Path(helpers._DATA.name) / 'draft-proposals' / self.root.name
                         / 'document-101' / 'latest.json')
        self.assertFalse(self.store.held())
        with self.engine.files:
            self.assertTrue(self.store.held())
            with self.engine.files:
                self.assertTrue(self.store.held())
            self.assertTrue(self.store.held())
        self.assertFalse(self.store.held())
        other = threading.Thread(target=lambda: self.seen.append(self.store.held()))
        self.seen = []
        with self.engine.files:
            other.start()
            other.join()
        self.assertEqual(self.seen, [False], 'another thread holding it is not this one')

    def test_the_record_follows_the_file(self):
        before = self.current()
        self.assertEqual(before['revision'], 1)
        self.assertEqual(before['file_sha256'],
                         workspace.sha256_file(self.root / 'document.md'))
        self.assertEqual(self.current(), before, 'an unchanged file is not split again')
        changed = example('document.md').replace('## Glossary', '## Words used').replace(
            'one running copy of an app', 'one running copy')
        self.write('document.md', changed)
        workspace.save(self.root, 'document', built=True)
        after = self.current()
        self.assertEqual(after['revision'], before['revision'] + 1)
        self.assertEqual(self.codec.join(after), changed)
        self.assertEqual(set(after['changed']),
                         {'opening', *(section['id'] for section in after['sections'])})
        self.assertEqual(set(after['changed'].values()), {after['revision']})
        old = {section['heading']: section['id'] for section in before['sections']}
        for section in after['sections']:
            if section['heading'] in old:
                self.assertEqual(section['id'], old[section['heading']], section['heading'])
        # A renamed heading keeps its id by its place, its neighbours being matched by theirs.
        self.assertEqual(headed(after, 'Words used')['id'], old['Glossary'])
        self.assertEqual(self.store.read('document'), after, 'the record is kept')

    def test_a_renamed_section_is_followed_by_its_covers_note(self):
        before = self.current()
        moved = example('document.md').replace('## When capacity holds', '## Capacity').replace(
            '## Why this matters\n\n<!-- covers: O3 -->\n\n', '## Why it matters\n\n'
            '<!-- covers: O3 -->\n\n')
        # The renamed section moves too, so its place alone would not find it.
        first, _, rest = moved.partition('## Why it matters')
        why, _, after = rest.partition('## What a rolling restart does')
        moved = first + '## What a rolling restart does' + after.replace(
            '## Summary', '## Why it matters' + why + '## Summary')
        self.write('document.md', moved)
        workspace.save(self.root, 'document', built=True)
        found = self.current()
        old = {section['heading']: section['id'] for section in before['sections']}
        self.assertEqual(headed(found, 'Why it matters')['id'], old['Why this matters'])
        self.assertEqual(headed(found, 'Capacity')['id'], old['When capacity holds'])
        self.assertEqual(len({section['id'] for section in found['sections']}),
                         len(found['sections']))

    def test_a_record_read_without_the_lock_is_not_kept(self):
        unlocked = drafts.current(self.store, self.codec, 'document')
        self.assertFalse(self.store.path('document', 'draft.json').exists())
        locked = self.current()
        self.assertTrue(self.store.path('document', 'draft.json').is_file())
        self.assertEqual({**unlocked, 'updated_at': None}, {**locked, 'updated_at': None},
                         'read with or without the lock, the same file reads the same way')

    def test_a_saved_part_is_written_to_the_file_and_accepted_on_the_desk(self):
        desk = drafts.TrainingDesk(self.store, self.codec)
        draft = self.current()
        part = headed(draft, 'Summary')['id']
        built_from = workspace.load(self.root)['artifacts']['document']['built_from']
        with self.engine.files:
            saved = desk.save('document', draft['revision'], part, 'Short summary.\n',
                              session='ab12')
        text = (self.root / 'document.md').read_text(encoding='utf-8')
        start, end = text.index('## Summary'), text.index('## Check your understanding')
        self.assertEqual(text[start:end], '## Summary\n\nShort summary.\n\n')
        old = example('document.md')
        self.assertEqual(text[:start] + text[end:], old[:old.index('## Summary')]
                         + old[old.index('## Check your understanding'):])
        session = workspace.load(self.root)
        entry = session['artifacts']['document']
        self.assertEqual(entry['built_from'], built_from, 'an edit keeps its inputs')
        self.assertEqual(entry['approved']['by'], 'desk')
        self.assertEqual(entry['approved']['sha256'], workspace.sha256_file(
            self.root / 'document.md'))
        event = [event for event in session['events'] if event['event'] == 'save'][-1]
        self.assertEqual((event['artifact'], event['via'], event['session']),
                         ('document', 'save', 'ab12'))
        self.assertEqual(saved['revision'], draft['revision'] + 1)
        self.assertEqual(saved['changed'][part], saved['revision'])
        self.assertEqual(saved['file_sha256'], entry['sha256'])
        self.assertEqual(self.current(), saved, 'the file is the record: not split again')
        self.assertEqual(sorted(path.name for path in self.store.folder('document').iterdir()),
                         ['draft.json', 'versions'], 'the joined copy is not left behind')
        # A restore is a save of its own kind.
        with self.engine.files:
            restored = desk.restore('document', saved['revision'], part, 0)
        self.assertIn('- A rolling restart replaces instances in batches',
                      (self.root / 'document.md').read_text(encoding='utf-8'))
        event = [event for event in workspace.load(self.root)['events']
                 if event['event'] == 'save'][-1]
        self.assertEqual(event['via'], 'restore')
        self.assertEqual(restored['revision'], saved['revision'] + 1)

    def test_a_form_older_than_the_file_is_told_to_reload(self):
        desk = drafts.TrainingDesk(self.store, self.codec)
        seen = self.current()['revision']
        self.write('document.md', example('document.md').replace('Capacity holds only',
                                                                  'Capacity holds just'))
        workspace.save(self.root, 'document', built=True)
        part = headed(self.current(), 'Summary')['id']
        with self.engine.files, self.assertRaisesRegex(
                ValueError, '^This draft changed since you opened it. Reload to see the '
                            'latest.$'):
            desk.save('document', seen, part, 'Typed in an old form.')

    def test_desk_writes_run_under_the_files_lock(self):
        desk = drafts.TrainingDesk(self.store, self.codec)
        draft = self.current()
        part = headed(draft, 'Summary')['id']
        before = (self.root / 'document.md').read_bytes()
        with self.assertRaisesRegex(RuntimeError, f'^{HELD}$'):
            desk.save('document', draft['revision'], part, 'Without the lock.')
        with self.assertRaisesRegex(RuntimeError, f'^{HELD}$'):
            self.store.write('document', draft, [part])
        self.assertEqual((self.root / 'document.md').read_bytes(), before)
        self.assertIsNone(self.store._making, 'a refused save leaves no kind of change behind')

    def test_a_held_material_is_saved_and_left_held(self):
        self.write('blueprint.md', example('blueprint.md') + '\nA changed plan.\n')
        workspace.save(self.root, 'blueprint', built=True)
        workspace.accept_desk(self.root, 'blueprint')
        state = workspace.statuses(self.root, workspace.load(self.root))
        self.assertEqual(state['document'], 'stale')
        approved = workspace.load(self.root)['artifacts']['document']['approved']
        desk = drafts.TrainingDesk(self.store, self.codec)
        draft = self.current()
        with self.engine.files:
            desk.save('document', draft['revision'], headed(draft, 'Summary')['id'],
                      'Typed while held.')
        self.assertIn('Typed while held.', (self.root / 'document.md').read_text())
        session = workspace.load(self.root)
        self.assertEqual(session['artifacts']['document']['approved'], approved,
                         'not accepted on the desk: an edit never clears what is out of date')
        self.assertEqual(workspace.statuses(self.root, session)['document'], 'stale')

    def test_a_part_closes_its_code_blocks(self):
        desk = drafts.TrainingDesk(self.store, self.codec)
        draft = self.current()
        part = headed(draft, 'Answer key')['id']
        before = (self.root / 'document.md').read_bytes()
        with self.engine.files, self.assertRaisesRegex(ValueError, f'^{UNCLOSED}$'):
            desk.save('document', draft['revision'], part, 'Run this:\n\n```\nrestart app')
        self.assertEqual((self.root / 'document.md').read_bytes(), before,
                         'the headings after it, Sources among them, stay sections')
        with self.engine.files:
            desk.save('document', draft['revision'], part, 'Run this:\n\n```\nrestart\n```')
        self.assertEqual(len(self.current()['sections']), len(draft['sections']))

    def test_the_sources_part_cannot_be_typed_in(self):
        desk = drafts.TrainingDesk(self.store, self.codec)
        draft = self.current()
        part = headed(draft, 'Sources')['id']
        before = (self.root / 'document.md').read_bytes()
        with self.engine.files, self.assertRaisesRegex(ValueError, f'^{LOCKED}$'):
            desk.save('document', draft['revision'], part, '1. Another source')
        self.assertEqual((self.root / 'document.md').read_bytes(), before)

    def test_a_save_names_a_listed_kind_of_change(self):
        desk = drafts.TrainingDesk(self.store, self.codec)
        draft = self.current()
        part = headed(draft, 'Summary')['id']
        with self.engine.files, self.assertRaisesRegex(
                (ValueError, WorkspaceError), '^Choose a listed kind of change.$'):
            desk.save('document', draft['revision'], part, 'Words.', source='first-pass')


if __name__ == '__main__':
    unittest.main()
