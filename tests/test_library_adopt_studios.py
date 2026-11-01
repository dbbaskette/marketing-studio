"""Add existing work to library for Presentation Studio, Training Studio and Infographic
Studio: delivered decks, guides and briefs marked ready, and approved infographics, each
under the studio's own library key, with a PDF only when it is checked against the exact
revision it came from.

Every workspace here is a disposable folder of synthetic records in each studio's own
layout, under the test's temporary folder; the library, the studios config and HOME are
disposable too. Where it matters, the studio's own code is run on the same fixture, in a
child process with the same disposable folders, to show the adapter reads it as the studio
does (its statuses, its PDF check, its keys) and that the studio's own Keep in library finds
the same document. No studio is started, and no assistant, renderer, slides tool, Git,
Google or network is used.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import marketing_studio  # noqa: F401  puts the core on the import path
from studio_core import document_library as library
from studio_core.document_library import adopt, infographic_existing, training_existing

REPO = Path(__file__).resolve().parents[1]
CREATED = '2026-03-02T09:10:11Z'
PDF = b'%PDF-1.4\n% synthetic deck\n1 0 obj << >> endobj\n%%EOF\n'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def tree(root):
    """Every file under a folder with its bytes' hash: what a test proves is left alone."""
    return {str(path.relative_to(root)): sha(path.read_bytes())
            for path in sorted(Path(root).rglob('*')) if path.is_file()}


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(data, (dict, list)):
        data = json.dumps(data, indent=2)
    path.write_bytes(data.encode() if isinstance(data, str) else data)
    return path


class Decks:
    """A synthetic Presentation Studio workspace: <root>/<deck>/run.json and the rest."""

    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True)

    def deck(self, ident, title, delivered=True, slides=2, created=CREATED, key=None,
             outline='# {title}\n\n## 1. Why now\n\n## 2. What changes\n', pdf=PDF):
        """A deck, delivered as a PowerPoint file after one whole-deck preview that left
        `deck.pdf` beside the `deck.pptx` it rendered, as Harness Slides does."""
        folder = self.root / ident
        deck = b'PK\x03\x04 synthetic deck ' + ident.encode()
        preview = 'work/build/whole-1/preview'
        run = {'schema': 1, 'id': ident, 'title': title, 'route': 'scratch',
               'form': {'title': title, 'output': 'pptx'}, 'created': created, 'gates': {},
               'steps': {}, 'revisions': [{'revision': 1, 'at': CREATED, 'pptx': 'deck.pptx'}]}
        if created is None:
            del run['created']
        write(folder / 'run.json', run)
        write(folder / 'outline.md', outline.format(title=title))
        write(folder / preview / 'deck.pptx', deck)
        if pdf is not None:
            write(folder / preview / 'deck.pdf', pdf)
        write(folder / preview / 'preview.json', {'deckSha256': sha(deck),
                                                  'slides': [{'number': n} for n in range(1, slides + 1)]})
        write(folder / 'work/build/state.json', {'rounds': [{
            'preview': preview, 'deck': sha(deck), 'pdf': sha(pdf) if pdf is not None else None,
            'slides': [{'number': n} for n in range(1, slides + 1)]}], 'deck': f'{preview}/deck.pptx'})
        if delivered:
            write(folder / 'deck.pptx', deck)
            write(folder / 'deliver.json', {'output': 'pptx', 'url': None, 'fileId': None,
                                            'pptx': 'deck.pptx', 'revision': 1, 'at': CREATED,
                                            'deck_sha256': sha(deck)})
        if key:
            write(folder / 'sources/library.json', {'key': key, 'state': 'failed',
                                                    'problem': 'The library is busy.'})
        return folder


class Trainings:
    """A synthetic Training Studio workspace: <root>/<training>/.training-studio/session.json,
    every material on disk, recorded and approved as Training Studio records them."""

    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True)

    @staticmethod
    def entry(name, digest, built_from, by='page'):
        return {'file': name, 'sha256': digest, 'built_from': built_from,
                'approved': {'sha256': digest, 'inputs': dict(built_from), 'at': CREATED, 'by': by}
                if by else None}

    def training(self, folder, title, levels=('101',), marked=None, started_at=CREATED,
                 brief_kind='product', flow='desk'):
        """`marked` is {material: who approved it}: 'page' (the person), 'desk' (the desk on
        its way through), or None (a draft)."""
        root = self.root / folder
        files = {
            'intake.md': '# Intake\n\nTeach the restart runbook.\n',
            '.training-studio/research-plan.json': json.dumps({'topic': title, 'items': [
                {'id': 'q1', 'question': 'How is one instance restarted?'}]}),
            '.harness-research/research-report.md': '# Research\n\nRestart one at a time.\n',
            '.harness-research/research.json': json.dumps({'schema': 1, 'owner': 'harness-research',
                                                           'items': [], 'results': {}}),
            'research-report.md': '# Research\n\nRestart one at a time.\n',
        }
        # A training with no levels keeps its materials at the top: blueprint.md, and so on.
        places = [(level, f'{level}/', f'@{level}') for level in levels] or [(None, '', '')]
        for level, folder_, _ in places:
            files[f'{folder_}blueprint.md'] = f'# Blueprint {level}\n\n## M1 Restart\n\n### O1 Restart one instance\n'
            files[f'{folder_}document.md'] = (
                f'# {title}\n\n## Restarting\n\n<!-- covers: O1 -->\n\nRestart one instance at a '
                f'time.<!-- findings: q1 -->\n\n```\n<!-- covers: kept in code -->\n```\n')
            files[f'{folder_}{brief_kind}-brief.md'] = f'# Brief {level}\n\nWhat the product does.\n'
        for name, text in files.items():
            write(root / name, text)
        digest = {name: sha((root / name).read_bytes()) for name in files}
        report, record, copy = (digest[name] for name in (
            '.harness-research/research-report.md', '.harness-research/research.json', 'research-report.md'))
        research = sha('\n'.join([report, record, copy]).encode())
        artifacts = {
            'intake': self.entry('intake.md', digest['intake.md'], {}),
            'research-plan': self.entry('.training-studio/research-plan.json',
                                        digest['.training-studio/research-plan.json'],
                                        {'intake': digest['intake.md']}),
            'research': self.entry('.harness-research/research-report.md', report,
                                   {'research-plan': digest['.training-studio/research-plan.json']}),
        }
        marked = marked if marked is not None else {}
        for _, folder_, at in places:
            blueprint = digest[f'{folder_}blueprint.md']
            artifacts[f'blueprint{at}'] = self.entry(f'{folder_}blueprint.md', blueprint,
                                                     {'intake': digest['intake.md'], 'research': research})
            artifacts[f'document{at}'] = self.entry(
                f'{folder_}document.md', digest[f'{folder_}document.md'],
                {f'blueprint{at}': blueprint}, by=marked.get(f'document{at}'))
            artifacts[f'brief{at}'] = self.entry(
                f'{folder_}{brief_kind}-brief.md', digest[f'{folder_}{brief_kind}-brief.md'],
                {f'blueprint{at}': blueprint, 'research': research, 'setting:brief_kind': brief_kind},
                by=marked.get(f'brief{at}'))
        for entry in artifacts.values():
            if entry['approved'] is None:
                del entry['approved']
        session = {'schema': 1, 'id': folder, 'title': title, 'levels': list(levels), 'sizing': {},
                   'stage': 'done', 'settings': {'deck_target': None, 'brand': None,
                                                 'brief_kind': brief_kind, 'stages': ['document', 'brief'],
                                                 'copies': [], 'approval': 'page'},
                   'unavailable': {}, 'pins': {}, 'artifacts': artifacts, 'exports': {},
                   'decisions': [], 'events': [], 'requests': [],
                   'research': {'report_sha256': copy, 'record_sha256': record}}
        if flow:
            session['flow'] = flow
        write(root / '.training-studio/session.json', session)
        if started_at:
            write(root / '.training-studio/run.json', {'flow': flow, 'started_at': started_at})
        return root

    @staticmethod
    def session(root):
        return json.loads((root / '.training-studio/session.json').read_text())


# Infographic Studio's own synthetic contract record (tests/helpers.py), approved and
# visually reviewed, published through its own store into a disposable workspace with one
# export of its approved files. Run in a child process; nothing is rendered.
INFOGRAPHIC = r'''
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(sys.path[0]) / 'tests'))
import helpers
from runner.contracts import basis, canonical, digest
from runner.validation import REQUIRED_CHECKS
from runner.workspace import Store, _atomic
root, owner, ident, title, mode = Path(sys.argv[1]), sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
p = helpers.project()
p.update(owner=owner, id=ident)
p['brief']['title'] = title
review = {'basis': basis(p), 'scene_digest': digest(p['scene']), 'sequence': 1, 'status': 'passed',
          'observations': [{'kind': 'counts', 'text': 'Synthetic review of the composed page.'}],
          'findings': []}
p['checks'] = [{'id': 'check' + str(i), 'kind': kind, 'scene_digest': digest(p['scene']),
                'basis': basis(p), 'status': 'passed', 'blocking': True,
                **({'review_digest': digest(review)} if kind == 'visual' else {})}
               for i, kind in enumerate(sorted(REQUIRED_CHECKS))]
draft = mode == 'draft'
p['approval'] = None if draft else {'revision': p['revision'], 'owner': owner,
                                    'basis': basis(p), 'scene_digest': digest(p['scene'])}
marker = root / '.infographic-studio' / 'workspace.json'
if not marker.exists():
    _atomic(marker, canonical({'schema': 1, 'product': 'Infographic Studio', 'owner': owner}))
    (root / 'projects').mkdir()
store = Store(root, owner)
raw = b'Synthetic counts: baseline 12; comparison 24.'
files = {'png': ('page.png', b'\x89PNG\r\n\x1a\n synthetic'), 'pdf': ('page.pdf', b'%PDF-1.4\n% synthetic page\n%%EOF\n'),
         'svg': ('page.svg', b'<svg xmlns="http://www.w3.org/2000/svg"/>'),
         'text': ('page.txt', (title + '\nBaseline 12, comparison 24.\n').encode())}
mimes = {'png': 'image/png', 'pdf': 'application/pdf', 'svg': 'image/svg+xml', 'text': 'text/plain; charset=utf-8'}
key = 'e_' + digest({'project': p, 'draft': draft})[:24]
with store.locked():
    store._publish(p)
    store.write_blob(ident, 'sources/input.txt', raw)
    store.write_blob(ident, 'jobs/visual_1/review.json', canonical(review))
    listed = []
    for kind, (name, data) in files.items():
        store.write_blob(ident, f'exports/{key}/{name}', data)
        listed.append({'format': kind, 'file': f'exports/{key}/{name}', 'sha256': __import__('hashlib').sha256(data).hexdigest(),
                       'bytes': len(data), 'mime': mimes[kind]})
    manifest = {'schema': 1, 'id': key, 'revision': p['revision'], 'basis': basis(p),
                'scene_digest': digest(p['scene']), 'checks_digest': digest(p['checks']),
                'approval_digest': digest(p['approval']), 'draft': draft,
                'measurement_sha256': '0' * 64, 'font_caveat': 'Synthetic font licence.', 'files': listed}
    store.write_blob(ident, f'exports/{key}/manifest.json', canonical(manifest))
print(json.dumps({'export': key, 'revision': p['revision']}))
'''


class StudiosCase(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name).resolve()
        self.config = self.base / 'studios-config.json'
        self.env = {'HOME': str(self.base / 'home'), 'STUDIOS_CONFIG': str(self.config),
                    'STUDIOS_LIBRARY': str(self.base / 'library')}
        patcher = mock.patch.dict(os.environ, self.env)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.decks = Decks(self.base / 'presentations')
        self.trainings = Trainings(self.base / 'trainings')
        self.pictures = self.base / 'infographics'
        self.pictures.mkdir()
        self.owner = '0123456789abcdef0123456789abcdef'
        self.known = {'blog': None, 'presentation': {'root': str(self.decks.root)},
                      'training': {'root': str(self.trainings.root)},
                      'infographic': {'root': str(self.pictures)}}

    def studio(self, which, code, *args):
        """Run `code` with that studio's own modules, in a child process that sees only the
        test's disposable folders, and return the JSON it prints last."""
        native = REPO / 'studios' / which
        env = {'PATH': os.environ.get('PATH', ''), **self.env,
               'TRAINING_STUDIO_DATA': str(self.base / 'training-data'),
               'PRESENTATION_STUDIO_DATA': str(self.base / 'presentation-data'),
               'INFOGRAPHIC_STUDIO_DATA': str(self.base / 'infographic-data'),
               'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull, 'BROWSER': 'false'}
        # A runner package puts the studio's own scripts and the core on the import path.
        prelude = f'import sys; sys.path.insert(0, {str(native)!r})\n' \
            + ('import runner\n' if which in ('training', 'presentation') else '')
        done = subprocess.run([sys.executable, '-I', '-c', prelude + code,
                               *map(str, args)], env=env, capture_output=True, text=True,
                              timeout=60, cwd=self.base)
        self.assertEqual(done.returncode, 0, done.stderr[-3000:])
        return json.loads(done.stdout.strip().splitlines()[-1])

    def infographic(self, ident, title, mode='approved'):
        return self.studio('infographic', INFOGRAPHIC, self.pictures, self.owner, ident, title, mode)

    def items(self, found):
        return {row['title']: row for row in found['items']}

    def places(self, found):
        return {row['studio']: row for row in found['workspaces']}

    def catalog(self, **filters):
        found = library.opened()
        return found.catalog(limit=50, **filters)['items'] if found else []

    def revision(self, row, number=None):
        place = library.opened().root / 'documents' / row['id'] / 'revisions' / str(number or row['revision'])
        return json.loads((place / 'revision.json').read_text())


KEEP_DECK = ('import json; from pathlib import Path; from runner import library_keep, decks\n'
             'root = Path(sys.argv[1])\n'
             'print(json.dumps(library_keep.keep(root, decks.read_run(root), decks.delivered(root))))')
DECK_PDF = ('import json, hashlib; from pathlib import Path; from runner import library_keep, decks\n'
            'root = Path(sys.argv[1]); run = decks.read_run(root)\n'
            'data, why = library_keep.rendered_pdf(root, decks.delivered(root), run)\n'
            'print(json.dumps([hashlib.sha256(data).hexdigest() if data else None, why, '
            'library_keep._key(root, run)]))')


class PresentationTests(StudiosCase):
    def test_only_delivered_decks_are_offered_with_the_pdf_checked_as_deliver_checks_it(self):
        good = self.decks.deck('launch-plan', 'Launch plan')
        self.decks.deck('draft-deck', 'Draft deck', delivered=False)
        before = tree(self.decks.root)
        found = adopt.preview(self.known)
        self.assertEqual(tree(self.decks.root), before)
        self.assertFalse((self.base / 'library').exists())
        place = self.places(found)['presentation']
        self.assertEqual((place['state'], place['count'], place['summary']), ('found', 1, '1 delivered deck.'))
        self.assertIn('1 deck is not delivered yet, so it is not offered.', place['gaps'])
        row = self.items(found)['Launch plan']
        self.assertEqual((row['kind_label'], row['studio_label'], row['note'], row['formats'], row['state']),
                         ('Presentation', 'Presentation Studio', 'Delivered deck', ['markdown', 'pdf'], 'new'))
        self.assertNotIn('Draft deck', self.items(found))
        # Presentation Studio's own check finds exactly this PDF, and makes the same key.
        candidate = next(one for one in adopt._scan(self.known)[1] if one['studio'] == 'presentation')
        self.assertEqual(self.studio('presentation', DECK_PDF, good), [sha(PDF), None, candidate['key']])

        done = adopt.confirm(self.known, found['signature'])
        self.assertEqual((done['added'], done['failed']), (1, []))
        self.assertEqual(tree(self.decks.root), before, 'Adding writes nothing in the workspace.')
        [kept] = self.catalog(kind='presentation')
        self.assertEqual((kept['formats'], kept['pdf'], kept['project']['revision']),
                         (['markdown', 'pdf'], 'saved', 1))
        self.assertEqual(library.opened().download(kept['id'], 1, 'pdf')[2], PDF)
        record = self.revision(kept)
        self.assertEqual((record['key'], record['native']['deck'], record['native']['key']),
                         (candidate['key'], 'launch-plan', 'deck'))

    def test_a_deck_delivered_later_in_presentation_studio_is_the_same_document(self):
        folder = self.decks.deck('launch-plan', 'Launch plan')
        adopt.confirm(self.known, adopt.preview(self.known)['signature'])
        [first] = self.catalog()
        # Presentation Studio's own Keep in library (as Deliver calls it) finds the added
        # document by the deck's key: no second document and no new revision.
        kept = self.studio('presentation', KEEP_DECK, folder)
        self.assertEqual((kept['state'], kept['document'], kept['revision'], kept['pdf']),
                         ('kept', first['id'], 1, 'saved'))
        self.assertEqual(len(self.catalog()), 1)
        again = adopt.preview(self.known)
        self.assertEqual((again['adding'], again['kept']), (0, 1))

    def test_a_deck_deliver_already_kept_is_already_in_the_library(self):
        folder = self.decks.deck('launch-plan', 'Launch plan')
        kept = self.studio('presentation', KEEP_DECK, folder)
        found = adopt.preview(self.known)
        self.assertEqual((found['adding'], found['kept']), (0, 1))
        self.assertEqual(self.items(found)['Launch plan']['state_label'], 'Already in the library')
        self.assertEqual(adopt.confirm(self.known, found['signature'])['unchanged'], 1)
        self.assertEqual([row['id'] for row in self.catalog()], [kept['document']])
        # The preview Harness Slides left is cleared away later: the deck has no checked PDF
        # here now, but the library keeps its own, and nothing is added without it.
        shutil.rmtree(folder / 'work')
        later = adopt.preview(self.known)
        self.assertEqual((later['adding'], later['kept']), (0, 1))
        row = self.items(later)['Launch plan']
        self.assertEqual((row['formats'], row['gaps']), (['markdown', 'pdf'], []))

    def test_the_recorded_key_is_used(self):
        key = 'presentation:launch-plan-abcdefabcdef'
        self.decks.deck('launch-plan', 'Launch plan', key=key)
        adopt.confirm(self.known, adopt.preview(self.known)['signature'])
        [row] = self.catalog()
        self.assertEqual((self.revision(row)['key'], self.revision(row)['native']['key']), (key, 'recorded'))

    def test_a_stale_or_mismatched_pdf_is_left_out_and_said(self):
        redrawn = self.decks.deck('redrawn', 'Redrawn deck')
        state = json.loads((redrawn / 'work/build/state.json').read_text())
        state['rounds'].append({**state['rounds'][0], 'deck': 'f' * 64})     # drawn again since
        write(redrawn / 'work/build/state.json', state)
        changed = self.decks.deck('changed', 'Changed PDF')
        write(changed / 'work/build/whole-1/preview/deck.pdf', PDF.replace(b'synthetic', b'different'))
        selected = self.decks.deck('selected', 'Selected changes')
        run = json.loads((selected / 'run.json').read_text())
        write(selected / 'run.json', {**run, 'route': 'existing', 'form': {**run['form'], 'level': 'selected'}})
        unrecorded = self.decks.deck('unrecorded', 'Unrecorded deck')
        said = json.loads((unrecorded / 'deliver.json').read_text())
        del said['deck_sha256']
        write(unrecorded / 'deliver.json', said)
        found = self.items(adopt.preview(self.known))
        for title, words in (('Redrawn deck', 'drawn again after it was delivered'),
                             ('Changed PDF', 'no longer matches the delivered deck'),
                             ('Selected changes', 'Selected changes'),
                             ('Unrecorded deck', 'recorded which deck file')):
            with self.subTest(title):
                self.assertEqual(found[title]['formats'], ['markdown'])
                self.assertIn(words, ' '.join(found[title]['gaps']))
        # Presentation Studio's own check refuses each of them too.
        for folder in (redrawn, changed, selected, unrecorded):
            self.assertIsNone(self.studio('presentation', DECK_PDF, folder)[0], folder.name)
        adopt.confirm(self.known, adopt.preview(self.known)['signature'])
        rows = self.catalog()
        self.assertEqual(len(rows), 4)
        self.assertTrue(all(row['formats'] == ['markdown'] and row['pdf'] == 'needs-export' for row in rows))

    def test_a_pdf_changed_after_the_preview_refuses_the_confirm(self):
        folder = self.decks.deck('launch-plan', 'Launch plan')
        found = adopt.preview(self.known)
        write(folder / 'work/build/whole-1/preview/deck.pdf', PDF + b'changed')
        with self.assertRaisesRegex(library.LibraryError, 'changed since'):
            adopt.confirm(self.known, found['signature'])
        self.assertFalse((self.base / 'library').exists())

    def test_a_deck_with_no_outline_or_no_key_is_left_out_and_said(self):
        self.decks.deck('no-outline', 'No outline', outline='  \n')
        self.decks.deck('no-key', 'No key', created=None)
        place = self.places(adopt.preview(self.known))['presentation']
        self.assertEqual(place['count'], 0)
        said = ' '.join(place['gaps'])
        self.assertIn('“No outline” was left out: it has no slide outline', said)
        self.assertIn('“No key” was left out: Presentation Studio has no library key', said)


STATUSES = ('import json; from pathlib import Path; import workspace\n'
            'root = Path(sys.argv[1])\n'
            'print(json.dumps(workspace.person_statuses(root, workspace.load(root))))')
KEEP_MATERIAL = ('import json; from pathlib import Path; from runner import library\n'
                 'print(json.dumps(library.keep(Path(sys.argv[1]), sys.argv[2])))')


class TrainingTests(StudiosCase):
    def test_only_guides_and_briefs_the_person_marked_ready_are_offered(self):
        root = self.trainings.training('restart-runbook', 'Restart runbook', levels=('101', '201'),
                                       marked={'document@101': 'page', 'brief@101': 'desk',
                                               'document@201': 'page', 'brief@201': None})
        # Edited after it was marked ready: a draft again.
        write(root / '201/document.md', '# Edited since\n')
        # Training Studio reads the same statuses from the same files.
        statuses = self.studio('training', STATUSES, root)
        self.assertEqual({name: statuses[name] for name in ('document@101', 'brief@101', 'document@201', 'brief@201')},
                         {'document@101': 'approved', 'brief@101': 'draft', 'document@201': 'draft',
                          'brief@201': 'draft'})
        before = tree(self.trainings.root)
        found = adopt.preview(self.known)
        self.assertEqual(tree(self.trainings.root), before)
        place = self.places(found)['training']
        self.assertEqual((place['count'], place['summary']), (1, '1 learner guide or brief marked ready.'))
        self.assertIn('3 learner guides or briefs not marked ready are not offered.', place['gaps'])
        row = self.items(found)['Restart runbook: level 101 learner guide']
        self.assertEqual((row['kind_label'], row['studio_label'], row['note'], row['formats']),
                         ('Training material', 'Training Studio', 'Marked ready', ['markdown']))
        self.assertIn('no PDF', ' '.join(row['gaps']))

        done = adopt.confirm(self.known, found['signature'])
        self.assertEqual(done['added'], 1)
        self.assertEqual(tree(self.trainings.root), before, 'Adding writes nothing in the workspace.')
        [kept] = self.catalog()
        record = self.revision(kept)
        digest = Trainings.session(root)['artifacts']['document@101']['sha256']
        self.assertEqual((record['native']['material'], record['native']['sha256'], record['project']['revision']),
                         ('document@101', digest, digest[:12]))
        # As learners read it: coverage notes are left out, as Training Studio leaves them out.
        text = library.opened().preview(kept['id'])['text']
        self.assertNotIn('covers: O1', text)
        self.assertNotIn('findings', text)
        self.assertIn('<!-- covers: kept in code -->', text)
        stripped = self.studio('training', (
            'import json; import gdocs\n'
            'print(json.dumps(gdocs.strip_comments(open(sys.argv[1], encoding="utf-8").read())[0]))'),
            root / '101/document.md')
        self.assertEqual(text, stripped)

    def test_marking_ready_later_in_training_studio_is_the_same_document(self):
        root = self.trainings.training('restart-runbook', 'Restart runbook',
                                       marked={'document@101': 'page', 'brief@101': 'page'})
        found = adopt.preview(self.known)
        keys = sorted(one['key'] for one in adopt._scan(self.known)[1])
        self.assertTrue(all(key.startswith('training:restart-runbook-') for key in keys), keys)
        self.assertEqual([key.rsplit('.', 1)[1] for key in keys], ['brief-101', 'document-101'])
        adopt.confirm(self.known, found['signature'])
        first = {row['title']: row['id'] for row in self.catalog()}
        # Training Studio's own Keep in library (as Mark ready calls it) finds each one.
        for name, title in (('document@101', 'Restart runbook: level 101 learner guide'),
                            ('brief@101', 'Restart runbook: level 101 brief')):
            kept = self.studio('training', KEEP_MATERIAL, root, name)
            self.assertEqual((kept['state'], kept['document'], kept['revision']), ('kept', first[title], 1))
        self.assertEqual(len(self.catalog()), 2)
        again = adopt.preview(self.known)
        self.assertEqual((again['adding'], again['kept']), (0, 2))

    def test_what_mark_ready_already_kept_is_already_in_the_library(self):
        root = self.trainings.training('restart-runbook', 'Restart runbook', marked={'document@101': 'page'})
        kept = self.studio('training', KEEP_MATERIAL, root, 'document@101')
        self.assertEqual(kept['state'], 'kept')
        found = adopt.preview(self.known)
        self.assertEqual((found['adding'], found['kept']), (0, 1))
        self.assertEqual(adopt.confirm(self.known, found['signature'])['unchanged'], 1)
        self.assertEqual(len(self.catalog()), 1)

    def test_out_of_date_skipped_and_keyless_work_is_not_offered(self):
        stale = self.trainings.training('stale', 'Stale guide', marked={'document@101': 'page'})
        write(stale / '101/blueprint.md', '# Blueprint 101\n\n## M1 Changed\n\n### O1 Changed\n')
        self.assertEqual(self.studio('training', STATUSES, stale)['document@101'], 'stale')
        skipped = self.trainings.training('skipped', 'Skipped brief', marked={'brief@101': 'page'})
        session = Trainings.session(skipped)
        session['settings']['stages'] = ['document']
        write(skipped / '.training-studio/session.json', session)
        self.assertEqual(self.studio('training', STATUSES, skipped)['brief@101'], 'skipped')
        self.trainings.training('chat-only', 'Chat only', marked={'document@101': 'page'}, started_at=None)
        place = self.places(adopt.preview(self.known))['training']
        self.assertEqual(place['count'], 0)
        self.assertIn('“Chat only” was left out: Training Studio has no library key', ' '.join(place['gaps']))

    def test_a_training_with_no_levels_and_a_recorded_key(self):
        root = self.trainings.training('one-lesson', 'One lesson', levels=(), marked={'document': 'page'})
        write(root / 'sources/library.json', {'key': 'training:one-lesson-0123456789ab', 'materials': {}})
        [one] = adopt._scan(self.known)[1]
        self.assertEqual((one['key'], one['title']), ('training:one-lesson-0123456789ab.document',
                                                       'One lesson: learner guide'))
        self.assertEqual(self.studio('training', STATUSES, root)['document'], 'approved')

    def test_an_odd_training_is_a_gap_and_never_stops_the_rest(self):
        self.trainings.training('fine', 'Fine guide', marked={'document@101': 'page'})
        odd = self.trainings.root / 'odd'
        write(odd / '.training-studio/session.json', {'schema': 1, 'title': 'Odd', 'levels': 'all'})
        write(self.trainings.root / 'broken/.training-studio/session.json', '{not json')
        place = self.places(adopt.preview(self.known))['training']
        self.assertEqual(place['count'], 1)
        said = ' '.join(place['gaps'])
        self.assertIn('“odd” was left out', said)
        self.assertIn('“broken” was left out', said)

    def test_a_material_the_desk_accepted_is_ready_once_the_person_marks_it(self):
        root = self.trainings.training('desk', 'Desk guide', marked={'document@101': 'desk'})
        self.assertEqual(adopt.preview(self.known)['total'], 0)
        session = Trainings.session(root)
        session['desk_ready'] = {'document@101': session['artifacts']['document@101']['sha256']}
        write(root / '.training-studio/session.json', session)
        self.assertEqual(self.studio('training', STATUSES, root)['document@101'], 'approved')
        self.assertEqual(adopt.preview(self.known)['total'], 1)


INFOGRAPHIC_KEEP = ('import json; from pathlib import Path\n'
                    'from runner import library; from runner.workspace import Store\n'
                    'print(json.dumps(library.keep(Store(Path(sys.argv[1]), sys.argv[2]), sys.argv[3])))')
DELIVERIES = ('import json; from pathlib import Path\n'
              'from runner.engine import Engine; from runner.workspace import Store\n'
              'found = Engine(Store(Path(sys.argv[1]), sys.argv[2])).deliveries(sys.argv[3])\n'
              'print(json.dumps([[one["id"], one["approved_current"]] for one in found]))')


class InfographicTests(StudiosCase):
    def export(self, ident, made, name):
        return self.pictures / 'projects' / ident / 'exports' / made['export'] / name

    def test_only_approved_exports_are_offered_under_infographic_studios_key(self):
        made = self.infographic('restart1', 'Restart one instance')
        self.infographic('draft1', 'Draft page', mode='draft')
        # Infographic Studio's own reading: the one export is approved and current.
        self.assertEqual(self.studio('infographic', DELIVERIES, self.pictures, self.owner, 'restart1'),
                         [[made['export'], True]])
        self.assertEqual(self.studio('infographic', DELIVERIES, self.pictures, self.owner, 'draft1')[0][1], False)
        before = tree(self.pictures)
        found = adopt.preview(self.known)
        self.assertEqual(tree(self.pictures), before)
        place = self.places(found)['infographic']
        self.assertEqual((place['count'], place['summary']), (1, '1 approved infographic.'))
        self.assertIn('1 infographic is not approved', ' '.join(place['gaps']))
        row = self.items(found)['Restart one instance']
        self.assertEqual((row['kind_label'], row['note'], row['formats']),
                         ('Infographic', 'Approved infographic', ['markdown', 'pdf']))
        done = adopt.confirm(self.known, found['signature'])
        self.assertEqual(done['added'], 1)
        self.assertEqual(tree(self.pictures), before, 'Adding writes nothing in the workspace.')
        [kept] = self.catalog()
        record = self.revision(kept)
        self.assertEqual(record['key'], f'infographic:{self.owner[:12]}-restart1')
        self.assertEqual((record['native']['export'], kept['pdf']), (made['export'], 'saved'))
        self.assertEqual(library.opened().download(kept['id'], 1, 'pdf')[2],
                         self.export('restart1', made, 'page.pdf').read_bytes())
        self.assertEqual(library.opened().download(kept['id'], 1, 'markdown')[2],
                         self.export('restart1', made, 'page.txt').read_bytes())

    def test_keeping_in_infographic_studio_later_or_before_is_the_same_document(self):
        self.infographic('restart1', 'Restart one instance')
        adopt.confirm(self.known, adopt.preview(self.known)['signature'])
        [first] = self.catalog()
        kept = self.studio('infographic', INFOGRAPHIC_KEEP, self.pictures, self.owner, 'restart1')
        self.assertEqual((kept['state'], kept['document'], kept['library_revision']), ('kept', first['id'], 1))
        self.infographic('other1', 'Another page')
        self.studio('infographic', INFOGRAPHIC_KEEP, self.pictures, self.owner, 'other1')
        found = adopt.preview(self.known)
        self.assertEqual((found['adding'], found['kept']), (0, 2))
        self.assertEqual(len(self.catalog()), 2)

    def test_a_changed_pdf_is_left_out_and_changed_text_leaves_it_out(self):
        made = self.infographic('restart1', 'Restart one instance')
        self.export('restart1', made, 'page.pdf').write_bytes(b'%PDF-1.4\n% changed\n%%EOF\n')
        texts = self.infographic('words1', 'Changed words')
        self.export('words1', texts, 'page.txt').write_text('Not what was approved.\n')
        found = adopt.preview(self.known)
        row = self.items(found)['Restart one instance']
        self.assertEqual(row['formats'], ['markdown'])
        self.assertIn('Its PDF does not match the approved export', ' '.join(row['gaps']))
        self.assertNotIn('Changed words', self.items(found))
        self.assertIn('“Changed words” was left out: its approved files no longer match',
                      ' '.join(self.places(found)['infographic']['gaps']))
        adopt.confirm(self.known, found['signature'])
        [kept] = self.catalog()
        self.assertEqual((kept['formats'], kept['pdf']), (['markdown'], 'needs-export'))

    def test_a_source_changed_since_approval_is_not_approved(self):
        self.infographic('restart1', 'Restart one instance')
        (self.pictures / 'projects/restart1/sources/input.txt').write_bytes(b'Changed.')
        self.assertFalse(self.studio('infographic', DELIVERIES, self.pictures, self.owner, 'restart1')[0][1])
        self.assertEqual(adopt.preview(self.known)['total'], 0)

    def test_a_folder_that_is_not_a_workspace_is_said(self):
        shutil.rmtree(self.pictures)
        self.pictures.mkdir()
        place = self.places(adopt.preview(self.known))['infographic']
        self.assertEqual(place['state'], 'unreadable')
        self.assertIn('not an Infographic Studio workspace', place['summary'])


class AllStudiosTests(StudiosCase):
    def test_one_preview_of_every_studio_writes_nothing_and_adding_twice_adds_once(self):
        self.decks.deck('launch-plan', 'Launch plan')
        self.trainings.training('restart-runbook', 'Restart runbook', marked={'document@101': 'page'})
        self.infographic('restart1', 'Restart one instance')
        before = {name: tree(Path(place['root'])) for name, place in self.known.items() if place}
        found = adopt.preview(self.known)
        self.assertEqual((found['total'], found['new']), (3, 3))
        self.assertFalse((self.base / 'library').exists(), 'A preview does not make the library.')
        self.assertFalse(self.config.exists(), 'A preview saves no setting.')
        done = adopt.confirm(self.known, found['signature'])
        self.assertEqual((done['added'], done['failed']), (3, []))
        self.assertEqual({name: tree(Path(place['root'])) for name, place in self.known.items() if place}, before)
        again = adopt.preview(self.known)
        self.assertEqual((again['adding'], again['kept']), (0, 3))
        self.assertEqual(adopt.confirm(self.known, again['signature'])['unchanged'], 3)
        self.assertEqual(len(self.catalog()), 3)
        for place in self.places(again).values():
            self.assertNotIn('not offered yet', place['summary'])

    def test_a_new_revision_of_the_work_adds_a_library_revision(self):
        folder = self.decks.deck('launch-plan', 'Launch plan')
        adopt.confirm(self.known, adopt.preview(self.known)['signature'])
        write(folder / 'outline.md', '# Launch plan\n\n## 1. Why now\n\n## 2. What changes\n\n## 3. Next\n')
        found = adopt.preview(self.known)
        self.assertEqual((found['changed'], self.items(found)['Launch plan']['state_label']),
                         (1, 'Adds revision 2'))
        self.assertEqual(adopt.confirm(self.known, found['signature'])['revised'], 1)
        [row] = self.catalog()
        self.assertEqual(row['revision'], 2)


@unittest.skipUnless(shutil.which('node'), 'Node.js runs the page script.')
class PageTests(StudiosCase):
    """The Add existing work sheet, run through the shared settings page harness."""

    def test_the_sheet_lists_every_studios_finished_work_with_its_formats(self):
        self.decks.deck('launch-plan', 'Launch plan')
        self.decks.deck('draft-deck', 'Draft deck', delivered=False)
        self.trainings.training('restart-runbook', 'Restart runbook', marked={'document@101': 'page'})
        self.infographic('restart1', 'Restart one instance')
        plan = self.base / 'plan.json'
        plan.write_text(json.dumps({'steps': [
            {'responses': {'library-existing': adopt.preview(self.known)}},
            {'press': '#library-existing-preview'},
            {'snapshot': 'preview', 'ids': ['library-existing-result']}]}))
        done = subprocess.run(['node', str(REPO / 'tests' / 'settings_page_harness.js'), str(plan)],
                              capture_output=True, text=True, timeout=30)
        self.assertEqual(done.returncode, 0, done.stderr)
        shown = json.loads(done.stdout)['preview']['words']['library-existing-result']
        for words in ('1 delivered deck.', '1 deck is not delivered yet',
                      '1 learner guide or brief marked ready.', '1 approved infographic.',
                      'Presentation · Presentation Studio · Delivered deck · Markdown, PDF',
                      'Training material · Training Studio · Marked ready · Markdown',
                      'Infographic · Infographic Studio · Approved infographic · Markdown, PDF',
                      'Restart runbook: level 101 learner guide', '3 items found: 3 new',
                      'Add 3 to library'):
            self.assertIn(words, shown)
        self.assertNotIn('not offered yet', shown)
        self.assertNotIn('Draft deck', shown)


class StorePdfTests(StudiosCase):
    """Library.adopt takes a checked PDF as retain does, and never drops one it keeps."""

    def test_adopt_keeps_a_saved_pdf_and_adding_again_or_without_it_adds_nothing(self):
        made = library.opened(create=True)
        first = made.adopt('presentation:deck-0123456789ab', 'presentation', 'presentation', 'created',
                           'Deck', text='# Deck\n', pdf={'state': 'saved', 'data': PDF})
        self.assertEqual((first['revision'], first['changed']), (1, True))
        self.assertEqual(made.keyed(['presentation:deck-0123456789ab'])['presentation:deck-0123456789ab']['pdf'],
                         sha(PDF))
        for pdf in ({'state': 'saved', 'data': PDF}, None, {'state': 'needs-export', 'reason': 'Gone.'}):
            again = made.adopt('presentation:deck-0123456789ab', 'presentation', 'presentation', 'created',
                               'Deck', text='# Deck\n', pdf=pdf)
            self.assertEqual((again['revision'], again['changed']), (1, False), pdf)
        # The same text from Deliver with the same PDF is the same revision too.
        kept = made.retain('presentation:deck-0123456789ab', 'presentation', 'presentation', 'Deck',
                           '# Deck\n', pdf={'state': 'saved', 'data': PDF})
        self.assertEqual((kept['revision'], kept['changed']), (1, False))
        # Another PDF, or a kept one gone missing, adds a revision with it.
        other = PDF.replace(b'synthetic', b'another')
        self.assertEqual(made.adopt('presentation:deck-0123456789ab', 'presentation', 'presentation',
                                    'created', 'Deck', text='# Deck\n',
                                    pdf={'state': 'saved', 'data': other})['revision'], 2)
        place = made.root / 'documents' / first['document'] / 'revisions' / '2' / 'content.pdf'
        place.unlink()
        self.assertIsNone(made.keyed(['presentation:deck-0123456789ab'])['presentation:deck-0123456789ab']['pdf'])
        self.assertEqual(made.adopt('presentation:deck-0123456789ab', 'presentation', 'presentation',
                                    'created', 'Deck', text='# Deck\n',
                                    pdf={'state': 'saved', 'data': other})['revision'], 3)

    def test_adopt_refuses_what_is_not_a_pdf(self):
        made = library.opened(create=True)
        with self.assertRaisesRegex(library.LibraryError, 'only once it has been exported'):
            made.adopt('infographic:abc-1', 'infographic', 'infographic', 'created', 'Page',
                       text='Words.\n', pdf={'state': 'saved', 'data': b'not a pdf'})
        self.assertEqual(made.catalog()['total'], 0)


if __name__ == '__main__':
    unittest.main()
