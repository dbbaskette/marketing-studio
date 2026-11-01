"""Selected files, isolated bare remotes and competing workspace owners."""
import hashlib
import json
import os
import subprocess
from unittest import mock
from helpers import Isolated
import test_desk_engine as desk
from runner import handoffs,intake,sources,team
from runner.contracts import Invalid
from runner.workspace import Store


class HandoffTests(Isolated):
    def test_selected_material_hash_and_source_revision(self):
        root=self.temp/'origin'/'blogs';root.mkdir(parents=True)
        (root/'hub.json').write_text(json.dumps({'tool':'blog-studio','schema':1,'folder':'blogs'}))
        folder=root/'synthetic-blog';folder.mkdir();(folder/'DRAFT.md').write_text('Synthetic original.')
        (folder/'.private').write_text('Never selected');(folder/'README.md').write_text('Other material.')
        inventory=handoffs.inventory(root,'blog');self.assertEqual(len(inventory['files']),2)
        selected=next(x for x in inventory['files'] if x['file'].endswith('DRAFT.md'))
        preview=handoffs.prepare(root,'blog',selected['file'],selected['sha256'])
        store=Store.setup(self.workspace);p=store.create('Selected blog');p=intake.adopt(store,p['id'],preview['id'],expected_revision=0)
        self.assertEqual(p['sources'][0]['provenance']['studio'],'Blog Studio')
        (folder/'DRAFT.md').write_text('Changed origin.')
        with self.assertRaisesRegex(Invalid,'changed'):handoffs.prepare(root,'blog',selected['file'],selected['sha256'])
        fresh=next(x for x in handoffs.inventory(root,'blog')['files'] if x['file'].endswith('DRAFT.md'))
        update=handoffs.prepare(root,'blog',fresh['file'],fresh['sha256']);p=intake.adopt(store,p['id'],update['id'],replace_id=p['sources'][0]['id'],expected_revision=1)
        self.assertEqual(p['revision'],2);self.assertEqual(len(p['sources']),1);self.assertEqual(sources.read(store,p,p['sources'][0]),'Changed origin.')

    def test_hidden_link_and_wrong_studio_refused(self):
        root=self.temp/'blogs';root.mkdir();(root/'hub.json').write_text(json.dumps({'tool':'blog-studio','schema':1,'folder':'blogs'}));(root/'entry').mkdir()
        secret=self.temp/'secret.md';secret.write_text('Synthetic private');(root/'entry'/'leak.md').symlink_to(secret)
        self.assertEqual(handoffs.inventory(root,'blog')['files'],[])
        for name in ('entry/leak.md','../secret.md','entry/.private.md'):
            with self.assertRaises(Invalid):handoffs.prepare(root,'blog',name,hashlib.sha256(b'Synthetic private').hexdigest())
        with self.assertRaises(Invalid):handoffs.inventory(root,'training')

    def test_a_missing_folder_is_named_with_its_studio(self):
        # The page pre-fills each studio's usual folder; when it is not there, say which one.
        missing=self.temp/'Studios'/'blog-workspace'/'blogs'
        with self.assertRaises(Invalid) as refused:handoffs.inventory(str(missing),'blog')
        self.assertEqual(str(refused.exception),'No Blog Studio materials folder was found at '+str(missing)
                         +". Check Blog Studio's workspace in shared settings.")
        plain=self.temp/'plain';plain.mkdir()
        with self.assertRaises(Invalid) as refused:handoffs.inventory(str(plain),'presentation')
        self.assertIn(str(plain)+' is not a Presentation Studio materials folder',str(refused.exception))
        self.assertNotIn('Infographic Studio file',str(refused.exception))


class TeamTests(Isolated):
    current=desk.DeskEngineTests.current
    review_and_approve=desk.DeskEngineTests.review_and_approve

    def setUp(self):
        super().setUp();desk.setup_desk(self)
        self.remote=self.temp/'team.git';self.seed=self.temp/'seed';self.seed.mkdir()
        def git(*args):subprocess.run(['git',*args],capture_output=True,check=True)
        git('init','--bare','--initial-branch=main',str(self.remote));git('-C',str(self.seed),'init','--initial-branch=main')
        (self.seed/'README.md').write_text('Synthetic team repository.');git('-C',str(self.seed),'add','README.md');git('-C',str(self.seed),'commit','-m','Synthetic seed');git('-C',str(self.seed),'remote','add','origin',str(self.remote));git('-C',str(self.seed),'push','origin','main')
        self.settings.write_text(json.dumps({'team':{'repository':str(self.remote),'branch':'main'},'person':{'name':'Synthetic owner','email':'owner@example.invalid'}}))
        self.review_and_approve();self.delivery=self.engine.preview(self.ident,expected_revision=self.current()['revision'],draft=False)
        from runner import settings
        settings.save({'team_email':'owner@example.invalid'},expected=settings.snapshot()['native_revision'])
        team.connect()

    def selection(self,editable=False,sources_=False):return {'expected_revision':self.current()['revision'],'export_id':self.delivery['id'],'include_editable':editable,'source_ids':[s['id'] for s in self.current()['sources']] if sources_ else [],'asset_ids':[]}

    def share(self,editable=False,sources_=False):
        selection=self.selection(editable,sources_);preview=team.preview(self.store,self.ident,**selection)
        return team.share(self.store,self.ident,**selection,inventory_digest=preview['inventory_digest'],expected_head=preview['expected_head'],expected_claim=preview['expected_claim'],expected_connection=preview['expected_connection'],confirm_private=editable)

    def test_default_share_exact_public_inventory_no_sources_prompts(self):
        self.share();entry=team.status()['items'][0]
        self.assertEqual({i['file'] for i in entry['files']},{'README.md','delivery/page.png','delivery/page.pdf','delivery/page.svg','delivery/page.txt'})
        self.assertNotIn('project.json',{i['file'] for i in entry['files']});self.assertTrue(team.download(self.ident,'pdf')[1].startswith(b'%PDF'))
        self.assertEqual(Store.current().root,self.store.root)

    def test_foreign_owner_takeover_editable_import_and_missing_private_sources(self):
        self.share(editable=True)
        original_data=os.environ['INFOGRAPHIC_STUDIO_DATA']
        with mock.patch.dict(os.environ,{'INFOGRAPHIC_STUDIO_DATA':str(self.temp/'data2')}):
            other=Store.setup(self.temp/'workspace2');
            from runner import settings
            settings.save({'team_email':'other@example.invalid'},expected=settings.snapshot()['native_revision']);team.connect();state=team.status();entry=state['items'][0]
            with self.assertRaises(Invalid):team.take(other,self.ident,expected_head=state['head'],expected_claim=entry['claim'])
            claim=team.claim(other,self.ident,expected_head=state['head'],expected_claim=entry['claim']);state=team.status()
            taken=team.take(other,self.ident,expected_head=state['head'],expected_claim=claim)
            self.assertIsNone(taken['project']['approval']);self.assertEqual(taken['project']['owner'],other.owner);self.assertTrue(taken['missing_sources'])
            with self.assertRaises(Invalid):sources.read(other,taken['project'],taken['project']['sources'][0])
        self.assertEqual(os.environ['INFOGRAPHIC_STUDIO_DATA'],original_data)
        # The original driver's stale view cannot overwrite the new owner remotely.
        with self.assertRaisesRegex(Invalid,'repository changed'):self.share()
        team.connect()
        with self.assertRaisesRegex(Invalid,'Someone else'):self.share()

    def test_selected_sources_only_and_private_confirmation(self):
        selection=self.selection(True,True);preview=team.preview(self.store,self.ident,**selection)
        with self.assertRaisesRegex(Invalid,'Confirm'):team.share(self.store,self.ident,**selection,inventory_digest=preview['inventory_digest'],expected_head=preview['expected_head'],expected_claim=None,expected_connection=preview['expected_connection'])
        self.share(True,True);entry=team.status()['items'][0]
        self.assertTrue(any(f['file'].startswith('editable/sources/') for f in entry['files']))
        self.assertFalse(any('jobs/' in f['file'] or 'prompt' in f['file'] for f in entry['files']))

    def test_dirty_clone_and_symlink_namespace_preserved(self):
        folder=team.root();(folder/'unfinished.txt').write_text('Keep this')
        with self.assertRaisesRegex(Invalid,'unfinished'):team.connect()
        self.assertEqual((folder/'unfinished.txt').read_text(),'Keep this');(folder/'unfinished.txt').unlink()
        outside=self.temp/'outside';outside.mkdir();(folder/'infographics').symlink_to(outside)
        with self.assertRaisesRegex(Invalid,'links'):team.status()
        self.assertEqual(list(outside.iterdir()),[])

    def test_failed_push_keeps_commit_for_explicit_retry(self):
        actual=team.git
        def fail(folder,*args,**kw):
            if args[0]=='push':raise Invalid('Synthetic offline push')
            return actual(folder,*args,**kw)
        with mock.patch.object(team,'git',side_effect=fail):
            with self.assertRaisesRegex(Invalid,'offline'):self.share()
        pending=team.head(team.root());self.assertTrue(team.status()['items'])
        self.assertTrue(team.retry_pending(expected_commit=pending)['connected'])

    def test_existing_git_auth_configuration_is_kept_but_content_filters_never_run(self):
        marker=self.temp/'filter-executed'
        script=self.temp/'synthetic-filter'
        script.write_text('#!/bin/sh\ntouch '+str(marker)+'\ncat\n');script.chmod(0o700)
        (self.home/'.gitconfig').write_text('[filter "synthetic"]\n smudge = '+str(script)+'\n clean = '+str(script)+'\n required = true\n')
        (self.seed/'.gitattributes').write_text('*.md filter=synthetic\n')
        # Build the synthetic remote without consulting that filter configuration.
        subprocess.run(['git','-C',str(self.seed),'add','.gitattributes'],capture_output=True,check=True)
        subprocess.run(['git','-C',str(self.seed),'commit','-m','Synthetic remote attributes'],capture_output=True,check=True)
        subprocess.run(['git','-C',str(self.seed),'push','origin','main'],capture_output=True,check=True)
        team.connect();self.share()
        self.assertFalse(marker.exists(),'Remote attributes must not execute a configured content filter.')
