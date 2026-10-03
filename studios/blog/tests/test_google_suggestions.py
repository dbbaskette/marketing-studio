"""Native suggestions contract fixtures; no live credentials or external writes."""
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from test_google_roundtrip import Provider, document
import google_drive as gd
import google_roundtrip as rt
import google_workflow as gw
import google_suggestions as gs
import studio
import author_workflow


class ReviewProvider(Provider):
    """Retain suggested deletions inline; project accepted/rejected views separately."""
    def __init__(self):
        super().__init__(); self.comments=[]; self.anchors=[]; self.threads=[]
    def native_read(self, file_id, inline=False, comments=False, accepted_preview=False):
        doc=copy.deepcopy(self.doc)
        doc['suggestionsViewMode']='SUGGESTIONS_INLINE' if inline else 'PREVIEW_SUGGESTIONS_ACCEPTED' if accepted_preview else 'PREVIEW_WITHOUT_SUGGESTIONS'
        if not inline:
            start=1
            for block in doc['tabs'][0]['documentTab']['body']['content']:
                if 'paragraph' not in block:continue
                block['startIndex']=start; elements=[]
                for e in block['paragraph']['elements']:
                    run=e['textRun']
                    if run.get('suggestedDeletionIds') if accepted_preview else run.get('suggestedInsertionIds'):continue
                    run.pop('suggestedInsertionIds',None);run.pop('suggestedDeletionIds',None)
                    e['startIndex']=start;start+=rt.utf16(run['content']);e['endIndex']=start;elements.append(e)
                block['paragraph']['elements']=elements;block['endIndex']=start
        if comments:
            doc.update(commentsViewMode='COMMENTS_VIEW_MODE_INCLUDED',comments=copy.deepcopy(self.comments),suggestions=copy.deepcopy(self.threads))
            doc['tabs'][0]['documentTab']['commentAnchors']=copy.deepcopy(self.anchors)
        return doc
    def native_review_update(self,file_id,revision,requests):
        if self.doc['revisionId']!=revision:raise gd.GoogleError('stale revision')
        self.writes+=1
        blocks=self.doc['tabs'][0]['documentTab']['body']['content']
        for b in blocks:
            if 'paragraph' in b:
                b['paragraph']['elements']=[{'textRun':dict(copy.deepcopy(e['textRun']),content=c)} for e in b['paragraph']['elements'] for c in e['textRun']['content']]
        def reindex():
            start=1
            for b in blocks:
                if 'paragraph' not in b:continue
                b['startIndex']=start
                for e in b['paragraph']['elements']:
                    e['startIndex']=start;start+=rt.utf16(e['textRun']['content']);e['endIndex']=start
                b['endIndex']=start
        reindex()
        for req in requests:
            if 'insertComment' in req:
                c=req['insertComment'];r=c['range']; cid='c'+str(len(self.comments));aid='a'+cid
                quote=''.join(e['textRun']['content'] for b in blocks if 'paragraph' in b for e in b['paragraph']['elements'] if r['startIndex']<=e['startIndex']<r['endIndex'])
                self.comments.append({'commentId':cid,'anchorId':aid,'headPost':{'content':c['content']},'status':'OPEN','plainTextQuote':quote})
                self.anchors.append({'anchorId':aid,'ranges':[r]});continue
            if 'insertText' in req:
                x=req['insertText']; index=x['location']['index']
                for b in blocks:
                    if 'paragraph' not in b:continue
                    elements=b['paragraph']['elements']
                    found=next((i for i,e in enumerate(elements) if e['startIndex']==index),None)
                    if found is not None:
                        sid='s'+str(len(self.threads));self.threads.append({'suggestionId':sid,'status':'OPEN'})
                        elements[found:found]=[{'textRun':{'content':c,'textStyle':{},'suggestedInsertionIds':[sid]}} for c in x['text']]
                        break
                else:raise AssertionError(index)
                reindex();continue
            deletion='deleteContentRange' in req
            x=req['deleteContentRange' if deletion else 'updateTextStyle'];r=x['range']
            if deletion:
                sid='s'+str(len(self.threads));self.threads.append({'suggestionId':sid,'status':'OPEN'})
            for b in blocks:
                if 'paragraph' not in b:continue
                for e in b['paragraph']['elements']:
                    if r['startIndex']<=e['startIndex']<r['endIndex']:
                        if deletion:e['textRun']['suggestedDeletionIds']=[sid]
                        else:e['textRun']['textStyle']=copy.deepcopy(x['textStyle'])
        self.doc['revisionId']='r2';self.version='2'
        return {'commentUpdateState':'ALL_SAVED'}


class SuggestionsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)/'work';studio.initialize(self.root);self.client=ReviewProvider()
        args=studio.parser().parse_args(['--root',str(self.root),'article','create','--title','Review fixture','--mode','existing'])
        self.aid=studio.article_command(self.root,args)['id']
        self.directory,self.record=studio.item(self.root,'articles',self.aid)
        (self.directory/'DRAFT.md').write_text('Saved unchanged draft.\n')
        self.record['google']={'schema':1,'transfers':{},'baselines':{'draft':{'local_sha256':gd.digest(b'Saved unchanged draft.\n'),'document':{'document_id':'fixture-doc','url':'https://docs.google.com/document/d/fixture-doc/edit','tab_ids':['t.0'],'format_sha256':gs.signature(self.client.doc)}}}}
        studio.persist(self.directory,'articles',self.record)
    def findings(self):
        blocks=self.client.doc['tabs'][0]['documentTab']['body']['content']
        return [dict(id='proof-1',kind='edit',tab_id='t.0',start_index=5,before='delay',after='wait',reason='Use a plainer word.'),
                dict(id='proof-2',kind='edit',tab_id='t.0',start_index=blocks[2]['startIndex']+8,before='isn’t',after='is not',reason='Requested formal voice.'),
                dict(id='proof-3',kind='comment',tab_id='t.0',start_index=blocks[3]['startIndex'],before='Keep',reason='Check the cited source.')]
    def plan(self,findings=None):
        path=self.root/'review-plan.json'
        gs.plan(self.client,self.root,self.aid,'draft',findings or self.findings(),path)
        return json.loads(path.read_text())
    def test_suggestions_keep_accepted_text_and_formatting_and_verify_anchors(self):
        old=gs.signature(self.client.doc); saved=self.plan();result=gs.apply(self.client,self.root,saved)
        self.assertEqual(result['status'],'verified-pending');self.assertTrue(result['accepted_text_unchanged'])
        self.assertEqual(gs.signature(self.client.native_read('fixture-doc')),old)
        self.assertEqual(gs.signature(self.client.native_read('fixture-doc',accepted_preview=True)),saved['expected_sha256'])
        self.assertEqual(len(result['comments']),3);self.assertEqual(self.client.writes,1)
        self.assertEqual((self.directory/'DRAFT.md').read_text(),'Saved unchanged draft.\n')
        with self.assertRaises(gd.GoogleError):gs.apply(self.client,self.root,saved)
        self.assertEqual(self.client.writes,1)
    def test_changed_google_or_local_and_tampered_requests_block_writes(self):
        saved=self.plan();self.client.doc['revisionId']='new'
        with self.assertRaises(gd.GoogleError):gs.apply(self.client,self.root,saved)
        self.client.doc['revisionId']='r1';bad=copy.deepcopy(saved);bad['requests'].append({'deleteContentRange':{}})
        with self.assertRaises(gd.GoogleError):gs.apply(self.client,self.root,bad)
        (self.directory/'DRAFT.md').write_text('Local changed')
        with self.assertRaises(gd.GoogleError):gs.apply(self.client,self.root,saved)
        self.assertEqual(self.client.writes,0)
    def test_fresh_read_requires_pull_when_only_formatting_changes(self):
        self.client.doc['tabs'][0]['documentTab']['body']['content'][1]['paragraph']['paragraphStyle']['lineSpacing']=222
        with self.assertRaisesRegex(gd.GoogleError,'Pull the latest'):self.plan()
        self.assertEqual(self.client.writes,0)
    def test_stale_quotes_overlaps_and_unicode_splits_are_refused(self):
        for changed in ({'before':'missing'},{'start_index':-1},{'kind':'wrong'}):
            f=self.findings();f[0].update(changed)
            with self.assertRaises(gd.GoogleError):gs.build(self.client.doc,f,['t.0'])
        f=self.findings();f.append({**f[0],'id':'overlap'})
        with self.assertRaisesRegex(gd.GoogleError,'Overlapping'):gs.build(self.client.doc,f,['t.0'])
        f=self.findings();f[1].update(start_index=self.client.doc['tabs'][0]['documentTab']['body']['content'][2]['startIndex']+1)
        with self.assertRaises(gd.GoogleError):gs.build(self.client.doc,f,['t.0'])
    def test_uncertain_submission_reserves_attempt_and_never_retries(self):
        saved=self.plan();write=self.client.native_review_update
        def timeout(*args):write(*args);raise gd.GoogleError('timeout')
        self.client.native_review_update=timeout
        with self.assertRaises(gd.GoogleError):gs.apply(self.client,self.root,saved)
        with self.assertRaises(gd.GoogleError):gs.apply(self.client,self.root,saved)
        self.assertEqual(gs.verify(self.client,self.root,saved)['status'],'needs-reconciliation')
        self.assertEqual(self.client.writes,1)
    def test_partial_comments_and_wrong_anchors_fail_verification(self):
        saved=self.plan();gs.apply(self.client,self.root,saved)
        self.client.anchors[0]['ranges'][0]={**self.client.anchors[0]['ranges'][0],'startIndex':1}
        self.assertEqual(gs.verify(self.client,self.root,saved)['status'],'needs-reconciliation')
        self.client.comments=[]
        self.assertEqual(gs.verify(self.client,self.root,saved)['status'],'needs-reconciliation')
    def test_comment_only_needs_no_suggested_text_changes(self):
        saved=self.plan([self.findings()[2]])
        self.assertEqual(gs.apply(self.client,self.root,saved)['status'],'verified-pending')
        self.assertEqual(self.client.threads,[])
    def test_review_pull_separates_pending_text_and_preserves_docx_and_threads(self):
        saved=self.plan();gs.apply(self.client,self.root,saved)
        output=self.root/'snapshot';rt.capture(self.client,'fixture-doc','t.0',output,include_review=True)
        body=(output/'document.md').read_text();obs=json.loads((output/'observation.json').read_text())
        self.assertIn('isn’t',body);self.assertNotIn('is not',body)
        self.assertEqual(obs['suggestions'],'excluded');self.assertGreater(obs['review_state']['pending'],0)
        self.assertIn('accepted.json',gw.formatted_snapshot(output,obs,body))
        native=json.loads((output/'native.json').read_text());self.assertEqual(len(native['comments']),3)
        obs['review_state']['pending']=0
        with self.assertRaises(ValueError):gw.formatted_snapshot(output,obs,body)
    def test_review_pull_blocks_races_unsupported_structures_and_multiple_tabs(self):
        self.client.metadata=Mock(side_effect=[{'version':'1'},{'version':'2'}])
        with self.assertRaises(gd.GoogleError):rt.capture(self.client,'fixture-doc','t.0',self.root/'race',include_review=True)
        self.assertFalse((self.root/'race').exists())
        doc=self.client.native_read('fixture-doc');doc['tabs'][0]['documentTab']['body']['content'].append({'table':{}})
        with self.assertRaises(gd.GoogleError):gs.accepted_markdown(doc)
        doc=self.client.native_read('fixture-doc');doc['tabs'].append(copy.deepcopy(doc['tabs'][0]))
        with self.assertRaises(gd.GoogleError):gs.accepted_markdown(doc)
    def test_pulled_pending_snapshot_enters_checkpoint_and_keeps_local_conflicts(self):
        from test_google_workflow import GoogleWorkflowTests
        fixture=GoogleWorkflowTests('runTest');fixture.setUp();self.addCleanup(fixture.temp.cleanup)
        body=gs.accepted_markdown(self.client.native_read('fixture-doc')).decode()
        fixture.save('draft',body);fixture.handoff()
        saved=self.plan();gs.apply(self.client,self.root,saved)
        out=self.root/'pull';rt.capture(self.client,'fixture-doc','t.0',out,include_review=True)
        inputs=['--observation',str(out/'observation.json'),'--file',str(out/'document.md')]
        compare=fixture.run_command('google','compare','--id',fixture.aid,*inputs)
        self.assertEqual(compare['status'],'unchanged')
        result=fixture.run_command('google','accept','--id',fixture.aid,*inputs,'--snapshot',str(out),'--expected-comparison',compare['comparison'])
        self.assertIn('accepted.json',result['formatted_snapshot'])
        self.assertEqual(fixture.body(),body)
        directory,record=studio.item(fixture.root,'articles',fixture.aid)
        self.assertGreater(record['google']['baselines']['draft']['document']['review_state']['pending'],0)
        from hub_workspace import Workspace
        self.assertTrue(any(name.endswith('-accepted.json') for name in Workspace.__new__(Workspace).read_artifacts(directory,'articles')))
        fixture.save('draft','Unsent local work.')
        compare=fixture.run_command('google','compare','--id',fixture.aid,*inputs)
        with self.assertRaises(ValueError):
            fixture.run_command('google','accept','--id',fixture.aid,*inputs,'--snapshot',str(out),'--expected-comparison',compare['comparison'])
        self.assertEqual(fixture.body(),'Unsent local work.')
    def test_deleted_text_and_multiple_same_paragraph_edits(self):
        f=self.findings()[:1];f[0]['after']=''
        f.append(dict(id='second',kind='edit',tab_id='t.0',start_index=17,before='handoffs',after='coordination',reason='Clarify.'))
        saved=self.plan(f)
        self.assertEqual(gs.apply(self.client,self.root,saved)['status'],'verified-pending')
    def test_existing_comment_prevents_duplicate_on_another_machine(self):
        self.client.comments=[{'headPost':{'content':'[Blog Studio proof-1] Earlier finding.'},'status':'RESOLVED'}]
        with self.assertRaisesRegex(gd.GoogleError,'already has'):self.plan()
        self.assertEqual(self.client.writes,0)
    def test_fragmented_runs_project_same_markdown_and_omit_pending(self):
        original=self.client.native_read('fixture-doc');before=gs.accepted_markdown(original)
        for b in original['tabs'][0]['documentTab']['body']['content']:
            if 'paragraph' not in b:continue
            b['paragraph']['elements']=[{'textRun':{**e['textRun'],'content':c}} for e in b['paragraph']['elements'] for c in e['textRun']['content']]
        self.assertEqual(gs.accepted_markdown(original),before)
    def test_partial_response_even_with_complete_readback_stays_unverified(self):
        saved=self.plan();write=self.client.native_review_update
        def partial(*args):write(*args);return {'commentUpdateState':'ALL_FAILED_UNKNOWN_REASON'}
        self.client.native_review_update=partial
        self.assertEqual(gs.apply(self.client,self.root,saved)['status'],'needs-reconciliation')
        self.assertEqual(self.client.writes,1)

    def test_markdown_style_boundaries_preserve_whitespace_outside_delimiters(self):
        doc=self.client.native_read('fixture-doc')
        p=doc['tabs'][0]['documentTab']['body']['content'][1]['paragraph']
        p['elements']=[{'textRun':{'content':'  Bold space \n','textStyle':{'bold':True}}}]
        self.assertTrue(gs.accepted_markdown(doc).decode().startswith('##   **Bold space** \n'))
        p['elements'][0]['textRun']['content']='Line one\nLine two\n'
        with self.assertRaises(gd.GoogleError):gs.accepted_markdown(doc)

    def test_online_status_distinguishes_pending_review_from_in_sync(self):
        saved=self.plan();gs.apply(self.client,self.root,saved)
        with patch('google_drive.Client',return_value=self.client):
            result=gw.sync_status(self.root,self.directory,self.record,online=True)
        self.assertEqual(result['status'],'pending-review')
        self.assertGreater(result['review_state']['pending'],0)

    def test_provider_contract_uses_suggest_and_required_revision(self):
        client=gd.Client.__new__(gd.Client);client.request=Mock(return_value={})
        client.native_review_update('fixture-doc','r1',[{'insertComment':{}}])
        self.assertEqual(client.request.call_args.kwargs['body']['writeControl'],{'requiredRevisionId':'r1','writeMode':'SUGGEST'})
        client.native_read('fixture-doc',inline=True,comments=True)
        self.assertIn('commentsViewMode=COMMENTS_VIEW_MODE_INCLUDED',client.request.call_args.args[0])
        self.assertIn('includeTabsContent=true',client.request.call_args.args[0])
    def test_short_command_routes_only_explicit_suggestions(self):
        route=author_workflow.route(self.root,'Push these as suggestions to Google Docs',self.aid)
        self.assertEqual(route['actions'],['google-suggest'])
        self.assertEqual(author_workflow.route(self.root,'Push to Google Docs',self.aid)['actions'],['google-push'])


if __name__=='__main__':unittest.main()
