"""The Brands section: making and updating brand packs and icon libraries.

Everything here is disposable: shared settings, Marketing Studio's data folder, the home
folder, Git's identity and every repository are made in a temporary folder. Harness Brand is
the stand-in in tests/brand_stand_in (Node runs a small Python script), and no real assistant
job is started: the job's assistant is a function, or a stand-in `claude` on PATH that only
prints events.
"""
import base64
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
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
        self.brands = self.studios / 'brands'

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
        self.assertFalse(found['check']['ok'])
        self.assertIn('brand.json is still a draft: Write the guide.', found['check']['problems'])
        [shelf] = listed['libraries']
        self.assertEqual((shelf['name'], shelf['kind'], shelf['count'], shelf['usedBy']),
                         ('Shapes', 'glyph', 2, ['Example Co']))
        self.assertTrue(shelf['check']['ok'])

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
        self.assertTrue(listed['packs'][0]['check']['ok'], listed['packs'][0]['check'])

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
        self.assertTrue(self.call('list')['packs'][0]['check']['ok'])

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


class TeamRepository(BrandsCase):
    def setUp(self):
        super().setUp()
        self.remote = self.root / 'team.git'
        subprocess.run(['git', 'init', '--quiet', '--bare', '-b', 'main', str(self.remote)], check=True)
        seed = self.root / 'seed'
        subprocess.run(['git', 'clone', '--quiet', str(self.remote), str(seed)], check=True, capture_output=True)
        (seed / 'README.md').write_text('Team work\n')
        self.log(seed, 'add', 'README.md')
        self.log(seed, 'commit', '--quiet', '-m', 'Start')
        self.log(seed, 'push', '--quiet', 'origin', 'main')
        self.checkout = self.root / 'presentation-clone'
        subprocess.run(['git', 'clone', '--quiet', str(self.remote), str(self.checkout)], check=True, capture_output=True)
        shared.update({'team': {'repository': str(self.remote), 'branch': 'main'}})
        patcher = mock.patch.object(workspaces, 'checkouts', return_value=[(self.checkout, str(self.remote))])
        patcher.start()
        self.addCleanup(patcher.stop)
        self.brands = self.checkout / 'brands'

    def test_the_commit_is_made_in_the_checkout_and_pushed_only_after_yes(self):
        (self.checkout / 'studio-note.md').write_text('a studio file left uncommitted\n')
        saved = self.made()
        self.assertTrue(saved['committed'])
        self.assertEqual(saved['push'], {'branch': 'main', 'address': str(self.remote), 'commits': 1, 'brands': 1})
        self.assertEqual(self.log(self.remote, 'log', '--format=%s', 'main').strip(), 'Start')
        self.assertIn('studio-note.md', self.log(self.checkout, 'status', '--porcelain'))   # never taken
        self.assertNotIn('studio-note.md', self.log(self.checkout, 'show', '--name-only', '--format='))
        self.assertEqual(self.call('list')['packs'][0]['unshared'], 1)
        with self.assertRaisesRegex(WorkspaceError, 'Say yes'):
            self.call('push')
        self.assertEqual(self.log(self.remote, 'log', '--format=%s', 'main').strip(), 'Start')
        pushed = self.call('push', confirm=True)
        self.assertTrue(pushed['pushed'])
        self.assertEqual(self.log(self.remote, 'log', '--format=%s', 'main').split('\n')[0], 'Add the Example Co brand pack')
        self.assertEqual(self.call('list')['packs'][0]['unshared'], 0)

    def test_a_refused_push_keeps_the_commit_here(self):
        self.made()
        other = self.root / 'other'
        subprocess.run(['git', 'clone', '--quiet', str(self.remote), str(other)], check=True, capture_output=True)
        (other / 'theirs.md').write_text('x\n')
        self.log(other, 'add', 'theirs.md')
        self.log(other, 'commit', '--quiet', '-m', 'Theirs')
        self.log(other, 'push', '--quiet', 'origin', 'main')
        with self.assertRaisesRegex(WorkspaceError, 'stays committed on this computer'):
            self.call('push', confirm=True)
        self.assertIn('Add the Example Co brand pack', self.log(self.checkout, 'log', '--format=%s'))

    def test_without_any_checkout_of_the_team_repository_brands_says_so(self):
        with mock.patch.object(workspaces, 'checkouts', return_value=[]):
            with self.assertRaisesRegex(WorkspaceError, 'Open a studio once'):
                self.call('list')


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
