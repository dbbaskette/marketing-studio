"""Editorial/library/local HTTP behavior using disposable workspaces and Git transports."""
import base64
from contextlib import contextmanager
import http.client
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch, Mock

from hub_fixtures import FakeProvider, SCRIPTS
from hub import Registry
from hub_workspace import Workspace
from hub_store import HubError, encoded, sha, validate_files
import studio
import editorial
import blog_library as library
import management


class Fixture(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve();self.root = self.base / 'writing';studio.initialize(self.root)
        self.file = self.base / 'input.md'
    def command(self, *words):
        args = studio.parser().parse_args(['--root', str(self.root), *words])
        return getattr(studio, args.group + '_command')(self.root, args)
    def article(self, text='Clients send requests to a gateway. The gateway calls the service.'):
        article = self.command('article', 'create', '--title', 'Gateway guide', '--mode', 'first-draft', '--author', 'Avery')
        self.file.write_text(text)
        self.command('article', 'save', '--id', article['id'], '--kind', 'draft', '--file', str(self.file))
        return article['id']
    def source(self, text='The gateway calls the service.'):
        self.file.write_text(text)
        return self.command('source', 'add', '--name', 'Specification', '--file', str(self.file), '--purpose', 'reference')


class EditorialTests(Fixture):
    def test_article_details_derive_next_action_without_mutation(self):
        empty = self.command('article','create','--title','New idea','--mode','outline-only')
        self.assertEqual(management.detail(self.root, empty['id'])['view']['state'], 'empty')
        self.file.write_text('An outline with a clear reader outcome.')
        self.command('article','save','--id',empty['id'],'--kind','outline','--file',str(self.file))
        outline = management.detail(self.root, empty['id'])['view']
        self.assertTrue(outline['stop_reached']);self.assertIn('outline', outline['next_action']['command'])
        ident = self.article('Manuscript text. ' * 2000);directory, record = studio.item(self.root,'articles',ident)
        before = (directory/'session.json').read_bytes()
        result = management.detail(self.root,ident)
        self.assertEqual((directory/'session.json').read_bytes(),before)
        self.assertTrue(result['view']['preview']['truncated']);self.assertLessEqual(len(result['view']['preview']['text']),16000)
        self.assertIn(ident,result['view']['next_action']['command']);self.assertTrue(result['view']['stop_reached'])
        self.assertNotIn('Gather missing',result['view']['next_action']['command'])
        record['stop_point']='review';record['reviews']['proofread']={'status':'current','inputs':studio.fingerprints(self.root,directory,record),'result':{'findings':[]},'checked_at':studio.now()}
        studio.persist(directory,'articles',record)
        editorial.schedule(self.root,ident,{'stage':'ready'})
        ready = management.detail(self.root,ident)['view'];self.assertEqual(ready['stage'],'ready')
        self.assertIn('publication remains',ready['next_action']['command'])
        (directory/'DRAFT.md').write_text('Changed outside Blog Studio.')
        stale = management.detail(self.root,ident)['view']
        self.assertTrue(stale['decision_stale']);self.assertEqual(stale['stage'],'review')
        self.assertIn('no longer current',stale['blocker'])
        self.assertEqual(next(r for r in stale['reviews'] if r['check']=='proofread')['status'],'stale')
        self.assertIsNone(stale['google']);self.assertIn('No saved Google',stale['google_observation'])
        with self.assertRaises(ValueError):management.detail(self.root,ident,'invalid')

    def test_inbox_search_and_exact_finding_detail_keep_article_identity(self):
        ident=self.article();directory,record=studio.item(self.root,'articles',ident)
        source=self.source();self.command('article','attach','--id',ident,'--source',source['id'])
        _,record=studio.item(self.root,'articles',ident)
        record['stop_point']='review'
        record['reviews']['proofread']={'status':'current','inputs':studio.fingerprints(self.root,directory,record),'result':{'findings':[{'message':'Fix gateway punctuation.'}]},'checked_at':studio.now()}
        studio.persist(directory,'articles',record)
        self.assertEqual(editorial.inbox(self.root,query='no-match-ever')['total'],0)
        row=editorial.inbox(self.root,query='punctuation')['items'][0]
        detail=management.finding_detail(self.root,ident,row['key'])
        self.assertEqual(detail['finding']['finding']['message'],'Fix gateway punctuation.')
        self.assertIn(ident,detail['command']);self.assertIn(row['key'],detail['command'])
        self.assertEqual(detail['article']['view']['stop_point'],'review')
        claim='The gateway calls the service.'
        text=(directory/'DRAFT.md').read_text()
        editorial.evidence(self.root,ident,[{'claim':claim,'start':text.index(claim),'status':'insufficient','citations':[{'source':0,'start':0,'quote':claim}]}])
        evidence=editorial.inbox(self.root,query='claim evidence')['items'][0]
        self.assertEqual(management.finding_detail(self.root,ident,evidence['key'])['evidence'][0]['quote'],claim)
        _,record=studio.item(self.root,'articles',ident);record['reviews']['proofread']['result']['findings'][0]['message']='Changed finding'
        studio.persist(directory,'articles',record)
        with self.assertRaisesRegex(ValueError,'changed'):management.finding_detail(self.root,ident,row['key'])

    def test_external_draft_changes_invalidate_readiness_without_mutating_saved_state(self):
        ident = self.article()
        directory, _ = studio.item(self.root, 'articles', ident)
        for stage in ('ready', 'published'):
            editorial.schedule(self.root, ident, {'stage': stage, 'publication_url': 'https://team.example/blog/gateway'})
            saved = (directory / 'session.json').read_bytes()
            (directory / 'DRAFT.md').write_text('External edit after the recorded decision.')
            row = editorial.board(self.root)['items'][0]
            self.assertEqual(row['stage'], 'review')
            self.assertTrue(row['decision_stale'])
            self.assertEqual(editorial.board(self.root, stage=stage)['total'], 0)
            self.assertEqual((directory / 'session.json').read_bytes(), saved)
            self.file.write_text('A newly saved manuscript.')
            self.command('article', 'save', '--id', ident, '--kind', 'draft', '--file', str(self.file))
        editorial.schedule(self.root, ident, {'stage': 'ready'})
        (directory / 'DRAFT.md').unlink()
        self.assertTrue(editorial.board(self.root)['items'][0]['decision_stale'])

    def test_board_explicit_ownership_ready_and_guarded_decisions(self):
        ident = self.article()
        self.assertEqual(editorial.board(self.root)['items'][0]['owner'], 'Unassigned')
        record = editorial.schedule(self.root, ident, {'owner': 'Morgan', 'due': '2020-01-01', 'stage': 'review'})
        row = editorial.board(self.root, owner='Morgan', stage='review')['items'][0]
        self.assertEqual(row['author'], 'Avery');self.assertTrue(row['overdue'])
        with self.assertRaises(ValueError):editorial.schedule(self.root, ident, {'stage': 'published'})
        directory, _ = studio.item(self.root, 'articles', ident)
        expected = sha((directory / 'session.json').read_bytes())
        editorial.schedule(self.root, ident, {'stage': 'ready'})
        with self.assertRaises(ValueError):editorial.schedule(self.root, ident, {'owner': 'Other', 'expected': expected})
        with self.assertRaises(ValueError):editorial.board(self.root, limit=0)
        self.file.write_text('Changed after readiness.');self.command('article', 'save', '--id', ident, '--kind', 'draft', '--file', str(self.file))
        editorial.schedule(self.root, ident, {'owner': 'Other'})
        self.assertEqual(editorial.board(self.root)['items'][0]['stage'], 'review')
    def test_evidence_exact_pinned_references_and_changed_draft(self):
        ident = self.article();source = self.source();self.command('article', 'attach', '--id', ident, '--source', source['id'])
        claim = 'The gateway calls the service.'
        claims = [{'claim': claim, 'start': 35, 'status': 'supported', 'citations': [{'source': 0, 'quote': claim, 'start': 0}]}]
        # Determine the real manuscript offset rather than relying on the fixture wording.
        directory, _ = studio.item(self.root, 'articles', ident);claims[0]['start'] = (directory / 'DRAFT.md').read_text().index(claim)
        editorial.evidence(self.root, ident, claims)
        self.assertEqual(editorial.command(self.root, type('Args', (), {'action': 'assets', 'id': ident})())['items']['evidence']['status'], 'current')
        self.file.write_text('New specification.');self.command('source', 'update', '--id', source['id'], '--text-file', str(self.file))
        # Original pin is still readable and exact; publishing it must not substitute a new source.
        editorial.evidence(self.root, ident, claims)
        bad = json.loads(json.dumps(claims));bad[0]['citations'][0]['quote'] = 'invented'
        with self.assertRaises(ValueError):editorial.evidence(self.root, ident, bad)
        self.file.write_text('Different draft.');self.command('article', 'save', '--id', ident, '--kind', 'draft', '--file', str(self.file))
        self.assertEqual(editorial.derived_status(self.root, directory, studio.item(self.root, 'articles', ident)[1])['evidence']['status'], 'stale')
    def test_inspiration_cannot_support_claims(self):
        ident = self.article();source = self.source();self.command('article', 'attach', '--id', ident, '--source', source['id'], '--purpose', 'inspiration')
        with self.assertRaises(ValueError):editorial.evidence(self.root, ident, [{'claim': 'Clients', 'start': 0, 'status': 'supported', 'citations': [{'source': 0, 'quote': 'The', 'start': 0}]}])
    def test_companions_are_bounded_grounded_and_stale_after_tampering(self):
        ident = self.article();quote = 'The gateway calls the service.'
        record = editorial.package(self.root, ident, {'channels': [{'name': 'Social', 'text': 'A gateway guide', 'max_characters': 5, 'manuscript_quotes': [quote]}]})
        directory, _ = studio.item(self.root, 'articles', ident)
        package = studio.read_json(directory / 'derived/publication-package.json')['content']
        self.assertTrue(package['missing_publication_url']);self.assertTrue(package['channels'][0]['over_limit'])
        editorial.visual(self.root, ident, {'type': 'diagram', 'content': 'flowchart LR\nGateway --> Service', 'caption': 'Request path', 'alt': quote, 'manuscript_quotes': [quote]})
        with self.assertRaises(ValueError):editorial.visual(self.root, ident, {'type': 'diagram', 'content': 'click Gateway "https://outside.invalid"', 'caption': 'x', 'alt': 'x', 'manuscript_quotes': [quote]})
        (directory / 'derived/visual-companion.json').write_text('{}')
        self.assertEqual(editorial.derived_status(self.root, directory, studio.item(self.root, 'articles', ident)[1])['visual-companion']['status'], 'stale')
    def test_inbox_keeps_local_findings_when_google_read_is_unavailable(self):
        ident = self.article();directory, record = studio.item(self.root, 'articles', ident)
        record['google'] = {'baselines': {'draft': {'document': {'document_id': 'fixture', 'url': 'https://docs.google.com/document/d/fixture/edit'}}}}
        record['reviews']['proofread'] = {'status': 'current', 'inputs': studio.fingerprints(self.root, directory, record), 'result': {'findings': [{'message': 'Improve punctuation.'}]}, 'checked_at': studio.now()}
        studio.persist(directory, 'articles', record)
        from google_drive import GoogleError
        client = Mock();client.docs_get.side_effect = GoogleError('unavailable');client.review_comments.side_effect = GoogleError('unavailable')
        with patch('google_suggestions.review_read', side_effect=GoogleError('unavailable')):
            result = editorial.inbox(self.root, ident, online=True, client=client)
        self.assertTrue(any(r['kind'] == 'proofread' for r in result['items']))
        self.assertTrue(any(r['kind'] == 'Google review' and r['status'] == 'unavailable' for r in result['items']))
        self.assertFalse(client.create_review_comment.called)
        with patch('google_suggestions.review_read', side_effect=GoogleError('unavailable')):
            client.review_comments.side_effect=None;client.review_comments.return_value=[{'content':'Please clarify this.', 'resolved':False}]
            result=editorial.inbox(self.root, ident, online=True, client=client)
            self.assertTrue(any(r['kind']=='Google comment' for r in result['items']))
        with self.assertRaises(ValueError):editorial.inbox(self.root, online=True)


class LibraryTests(Fixture):
    def test_catalog_releases_database_resources_after_success_and_failure(self):
        self.collection()
        library.import_batch(self.root, library.preview(self.root, 'team-a')['preview'], delay=0)
        connect = library.sqlite3.connect
        connections = []
        def observed_connect(*args, **kwargs):
            connection = connect(*args, **kwargs)
            connections.append(connection)
            self.addCleanup(connection.close)
            return connection
        with patch.object(library.sqlite3, 'connect', side_effect=observed_connect):
            self.assertEqual(library.catalog(self.root)['total'], 1)
            with self.assertRaises(library.sqlite3.ProgrammingError):
                library.catalog(self.root, since={'invalid': 'filter'})
        self.assertEqual(len(connections), 2)
        for connection in connections:
            with self.assertRaisesRegex(library.sqlite3.ProgrammingError, 'closed'):
                connection.execute('SELECT 1')
        self.assertEqual(library.catalog(self.root, query='routing')['total'], 1)

    def test_atom_selects_the_article_link_independently_of_link_order(self):
        html = '<link rel="alternate" type="text/html" href="https://team.example/blog/article"/>'
        self_link = '<link rel="self" type="application/atom+xml" href="https://team.example/api/article"/>'
        enclosure = '<link rel="enclosure" href="https://team.example/media/article.mp3"/>'
        alternate = '<link rel="alternate" type="application/json" href="https://team.example/api/article.json"/>'
        for links in (html + self_link + enclosure, enclosure + self_link + html,
                      html + alternate, alternate + html, html.replace('rel="alternate" ', '') + self_link):
            feed = ('<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>article</id><title>Article</title>'
                    '<author><name>Avery</name><uri>https://team.example/authors/avery</uri><email>avery@example.test</email></author>'
                    + links + '</entry></feed>').encode()
            entries, excluded, _ = library.parse_discovery(feed, 'feed', 'https://team.example/feed', 'https://team.example/blog')
            self.assertEqual([entry['url'] for entry in entries], ['https://team.example/blog/article'])
            self.assertEqual(excluded, [])
            self.assertEqual(entries[0]['external_id'], 'article')
            self.assertEqual(entries[0]['author'], 'Avery')
        feed = ('<feed xmlns="http://www.w3.org/2005/Atom"><entry>' + self_link + enclosure + '</entry></feed>').encode()
        entries, _, _ = library.parse_discovery(feed, 'feed', 'https://team.example/feed', 'https://team.example')
        self.assertEqual(entries, [])

    # Inherit fixture helpers, without re-running editorial cases below.
    def collection(self, key='team-a', entries=None):
        path = self.base / (key + '.json');path.write_text(json.dumps(entries or [{'external_id': key + '-1', 'title': 'Request routing', 'text': 'Gateway routes requests.\n\nVersion 1 had this behavior.', 'author': 'Avery', 'published': '2020-01-01', 'topics': ['routing'], 'products': ['Product A']}]))
        library.setup(self.root, {'key': key, 'name': key, 'type': 'export', 'path': str(path)})
        return path
    def test_import_two_generic_collections_idempotency_updates_retirement_and_catalog(self):
        path = self.collection();self.collection('team-b')
        first = library.preview(self.root, 'team-a');result = library.import_batch(self.root, first['preview'], delay=0)
        self.assertEqual(result['counts']['imported'], 1)
        library.import_batch(self.root, library.preview(self.root, 'team-b')['preview'], delay=0)
        result = library.import_batch(self.root, library.preview(self.root, 'team-a')['preview'], delay=0)
        self.assertEqual(result['counts']['unchanged'], 1)
        found = library.catalog(self.root, query='routes', author='Avery', topic='routing', product='Product A', collection='team-a', since='2019-01-01', until='2021-01-01')
        self.assertEqual(found['total'], 1);self.assertTrue(found['items'][0]['historical'])
        ident = found['items'][0]['id'];old_hash = found['items'][0]['sha256']
        data = json.loads(path.read_text());data[0]['text'] = 'Gateway routes updated requests.';data[0]['url'] = 'https://team.example/blog/new';path.write_text(json.dumps(data))
        result = library.import_batch(self.root, library.preview(self.root, 'team-a')['preview'], delay=0)
        self.assertEqual(result['counts']['updated'], 1)
        directory, record = studio.item(self.root, 'sources', ident)
        self.assertEqual(studio.read_json(directory / 'revisions/1/record.json')['content_sha256'], old_hash)
        library.curate(self.root, ident, {'curation': 'retired'})
        self.assertEqual(library.catalog(self.root, collection='team-a')['total'], 0)
        self.assertEqual(library.catalog(self.root, collection='team-a', include_retired=True)['total'], 1)
    def test_batched_failed_import_resume_and_unknown_authors(self):
        self.collection(entries=[{'external_id': 'one', 'title': 'First', 'text': 'Good text.'}, {'external_id': 'two', 'title': 'Second', 'text': 3}, {'external_id': 'three', 'title': 'Third', 'text': 'More text.'}])
        preview = library.preview(self.root, 'team-a')['preview']
        result = library.import_batch(self.root, preview, limit=2, delay=0)
        self.assertEqual(result['counts']['failed'], 1);self.assertEqual(result['remaining'], 1)
        result = library.import_batch(self.root, preview, limit=2, delay=0)
        self.assertEqual(result['counts']['imported'], 2);self.assertEqual(result['remaining'], 0)
        self.assertIsNone(library.catalog(self.root)['items'][0]['author'])
        self.assertEqual(list((self.root / 'articles').iterdir()), [])
    def test_feed_atom_sitemap_archive_scoping_and_malformed_discovery(self):
        scope = 'https://team.example/blog'
        rss = b'<rss><channel><item><title>Post</title><link>https://team.example/blog/one</link><guid>stable-id</guid><author>Avery</author></item><item><link>https://other.example/secret</link></item></channel></rss>'
        rows, excluded, _ = library.parse_discovery(rss, 'feed', scope, scope)
        self.assertEqual(rows[0]['identity'], 'stable-id');self.assertEqual(rows[0]['author'], 'Avery');self.assertEqual(len(excluded), 1)
        atom = b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Post</title><link href="/blog/one"/><id>post-1</id></entry></feed>'
        self.assertEqual(library.parse_discovery(atom, 'feed', scope, scope)[0][0]['url'], scope + '/one')
        sitemap = b'<urlset><url><loc>https://team.example/blog/one</loc></url></urlset>'
        self.assertEqual(len(library.parse_discovery(sitemap, 'sitemap', scope, scope)[0]), 1)
        archive = b'<a href="/blog/one">One</a><a href="/blog/one">Duplicate</a><a href="/admin">Out</a>'
        self.assertEqual(len(library.parse_discovery(archive, 'archive', scope, scope)[0]), 1)
        with self.assertRaises(ValueError):library.parse_discovery(b'<sitemapindex/>', 'sitemap', scope, scope)
    def test_public_network_guard_pins_address_and_rejects_redirect_escape(self):
        address = [(2, 1, 6, '', ('127.0.0.1', 443))]
        with patch.object(library.socket, 'getaddrinfo', return_value=address), patch.object(library, 'PinnedHTTPS') as connection:
            with self.assertRaises(ValueError):library.fetch('https://team.example/blog/a', 'https://team.example/blog')
            connection.assert_not_called()
        with patch.object(library.socket, 'getaddrinfo', return_value=[(2, 1, 6, '', ('8.8.8.8', 443))]), patch.object(library, 'PinnedHTTPS') as connection:
            response = connection.return_value.getresponse.return_value;response.status = 302;response.getheader.return_value = 'https://private.example/secret'
            with self.assertRaises(ValueError):library.fetch('https://team.example/blog/a', 'https://team.example/blog')
            connection.assert_called_once_with('team.example', '8.8.8.8')
        self.assertFalse(library.in_scope('https://team.example/blogging/a', 'https://team.example/blog'))
        private_response = [(2, 1, 6, '', ('169.254.169.254', 443))]
        with patch.object(library.socket, 'getaddrinfo', return_value=private_response):
            with self.assertRaises(ValueError):library.fetch('https://team.example/blog/a', 'https://team.example/blog')
        with self.assertRaises(ValueError):library.canonical('https://user:password@team.example/blog')
    def test_two_independent_teams_share_no_collection_content(self):
        provider=FakeProvider(self.base/'two-team-remotes');adapters={}
        for team in ('first','second'):
            root=self.base/team;studio.initialize(root)
            registry=Registry(self.base/(team+'-hubs'),provider)
            hub_id=registry.create('fixture/'+team,team)['hub'];adapters[root]=Workspace(root,registry.hub(hub_id))
        with patch('hub_workspace.active',side_effect=lambda root:adapters.get(root)):
            for root,adapter in adapters.items():
                export=self.base/(root.name+'-export.json');export.write_text(json.dumps([{'external_id':'same-external-id','title':root.name+' blog','text':root.name+' private collection'}]))
                library.setup(root,{'key':'old-posts','name':'Old posts','type':'export','path':str(export)})
                library.import_batch(root,library.preview(root,'old-posts')['preview'],delay=0)
            first=self.base/'first';second=self.base/'second'
            self.assertEqual(library.catalog(first,query='second')['total'],0)
            self.assertEqual(library.catalog(second,query='first')['total'],0)
            refs=[library.source_rows(root)[0]['binding']['item'] for root in (first,second)]
            self.assertNotEqual(*refs)

    def test_malformed_discovery_and_escaping_source_files_fail_closed(self):
        with self.assertRaisesRegex(ValueError,'Malformed'):library.parse_discovery(b'<broken', 'feed', 'https://team.example/blog', 'https://team.example/blog')
        source=self.source();directory,_=studio.item(self.root,'sources',source['id'])
        outside=self.base/'outside-secret.txt';outside.write_text('Not authorized as a source.')
        (directory/'content.md').unlink();(directory/'content.md').symlink_to(outside)
        with self.assertRaises(ValueError):library.catalog(self.root)

    def test_large_fixture_has_bounded_retrieval_and_rebuildable_index(self):
        self.collection(entries=[{'external_id': 'post-' + str(n), 'title': 'Post ' + str(n), 'text': 'A technical example for routing.\n\n' + 'Retained evidence. ' * 50} for n in range(125)])
        preview = library.preview(self.root, 'team-a')['preview'];start = time.monotonic()
        for _ in range(5):library.import_batch(self.root, preview, delay=0)
        result = library.catalog(self.root, query='routing', limit=3)
        self.assertEqual(result['total'], 125);self.assertEqual(len(result['items']), 3)
        self.assertLess(len(json.dumps(result)), 6000)
        read = library.read_source(self.root, result['items'][0]['id'], query='routing', max_chars=200)
        self.assertLessEqual(sum(len(p['quote']) for p in read['passages']), 200)
        (self.root / '.derived-cache/library.sqlite3').unlink()
        self.assertTrue(library.catalog(self.root, limit=3)['cache_rebuilt'])
        self.assertLess(time.monotonic() - start, 20)


class HubEditorialTests(Fixture):
    def setUp(self):
        super().setUp()
        self.provider = FakeProvider(self.base / 'remotes');self.registry = Registry(self.base / 'hubs', self.provider)
        self.hub_id = self.registry.create('fixture/editorial', 'Editorial')['hub'];self.hub = self.registry.hub(self.hub_id)
        self.workspace = Workspace(self.root, self.hub)
        self.active_patch = patch('hub_workspace.active', side_effect=lambda root:self.workspace if root == self.root else self.other_workspace)
        self.active_patch.start();self.addCleanup(self.active_patch.stop)
    def test_shared_preview_conflict_and_newer_revision_offer_safe_continuation(self):
        ident=self.article();directory,record=studio.item(self.root,'articles',ident)
        record['reviews']['proofread']={'status':'current','inputs':studio.fingerprints(self.root,directory,record),'result':{'findings':[{'message':'Inspect saved punctuation.'}]}}
        studio.persist(directory,'articles',record)
        shared=self.workspace.publish_selected({'articles':[ident]})['items'][0]
        result=management.detail(self.root,shared['item'],'hub')
        self.assertIn('gateway',result['view']['preview']['text'])
        self.assertEqual(result['view']['reviews'][0]['status'],'needs-local-check')
        self.assertIn(shared['item'],result['view']['next_action']['command'])
        finding=editorial.inbox(self.root,shared_id=shared['item'])['items'][0]
        self.assertEqual(management.finding_detail(self.root,shared['item'],finding['key'],'hub')['finding']['location'],'hub')
        original=self.hub.read(shared['item'])['record']
        newer=self.hub.save('article',original['title'],'A newer draft',item=shared['item'],parents=[shared['revision']],data=original['data'],artifacts={'DRAFT.md':(b'A newer draft','text')},sync=False)
        self.assertTrue(management.detail(self.root,ident)['view']['shared_newer'])
        self.hub.save('article',original['title'],'Another branch',item=shared['item'],parents=[shared['revision']],data=original['data'],artifacts={'DRAFT.md':(b'Another branch','text')},sync=False)
        conflict=management.detail(self.root,shared['item'],'hub')['view']
        self.assertTrue(conflict['conflict']);self.assertIn('Compare competing',conflict['next_action']['command'])
        with self.assertRaises(ValueError):management.detail(self.root,shared['item'],'hub',shared['revision'])

    def test_shared_curation_refreshes_and_rejects_changed_head_before_checkout(self):
        source = self.source();shared = self.workspace.publish_selected({'sources': [source['id']]})['items'][0]
        other = self.base / 'curation-other';studio.initialize(other)
        registry = Registry(self.base / 'curation-registry', self.provider);registry.join('fixture/editorial')
        self.other_workspace = Workspace(other, registry.hub(self.hub_id))
        detail = management.source_detail(other, shared['item'], 'hub')
        library.curate(self.root, source['id'], {'topics': ['changed-by-member']})
        newest = self.workspace.publish_selected({'sources': [source['id']]})['items'][0]
        with self.assertRaises(management.CurationConflict):
            management.dispatch(other, 'curate', {'id': shared['item'], 'location': 'hub', 'expected': detail['expected'], 'note': 'Old form'})
        self.assertEqual(list((other / 'sources').iterdir()), [])
        self.assertEqual(self.other_workspace.hub.graph()['heads'][shared['item']], [newest['revision']])
        current = management.source_detail(other, shared['item'], 'hub')
        result = management.dispatch(other, 'curate', {'id': shared['item'], 'location': 'hub', 'expected': current['expected'], 'note': 'Explicit resubmission'})
        self.assertEqual(result['note'], 'Explicit resubmission')
        self.assertEqual(result['library']['topics'], ['changed-by-member'])

    def test_local_form_rejects_new_shared_head_and_unshared_edits_are_protected(self):
        source = self.source();shared = self.workspace.publish_selected({'sources': [source['id']]})['items'][0]
        old = management.source_detail(self.root, source['id'])
        other = self.base / 'curation-member';studio.initialize(other)
        registry = Registry(self.base / 'curation-member-registry', self.provider);registry.join('fixture/editorial')
        self.other_workspace = Workspace(other, registry.hub(self.hub_id))
        other_id = self.other_workspace._checkout(shared['item'])
        library.curate(other, other_id, {'note': 'New shared note'})
        self.other_workspace.publish_selected({'sources': [other_id]})
        with self.assertRaises(management.CurationConflict):
            management.dispatch(self.root, 'curate', {'id': source['id'], 'expected': old['expected'], 'note': 'Old local form'})
        self.assertEqual(studio.item(self.root, 'sources', source['id'])[1]['note'], '')
        latest = management.source_detail(self.root, source['id'])
        self.assertEqual(latest['location'], 'hub')
        self.assertEqual(latest['record']['note'], 'New shared note')
        # A form inspecting shared metadata must never overwrite preexisting local changes.
        self.workspace._checkout(shared['item'])
        local_id = next(k.split('/', 1)[1] for k,v in self.workspace.state['items'].items() if k.startswith('sources/') and v['item'] == shared['item'] and k != 'sources/' + source['id'])
        library.curate(self.root, local_id, {'note': 'Unshared local note'})
        snapshot = management.source_detail(self.root, shared['item'], 'hub')
        with self.assertRaises(management.CurationConflict):
            management.dispatch(self.root, 'curate', {'id': shared['item'], 'location': 'hub', 'expected': snapshot['expected'], 'note': 'Shared form replacement'})
        self.assertEqual(studio.item(self.root, 'sources', local_id)[1]['note'], 'Unshared local note')

    def test_shared_inbox_excludes_closed_findings_but_keeps_open_and_stale_work(self):
        ident = self.article()
        directory, record = studio.item(self.root, 'articles', ident)
        closed = [{'status': status, 'message': 'Handled finding.'} for status in ('resolved', 'dismissed', 'applied')]
        record['reviews']['proofread'] = {'status': 'current', 'inputs': studio.fingerprints(self.root, directory, record),
                                          'result': {'findings': closed}, 'checked_at': studio.now()}
        studio.persist(directory, 'articles', record)
        self.workspace.publish_selected({'articles': [ident]})
        other = self.base / 'other-inbox';studio.initialize(other)
        registry = Registry(self.base / 'other-inbox-registry', self.provider);registry.join('fixture/editorial')
        self.other_workspace = Workspace(other, registry.hub(self.hub_id))
        self.assertEqual(editorial.inbox(other)['total'], 0)
        record['reviews']['proofread']['result']['findings'] = closed + [{'message': 'Still needs attention.'}]
        studio.persist(directory, 'articles', record);self.workspace.publish_selected({'articles': [ident]})
        self.other_workspace.hub.refresh()
        self.assertEqual(editorial.inbox(other)['items'][0]['kind'], 'proofread')
        record['reviews']['proofread'].update(status='stale', result={'findings': closed})
        studio.persist(directory, 'articles', record);self.workspace.publish_selected({'articles': [ident]})
        self.other_workspace.hub.refresh()
        self.assertEqual(editorial.inbox(other)['items'][0]['status'], 'stale')

    def test_shared_board_generated_pages_manual_edits_and_source_pins(self):
        ident = self.article();source = self.source();self.command('article', 'attach', '--id', ident, '--source', source['id'])
        claim='The gateway calls the service.'
        directory,_=studio.item(self.root,'articles',ident)
        editorial.evidence(self.root,ident,[{'claim':claim,'start':(directory/'DRAFT.md').read_text().index(claim),'status':'supported','citations':[{'source':0,'quote':claim,'start':0}]}])
        self.file.write_text('A new specification.');self.command('source', 'update', '--id', source['id'], '--text-file', str(self.file))
        editorial.schedule(self.root, ident, {'owner': 'Morgan', 'stage': 'review'})
        result = self.workspace.publish_selected({'articles': [ident]});reference = result['items'][0]
        files = self.hub.files();self.assertIn('editorial/README.md', files);self.assertIn(b'Morgan', files['editorial/README.md'])
        self.assertEqual(self.hub.graph()['manifest']['minimum_runtime'], '1.12.3')
        other = self.base / 'other';studio.initialize(other)
        registry_b = Registry(self.base / 'other-hubs', self.provider);registry_b.join('fixture/editorial')
        self.other_workspace = Workspace(other, registry_b.hub(self.hub_id))
        self.assertEqual(editorial.board(other)['items'][0]['location'], 'hub')
        bid = self.other_workspace._checkout(reference['item'])
        _, record = studio.item(other, 'articles', bid)
        pinned_dir, _ = studio.item(other, 'sources', record['sources'][0]['source_id'])
        self.assertEqual((pinned_dir / 'content.md').read_text(), 'The gateway calls the service.')
        imported_dir,imported=studio.item(other,'articles',bid)
        self.assertEqual(editorial.derived_status(other,imported_dir,imported)['evidence']['status'],'current')
        import hub_browse
        broken = dict(files);broken['editorial/README.md'] = b'manual edit'
        with self.assertRaises(HubError):hub_browse.verify(broken, validate_files(broken, 'fixture/editorial'))
    def test_library_rebuild_by_second_member_and_lesson_promotion_staleness(self):
        entries = [{'external_id': 'post-1', 'title': 'Prior blog', 'url': 'https://team.example/blog/one', 'text': 'Explain a concrete request before the mechanism.'}]
        export = self.base / 'export.json';export.write_text(json.dumps(entries))
        library.setup(self.root, {'key': 'old-posts', 'name': 'Old posts', 'type': 'export', 'path': str(export)})
        result = library.import_batch(self.root, library.preview(self.root, 'old-posts')['preview'], delay=0)
        self.assertEqual(result['counts']['imported'], 1)
        self.assertIn('collections/README.md', self.hub.files())
        other = self.base / 'other';studio.initialize(other);rb = Registry(self.base / 'other-hubs', self.provider);rb.join('fixture/editorial');self.other_workspace = Workspace(other, rb.hub(self.hub_id))
        found = library.catalog(other, query='concrete');self.assertEqual(found['total'], 1);self.assertEqual(found['items'][0]['location'], 'hub')
        source = library.source_rows(self.root)[0]['binding']
        candidate = library.lesson(self.root, {'title': 'Start with an example', 'type': 'recommendation', 'text': 'Consider showing a request first.', 'references': [{**source, 'quote': 'Explain a concrete request'}]})
        saved = self.hub.graph()['revisions'][candidate['revision']]
        self.assertEqual(library.lesson_state(self.workspace, saved), 'current')
        approved = library.lesson(self.root, {'item': candidate['item']}, True)
        self.assertEqual(self.hub.graph()['revisions'][approved['revision']]['kind'], 'rule')
        entries[0]['text'] = 'A revised prior blog.';export.write_text(json.dumps(entries))
        library.import_batch(self.root, library.preview(self.root, 'old-posts')['preview'], delay=0)
        self.assertEqual(library.lesson_state(self.workspace, saved), 'stale')
        with self.assertRaises(ValueError):library.lesson(self.root, {'item': candidate['item']}, True)
    def test_retry_requeues_a_locally_retained_post_after_sharing_failure(self):
        export=self.base/'retry-export.json';export.write_text(json.dumps([{'external_id':'retry-post','title':'Retained post','text':'Retained private reference.'}]))
        library.setup(self.root,{'key':'retry','name':'Retry collection','type':'export','path':str(export)})
        preview=library.preview(self.root,'retry')['preview']
        with patch.object(self.workspace,'_publish',side_effect=HubError('Fixture outbox unavailable.')):
            result=library.import_batch(self.root,preview,delay=0)
        self.assertEqual(result['counts']['failed'],1)
        self.assertEqual(len(list((self.root/'sources').iterdir())),1)
        result=library.import_batch(self.root,preview,retry=True,delay=0)
        self.assertEqual(result['counts']['failed'],0)
        self.assertEqual(result['counts']['unchanged'],1)
        graph=self.hub.graph()
        self.assertEqual(sum(graph['revisions'][heads[0]]['kind']=='source' for heads in graph['heads'].values()),1)

    def test_receipts_report_partial_upload_and_retry_without_duplicate_mutations(self):
        data = {'operation': 'd' * 32, 'filename': 'receipt.md', 'content': base64.b64encode(b'Retained draft.').decode(), 'as_blog': True}
        publish = self.workspace.publish_mutation
        def partial(group, record):
            if group == 'article':raise OSError('Fixture transport unavailable.')
            return publish(group, record)
        with patch.object(self.workspace, 'publish_mutation', side_effect=partial):
            saved = management.dispatch(self.root, 'upload', data)
        self.assertEqual([r['sharing'] for r in saved['receipts']], ['shared', 'local-saved-not-shared'])
        pending = management.receipts(self.root)['items']
        failed = next(r for r in pending if r['sharing'] == 'local-saved-not-shared')
        before = len(self.hub.graph()['revisions'])
        result = management.dispatch(self.root, 'retry-sync', {'id': failed['id']})
        self.assertEqual(result['receipts'][0]['sharing'], 'shared')
        after = len(self.hub.graph()['revisions'])
        self.assertEqual(after, before + 1)
        management.dispatch(self.root, 'retry-sync', {'id': failed['id']})
        self.assertEqual(len(self.hub.graph()['revisions']), after)
        self.assertEqual(len(list((self.root / 'articles').iterdir())), 1)
        self.assertEqual(len(list((self.root / 'sources').iterdir())), 1)

    def test_receipts_keep_review_queue_and_reject_changed_unqueued_checkpoint(self):
        self.provider.review = True
        saved = management.dispatch(self.root, 'memory', {'kind':'note', 'title':'Context', 'body':'Fixture', 'operation':'e'*32})
        self.assertEqual(saved['receipts'][0]['sharing'], 'pending-review')
        retried = management.dispatch(self.root, 'retry-sync', {'id':saved['receipts'][0]['id']})
        self.assertEqual(retried['receipts'][0]['sharing'], 'pending-review')
        self.provider.merge_review(*next(iter(self.provider.prs)))
        # The actual contribution branch is recorded in the intent; no provider identity is changed.
        self.hub.refresh()
        self.assertEqual(management.receipts(self.root)['items'][0]['sharing'], 'shared')
        self.provider.review = False
        data = {'operation':'f'*32,'filename':'source.md','content':base64.b64encode(b'Source').decode()}
        with patch.object(self.workspace, 'publish_mutation', side_effect=OSError('Fixture unavailable')):
            upload = management.dispatch(self.root, 'upload', data)
        library.curate(self.root, upload['source']['id'], {'note':'Newer work'})
        with self.assertRaisesRegex(ValueError, 'changed'):
            management.dispatch(self.root, 'retry-sync', {'id':upload['receipts'][0]['id']})

    def test_memory_details_support_each_kind_and_protect_specialized_records(self):
        for kind in ('note', 'context', 'rule', 'decision'):
            with self.subTest(kind=kind):
                saved = self.hub.save(kind, kind.title(), 'Saved body', sync=False)
                result = management.memory_detail(self.root, saved['item'], saved['revision'])
                self.assertEqual(result['record']['kind'], kind)
                self.assertEqual(result['body'], 'Saved body')
                self.assertEqual(result['editable'], kind != 'decision')
                if kind == 'decision':
                    with self.assertRaisesRegex(ValueError, 'read-only'):
                        management.dispatch(self.root, 'memory', {'item':saved['item'], 'revision':saved['revision'], 'kind':'note', 'title':'Converted', 'body':'Changed'})
                    self.assertEqual(self.hub.read(saved['item'])['record']['kind'], 'decision')
        for marker in ('collection', 'lesson'):
            saved = self.hub.save('context', marker, 'Focused body', data={marker:{'fixture':True}}, sync=False)
            result = management.memory_detail(self.root, saved['item'])
            self.assertFalse(result['editable']);self.assertIn(marker, result['read_only_reason'].casefold())
            with self.assertRaisesRegex(ValueError, 'focused'):
                management.dispatch(self.root, 'memory', {'item':saved['item'], 'revision':saved['revision'], 'kind':'context', 'title':marker, 'body':'Changed'})

    def test_provider_distinguishes_expired_authentication_from_transport_failure(self):
        from hub_store import GitHub, AuthenticationError, TransportError
        from types import SimpleNamespace
        for stderr, expected in ((b'HTTP 401: Bad credentials', AuthenticationError),(b'Network unavailable',TransportError)):
            with patch('hub_store.subprocess.run', return_value=SimpleNamespace(returncode=1,stdout=b'',stderr=stderr)):
                with self.assertRaises(expected):GitHub().lookup('fixture/editorial')

    def test_read_only_refresh_and_capability_states_do_not_authorize_writes(self):
        from hub_store import AuthenticationError, TransportError
        self.assertEqual(management.capabilities(self.root)['status'], 'writable')
        self.provider.repos['fixture/editorial']['write'] = False
        result = management.capabilities(self.root)
        self.assertEqual(result['status'], 'read-only');self.assertTrue(result['actions']['refresh'])
        self.assertFalse(result['actions']['edit']);self.assertTrue(management.dispatch(self.root, 'refresh', {})['fresh'])
        with self.assertRaises(ValueError):management.dispatch(self.root, 'upload', {})
        for failure, status in ((AuthenticationError('Expired'), 'access-expired'), (TransportError('Offline'), 'unavailable')):
            with patch.object(self.provider, 'lookup', side_effect=failure):
                result = management.capabilities(self.root)
                self.assertEqual(result['status'], status);self.assertFalse(any(result['actions'].values()))
                with self.assertRaises(HubError):management.dispatch(self.root, 'refresh', {})
        self.provider.repos['fixture/editorial']['private'] = False
        self.assertEqual(management.capabilities(self.root)['status'], 'identity-mismatch')
        with self.assertRaises(HubError):management.dispatch(self.root, 'refresh', {})
        self.provider.repos['fixture/editorial']['private'] = True
        self.provider.repos['fixture/editorial']['repository'] = 'fixture/changed'
        self.assertEqual(management.capabilities(self.root)['status'], 'identity-mismatch')
        with self.assertRaises(HubError):management.authorize_write(self.root)

    def test_one_access_level_uses_fresh_github_permissions(self):
        self.assertEqual(management.authorize_write(self.root), self.workspace)
        self.provider.repos['fixture/editorial']['write'] = False
        with self.assertRaises(ValueError):management.authorize_write(self.root)
        self.provider.repos['fixture/editorial']['write'] = True
        self.provider.repos['fixture/editorial']['private'] = False
        with self.assertRaises(HubError):management.authorize_write(self.root)


class CurationConflictTests(Fixture):
    def test_stale_forms_preserve_tags_notes_retirement_and_source_pins(self):
        for change in ({'topics': ['new-topic']}, {'note': 'A newer note'}, {'curation': 'retired'}):
            with self.subTest(change=change):
                source = self.source();ident = self.article()
                self.command('article', 'attach', '--id', ident, '--source', source['id'])
                before = management.source_detail(self.root, source['id'])
                updated = library.curate(self.root, source['id'], change)
                directory, _ = studio.item(self.root, 'sources', source['id'])
                history = list((directory / 'revisions').iterdir())
                with self.assertRaises(management.CurationConflict):
                    management.dispatch(self.root, 'curate', {'id': source['id'], 'expected': before['expected'], 'topics': ['old-proposal']})
                self.assertEqual(studio.item(self.root, 'sources', source['id'])[1], updated)
                self.assertEqual(list((directory / 'revisions').iterdir()), history)
                _, article = studio.item(self.root, 'articles', ident)
                self.assertEqual(article['sources'][0]['revision'], source['revision'])
                self.assertEqual(studio.read_json(directory / 'revisions' / str(source['revision']) / 'record.json'), source)
                current = management.source_detail(self.root, source['id'])
                saved = management.dispatch(self.root, 'curate', {'id': source['id'], 'expected': current['expected'], 'topics': ['explicit-proposal']})
                self.assertEqual(saved['library']['topics'], ['explicit-proposal'])

    def test_second_editor_and_missing_guard_cannot_mutate(self):
        source = self.source();detail = management.source_detail(self.root, source['id'])
        proposal = {'id': source['id'], 'expected': detail['expected'], 'note': 'First editor'}
        management.dispatch(self.root, 'curate', proposal)
        with self.assertRaises(management.CurationConflict):management.dispatch(self.root, 'curate', dict(proposal, note='Second editor'))
        with self.assertRaises(management.CurationConflict):management.dispatch(self.root, 'curate', {'id': source['id'], 'note': 'Missing guard'})
        self.assertEqual(studio.item(self.root, 'sources', source['id'])[1]['note'], 'First editor')


class ManagementTests(Fixture):
    def start_server(self):
        server, url = management.server(self.root)
        thread = threading.Thread(target=server.serve_forever, daemon=True);thread.start()
        self.addCleanup(server.server_close);self.addCleanup(server.shutdown)
        return server, url.split('#')[1]
    def request(self, server, token, path='/api/board', method='GET', data=None, headers=None):
        connection = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=5)
        payload = json.dumps(data) if data is not None else None
        fields = {'X-Blog-Studio-Token': token}
        if payload:fields['Content-Type'] = 'application/json'
        fields.update(headers or {});connection.request(method, path, payload, fields);response = connection.getresponse();body = response.read();connection.close()
        return response.status, json.loads(body) if response.getheader('Content-Type') == 'application/json' else body
    def test_http_auth_host_origin_paths_and_page(self):
        self.article();server, token = self.start_server()
        self.assertEqual(self.request(server, token)[0], 200)
        self.assertEqual(self.request(server, token, '/api/capabilities')[1]['status'],'local-only')
        self.assertEqual(self.request(server, token, '/api/inbox?query=no-match-ever')[1]['total'],0)
        self.assertEqual(self.request(server, 'bad', '/api/capabilities')[0],400)
        self.assertEqual(self.request(server, 'bad', '/api/finding?id=fixture&key=fixture')[0],400)
        self.assertEqual(self.request(server, 'bad')[0], 400)
        self.assertEqual(self.request(server, token, headers={'Origin': 'https://outside.example'})[0], 400)
        self.assertEqual(self.request(server, token, headers={'Host': 'outside.example'})[0], 400)
        self.assertEqual(self.request(server, token, '/../../private')[0], 404)
        status, page = self.request(server, token, '/')
        self.assertEqual(status, 200);self.assertIn(b'Editorial desk', page)
        self.assertEqual(self.request(server, token, '/api/upload', 'POST', data={}, headers={'Content-Length': str(management.MAX_BODY+1)})[0], 400)
        self.assertEqual(self.request(server, token, '/api/upload', 'POST', data={}, headers={'Content-Type':'text/plain'})[0], 400)
        self.assertEqual(self.request(server, 'bad', '/api/upload', 'POST', data={})[0], 400)
    def test_http_curation_conflict_returns_409_without_overwrite(self):
        source = self.source();snapshot = management.source_detail(self.root, source['id'])
        library.curate(self.root, source['id'], {'note': 'Newest note'})
        server, token = self.start_server()
        status, body = self.request(server, token, '/api/curate', 'POST', {'id': source['id'], 'expected': snapshot['expected'], 'note': 'Old proposal'})
        self.assertEqual(status, 409);self.assertEqual(body['code'], 'source-conflict')
        self.assertEqual(studio.item(self.root, 'sources', source['id'])[1]['note'], 'Newest note')

    def test_upload_idempotency_original_preservation_and_pending_pdf(self):
        data = {'operation': 'a' * 32, 'filename': 'draft.md', 'content': base64.b64encode(b'A draft with a clear argument.').decode(), 'title': '<script>private</script>', 'as_blog': True}
        first = management.dispatch(self.root, 'upload', data)
        second = management.dispatch(self.root, 'upload', data)
        self.assertEqual(first, second);self.assertEqual(len(list((self.root / 'articles').iterdir())), 1)
        directory, _ = studio.item(self.root, 'articles', first['article']['id'])
        self.assertEqual((directory / 'ORIGINAL.md').read_bytes(), b'A draft with a clear argument.')
        changed = dict(data, title='different')
        with self.assertRaises(ValueError):management.dispatch(self.root, 'upload', changed)
        pdf = dict(operation='b' * 32, filename='notes.pdf', content=base64.b64encode(b'%PDF-fixture').decode())
        result = management.dispatch(self.root, 'upload', pdf);self.assertEqual(result['state'], 'pending')
        with self.assertRaises(ValueError):management.dispatch(self.root, 'upload', dict(pdf, operation='c' * 32, filename='../escape.md'))
    def test_ui_treats_data_as_text_and_has_no_external_assets(self):
        js = (management.ASSETS / 'app.js').read_text();html = (management.ASSETS / 'index.html').read_text()
        self.assertNotIn('innerHTML', js);self.assertNotIn('https://', html);self.assertIn('textContent', js)
        self.assertNotIn('admin', html.lower())
