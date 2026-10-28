"""Delivery intent/recovery against synthetic accounts only; no live Google conversion claim."""
import io
import zipfile
from unittest import mock
from helpers import Isolated
import test_desk_engine as desk
from runner import google_delivery
from runner.contracts import Invalid
from studio_core.google_api import DOC_MIME, GoogleError


class GoogleDeliveryTests(Isolated):
    def setUp(self):
        super().setUp();desk.setup_desk(self)
    current=desk.DeskEngineTests.current
    review_and_approve=desk.DeskEngineTests.review_and_approve

    # Inherit the full source→review setup and its invariant tests.
    def ready(self):
        self.review_and_approve()
        return self.engine.preview(self.ident,expected_revision=self.current()['revision'],draft=False)

    def send(self,delivery,client,**extra):
        return google_delivery.execute(self.store,self.ident,expected_revision=extra.pop('revision',self.current()['revision']),
            export_id=delivery['id'],request_id='synthetic_delivery',account='editor@example.invalid',client=client,**extra)

    def client(self):
        client=mock.Mock()
        def created(payload,**kw):
            self.assertTrue((self.store._project(self.ident)/'jobs/google_synthetic_delivery/delivery-intent.json').is_file())
            return {'id':'new_doc','mimeType':DOC_MIME,'appProperties':{'infographic_request':kw['request_key'],'infographic_payload':kw['payload_hash']}}
        client.create_document.side_effect=created
        return client

    def test_creates_private_image_and_editable_text_only_once(self):
        delivery=self.ready();client=self.client()
        result=self.send(delivery,client)
        self.assertEqual(result['state'],'delivered');self.assertEqual(result['document_id'],'new_doc')
        archive=zipfile.ZipFile(io.BytesIO(client.create_document.call_args.args[0]))
        self.assertIn('word/media/page.png',archive.namelist())
        content=archive.read('word/document.xml').decode()
        self.assertIn('Captured sources',content);self.assertIn('descr=',content)
        self.assertNotIn('TargetMode="External"',archive.read('word/_rels/document.xml.rels').decode())
        self.assertEqual(self.send(delivery,client),result);client.create_document.assert_called_once()
        inspected=self.engine.inspect(self.ident)
        self.assertEqual(len(inspected['google_deliveries']),1);self.assertTrue(inspected['google_deliveries'][0]['current']);self.assertEqual(inspected['recovery'],[])

    def test_uncertain_upload_never_resends_and_reconciles_by_exact_payload(self):
        delivery=self.ready();client=self.client();client.create_document.side_effect=GoogleError('Synthetic timeout',uncertain=True)
        self.assertEqual(self.send(delivery,client)['state'],'unknown')
        self.assertEqual(self.send(delivery,client)['state'],'unknown');client.create_document.assert_called_once()
        intent=google_delivery.listing(self.store,self.ident)[0]
        client.find_delivery.return_value=[{'id':'recovered_doc','mimeType':DOC_MIME,'appProperties':{'infographic_request':'synthetic_delivery','infographic_payload':intent['payload_sha256']}}]
        self.assertEqual(self.send(delivery,client,reconcile=True)['document_id'],'recovered_doc');client.create_document.assert_called_once()

    def test_changed_page_cannot_deliver_but_old_unknown_can_reconcile(self):
        delivery=self.ready();revision=self.current()['revision'];client=self.client()
        client.create_document.side_effect=GoogleError('Synthetic timeout',uncertain=True)
        self.send(delivery,client)
        p=self.current();self.store.edit_brief(self.ident,{**p['brief'],'title':'New title'},expected_revision=p['revision'])
        with self.assertRaises(Invalid):google_delivery.execute(self.store,self.ident,expected_revision=self.current()['revision'],export_id=delivery['id'],request_id='new_request',account='editor@example.invalid',client=client)
        client.find_delivery.return_value=[]
        self.assertEqual(self.send(delivery,client,reconcile=True,revision=revision)['state'],'unknown')
        client.create_document.assert_called_once()
        self.assertFalse(google_delivery.listing(self.store,self.ident)[0]['current'])

    def test_destination_conflict_and_multiple_results_refuse(self):
        delivery=self.ready();client=self.client();client.create_document.side_effect=GoogleError('Synthetic timeout',uncertain=True)
        self.send(delivery,client)
        with self.assertRaises(Invalid):self.send(delivery,client,folder='other_folder')
        client.find_delivery.return_value=[{},{}]
        with self.assertRaises(Invalid):self.send(delivery,client,reconcile=True)
