"""The Document Library handoff in Blog Studio (#514): a folder on this computer, a Google
Drive folder link and spreadsheets through studio_core.source_intake, saved as files for one
blog; and a folder on this computer refused to a caller from afar (Marketing Studio's phone
link). The page's own handling of library= and Continue in another studio is checked by
scripts/ci/check-management.cjs (documentLibraryHandoff).

Folders and workbooks are made here, in a disposable folder; no Google account is used.
"""

import isolation  # noqa: F401  (first: keeps every test off this computer's own settings)
import base64
import json
import sys
import time
from pathlib import Path
from unittest.mock import patch

import management
import studio
from studio_core import source_intake
from test_blog_runner import RunnerCase

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / 'tests'))
import xlsx_fixture  # noqa: E402  (Marketing Studio's synthetic workbooks)

PORT = 54321
OPERATION = 'f' * 32


class IntakeCase(RunnerCase):
    def setUp(self):
        super().setUp()
        self.folder = self.base / 'Launch'
        (self.folder / 'Plans').mkdir(parents=True)
        (self.folder / 'Plans' / 'Brief.md').write_text('# Brief\n\nThe gateway retries twice.\n')
        (self.folder / 'notes.txt').write_text('Launch notes for the gateway.\n')
        (self.folder / 'Pricing.xlsx').write_bytes(
            xlsx_fixture.workbook([('Prices', [['Plan', 'Price'], ['Team', 30]])])
        )

    def intake(self, **data):
        return management.dispatch(
            self.root, 'files-intake', {'operation': OPERATION, 'role': 'material', **data}
        )


class FolderTests(IntakeCase):
    def test_a_folder_on_this_computer_becomes_files_for_one_blog(self):
        result = self.intake(folder=str(self.folder), local=True)
        names = sorted(row['filename'] for row in result['files'])
        self.assertEqual(len(names), 3, names)
        self.assertTrue(any(name.startswith('Plans - Brief') for name in names), names)
        self.assertTrue(any('Pricing.xlsx' in name for name in names), 'a workbook read as text')
        self.assertTrue(all(row['state'] == 'ready' for row in result['files']))
        self.assertIn('said', result)
        for row in result['files']:
            directory, record = studio.item(self.root, 'sources', row['source']['id'])
            self.assertTrue(studio.is_material(self.root, directory, record), 'for this blog only')
        sheet = next(row for row in result['files'] if 'Pricing' in row['filename'])
        directory, _ = studio.item(self.root, 'sources', sheet['source']['id'])
        self.assertIn('Team', (directory / 'content.md').read_text())

    def test_a_folder_here_is_refused_from_afar_and_nothing_is_read(self):
        with patch.object(source_intake.research_sources.Sources, 'add_folder') as sources:
            with self.assertRaisesRegex(ValueError, 'only on this computer'):
                self.intake(folder=str(self.folder), local=False)
        sources.assert_not_called()
        self.assertFalse((self.root / 'sources').exists() and any((self.root / 'sources').iterdir()))

    def test_room_and_names_already_taken_are_kept(self):
        result = self.intake(folder=str(self.folder), local=True, room=1)
        self.assertEqual(len(result['files']), 1)
        self.assertTrue(result['next'], 'what was left is said')

    def test_one_spreadsheet_is_read_as_text(self):
        data = (self.folder / 'Pricing.xlsx').read_bytes()
        result = self.intake(
            file={'name': 'Pricing.xlsx', 'content': base64.b64encode(data).decode()}, local=False
        )
        self.assertEqual([row['filename'] for row in result['files']], ['Pricing.xlsx.md'])
        with self.assertRaisesRegex(ValueError, 'Excel workbook'):
            self.intake(file={'name': 'notes.txt', 'content': 'eA=='}, local=True)

    def test_requests_the_page_does_not_send_are_refused(self):
        for data, words in (
            ({'folder': 'x', 'file': {}}, 'one folder, or one spreadsheet'),
            ({'local': True}, 'one folder, or one spreadsheet'),
            ({'folder': str(self.folder)}, 'at this computer'),
            ({'folder': str(self.folder), 'local': 'yes'}, 'at this computer'),
            ({'folder': str(self.folder), 'local': True, 'role': 'voice'}, 'facts'),
            ({'folder': str(self.folder), 'local': True, 'room': 21}, 'up to 20'),
            ({'folder': str(self.folder), 'local': True, 'path': '/'}, 'fields'),
        ):
            with self.assertRaisesRegex(ValueError, words):
                self.intake(**data)


class RemoteCallerTests(IntakeCase):
    """Whether a request is from this computer is the page server's to say, never the page's."""

    def setUp(self):
        super().setUp()
        self.server, url = management.server(self.root, port=PORT, bind=False)
        self.addCleanup(self.server.server_close)
        self.token = url.split('#')[1]

    def post(self, data, **extra):
        body = json.dumps(data).encode()
        headers = {
            'Host': '127.0.0.1:%d' % PORT,
            'X-Blog-Studio-Token': self.token,
            'Content-Type': 'application/json',
            'Content-Length': str(len(body)),
            **extra,
        }
        status, _, reply, _ = self.server.desk.answer('/api/files-intake', headers, 'POST', body)
        self.assertEqual(status, 200, reply)
        job = json.loads(reply)['job']
        ends = time.monotonic() + 20
        while job['status'] == 'working':
            self.assertLess(time.monotonic(), ends)
            time.sleep(0.02)
            _, _, reply, _ = self.server.desk.answer(
                '/api/tool-job?job=' + job['id'], {k: v for k, v in headers.items() if k in (
                    'Host', 'X-Blog-Studio-Token')}
            )
            job = json.loads(reply)
        return job

    def test_a_folder_here_is_read_only_for_a_request_from_this_computer(self):
        request = {'operation': OPERATION, 'folder': str(self.folder), 'role': 'material'}
        # Through the phone link the page's own header never arrives: refused.
        refused = self.post(request)
        self.assertEqual(refused['status'], 'failed')
        self.assertEqual(refused['error'], source_intake.REMOTE)
        # A page cannot say for itself that it is on this computer.
        self.assertEqual(self.post({**request, 'local': True})['status'], 'failed')
        # A link that says the request came over the network is believed.
        said = self.post(request, **{'X-Blog-Studio-Local': '1', 'X-Marketing-Studio-Via': 'network'})
        self.assertEqual(said['status'], 'failed')
        self.assertFalse((self.root / 'sources').exists() and any((self.root / 'sources').iterdir()))
        # From this computer's own page it is read and saved.
        taken = self.post(request, **{'X-Blog-Studio-Local': '1'})
        self.assertEqual(taken['status'], 'ready', taken)
        self.assertEqual(len(taken['result']['files']), 3)

    def test_the_phone_links_via_header_alone_refuses_a_folder_here(self):
        request = {'operation': OPERATION, 'folder': str(self.folder), 'role': 'material'}
        refused = self.post(
            request, **{'X-Blog-Studio-Local': '1', 'X-Marketing-Studio-Via': 'network'}
        )
        self.assertEqual((refused['status'], refused['error']), ('failed', source_intake.REMOTE))
        self.assertTrue(management.remote_caller({'X-Marketing-Studio-Via': 'network'}))
        self.assertTrue(
            management.remote_caller(
                {'X-Marketing-Studio-Via': 'network', 'X-Blog-Studio-Local': '1'}
            )
        )
        self.assertFalse(management.remote_caller({'X-Blog-Studio-Local': '1'}))

    def test_a_drive_folder_is_read_with_this_workspaces_google_account(self):
        import google_drive

        seen = []

        def take(given, **options):
            seen.append(options['store'].account())
            return {'uploads': {}, 'documents': [], 'skipped': [], 'said': 'Nothing.',
                    'next': None, 'report': {}}

        with (
            patch.object(source_intake, 'take', take),
            patch.object(google_drive, 'account_for', lambda root=None: 'writer@example.test'),
        ):
            self.intake_direct('https://drive.google.com/drive/folders/abc123')
        self.assertEqual(seen, ['writer@example.test'])

    def intake_direct(self, folder):
        return management.dispatch(
            self.root,
            'files-intake',
            {'operation': OPERATION, 'role': 'material', 'folder': folder, 'local': False},
        )

    def test_a_drive_folder_link_is_taken_from_afar(self):
        found = {'uploads': {'Plan.md': b'# Plan\n'}, 'documents': [], 'skipped': [],
                 'said': '1 document was added from Plans.', 'next': None, 'report': {}}
        seen = []

        def take(given, **options):
            seen.append((given, options['local']))
            return found

        with patch.object(source_intake, 'take', take):
            done = self.post(
                {'operation': OPERATION, 'folder': 'https://drive.google.com/drive/folders/abc123'}
            )
        self.assertEqual(done['status'], 'ready', done)
        self.assertEqual(seen, [('https://drive.google.com/drive/folders/abc123', False)])
        self.assertEqual(done['result']['said'], '1 document was added from Plans.')
        self.assertEqual([row['filename'] for row in done['result']['files']], ['Plan.md'])


class IntakeFieldTests(RunnerCase):
    def test_every_field_the_page_keeps_is_one_the_server_saves(self):
        import re

        page = (
            Path(management.__file__).resolve().parents[1] / 'assets/management/desk.js'
        ).read_text()
        fields = set(re.search(r"const DESK_INTAKE_FIELDS='([^']+)'", page).group(1).split())
        self.assertIn('libraryStart', fields)
        self.assertEqual(fields - management.INTAKE_FIELDS, set())
        pick = {'id': 'launch-facts', 'revision': 2, 'title': 'Launch facts', 'role': 'facts'}
        saved = management.dispatch(
            self.root,
            'intake-draft',
            {'action': 'save', 'expected': 0, 'patch': {'libraryStart': pick}},
        )
        self.assertEqual(saved['draft']['libraryStart'], pick)
