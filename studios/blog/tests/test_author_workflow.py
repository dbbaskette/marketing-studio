"""Epic 27 observable workflow invariants; disposable files and local Git only."""
import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from hub_fixtures import SCRIPTS, FakeProvider, Registry
import studio
import author_workflow as flow
import writing_defaults as defaults
from hub_workspace import Workspace


class AuthorWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve();self.root = self.base / 'writing'
        studio.initialize(self.root)
        self.count = 0

    def args(self, *words):
        return studio.parser().parse_args(['--root', str(self.root), *words])

    def article(self, title='Example', **options):
        words = ['article', 'create', '--title', title, '--mode', options.pop('mode', 'first-draft')]
        for key, value in options.items(): words += ['--'+key.replace('_','-'), value]
        return studio.article_command(self.root, self.args(*words))['id']

    def file(self, text):
        self.count += 1;p = self.base / f'input-{self.count}.md';p.write_text(text);return str(p)

    def save(self, aid, body, label='save'):
        return studio.article_command(self.root, self.args('article','save','--id',aid,'--kind','draft','--file',self.file(body),'--label',label))

    def default(self, action, key, value=None, scope='personal'):
        words=['defaults',action,'--scope',scope,'--key',key]
        if value is not None: words += ['--value', value if isinstance(value,str) else json.dumps(value)]
        return defaults.command(self.root, self.args(*words))

    def test_short_routes_compounds_and_ambiguity(self):
        self.assertEqual(flow.route(self.root,'Proofread')['status'],'choose-article')
        a=self.article();b=self.article()
        self.assertEqual(flow.route(self.root,'Proofread')['id'],b)
        self.assertEqual(flow.route(self.root,'Continue Example')['status'],'choose-article')
        self.assertEqual(flow.route(self.root,'Push')['status'],'needs-destination')
        self.assertEqual(flow.route(self.root,'Push',a,'google')['actions'],['google-push'])
        self.assertEqual(flow.route(self.root,'Pull',a,'hub')['actions'],['hub-refresh'])
        route=flow.route(self.root,'Pull and proofread',a)
        self.assertEqual(route['actions'],['google-pull','proofread'])
        self.assertNotIn('google-push',route['actions'])
        self.assertEqual(flow.route(self.root,'Show my defaults')['actions'],['defaults-show'])
        self.assertEqual(flow.route(self.root,'delete all blogs')['status'],'interpret-request')
        for name in route['references']: self.assertTrue((SCRIPTS.parent/name).is_file())
        # Routing and status do not create a manuscript or publish anything.
        self.assertFalse((self.root/'articles'/a/'DRAFT.md').exists())

    def test_status_before_init_and_local_save_evidence(self):
        missing=self.base/'new'
        self.assertEqual(flow.status(missing)['status'],'choose-article');self.assertFalse(missing.exists())
        a=self.article();self.save(a,'A draft.')
        value=flow.status(self.root,a)
        self.assertEqual(value['local'],'saved');self.assertEqual(value['hub']['status'],'local-only')
        self.assertEqual(value['google']['label'],'Not linked')
        self.assertNotIn('details',value)
        (self.root/'articles'/a/'DRAFT.md').write_text('An external edit.')
        self.assertEqual(flow.status(self.root,a)['local'],'uncheckpointed-changes')
        result=subprocess.run([sys.executable,str(SCRIPTS/'studio.py'),'--root',str(self.root),'status','--format','markdown'],capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr);self.assertIn('**Example**',result.stdout)

    def test_defaults_precedence_reset_and_existing_pins(self):
        self.default('set','author','Alex');self.default('set','audience','Engineers')
        self.default('set','blog_type','tutorial')
        a=self.article(author='Sam');_,record=studio.item(self.root,'articles',a)
        self.assertEqual(record['author'],'Sam')
        self.assertEqual(record['writing_preferences']['audience'],'Engineers')
        self.default('set','audience','Managers')
        self.assertEqual(defaults.resolve(self.root,record)['values']['audience'],{'scope':'article','value':'Engineers'})
        self.assertEqual(defaults.resolve(self.root,record,{'audience':'Architects'})['values']['audience']['value'],'Architects')
        self.default('reset','audience');self.assertNotIn('audience',defaults.personal(self.root)['values'])
        with self.assertRaises(ValueError): self.default('set','review_folder','https://example.com/token?secret=1')
        self.assertEqual((self.root/'.writing-defaults.json').stat().st_mode & 0o777,0o600)

    def test_default_voice_pins_and_preserved_import(self):
        profile=studio.profile_command(self.root,self.args('profile','create','--name','Alex','--guide-file',self.file('Direct prose.'),'--status','confirmed'))
        self.default('set','voice',{'profile_id':profile['id'],'revision':1})
        a=self.article();self.assertEqual(studio.item(self.root,'articles',a)[1]['voice']['revision'],1)
        b=self.article(mode='existing');self.assertEqual(studio.item(self.root,'articles',b)[1]['voice']['mode'],'preserve')
        c=self.article(voice='tone',tone='Warm');self.assertEqual(studio.item(self.root,'articles',c)[1]['voice']['tone'],'Warm')
        (self.root/'profiles'/profile['id']/'revisions'/'1'/'record.json').unlink()
        self.assertEqual(defaults.resolve(self.root)['problems'][0]['status'],'unavailable')
        with self.assertRaises(ValueError): self.article()

    def test_changes_and_guarded_restore_keep_history_and_stale_reviews(self):
        a=self.article();self.save(a,'# Intro\nAn original sentence.')
        self.save(a,'# Intro\nA corrected sentence.','proofread')
        studio.article_command(self.root,self.args('article','review','--id',a,'--check','proofread','--status','current','--file',self.file('{"findings":[]}')))
        result=flow.changes(self.root,self.args('changes','--id',a))
        self.assertTrue(result['local']['text_changed']);self.assertEqual(result['local']['changes'][0]['section'],'Intro')
        rev=result['revisions'][-1];self.assertEqual(rev['before_operation'],'proofread')
        preview=flow.restore(self.root,self.args('article','restore','--id',a,'--revision',rev['revision']))
        with self.assertRaises(ValueError):flow.restore(self.root,self.args('article','restore','--id',a,'--revision',rev['revision'],'--apply','--expected','bad'))
        output=flow.restore(self.root,self.args('article','restore','--id',a,'--revision',rev['revision'],'--apply','--expected',preview['expected']))
        self.assertFalse(output['google_written'])
        d,r=studio.item(self.root,'articles',a)
        self.assertEqual((d/'DRAFT.md').read_text(),'# Intro\nAn original sentence.')
        self.assertEqual(studio.freshness(self.root,d,r)['proofread']['status'],'stale')
        self.assertEqual(len(flow.histories(d,'draft')),2)
        self.assertIn('A corrected sentence.',flow.histories(d,'draft')[-1].read_text())
        with self.assertRaises(ValueError):flow.history_file(d,'draft','../../source.md')
        with self.assertRaises(ValueError):flow.restore(self.root,self.args('article','restore','--id',a,'--revision',rev['revision'],'--apply','--expected',preview['expected']))

    def test_google_comparison_keeps_both_sides_and_unknown_format(self):
        import google_workflow as google
        a=self.article();self.save(a,'Baseline')
        d,r=studio.item(self.root,'articles',a);transfer='a'*32
        obs={'schema':1,'document_id':'doc1','url':'https://docs.google.com/document/d/doc1/edit','tab_ids':['t.0'],
             'observed_at':'2026-10-03T00:00:00+00:00','content_sha256':studio.digest(b'Baseline'),
             'revision_id':'r1','suggestions':'excluded','structure_verified':True}
        r['google']={'schema':1,'baselines':{'draft':{'transfer':transfer,'local_sha256':obs['content_sha256'],'document':obs}},'transfers':{},'receipts':[]}
        google.snapshot(d,transfer,'document','Baseline');studio.persist(d,'articles',r)
        self.save(a,'Local changes')
        returned={**obs,'content_sha256':studio.digest(b'Team changes'),'revision_id':'r2'}
        comparison=flow.changes(self.root,self.args('changes','--id',a,'--google-file',self.file('Team changes'),'--observation',self.file(json.dumps(returned))))
        self.assertEqual(comparison['google'],'conflict');self.assertTrue(comparison['local']['text_changed']);self.assertTrue(comparison['remote']['text_changed'])
        self.assertIsNone(comparison['format_changed'])
        card=flow.status(self.root,a);self.assertEqual(card['google']['status'],'not-checked')
        self.assertIn('[Google Doc]',card['card']);self.assertEqual((d/'DRAFT.md').read_text(),'Local changes')

    def hub(self):
        self.provider=FakeProvider(self.base/'remotes')
        registry=Registry(self.base/'registry',self.provider)
        hid=registry.create('fixture/writing','Team')['hub']
        return Workspace(self.root,registry.hub(hid))

    def test_hub_card_tracks_queue_review_shared_local_changes_and_conflict(self):
        a=self.article();self.save(a,'Draft')
        adapter=self.hub()
        with patch('hub_workspace.active',return_value=adapter):
            adapter.publish_selected({'articles':[a]},offline=True)
            self.assertEqual(flow.status(self.root,a)['hub']['status'],'queued')
            adapter.publish_selected({'articles':[a]})
            value=flow.status(self.root,a)
            self.assertEqual(value['hub']['status'],'shared');self.assertTrue(value['hub']['last_confirmed_saved']);self.assertTrue(value['hub']['url'])
            self.save(a,'A local change')
            self.assertEqual(flow.status(self.root,a)['hub']['status'],'local-changes-not-shared')
            comparison=flow.changes(self.root,self.args('changes','--id',a,'--against','hub'))
            self.assertTrue(comparison['local']['text_changed']);self.assertFalse(comparison['remote']['text_changed'])
            self.provider.review=True
            adapter.publish_selected({'articles':[a]})
            self.assertEqual(flow.status(self.root,a)['hub']['status'],'pending-review')
            saved=adapter.state['items']['articles/'+a]
            adapter.hub.save('article','Competing',item=saved['item'],parents=[],data={'studio':{}},sync=False)
            self.assertEqual(flow.status(self.root,a)['hub']['status'],'conflicted')

    def test_team_defaults_conflicts_and_cross_member_portability(self):
        adapter=self.hub()
        with patch('hub_workspace.active',return_value=adapter):
            self.default('set','audience','Team engineers',scope='team')
            self.assertEqual(defaults.resolve(self.root)['values']['audience']['scope'],'team')
            self.default('set','audience','Personal audience')
            self.assertEqual(defaults.resolve(self.root)['values']['audience']['scope'],'personal')
            a=self.article();adapter.publish_selected({'articles':[a]})
            payload='\n'.join(adapter.hub.files().keys())
            self.assertNotIn('.writing-defaults.json',payload)
            other=self.base/'other';studio.initialize(other)
            other_adapter=Workspace(other,adapter.hub)
            self.assertEqual(defaults.resolve(other,adapter=other_adapter)['values']['audience']['value'],'Team engineers')
            adapter.hub.save('context','Competing default',data={'key':'writing-default:audience','value':'Another team audience'})
            self.assertEqual(defaults.resolve(other,adapter=other_adapter)['problems'][0]['status'],'conflicted')
            # Personal choice resolves the same key without silently changing team records.
            self.assertFalse(defaults.resolve(self.root)['problems'])
            with self.assertRaises(ValueError):self.default('set','audience','Overwrite',scope='team')

    def test_team_voice_default_projects_exact_shared_profile(self):
        profile=studio.profile_command(self.root,self.args('profile','create','--name','Voice','--guide-file',self.file('Measured voice'),'--status','confirmed'))
        adapter=self.hub()
        with patch('hub_workspace.active',return_value=adapter):
            ref=adapter.publish_selected({'profiles':[profile['id']]})['items'][0]
            self.default('set','voice',{k:ref[k] for k in ('item','revision')},scope='team')
        other=self.base/'other';studio.initialize(other);other_adapter=Workspace(other,adapter.hub)
        with patch('hub_workspace.active',return_value=other_adapter):
            args=studio.parser().parse_args(['--root',str(other),'article','create','--title','Other writer','--mode','first-draft'])
            article=studio.article_command(other,args)
            self.assertEqual(article['voice']['mode'],'profile')
            folder,_=studio.item(other,'profiles',article['voice']['profile_id'])
            self.assertEqual((folder/'VOICE.md').read_text(),'Measured voice')

    def test_restore_preview_cli_never_syncs_and_apply_publishes_once(self):
        aid=self.article();self.save(aid,'Before');self.save(aid,'After','proofread')
        directory,_=studio.item(self.root,'articles',aid)
        revision=flow.histories(directory,'draft')[-1].name
        preview_args=['studio.py','--root',str(self.root),'article','restore','--id',aid,'--revision',revision]
        from unittest.mock import Mock
        adapter=Mock()
        output=io.StringIO()
        with patch.object(sys,'argv',preview_args), patch('hub_workspace.active',return_value=None), redirect_stdout(output):
            self.assertEqual(studio.main(),0)
        preview=json.loads(output.getvalue())
        self.assertEqual((directory/'DRAFT.md').read_text(),'After')
        # A stale preview must not write or publish.
        self.save(aid,'Changed again')
        errors=io.StringIO()
        from contextlib import redirect_stderr
        with patch.object(sys,'argv',preview_args+['--apply','--expected',preview['expected']]), patch('hub_workspace.active',return_value=None), redirect_stderr(errors):
            self.assertEqual(studio.main(),1)
        self.assertEqual((directory/'DRAFT.md').read_text(),'Changed again')
        with patch('hub_workspace.active',return_value=None):
            preview=flow.restore(self.root,self.args(*preview_args[3:]))
        # Actual restore follows normal selected-article publication.
        adapter.publish_mutation.return_value={'status':'queued-offline'}
        output=io.StringIO()
        with patch.object(sys,'argv',preview_args+['--apply','--expected',preview['expected']]), patch('author_workflow.hub_state',return_value=preview['hub']), patch('hub_workspace.active',return_value=adapter), redirect_stdout(output):
            self.assertEqual(studio.main(),0)
        self.assertEqual(json.loads(output.getvalue())['hub_sync']['status'],'queued-offline')
        adapter.publish_mutation.assert_called_once()
        self.assertEqual((directory/'DRAFT.md').read_text(),'Before')

    def test_format_only_history_and_unknown_legacy_baselines(self):
        a=self.article();self.save(a,'Same text')
        d,r=studio.item(self.root,'articles',a)
        def transfer(revision, native, content):
            return {'kind':'draft','document':{'document_id':'doc','tab_ids':['t.0'],
                'observed_at':f'2026-10-03T00:00:0{revision}+00:00',
                'format_sha256':native*64,'content_sha256':studio.digest(content.encode())}}
        r['google']={'schema':1,'baselines':{},'transfers':{'a':transfer(1,'a','Same text'),'b':transfer(2,'b','Same text')}}
        studio.persist(d,'articles',r)
        result=flow.changes(self.root,self.args('changes','--id',a))
        self.assertTrue(result['format_changed']);self.assertEqual(len(result['format_baseline']),2)
        r['google']['transfers']['b']=transfer(2,'b','Different text');studio.persist(d,'articles',r)
        self.assertIsNone(flow.changes(self.root,self.args('changes','--id',a))['format_changed'])

    def test_team_reset_retires_default_and_private_values_stay_outside_payload(self):
        adapter=self.hub()
        with patch('hub_workspace.active',return_value=adapter):
            self.default('set','author','Team author',scope='team')
            self.default('reset','author',scope='team')
            self.assertNotIn('author',defaults.resolve(self.root)['values'])
            self.default('set','audience','PRIVATE UNUSED VALUE')
            a=self.article(audience='Selected public audience')
            adapter.publish_selected({'articles':[a]})
            self.assertFalse(any(b'PRIVATE UNUSED VALUE' in value for value in adapter.hub.files().values()))
            self.assertTrue(any(record['status']=='tombstone' for record in adapter.hub.graph()['revisions'].values()))

    def test_status_handles_unavailable_hub_and_live_google_result(self):
        from hub_store import HubError
        a=self.article();self.save(a,'Draft')
        with patch('hub_workspace.active',side_effect=HubError('Unavailable')):
            card=flow.status(self.root,a)
            self.assertEqual(card['hub']['status'],'unknown');self.assertEqual(card['local'],'saved')
        fake={'status':'google-changes','label':'Google has changes','document_url':'https://docs.google.com/document/d/doc/edit',
              'last_checked_at':'now','last_successful_check_at':'now','next_step':'Pull the edits.','reason':'fresh fixture read'}
        with patch('google_workflow.sync_status',return_value=fake) as check:
            card=flow.status(self.root,a,online=True)
            self.assertTrue(check.call_args.args[4]);self.assertEqual(card['next_step'],'Pull the edits.')
            self.assertNotIn('guidance',card)
