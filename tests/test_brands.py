"""The Brands section: making and updating brand packs and icon libraries.

Everything here is disposable: shared settings, Marketing Studio's data folder, the home
folder, Git's identity and every repository are made in a temporary folder. Harness Brand is
the stand-in in tests/brand_stand_in (Node runs a small Python script), and no real assistant
job is started: the job's assistant is a function, or a stand-in `claude` on PATH that only
prints events.
"""
import base64
import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import zipfile
from pathlib import Path
from unittest import mock

from marketing_studio import brand_job, brand_skill, brand_store, shared, workspaces
from marketing_studio.errors import WorkspaceError
from marketing_studio.launcher import Launcher
from marketing_studio.page import Home

ROOT = Path(__file__).resolve().parents[1]
STAND_IN = ROOT / 'tests/brand_stand_in/harness-brand'
TOKENS = {'name': 'Example Co', 'colors': [
    {'name': 'white', 'light': '#ffffff', 'dark': '#1b1d36', 'usage': 'The ground.'},
    {'name': 'black', 'light': '#000000', 'dark': '#ffffff', 'usage': 'Body text.'},
    {'name': 'blue', 'light': '#005c8a', 'usage': 'Titles.'}],
    'type': {'styles': [{'name': 'title', 'group': 'Titles', 'fontSize': '36px'}]}}


def export_zip():
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as made:
        made.writestr('tokens.json', json.dumps(TOKENS))
        made.writestr('README.md', '# Example Co brand book\n\nTitles are sentence case.\n')
        made.writestr('assets/logo.svg', '<svg xmlns="http://www.w3.org/2000/svg"/>')
    return data.getvalue()


def proposal(brand_id='example', note=''):
    """What a stand-in assistant answers: every part, finished."""
    layouts = {'light': {'light-layout-001': {'relationship': 'statement', 'searchTerms': ['one idea']},
                         'light-layout-002': {'relationship': 'section'}}}
    brand = {'schema': 1, 'id': brand_id, 'name': 'Example Co', 'aliases': [brand_id], 'defaultVariant': 'light',
             'fonts': {'sans': 'Arial'}, 'logos': {'onLight': 'assets/logo.svg', 'onDark': 'assets/logo.svg'},
             'variants': {'light': {'theme': 'light', 'colors': {'canvasPrimary': 'white', 'inkPrimary': 'black',
                                                               'headingPrimary': 'blue'}}},
             'files': {'forged': '0' * 64}}
    return {'parts': {
        'roles': {'brand': brand, 'assets': [{'from': 'sources/export.zip!assets/logo.svg', 'to': 'assets/logo.svg'}],
                  'quotes': [{'rule': 'Titles are blue', 'source': 'export.zip README.md'}]},
        'layouts': {'layouts': layouts, 'quotes': []},
        'guide': {'text': f'## Brand rules\n\nTitles are sentence case (brand book).{note}\n', 'quotes': []},
        'directions': {'directions': {'schema': 1, 'house': ['Fill cards.'], 'variants': {}}, 'quotes': []},
        'audit': {'audit': {'schema': 1, 'minTextPt': 20}, 'quotes': []}},
        'disagreements': ['The template and the export disagree on the title colour; the export was taken.']}


@unittest.skipUnless(shutil.which('node') and shutil.which('git'), 'needs Node and Git')
class BrandsCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        (self.root / 'home').mkdir()
        gitconfig = self.root / 'gitconfig'
        gitconfig.write_text('[user]\n\tname = Test Person\n\temail = test@example.com\n'
                             '[init]\n\tdefaultBranch = main\n')
        self.calls = self.root / 'calls.jsonl'
        env = {'STUDIOS_CONFIG': str(self.root / 'shared.json'),
               'MARKETING_STUDIO_DATA': str(self.root / 'data'), 'HOME': str(self.root / 'home'),
               'XDG_CONFIG_HOME': str(self.root / 'home/.config'),
               'BRAND_SKILL_RUNTIME': str(STAND_IN), 'STAND_IN_PYTHON': sys.executable,
               'STAND_IN_CALLS': str(self.calls), 'GIT_CONFIG_GLOBAL': str(gitconfig),
               'GIT_CONFIG_NOSYSTEM': '1', 'HARNESS_BRAND_DATA': ''}
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop('HARNESS_BRAND_DATA')
        self.studios = self.root / 'Studios'
        shared.update({'local': {'root': str(self.studios)}, 'assistant': {'agent': 'claude'}})
        self.launcher = Launcher()
        self.addCleanup(self.launcher.close)
        self.page = Home(8000, self.launcher)
        self.brands = self.root / 'configured-brands'
        shared.update({'brand': {'brands': str(self.brands)}})

    def tearDown(self):
        for key, (thread, stop) in list(brand_store.TASKS.items()):
            stop.set()
            thread.join(10)
        brand_store.TASKS.clear()

    def call(self, route, **sent):
        status, kind, data = self.page.write(f"/api/brand-{route}", sent)
        self.assertEqual(status, 200)
        return json.loads(data) if kind.startswith('application/json') else (kind, data)

    def add(self, key, name, data):
        return self.call('source', key=key, name=name, content=base64.b64encode(data).decode())

    def settle(self, key):
        brand_store.wait(key, 60)
        work = self.call('work', key=key)
        self.assertNotEqual(work['task']['state'], 'running')
        return work

    def new_brand(self, ident='example'):
        work = self.call('start', kind='brand', id=ident, name='Example Co')
        key = work['key']
        self.add(key, 'export.zip', export_zip())
        self.add(key, 'example-light.pptx', b'PK stand-in template')
        self.add(key, 'brand-book.md', b'# Example Co\n\nTitles are sentence case.\n')
        return key

    def extract(self, key, **given):
        given = given or {'tokens': 'export.zip', 'templates': [{'source': 'example-light.pptx', 'variant': 'light'}]}
        self.call('extract', key=key, **given)
        return self.settle(key)

    def interpret(self, key, answer=None, part=None, note=None, seen=None):
        def assistant(agent, guidance, task, folder, model, effort, line, stop, seconds=0):
            if seen is not None:
                seen.append({'agent': agent, 'guidance': guidance, 'task': task})
            line('Thinking')
            return json.dumps(answer or proposal())
        with mock.patch.object(brand_job, 'run_assistant', assistant):
            self.call('interpret', key=key, **({'part': part} if part else {}), **({'note': note} if note else {}))
            return self.settle(key)

    def accept_all(self, key):
        for part in self.call('work', key=key)['parts']:
            if part['state'] == 'review':
                self.call('part', key=key, part=part['id'], action='accept')
        return self.call('work', key=key)

    def made(self, ident='example'):
        """A brand pack saved to local Git storage, the whole way through."""
        key = self.new_brand(ident)
        self.extract(key)
        self.interpret(key, proposal(ident))
        self.accept_all(key)
        return self.call('save', key=key)

    def log(self, repo, *args):
        return subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True,
                              check=True).stdout


class FindingHarnessBrand(BrandsCase):
    def test_the_stand_in_is_found_as_harness_brand(self):
        found = brand_skill.find(None, self.brands)
        self.assertEqual((found.name, found.version), ('Harness Brand', '1.0.0'))
        self.assertEqual(found.runtime, STAND_IN.resolve())

    def test_another_brand_skill_in_use_is_said_in_one_line_and_nothing_is_offered(self):
        with mock.patch.dict(os.environ, {'STAND_IN_NAME': 'Tanzu Brand'}):
            listed = self.call('list')
            self.assertEqual(set(listed), {'unavailable', 'where'})
            self.assertIn('The brand skill in use is Tanzu Brand, not Harness Brand.', listed['unavailable'])
            self.assertIn('https://github.com/dbbaskette/harness-brand-skill', listed['unavailable'])
            with self.assertRaisesRegex(WorkspaceError, 'Tanzu Brand'):
                self.call('start', kind='brand', id='example', name='Example Co')
        self.assertFalse((self.root / 'data/brand-work').exists())

    def test_no_brand_skill_says_how_to_get_harness_brand(self):
        with mock.patch.dict(os.environ, {'BRAND_SKILL_RUNTIME': str(self.root / 'nothing')}):
            listed = self.call('list')
        self.assertIn('No brand skill was found', listed['unavailable'])
        self.assertIn('install it from https://github.com/dbbaskette/harness-brand-skill', listed['unavailable'])

    def test_brands_are_refused_over_the_network(self):
        self.page.caller.remote = True
        try:
            with self.assertRaisesRegex(WorkspaceError, 'computer Marketing Studio runs on'):
                self.call('list')
        finally:
            self.page.caller.remote = False


class Listing(BrandsCase):
    def test_lists_packs_with_what_pack_check_says_and_libraries_with_their_users(self):
        pack = self.brands / 'example/pack'
        pack.mkdir(parents=True)
        (pack / 'brand.json').write_text(json.dumps({
            'schema': 1, 'id': 'example', 'name': 'Example Co', 'variants': {
                'light': {'slides': {'layout': 'Title Only'}}, 'dark': {}},
            'icons': [{'library': 'shapes'}], 'draft': ['Write the guide.']}))
        library = self.brands / 'icon-libraries/shapes'
        library.mkdir(parents=True)
        with zipfile.ZipFile(library / 'library.zip', 'w') as made:
            made.writestr('library.json', json.dumps({'name': 'Shapes', 'kind': 'glyph'}))
            made.writestr('icons.json', json.dumps({'icons': [{'slug': 'a'}, {'slug': 'b'}]}))
        listed = self.call('list')
        self.assertEqual(listed['where'], f'{self.brands}, kept with local Git')
        [found] = listed['packs']
        self.assertEqual((found['name'], found['variants'], found['slides']), ('Example Co', ['light', 'dark'], True))
        self.assertIsNone(found['check']['ok'])
        self.assertEqual(found['check']['problems'], [])
        calls = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertFalse(any(call[:2] == ['pack', 'check'] for call in calls))
        [shelf] = listed['libraries']
        self.assertEqual((shelf['name'], shelf['kind'], shelf['count'], shelf['usedBy']),
                         ('Shapes', 'glyph', 2, ['Example Co']))
        self.assertIsNone(shelf['check']['ok'])

    def test_an_empty_storage_lists_nothing_and_makes_nothing(self):
        listed = self.call('list')
        self.assertEqual((listed['packs'], listed['libraries'], listed['work']), ([], [], []))
        self.assertFalse(self.brands.exists())


class Sources(BrandsCase):
    def test_new_asks_for_an_id_and_a_name_and_a_librarys_kind(self):
        with self.assertRaisesRegex(WorkspaceError, 'lower-case'):
            self.call('start', kind='brand', id='Example Co', name='Example Co')
        with self.assertRaisesRegex(WorkspaceError, 'name of at most 80'):
            self.call('start', kind='brand', id='example', name='')
        with self.assertRaisesRegex(WorkspaceError, 'kind'):
            self.call('start', kind='library', id='shapes', name='Shapes')
        with self.assertRaisesRegex(WorkspaceError, 'lower-case'):
            self.call('start', kind='brand', id='icon-libraries', name='Icons')

    def test_sources_go_into_the_working_copy_and_storage_is_untouched(self):
        key = self.new_brand()
        work = self.call('work', key=key)
        self.assertEqual([s['name'] for s in work['sources']], ['brand-book.md', 'example-light.pptx', 'export.zip'])
        self.assertTrue((self.root / 'data/brand-work/brand-example/brands/example/sources/export.zip').is_file())
        self.assertFalse(self.brands.exists())
        self.assertEqual(work['choices']['exports'], ['export.zip'])
        self.assertEqual(work['choices']['templates'], [{'source': 'example-light.pptx', 'variant': 'light'}])

    def test_a_taken_name_waits_until_the_person_says_which_to_keep(self):
        key = self.new_brand()
        sources = self.root / 'data/brand-work/brand-example/brands/example/sources'
        answer = self.add(key, 'brand-book.md', b'a newer book')
        self.assertEqual(answer['clash'], 'brand-book.md')
        self.assertEqual((sources / 'brand-book.md').read_bytes(), b'# Example Co\n\nTitles are sentence case.\n')
        self.assertEqual(answer['work']['clashes'], ['brand-book.md'])
        self.assertIn('Choose which file to keep', answer['work']['ready'])
        kept = self.call('keep', key=key, name='brand-book.md', which='both')
        self.assertEqual(kept['kept'], 'brand-book (2).md')
        self.assertEqual((sources / 'brand-book (2).md').read_bytes(), b'a newer book')
        self.add(key, 'brand-book.md', b'newest')
        self.call('keep', key=key, name='brand-book.md', which='new')
        self.assertEqual((sources / 'brand-book.md').read_bytes(), b'newest')
        self.add(key, 'brand-book.md', b'not wanted')
        self.call('keep', key=key, name='brand-book.md', which='there')
        self.assertEqual((sources / 'brand-book.md').read_bytes(), b'newest')
        self.assertEqual(self.call('work', key=key)['clashes'], [])

    def test_a_source_name_cannot_leave_the_sources_folder(self):
        key = self.call('start', kind='brand', id='example', name='Example Co')['key']
        for name in ('../escape.md', '.hidden', 'a/b.md'):
            with self.subTest(name=name), self.assertRaises(WorkspaceError):
                self.add(key, name, b'x')


class Extract(BrandsCase):
    def test_extract_runs_the_pack_commands_into_the_working_copy_and_shows_what_came_out(self):
        key = self.new_brand()
        work = self.extract(key, tokens='export.zip', templates=[{'source': 'example-light.pptx', 'variant': 'light'}],
                            icons=[])
        self.assertEqual(work['task']['state'], 'done', work['task'])
        calls = [json.loads(line)[:2] for line in self.calls.read_text().splitlines()]
        self.assertEqual([c for c in calls if c[0] == 'pack'],
                         [['pack', 'tokens'], ['pack', 'measure'], ['pack', 'previews'], ['pack', 'scaffold']])
        self.assertEqual([c['name'] for c in work['tokens']['colors']], ['white', 'black', 'blue'])
        self.assertEqual(work['tokens']['colors'][0]['dark'], '#1b1d36')
        self.assertEqual(work['tokens']['styles'][0]['name'], 'title')
        self.assertEqual([l['name'] for l in work['layouts']['light']], ['Title Only', 'Section'])
        kind, data = self.call('file', key=key, path=work['layouts']['light'][0]['preview'])
        self.assertEqual(kind, 'image/png')
        self.assertTrue(data.startswith(b'\x89PNG'))
        self.assertEqual(work['extracted']['draft'][0], 'Check every colour role against the brand book.')
        self.assertEqual([p['id'] for p in work['parts']], ['roles', 'layouts', 'guide', 'directions', 'audit'])
        self.assertTrue(all(p['state'] == 'review' for p in work['parts']))
        self.assertFalse(self.brands.exists())

    def test_missing_libreoffice_is_reported_and_the_rest_is_extracted(self):
        key = self.new_brand()
        with mock.patch.dict(os.environ, {'STAND_IN_NO_PREVIEWS': '1'}):
            work = self.extract(key)
        self.assertEqual(work['task']['state'], 'done')
        self.assertIn('Previews need LibreOffice', work['extracted']['previews']['light'])
        self.assertIn('brew install --cask libreoffice', work['extracted']['previews']['light'])
        self.assertIsNone(work['layouts']['light'][0]['preview'])

    def test_a_failed_extract_leaves_the_working_pack_as_it_was(self):
        key = self.new_brand()
        self.add(key, 'broken.zip', export_zip().replace(b'tokens.json', b'tokenz.json'))
        work = self.extract(key, tokens='broken.zip', templates=[])
        self.assertEqual(work['task']['state'], 'failed')
        self.assertIn('it has no tokens.json', work['task']['detail'])
        self.assertEqual(list((self.root / 'data/brand-work/brand-example/brands/example/pack').iterdir()), [])
        self.assertIsNone(work['extracted'])

    def test_extract_refuses_choices_not_from_the_sources(self):
        key = self.new_brand()
        with self.assertRaisesRegex(WorkspaceError, 'design-system export'):
            self.call('extract', key=key, tokens='elsewhere.zip', templates=[])
        with self.assertRaisesRegex(WorkspaceError, 'variant of its own'):
            self.call('extract', key=key, tokens='export.zip', templates=[
                {'source': 'example-light.pptx', 'variant': 'light'}, {'source': 'example-light.pptx', 'variant': 'light'}])

    def test_an_icon_library_is_made_with_pack_icons_and_goes_straight_to_save(self):
        key = self.call('start', kind='library', id='shapes', name='Shapes', libraryKind='glyph')['key']
        self.add(key, 'circle.svg', b'<svg><circle r="1"/></svg>')
        self.add(key, 'label.svg', b'<svg><text>A</text></svg>')
        self.call('extract', key=key)
        work = self.settle(key)
        self.assertEqual(work['task']['state'], 'done', work['task'])
        self.assertEqual(work['extracted']['icons'], 1)
        self.assertEqual(work['extracted']['skipped'][0]['reason'], 'it holds text, which is not a glyph')
        self.assertEqual(work['library']['sheet'], 'contact-sheet.svg')
        self.assertEqual(self.call('file', key=key, path='contact-sheet.svg')[0], 'image/svg+xml')
        self.assertIsNone(work['ready'])
        with self.assertRaisesRegex(WorkspaceError, 'no assistant'):
            self.call('interpret', key=key)
        saved = self.call('save', key=key)
        self.assertEqual(saved['message'], 'Add the Shapes icon library')
        self.assertTrue((self.brands / 'icon-libraries/shapes/library.zip').is_file())
        self.assertTrue((self.brands / 'icon-libraries/shapes/sources/circle.svg').is_file())
        self.assertEqual(self.log(self.brands, 'log', '--format=%s').strip(), 'Add the Shapes icon library')

    def test_a_library_takes_only_icon_sources(self):
        key = self.call('start', kind='library', id='shapes', name='Shapes', libraryKind='picture')['key']
        with self.assertRaisesRegex(WorkspaceError, 'not an icon source'):
            self.add(key, 'template.pptx', b'x')


class Interpret(BrandsCase):
    def test_the_job_is_told_harness_brands_guide_and_writes_only_judgement_files(self):
        key = self.new_brand()
        self.extract(key)
        pack = self.root / 'data/brand-work/brand-example/brands/example/pack'
        measured = json.loads((pack / 'layouts.json').read_text())
        seen = []
        work = self.interpret(key, seen=seen)
        self.assertEqual(work['task']['state'], 'done', work['task'])
        [asked] = seen
        self.assertEqual(asked['agent'], 'claude')
        self.assertIn('# Building a brand pack (stand-in)', asked['guidance'])
        self.assertIn('# Brand pack format (stand-in)', asked['guidance'])
        self.assertIn('Titles are sentence case.', asked['task'])   # the brand book's text
        self.assertIn('export.zip!README.md', asked['task'])
        brand = json.loads((pack / 'brand.json').read_text())
        self.assertNotIn('files', brand)            # a forged seal is never kept
        self.assertNotIn('draft', brand)
        self.assertTrue((pack / 'assets/logo.svg').is_file())
        layouts = json.loads((pack / 'layouts.json').read_text())
        light = layouts['variants']['light']['layouts']
        self.assertEqual(light[0]['relationship'], 'statement')
        for before, after in zip(measured['variants']['light']['layouts'], light):
            self.assertEqual({k: v for k, v in after.items() if k not in brand_store.JUDGEMENT}, before)
        self.assertEqual(json.loads((pack / 'audit.json').read_text())['minTextPt'], 20)
        roles = {r['role']: r['value'] for r in work['roles']['light']}
        self.assertEqual(roles['headingPrimary'], '#005c8a')
        parts = {p['id']: p for p in work['parts']}
        self.assertEqual(parts['roles']['quotes'][0]['source'], 'export.zip README.md')
        self.assertTrue(all(p['state'] == 'review' and p['by'] == 'assistant' for p in parts.values()))
        self.assertEqual(work['notes'][0][:37], 'The template and the export disagree ')
        self.assertFalse(self.brands.exists())

    def test_an_answer_that_is_not_whole_writes_nothing(self):
        key = self.new_brand()
        self.extract(key)
        pack = self.root / 'data/brand-work/brand-example/brands/example/pack'
        before = {p.name: p.read_bytes() for p in pack.glob('*.*')}
        broken = proposal()
        broken['parts']['layouts']['layouts'] = {'light': {'no-such-layout': {'relationship': 'x'}}}
        work = self.interpret(key, broken)
        self.assertEqual(work['task']['state'], 'failed')
        self.assertIn('no layout no-such-layout', work['task']['detail'])
        self.assertEqual({p.name: p.read_bytes() for p in pack.glob('*.*')}, before)
        self.assertFalse((pack / 'assets').exists())

    def test_a_stopped_job_keeps_nothing(self):
        key = self.new_brand()
        self.extract(key)
        pack = self.root / 'data/brand-work/brand-example/brands/example/pack'
        before = (pack / 'guide.md').read_text()
        started = []

        def slow(agent, guidance, task, folder, model, effort, line, stop, seconds=0):
            started.append(True)
            stop.wait(10)
            raise brand_skill.Stopped()
        with mock.patch.object(brand_job, 'run_assistant', slow):
            self.call('interpret', key=key)
            while not started:
                time.sleep(0.01)
            self.call('stop', key=key)
            work = self.settle(key)
        self.assertEqual(work['task']['state'], 'stopped')
        self.assertEqual((pack / 'guide.md').read_text(), before)

    def test_sending_one_part_back_runs_the_job_for_that_part_only(self):
        key = self.new_brand()
        self.extract(key)
        self.interpret(key)
        self.call('part', key=key, part='audit', action='accept')
        seen = []
        work = self.interpret(key, proposal(note=' Headlines never end in a full stop (brand book).'),
                              part='guide', note='Add the rule about full stops.', seen=seen)
        self.assertEqual(work['task']['state'], 'done', work['task'])
        self.assertIn('Propose these parts of the pack: guide.', seen[0]['task'])
        self.assertIn('Add the rule about full stops.', seen[0]['task'])
        parts = {p['id']: p for p in work['parts']}
        self.assertIn('full stop', parts['guide']['content'])
        self.assertEqual(parts['guide']['note'], 'Add the rule about full stops.')
        self.assertEqual(parts['audit']['state'], 'accepted')   # not asked again, still accepted

    def test_job_cleanup_waits_for_a_record_reader(self):
        key = self.new_brand()
        self.extract(key)
        found = brand_skill.find()
        job = brand_job.interpret(found, key, shared.read()[0])
        real_lock, real_remove = brand_store.LOCK, shutil.rmtree
        boundary, cleaning = threading.Event(), threading.Event()
        failures = []

        class ObservedLock:
            def __enter__(self):
                boundary.set()
                real_lock.acquire()
                return self
            def __exit__(self, *args):
                real_lock.release()

        def remove(path, *args, **kwargs):
            if Path(path).name == 'job':
                cleaning.set(); boundary.set()
            return real_remove(path, *args, **kwargs)

        def run():
            try:
                job(lambda _: None, threading.Event())
            except brand_skill.Stopped:
                pass
            except BaseException as error:
                failures.append(error)

        with mock.patch.object(brand_store, 'LOCK', ObservedLock()), \
             mock.patch.object(brand_job.shutil, 'rmtree', remove), \
             mock.patch.object(brand_job, 'run_assistant', side_effect=brand_skill.Stopped()):
            with real_lock:  # A record reader owns the tree while a new job starts.
                thread = threading.Thread(target=run)
                thread.start()
                self.assertTrue(boundary.wait(5))
                overlapping = cleaning.is_set()
            thread.join(5)
            self.assertFalse(thread.is_alive())
            self.assertFalse(overlapping, 'Cleanup changed the tree while its reader held the lock.')
            self.assertTrue(cleaning.is_set())
            self.assertEqual(failures, [])

    def test_the_person_edits_a_part_and_it_counts_as_accepted(self):
        key = self.new_brand()
        self.extract(key)
        self.interpret(key)
        work = self.call('part', key=key, part='guide', action='edit', content='## Brand rules\n\nMine.\n')
        guide = next(p for p in work['parts'] if p['id'] == 'guide')
        self.assertEqual((guide['state'], guide['by']), ('accepted', 'you'))
        with self.assertRaisesRegex(WorkspaceError, 'not JSON'):
            self.call('part', key=key, part='audit', action='edit', content='{not json')

    def test_the_real_command_runs_a_stand_in_claude_that_has_no_tools(self):
        bin_folder = self.root / 'bin'
        bin_folder.mkdir()
        argv = self.root / 'argv.json'
        answer = json.dumps(proposal())
        script = bin_folder / 'claude'
        script.write_text(f'#!{sys.executable}\nimport json, sys\n'
                          f'json.dump(sys.argv[1:], open({str(argv)!r}, "w"))\nsys.stdin.read()\n'
                          'print(json.dumps({"type": "system", "subtype": "init", "model": "stand-in"}))\n'
                          f'print(json.dumps({{"type": "result", "subtype": "success", "result": {answer!r}}}))\n')
        script.chmod(0o755)
        key = self.new_brand()
        self.extract(key)
        with mock.patch.dict(os.environ, {'PATH': f'{bin_folder}:{os.environ["PATH"]}'}):
            self.call('interpret', key=key)
            work = self.settle(key)
        self.assertEqual(work['task']['state'], 'done', work['task'])
        self.assertIn('Started on stand-in', work['task']['lines'])
        given = json.loads(argv.read_text())
        self.assertEqual(given[given.index('--tools') + 1], '')
        self.assertEqual(given[given.index('--allowedTools') + 1], '')
        self.assertIn('--restricted', given)
        self.assertIn('# Building a brand pack (stand-in)', given[given.index('--append-system-prompt') + 1])

    def test_codex_features_switched_off_match_the_shared_runner(self):
        source = (ROOT / 'core/studio_core/shared_runner/agents.py').read_text()
        start = source.index('CODEX_OFF = (')
        found = eval(source[start + len('CODEX_OFF = '):source.index(')', start) + 1])
        self.assertEqual(found, brand_job.CODEX_OFF)


def made_pdf(words=b'BT /F1 12 Tf 72 720 Td (Example Co brand book: titles are blue.) Tj ET'):
    """A one-page PDF of made-up words; with no words, a page with no text layer at all."""
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>',
               b'<< /Length ' + str(len(words)).encode() + b' >>\nstream\n' + words + b'\nendstream',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    raw, offsets = b'%PDF-1.4\n', []
    for number, value in enumerate(objects, 1):
        offsets.append(len(raw))
        raw += str(number).encode() + b' 0 obj\n' + value + b'\nendobj\n'
    at = len(raw)
    raw += b'xref\n0 6\n0000000000 65535 f \n' + b''.join(f'{offset:010d} 00000 n \n'.encode() for offset in offsets)
    return raw + b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n' + str(at).encode() + b'\n%%EOF\n'


def zipped(members):
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as made:
        for name, content in members.items():
            made.writestr(name, content)
    return data.getvalue()


class PdfBrandBooks(BrandsCase):
    """An uploaded PDF brand book, alone or in a ZIP archive, reaches the assistant as text."""

    def sources(self, **files):
        folder = self.root / 'sources'
        folder.mkdir()
        for name, data in files.items():
            (folder / name.replace('__', '.')).write_bytes(data)
        return brand_job.source_texts(folder)

    @unittest.skipUnless(shutil.which('pdftotext'), 'needs the pdftotext reader')
    def test_a_pdf_and_a_pdf_in_a_zip_are_read_as_text_and_reach_the_assistant(self):
        given, named = self.sources(book__pdf=made_pdf(), kit__zip=zipped({'guide/rules.pdf': made_pdf()}))
        texts = {item['source']: item for item in given}
        self.assertEqual(sorted(texts), ['book.pdf', 'kit.zip!guide/rules.pdf'])
        for item in texts.values():
            self.assertIn('Example Co brand book: titles are blue.', item['text'])
            self.assertTrue(item['whole'])
        self.assertEqual(named, [])
        # And through the real job: the assistant is told the PDF's words.
        key = self.new_brand()
        self.add(key, 'brand-book.pdf', made_pdf())
        self.extract(key)
        seen = []
        work = self.interpret(key, seen=seen)
        self.assertEqual(work['task']['state'], 'done', work['task'])
        self.assertIn('Example Co brand book: titles are blue.', seen[0]['task'])
        self.assertIn('Reading the sources', work['task']['lines'])

    @unittest.skipUnless(shutil.which('pdftotext'), 'needs the pdftotext reader')
    def test_a_pdf_with_no_text_layer_is_named_as_unreadable_with_why(self):
        given, named = self.sources(scan__pdf=made_pdf(b''), kit__zip=zipped({'scan.pdf': made_pdf(b'')}))
        self.assertEqual(given, [])
        reason = 'not readable: It has no text layer, only pictures of pages; no OCR is attempted'
        self.assertEqual(sorted(named), [f'kit.zip!scan.pdf ({reason})', f'scan.pdf ({reason})'])

    def test_without_the_reader_a_pdf_is_named_as_unreadable_with_why(self):
        with mock.patch.object(brand_job.source_documents.shutil, 'which', return_value=None):
            given, named = self.sources(book__pdf=made_pdf())
        self.assertEqual(given, [])
        self.assertEqual(len(named), 1)
        self.assertTrue(named[0].startswith('book.pdf (not readable: PDF reading needs an explicitly installed '
                                            'pdftotext reader'), named)

    def test_a_pdf_is_held_to_the_same_per_source_and_total_budgets(self):
        long = 'Rule. ' * 40_000                                   # 240,000 characters
        with mock.patch.object(brand_job.source_documents, 'pdf_text', return_value=long) as read, \
                mock.patch.object(brand_job, 'SOURCE_BUDGET', 150_000):
            given, named = self.sources(a__pdf=made_pdf(), b__pdf=made_pdf(), c__pdf=made_pdf())
        self.assertEqual([(item['source'], len(item['text']), item['whole']) for item in given],
                         [('a.pdf', brand_job.ONE_SOURCE, False), ('b.pdf', 150_000 - brand_job.ONE_SOURCE, False)])
        self.assertEqual(named, ['c.pdf (left out: the prompt had no room)'])
        self.assertEqual(read.call_count, 2, 'a PDF with no room left is not read at all')

    def test_starting_the_job_reads_no_pdf_in_the_request(self):
        key = self.new_brand()
        self.extract(key)
        started = threading.Event()
        def assistant(*args, **kwargs):
            started.wait(10)
            return json.dumps(proposal())
        with mock.patch.object(brand_job, 'source_texts', wraps=brand_job.source_texts) as read, \
                mock.patch.object(brand_job, 'run_assistant', assistant):
            self.call('interpret', key=key)
            requested = read.call_count
            started.set()
            self.settle(key)
        self.assertLessEqual(requested, 1)
        self.assertEqual(read.call_count, 1)


BRIEF = {'id': 'solution-brief', 'name': 'Solution brief', 'useWhen': 'A two-page overview of one solution.',
         'page': 'US Letter', 'notes': 'Needs the brand fonts installed. The cover photo is a placeholder; not an official template.',
         'file': 'templates/documents/solution-brief.dotx'}


def brand_pack(brands: Path, ident, documents=()):
    """A finished, made-up brand pack written straight into a brands folder."""
    pack = brands / ident / 'pack'
    (pack / 'assets').mkdir(parents=True)
    (pack / 'assets/logo.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    (pack / 'guide.md').write_text('## Brand rules\n\nTitles are sentence case.\n')
    brand = {'schema': 1, 'id': ident, 'name': f'{ident.title()} Co', 'aliases': [ident], 'defaultVariant': 'light',
             'variants': {'light': {'theme': 'light', 'colors': {}}},
             'logos': {'onLight': 'assets/logo.svg', 'onDark': 'assets/logo.svg'}, 'documents': list(documents)}
    (pack / 'brand.json').write_text(json.dumps(brand))
    for entry in documents:
        (pack / entry['file']).parent.mkdir(parents=True, exist_ok=True)
        (pack / entry['file']).write_bytes(b'PK made-up Word template ' + entry['id'].encode())
    return pack


class DocumentTemplates(BrandsCase):
    def setUp(self):
        super().setUp()
        self.pack = brand_pack(self.brands, 'example', [BRIEF])
        brand_pack(self.brands, 'plain')
        brand_store._DOCUMENTS.clear()

    def asked(self):
        lines = self.calls.read_text().splitlines() if self.calls.exists() else []
        return [json.loads(line) for line in lines if json.loads(line)[:1] == ['documents']]

    def refused(self, **sent):
        with self.assertRaises(WorkspaceError) as caught:
            self.page.write('/api/brand-document', sent)
        return str(caught.exception)

    def test_a_brands_templates_are_listed_with_what_each_is_for_and_kept_briefly(self):
        listed = self.call('documents', id='example')
        self.assertEqual(listed, {'brand': 'example', 'documents': [{
            'id': 'solution-brief', 'name': 'Solution brief', 'useWhen': 'A two-page overview of one solution.',
            'page': 'US Letter', 'notes': BRIEF['notes'], 'file': 'solution-brief.dotx'}]})
        self.assertEqual(self.asked(), [['documents', '--brand', 'example', '--json']])
        self.call('documents', id='example')
        self.assertEqual(len(self.asked()), 1, 'asked again within the moment it is kept')
        brand = self.pack / 'brand.json'
        os.utime(brand, ns=(brand.stat().st_atime_ns, brand.stat().st_mtime_ns + 1_000_000))
        self.call('documents', id='example')
        self.assertEqual(len(self.asked()), 2, 'a changed brand.json is asked again')

    def test_a_brand_with_no_templates_says_so_and_the_list_is_asked_only_when_opened(self):
        self.call('list')
        self.assertEqual(self.asked(), [])
        self.assertEqual(self.call('documents', id='plain'), {'brand': 'plain', 'documents': []})
        script = (ROOT / 'marketing_studio/web/brands.js').read_text()
        self.assertIn('has no document templates.', script)
        self.assertIn("more.addEventListener('toggle'", script)

    def test_a_listed_template_downloads_from_the_page_server(self):
        kind, data = self.call('document', id='example', template='solution-brief')
        self.assertEqual(kind, 'application/vnd.openxmlformats-officedocument.wordprocessingml.template')
        self.assertEqual(data, b'PK made-up Word template solution-brief')

    def test_only_the_files_the_skill_listed_for_that_brand_are_served(self):
        # A template the listing does not name, another brand's, or a path the page sends.
        self.assertIn('not a document template', self.refused(id='example', template='white-paper'))
        self.assertIn('not a document template', self.refused(id='plain', template='solution-brief'))
        self.assertIn('not a document template', self.refused(id='example', template='../brand.json',
                                                              path=str(self.pack / 'brand.json')))
        self.assertIn('Choose a brand', self.refused(id='../example', template='solution-brief'))
        # A listing that names a file outside the brand's pack folder is not served.
        outside = self.root / 'outside.dotx'
        outside.write_bytes(b'PK private')
        for listed in (outside, self.brands / 'plain' / 'pack' / 'guide.md', self.pack / 'brand.json'):
            brand_store._DOCUMENTS.clear()
            with mock.patch.dict(os.environ, {'STAND_IN_DOCUMENT_PATH': str(listed)}):
                with self.subTest(listed=listed.name):
                    self.assertIn('not offered', self.refused(id='example', template='solution-brief'))
        # Nor one that reaches outside through a link.
        brand_store._DOCUMENTS.clear()
        template = self.pack / BRIEF['file']
        template.unlink()
        template.symlink_to(outside)
        self.assertIn('symbolic links', self.refused(id='example', template='solution-brief'))


class Save(BrandsCase):
    def test_save_waits_for_every_part_and_is_refused_until_pack_check_passes(self):
        key = self.new_brand()
        self.extract(key)
        self.interpret(key)
        with self.assertRaisesRegex(WorkspaceError, 'Accept or edit each part first'):
            self.call('save', key=key)
        self.accept_all(key)
        with mock.patch.dict(os.environ, {'STAND_IN_PROBLEM': 'Text on canvasPrimary is 2.1 to 1; it needs 4.5.'}):
            with self.assertRaises(WorkspaceError) as refused:
                self.call('save', key=key)
        self.assertIn('pack check does not pass yet', str(refused.exception))
        self.assertIn('Text on canvasPrimary is 2.1 to 1; it needs 4.5.', refused.exception.details['problems'])
        self.assertEqual(self.call('work', key=key)['checked']['ok'], False)
        self.assertFalse(self.brands.exists())

    def test_local_git_save_seals_copies_commits_and_removes_the_working_copy(self):
        saved = self.made()
        self.assertEqual(saved['message'], 'Add the Example Co brand pack')
        self.assertTrue(saved['committed'])
        self.assertNotIn('push', saved)
        brand = json.loads((self.brands / 'example/pack/brand.json').read_text())
        self.assertIn('files', brand)               # sealed by pack seal
        self.assertTrue((self.brands / 'example/sources/export.zip').is_file())
        self.assertEqual(self.log(self.brands, 'log', '--format=%s %an').strip(), 'Add the Example Co brand pack Test Person')
        tracked = self.log(self.brands, 'ls-files').split()
        self.assertIn('.gitattributes', tracked)
        self.assertIn('example/pack/brand.json', tracked)
        self.assertIn('example/sources/brand-book.md', tracked)
        self.assertFalse((self.root / 'data/brand-work/brand-example').exists())
        listed = self.call('list')
        self.assertIsNone(listed['packs'][0]['check']['ok'])

    def test_an_update_shows_only_what_changed_and_saves_as_an_update(self):
        self.made()
        work = self.call('start', kind='brand', id='example', update=True)
        key = work['key']
        self.assertEqual(work['name'], 'Example Co')
        self.assertTrue(all(p['state'] == 'unchanged' for p in work['parts']), work['parts'])
        changed = proposal()
        changed['parts']['audit']['audit']['minTextPt'] = 24
        work = self.interpret(key, changed, part='audit', note='The brand book now says 24 points.')
        states = {p['id']: p['state'] for p in work['parts']}
        self.assertEqual(states.pop('audit'), 'review')
        self.assertEqual(set(states.values()), {'unchanged'})
        self.call('part', key=key, part='audit', action='accept')
        saved = self.call('save', key=key)
        self.assertEqual(saved['message'], 'Update the Example Co brand pack')
        self.assertEqual(json.loads((self.brands / 'example/pack/audit.json').read_text())['minTextPt'], 24)
        self.assertIsNone(self.call('list')['packs'][0]['check']['ok'])

    def test_save_is_refused_when_the_pack_in_storage_changed_since(self):
        self.made()
        key = self.call('start', kind='brand', id='example', update=True)['key']
        changed = proposal()
        changed['parts']['audit']['audit']['minTextPt'] = 24
        self.interpret(key, changed, part='audit', note='24 points.')
        self.call('part', key=key, part='audit', action='accept')
        guide = self.brands / 'example/pack/guide.md'
        guide.write_text(guide.read_text() + '\nSomeone else added this.\n')
        with self.assertRaisesRegex(WorkspaceError, 'changed after this working copy was made'):
            self.call('save', key=key)
        self.assertIn('Someone else added this.', guide.read_text())
        self.assertEqual(json.loads((self.brands / 'example/pack/audit.json').read_text())['minTextPt'], 20)
        self.assertTrue((self.root / 'data/brand-work/brand-example').exists())   # kept to discard

    def test_new_is_refused_for_a_brand_already_in_storage_and_discard_leaves_storage(self):
        self.made()
        with self.assertRaisesRegex(WorkspaceError, 'Update it instead'):
            self.call('start', kind='brand', id='example', name='Example Co')
        key = self.call('start', kind='brand', id='example', update=True)['key']
        before = brand_store.fingerprint(self.brands / 'example')
        self.call('discard', key=key)
        self.assertFalse((self.root / 'data/brand-work/brand-example').exists())
        self.assertEqual(brand_store.fingerprint(self.brands / 'example'), before)

    def test_git_with_no_identity_records_nothing(self):
        key = self.new_brand()
        self.extract(key)
        self.interpret(key)
        self.accept_all(key)
        (self.root / 'gitconfig').write_text('[user]\n\tuseConfigOnly = true\n')
        with mock.patch.dict(os.environ, {'GIT_AUTHOR_NAME': '', 'GIT_COMMITTER_NAME': '', 'EMAIL': ''}):
            with self.assertRaisesRegex(WorkspaceError, 'Git does not know who you are'):
                self.call('save', key=key)
        self.assertFalse((self.brands / 'example').exists())


class ConfiguredRepository(BrandsCase):
    def test_no_team_checkout_or_environment_override_can_change_the_authority(self):
        elsewhere = self.root / 'old-team'
        shared.update({'team': {'repository': str(elsewhere), 'branch': 'main'}})
        with mock.patch.dict(os.environ, {'HARNESS_BRAND_DATA': str(elsewhere)}), mock.patch.object(workspaces, 'checkouts', side_effect=AssertionError('must not inspect studios'), create=True):
            self.made()
        self.assertTrue((self.brands / 'example/pack/brand.json').is_file())
        self.assertFalse(elsewhere.exists())
        self.assertFalse((self.studios / 'brands').exists())

    def test_missing_remote_copy_lists_an_explicit_get_brands_action_without_cloning(self):
        shared.update({'brand': {'brands': 'https://example.invalid/brands.git'}})
        with mock.patch.object(brand_store, 'git', side_effect=AssertionError('read must not use Git')):
            listed = self.call('list')
        self.assertIn('Get brands', listed['unavailable'])
        self.assertFalse((self.root / 'data/brands').exists())

    def test_missing_setting_never_falls_back_to_team_storage(self):
        shared.update({'brand': {'brands': None}})
        self.assertIn('Harness Brand has no brands folder yet', self.call('list')['unavailable'])
        self.assertFalse(self.brands.exists())

    def test_changed_repository_refuses_an_old_working_copy(self):
        key = self.new_brand()
        self.extract(key)
        self.interpret(key)
        self.accept_all(key)
        shared.update({'brand': {'brands': str(self.root / 'other-brands')}})
        with self.assertRaisesRegex(WorkspaceError, 'working copy was made for'):
            self.call('save', key=key)
        self.assertFalse((self.root / 'other-brands').exists())


class Boundaries(BrandsCase):
    def test_update_refuses_symlinked_brand_without_reading_its_content(self):
        outside = self.root / 'outside'
        (outside / 'pack').mkdir(parents=True)
        (outside / 'pack/brand.json').write_text('{}')
        self.brands.mkdir()
        (self.brands / 'example').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(WorkspaceError, 'symbolic links'):
            self.call('start', kind='brand', id='example', update=True)
        self.assertFalse((self.root / 'data/brand-work').exists())

    def test_source_symlink_and_forged_work_identity_cannot_write_outside(self):
        key = self.new_brand()
        work = brand_store.record(key)
        outside = self.root / 'outside.md'
        outside.write_text('safe')
        source = brand_store.inside(work) / 'sources/escape.md'
        source.symlink_to(outside)
        with self.assertRaisesRegex(WorkspaceError, 'symbolic links'):
            self.add(key, 'escape.md', b'unsafe')
        self.assertEqual(outside.read_text(), 'safe')
        source.unlink()
        work['id'] = '../outside'
        brand_store.write_json(brand_store.folder_of(key) / 'work.json', work)
        with self.assertRaisesRegex(WorkspaceError, 'invalid identity'):
            self.call('work', key=key)

    def test_one_brand_commit_preserves_unrelated_staged_and_unstaged_files(self):
        self.made()
        (self.brands / 'unrelated.md').write_text('staged elsewhere')
        self.log(self.brands, 'add', 'unrelated.md')
        (self.brands / 'loose.md').write_text('unstaged elsewhere')
        saved = self.made('second')
        self.assertTrue(saved['committed'])
        changed = self.log(self.brands, 'show', '--name-only', '--format=').splitlines()
        self.assertTrue(changed)
        self.assertTrue(all(path.startswith('second/') for path in changed))
        self.assertEqual(self.log(self.brands, 'diff', '--cached', '--name-only').strip(), 'unrelated.md')
        self.assertIn('?? loose.md', self.log(self.brands, 'status', '--porcelain'))
        self.assertTrue((self.brands / 'example/pack/brand.json').is_file())

    def test_failed_commit_restores_the_brand_and_original_index_for_retry(self):
        self.made()
        before = brand_store.fingerprint(self.brands / 'example')
        key = self.call('start', kind='brand', id='example', update=True)['key']
        self.call('part', key=key, part='guide', action='edit', content='## Brand rules\nUpdated guide.')
        (self.brands / 'unrelated.md').write_text('staged elsewhere')
        self.log(self.brands, 'add', 'unrelated.md')
        index = (self.brands / '.git/index').read_bytes()
        real = brand_store.git
        def fail(repo, *args, **kwargs):
            if 'commit' in args:
                return subprocess.CompletedProcess(args, 1, '', 'synthetic commit failure')
            return real(repo, *args, **kwargs)
        with mock.patch.object(brand_store, 'git', fail), self.assertRaisesRegex(WorkspaceError, 'Nothing was saved'):
            self.call('save', key=key)
        self.assertEqual(brand_store.fingerprint(self.brands / 'example'), before)
        self.assertEqual((self.brands / '.git/index').read_bytes(), index)
        self.assertTrue(brand_store.folder_of(key).is_dir())
        self.assertTrue(self.call('save', key=key)['committed'])

    def test_preexisting_selected_brand_edits_are_preserved(self):
        self.made()
        guide = self.brands / 'example/pack/guide.md'
        guide.write_text('Existing uncommitted edit')
        key = self.call('start', kind='brand', id='example', update=True)['key']
        with self.assertRaisesRegex(WorkspaceError, 'uncommitted files'):
            self.call('save', key=key)
        self.assertEqual(guide.read_text(), 'Existing uncommitted edit')


class RemoteRepository(BrandsCase):
    def setUp(self):
        super().setUp()
        self.remote = self.root / 'remote.git'
        subprocess.run(['git', 'init', '--quiet', '--bare', '-b', 'main', str(self.remote)], check=True)
        seed = self.root / 'seed'
        subprocess.run(['git', 'clone', '--quiet', str(self.remote), str(seed)], check=True, capture_output=True)
        (seed / 'README.md').write_text('Brands repository\n')
        self.log(seed, 'add', 'README.md')
        self.log(seed, 'commit', '--quiet', '-m', 'Start')
        self.log(seed, 'push', '--quiet', 'origin', 'main')
        self.address = 'https://example.invalid/brands.git'
        from studio_core import brand_data
        self.brands = brand_data.place(self.address)
        self.brands.parent.mkdir(parents=True)
        subprocess.run(['git', 'clone', '--quiet', str(self.remote), str(self.brands)], check=True, capture_output=True)
        self.log(self.brands, 'remote', 'set-url', 'origin', self.address)
        shared.update({'brand': {'brands': self.address}})
        self.pushes = []
        real = brand_store.git
        def local_only(repo, *args, **kwargs):
            if args[0] == 'push':
                self.pushes.append(args)
                args = tuple(str(self.remote) if arg == self.address else arg for arg in args)
            return real(repo, *args, **kwargs)
        patcher = mock.patch.object(brand_store, 'git', local_only)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_save_never_pushes_and_push_requires_yes_to_the_exact_preview(self):
        saved = self.made()
        self.assertEqual(self.pushes, [])
        preview = saved['push']
        self.assertEqual((preview['commits'], preview['items'], preview['blocked']), (1, ['example'], None))
        self.assertEqual(self.log(self.remote, 'log', '--format=%s', 'main').strip(), 'Start')
        for sent, why in (({}, 'Say yes'), ({'confirm': True}, 'preview changed'), ({'confirm': True, 'expected': 'stale'}, 'preview changed')):
            with self.subTest(sent=sent), self.assertRaisesRegex(WorkspaceError, why):
                self.call('push', **sent)
        self.assertEqual(self.pushes, [])
        pushed = self.call('push', confirm=True, expected=preview['expected'])
        self.assertTrue(pushed['pushed'])
        self.assertEqual(len(self.pushes), 1)
        self.assertEqual(self.pushes[0][-1], preview['head']+':refs/heads/main')
        self.assertEqual(self.call('list')['packs'][0]['unshared'], 0)

    def test_batched_preview_keeps_commit_boundaries_and_blocks_an_empty_commit(self):
        self.made()
        (self.brands / 'other').mkdir()
        (self.brands / 'other' / 'guide').write_text('Second brand')
        self.log(self.brands, 'add', 'other/guide')
        self.log(self.brands, 'commit', '--quiet', '-m', 'Second brand')
        preview = self.call('list')['push']
        self.assertEqual((preview['commits'], preview['items'], preview['blocked']),
                         (2, ['example', 'other'], None))
        self.log(self.brands, 'commit', '--allow-empty', '-m', 'Empty')
        self.assertTrue(self.call('list')['push']['blocked'])

    def test_an_unrelated_outgoing_commit_or_changed_head_refuses_push(self):
        preview = self.made()['push']
        (self.brands / 'unrelated.md').write_text('not a brand')
        self.log(self.brands, 'add', 'unrelated.md')
        self.log(self.brands, 'commit', '--quiet', '-m', 'Unrelated')
        with self.assertRaisesRegex(WorkspaceError, 'preview changed'):
            self.call('push', confirm=True, expected=preview['expected'])
        fresh = self.call('list')['push']
        self.assertTrue(fresh['blocked'])
        with self.assertRaisesRegex(WorkspaceError, 'exactly one brand|outside a brand'):
            self.call('push', confirm=True, expected=fresh['expected'])
        self.assertEqual(self.pushes, [])

    def test_listing_counts_unshared_commits_with_no_git_run_per_pack(self):
        self.made('one')
        shelf = self.brands / 'icon-libraries/shapes'
        shelf.mkdir(parents=True)
        with zipfile.ZipFile(shelf / 'library.zip', 'w') as made:
            made.writestr('library.json', json.dumps({'name': 'Shapes', 'kind': 'glyph'}))
            made.writestr('icons.json', json.dumps({'icons': []}))
        self.log(self.brands, 'add', 'icon-libraries')
        self.log(self.brands, 'commit', '--quiet', '-m', 'Shapes')

        def runs():
            with mock.patch.object(brand_store, 'git', wraps=brand_store.git) as run:
                listed = self.call('list')
            return listed, [call.args[1:] for call in run.call_args_list]

        listed, before = runs()
        self.assertEqual({p['id']: p['unshared'] for p in listed['packs']}, {'one': 1})
        self.assertEqual({l['id']: l['unshared'] for l in listed['libraries']}, {'shapes': 1})
        self.made('two')
        listed, after = runs()
        self.assertEqual({p['id']: p['unshared'] for p in listed['packs']}, {'one': 1, 'two': 1})
        self.assertEqual(len(after), len(before), 'a pack added a Git run to the listing')

    def test_non_fast_forward_push_keeps_the_local_commit(self):
        preview = self.made()['push']
        other = self.root / 'other'
        subprocess.run(['git', 'clone', '--quiet', str(self.remote), str(other)], check=True, capture_output=True)
        (other / 'theirs.md').write_text('x\n')
        self.log(other, 'add', 'theirs.md')
        self.log(other, 'commit', '--quiet', '-m', 'Theirs')
        self.log(other, 'push', '--quiet', 'origin', 'main')
        with self.assertRaisesRegex(WorkspaceError, 'stays committed on this computer'):
            self.call('push', confirm=True, expected=preview['expected'])
        self.assertIn('Add the Example Co brand pack', self.log(self.brands, 'log', '--format=%s'))


class DoingEachJobOnce(BrandsCase):
    """Counted, never timed: walks of a working copy, work.json writes, hashes and Git runs."""

    def test_a_burst_of_lines_walks_nothing_and_work_json_is_written_a_bounded_number_of_times(self):
        key = self.new_brand()
        now = [1000.0]
        go, paused, resume = threading.Event(), threading.Event(), threading.Event()
        writes, during = [], {}
        real_write = brand_store.write_json

        def counted(path, value):
            if Path(path).name == 'work.json':
                writes.append(json.loads(json.dumps(value)))
            return real_write(path, value)

        def job(line, stop):
            go.wait(10)
            for number in range(500):
                line(f'Line {number}')
            during.update(walks=walked.call_count, writes=len(writes))
            paused.set()
            resume.wait(10)
            now[0] += brand_store.LINE_WRITES
            line('After a pause')
            line('The last line')

        with mock.patch.object(brand_store, '_clock', lambda: now[0]):
            brand_store.begin(key, 'extract', job)
            with mock.patch.object(brand_store, 'walk', wraps=brand_store.walk) as walked, \
                    mock.patch.object(brand_store, 'write_json', counted):
                go.set()
                self.assertTrue(paused.wait(10))
                self.assertEqual(during, {'walks': 0, 'writes': 0})
                on_disk = json.loads((brand_store.folder_of(key) / 'work.json').read_text())
                self.assertEqual(on_disk['task']['lines'], [])
                # A reader is shown every line at once, from memory.
                shown = brand_store.view(key)['task']['lines']
                self.assertEqual((len(shown), shown[-1]), (brand_store.LINES, 'Line 499'))
                resume.set()
                brand_store.wait(key, 30)
        # One write once LINE_WRITES had passed, and one as the task ended; nothing per line.
        self.assertEqual(len(writes), 2)
        self.assertEqual(writes[0]['task']['lines'][-1], 'After a pause')
        on_disk = json.loads((brand_store.folder_of(key) / 'work.json').read_text())
        self.assertEqual(on_disk['task']['state'], 'done')
        self.assertEqual(on_disk['task']['lines'][-2:], ['After a pause', 'The last line'])
        self.assertEqual(len(on_disk['task']['lines']), brand_store.LINES)
        self.assertEqual((brand_store.TASKS, brand_store.LIVE), ({}, {}))

    def test_tasks_do_not_grow_after_jobs_finish_and_the_last_outcome_is_still_shown(self):
        key = self.new_brand()
        other = self.new_brand('other')

        def failing(line, stop):
            line('Trying')
            raise WorkspaceError('It did not work.')

        for number in range(4):
            brand_store.begin(key, 'extract', lambda line, stop: line(f'Ran {number}'))
            brand_store.wait(key, 30)
            self.assertEqual(brand_store.TASKS, {})
        brand_store.begin(other, 'extract', failing)
        brand_store.wait(other, 30)
        self.assertEqual((brand_store.TASKS, brand_store.LIVE), ({}, {}))
        shown = self.call('work', key=key)['task']
        self.assertEqual((shown['state'], shown['lines']), ('done', ['Ran 3']))
        shown = self.call('work', key=other)['task']
        self.assertEqual((shown['state'], shown['detail']), ('failed', 'It did not work.'))
        self.call('discard', key=other)
        self.assertEqual(brand_store.TASKS, {})

    def test_view_walks_the_working_copy_once_and_hashes_each_part_once(self):
        key = self.new_brand()
        self.extract(key)
        self.interpret(key)
        with mock.patch.object(brand_store, 'walk', wraps=brand_store.walk) as walked, \
                mock.patch.object(brand_store, 'digest', wraps=brand_store.digest) as hashed:
            shown = brand_store.view(key)
        self.assertEqual(len(shown['parts']), len(brand_store.PARTS))
        self.assertEqual(hashed.call_count, len(shown['parts']))
        self.assertEqual(walked.call_count, 1)
        self.assertEqual({s['name'] for s in shown['sources']},
                         {'export.zip', 'example-light.pptx', 'brand-book.md'})
        self.assertTrue(shown['ready'].startswith('Accept or edit each part first'))

    def test_two_saves_of_one_brand_cannot_both_run_while_another_brand_saves(self):
        first, second = self.new_brand('first'), self.new_brand('second')
        for key, ident in ((first, 'first'), (second, 'second')):
            self.extract(key)
            self.interpret(key, proposal(ident))
            self.accept_all(key)
        entered, release = threading.Event(), threading.Event()
        real = brand_store.checked
        outcome = {}

        def held(found, folder, env=None):
            if 'brand-first' in str(folder):
                entered.set()
                release.wait(30)
            return real(found, folder, env=env)

        def save_first():
            try:
                outcome['first'] = self.call('save', key=first)
            except BaseException as failure:
                outcome['first'] = failure

        with mock.patch.object(brand_store, 'checked', held):
            saving = threading.Thread(target=save_first)
            saving.start()
            try:
                self.assertTrue(entered.wait(30))
                # Harness Brand is checking the first brand: nothing else of it may start.
                with self.assertRaisesRegex(WorkspaceError, 'already being saved'):
                    self.call('save', key=first)
                with self.assertRaisesRegex(WorkspaceError, 'being saved'):
                    self.call('part', key=first, part='guide', action='edit', content='## Brand rules\n\nMine.\n')
                with self.assertRaisesRegex(WorkspaceError, 'being saved'):
                    self.call('discard', key=first)
                # Another brand is saved meanwhile: LOCK is not held across the checks.
                self.assertTrue(self.call('save', key=second)['committed'])
                self.assertTrue(saving.is_alive())
                self.assertEqual(self.call('work', key=first)['key'], first)
            finally:
                release.set()
                saving.join(60)
        self.assertNotIsInstance(outcome['first'], BaseException, outcome['first'])
        self.assertTrue(outcome['first']['committed'])
        self.assertEqual(brand_store.SAVING, set())
        self.assertEqual(self.log(self.brands, 'log', '--format=%s').split('\n')[:2],
                         ['Add the Example Co brand pack', 'Add the Example Co brand pack'])
        self.assertTrue((self.brands / 'first/pack/brand.json').is_file())
        self.assertTrue((self.brands / 'second/pack/brand.json').is_file())

    def test_save_reads_and_hashes_each_working_copy_file_once(self):
        key = self.new_brand()
        self.extract(key)
        self.interpret(key)
        self.accept_all(key)
        here = brand_store.folder_of(key)
        real = brand_store.hashlib.file_digest
        read = []

        def counted(stream, name):
            read.append(Path(stream.name))
            return real(stream, name)

        with mock.patch.object(brand_store.hashlib, 'file_digest', counted):
            self.assertTrue(self.call('save', key=key)['committed'])
        mine = [path for path in read if here in path.parents]
        self.assertTrue(mine)
        self.assertEqual(len(mine), len(set(mine)), 'a working-copy file was hashed twice')

    def test_a_refused_save_lets_go_of_its_mark(self):
        key = self.new_brand()
        self.extract(key)
        self.interpret(key)
        self.accept_all(key)
        with mock.patch.dict(os.environ, {'STAND_IN_PROBLEM': 'Too little contrast.'}), \
                self.assertRaisesRegex(WorkspaceError, 'pack check does not pass yet'):
            self.call('save', key=key)
        self.assertEqual(brand_store.SAVING, set())
        self.assertTrue(self.call('save', key=key)['committed'])


class UnderConcurrentUse(BrandsCase):
    """Saves, jobs and page reads that overlap, ordered by events rather than by time."""

    def ready(self, ident):
        key = self.new_brand(ident)
        self.extract(key)
        self.interpret(key, proposal(ident))
        self.accept_all(key)
        return key

    def test_a_file_that_vanishes_while_walked_is_passed_over(self):
        key = self.new_brand()
        sources = brand_store.inside(brand_store.record(key)) / 'sources'
        (sources / 'gone.md').write_text('a file a running command renames away')
        real = os.scandir

        def vanishing(target):
            with real(target) as listing:
                entries = list(listing)
            if any(entry.name == 'gone.md' for entry in entries):
                (sources / 'gone.md').unlink(missing_ok=True)   # listed, then gone before its stat
            return contextlib.nullcontext(entries)

        with mock.patch.object(brand_store.os, 'scandir', vanishing):
            shown = brand_store.view(key)
        self.assertNotIn('gone.md', {s['name'] for s in shown['sources']})
        self.assertIn('export.zip', {s['name'] for s in shown['sources']})

    def test_the_listing_shows_a_brand_being_saved_or_changing_as_last_recorded(self):
        saving, changing = self.new_brand('saving'), self.new_brand('changing')
        with brand_store.LOCK:
            brand_store.SAVING.add(saving)
        self.addCleanup(brand_store.SAVING.discard, saving)

        def changing_walk(folder):
            raise FileNotFoundError(2, 'renamed while it was walked', str(folder))

        with mock.patch.object(brand_store, 'walk', changing_walk):
            listed = {work['key']: work for work in self.call('list')['work']}
        self.assertEqual(set(listed), {saving, changing})
        self.assertTrue(listed[saving]['saving'])
        self.assertFalse(listed[changing]['saving'])
        self.assertEqual(listed[changing]['name'], 'Example Co')

    def test_a_second_save_to_one_repository_waits_for_the_first_however_long_it_takes(self):
        first, second = self.ready('first'), self.ready('second')
        sealing, release_seal = threading.Event(), threading.Event()
        committing, release_commit, waiting = threading.Event(), threading.Event(), threading.Event()
        real_answer, real_git, held = brand_skill.answer, brand_store.git, threading.Lock()
        commits, outcome = [], {}

        def answer(found, args, *rest, **given):
            if args[:2] == ['pack', 'seal'] and 'brand-second' in args[2]:
                sealing.set()
                release_seal.wait(30)
            return real_answer(found, args, *rest, **given)

        def git(repo, *args, **given):
            if 'commit' in args and not commits:
                commits.append(args)
                committing.set()
                release_commit.wait(30)
            return real_git(repo, *args, **given)

        class Watched:
            def __enter__(self):
                if not held.acquire(blocking=False):
                    waiting.set()
                    held.acquire()
                return self

            def __exit__(self, *args):
                held.release()

        def save(key):
            try:
                outcome[key] = self.call('save', key=key)
            except BaseException as failure:
                outcome[key] = failure

        # write_lock gives up after 0.2 s here: a Save that reached it while the other
        # committed would fail, so passing shows the second one waited before it.
        quick = lambda place: brand_store.ProcessRLock(
            lambda: brand_store.brand_data.lock_path(place.folder), timeout=0.2, refusal=WorkspaceError)
        with mock.patch.object(brand_skill, 'answer', answer), \
                mock.patch.object(brand_store, 'git', git), \
                mock.patch.object(brand_store, 'repo_lock', lambda folder: Watched()), \
                mock.patch.object(brand_store, 'write_lock', quick):
            later = threading.Thread(target=save, args=(second,))
            later.start()
            sooner = None
            try:
                self.assertTrue(sealing.wait(60))
                sooner = threading.Thread(target=save, args=(first,))
                sooner.start()
                self.assertTrue(committing.wait(60))
                release_seal.set()
                self.assertTrue(waiting.wait(60), 'the second Save never reached the repository')
            finally:
                release_seal.set()
                release_commit.set()
                later.join(60)
                if sooner is not None:
                    sooner.join(60)
        for key in (first, second):
            self.assertNotIsInstance(outcome[key], BaseException, outcome[key])
            self.assertTrue(outcome[key]['committed'])
        # Both were first saves: the second committed into the repository the first made.
        self.assertEqual(self.log(self.brands, 'rev-list', '--count', 'HEAD').strip(), '2')
        self.assertEqual(self.log(self.brands, 'ls-tree', '--name-only', 'HEAD').split(),
                         ['.gitattributes', 'first', 'second'])

    def test_a_repository_made_by_hand_during_a_first_save_is_refused_as_before(self):
        key = self.ready('example')
        real = brand_store.checked

        def made_by_hand(found, folder, env=None):
            if not (self.brands / '.git').exists():
                self.brands.mkdir(exist_ok=True)
                subprocess.run(['git', 'init', '--quiet', '-b', 'main', str(self.brands)], check=True)
            return real(found, folder, env=env)

        with mock.patch.object(brand_store, 'checked', made_by_hand), \
                self.assertRaisesRegex(WorkspaceError, 'inside another repository'):
            self.call('save', key=key)
        self.assertTrue(brand_store.folder_of(key).is_dir())
        self.assertEqual(subprocess.run(['git', '-C', str(self.brands), 'rev-parse', '--verify', 'HEAD'],
                                        capture_output=True).returncode, 128)
        self.assertEqual(brand_store.SAVING, set())

    def test_a_job_ended_by_system_exit_still_writes_its_lines_and_how_it_ended(self):
        key = self.new_brand()

        def job(line, stop):
            line('One')
            line('Two')
            raise SystemExit(3)

        brand_store.begin(key, 'extract', job)
        brand_store.wait(key, 30)
        on_disk = json.loads((brand_store.folder_of(key) / 'work.json').read_text())
        self.assertEqual((on_disk['task']['state'], on_disk['task']['lines']), ('failed', ['One', 'Two']))
        self.assertIn('ended unexpectedly', on_disk['task']['detail'])
        self.assertEqual((brand_store.TASKS, brand_store.LIVE), ({}, {}))


class WalkBoundaries(unittest.TestCase):
    """A folder swapped for a link while it waits to be walked is refused, never followed."""

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.brand = self.root / 'brand'
        (self.brand / 'inner').mkdir(parents=True)
        (self.brand / 'inner/kept.md').write_text('inside')
        (self.brand / 'top.md').write_text('inside')
        self.outside = self.root / 'outside'
        self.outside.mkdir()
        (self.outside / 'secret.md').write_text('outside the brand')

    def swapped(self, into):
        real, done = os.open, []

        def opening(name, flags, *args, dir_fd=None, **given):
            if name == 'inner' and dir_fd is not None and not done:
                done.append(name)
                os.rename(self.brand / 'inner', self.root / 'moved-inner')
                into()
            return real(name, flags, *args, dir_fd=dir_fd, **given)
        return mock.patch.object(brand_store.os, 'open', opening)

    def test_the_tree_is_walked_whole_when_nothing_changes(self):
        self.assertEqual([path.relative_to(self.brand).as_posix() for path, _ in brand_store.walk(self.brand)],
                         ['inner/kept.md', 'top.md'])

    def test_a_folder_swapped_for_a_link_mid_walk_is_refused(self):
        for nofollow in (brand_store.NOFOLLOW, 0):       # 0: as on a platform without O_NOFOLLOW
            with self.subTest(nofollow=nofollow):
                if (self.brand / 'inner').is_symlink():
                    (self.brand / 'inner').unlink()
                    os.rename(self.root / 'moved-inner', self.brand / 'inner')
                link = lambda: (self.brand / 'inner').symlink_to(self.outside, target_is_directory=True)
                with self.swapped(link), mock.patch.object(brand_store, 'NOFOLLOW', nofollow), \
                        self.assertRaisesRegex(WorkspaceError, 'symbolic links'):
                    brand_store.walk(self.brand)

    def test_a_folder_swapped_for_another_folder_mid_walk_is_refused(self):
        other = lambda: os.rename(self.outside, self.brand / 'inner')
        with self.swapped(other), self.assertRaisesRegex(WorkspaceError, 'symbolic links'):
            brand_store.walk(self.brand)


@unittest.skipUnless(shutil.which('git'), 'needs Git')
class UnsharedCounts(unittest.TestCase):
    """One Git run gives what `git rev-list --count @{u}..HEAD -- <path>` gave for each path."""

    PATHS = ('a', 'b', 'c', 'icon-libraries/lib')

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        config = self.root / 'gitconfig'
        config.write_text('[user]\n\tname = Test Person\n\temail = test@example.com\n')
        patcher = mock.patch.dict(os.environ, {'GIT_CONFIG_GLOBAL': str(config), 'GIT_CONFIG_NOSYSTEM': '1',
                                               'HOME': str(self.root)})
        patcher.start()
        self.addCleanup(patcher.stop)

    def git(self, repo, *args):
        return subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True, check=True).stdout

    def put(self, repo, path, text, message=None):
        (repo / path).parent.mkdir(parents=True, exist_ok=True)
        (repo / path).write_text(text)
        self.git(repo, 'add', path)
        if message:
            self.git(repo, 'commit', '--quiet', '-m', message)

    def old(self, repo):
        counts = {}
        for path in self.PATHS:
            done = subprocess.run(['git', '-C', str(repo), 'rev-list', '--count', '@{u}..HEAD', '--', path],
                                  capture_output=True, text=True)
            number = int(done.stdout.strip() or 0) if done.returncode == 0 else 0
            if number:
                counts[path] = number
        return counts

    def new(self, repo):
        place = brand_store.Storage(repo, True, repo, 'https://example.invalid/brands.git')
        with mock.patch.object(brand_store, 'git', wraps=brand_store.git) as run:
            counts = brand_store.unshared_counts(place)
        self.assertLessEqual(run.call_count, 2)     # the upstream's commit, then one log
        return {path: number for path, number in counts.items() if path in self.PATHS}

    def test_the_counts_are_what_path_limited_rev_list_gave(self):
        upstream = self.root / 'upstream.git'
        subprocess.run(['git', 'init', '--quiet', '--bare', '-b', 'main', str(upstream)], check=True)
        repo = self.root / 'brands'
        subprocess.run(['git', 'init', '--quiet', '-b', 'main', str(repo)], check=True)
        for path in ('a/x', 'b/x', 'c/x', 'icon-libraries/lib/library.zip'):
            self.put(repo, path, 'base\n')
        self.git(repo, 'commit', '--quiet', '-m', 'Base')
        # The upstream is not origin/<branch>: a remote named upstream.
        self.git(repo, 'remote', 'add', 'upstream', str(upstream))
        self.git(repo, 'push', '--quiet', '-u', 'upstream', 'main')
        self.put(repo, 'a/x', 'main\n', 'Main changes a')
        self.git(repo, 'checkout', '--quiet', '-b', 'side', 'upstream/main')
        self.put(repo, 'a/y', 'side\n')
        self.put(repo, 'b/y', 'side\n', 'Side changes a and b')
        self.put(repo, 'icon-libraries/lib/library.zip', 'side\n', 'Side changes the library')
        self.git(repo, 'checkout', '--quiet', 'main')
        self.git(repo, 'merge', '--quiet', '--no-ff', '--no-edit', 'side')
        # A merge that keeps its first parent's tree: the side's change to b is hidden.
        self.git(repo, 'checkout', '--quiet', '-b', 'kept-out', 'upstream/main')
        self.put(repo, 'b/z', 'dropped\n', 'Kept out of b')
        self.git(repo, 'checkout', '--quiet', 'main')
        self.git(repo, 'merge', '--quiet', '-s', 'ours', '--no-edit', 'kept-out')
        self.put(repo, 'b/x', 'later\n', 'Main changes b')
        # A conflicting merge resolved by hand.
        self.git(repo, 'checkout', '--quiet', '-b', 'conflict', 'HEAD~1')
        self.put(repo, 'a/x', 'theirs\n', 'Conflict side changes a')
        self.git(repo, 'checkout', '--quiet', 'main')
        self.put(repo, 'a/x', 'ours\n', 'Main changes a again')
        subprocess.run(['git', '-C', str(repo), 'merge', '--quiet', '--no-edit', 'conflict'],
                       capture_output=True, text=True)
        self.put(repo, 'a/x', 'resolved\n', 'Resolve the conflict')
        # An empty commit, and a merge whose parents have the same tree.
        self.git(repo, 'commit', '--quiet', '--allow-empty', '-m', 'Empty')
        self.git(repo, 'checkout', '--quiet', '-b', 'same', 'HEAD')
        self.git(repo, 'commit', '--quiet', '--allow-empty', '-m', 'Empty side')
        self.git(repo, 'checkout', '--quiet', 'main')
        self.git(repo, 'merge', '--quiet', '--no-ff', '--no-edit', 'same')
        # A merge of the upstream itself after it moved on.
        other = self.root / 'other'
        subprocess.run(['git', 'clone', '--quiet', str(upstream), str(other)], check=True, capture_output=True)
        self.put(other, 'c/x', 'theirs\n', 'Upstream changes c')
        self.git(other, 'push', '--quiet', 'origin', 'main')
        self.git(repo, 'fetch', '--quiet', 'upstream')
        self.git(repo, 'merge', '--quiet', '--no-edit', 'upstream/main')
        # The merged upstream commit is the upstream itself: its change to c is not ours.
        expected = self.old(repo)
        self.assertEqual(set(expected), {'a', 'b', 'icon-libraries/lib'})
        self.assertEqual(self.new(repo), expected)
        # The upstream moves on: the commit merged before is now only one of its ancestors.
        self.put(other, 'c/y', 'more\n', 'Upstream changes c again')
        self.git(other, 'push', '--quiet', 'origin', 'main')
        self.git(repo, 'fetch', '--quiet', 'upstream')
        expected = self.old(repo)
        self.assertEqual(self.new(repo), expected)

    def test_no_upstream_counts_nothing_as_before(self):
        repo = self.root / 'brands'
        subprocess.run(['git', 'init', '--quiet', '-b', 'main', str(repo)], check=True)
        self.put(repo, 'a/x', 'one\n', 'One')
        self.assertEqual(self.old(repo), {})
        self.assertEqual(self.new(repo), {})


class CommandBounds(unittest.TestCase):
    def test_oversized_output_is_stopped_and_reported(self):
        with self.assertRaisesRegex(WorkspaceError, 'too much output'):
            brand_skill.run([sys.executable, '-c', 'print("x" * 5000000)'], seconds=10)

    def test_command_timeout_is_bounded(self):
        began = time.monotonic()
        with self.assertRaisesRegex(WorkspaceError, 'did not finish'):
            brand_skill.run([sys.executable, '-c', 'import time; time.sleep(30)'], seconds=.1)
        self.assertLess(time.monotonic() - began, 3)


class Routes(unittest.TestCase):
    def test_every_brand_route_is_a_write_with_its_bridge_limit(self):
        from marketing_studio import network
        for name in ('list', 'start', 'work', 'source', 'keep', 'extract', 'interpret', 'stop', 'part',
                     'save', 'push', 'discard', 'file'):
            self.assertIn(f'/api/brand-{name}', Home.writes)
        home = object.__new__(Home)
        self.assertEqual(network.body_limit('marketing', '/api/brand-source'),
                         home.body_limit('/api/brand-source', None))
        self.assertIn('/brands.js', network.STATIC)


if __name__ == '__main__':
    unittest.main()
