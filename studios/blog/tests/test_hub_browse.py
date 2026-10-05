"""GitHub-facing projections are deterministic and never become canonical memory."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hub_fixtures import FakeProvider
from hub import Registry
import hub_store as store
from hub_browse import render, verify, START
import studio
from hub_workspace import Workspace


class BrowseTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve();self.provider=FakeProvider(self.base/'remote')
        self.a=Registry(self.base/'a',self.provider);self.b=Registry(self.base/'b',self.provider)
        self.id=self.a.create('fixture/library','Our team')['hub']
        self.ha=self.a.hub(self.id);self.b.join('fixture/library');self.hb=self.b.hub(self.id)
        self.remote=self.provider.transport({'repository':'fixture/library'})

    def files(self):
        return store.tree_files(self.remote,store.git(self.remote,'rev-parse','main').decode().strip())

    def save(self,title='Better handoffs',author='Dan Baskette',**kwargs):
        return self.ha.save('article',title,'Current manuscript.',data={'studio':{'author':author,'stage':'draft','research_policy':'supplied-only'}},**kwargs)

    def test_new_hub_index_and_article_render_links_without_extra_private_content(self):
        self.assertIn(b'No blogs have been shared',self.files()['README.md'])
        note=self.ha.save('note','Private planning','SECRET unrelated planning')
        source=self.ha.save('source','Pilot notes','SECRET source body')
        self.ha.save('article','Better handoffs','Readable current draft.',data={'studio':{'author':'Dan Baskette','stage':'draft'}},
                     dependencies=[{'item':source['item'],'revision':source['revision'],'kind':'source','role':'source'}],
                     artifacts={'OUTLINE.md':(b'# Outline\nA useful point.','text')})
        files=self.files();folder='blogs/dan-baskette/better-handoffs/'
        self.assertIn(b'Readable current draft.',files[folder+'README.md'])
        self.assertIn(b'outline.md',files[folder+'README.md'])
        self.assertIn(b'Pilot notes',files[folder+'context.md'])
        views=b'\n'.join(body for name,body in files.items() if name.startswith('blogs/'))
        self.assertNotIn(b'SECRET unrelated planning',views)
        self.assertIn(b'SECRET source body',views)
        self.assertIn(b'blogs/dan-baskette/better-handoffs/README.md',files['README.md'])
        self.assertEqual(self.ha.status()['blog_library'],'available')
        verify(files,store.validate_files(files))
        for name,body in files.items():
            if name.startswith('blogs/'):
                import re,posixpath
                for target in re.findall(r'\]\(([^)]+)\)',body.decode()):
                    self.assertIn(posixpath.normpath(posixpath.join(posixpath.dirname(name),target)),files)

    def test_google_working_link_migrates_old_views_without_rewriting_memory(self):
        from hub_browse import changes, google_doc_links
        doc = {'document_id':'doc_123','url':'https://docs.google.com/document/d/doc_123/edit',
               'observed_at':'2026-10-02T17:07:34-04:00'}
        data = {'studio':{'author':'Dan','google':{'baselines':{'draft':{'document':doc}}}}}
        self.ha.save('article','Linked post','Body',data=data)
        current = self.files();graph=store.validate_files(current)
        # Reproduce a 1.6 library: metadata already has the link, generated pages lack it.
        legacy={k.replace('.blog-studio/items/', 'memory/items/'):v for k,v in current.items()
                if k == 'hub.json' or k == 'README.md' or k.startswith('.blog-studio/items/')}
        manifest=dict(graph['manifest']);manifest.pop('storage_schema');manifest.pop('history_schema', None);manifest['browse_schema']=1
        legacy['hub.json']=store.encoded(manifest)
        legacy.update(render(legacy,store.validate_files(legacy),show_google_links=False))
        manifest=dict(manifest);manifest.pop('google_doc_links');manifest['minimum_runtime']='1.5.0'
        legacy['hub.json']=store.encoded(manifest)
        old_graph=store.validate_files(legacy);verify(legacy,old_graph)
        additions=changes(legacy,old_graph)
        updated=dict(legacy)
        for k,v in additions.items():
            if v is None:updated.pop(k,None)
            else:updated[k]=v
        new_graph=store.validate_files(updated);verify(updated,new_graph)
        self.assertEqual(new_graph['manifest']['browse_schema'],3)
        self.assertEqual(new_graph['manifest']['minimum_runtime'],'1.13.1')
        page=updated['blogs/dan/linked-post/README.md']
        self.assertIn(b'[Open working Google Doc](https://docs.google.com/document/d/doc_123/edit)',page)
        self.assertIn(b'2026-10-02 21:07 UTC',page)
        self.assertEqual(store.immutable_files(legacy,old_graph),store.immutable_files(updated,new_graph))
        self.assertEqual(changes(updated,new_graph),{})
        with patch.object(store,'VERSION','1.5.0'):
            with self.assertRaises(store.HubError):store.validate_files(updated)
        edited=dict(legacy);edited['blogs/dan/linked-post/README.md']+=b'User edit'
        with self.assertRaises(store.HubError):verify(edited,old_graph)
        for value in ('https://evil.invalid/', 'javascript:alert(1)', doc['url']+'?token=private'):
            bad={'google':{'baselines':{'draft':{'document':{**doc,'url':value}}}}}
            self.assertEqual(google_doc_links(bad),'')
        self.assertIn('Google Doc (outline)',google_doc_links({'google':{'baselines':{'outline':{'document':doc}}}}))

    def test_revision_history_explains_import_and_marks_current_revision(self):
        transfer='a'*32
        imported={'studio':{'author':'Dan Baskette','stage':'draft','google':{
            'transfers':{transfer:{'direction':'from-google','status':'confirmed'}}}}}
        first=self.ha.save('article','Columnar storage','Imported manuscript.',data=imported)
        bound=self.ha.save('article','Columnar storage','Imported manuscript.',item=first['item'],
                           parents=[first['revision']],data={**imported,'guidance':{'task':'task-id'}})
        history=self.files()['blogs/dan-baskette/columnar-storage/history.md'].decode()
        self.assertIn('Current · '+bound['revision'][:8],history)
        self.assertIn('Writing guidance pinned',history)
        self.assertIn('Earlier · '+first['revision'][:8],history)
        self.assertIn('Imported from Google Docs',history)
        self.assertNotIn('| Title |',history)
        self.assertIn('| Saved | Revision | What changed | Article state |',history)

    def test_existing_detailed_history_migrates_to_readable_layout(self):
        from hub_browse import changes
        self.save()
        current = self.files()
        legacy = {k.replace('.blog-studio/items/', 'memory/items/'): v for k, v in current.items()
                  if k in ('hub.json', 'README.md') or k.startswith('.blog-studio/items/')}
        manifest = json.loads(legacy['hub.json'])
        manifest.pop('storage_schema');manifest.pop('history_schema', None)
        manifest['browse_schema'] = 2;manifest['minimum_runtime'] = '1.12.3'
        legacy['hub.json'] = store.encoded(manifest)
        graph = store.validate_files(legacy)
        legacy.update(render(legacy, graph, layout_schema=1))
        verify(legacy, store.validate_files(legacy))
        updated = dict(legacy)
        for name, body in changes(legacy, store.validate_files(legacy)).items():
            if body is None:updated.pop(name, None)
            else:updated[name] = body
        graph = store.validate_files(updated);verify(updated, graph)
        self.assertEqual(graph['manifest']['storage_schema'], 2)
        self.assertEqual(graph['manifest']['history_schema'], 2)
        self.assertIn(b'What changed', next(v for k, v in updated.items() if k.endswith('/history.md')))

    def test_new_history_schema_requires_compatible_runtime(self):
        manifest=store.manifest(self.id,'Our team','fixture/library');manifest.pop('storage_schema',None);manifest['browse_schema']=2;manifest['minimum_runtime']='1.12.2'
        with self.assertRaisesRegex(store.HubError,'compatible newer'):
            store.validate_manifest(manifest)
        manifest['minimum_runtime']='1.12.3'
        self.assertEqual(store.validate_manifest(manifest)['browse_schema'],2)

    def test_review_snapshots_require_runtime_19_even_with_google_links(self):
        doc={'document_id':'doc_123','url':'https://docs.google.com/document/d/doc_123/edit','observed_at':'2026-10-03T12:00:00+00:00'}
        self.ha.save('article','Review copy','Body',data={'studio':{'google':{'baselines':{'draft':{'document':doc}}}}},
                     artifacts={'history/google-'+'a'*32+'-accepted.json':(b'{}','text')})
        files=self.files()
        self.assertEqual(json.loads(files['hub.json'])['minimum_runtime'],'1.13.1')
        with patch.object(store,'VERSION','1.8.0'):
            with self.assertRaises(store.HubError):store.validate_files(files)

    def test_explicit_author_survives_other_editor_and_title_rename_cleans_only_views(self):
        saved=self.save();old=self.files();self.hb.refresh()
        self.hb.save('article','Renamed blog','Changed manuscript.',item=saved['item'],parents=[saved['revision']],
                     actor='Another editor',data={'studio':{'author':'Dan Baskette','stage':'review'}})
        files=self.files()
        self.assertIn('blogs/dan-baskette/renamed-blog/README.md',files)
        self.assertNotIn('blogs/dan-baskette/better-handoffs/README.md',files)
        self.assertEqual({k:v for k,v in old.items() if k.startswith('.blog-studio/items/')},
                         {k:files[k] for k in old if k.startswith('.blog-studio/items/')})
        history=files['blogs/dan-baskette/renamed-blog/history.md']
        self.assertIn(b'Better handoffs',history);self.assertIn(b'Renamed blog',history)

    def test_voice_author_and_unassigned_fallback_never_use_last_editor(self):
        voice=self.ha.save('voice','Alex Writer','VOICE text')
        self.ha.save('article','Voice post','Blog',actor='Uploader',
                     dependencies=[{'item':voice['item'],'revision':voice['revision'],'kind':'voice','role':'voice'}])
        self.ha.save('article','No author','Blog',actor='Uploader')
        files=self.files()
        self.assertIn('blogs/alex-writer/voice-post/README.md',files)
        self.assertIn('blogs/unassigned/no-author/README.md',files)
        self.assertFalse(any('uploader' in name for name in files))

    def test_collision_suffixes_extend_until_unique_and_metadata_cannot_escape(self):
        for operation in ('a'*31+'1','a'*31+'2'):
            self.save(title='Same title',operation=operation)
        self.save(title='Same title-' + 'a'*31+'1')
        files=self.files()
        paths=[name for name in files if name.startswith('blogs/dan-baskette/same-title') and name.endswith('/README.md') and name.count('/') == 3]
        self.assertEqual(len(paths),3);self.assertTrue(all(len(Path(name).parent.name)>len('same-title-')+8 for name in paths))
        self.save(title='../[click](https://bad.invalid) | @someone',author='../../<script>')
        files=self.files()
        self.assertTrue(all('..' not in name for name in files if name.startswith('blogs/')))
        self.assertNotIn(b'[click](https://bad.invalid)',files['README.md'])
        self.assertNotIn(b'@someone',files['README.md'])

    def test_tombstone_removes_browsing_paths_and_retains_canonical_history(self):
        saved=self.save();before=self.files()
        self.ha.save('article','Better handoffs','',item=saved['item'],parents=[saved['revision']],status='tombstone')
        files=self.files();self.assertEqual([p for p in files if p.startswith('blogs/')],['blogs/README.md'])
        self.assertTrue(all(files[p]==body for p,body in before.items() if p.startswith('.blog-studio/items/')))

    def test_concurrent_edits_show_conflict_without_silently_picking_a_draft(self):
        saved=self.save();self.hb.refresh()
        one=self.ha.save('article','Better handoffs','FIRST SIDE',item=saved['item'],offline=True)
        two=self.hb.save('article','Better handoffs','SECOND SIDE',item=saved['item'],offline=True)
        self.ha.sync();self.hb.sync()
        files=self.files();page=next(body for name,body in files.items() if name.startswith('blogs/') and name.endswith('/README.md') and name!='blogs/README.md')
        self.assertIn(b'Competing revisions',page);self.assertNotIn(b'FIRST SIDE',page);self.assertNotIn(b'SECOND SIDE',page)
        self.hb.save('article','Resolved','COMBINED',item=saved['item'],parents=[one['revision'],two['revision']],data={'studio':{'author':'Dan'}})
        self.assertIn(b'COMBINED',self.files()['blogs/dan/resolved/README.md'])

    def test_manual_generated_edits_block_overwrite_and_keep_queued_work(self):
        saved=self.save();base=store.git(self.remote,'rev-parse','main').decode().strip()
        custom=self.files()['README.md']+b'\nCustom team instructions.\n'
        commit=store.commit_files(self.remote,base,{'README.md':custom},'Homepage edit','User')
        store.git(self.remote,'update-ref','refs/heads/main',commit)
        self.ha.save('note','Ordinary note','A shared note')
        self.assertIn(b'Custom team instructions.',self.files()['README.md'])
        base=store.git(self.remote,'rev-parse','main').decode().strip()
        page='blogs/dan-baskette/better-handoffs/README.md'
        commit=store.commit_files(self.remote,base,{page:b'MANUAL EDIT'},'User edit','User')
        store.git(self.remote,'update-ref','refs/heads/main',commit)
        with self.assertRaisesRegex(store.HubError,'Generated blog pages were edited'):
            self.ha.save('note','New note','Saved locally')
        self.assertEqual(self.files()[page],b'MANUAL EDIT');self.assertEqual(self.ha.status()['queued'],1)
        self.assertEqual(self.ha.find('New note')['total'],1)

    def legacy(self):
        files=self.files();manifest=json.loads(files['hub.json']);manifest.pop('browse_schema');manifest.pop('storage_schema');manifest.pop('history_schema', None);manifest['minimum_runtime']='1.1.0'
        changes={name:None for name in files if name.startswith(('blogs/', 'memory/'))}
        changes.update({'hub.json':store.encoded(manifest),'README.md':b'# Our custom homepage\n\nKeep this explanation.\n'})
        base=store.git(self.remote,'rev-parse','main').decode().strip()
        commit=store.commit_files(self.remote,base,changes,'Legacy fixture','Fixture')
        store.git(self.remote,'update-ref','refs/heads/main',commit)

    def test_legacy_sync_migrates_without_memory_mutation_and_is_idempotent(self):
        self.legacy();self.assertEqual(self.ha.sync()['status'],'shared')
        files=self.files();self.assertIn(b'Keep this explanation.',files['README.md'])
        self.assertIn(START.encode(),files['README.md']);self.assertEqual(json.loads(files['hub.json'])['minimum_runtime'],'1.13.1')
        before=store.git(self.remote,'rev-parse','main')
        self.assertEqual(self.ha.sync()['status'],'synchronized');self.assertEqual(before,store.git(self.remote,'rev-parse','main'))
        with patch.object(store,'VERSION','1.2.0'):
            with self.assertRaisesRegex(store.HubError,'newer'):store.validate_files(files)

    def test_review_policy_keeps_library_on_branch_until_merge_including_empty_upgrade(self):
        self.legacy();self.provider.review=True
        result=self.ha.sync();self.assertEqual(result['status'],'pending-review')
        self.assertNotIn('blogs/README.md',self.files())
        branch=self.ha._state()['review_branch'];self.ha.refresh()
        self.assertEqual(self.ha._state()['review_branch'],branch)
        self.provider.merge_review('fixture/library',branch);self.ha.refresh()
        self.assertEqual(self.ha.status()['blog_library'],'available')
        saved=self.save();self.assertEqual(saved['status'],'pending-review')
        self.assertNotIn('blogs/dan-baskette/better-handoffs/README.md',self.files())
        branch=self.ha._state()['review_branch'];self.provider.merge_review('fixture/library',branch);self.ha.refresh()
        self.assertIn('blogs/dan-baskette/better-handoffs/README.md',self.files())

    def test_article_author_command_round_trips_to_shared_view(self):
        root=self.base/'writing';studio.initialize(root)
        def command(*words):
            args=studio.parser().parse_args(['--root',str(root),*words])
            return studio.article_command(root,args)
        saved=command('article','create','--title','Authored','--mode','outline-only','--author','First Writer')
        command('article','author','--id',saved['id'],'--name','Chosen Writer')
        command('article','rename','--id',saved['id'],'--title','Chosen title')
        Workspace(root,self.ha).publish_selected({'articles':[saved['id']]})
        self.assertIn('blogs/chosen-writer/chosen-title/README.md',self.files())

if __name__=='__main__':unittest.main()
