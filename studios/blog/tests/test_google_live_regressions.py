"""Sanitized live-report regressions; never reads user documents or credentials."""
import copy
import contextlib
import io
import json
import subprocess
import sys
import unittest
from unittest.mock import Mock, patch
import urllib.error

import test_google_suggestions as fixtures
import google_suggestions as gs
import google_roundtrip as rt
import google_review_comments as comments
import google_drive as gd
import google_workflow as gw
import studio


class LiveReviewRegressions(unittest.TestCase):
    def setUp(self): fixtures.SuggestionsTests.setUp(self)
    findings = fixtures.SuggestionsTests.findings
    plan = fixtures.SuggestionsTests.plan

    def test_native_plan_finds_text_before_and_after_inline_chart(self):
        blocks = self.client.doc['tabs'][0]['documentTab']['body']['content']
        chart = {'paragraph': {'elements': [{'inlineObjectElement': {'inlineObjectId': 'chart-fixture'}},
            {'textRun': {'content': '\n'}}]}}
        blocks.insert(2, chart)
        index = 1
        for block in blocks:
            if 'paragraph' not in block: continue
            block['startIndex'] = index
            for element in block['paragraph']['elements']:
                element['startIndex'] = index
                index += rt.utf16(element['textRun']['content']) if 'textRun' in element else 1
                element['endIndex'] = index
            block['endIndex'] = index
        self.record['google']['baselines']['draft']['document']['format_sha256'] = gs.signature(self.client.doc)
        studio.persist(self.directory, 'articles', self.record)
        findings = [dict(id='before',kind='edit',tab_id='t.0',start_index=5,before='delay',after='wait',reason='Plain language.'),
            dict(id='after',kind='comment',tab_id='t.0',start_index=blocks[4]['startIndex'],before='Keep',reason='Check source.')]
        output = self.root/'native-plan.json'
        gs.plan(self.client, self.root, self.aid, 'draft', findings, output, mode='native')
        planned = json.loads(output.read_text())
        self.assertEqual(len(planned['comment_plan']['comments']), 2)
        self.assertEqual(planned['comment_plan']['comments'][1]['range']['startIndex'], blocks[4]['startIndex'])
        self.assertEqual(planned['comments'][1]['range']['startIndex'], blocks[4]['startIndex'] + len('wait'))
        unsupported = [{**findings[1], 'start_index': chart['startIndex']}]
        with self.assertRaisesRegex(gd.GoogleError, 'unsupported objects'):
            gs.build(self.client.doc, unsupported, ['t.0'])

    def test_verified_native_response_with_tab_scoped_anchors_trimmed_quote_and_inherited_false(self):
        native = self.client.doc['tabs'][0]['documentTab']
        native['namedStyles'] = {'styles': [{'namedStyleType': 'NORMAL_TEXT', 'textStyle': {'italic': False}}]}
        native['body']['content'][1]['paragraph']['elements'][0]['textRun']['textStyle']['italic'] = False
        self.record['google']['baselines']['draft']['document']['format_sha256'] = gs.signature(self.client.doc)
        studio.persist(self.directory, 'articles', self.record)
        finding = dict(id='boundary',kind='edit',tab_id='t.0',start_index=4,before=' delay',after=' wait',reason='Plain language.')
        saved = self.plan([finding])
        actual = self.client.native_read
        def normalized(*args, **kwargs):
            doc = actual(*args, **kwargs)
            if kwargs.get('comments'):
                for anchor in doc['tabs'][0]['documentTab']['commentAnchors']:
                    for r in anchor['ranges']: r.pop('tabId', None)
                for comment in doc['comments']: comment['plainTextQuote'] = comment['plainTextQuote'].strip(' ')
            if kwargs.get('accepted_preview'):
                for para in rt.paragraphs(doc).values():
                    for e in para['elements']: e['textRun'].get('textStyle', {}).pop('italic', None)
            return doc
        self.client.native_read = normalized
        result = gs.apply(self.client, self.root, saved)
        self.assertEqual(result['status'], 'verified-pending')
        self.assertTrue(result['accepted_text_unchanged'])
        # A changed internal space remains a real mismatch despite exact ranges.
        self.client.comments[0]['plainTextQuote'] = 'de lay'
        self.assertEqual(gs.verify(self.client, self.root, saved)['status'], 'needs-reconciliation')

    def test_anchor_scope_and_quote_normalization_are_bounded_for_comment_fallback(self):
        doc = {'tabs': [{'tabProperties': {'tabId': 'first'}, 'documentTab': {'commentAnchors': [
            {'anchorId': 'a', 'ranges': [{'startIndex': 1, 'endIndex': 6}]}]},
            'childTabs': [{'tabProperties': {'tabId': 'second'}, 'documentTab': {'commentAnchors': [
                {'anchorId': 'b', 'ranges': [{'startIndex': 1, 'endIndex': 6}]}]}}]}]}
        anchors = gs.native_anchors(doc)
        self.assertEqual([a['ranges'][0]['tabId'] for a in anchors], ['first', 'second'])
        expected = {'content': 'Reason', 'quote': ' (EF)', 'range': {'tabId': 'first','startIndex': 1,'endIndex': 6}}
        thread = {'id': 'comment', 'content': 'Reason', 'quote': '(EF)', 'ranges': anchors[0]['ranges']}
        self.assertTrue(comments.matches(thread, expected, 'native-comments'))
        self.assertFalse(comments.matches(thread, expected, 'drive-comments'))
        thread['ranges'] = anchors[1]['ranges']
        self.assertFalse(comments.matches(thread, expected, 'native-comments'))
        self.assertFalse(gs.quote_matches('(EF)', '\u00a0(EF)'))
        self.assertFalse(gs.quote_matches('a b', 'a  b'))

    def test_omitted_style_matches_only_proven_inheritance(self):
        doc = copy.deepcopy(self.client.doc)
        native = doc['tabs'][0]['documentTab']
        native['namedStyles'] = {'styles': [{'namedStyleType': 'NORMAL_TEXT', 'textStyle': {'italic': False}}]}
        para = native['body']['content'][1]['paragraph']
        para['paragraphStyle']['namedStyleType'] = 'NORMAL_TEXT'
        para['elements'][0]['textRun']['textStyle']['italic'] = False
        omitted = copy.deepcopy(doc)
        omitted['tabs'][0]['documentTab']['body']['content'][1]['paragraph']['elements'][0]['textRun']['textStyle'].pop('italic')
        self.assertEqual(gs.signature(doc), gs.signature(omitted))
        for value in (doc, omitted):
            value['tabs'][0]['documentTab']['namedStyles']['styles'][0]['textStyle']['italic'] = True
        self.assertNotEqual(gs.signature(doc), gs.signature(omitted))
        for value in (doc, omitted): value['tabs'][0]['documentTab'].pop('namedStyles')
        self.assertNotEqual(gs.signature(doc), gs.signature(omitted))

    def test_table_inheritance_is_not_guessed_from_body_named_style(self):
        para = {'elements': [{'textRun': {'content': 'Cell', 'textStyle': {'italic': False}}}]}
        doc = {'namedStyles': {'styles': [{'namedStyleType': 'NORMAL_TEXT','textStyle': {'italic': False}}]},
               'table': {'tableRows': [{'tableCells': [{'content': [{'paragraph': para}]}]}]}}
        omitted = copy.deepcopy(doc)
        omitted['table']['tableRows'][0]['tableCells'][0]['content'][0]['paragraph']['elements'][0]['textRun']['textStyle'].pop('italic')
        self.assertNotEqual(rt.semantic(doc), rt.semantic(omitted))

    def test_hub_filesystem_failure_keeps_local_checkpoint_success_visible(self):
        for error in (PermissionError('private-path secret'), OSError('disk unavailable secret')):
            adapter = Mock(); adapter.publish_mutation.side_effect = error
            output = io.StringIO()
            with patch('hub_workspace.active', return_value=adapter), patch.object(sys, 'argv',
                ['studio.py','--root',str(self.root),'google','prepare','--id',self.aid,'--new-document']), contextlib.redirect_stdout(output):
                self.assertEqual(studio.main(), 0)
            result = json.loads(output.getvalue())
            self.assertEqual(result['status'], 'prepared')
            self.assertEqual(result['hub_sync']['status'], 'local-saved-not-shared')
            self.assertNotIn('secret', output.getvalue())
            _, record = studio.item(self.root, 'articles', self.aid)
            self.assertIn(result['transfer'], record['google']['transfers'])
            self.assertTrue(gw.snapshot_path(self.directory, result['transfer'], 'local').exists())


class GoogleAuthRegressions(unittest.TestCase):
    def test_local_credential_denial_is_not_reported_as_login_expiry(self):
        for failure in (PermissionError('private-path secret'),
                        subprocess.CompletedProcess([], 1, 'secret', 'gcloud credentials.db: Operation not permitted secret')):
            with patch.object(gd, 'gcloud', return_value='gcloud'), patch.object(gd.subprocess, 'run') as run:
                if isinstance(failure, Exception): run.side_effect = failure
                else: run.return_value = failure
                with self.assertRaisesRegex(gd.GoogleError, 'access.*denied') as caught: gd.token()
                self.assertNotIn('secret', str(caught.exception))
                self.assertNotIn('auth login', str(caught.exception))

    def test_scope_policy_and_rate_errors_never_trigger_review_fallback_or_leak_bodies(self):
        for reason in ('ACCESS_TOKEN_SCOPE_INSUFFICIENT', 'insufficientPermissions', 'SERVICE_DISABLED', 'insufficientFilePermissions', 'rateLimitExceeded', 'unknown-secret'):
            payload = {'error': {'status': 'PERMISSION_DENIED', 'message': 'secret writeMode unsupported',
                'details': [{'reason': reason, 'metadata': {'token': 'secret'}}]}}
            client = gd.Client(); client.opener.open = Mock(side_effect=urllib.error.HTTPError(gd.DOCS,403,'secret',{},io.BytesIO(json.dumps(payload).encode())))
            with patch.object(gd, 'token', return_value='secret'):
                with self.assertRaises(gd.GoogleError) as caught: client.request(gd.DOCS+'fixture',method='POST',body={})
            self.assertNotIn('secret', str(caught.exception))
            if reason != 'unknown-secret': self.assertIn(reason, str(caught.exception))
            self.assertFalse(caught.exception.review_unavailable)
            if reason in ('ACCESS_TOKEN_SCOPE_INSUFFICIENT', 'insufficientPermissions'):
                self.assertIn('--no-activate', str(caught.exception))
            self.assertEqual(client.opener.open.call_count, 1)

    def test_explicit_unsupported_field_is_distinct_from_scope_failure(self):
        client = gd.Client()
        payload = {'error': {'status': 'INVALID_ARGUMENT', 'message': 'Unknown name "writeMode"'}}
        client.opener.open = Mock(side_effect=urllib.error.HTTPError(gd.DOCS,400,'error',{},io.BytesIO(json.dumps(payload).encode())))
        with patch.object(gd, 'token', return_value='fixture'):
            with self.assertRaises(gd.GoogleError) as caught: client.request(gd.DOCS+'fixture', method='POST',body={})
        self.assertTrue(caught.exception.review_unavailable)
