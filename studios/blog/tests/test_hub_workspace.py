"""Team writing handoff using disposable homes and Git repositories."""
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout

from hub_fixtures import FakeProvider
from hub import Registry
from hub_store import HubError, encoded, sha
from hub_workspace import Workspace
import hub_workspace as adapter_module
import studio

class HubWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        provider = FakeProvider(self.base/'remotes')
        self.ra = Registry(self.base/'a-hubs', provider);self.rb = Registry(self.base/'b-hubs', provider)
        self.id = self.ra.create('fixture/writing', 'Writing')['hub'];self.rb.join('fixture/writing')
        self.ha = self.ra.hub(self.id);self.hb = self.rb.hub(self.id)
        self.a = self.base/'author-a';self.b = self.base/'author-b'
        studio.initialize(self.a);studio.initialize(self.b)
        self.wa = Workspace(self.a,self.ha);self.wb = Workspace(self.b,self.hb)
        self.number = 0

    def file(self, text, suffix='.md'):
        self.number+=1;p=self.base/('input'+str(self.number)+suffix);p.write_text(text);return str(p)

    def command(self, root, *words):
        args=studio.parser().parse_args(['--root',str(root),*words])
        with studio.locked(root):
            return getattr(studio,args.group+'_command')(root,args)

    def article(self, root=None, mode='first-draft', profile=None):
        words=['article','create','--title','Writing handoffs','--mode',mode]
        if profile:words+=['--profile',profile]
        return self.command(root or self.a,*words)['id']

    def save(self, root, aid, kind, body):
        return self.command(root,'article','save','--id',aid,'--kind',kind,'--file',self.file(body))

    def export(self, aid):
        result=self.wa.publish_selected({'articles':[aid]})
        self.assertEqual(result['status'],'shared')
        return result['items'][0]

    def checkout(self, reference, workspace=None):
        return (workspace or self.wb).checkout_selected({'articles':[reference['item']]})['items'][0]['local_id']

    def test_hub_saved_timestamp_requires_remote_confirmation_and_does_not_drift(self):
        aid=self.article();self.save(self.a,aid,'draft','First version.')
        self.assertEqual(self.wa.publish_selected({'articles':[aid]},offline=True)['status'],'queued-offline')
        key='articles/'+aid
        self.assertNotIn('last_saved_to_hub',self.wa.state['items'][key])
        ref=self.export(aid)
        first=dict(self.wa.state['items'][key])
        self.assertTrue(first['last_saved_to_hub'])
        self.assertEqual(first['last_saved_revision'],ref['revision'])
        self.assertEqual(self.wa.publish_selected({'articles':[aid]})['status'],'synchronized')
        self.assertEqual(first,self.wa.state['items'][key])
        bid=self.checkout(ref)
        self.assertTrue(self.wb.state['items']['articles/'+bid]['last_saved_to_hub'])
        self.save(self.a,aid,'draft','Second version.')
        self.wa.publish_selected({'articles':[aid]},offline=True)
        pending=self.wa.state['items'][key]
        self.assertEqual(pending['last_saved_revision'],first['revision'])
        self.assertEqual(pending['last_saved_to_hub'],first['last_saved_to_hub'])
        self.assertNotEqual(pending['revision'],first['revision'])
        self.export(aid)
        self.assertNotEqual(self.wa.state['items'][key]['last_saved_revision'],first['revision'])
        confirmed = dict(self.wa.state['items'][key])
        self.ha.registry.provider.review = True
        self.save(self.a,aid,'draft','Review-required version.')
        self.assertEqual(self.wa.publish_selected({'articles':[aid]})['status'],'pending-review')
        self.assertEqual(self.wa.state['items'][key]['last_saved_to_hub'],confirmed['last_saved_to_hub'])
        import experience
        status = experience.context(self.a,aid)['google_sync']
        self.assertEqual(status['last_saved_to_hub'],confirmed['last_saved_to_hub'])
        self.assertEqual(status['hub_saved_revision'],confirmed['last_saved_revision'])

    def test_original_author_resumes_other_member_edit_without_duplicate_blog(self):
        aid = self.article();self.save(self.a, aid, 'original', 'Original manuscript.')
        self.save(self.a, aid, 'draft', 'Shared draft.')
        ref = self.export(aid);bid = self.checkout(ref)
        self.save(self.b, bid, 'draft', 'Other member edit.')
        self.wb.publish_selected({'articles': [bid]})
        resumed = self.wa.checkout_selected({'articles': [ref['item']]})['items'][0]
        self.assertEqual(resumed['local_id'], aid)
        self.assertEqual((self.a / 'articles' / aid / 'DRAFT.md').read_text(), 'Other member edit.')
        self.assertEqual((self.a / 'articles' / aid / 'ORIGINAL.md').read_text(), 'Original manuscript.')
        self.assertEqual(len(list((self.a / 'articles').iterdir())), 1)
        # A changed shared head cannot erase an unshared local edit.
        (self.a / 'articles' / aid / 'DRAFT.md').write_text('Unsaved local edit.')
        self.save(self.b, bid, 'draft', 'New shared edit.')
        self.wb.publish_selected({'articles': [bid]})
        with self.assertRaisesRegex(HubError, 'unshared local edits'):
            self.wa.checkout_selected({'articles': [ref['item']]})
        self.assertEqual((self.a / 'articles' / aid / 'DRAFT.md').read_text(), 'Unsaved local edit.')

    def test_cross_machine_dependencies_original_review_checkpoint_and_portable_guidance(self):
        source=self.command(self.a,'source','add','--name','Evidence','--file',self.file('Observed facts.'),'--purpose','reference','--purpose','voice-sample')['id']
        profile=self.command(self.a,'profile','create','--name','Author','--guide-file',self.file('Write plainly.'),'--sample',source)['id']
        aid=self.article(mode='existing',profile=profile)
        self.command(self.a,'article','attach','--id',aid,'--source',source)
        self.save(self.a,aid,'original','Original manuscript.');self.save(self.a,aid,'draft','Edited manuscript.')
        self.command(self.a,'article','note','--id',aid,'--kind','interview','--text','An actual example.')
        self.command(self.a,'article','derive','--id',aid,'--name','newsletter','--file',self.file('Newsletter copy.'))
        task='a'*32;pin=self.a/'task-context/tasks'/task/'pin.json';pin.parent.mkdir(parents=True);pin.write_text(json.dumps({'task':task,'revision':'a'*40}))
        self.command(self.a,'article','guidance','--id',aid,'--task',task)
        for check in ('proofread','factual-support'):
            self.command(self.a,'article','review','--id',aid,'--check',check,'--status','current','--file',self.file('{"findings":[]}', '.json'))
        ref=self.export(aid);bid=self.checkout(ref)
        shown=self.command(self.b,'article','show','--id',bid)
        self.assertEqual(shown['stop_point'],'review')
        self.assertEqual(shown['reviews']['proofread']['status'],'current')
        self.assertEqual(shown['reviews']['factual-support']['status'],'current')
        self.assertEqual(shown['guidance']['revision'],'a'*40);self.assertIsNone(shown['guidance']['task'])
        folder=self.b/'articles'/bid
        self.assertEqual((folder/'ORIGINAL.md').read_text(),'Original manuscript.')
        self.assertEqual((folder/'derived/newsletter.md').read_text(),'Newsletter copy.')
        self.assertIn('actual example',(folder/'INTERVIEW.md').read_text())
        global_record=self.ha.read(ref['item'])['record'];text=json.dumps(global_record)
        self.assertNotIn(str(self.a),text);self.assertNotIn('runtime',text);self.assertNotIn(source,text)
        before=len(self.hb.graph()['revisions']);self.wb.publish_selected({'articles':[bid]})
        self.assertEqual(len(self.hb.graph()['revisions']),before)
        task2='b'*32;pin=self.b/'task-context/tasks'/task2/'pin.json';pin.parent.mkdir(parents=True);pin.write_text(json.dumps({'task':task2,'revision':'a'*40}))
        self.command(self.b,'article','guidance','--id',bid,'--task',task2)
        self.assertEqual(self.command(self.b,'article','show','--id',bid)['reviews']['proofread']['status'],'current')

    def test_article_memory_round_trip_and_retirement_keep_history(self):
        aid=self.article();self.save(self.a,aid,'draft','A preserved draft.')
        self.command(self.a,'article','remember','--id',aid,'--key','headings','--file',self.file('Use short headings.'))
        ref=self.export(aid);bid=self.checkout(ref)
        shown=self.command(self.b,'article','show','--id',bid)
        self.assertEqual(shown['memory']['headings']['text'],'Use short headings.')
        self.command(self.b,'article','remember','--id',bid,'--key','headings','--file',self.file('Use descriptive headings.'))
        self.command(self.b,'article','forget','--id',bid,'--key','headings')
        self.wb.publish_selected({'articles':[bid]})
        self.ha.refresh()
        shared=self.ha.read(ref['item'])['record']['data']['studio']
        self.assertEqual(shared['memory']['headings']['status'],'forgotten')
        self.assertEqual(shared['memory']['headings']['history'][0]['text'],'Use short headings.')
        self.assertEqual((self.b/'articles'/bid/'DRAFT.md').read_text(),'A preserved draft.')

    def test_clean_projection_resumes_new_shared_head_and_keeps_prior_folder(self):
        aid=self.article();self.save(self.a,aid,'draft','Initial draft.')
        ref=self.export(aid);bid=self.checkout(ref)
        c=self.base/'author-c';studio.initialize(c);wc=Workspace(c,self.hb);cid=self.checkout(ref,wc)
        self.save(self.b,bid,'draft','Updated draft.');self.wb.publish_selected({'articles':[bid]})
        self.checkout(ref,wc)
        self.assertEqual((c/'articles'/cid/'DRAFT.md').read_text(),'Updated draft.')
        self.assertEqual((c/'.hub-history'/cid/ref['revision']/'DRAFT.md').read_text(),'Initial draft.')

    def test_dirty_projection_is_preserved_when_shared_head_changes(self):
        aid=self.article();self.save(self.a,aid,'draft','Initial draft.')
        ref=self.export(aid);bid=self.checkout(ref)
        self.save(self.b,bid,'draft','Unshared local edits.')
        self.save(self.a,aid,'draft','Other author changes.');self.export(aid)
        with self.assertRaisesRegex(HubError,'unshared local edits'):self.checkout(ref)
        self.assertEqual((self.b/'articles'/bid/'DRAFT.md').read_text(),'Unshared local edits.')

    def test_same_baseline_writers_create_visible_conflict(self):
        aid=self.article();self.save(self.a,aid,'draft','Initial draft.')
        ref=self.export(aid);bid=self.checkout(ref)
        self.save(self.a,aid,'draft','A changes.');self.export(aid)
        self.save(self.b,bid,'draft','B changes.');self.wb.publish_selected({'articles':[bid]})
        self.assertEqual(self.hb.status()['conflicts'],1)
        self.assertEqual(len(self.hb.graph()['heads'][ref['item']]),2)

    def test_all_six_entry_paths_keep_checkpoints_and_stops(self):
        for mode, stop in [('existing','review'),('first-draft','draft'),('outline-only','outline'),('from-outline','draft'),('interview','outline'),('discover','brief')]:
            aid=self.article(mode=mode)
            self.command(self.a,'article','progress','--id',aid,'--stage','intake','--next-step','Continue intake','--pending-question','Who is the reader?')
            ref=self.export(aid);bid=self.checkout(ref)
            record=self.command(self.b,'article','show','--id',bid)
            self.assertEqual(record['stop_point'],stop);self.assertEqual(record['pending_question'],'Who is the reader?')
            if mode=='outline-only':
                with self.assertRaisesRegex(ValueError,'stops before drafting'):self.save(self.b,bid,'draft','A draft.')

    def test_migration_only_shares_selected_item_and_dependencies(self):
        selected=self.article();other=self.article()
        (self.a/'articles'/selected/'credentials.json').write_text('DO NOT SHARE CREDENTIALS')
        (self.a/'articles'/selected/'.cache').mkdir();(self.a/'articles'/selected/'.cache/private.md').write_text('DO NOT SHARE CACHE')
        self.save(self.a,selected,'draft','Selected.');self.save(self.a,other,'draft','Private unrelated draft.')
        self.export(selected)
        self.assertEqual(self.ha.find(kind='article')['total'],1)
        shared=b''.join(self.ha.files().values())
        self.assertNotIn(b'Private unrelated draft.',shared)
        self.assertNotIn(b'DO NOT SHARE',shared)

    def test_old_voice_revision_remains_pinned_across_handoff(self):
        profile=self.command(self.a,'profile','create','--name','Author','--guide-file',self.file('Original voice.'))['id']
        aid=self.article(profile=profile)
        self.command(self.a,'profile','save','--id',profile,'--guide-file',self.file('Newer voice.'))
        ref=self.export(aid);bid=self.checkout(ref)
        record=self.command(self.b,'article','show','--id',bid)
        guide=self.command(self.b,'profile','show','--id',record['voice']['profile_id'],'--revision','1')['guide']
        self.assertEqual(Path(guide).read_text(),'Original voice.')

    def test_context_adoption_stales_reviews_without_unrelated_hub_churn(self):
        aid=self.article();self.save(self.a,aid,'draft','An article.')
        self.command(self.a,'article','review','--id',aid,'--check','proofread','--status','current','--file',self.file('{"findings":[]}', '.json'))
        rule=self.ha.save('rule','Style','Use sentence case.',data={'key':'headings'})
        context=self.ha.context();self.ra.select(self.id,self.a)
        with patch.object(adapter_module,'active',return_value=self.wa):
            self.command(self.a,'article','context','--id',aid,'--file',self.file(json.dumps(context),'.json'))
        self.assertEqual(self.command(self.a,'article','show','--id',aid)['reviews']['proofread']['status'],'stale')
        self.command(self.a,'article','review','--id',aid,'--check','proofread','--status','current','--file',self.file('{"findings":[]}', '.json'))
        self.ha.save('note','Unrelated','A note.')
        self.assertEqual(self.command(self.a,'article','show','--id',aid)['reviews']['proofread']['status'],'current')
        ref=self.export(aid);bid=self.checkout(ref)
        self.assertEqual(self.command(self.b,'article','show','--id',bid)['hub_context']['selected'][0]['revision'],rule['revision'])

    def test_auto_save_reports_offline_queue_and_configuration_errors_preserve_local(self):
        aid=self.article();self.ra.provider.unavailable=True
        output=io.StringIO()
        args=['studio','--root',str(self.a),'article','save','--id',aid,'--kind','draft','--file',self.file('Offline draft.')]
        with patch.object(sys,'argv',args),patch.object(adapter_module,'active',return_value=self.wa),redirect_stdout(output):
            self.assertEqual(studio.main(),0)
        self.assertEqual(json.loads(output.getvalue())['hub_sync']['status'],'queued-unavailable')
        self.assertEqual(self.ha.status()['queued'],1)
        output=io.StringIO()
        with patch.object(sys,'argv',args),patch.object(adapter_module,'active',side_effect=HubError('Invalid hub selection')),redirect_stdout(output):
            self.assertEqual(studio.main(),0)
        self.assertEqual(json.loads(output.getvalue())['hub_sync']['status'],'local-saved-not-shared')
        self.assertEqual((self.a/'articles'/aid/'DRAFT.md').read_text(),'Offline draft.')

    def test_enqueue_crash_before_mapping_recovers_same_operation(self):
        aid=self.article();self.save(self.a,aid,'draft','Durable content.')
        with patch.object(self.wa,'persist',side_effect=OSError('Fixture crash')):
            with self.assertRaises(OSError):self.wa.publish_selected({'articles':[aid]},offline=True)
        recovered=Workspace(self.a,self.ha);recovered.publish_selected({'articles':[aid]},offline=True)
        self.assertEqual(len(self.ha.graph()['revisions']),1)

    def test_failed_projection_does_not_leave_partial_article_and_can_retry(self):
        aid=self.article();self.save(self.a,aid,'draft','Shared draft.')
        ref=self.export(aid)
        real=adapter_module.atomic
        def fail(path,data):
            if path.name=='DRAFT.md':raise OSError('Fixture write failure')
            return real(path,data)
        with patch.object(adapter_module,'atomic',side_effect=fail):
            with self.assertRaises(OSError):self.checkout(ref)
        self.assertEqual(list((self.b/'articles').iterdir()),[])
        self.assertFalse(list(self.b.glob('.hub-projection-*')))
        bid=self.checkout(ref);self.assertEqual((self.b/'articles'/bid/'DRAFT.md').read_text(),'Shared draft.')

    def test_inconsistent_portable_draft_is_rejected_without_projection(self):
        aid=self.article();self.save(self.a,aid,'draft','Original shared draft.')
        ref=self.export(aid);read=self.ha.read(ref['item']);record=read['record']
        artifacts={name[10:]:(Path(path).read_bytes(),record['files'][name]['media']) for name,path in read['paths'].items() if name.startswith('artifacts/')}
        bad=self.ha.save('article',record['title'],'Different canonical body.',item=ref['item'],data=record['data'],dependencies=record['dependencies'],artifacts=artifacts)
        with self.assertRaisesRegex(HubError,'body and draft disagree'):self.checkout(bad)
        self.assertEqual(list((self.b/'articles').iterdir()),[])

    def test_projection_mapping_crash_preserves_later_unshared_edits(self):
        aid=self.article();self.save(self.a,aid,'draft','Shared draft.')
        ref=self.export(aid)
        with patch.object(self.wb,'persist',side_effect=OSError('Mapping interrupted')):
            with self.assertRaises(OSError):self.checkout(ref)
        bid='hub-'+ref['item']
        (self.b/'articles'/bid/'DRAFT.md').write_text('Edits after interruption.')
        self.wb=Workspace(self.b,self.hb);self.checkout(ref)
        self.save(self.a,aid,'draft','Another shared revision.');self.export(aid)
        with self.assertRaisesRegex(HubError,'unshared local edits'):self.checkout(ref)
        self.assertEqual((self.b/'articles'/bid/'DRAFT.md').read_text(),'Edits after interruption.')

    def test_complete_article_conflict_resolution_retains_original_and_resumes(self):
        aid=self.article(mode='existing');self.save(self.a,aid,'original','Original.')
        self.save(self.a,aid,'draft','Initial.');ref=self.export(aid);bid=self.checkout(ref)
        self.save(self.a,aid,'draft','A edit.');a=self.export(aid)
        self.save(self.b,bid,'draft','B edit.');self.wb.publish_selected({'articles':[bid]})
        self.ha.refresh();graph=self.ha.graph();heads=graph['heads'][ref['item']]
        chosen=self.ha.read(ref['item'],a['revision']);record=chosen['record']
        artifacts={name[10:]:(Path(path).read_bytes(),record['files'][name]['media']) for name,path in chosen['paths'].items() if name.startswith('artifacts/')}
        artifacts['DRAFT.md']=(b'Merged author choice.','text')
        data=record['data'];data['studio']['reviews']={}
        resolved=self.ha.save('article',record['title'],'Merged author choice.',item=ref['item'],parents=heads,data=data,dependencies=record['dependencies'],artifacts=artifacts)
        root=self.base/'resolved';studio.initialize(root);wc=Workspace(root,self.hb)
        cid=self.checkout(resolved,wc)
        self.assertEqual((root/'articles'/cid/'ORIGINAL.md').read_text(),'Original.')
        self.assertEqual((root/'articles'/cid/'DRAFT.md').read_text(),'Merged author choice.')
        self.assertEqual(self.ha.status()['conflicts'],0)
        self.assertEqual(set(self.ha.read(ref['item'])['record']['parents']),set(heads))

    def test_unavailable_and_inspiration_sources_do_not_become_evidence(self):
        aid=self.article();self.save(self.a,aid,'draft','A claim.')
        source=self.command(self.a,'source','add','--name','Inspiration','--file',self.file('Inspiration only.'),'--purpose','inspiration')['id']
        self.command(self.a,'article','attach','--id',aid,'--source',source)
        self.command(self.a,'article','review','--id',aid,'--check','factual-support','--status','current','--file',self.file('{"findings":[]}', '.json'))
        ref=self.export(aid);bid=self.checkout(ref)
        self.assertEqual(self.command(self.b,'article','show','--id',bid)['reviews']['factual-support']['status'],'unavailable')

if __name__=='__main__':unittest.main()
