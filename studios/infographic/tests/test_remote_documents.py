"""Fixed Google destinations, exact permissioned captures and public network boundaries."""
import json
from unittest import mock
from helpers import Isolated
from runner import intake, remote_sources, sources
from runner.contracts import Invalid
from runner.workspace import Store
from studio_core import public_fetch
from studio_core.google_api import Client, GoogleError, Response, DOC_MIME


def metadata():
    return {'id':'synthetic_doc', 'mimeType':DOC_MIME, 'name':'Synthetic Google Doc',
            'version':'3','modifiedTime':'2026-10-28T00:00:00Z','capabilities':{'canDownload':True}}


def document():
    def paragraph(value): return {'paragraph':{'elements':[{'textRun':{'content':value}}]}}
    return {'documentId':'synthetic_doc','tabs':[{'tabProperties':{'tabId':'a','title':'First'},
        'documentTab':{'body':{'content':[paragraph('First tab.'), {'table':{'tableRows':[{'tableCells':[{'content':[paragraph('Table count 12.')]}]}]}}]}},
        'childTabs':[{'tabProperties':{'tabId':'b','title':'Second'},'documentTab':{'body':{'content':[paragraph('Second tab.')]}}}]}]}


class RemoteSourcesTests(Isolated):
    def test_google_capture_all_tabs_and_exact_preview_import_no_refetch(self):
        client=mock.Mock();client.file.return_value=metadata();client.document.return_value=document()
        preview=remote_sources.google('https://docs.google.com/document/d/synthetic_doc/edit?tab=a',account='editor@example.invalid',client=client)
        self.assertEqual(preview['characters'],len('First tab.\nTable count 12.\nSecond tab.\n'))
        self.assertEqual(len(preview['locations']),3)
        store=Store.setup(self.workspace);p=store.create('Synthetic imported Doc')
        p=intake.adopt(store,p['id'],preview['id'],expected_revision=0)
        self.assertEqual(p['sources'][0]['provenance']['version'],'3')
        self.assertIn('Second tab.',sources.read(store,p,p['sources'][0]))
        self.assertEqual(client.file.call_count,2);client.document.assert_called_once()

    def test_selected_tab_omits_other_private_tab_from_snapshot(self):
        client=mock.Mock();client.file.return_value=metadata();client.document.return_value=document()
        preview=remote_sources.google('https://docs.google.com/document/d/synthetic_doc/edit',account='editor@example.invalid',tabs=['b'],client=client)
        record,raw,extracted=intake.read(preview['id'])
        self.assertNotIn(b'First tab.',raw);self.assertEqual(extracted['text'],'Second tab.\n')
        self.assertEqual(record['provenance']['tabs'],['b'])

    def test_permission_change_or_version_race_refused(self):
        for changed in ({'version':'4'}, {'capabilities':{'canDownload':False}}):
            client=mock.Mock();client.file.side_effect=[metadata(),{**metadata(),**changed}];client.document.return_value=document()
            with self.assertRaisesRegex(Invalid,'changed'):remote_sources.google('https://docs.google.com/document/d/synthetic_doc/edit',account='editor@example.invalid',client=client)
        client=mock.Mock();client.file.return_value={**metadata(),'capabilities':{'canDownload':False}}
        with self.assertRaisesRegex(Invalid,'cannot capture'):remote_sources.google('https://docs.google.com/document/d/synthetic_doc/edit',account='editor@example.invalid',client=client)
        client.document.assert_not_called()

    def test_google_lookalikes_never_read_account(self):
        for url in ('https://docs.google.com.evil.example/document/d/x/edit','http://docs.google.com/document/d/x/edit','https://docs.google.com:443/document/d/x/edit','https://user@docs.google.com/document/d/x/edit'):
            client=mock.Mock()
            with self.assertRaises(Invalid):remote_sources.google(url,account='editor@example.invalid',client=client)
            client.file.assert_not_called()

    def test_public_redirect_rechecks_every_address_and_pins_transport(self):
        transport=mock.Mock(side_effect=[(302,{'location':'https://other.example/page'},b''),(200,{'content-type':'text/html'},b'<p>Read me.</p>')])
        resolver=mock.Mock(return_value=['8.8.8.8'])
        found=public_fetch.fetch('https://public.example/page',resolver=resolver,transport=transport)
        self.assertEqual(found['url'],'https://other.example/page');self.assertEqual(resolver.call_count,2)
        self.assertEqual(transport.call_args.args[1],'8.8.8.8')
        for addresses in (['127.0.0.1'],['8.8.8.8','10.0.0.1'],['::ffff:127.0.0.1'],[]):
            blocked=mock.Mock()
            with self.assertRaises(ValueError):public_fetch.fetch('https://public.example/page',resolver=lambda host:addresses,transport=blocked)
            blocked.assert_not_called()
        with self.assertRaises(ValueError):public_fetch.fetch('https://public.example/page',resolver=lambda host:['8.8.8.8'],transport=lambda *a:(302,{'location':'https://localhost/private'},b''))

    def test_google_transport_never_forwards_credentials_or_replays_write(self):
        token=mock.Mock(return_value='synthetic-memory-only')
        transport=mock.Mock(return_value=Response(302,{'location':'https://evil.example'},b''))
        client=Client('editor@example.invalid',token_provider=token,transport=transport)
        for url in ('https://evil.example/drive/v3/files','https://www.googleapis.com/drive/v3/../private',None):
            with self.assertRaises(GoogleError):client.request(url)
        token.assert_not_called();transport.assert_not_called()
        with self.assertRaises(GoogleError) as failed:client.request('https://www.googleapis.com/drive/v3/files',method='POST',body={})
        self.assertTrue(failed.exception.uncertain);self.assertEqual(transport.call_count,1)
        self.assertNotIn('synthetic-memory-only',str(failed.exception))

    def test_resumable_conversion_validates_private_session_and_metadata(self):
        responses=[Response(200,{'Location':'https://www.googleapis.com/upload/drive/v3/files?uploadType=resumable&upload_id=opaque'},b''),Response(200,{},json.dumps({'id':'new_doc'}).encode())]
        calls=[]
        def send(*args):calls.append(args);return responses.pop(0)
        client=Client('editor@example.invalid',token_provider=lambda _: 'synthetic-memory-only',transport=send)
        self.assertEqual(client.create_document(b'docx',title='Synthetic',request_key='request1',payload_hash='a'*64)['id'],'new_doc')
        self.assertEqual([c[0] for c in calls],['POST','PUT']);self.assertEqual(calls[-1][-1],b'docx')
        self.assertEqual(json.loads(calls[0][-1])['mimeType'],DOC_MIME)
        bad=Client('editor@example.invalid',token_provider=lambda _:'synthetic-memory-only',transport=lambda *a:Response(200,{'location':'https://evil.example/upload'},b''))
        with self.assertRaises(GoogleError):bad.create_document(b'docx',title='Synthetic',request_key='request1',payload_hash='a'*64)
