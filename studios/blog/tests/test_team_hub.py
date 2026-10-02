import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hub_fixtures import FakeProvider
from hub import Registry
import hub as module
import hub_store as store

class TeamHubTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.provider = FakeProvider(self.base / 'remotes')
        self.a = Registry(self.base / 'member a', self.provider)
        self.b = Registry(self.base / 'member b', self.provider)
        created = self.a.create('fixture/team-hub', 'Fixture Hub')
        self.id = created['hub'];self.ha = self.a.hub(self.id)
        self.b.join('https://github.com/fixture/team-hub.git');self.hb = self.b.hub(self.id)

    def test_create_join_and_selection_are_idempotent(self):
        self.assertEqual(self.provider.created, 1)
        self.assertEqual(self.a.create('fixture/team-hub', 'Fixture Hub')['hub'], self.id)
        self.assertEqual(self.b.join('fixture/team-hub')['hub'], self.id)
        self.assertEqual(len(self.b.list()), 1)
        project = self.base / 'writing project'
        self.b.select(self.id, project)
        self.assertEqual(self.b.selected(project).id, self.id)
        self.b.leave(self.id, project)
        self.assertIsNone(self.b.selected(project))
        self.assertTrue(self.hb.repository.exists())

    def test_creation_timeout_recovers_same_remote_and_identity(self):
        self.provider.timeout_after_create = True
        created = self.a.create('fixture/second-hub', 'Second hub')
        self.assertEqual(created['creation'], 'verified')
        self.assertEqual(self.provider.created, 2)
        self.a.create('fixture/second-hub', 'Second hub')
        self.assertEqual(self.provider.created, 2)
        with self.assertRaises(store.HubError):self.a.create('fixture/second-hub', 'Changed name')

    def test_nonempty_destination_and_foreign_repo_are_preserved(self):
        self.provider.repos['fixture/team-hub']['description'] = 'Unrelated repository'
        with self.assertRaises(store.HubError):self.a.create('fixture/team-hub', 'Fixture Hub')
        destination = self.base / 'existing';destination.mkdir();(destination / 'keep').write_text('Existing work')
        other = Registry(self.base / 'other', self.provider)
        with self.assertRaisesRegex(store.HubError, 'preserved'):other.join('fixture/team-hub', destination)
        self.assertEqual((destination / 'keep').read_text(), 'Existing work')
        self.assertEqual(other.list(), [])

    def test_remote_identity_public_visibility_and_bad_urls_are_rejected(self):
        metadata = self.provider.repos['fixture/team-hub']
        metadata['id'] = 999
        with self.assertRaisesRegex(store.HubError, 'identity'):self.ha.refresh()
        metadata['id'] = 1;metadata['private'] = False
        with self.assertRaises(store.HubError):Registry(self.base / 'new member', self.provider).join('fixture/team-hub')
        for value in ('https://SECRET@github.com/fixture/team-hub', 'https://example.com/a/b', 'git@github.com:a/b', '../a/b'):
            with self.assertRaises(store.HubError) as error:store.canonical_repository(value)
            self.assertNotIn('SECRET', str(error.exception))

    def test_member_save_find_read_and_revision_history(self):
        saved = self.ha.save('note', 'Product positioning', 'Useful market context', tags=['product'])
        self.assertEqual(saved['status'], 'shared')
        self.hb.refresh()
        found = self.hb.find('market context', kind='note', tag='product')
        self.assertEqual(found['total'], 1)
        read = self.hb.read(saved['item'])
        self.assertEqual(Path(read['paths']['BODY.md']).read_text(), 'Useful market context')
        changed = self.hb.save('note', 'Product positioning', 'Updated context', item=saved['item'])
        self.ha.refresh()
        self.assertEqual(self.ha.read(saved['item'])['record']['revision'], changed['revision'])
        self.assertEqual(Path(self.ha.read(saved['item'], saved['revision'])['paths']['BODY.md']).read_text(), 'Useful market context')

    def test_independent_saves_converge_after_offline_queue(self):
        one = self.ha.save('note', 'A', 'One', offline=True)
        two = self.hb.save('note', 'B', 'Two', offline=True)
        self.assertEqual(one['status'], 'queued-offline')
        self.assertEqual(two['queued'], 1)
        self.ha.sync();self.hb.sync();self.ha.refresh()
        self.assertEqual(self.ha.find()['total'], 2)
        self.assertEqual(self.hb.status()['queued'], 0)

    def test_same_baseline_conflict_and_resolution_preserve_both(self):
        original = self.ha.save('article', 'Shared blog', 'Original')
        self.hb.refresh()
        a = self.ha.save('article', 'Shared blog', 'Author A', item=original['item'], offline=True)
        b = self.hb.save('article', 'Shared blog', 'Author B', item=original['item'], offline=True)
        self.ha.sync();self.hb.sync();self.ha.refresh()
        self.assertEqual(self.ha.status()['conflicts'], 1)
        with self.assertRaisesRegex(store.HubError, 'conflicted'):self.ha.read(original['item'])
        with self.assertRaisesRegex(store.HubError, 'competing'):self.ha.save('article', 'Shared blog', 'Bad implicit resolution', item=original['item'])
        resolved = self.ha.save('article', 'Shared blog', 'Both contributions', item=original['item'], parents=[a['revision'], b['revision']])
        self.hb.refresh()
        self.assertEqual(self.hb.status()['conflicts'], 0)
        self.assertEqual(set(self.hb.read(original['item'])['record']['parents']), {a['revision'], b['revision']})
        self.assertEqual(len(self.hb.graph()['revisions']), 4)
        self.assertEqual(resolved['status'], 'shared')

    def test_stable_operation_retries_do_not_duplicate_or_accept_changed_payload(self):
        operation = 'a' * 32
        first = self.ha.save('note', 'Same request', 'Same body', operation=operation, offline=True)
        again = self.ha.save('note', 'Same request', 'Same body', operation=operation)
        self.assertEqual(first['revision'], again['revision'])
        self.assertEqual(len(self.ha.graph()['revisions']), 1)
        with self.assertRaisesRegex(store.HubError, 'different content'):
            self.ha.save('note', 'Same request', 'Different body', operation=operation)

    def test_stable_operation_is_idempotent_from_another_member(self):
        operation='c'*32
        first=self.ha.save('note','One operation','Same body',operation=operation)
        self.hb.refresh()
        again=self.hb.save('note','One operation','Same body',operation=operation)
        self.assertEqual(first['revision'],again['revision'])
        self.assertEqual(len(self.hb.graph()['revisions']),1)
        with self.assertRaisesRegex(store.HubError,'different content'):
            self.hb.save('note','One operation','Changed body',operation=operation)

    def test_text_encoding_graph_cycle_and_dependency_shape_are_rejected(self):
        saved=self.ha.save('note','Valid','Valid body')
        files=self.ha.files();prefix='memory/items/'+saved['item']+'/revisions/'+saved['revision']+'/'
        record=json.loads(files[prefix+'record.json'])
        for changes in ({'parents':[saved['revision']]},{'dependencies':['bad']},{'dependencies':[{'item':saved['item'],'revision':saved['revision'],'kind':'note'}]},{'files':[]},{'scope':{'level':'project','key':''}}):
            mutated=dict(files);mutated[prefix+'record.json']=store.encoded({**record,**changes})
            with self.assertRaises(store.HubError):store.validate_files(mutated)
        bad=dict(files);bad['README.md']=b'\xff'
        with self.assertRaisesRegex(store.HubError,'UTF-8'):store.validate_files(bad)

    def test_symlinks_and_executable_modes_never_materialize(self):
        remote=self.provider.transport({'repository':'fixture/team-hub'})
        base=store.git(remote,'rev-parse','main').decode().strip()
        blob=store.git(remote,'hash-object','-w','--stdin',data=b'outside').decode().strip()
        index=self.base/'unsafe-index'
        for mode in ('120000','100755'):
            env={'GIT_INDEX_FILE':str(index)}
            store.git(remote,'read-tree',base,extra_env=env)
            store.git(remote,'update-index','--add','--cacheinfo',mode+','+blob+',unsafe',extra_env=env)
            tree=store.git(remote,'write-tree',extra_env=env).decode().strip()
            commit=store.git(remote,'commit-tree',tree,'-p',base,data=b'Unsafe fixture',extra_env={**env,'GIT_AUTHOR_NAME':'Fixture','GIT_AUTHOR_EMAIL':'fixture@localhost','GIT_COMMITTER_NAME':'Fixture','GIT_COMMITTER_EMAIL':'fixture@localhost'}).decode().strip()
            store.git(remote,'update-ref','refs/heads/main',commit)
            with self.assertRaisesRegex(store.HubError,'non-executable'):self.hb.refresh()
        self.assertEqual(self.hb._state()['revision'],base)

    def test_catalog_and_context_disclose_bounded_metadata(self):
        for number in range(4):self.ha.save('context','Item '+str(number),'Context',offline=True)
        first=self.ha.find(limit=2);second=self.ha.find(limit=2,offset=2)
        self.assertTrue(first['truncated']);self.assertFalse(second['truncated'])
        self.assertEqual(len(set(r['item'] for r in first['items']+second['items'])),4)
        result=self.ha.context(limit=2)
        self.assertTrue(result['truncated']);self.assertEqual(len(result['selected']),2)
        self.assertNotIn('BODY.md',json.dumps(result))

    def test_response_loss_after_push_is_reconciled_without_duplicate_write(self):
        real = module.git;lost = False
        def uncertain(repository, *args, **kwargs):
            nonlocal lost
            result = real(repository, *args, **kwargs)
            if args[0] == 'push' and not lost:
                lost = True
                raise store.TransportError('Fixture response lost after delivery')
            return result
        with patch.object(module, 'git', side_effect=uncertain):
            saved = self.ha.save('note', 'Response loss', 'Durable content')
        self.assertEqual(saved['status'], 'queued-unavailable')
        result = self.ha.sync()
        self.assertEqual(result['queued'], 0)
        self.assertEqual(len(self.ha.graph()['revisions']), 1)

    def test_push_race_retries_with_same_operations_and_keeps_other_writer(self):
        real = module.git;raced = False
        def race(repository, *args, **kwargs):
            nonlocal raced
            if args[0] == 'push' and Path(repository) == self.ha.repository and not raced:
                raced = True
                self.hb.save('note', 'Other member', 'Independent record')
            return real(repository, *args, **kwargs)
        with patch.object(module, 'git', side_effect=race):
            saved = self.ha.save('note', 'My record', 'Preserved record')
        self.assertEqual(saved['status'], 'shared')
        self.assertEqual(self.ha.find()['total'], 2)

    def test_review_branch_stays_pending_until_merged(self):
        self.provider.review = True
        saved = self.ha.save('note', 'Needs review', 'Contribution')
        self.assertEqual(saved['status'], 'pending-review')
        self.assertEqual(saved['pending_review'], 1)
        self.hb.refresh();self.assertEqual(self.hb.find()['total'], 0)
        self.ha.save('note', 'Another contribution', 'Additional work')
        self.assertEqual(len(self.provider.prs), 1)
        branch = self.ha._state()['review_branch']
        self.provider.merge_review('fixture/team-hub', branch)
        result = self.ha.sync()
        self.assertEqual(result['pending_review'], 0)
        self.hb.refresh();self.assertEqual(self.hb.find()['total'], 2)

    def test_repeated_push_rejection_is_bounded_and_preserves_queue(self):
        real=module.git;pushes=[]
        def rejection(repository,*args,**kwargs):
            if args[0]=='push':
                import subprocess
                pushes.append(args)
                return subprocess.CompletedProcess([],1,b'',b'Rejected fixture')
            return real(repository,*args,**kwargs)
        with patch.object(module,'git',side_effect=rejection):
            saved=self.ha.save('note','Contention','Retained work')
        self.assertEqual(saved['status'],'queued-contention');self.assertEqual(len(pushes),3)
        self.assertEqual(saved['queued'],1)
        self.assertTrue(all('--force' not in args for args in pushes))
        self.assertEqual(self.ha.sync()['queued'],0)

    def test_unknown_pr_creation_recovers_one_contribution(self):
        self.provider.review=True;real=self.provider.ensure_pr;lost=False
        def uncertain(*args):
            nonlocal lost
            url=real(*args)
            if not lost:
                lost=True;raise store.TransportError('Lost PR response')
            return url
        with patch.object(self.provider,'ensure_pr',side_effect=uncertain):
            saved=self.ha.save('note','Review','Retained contribution')
            self.assertEqual(saved['status'],'queued-unavailable')
            retried=self.ha.sync()
        self.assertEqual(retried['status'],'pending-review');self.assertEqual(len(self.provider.prs),1)
        self.assertEqual(len(self.ha.graph()['revisions']),1)

    def test_read_only_member_keeps_queued_work_without_claiming_shared(self):
        self.provider.repos['fixture/team-hub']['write'] = False
        self.hb.refresh()
        saved = self.hb.save('note', 'Read-only attempt', 'Retained content')
        self.assertEqual(saved['status'], 'queued-read-only')
        self.assertEqual(saved['queued'], 1)
        self.ha.refresh();self.assertEqual(self.ha.find()['total'], 0)

    def test_rules_scope_precedence_and_equally_scoped_conflicts(self):
        team = self.ha.save('rule', 'Team tone', 'Conversational', data={'key': 'tone'})
        project = self.ha.save('rule', 'Project tone', 'Formal', data={'key': 'tone'}, scope={'level': 'project', 'key': 'launch'})
        context = self.ha.context(project='launch')
        self.assertEqual([r['revision'] for r in context['selected']], [project['revision'], team['revision']])
        self.ha.save('rule', 'Competing project tone', 'Technical', data={'key': 'tone'}, scope={'level': 'project', 'key': 'launch'})
        context = self.ha.context(project='launch')
        self.assertEqual(len(context['conflicts']), 2)
        self.assertEqual([r['revision'] for r in context['selected']], [team['revision']])
        self.assertEqual(len(self.ha.context(project='other')['selected']), 1)

    def test_tombstones_hide_current_record_and_preserve_prior_content(self):
        saved = self.ha.save('note', 'Old note', 'Keep original')
        self.ha.save('note', 'Old note', item=saved['item'], status='tombstone')
        self.assertEqual(self.ha.find()['total'], 0)
        self.assertEqual(Path(self.ha.read(saved['item'], saved['revision'])['paths']['BODY.md']).read_text(), 'Keep original')

    def test_invalid_data_and_queued_tampering_do_not_modify_remote(self):
        before = self.ha._state()['revision']
        with self.assertRaises(store.HubError):self.ha.save('note', 'Bad dependency', dependencies=[{'item': 'a'*32, 'revision': 'b'*32, 'kind': 'source'}])
        with self.assertRaises(store.HubError):self.ha.save('note', 'Bad artifact', artifacts={'../escape': (b'x', 'binary')})
        with patch.object(store, 'MAX_TEXT', 5):
            with self.assertRaises(store.HubError):self.ha.save('note', 'Too large', 'Large content')
        self.assertEqual(self.ha._state()['revision'], before)
        saved = self.ha.save('note', 'Queued', 'Valid', offline=True)
        intent = self.ha._intents()[0]
        name = next(n for n in intent['files'] if n.endswith('BODY.md'))
        path = self.ha.root / 'outbox' / saved['operation'] / 'payload' / name
        path.write_text('Changed outside helper')
        with self.assertRaisesRegex(store.HubError, 'changed'):self.ha.sync()

    def test_remote_revision_modification_and_executable_files_are_rejected(self):
        saved = self.ha.save('note', 'Immutable', 'Original')
        self.hb.refresh()
        files = self.ha._remote_files();prefix = 'memory/items/'+saved['item']+'/revisions/'+saved['revision']+'/'
        record = json.loads(files[prefix+'record.json']);record['files']['BODY.md']['sha256'] = store.sha(b'Changed')
        remote = self.provider.transport({'repository': 'fixture/team-hub'})
        base = store.git(remote, 'rev-parse', 'main').decode().strip()
        commit = store.commit_files(remote, base, {prefix+'BODY.md': b'Changed', prefix+'record.json': store.encoded(record)}, 'Fixture manual mutation', 'Fixture')
        store.git(remote, 'update-ref', 'refs/heads/main', commit)
        with self.assertRaisesRegex(store.HubError, 'modified'):self.hb.refresh()
        self.assertEqual(Path(self.hb.read(saved['item'])['paths']['BODY.md']).read_text(), 'Original')

    def test_offline_status_cache_and_busy_lock_are_honest(self):
        self.provider.unavailable = True
        self.assertFalse(self.ha.refresh()['fresh'])
        (self.ha.root / '.hub.lock').write_text('Busy')
        with self.assertRaisesRegex(store.HubError, 'running'):self.ha.sync()
        self.assertFalse(self.ha.status()['fresh'])

if __name__ == '__main__':unittest.main()
