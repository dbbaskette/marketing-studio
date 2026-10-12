"""Comment fallback fixtures: no Google login or real document writes."""
import contextlib
import copy
import json
import sys
import unittest
from unittest.mock import Mock, patch
import urllib.error
import io
import test_google_suggestions as fixtures
ReviewProvider=fixtures.ReviewProvider
import google_suggestions as gs
import google_review_comments as review
import google_roundtrip as rt
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
    def test_interrupted_comment_batch_resumes_by_marker_without_duplicates(self):
        # The first comment lands but its response is lost. A repeated apply finds it by
        # its in-Doc marker and posts only the comments that are still missing.
        saved=self.plan();self.client.fail_create=True
        with self.assertRaisesRegex(gd.GoogleError,'uncertain'):gs.apply(self.client,self.root,saved)
        self.assertEqual(self.client.creates,1)
        self.assertEqual(gs.verify(self.client,self.root,saved)['status'],'needs-reconciliation')
        self.client.fail_create=False
        result=gs.apply(self.client,self.root,saved)
        self.assertEqual(result['status'],'verified-comments')
        self.assertEqual(self.client.creates,3)
        self.assertEqual(len(self.client.drive_threads),3)
        with self.assertRaisesRegex(gd.GoogleError,'already attempted'):gs.apply(self.client,self.root,saved)
        self.assertEqual(self.client.creates,3)

    def test_uncertain_comment_that_is_not_visible_needs_an_explicit_repost(self):
        saved=self.plan()
        real=self.client.create_review_comment
        self.client.create_review_comment=Mock(side_effect=gd.GoogleError('timeout'))
        with self.assertRaisesRegex(gd.GoogleError,'uncertain'):gs.apply(self.client,self.root,saved)
        self.client.create_review_comment=real
        with self.assertRaisesRegex(gd.GoogleError,'--repost-missing'):gs.apply(self.client,self.root,saved)
        self.assertEqual(self.client.creates,0)
        result=gs.apply(self.client,self.root,saved,repost_missing=True)
        self.assertEqual(result['status'],'verified-comments');self.assertEqual(self.client.creates,3)

    def test_definite_refusal_mid_batch_resumes_and_rate_limits_are_waited_out(self):
        saved=self.plan();real=self.client.create_review_comment;waits=[];calls=[]
        def flaky(file_id,content,quote):
            calls.append(content)
            if len(calls)==1:raise gd.GoogleError('Slow down',status=429)
            if len(calls)==3:raise gd.GoogleError('Denied',status=403)
            return real(file_id,content,quote)
        self.client.create_review_comment=flaky
        # Comment 1 is rate limited once and then posted; comment 2 is refused outright.
        with self.assertRaisesRegex(gd.GoogleError,'was not posted') as caught:
            review.apply(self.client,self.root,saved,sleep=waits.append)
        self.assertTrue(caught.exception.definite)
        self.assertEqual(waits,[review.RATE_LIMIT_WAITS[0]]);self.assertEqual(self.client.creates,1)
        receipt=json.loads(review.path(self.root,saved).read_text())
        self.assertEqual(receipt['not_posted'],{'numbers':[2],'status':403});self.assertNotIn('pending_comment',receipt)
        self.assertIn('Run apply again',gs.verify(self.client,self.root,saved)['message'])
        self.client.create_review_comment=real
        result=gs.apply(self.client,self.root,saved)
        self.assertEqual(result['status'],'verified-comments')
        self.assertEqual(self.client.creates,3)
        self.assertEqual(len({t['content'] for t in self.client.drive_threads}),3)
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
        self.assertEqual(self.client.writes,1);self.assertEqual(self.client.resolutions,0)
        # verify-edits records what it finds: the edit is applied, its comment resolved, the attempt cleared.
        settled=review.verify_edits(self.client,self.root,saved)
        self.assertEqual(settled['status'],'applied-text-verified');self.assertEqual(settled['numbers'],[1])
        self.assertEqual(self.client.writes,1);self.assertEqual(self.client.resolutions,1)
        receipt=json.loads(review.path(self.root,saved).read_text())
        self.assertEqual(receipt['applied'],[1]);self.assertNotIn('edit_attempt',receipt)
        self.assertEqual(review.show(self.root,self.aid)['applied'],[1])
        with self.assertRaisesRegex(gd.GoogleError,'No uncertain edit'):review.verify_edits(self.client,self.root,saved)
        # The review is usable again: another numbered edit goes through.
        self.client.native_update=actual
        self.assertEqual(review.apply_edits(self.client,self.root,saved,[2])['status'],'applied')
        self.assertEqual(self.client.writes,2)

    def test_lost_edit_that_never_landed_is_cleared_and_can_be_applied_again(self):
        saved=self.plan();gs.apply(self.client,self.root,saved);actual=self.client.native_update
        self.client.native_update=Mock(side_effect=gd.GoogleError('timeout'))
        with self.assertRaises(gd.GoogleError):review.apply_edits(self.client,self.root,saved,[1])
        self.assertEqual(review.verify_edits(self.client,self.root,saved)['status'],'not-applied')
        self.assertNotIn('edit_attempt',json.loads(review.path(self.root,saved).read_text()))
        self.client.native_update=actual
        self.assertEqual(review.apply_edits(self.client,self.root,saved,[1])['status'],'applied')
        self.assertEqual(self.client.writes,1)

    def test_edit_that_matches_neither_state_stays_blocked(self):
        saved=self.plan();gs.apply(self.client,self.root,saved)
        self.client.native_update=Mock(side_effect=gd.GoogleError('timeout'))
        with self.assertRaises(gd.GoogleError):review.apply_edits(self.client,self.root,saved,[1])
        blocks=self.client.doc['tabs'][0]['documentTab']['body']['content']
        blocks[3]['paragraph']['elements'][0]['textRun']['content']='Keep that link.\n'
        self.assertEqual(review.verify_edits(self.client,self.root,saved)['status'],'needs-reconciliation')
        self.assertIn('edit_attempt',json.loads(review.path(self.root,saved).read_text()))

    def test_google_change_after_rejection_stops_fallback(self):
        self.client.native_available=True
        def reject(*args):
            blocks=self.client.doc['tabs'][0]['documentTab']['body']['content']
            blocks[1]['paragraph']['paragraphStyle']['lineSpacing']=175
            raise gd.GoogleError('Denied',status=403,review_unavailable=True)
        self.client.native_review_update=reject
        saved=self.plan()
        with self.assertRaises(gd.GoogleError):gs.apply(self.client,self.root,saved)
        self.assertEqual(self.client.creates,0)
        # Nothing was posted, so the rejected native reservation does not strand these findings.
        self.assertFalse(review.path(self.root,saved).exists())
        self.assertEqual(list(gs.ledger(self.root).glob('*.finding')),[])

    def test_renaming_the_doc_or_tab_is_not_a_google_change(self):
        saved=self.plan()
        self.client.doc['title']='Renamed during review'
        self.assertEqual(gs.apply(self.client,self.root,saved)['status'],'verified-comments')
        # A renamed tab still matches the saved formatting baseline, so a later review can be planned.
        self.client.doc['tabs'][0]['tabProperties']['title']='Renamed tab'
        later=self.root/'after-rename.json'
        gs.plan(self.client,self.root,self.aid,'draft',[dict(self.findings()[2],id='later')],later)
        self.assertIn('Tab: Renamed tab',json.loads(later.read_text())['comment_plan']['comments'][0]['content'])
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
    def later_findings(self):
        start=self.client.doc['tabs'][0]['documentTab']['body']['content'][3]['startIndex']
        return [dict(id='later-1',kind='edit',tab_id='t.0',start_index=start,before='Keep',after='Retain',reason='Second batch.'),
                dict(id='later-2',kind='edit',tab_id='t.0',start_index=start+5,before='this',after='that',reason='Second batch again.')]

    def second_plan(self,findings=None,name='second.json'):
        path=self.root/name
        gs.plan(self.client,self.root,self.aid,'draft',findings or self.later_findings(),path)
        return json.loads(path.read_text())

    def test_review_numbers_continue_per_blog_and_every_batch_stays_reachable(self):
        first=self.plan();gs.apply(self.client,self.root,first)
        second=self.second_plan()
        self.assertEqual(second['number_start'],4)
        result=gs.apply(self.client,self.root,second)
        self.assertEqual([c['numbers'] for c in result['comments']],[[4],[5]])
        self.assertEqual([t['content'].split(' ·')[0] for t in self.client.drive_threads],
                         ['Edit 1','Edit 2','Edit 3','Edit 4','Edit 5'])
        shown=review.show(self.root,self.aid)
        self.assertEqual([e['number'] for e in shown['edits']],[1,2,3,4,5])
        self.assertEqual(len(shown['reviews']),2)
        self.assertNotEqual(shown['edits'][0]['plan'],shown['edits'][4]['plan'])
        # One request can name edits from both batches; each number means exactly one edit.
        outcome=review.apply_selected(self.client,self.root,self.aid,[1,4])
        self.assertEqual(outcome['status'],'applied');self.assertEqual(outcome['applied'],[1,4])
        self.assertEqual(review.show(self.root,self.aid)['applied'],[1,4])
        text=''.join(rt.paragraph_text(paragraph) for paragraph in rt.paragraphs(self.client.doc).values())
        self.assertEqual(text,'The wait is in handoffs.\n😀 This isn’t slow.\nRetain this link.\n')
        with self.assertRaisesRegex(gd.GoogleError,'Unknown edit'):review.apply_selected(self.client,self.root,self.aid,[9])

    def test_numbers_already_used_in_the_doc_or_by_an_earlier_plan_are_never_reused(self):
        # A comment posted from another computer already uses number 9.
        self.client.drive_threads=[{'id':'elsewhere','content':'Edit 9 · Opening\nTab: Blog\n[Blog Studio other-machine]'}]
        first=self.plan()
        self.assertEqual(first['number_start'],10)
        # Two plans made before either was posted would both start at 10; only the first may post.
        rival=self.second_plan(name='rival.json')
        self.assertEqual(rival['number_start'],10)
        gs.apply(self.client,self.root,first)
        with self.assertRaisesRegex(gd.GoogleError,'continue from 13'):gs.apply(self.client,self.root,rival)
        self.assertEqual(self.client.creates,3)
        self.assertEqual(self.second_plan(name='fresh.json')['number_start'],13)

    def test_teammate_suggestion_does_not_block_comments_or_edits_elsewhere(self):
        fixtures.add_teammate_suggestion(self.client)
        saved=self.plan([self.findings()[0],self.findings()[2]])
        result=gs.apply(self.client,self.root,saved)
        self.assertEqual(result['status'],'verified-comments');self.assertTrue(result['accepted_text_unchanged'])
        # Only the paragraph that carries the colleague's suggestion is off limits.
        with self.assertRaisesRegex(gd.GoogleError,'pending suggestion'):
            gs.plan(self.client,self.root,self.aid,'draft',[self.findings()[1]],self.root/'blocked.json')
        self.assertEqual(review.apply_edits(self.client,self.root,saved,[1])['status'],'applied')
        self.assertIn('teammate-1',json.dumps(self.client.doc))

    def test_cli_reports_a_busy_ledger_and_plain_input_mistakes_without_tracebacks(self):
        from hub_store import HubError
        self.plan()
        def run(*words,**patches):
            stderr=io.StringIO();stdout=io.StringIO()
            argv=['google_suggestions.py','--root',str(self.root),*words]
            with contextlib.ExitStack() as stack:
                stack.enter_context(patch.object(gs,'Client',return_value=self.client))
                stack.enter_context(patch.object(sys,'argv',argv))
                stack.enter_context(contextlib.redirect_stderr(stderr))
                stack.enter_context(contextlib.redirect_stdout(stdout))
                for target,value in patches.items():stack.enter_context(patch.object(review,target,value))
                code=gs.main()
            return code,(json.loads(stderr.getvalue())['error'] if code else json.loads(stdout.getvalue()))
        busy=Mock(side_effect=HubError('Another hub operation is running. Retry after it finishes.'))
        code,error=run('apply','--plan',str(self.root/'review-plan.json'),locked=busy)
        self.assertEqual(code,1);self.assertIn('busy',error);self.assertIn('run verify',error)
        self.assertEqual(self.client.creates,0)
        code,error=run('show-review','--id',self.aid)
        self.assertEqual(code,1);self.assertIn('No review comments',error)
        code,error=run('plan','--id',self.aid,'--findings',str(self.root/'missing.json'))
        self.assertEqual(code,1);self.assertIn('not found',error);self.assertNotIn('do not retry',error)
        # A posted review is listed, and numbered edits are applied by blog ID.
        code,result=run('apply','--plan',str(self.root/'review-plan.json'))
        self.assertEqual(code,0);self.assertEqual(result['status'],'verified-comments')
        code,result=run('apply-edits','--id',self.aid,'--numbers','1')
        self.assertEqual(code,0);self.assertEqual(result['status'],'applied')

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
