"""Comment fallback fixtures: no Google login or real document writes."""
import copy
import json
import unittest
from unittest.mock import Mock
import urllib.error
import io
import test_google_suggestions as fixtures
ReviewProvider=fixtures.ReviewProvider
import google_suggestions as gs
import google_review_comments as review
import google_drive as gd
import author_workflow


class CommentProvider(ReviewProvider):
    def __init__(self):
        super().__init__();self.native_available=False;self.native_comments=True
        self.drive_threads=[];self.creates=0;self.resolutions=0;self.fail_create=False
        self.suggest_rejection=None
    def native_read(self, file_id, inline=False, comments=False, accepted_preview=False):
        if comments and not self.native_available:raise gd.ReviewUnavailable('No connector review surface')
        return super().native_read(file_id,inline,comments,accepted_preview)
    def native_review_update(self,*args):
        if self.suggest_rejection:raise self.suggest_rejection
        return super().native_review_update(*args)
    def native_comments_update(self,*args):
        if not self.native_comments:raise gd.GoogleError('Unsupported',status=400,review_unavailable=True)
        return ReviewProvider.native_review_update(self,*args)
    def metadata(self,file_id):return {'version':self.version,'capabilities':{'canComment':True}}
    def review_comments(self,file_id):return copy.deepcopy(self.drive_threads)
    def create_review_comment(self,file_id,content,quote):
        self.creates+=1
        result={'id':'comment'+str(self.creates),'content':content,'quotedFileContent':{'value':quote},'author':{'me':True},'resolved':False}
        self.drive_threads.append(result)
        if self.fail_create:raise gd.GoogleError('timeout')
        return copy.deepcopy(result)
    def resolve_review_comment(self,file_id,comment_id):
        self.resolutions+=1
        next(t for t in self.drive_threads if t['id']==comment_id)['resolved']=True
        return {'id':'reply','action':'resolve'}
    def resolve_native_comment(self,file_id,comment_id,revision):
        self.resolutions+=1
        next(t for t in self.comments if t['commentId']==comment_id)['status']='RESOLVED'
        return {'commentUpdateState':'ALL_SAVED'}


class CommentTests(unittest.TestCase):
    findings=fixtures.SuggestionsTests.findings
    plan=fixtures.SuggestionsTests.plan
    def setUp(self):
        fixtures.SuggestionsTests.setUp(self);self.client=CommentProvider()
    def test_explicit_comment_request_skips_supported_suggestions(self):
        self.client.native_available=True
        self.client.native_review_update=Mock(wraps=self.client.native_review_update)
        before=gs.signature(self.client.doc)
        routed=author_workflow.route(self.root,'Push feedback as comments',self.aid)
        path=self.root/'comments-first.json'
        gs.plan(self.client,self.root,self.aid,routed['kind'],self.findings(),path,mode=routed['review_mode'])
        saved=json.loads(path.read_text())
        result=gs.apply(self.client,self.root,saved)
        self.assertEqual(result['status'],'verified-comments')
        self.assertEqual(result['mode'],'native-comments')
        self.client.native_review_update.assert_not_called()
        self.assertFalse(self.client.threads)
        self.assertEqual(gs.signature(self.client.doc),before)
        self.assertEqual(len(self.client.comments),3)
    def test_explicit_comments_keep_drive_fallback_without_suggestion_attempt(self):
        self.client.native_available=True;self.client.native_comments=False
        self.client.native_review_update=Mock(wraps=self.client.native_review_update)
        path=self.root/'comments-first.json'
        gs.plan(self.client,self.root,self.aid,'draft',self.findings(),path,mode='comments')
        result=gs.apply(self.client,self.root,json.loads(path.read_text()))
        self.assertEqual(result['mode'],'drive-comments')
        self.assertEqual(result['status'],'verified-comments')
        self.assertTrue(result['accepted_text_unchanged'])
        self.client.native_review_update.assert_not_called()
        self.assertEqual(self.client.writes,0)
        self.assertEqual(self.client.creates,3)
    def test_comment_short_requests_preserve_mode_and_destination(self):
        for text in ('Push as comments','Push feedback as comments',
                     'Send feedback as comments to Google Docs',
                     'Push changes to Google as comments','Push edits as comments to Google'):
            with self.subTest(text=text):
                routed=author_workflow.route(self.root,text,self.aid)
                self.assertEqual(routed['actions'],['google-suggest'])
                self.assertEqual(routed['review_mode'],'comments')
                self.assertEqual(routed['linked_document'],self.record['google']['baselines']['draft']['document']['url'])
        for text in ('Push changes to Google','Push changes to Google Docs','Push as suggestions'):
            routed=author_workflow.route(self.root,text,self.aid)
            self.assertEqual(routed['review_mode'],'auto')
        direct=author_workflow.route(self.root,'Push to Google Docs',self.aid)
        self.assertEqual(direct['actions'],['google-push'])
        self.assertNotIn('review_mode',direct)
    def test_unavailable_native_read_posts_clear_numbered_drive_comments(self):
        saved=self.plan();self.assertEqual(saved['mode'],'comments')
        result=gs.apply(self.client,self.root,saved)
        self.assertEqual(result['status'],'verified-comments');self.assertEqual(result['mode'],'drive-comments')
        self.assertTrue(result['accepted_text_unchanged']);self.assertEqual(self.client.writes,0)
        self.assertEqual(self.client.creates,3)
        body=self.client.drive_threads[0]['content']
        for value in ('Edit 1','Current: delay','Proposed: wait','Why:', 'The delay is in handoffs.'):
            self.assertIn(value,body)
        self.assertIn('All Comments',result['next_step'])
        self.assertEqual(review.show(self.root,self.aid)['edits'][1]['number'],2)
        with self.assertRaises(gd.GoogleError):gs.apply(self.client,self.root,saved)
        self.assertEqual(self.client.creates,3)
    def test_definite_native_write_rejection_prefers_anchored_comments(self):
        self.client.native_available=True
        self.client.suggest_rejection=gd.GoogleError('Unsupported writeMode',status=400,review_unavailable=True)
        saved=self.plan();result=gs.apply(self.client,self.root,saved)
        self.assertEqual(result['status'],'verified-comments');self.assertEqual(result['mode'],'native-comments')
        self.assertEqual(self.client.creates,0);self.assertEqual(len(self.client.comments),3)
        self.assertFalse(self.client.threads)
    def test_native_comments_rejection_uses_drive_without_direct_edits(self):
        self.client.native_available=True;self.client.native_comments=False
        self.client.suggest_rejection=gd.GoogleError('Denied',status=403,review_unavailable=True)
        saved=self.plan();result=gs.apply(self.client,self.root,saved)
        self.assertEqual(result['status'],'verified-comments');self.assertEqual(result['mode'],'drive-comments')
        self.assertEqual(self.client.writes,0);self.assertEqual(self.client.creates,3)
    def test_uncertain_native_write_never_posts_fallback_comments(self):
        self.client.native_available=True;self.client.suggest_rejection=gd.GoogleError('timeout')
        saved=self.plan()
        with self.assertRaises(gd.GoogleError):gs.apply(self.client,self.root,saved)
        self.assertEqual(self.client.creates,0)
    def test_partial_native_response_never_posts_fallback(self):
        self.client.native_available=True
        def partial(*args):return {'commentUpdateState':'ALL_FAILED_UNKNOWN_REASON'}
        self.client.native_review_update=partial
        saved=self.plan();self.assertEqual(gs.apply(self.client,self.root,saved)['status'],'needs-reconciliation')
        self.assertEqual(self.client.creates,0)
    def test_uncertain_comment_create_does_not_retry(self):
        saved=self.plan();self.client.fail_create=True
        with self.assertRaises(gd.GoogleError):gs.apply(self.client,self.root,saved)
        with self.assertRaises(gd.GoogleError):gs.apply(self.client,self.root,saved)
        self.assertEqual(gs.verify(self.client,self.root,saved)['status'],'needs-reconciliation')
        self.assertEqual(self.client.creates,1)
    def test_remote_existing_resolved_finding_stops_duplicate(self):
        saved=self.plan();self.client.drive_threads=[{'id':'old','resolved':True,'content':'[Blog Studio proof-1]'}]
        with self.assertRaises(gd.GoogleError):gs.apply(self.client,self.root,saved)
        self.assertEqual(self.client.creates,0)
    def test_minor_fixes_group_but_keep_individual_edit_numbers(self):
        findings=[{**self.findings()[0],'minor':True},
                  {'id':'second','kind':'edit','tab_id':'t.0','start_index':17,'before':'handoffs','after':'coordination','reason':'Clarify.','minor':True}]
        saved=self.plan(findings);result=gs.apply(self.client,self.root,saved)
        self.assertEqual(len(result['comments']),1)
        result=review.apply_edits(self.client,self.root,saved,[1])
        self.assertEqual(result['status'],'applied');self.assertEqual(self.client.resolutions,0)
        result=review.apply_edits(self.client,self.root,saved,[2])
        self.assertEqual(result['status'],'applied');self.assertEqual(self.client.resolutions,1)
    def test_explicit_edits_preserve_formatting_and_only_resolve_selected_comments(self):
        saved=self.plan();gs.apply(self.client,self.root,saved)
        before=copy.deepcopy(self.client.doc['tabs'][0]['documentTab']['body']['content'][1]['paragraph']['paragraphStyle'])
        result=review.apply_edits(self.client,self.root,saved,[1,2])
        self.assertEqual(result['applied'],[1,2]);self.assertEqual(self.client.resolutions,2)
        self.assertEqual(self.client.doc['tabs'][0]['documentTab']['body']['content'][1]['paragraph']['paragraphStyle'],before)
        self.assertFalse(self.client.drive_threads[2]['resolved'])
        with self.assertRaises(gd.GoogleError):review.apply_edits(self.client,self.root,saved,[1])
    def test_resolved_comment_is_not_approval_and_changed_google_blocks_selected_apply(self):
        saved=self.plan();gs.apply(self.client,self.root,saved)
        self.client.drive_threads[0]['resolved']=True
        result=gs.verify(self.client,self.root,saved)
        self.assertEqual(self.client.writes,0);self.assertEqual(result['status'],'verified-comments')
        self.client.doc['tabs'][0]['documentTab']['body']['content'][1]['paragraph']['elements'][0]['textRun']['content']='Changed by team.\n'
        with self.assertRaises(gd.GoogleError):review.apply_edits(self.client,self.root,saved,[1])
        self.assertEqual(self.client.writes,0)
    def test_unknown_or_feedback_numbers_and_changed_comments_block_edits(self):
        saved=self.plan();gs.apply(self.client,self.root,saved)
        for numbers in ([99],[3],[1,1],[]):
            with self.assertRaises(gd.GoogleError):review.apply_edits(self.client,self.root,saved,numbers)
        self.client.drive_threads[0]['content']='Different review'
        with self.assertRaises(gd.GoogleError):review.apply_edits(self.client,self.root,saved,[1])
        self.assertEqual(self.client.writes,0)
    def test_ambiguous_paragraph_and_uncertain_edit_never_repeat(self):
        saved=self.plan();gs.apply(self.client,self.root,saved)
        actual=self.client.native_update
        def uncertain(*args):actual(*args);raise gd.GoogleError('timeout')
        self.client.native_update=uncertain
        with self.assertRaises(gd.GoogleError):review.apply_edits(self.client,self.root,saved,[1])
        with self.assertRaises(gd.GoogleError):review.apply_edits(self.client,self.root,saved,[1])
        self.assertEqual(review.verify_edits(self.client,self.root,saved)['status'],'applied-text-verified')
        self.assertEqual(self.client.writes,1);self.assertEqual(self.client.resolutions,0)
    def test_google_change_after_rejection_stops_fallback(self):
        self.client.native_available=True
        def reject(*args):
            self.client.doc['title']='Changed during submission'
            raise gd.GoogleError('Denied',status=403,review_unavailable=True)
        self.client.native_review_update=reject
        saved=self.plan()
        with self.assertRaises(gd.GoogleError):gs.apply(self.client,self.root,saved)
        self.assertEqual(self.client.creates,0)
    def test_resolution_timeout_reports_applied_without_repeating_text(self):
        saved=self.plan();gs.apply(self.client,self.root,saved)
        self.client.resolve_review_comment=Mock(side_effect=gd.GoogleError('timeout'))
        result=review.apply_edits(self.client,self.root,saved,[1])
        self.assertEqual(result['status'],'applied-comments-unresolved')
        self.assertEqual(self.client.writes,1)
        with self.assertRaises(gd.GoogleError):review.apply_edits(self.client,self.root,saved,[1])
    def test_revision_rejection_allows_new_guarded_plan_without_mutation(self):
        saved=self.plan();gs.apply(self.client,self.root,saved)
        self.client.native_update=Mock(side_effect=gd.GoogleError('Revision mismatch',status=409))
        with self.assertRaises(gd.GoogleError):review.apply_edits(self.client,self.root,saved,[1])
        self.assertNotIn('edit_attempt',json.loads(review.path(self.root,saved).read_text()))
        self.assertEqual(self.client.writes,0)
    def test_no_comment_permission_creates_no_submission_reservation(self):
        saved=self.plan();self.client.metadata=Mock(return_value={'capabilities':{'canComment':False}})
        with self.assertRaises(gd.GoogleError):gs.apply(self.client,self.root,saved)
        self.assertFalse(review.path(self.root,saved).exists());self.assertEqual(self.client.creates,0)
    def test_duplicate_paragraph_is_ambiguous_for_applying(self):
        saved=self.plan();gs.apply(self.client,self.root,saved)
        blocks=self.client.doc['tabs'][0]['documentTab']['body']['content']
        duplicate=copy.deepcopy(blocks[1]);duplicate['startIndex']=100;blocks.append(duplicate)
        with self.assertRaises(gd.GoogleError):review.apply_edits(self.client,self.root,saved,[1])
        self.assertEqual(self.client.writes,0)
    def test_comment_api_shapes_and_complete_pagination(self):
        client=gd.Client.__new__(gd.Client);client.request=Mock(return_value={'id':'c'})
        client.create_review_comment('fixture-doc','Review','quote')
        self.assertEqual(client.request.call_args.kwargs['body'],{'content':'Review','quotedFileContent':{'mimeType':'text/plain','value':'quote'}})
        client.resolve_review_comment('fixture-doc','c')
        self.assertEqual(client.request.call_args.kwargs['body']['action'],'resolve')
        client.drive=Mock(side_effect=[{'nextPageToken':'next','comments':[{'id':'1'}]}, {'comments':[{'id':'2'}]}])
        self.assertEqual([c['id'] for c in client.review_comments('fixture-doc')],['1','2'])
        self.assertEqual(client.drive.call_args.kwargs['pageToken'],'next')

    def test_short_commands_return_explicit_numbers(self):
        for text in ('Apply edits 2 and 4','Apply suggestions 2, 4'):
            result=author_workflow.route(self.root,text,self.aid)
            self.assertEqual(result['actions'],['google-apply-review-edits']);self.assertEqual(result['edit_numbers'],[2,4])
    def test_error_classification_never_treats_race_or_server_failure_as_fallback(self):
        client=gd.Client.__new__(gd.Client)
        from unittest.mock import patch
        for status,detail,expected in ((400,'Unknown name "writeMode"',True),(400,'Revision mismatch',False),(403,'Denied',False),(500,'Unknown name "writeMode"',False)):
            client.opener=Mock();client.opener.open.side_effect=urllib.error.HTTPError('https://docs.googleapis.com',status,'error',{},io.BytesIO(json.dumps({'error':{'message':detail}}).encode()))
            with patch('google_drive.token',return_value='fixture'):
                client.account=None
                with self.assertRaises(gd.GoogleError) as caught:client.request(gd.DOCS+'fixture:batchUpdate',method='POST',body={})
            self.assertEqual(caught.exception.review_unavailable,expected)
            self.assertNotIn(detail,str(caught.exception))


if __name__=='__main__':unittest.main()
