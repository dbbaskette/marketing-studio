"""Editorial/library/local HTTP behavior using disposable workspaces and Git transports."""
import base64
from contextlib import contextmanager
import http.client
import io
import json
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
import zipfile
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
    def desk_schedule(self, ident, **changes):
        """A desk save: the expected-state guard plus only the fields the page sends."""
        expected = management.detail(self.root, ident)['expected']
        return management.dispatch(self.root, 'schedule', {'id': ident, 'expected': expected, **changes})

    def test_desk_owner_save_never_renews_a_stale_decision_or_pins_the_stage(self):
        idea = self.command('article', 'create', '--title', 'Idea blog', '--mode', 'first-draft', '--author', 'Avery')['id']
        self.desk_schedule(idea, owner='Morgan')
        self.assertNotIn('stage', studio.item(self.root, 'articles', idea)[1]['editorial'])
        self.file.write_text('A real draft now exists.')
        self.command('article', 'save', '--id', idea, '--kind', 'draft', '--file', str(self.file))
        self.assertEqual(management.detail(self.root, idea)['view']['stage'], 'draft')  # Follows writing progress.

        ident = self.article()
        with self.assertRaisesRegex(ValueError, 'Confirm'):self.desk_schedule(ident, stage='ready')
        self.desk_schedule(ident, stage='ready', confirm_stage=True)
        self.file.write_text('A substantially different, unreviewed draft.')
        self.command('article', 'save', '--id', ident, '--kind', 'draft', '--file', str(self.file))
        self.assertTrue(management.detail(self.root, ident)['view']['decision_stale'])
        # An old page resends the recorded stage with the owner. That is not a new decision.
        self.desk_schedule(ident, owner='Jordan', stage='ready')
        view = management.detail(self.root, ident)['view']
        self.assertTrue(view['decision_stale']);self.assertEqual(view['stage'], 'review')
        self.assertEqual(studio.item(self.root, 'articles', ident)[1]['editorial']['owner'], 'Jordan')
        # Renewal is explicit.
        self.desk_schedule(ident, stage='ready', confirm_stage=True)
        view = management.detail(self.root, ident)['view']
        self.assertFalse(view['decision_stale']);self.assertEqual(view['stage'], 'ready')
        # A save that changes nothing writes nothing and shares nothing.
        directory, _ = studio.item(self.root, 'articles', ident)
        before = (directory / 'session.json').read_bytes()
        result = self.desk_schedule(ident, owner='Jordan', stage='ready')
        self.assertEqual(result['status'], 'unchanged');self.assertEqual(result['receipts'], [])
        self.assertEqual((directory / 'session.json').read_bytes(), before)
        # An empty stage returns the blog to writing progress; an ordinary stage needs no confirmation.
        self.desk_schedule(ident, stage='')
        self.assertNotIn('stage', studio.item(self.root, 'articles', ident)[1]['editorial'])
        self.desk_schedule(ident, stage='review')
        self.assertEqual(management.detail(self.root, ident)['view']['stage'], 'review')
        with self.assertRaisesRegex(ValueError, 'Confirm'):self.desk_schedule(ident, stage='published', publication_url='https://team.example/blog/x')
        # A decision file written in chat for one requested change keeps its explicit meaning.
        editorial.schedule(self.root, ident, {'stage': 'ready'})
        self.assertEqual(editorial.board(self.root, stage='ready')['total'], 1)

    def test_one_unreadable_blog_is_reported_and_never_hides_the_rest(self):
        ident = self.article()
        (self.root / 'articles' / 'empty-folder').mkdir()
        (self.root / 'articles' / 'damaged-record').mkdir()
        (self.root / 'articles' / 'damaged-record' / 'session.json').write_text('{not json')
        odd = self.root / 'articles' / 'odd-shapes';odd.mkdir()
        (odd / 'session.json').write_text(json.dumps({'id': 'odd-shapes', 'title': 7, 'editorial': 'not-an-object',
            'google': ['x'], 'artifact_hashes': 'x', 'updated_at': 5}))
        board = editorial.board(self.root)
        self.assertEqual({row['id'] for row in board['items']}, {ident, 'odd-shapes'})
        odd_row = next(row for row in board['items'] if row['id'] == 'odd-shapes')
        self.assertEqual((odd_row['title'], odd_row['owner'], odd_row['stage'], odd_row['google']), ('Untitled', 'Unassigned', 'draft', None))
        self.assertEqual(board['problem_count'], 2)
        self.assertEqual({p['id'] for p in board['problems']}, {'empty-folder', 'damaged-record'})
        inbox = editorial.inbox(self.root)
        self.assertEqual(inbox['problem_count'], 3)  # The odd record cannot supply review state.
        self.assertTrue(all(p['location'] == 'local' and p['status'] == 'unreadable' for p in inbox['problems']))
        self.assertEqual(inbox['total'], len(inbox['items']))
        with self.assertRaises(ValueError):editorial.inbox(self.root, 'empty-folder')  # An explicit request still says why.
        self.assertIsNone(editorial.doc_link(None));self.assertIsNone(editorial.doc_link({'google': {'documents': {'draft': 'x'}, 'baselines': ['y']}}))
        self.assertEqual(editorial.row('not-a-record', 'x', 'hub')['stage'], 'draft')

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
    def test_damaged_index_is_discarded_and_rebuilt_once(self):
        self.collection()
        library.import_batch(self.root, library.preview(self.root, 'team-a')['preview'], delay=0)
        index = self.root / '.derived-cache' / 'library.sqlite3'
        self.assertEqual(library.catalog(self.root)['total'], 1)
        index.write_bytes(b'this is not a database ' * 400)
        rebuilt = library.catalog(self.root, query='routing')
        self.assertEqual(rebuilt['total'], 1);self.assertTrue(rebuilt['cache_rebuilt'])
        self.assertFalse(library.catalog(self.root)['cache_rebuilt'])  # Healthy again; no rebuild loop.
        # A file that stays unusable is reported in plain words, never as a database error.
        with patch.object(library, 'search_index', side_effect=library.sqlite3.DatabaseError('database disk image is malformed')):
            with self.assertRaisesRegex(ValueError, 'could not be rebuilt'):library.catalog(self.root)
        # A busy index is not a damaged one: it is left alone.
        self.assertEqual(library.catalog(self.root)['total'], 1);saved = index.read_bytes()
        with patch.object(library, 'search_index', side_effect=library.sqlite3.OperationalError('database is locked')):
            with self.assertRaisesRegex(ValueError, 'busy'):library.catalog(self.root)
        self.assertEqual(index.read_bytes(), saved)

    def test_unreadable_docx_is_a_validation_error(self):
        damaged = io.BytesIO()
        with zipfile.ZipFile(damaged, 'w') as archive:archive.writestr('word/document.xml', '<w:document><broken')
        other = io.BytesIO()
        with zipfile.ZipFile(other, 'w') as archive:archive.writestr('readme.txt', 'not a word file')
        for label, content in (('not a zip', b'not a zip'), ('malformed xml', damaged.getvalue()), ('no document', other.getvalue())):
            with self.subTest(label=label):
                with self.assertRaisesRegex(ValueError, 'DOCX file could not be read'):library.extract(self.root, content, '.docx')
                with self.assertRaisesRegex(ValueError, 'DOCX file could not be read'):
                    management.dispatch(self.root, 'upload', {'operation': sha(content)[:32], 'filename': 'notes.docx',
                                                               'content': base64.b64encode(content).decode()})
        self.assertEqual(list((self.root / 'sources').iterdir()), [])
        self.assertFalse((self.root / '.studio.lock').exists())
        good = io.BytesIO()
        with zipfile.ZipFile(good, 'w') as archive:
            archive.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                                                  '<w:body><w:p><w:r><w:t>Readable text.</w:t></w:r></w:p></w:body></w:document>')
        self.assertEqual(library.extract(self.root, good.getvalue(), '.docx'), ('Readable text.', 'ready'))

    def test_fetch_has_one_total_deadline_and_plain_network_errors(self):
        public = [(2, 1, 6, '', ('8.8.8.8', 443))]
        url, scope = 'https://team.example/blog/a', 'https://team.example/blog'
        def connect(status=200, chunks=(b'<p>', b'post</p>', b'')):
            connection = Mock();response = connection.getresponse.return_value
            response.status = status;response.getheader.side_effect = lambda name, default=None: {'Content-Type': 'text/html'}.get(name, default)
            response.read1.side_effect = list(chunks)
            return connection
        with patch.object(library.socket, 'getaddrinfo', return_value=public):
            with patch.object(library, 'PinnedHTTPS', return_value=connect()) as made:
                self.assertEqual(library.fetch(url, scope), (b'<p>post</p>', url, 'text/html'))
                self.assertLessEqual(made.return_value.timeout, 15)
            # A server that keeps sending slowly is cut off by the deadline for the whole address.
            clock = iter(range(0, 10000, 20))
            slow = connect(chunks=[b'x'] * 50)
            with patch.object(library, 'PinnedHTTPS', return_value=slow), patch.object(library.time, 'monotonic', side_effect=lambda: next(clock)):
                with self.assertRaisesRegex(ValueError, 'took too long'):library.fetch(url, scope)
            self.assertLess(slow.getresponse.return_value.read1.call_count, 5)
            with patch.object(library, 'PinnedHTTPS', return_value=connect()):
                with self.assertRaisesRegex(ValueError, 'took too long'):library.fetch(url, scope, deadline=time.monotonic() - 1)
            # Size stays bounded when no Content-Length is declared.
            with patch.object(library, 'PinnedHTTPS', return_value=connect(chunks=[b'x' * 65536] * 40)):
                with self.assertRaisesRegex(ValueError, 'bounded fetch limit'):library.fetch(url, scope)
            for failure in (OSError('connection refused'), TimeoutError('timed out'), library.http.client.RemoteDisconnected('closed')):
                broken = connect();broken.request.side_effect = failure
                with patch.object(library, 'PinnedHTTPS', return_value=broken), self.subTest(failure=type(failure).__name__):
                    with self.assertRaisesRegex(ValueError, 'could not be reached|took too long'):library.fetch(url, scope)
                broken.close.assert_called()
        with patch.object(library.socket, 'getaddrinfo', side_effect=library.socket.gaierror('unknown host')):
            with self.assertRaisesRegex(ValueError, 'could not be reached'):library.fetch(url, scope)

    def test_curation_records_an_override_only_for_a_changed_value(self):
        source = self.source()
        same = library.curate(self.root, source['id'], {'curation': 'active', 'topics': [], 'products': [], 'note': source['note'] or ''})
        self.assertEqual(same['revision'], source['revision']);self.assertNotIn('curation_overrides', same)
        directory, _ = studio.item(self.root, 'sources', source['id'])
        self.assertFalse((directory / 'revisions').exists())
        noted = library.curate(self.root, source['id'], {'curation': 'active', 'topics': [], 'products': [], 'note': 'Reviewed.'})
        self.assertEqual(noted['curation_overrides'], ['note']);self.assertEqual(noted['revision'], source['revision'] + 1)
        tagged = library.curate(self.root, source['id'], {'topics': ['routing'], 'note': 'Reviewed.'})
        self.assertEqual(tagged['curation_overrides'], ['note', 'topics'])
        with self.assertRaises(ValueError):library.curate(self.root, source['id'], {'note': 'x' * 4001})
        self.assertEqual(studio.item(self.root, 'sources', source['id'])[1], tagged)  # A refused save writes nothing.
        # The desk answers "unchanged" before any revision, checkout or share.
        detail = management.source_detail(self.root, source['id'])
        result = management.dispatch(self.root, 'curate', {'id': source['id'], 'expected': detail['expected'], 'curation': 'active',
                                                           'topics': ['routing'], 'products': [], 'note': 'Reviewed.'})
        self.assertEqual(result['status'], 'unchanged')
        self.assertEqual(studio.item(self.root, 'sources', source['id'])[1], tagged)

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
        self.assertEqual(self.hub.graph()['manifest']['minimum_runtime'], '1.13.1')
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

    def test_malformed_shared_records_are_listed_and_saves_stay_truthful(self):
        # Shapes another client version, a hand edit or a collaborator could leave in the Hub.
        self.hub.save('article', 'Odd editorial', 'body', sync=False,
                      data={'studio': {'editorial': 'not-an-object', 'google': 'x', 'reviews': ['y'], 'artifact_hashes': 3}})
        self.hub.save('article', 'Odd studio', 'body', data={'studio': 'not-an-object'}, sync=False)
        board = editorial.board(self.root)
        self.assertEqual({row['title'] for row in board['items']}, {'Odd editorial', 'Odd studio'})
        self.assertTrue(all(row['stage'] == 'draft' and row['owner'] == 'Unassigned' and row['google'] is None for row in board['items']))
        self.assertEqual(board['problem_count'], 0)
        inbox = editorial.inbox(self.root)
        self.assertEqual((inbox['total'], inbox['problem_count']), (0, 0))
        # Sharing that stops for an unexpected reason is still reported as the local save it was.
        data = {'operation': '9' * 32, 'filename': 'kept.md', 'content': base64.b64encode(b'Kept reference.').decode()}
        with patch.object(management, 'note_unexpected') as noted, patch.object(self.workspace, 'publish_mutation', side_effect=AttributeError('renderer')):
            saved = management.dispatch(self.root, 'upload', data)
        self.assertEqual(saved['receipts'][0]['sharing'], 'local-saved-not-shared');noted.assert_called_once()
        self.assertEqual(management.dispatch(self.root, 'upload', data), saved)  # A replay returns the same saved result.
        self.assertEqual(len(list((self.root / 'sources').iterdir())), 1)

    def test_held_save_receipt_explains_itself_and_offers_no_blind_retry(self):
        value = {'id': 'a' * 64, 'label': 'Blog', 'local_saved': True, 'checked_at': 'now', 'hub': 'hub',
                 'sharing': 'newer-hub-revision'}
        shown = management.public_receipt(value)
        self.assertFalse(shown['retry']);self.assertIn('newer version', shown['message'])
        shown = management.public_receipt({**value, 'sharing': 'review-closed'})
        self.assertTrue(shown['retry']);self.assertIn('new review', shown['message'])

    def test_sync_renders_the_board_despite_a_malformed_shared_record(self):
        # The generated Hub board is rebuilt on every sync; one bad record must not stop all sharing.
        self.hub.save('article', 'Odd editorial', 'body', sync=False, data={'studio': {'editorial': 'not-an-object'}})
        self.hub.sync()
        board = self.hub.files()['editorial/README.md'].decode()
        row = next(line for line in board.splitlines() if 'Odd editorial' in line)
        self.assertIn('Unassigned', row)

    def test_memory_edit_sends_only_changes_and_keeps_the_rest_of_the_revision(self):
        long_body = 'A long saved memory sentence. ' * 700
        self.assertGreater(len(long_body), 16000)
        saved = self.hub.save('note', 'Saved title', long_body, scope={'level': 'project', 'key': 'gateway'}, sync=False)
        shown = management.memory_detail(self.root, saved['item'], saved['revision'])
        self.assertTrue(shown['truncated']);self.assertEqual(len(shown['body']), 16000)
        reference = {'item': saved['item'], 'revision': saved['revision']}
        for same in ({}, {'title': 'Saved title', 'kind': 'note', 'scope': 'project', 'scope_key': 'gateway'}):
            result = management.dispatch(self.root, 'memory', {**reference, **same})
            self.assertEqual(result['status'], 'unchanged');self.assertEqual(result['receipts'], [])
        self.assertEqual(self.hub.graph()['heads'][saved['item']], [saved['revision']])
        edited = management.dispatch(self.root, 'memory', {**reference, 'title': 'Better title'})
        current = self.hub.read(saved['item'])
        self.assertEqual(current['record']['revision'], edited['revision'])
        self.assertEqual((current['record']['title'], current['record']['kind'], current['record']['scope']),
                         ('Better title', 'note', {'level': 'project', 'key': 'gateway'}))
        self.assertEqual(Path(current['paths']['BODY.md']).read_text(), long_body)  # The part the form never showed is kept.
        newest = {'item': saved['item'], 'revision': edited['revision']}
        with self.assertRaisesRegex(ValueError, 'under 16000'):management.dispatch(self.root, 'memory', {**newest, 'body': 'x' * 16001})
        with self.assertRaisesRegex(ValueError, 'changed'):management.dispatch(self.root, 'memory', {**reference, 'title': 'Stale form'})
        with self.assertRaises(ValueError):management.dispatch(self.root, 'memory', {'kind': 'note', 'title': 'No body'})

    def test_capabilities_name_the_workspace_hub_and_analysis_cli(self):
        import source_curator
        result = management.capabilities(self.root)
        self.assertEqual(result['hub']['repository'], 'fixture/editorial')
        self.assertTrue(result['workspace'].endswith('writing'))
        self.assertIsNone(result['analysis']['harness']);self.assertIn('not sent to a model', result['analysis']['message'])
        source_curator.configure(self.root, 'claude')
        analysis = management.capabilities(self.root)['analysis']
        self.assertEqual((analysis['harness'], analysis['label'], analysis['max_characters']), ('claude', 'Claude', 24000))
        self.assertIn('24,000 characters', analysis['message']);self.assertIn('model provider', analysis['message'])

    def test_desk_collection_is_shared_on_first_import_and_a_teammates_name_is_kept(self):
        def collection_records():
            graph = self.hub.graph(include_local=False)
            return [graph['revisions'][heads[-1]] for heads in graph['heads'].values() if graph['revisions'][heads[-1]]['data'].get('collection')]
        export = base64.b64encode(json.dumps([{'external_id': 'p-1', 'title': 'Post', 'text': 'A retained post.'}]).encode()).decode()
        preview = management.dispatch(self.root, 'library-preview', {'operation': 'a' * 32, 'name': 'Team history', 'type': 'export', 'export': export})
        self.assertEqual(collection_records(), [])  # Previewing shares nothing with the Hub.
        result = management.dispatch(self.root, 'library-import', {'operation': 'b' * 32, 'preview': preview['preview'], 'expected': preview['expected'],
                                                                   'confirm': True, 'retry': False, 'selected': [preview['posts'][0]['key']]})
        self.assertEqual((result['counts']['imported'], result['sharing']), (1, 'shared'))
        self.assertEqual([record['data']['collection']['name'] for record in collection_records()], ['Team history'])
        # A teammate sees the shared collection before its posts reach this clone's catalog; the name is theirs.
        other = self.base / 'teammate';studio.initialize(other)
        registry = Registry(self.base / 'teammate-hubs', self.provider);registry.join('fixture/editorial')
        self.other_workspace = Workspace(other, registry.hub(self.hub_id))
        self.assertEqual([c['name'] for c in library.collections(other).values()], ['Team history'])
        with patch.object(library, 'imported_count', return_value=0):
            with self.assertRaisesRegex(ValueError, 'already has that name'):
                management.dispatch(other, 'library-preview', {'operation': 'c' * 32, 'name': 'Team history', 'type': 'export', 'export': export})
        self.assertEqual(library.local_config(other)['collections'], {})

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
    def unbound(self):
        """The real server and handler without opening a port; requests arrive over socket pairs."""
        server, url = management.server(self.root, port=54321, bind=False)
        self.addCleanup(server.server_close)
        return server, url.split('#')[1]

    def exchange(self, server, token, path='/api/board', method='GET', data=None, headers=None):
        client, inside = socket.socketpair()
        self.addCleanup(client.close)
        fields = {'Host': '127.0.0.1:54321', 'X-Blog-Studio-Token': token}
        payload = json.dumps(data).encode() if data is not None else b''
        if data is not None:fields.update({'Content-Type': 'application/json', 'Content-Length': str(len(payload))})
        fields.update(headers or {})
        lines = [method + ' ' + path + ' HTTP/1.1'] + [key + ': ' + value for key, value in fields.items() if value is not None]
        server.process_request(inside, ('127.0.0.1', 0))  # The same threaded path a TCP connection takes.
        client.sendall('\r\n'.join(lines).encode() + b'\r\n\r\n' + payload)
        client.settimeout(15);received = b''
        while chunk := client.recv(65536):received += chunk
        head, _, body = received.partition(b'\r\n\r\n')
        first, *rest = head.decode().split('\r\n')
        return int(first.split()[1]), dict(line.split(': ', 1) for line in rest), body

    def test_unexpected_failures_always_get_a_plain_json_reply(self):
        server, token = self.unbound()
        with patch.object(management, 'note_unexpected') as noted:
            with patch.object(management, 'view', side_effect=RuntimeError('private /Users/someone/secret.md')):
                status, headers, body = self.exchange(server, token)
            self.assertEqual(status, 500);self.assertEqual(json.loads(body)['code'], 'unexpected')
            self.assertNotIn(b'secret', body);self.assertIn('Content-Security-Policy', headers)
            with patch.object(management, 'dispatch', side_effect=LookupError('boom')):
                status, _, body = self.exchange(server, token, '/api/upload', 'POST', data={'operation': 'a' * 32})
            self.assertEqual(status, 500);self.assertIn('unexpected problem', json.loads(body)['error'])
            self.assertEqual(noted.call_count, 2)
        docx = {'operation': 'b' * 32, 'filename': 'notes.docx', 'content': base64.b64encode(b'not a zip').decode()}
        status, _, body = self.exchange(server, token, '/api/upload', 'POST', data=docx)
        self.assertEqual(status, 400);self.assertIn('DOCX', json.loads(body)['error'])
        legacy = {'operation': 'c' * 32, 'filename': 'old.txt', 'content': base64.b64encode('caf\u00e9 \u201cquoted\u201d'.encode('cp1252')).decode()}
        status, _, body = self.exchange(server, token, '/api/upload', 'POST', data=legacy)
        self.assertEqual(status, 400);self.assertIn('UTF-8', json.loads(body)['error']);self.assertNotIn('codec', body.decode())
        for path in ('/api/board?limit=abc', '/api/article', '/api/library-preview?preview=' + 'e' * 32):
            status, _, body = self.exchange(server, token, path)
            message = json.loads(body)['error']
            self.assertEqual(status, 400, path)
            for internal in ('int()', 'NoneType', 'Errno', 'Traceback'):self.assertNotIn(internal, message)
        # The stderr note names the exception type and code location, never its message.
        try:raise RuntimeError('private /Users/someone/secret.md')
        except RuntimeError as exc:
            with patch('sys.stderr', io.StringIO()) as stderr:management.note_unexpected(exc)
        self.assertRegex(stderr.getvalue(), r'unexpected RuntimeError at test_editorial_tools\.py:\d+');self.assertNotIn('secret', stderr.getvalue())

    def test_silent_connection_never_holds_up_another_request(self):
        with patch.object(management, 'HEADER_TIMEOUT', 1.5):server, token = self.unbound()
        silent, inside = socket.socketpair();self.addCleanup(silent.close)
        server.process_request(inside, ('127.0.0.1', 0))  # Connected, and then says nothing.
        started = time.monotonic()
        self.assertEqual(self.exchange(server, token)[0], 200)
        self.assertEqual(self.exchange(server, token, '/')[0], 200)
        self.assertLess(time.monotonic() - started, 1.0)
        silent.settimeout(10)
        self.assertEqual(silent.recv(1), b'')  # Closed after the short header wait, without a reply.
        self.assertLess(time.monotonic() - started, 6)
        self.assertIsInstance(server, management.ThreadingHTTPServer);self.assertTrue(server.daemon_threads)

    def test_api_handlers_run_one_at_a_time_and_others_are_told_busy(self):
        server, token = self.unbound()
        entered, release, running, most = threading.Event(), threading.Event(), [], []
        real = management.view
        def slow(root, name, query):
            running.append(name);most.append(len(running))
            try:
                if name == 'board':
                    entered.set();release.wait(15)
                return real(root, name, query)
            finally:running.remove(name)
        first = {}
        with patch.object(management, 'view', side_effect=slow), patch.object(management, 'API_WAIT', 0.3):
            thread = threading.Thread(target=lambda:first.update(reply=self.exchange(server, token)));thread.start()
            self.assertTrue(entered.wait(10))
            status, _, body = self.exchange(server, token, '/api/capabilities')
            self.assertEqual(status, 503);self.assertEqual(json.loads(body)['code'], 'busy')
            self.assertEqual(self.exchange(server, token, '/app.js')[0], 200)  # The page itself is never queued.
            self.assertEqual(self.exchange(server, 'wrong-token')[0], 400)  # Refusals do not wait either.
            release.set();thread.join(15)
            self.assertEqual(self.exchange(server, token, '/api/capabilities')[0], 200)
        self.assertEqual(first['reply'][0], 200)
        self.assertEqual(max(most), 1)  # Workspace access stayed serialized.

    def test_headers_methods_and_cross_site_requests(self):
        server, token = self.unbound()
        status, headers, page = self.exchange(server, token, '/')
        self.assertEqual(status, 200);self.assertIn(b'Editorial desk', page)
        self.assertEqual(headers['Cross-Origin-Resource-Policy'], 'same-origin')
        self.assertEqual(headers['Server'], 'Blog Studio desk')
        self.assertEqual(headers['X-Content-Type-Options'], 'nosniff');self.assertIn("frame-ancestors 'none'", headers['Content-Security-Policy'])
        for method in ('PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD', 'PROPFIND'):
            with self.subTest(method=method):
                status, headers, body = self.exchange(server, token, '/api/board', method)
                self.assertEqual(status, 501 if method == 'PROPFIND' else 405)
                self.assertEqual(headers['Content-Type'], 'application/json');self.assertIn('Content-Security-Policy', headers)
                self.assertNotIn('Python', ' '.join(headers.values()));self.assertNotIn('BaseHTTP', ' '.join(headers.values()))
                if method == 'HEAD':self.assertEqual(body, b'')
                else:self.assertIn('GET and POST', json.loads(body)['error'])
        cross = {'Sec-Fetch-Site': 'cross-site'}
        for path in ('/app.js', '/style.css', '/api/board', '/'):
            self.assertEqual(self.exchange(server, token, path, headers=cross)[0], 400, path)
        self.assertEqual(self.exchange(server, token, headers={'Sec-Fetch-Site': 'same-site'})[0], 400)
        self.assertEqual(self.exchange(server, token, '/api/upload', 'POST', data={}, headers=cross)[0], 400)
        framed = {**cross, 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Dest': 'iframe'}
        self.assertEqual(self.exchange(server, token, '/', headers=framed)[0], 400)
        # Following the desk link from another page is a top-level visit to the page shell, which holds no data.
        followed = {**cross, 'Sec-Fetch-Mode': 'navigate', 'Sec-Fetch-Dest': 'document'}
        self.assertEqual(self.exchange(server, token, '/', headers=followed)[0], 200)
        self.assertEqual(self.exchange(server, token, '/api/board', headers=followed)[0], 400)
        for site in ('same-origin', 'none'):
            self.assertEqual(self.exchange(server, token, headers={'Sec-Fetch-Site': site})[0], 200)
        # The existing checks are unchanged.
        self.assertEqual(self.exchange(server, 'bad')[0], 400)
        self.assertEqual(self.exchange(server, token, headers={'Host': 'outside.example'})[0], 400)
        self.assertEqual(self.exchange(server, token, headers={'Host': 'localhost:54321'})[0], 400)
        self.assertEqual(self.exchange(server, token, headers={'Origin': 'https://outside.example'})[0], 400)
        self.assertEqual(self.exchange(server, token, '/../../private')[0], 404)
        self.assertEqual(self.exchange(server, token, '/api/upload', 'POST', data={}, headers={'Content-Type': 'text/plain'})[0], 400)

    def test_opening_the_desk_saves_an_analysis_choice_only_when_asked(self):
        class Stopped:
            def serve_forever(self):raise KeyboardInterrupt
            def server_close(self):pass
        def launch(harness=None):
            output = io.StringIO()
            with patch.object(management, 'server', return_value=(Stopped(), 'http://127.0.0.1:1/#token')), patch('sys.stdout', output):
                self.assertEqual(management.main(self.root, harness=harness), 0)
            return json.loads(output.getvalue())['analysis']
        first = launch()
        self.assertFalse((self.root / '.curation.json').exists())
        self.assertEqual((first['harness'], first['saved_by_this_launch']), (None, False));self.assertIn('did not turn on', first['note'])
        chosen = launch('claude')
        self.assertEqual(studio.read_json(self.root / '.curation.json')['harness'], 'claude')
        self.assertEqual((chosen['harness'], chosen['saved_by_this_launch']), ('claude', True))
        self.assertIn('because --harness was passed', chosen['note']);self.assertIn('24,000 characters', chosen['note'])
        later = launch()
        self.assertEqual((later['harness'], later['saved_by_this_launch']), ('claude', False));self.assertIn('left as it is', later['note'])

    def test_http_curation_conflict_returns_409_without_overwrite(self):
        source = self.source();snapshot = management.source_detail(self.root, source['id'])
        library.curate(self.root, source['id'], {'note': 'Newest note'})
        server, token = self.start_server()
        status, body = self.request(server, token, '/api/curate', 'POST', {'id': source['id'], 'expected': snapshot['expected'], 'note': 'Old proposal'})
        self.assertEqual(status, 409);self.assertEqual(body['code'], 'source-conflict')
        self.assertEqual(studio.item(self.root, 'sources', source['id'])[1]['note'], 'Newest note')

    def test_saves_and_conflicts_keep_their_contract_on_the_threaded_path(self):
        source = self.source();snapshot = management.source_detail(self.root, source['id'])
        server, token = self.unbound()
        proposal = {'id': source['id'], 'expected': snapshot['expected'], 'note': 'First proposal'}
        status, _, body = self.exchange(server, token, '/api/curate', 'POST', data=proposal)
        self.assertEqual(status, 200);self.assertEqual(json.loads(body)['note'], 'First proposal')
        status, _, body = self.exchange(server, token, '/api/curate', 'POST', data=dict(proposal, note='Old proposal'))
        self.assertEqual(status, 409);self.assertEqual(json.loads(body)['code'], 'source-conflict')
        self.assertEqual(studio.item(self.root, 'sources', source['id'])[1]['note'], 'First proposal')
        self.assertFalse((self.root / '.studio.lock').exists())
        # A read of something that is gone stays an ordinary 400.
        self.assertEqual(self.exchange(server, token, '/api/source?id=missing')[0], 400)
        # The page's own same-origin POST, as a browser sends it.
        ident = self.article();expected = management.detail(self.root, ident)['expected']
        browser = {'Origin': 'http://127.0.0.1:54321', 'Sec-Fetch-Site': 'same-origin', 'Sec-Fetch-Mode': 'cors', 'Sec-Fetch-Dest': 'empty'}
        status, _, body = self.exchange(server, token, '/api/schedule', 'POST', data={'id': ident, 'expected': expected, 'owner': 'Morgan'}, headers=browser)
        self.assertEqual(status, 200);self.assertEqual(json.loads(body)['editorial']['owner'], 'Morgan')

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
        self.assertNotIn('innerHTML', js);self.assertIn('textContent', js)
        from html.parser import HTMLParser
        class Assets(HTMLParser):
            def __init__(self):super().__init__();self.urls=[]
            def handle_starttag(self, tag, attrs):
                self.urls.extend(value for key,value in attrs if key == 'src' or (tag == 'link' and key == 'href'))
        assets=Assets();assets.feed(html)
        self.assertTrue(assets.urls)
        for url in assets.urls:self.assertTrue(url.startswith('/') and not url.startswith('//'), url)
        self.assertNotIn('admin', html.lower())
