"""Ready references can be rediscovered and pinned across blogs without role leakage."""
from unittest.mock import patch
from test_editorial_tools import Fixture
import studio
import blog_library as library
from hub import Registry
from hub_workspace import Workspace


class ReferenceMemoryTests(Fixture):
    def test_reuse_filters_roles_readiness_and_retirement_and_retains_provenance(self):
        source=self.source('Gateway reference material with an attributed claim.')
        directory,record=studio.item(self.root,'sources',source['id'])
        record.update(origin='https://example.test/gateway/spec',note='Version 2; verify before reuse.')
        studio.persist(directory,'sources',record)
        for purpose in ('manuscript','voice-sample','author-background','inspiration'):
            self.file.write_text('Gateway material for '+purpose)
            self.command('source','add','--name',purpose,'--file',str(self.file),'--purpose',purpose)
        for status in ('pending','unavailable'):
            self.command('source','add','--name','Gateway '+status,'--origin','https://example.test/'+status,'--purpose','reference','--status',status)
        retired=self.source('Gateway retired reference')
        library.curate(self.root,retired['id'],{'curation':'retired'})
        pending=self.source('Gateway pending curation')
        library.curate(self.root,pending['id'],{'curation':'pending'})
        args=studio.parser().parse_args(['--root',str(self.root),'library','find','--query','gateway','--reusable-only','--limit','5'])
        result=library.command(self.root,args)
        self.assertEqual(result['total'],1)
        found=result['items'][0]
        self.assertEqual(found['id'],source['id'])
        self.assertEqual(found['origin'],'https://example.test/gateway/spec')
        self.assertEqual(found['purposes'],['reference'])
        self.assertEqual(found['retrieved_at'],record['retrieved_at'])
        self.assertIn('Version 2',found['limitations'])
        self.assertNotIn('body',found)
        excerpt=library.read_source(self.root,source['id'],query='attributed')
        self.assertEqual(excerpt['sha256'],source['content_sha256'])
        self.assertTrue(excerpt['passages'])
        self.assertGreater(library.catalog(self.root,query='gateway')['total'],1)

    def test_role_change_invalidates_reuse_index_without_content_change(self):
        source=self.source('Gateway retained text.')
        self.assertEqual(library.catalog(self.root,reusable_only=True)['total'],1)
        directory,record=studio.item(self.root,'sources',source['id'])
        record['purposes']=['voice-sample'];studio.persist(directory,'sources',record)
        result=library.catalog(self.root,reusable_only=True)
        self.assertTrue(result['cache_rebuilt']);self.assertEqual(result['total'],0)
        self.assertEqual(library.catalog(self.root)['total'],1)


class SharedReferenceMemoryTests(Fixture):
    def setUp(self):
        super().setUp()
        from hub_fixtures import FakeProvider
        self.provider=FakeProvider(self.base/'remotes');self.registry=Registry(self.base/'hubs',self.provider)
        self.hub_id=self.registry.create('fixture/editorial','Editorial')['hub'];self.hub=self.registry.hub(self.hub_id)
        self.workspace=Workspace(self.root,self.hub)
        active=patch('hub_workspace.active',side_effect=lambda root:self.workspace if root==self.root else self.other_workspace)
        active.start();self.addCleanup(active.stop)
    def test_other_workspace_reuses_retained_doc_and_article_pin_survives_source_update(self):
        source=self.source('The gateway uses version two.')
        shared=self.workspace.publish_selected({'sources':[source['id']]})['items'][0]
        other=self.base/'reference-other';studio.initialize(other)
        registry=Registry(self.base/'reference-registry',self.provider);registry.join('fixture/editorial')
        self.other_workspace=Workspace(other,registry.hub(self.hub_id))
        found=library.catalog(other,query='gateway',reusable_only=True,limit=5)
        self.assertEqual(found['total'],1)
        self.assertEqual(found['items'][0]['location'],'hub')
        self.assertEqual(found['items'][0]['id'],shared['item'])
        local=self.other_workspace._checkout(shared['item'])
        article=studio.article_command(other,studio.parser().parse_args(['--root',str(other),'article','create','--title','Another blog','--mode','outline-only']))
        studio.article_command(other,studio.parser().parse_args(['--root',str(other),'article','attach','--id',article['id'],'--source',local,'--purpose','reference']))
        self.file.write_text('The gateway now uses version three.')
        self.command('source','update','--id',source['id'],'--text-file',str(self.file))
        self.workspace.publish_selected({'sources':[source['id']]});self.other_workspace.hub.refresh()
        refreshed=library.catalog(other,query='gateway',reusable_only=True)
        self.assertNotEqual(refreshed['items'][0]['revision'],shared['revision'])
        self.assertEqual(library.read_source(other,refreshed['items'][0]['id'])['passages'][0]['quote'],'The gateway now uses version three.')
        _,record=studio.item(other,'articles',article['id'])
        self.assertEqual(record['sources'][0]['revision'],1)
        self.assertEqual(studio.item(other,'sources',local)[1]['content_sha256'],source['content_sha256'])
