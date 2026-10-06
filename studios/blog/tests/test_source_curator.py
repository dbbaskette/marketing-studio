"""Import-time analysis preserves evidence, corrections, and retry semantics."""
import base64
import json
from unittest.mock import patch
from test_editorial_tools import Fixture
import studio
import blog_library
import management
import source_curator as curator

ANALYSIS={'summary':'A gateway reference about routing.','topics':['routing'],'products':['ExampleGate'],
          'kind':'Technical reference','cautions':['Historical behavior requires verification.']}

class CurationTests(Fixture):
    def setUp(self):
        super().setUp();curator.configure(self.root,'codex')
        self.runner=patch.object(curator,'analyze',side_effect=lambda engine,payload: {v['id']:dict(ANALYSIS) for v in payload} if isinstance(payload,list) else dict(ANALYSIS))
        self.model=self.runner.start();self.addCleanup(self.runner.stop)
    def test_source_intake_is_analyzed_and_unchanged_update_reuses_analysis(self):
        source=self.source('A gateway routes requests.')
        self.assertEqual(source['analysis']['status'],'ready')
        self.assertEqual(source['analysis']['sha256'],source['content_sha256'])
        self.assertEqual(source['library']['products'],['ExampleGate'])
        updated=self.command('source','update','--id',source['id'])
        self.assertEqual(self.model.call_count,1)
        self.assertEqual(updated['analysis']['sha256'],source['analysis']['sha256'])
        self.assertEqual(blog_library.catalog(self.root,query='technical')['total'],0)
        self.assertEqual(blog_library.catalog(self.root,query='ExampleGate')['total'],1)
    def test_manual_corrections_survive_body_change_and_prior_analysis_is_versioned(self):
        source=self.source('A gateway routes requests.')
        blog_library.curate(self.root,source['id'],{'topics':['team-chosen'],'products':[],'note':'Keep this note.','curation':'retired'})
        self.file.write_text('New version routes requests differently.')
        updated=self.command('source','update','--id',source['id'],'--text-file',str(self.file))
        self.assertEqual(updated['library']['topics'],['team-chosen']);self.assertEqual(updated['library']['products'],[])
        self.assertEqual(updated['note'],'Keep this note.');self.assertEqual(updated['library']['curation'],'retired')
        self.assertNotEqual(updated['analysis']['sha256'],source['analysis']['sha256'])
        directory,_=studio.item(self.root,'sources',source['id'])
        self.assertEqual(studio.read_json(directory/'revisions'/'1'/'record.json')['analysis'],source['analysis'])
    def test_analysis_failure_preserves_original_and_explicit_retry_is_idempotent(self):
        self.model.side_effect=ValueError('Selected CLI is unavailable.')
        source=self.source('Retain the gateway original.')
        self.assertEqual(source['analysis']['status'],'needs-analysis')
        directory,_=studio.item(self.root,'sources',source['id']);original=(directory/source['original_path']).read_bytes()
        self.model.side_effect=lambda engine,payload:{v['id']:dict(ANALYSIS) for v in payload}
        result=curator.retry(self.root,[source['id']]);self.assertEqual(result['results'][0]['analysis']['status'],'ready')
        before=self.model.call_count
        curator.retry(self.root,[source['id']]);self.assertEqual(self.model.call_count,before)
        self.assertEqual((directory/source['original_path']).read_bytes(),original)
        self.assertEqual(studio.item(self.root,'sources',source['id'])[1]['revision'],2)
    def test_upload_and_selected_archive_import_analyze_only_readable_selected_content(self):
        uploaded=management.dispatch(self.root,'upload',{'operation':'f'*32,'filename':'one.md','content':base64.b64encode(b'# Gateway\n\nRouting.').decode(),'title':'Gateway'})
        self.assertEqual(uploaded['source']['analysis']['status'],'ready')
        with patch.object(blog_library,'fetch',side_effect=lambda url,scope:(b'<a href="/post">Gateway</a><a href="/author">Author</a>' if url.endswith('/archive') else b'<h1>Gateway</h1><p>Routes requests.</p>',url,'text/html')) as fetch:
            preview=management.dispatch(self.root,'library-preview',{'operation':'a'*32,'name':'Old posts','type':'archive','url':'https://example.test/archive','scope':'https://example.test/'})
            chosen=next(row for row in preview['posts'] if row['url'].endswith('/post'))
            result=management.dispatch(self.root,'library-import',{'operation':'b'*32,'preview':preview['preview'],'expected':preview['expected'],'confirm':True,'retry':False,'selected':[chosen['key']]})
            self.assertEqual(result['counts']['imported'],1)
            self.assertEqual(fetch.call_count,2)
        self.assertEqual(self.model.call_count,2)
        self.assertIsInstance(self.model.call_args.args[1],list)
        rows=blog_library.catalog(self.root)['items'];self.assertEqual(len(rows),2)
        self.assertTrue(all(row['analysis']['status']=='ready' for row in rows))
    def test_interrupted_analysis_keeps_a_readable_source_record(self):
        self.model.side_effect=KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt):self.source('Retained before the model starts.')
        rows=blog_library.source_rows(self.root);self.assertEqual(len(rows),1)
        directory,record=studio.item(self.root,'sources',rows[0]['id'])
        self.assertEqual((directory/'content.md').read_text(),'Retained before the model starts.')
        self.assertEqual(record['status'],'ready')

    def test_pending_files_do_not_use_model_and_bad_results_never_become_ready(self):
        source=self.command('source','add','--name','PDF','--origin','file.pdf','--purpose','reference','--status','pending')
        self.assertEqual(source['analysis']['status'],'needs-extraction');self.model.assert_not_called()
        self.model.side_effect=None;self.model.return_value={'summary':'Only one field'}
        bad=self.source('Saved readable source.')
        self.assertEqual(bad['analysis']['status'],'needs-analysis')
        with self.assertRaises(ValueError):curator.validate({**ANALYSIS,'topics':['tag']*9})
    def test_archive_refresh_preserves_human_note_and_tags(self):
        folder=self.base/'archive';folder.mkdir();post=folder/'one.md';post.write_text('A gateway routes requests.')
        blog_library.setup(self.root,{'key':'old','name':'Old','type':'folder','path':str(folder)})
        first=blog_library.preview(self.root,'old');blog_library.import_batch(self.root,first['preview'],delay=0)
        ident=blog_library.catalog(self.root)['items'][0]['id']
        blog_library.curate(self.root,ident,{'note':'Team correction.','topics':['specific-topic'],'products':[]})
        post.write_text('A changed gateway example.')
        next_preview=blog_library.preview(self.root,'old');blog_library.import_batch(self.root,next_preview['preview'],delay=0)
        record=studio.item(self.root,'sources',ident)[1]
        self.assertEqual(record['note'],'Team correction.');self.assertEqual(record['library']['topics'],['specific-topic'])
        self.assertEqual(record['library']['products'],[]);self.assertEqual(record['analysis']['status'],'ready')
    def test_codex_invocation_keeps_selected_model_but_disables_customizations(self):
        cfg=self.base/'codex';cfg.mkdir();(cfg/'config.toml').write_text('model="configured-model"\n[model_providers.secret]\napi_key="DO-NOT-COPY"\n[mcp_servers.secret]\ncommand="dangerous"\n')
        with patch.dict('os.environ',{'CODEX_HOME':str(cfg)}):options=curator.codex_options()
        flat=' '.join(options)
        self.assertIn('model="configured-model"',flat)
        for gate in ('shell_tool','apps','plugins','hooks','multi_agent','browser_use','computer_use'):
            self.assertIn('features.'+gate+'=false',flat)
        self.assertIn('--ignore-user-config',options);self.assertIn('web_search="disabled"',flat)
        self.assertNotIn('DO-NOT-COPY',flat);self.assertNotIn('dangerous',flat)


class SharedCurationTests(Fixture):
    def test_analysis_syncs_to_another_workspace_and_retains_source_bytes(self):
        from hub_fixtures import FakeProvider
        from hub import Registry
        from hub_workspace import Workspace
        provider=FakeProvider(self.base/'remotes');registry=Registry(self.base/'hubs',provider)
        hub_id=registry.create('fixture/curation','Curation')['hub'];workspace=Workspace(self.root,registry.hub(hub_id))
        source=self.source('A retained gateway reference.');workspace.publish_selected({'sources':[source['id']]})
        original=studio.item(self.root,'sources',source['id'])[0]/source['original_path'];before=original.read_bytes()
        curator.configure(self.root,'codex')
        with patch('hub_workspace.active',return_value=workspace),patch.object(curator,'analyze',side_effect=lambda engine,payload:{v['id']:dict(ANALYSIS) for v in payload}):
            result=curator.retry(self.root,[source['id']])
        self.assertEqual(result['sharing']['status'],'shared');self.assertEqual(original.read_bytes(),before)
        other=self.base/'member';studio.initialize(other)
        other_registry=Registry(self.base/'member-hubs',provider);other_registry.join('fixture/curation')
        second=Workspace(other,other_registry.hub(hub_id))
        with patch('hub_workspace.active',return_value=second):
            found=blog_library.catalog(other,query='ExampleGate',reusable_only=True)
        self.assertEqual(found['total'],1);self.assertEqual(found['items'][0]['analysis']['summary'],ANALYSIS['summary'])
