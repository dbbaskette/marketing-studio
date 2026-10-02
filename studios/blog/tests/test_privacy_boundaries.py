"""No live accounts or external content are used by these privacy regressions."""
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from hub_fixtures import FakeProvider
from hub import Registry
import hub as hub_module
import hub_store
import studio
import linkedin_import
import text_checks

class PrivacyTests(unittest.TestCase):
    def test_provider_host_and_debug_environment_cannot_redirect_api_calls(self):
        observed=[]
        def capture(command,**kwargs):
            observed.append((command,kwargs))
            return subprocess.CompletedProcess(command,0,b'{"login":"fixture"}',b'')
        with patch.dict(os.environ,{'GH_HOST':'unapproved.invalid','GH_DEBUG':'api'}),patch.object(hub_store.subprocess,'run',side_effect=capture):
            self.assertEqual(hub_store.GitHub().actor(),'fixture')
            hub_store.GitHub().create('fixture/private-hub','a'*32)
        self.assertEqual(len(observed),2)
        for command,kwargs in observed:
            self.assertEqual(kwargs['env']['GH_HOST'],'github.com')
            self.assertNotIn('GH_DEBUG',kwargs['env'])
            self.assertTrue(kwargs['capture_output'])
        self.assertEqual(observed[0][0][-2:],['--hostname','github.com'])
        self.assertIn('--private',observed[1][0])

    def test_visibility_change_blocks_content_delivery_and_retains_offline_queue(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve();provider=FakeProvider(root/'remotes')
            registry=Registry(root/'registry',provider)
            identifier=registry.create('fixture/private-hub','Private hub')['hub']
            hub=registry.hub(identifier)
            saved=hub.save('note','Private note','PRIVATE CONTENT',offline=True)
            remote=provider.transport({'repository':'fixture/private-hub'})
            before=hub_store.git(remote,'rev-parse','main')
            provider.repos['fixture/private-hub']['private']=False
            real=hub_module.git;pushes=[]
            def watch(repository,*args,**kwargs):
                if args[0]=='push':pushes.append(args)
                return real(repository,*args,**kwargs)
            with patch.object(hub_module,'git',side_effect=watch):
                with self.assertRaisesRegex(hub_store.HubError,'visibility'):hub.sync()
            self.assertEqual(pushes,[])
            self.assertEqual(before,hub_store.git(remote,'rev-parse','main'))
            self.assertEqual(hub.status()['queued'],1)
            self.assertEqual(Path(hub.read(saved['item'])['paths']['BODY.md']).read_text(),'PRIVATE CONTENT')

    def test_local_writing_voice_intake_and_checks_need_no_transport(self):
        with tempfile.TemporaryDirectory() as temporary:
            base=Path(temporary).resolve();root=base/'work';upload=base/'source.md';upload.write_text('Private authored sample.')
            guide=base/'voice.md';guide.write_text('Use a clear voice.')
            exported=io.BytesIO()
            with zipfile.ZipFile(exported,'w') as archive:
                archive.writestr('Profile.csv','Headline,Summary\nWriter,Private background.\n')
                archive.writestr('Contacts.csv','DO NOT INGEST CONTACTS')
            def command(*words):
                args=studio.parser().parse_args(['--root',str(root),*words])
                return getattr(studio,args.group+'_command')(root,args)
            with patch.object(subprocess,'run',side_effect=AssertionError('Unexpected external command')),patch.object(socket,'socket',side_effect=AssertionError('Unexpected network connection')):
                studio.initialize(root)
                source=command('source','add','--name','Sample','--file',str(upload),'--purpose','voice-sample')
                profile=command('profile','create','--name','Writer','--guide-file',str(guide),'--sample',source['id'])
                article=command('article','create','--title','Private working title','--mode','first-draft','--profile',profile['id'])
                command('article','save','--id',article['id'],'--kind','draft','--file',str(upload))
                self.assertEqual(text_checks.lint(upload.read_text(),{})['findings'],[])
                parsed=linkedin_import.parse(exported.getvalue())
            self.assertNotIn('CONTACTS',json.dumps(parsed))
            self.assertEqual((root/'articles'/article['id']/'DRAFT.md').read_text(),'Private authored sample.')

if __name__=='__main__':unittest.main()
