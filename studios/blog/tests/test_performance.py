"""Exact-input reuse and bounded disclosure; no live accounts or models."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from hub_fixtures import SCRIPTS, FakeProvider
import studio
import performance as perf
import local_cache
import local_reads
import text_checks
from hub import Registry
from hub_workspace import Workspace


class PerformanceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name).resolve();self.root=self.base/'work';studio.initialize(self.root)
        self.aid=self.call('article','create','--title','Fixture','--mode','first-draft')['id']
        self.draft='# Heading\n\nAn opening — with a rule violation.\n\n## Second\n\nSecond paragraph.'
        self.save(self.draft)
    def file(self,name,text):
        p=self.base/name;p.write_text(text);return str(p)
    def call(self,*words):
        args=studio.parser().parse_args(['--root',str(self.root),*words])
        with studio.locked(self.root):return getattr(studio,args.group+'_command')(self.root,args)
    def save(self,body):
        return self.call('article','save','--id',self.aid,'--kind','draft','--file',self.file('draft.md',body))
    def source(self,body='First evidence.'):
        source=self.call('source','add','--name','Source','--file',self.file('source.md',body),'--purpose','reference')
        self.call('article','attach','--id',self.aid,'--source',source['id'])
        return source['id']
    def test_extraction_reuses_only_identical_bytes_format_and_version(self):
        raw=b'<p>Useful <b>evidence</b>.</p><script>PRIVATE SCRIPT</script>'
        first,hit=perf.extract(self.root,raw,'.html');self.assertFalse(hit)
        self.assertNotIn('PRIVATE',first['text']);self.assertIn('evidence',first['text'])
        self.assertTrue(perf.extract(self.root,raw,'.html')[1])
        self.assertFalse(perf.extract(self.root,raw+b'Changed','.html')[1])
        self.assertFalse(perf.extract(self.root,raw,'.txt')[1])
        with patch.object(perf,'EXTRACTOR_VERSION','v2'):self.assertFalse(perf.extract(self.root,raw,'.html')[1])
        with self.assertRaises(ValueError):perf.extract(self.root,b'bad','.pdf')
        before=local_cache.maintain(self.root)['entries']
        with self.assertRaises(UnicodeError):perf.extract(self.root,b'\xff','.txt')
        self.assertEqual(local_cache.maintain(self.root)['entries'],before)
    def test_html_intake_retains_original_and_extraction_provenance(self):
        path=self.file('source.html','<h1>Heading</h1><p>Evidence</p>')
        record=self.call('source','add','--name','HTML','--file',path,'--purpose','reference')
        directory,_=studio.item(self.root,'sources',record['id'])
        self.assertEqual((directory/'original.html').read_bytes(),Path(path).read_bytes())
        self.assertEqual(record['extraction']['source_sha256'],record['original_sha256'])
        self.assertEqual(record['status'],'ready')
    def test_review_reuse_all_dependencies_and_version(self):
        sid=self.source();rules={'no_em_dashes':True}
        first=perf.check(self.root,self.aid,rules);self.assertFalse(first['cache_hit'])
        with patch.object(text_checks,'lint',side_effect=AssertionError('should reuse')):
            reused=perf.check(self.root,self.aid,rules)
        self.assertTrue(reused['cache_hit']);self.assertEqual(reused['result'],first['result'])
        self.assertFalse(perf.check(self.root,self.aid,{})['cache_hit'])
        for field,value in [('voice',{'mode':'tone','tone':'Formal'}),('guidance',{'revision':'b'*40}),
                            ('memory',{'audience':{'status':'active','revision':1,'text':'Engineers'}}),
                            ('hub_context',{'selected':[{'item':'rule','revision':'new'}]})]:
            directory,record=studio.item(self.root,'articles',self.aid)
            record[field]=value;studio.persist(directory,'articles',record)
            self.assertFalse(perf.check(self.root,self.aid,rules)['cache_hit'],field)
        self.call('source','update','--id',sid,'--text-file',self.file('updated.md','Updated evidence.'))
        self.assertFalse(perf.check(self.root,self.aid,rules)['cache_hit'])
        with patch.object(perf,'CHECK_VERSION','v2'):self.assertFalse(perf.check(self.root,self.aid,rules)['cache_hit'])
    def test_moved_deleted_passages_recompute_and_never_mark_reviews_clean(self):
        first=perf.check(self.root,self.aid,{'no_em_dashes':True})
        self.save('New beginning.\n\n'+self.draft)
        moved=perf.check(self.root,self.aid,{'no_em_dashes':True})
        self.assertFalse(moved['cache_hit'])
        self.assertNotEqual(first['result']['findings'][0]['start'],moved['result']['findings'][0]['start'])
        self.save('No restricted punctuation.')
        self.assertFalse(perf.check(self.root,self.aid,{'no_em_dashes':True})['cache_hit'])
        directory,record=studio.item(self.root,'articles',self.aid)
        self.assertEqual(studio.freshness(self.root,directory,record)['proofread']['status'],'not-run')
        self.call('article','review','--id',self.aid,'--check','proofread','--status','failed')
        perf.check(self.root,self.aid,{})
        directory,record=studio.item(self.root,'articles',self.aid)
        self.assertEqual(studio.freshness(self.root,directory,record)['proofread']['status'],'failed')
    def test_cache_bounds_privacy_corruption_and_clear(self):
        perf.check(self.root,self.aid,{})
        folder=local_cache.folder(self.root)
        self.assertEqual(folder.stat().st_mode&0o777,0o700)
        entry=next(folder.glob('*.json'));self.assertEqual(entry.stat().st_mode&0o777,0o600)
        for malformed in ('broken','[]','null'):
            entry.write_text(malformed);self.assertFalse(perf.check(self.root,self.aid,{})['cache_hit'])
        with patch.object(local_cache,'MAX_ENTRIES',2):
            for n in range(6):local_cache.put(self.root,local_cache.key_for('fixture',n),{'n':n})
            self.assertLessEqual(local_cache.maintain(self.root)['entries'],2)
        before=(self.root/'articles'/self.aid/'DRAFT.md').read_bytes()
        self.assertEqual(local_cache.maintain(self.root,clear=True)['entries'],0)
        self.assertEqual((self.root/'articles'/self.aid/'DRAFT.md').read_bytes(),before)
        other=self.base/'other';other.mkdir();(other/'private').write_text('secret')
        folder.rmdir();folder.symlink_to(other,target_is_directory=True)
        with self.assertRaises(ValueError):local_cache.maintain(self.root,clear=True)
        self.assertEqual((other/'private').read_text(),'secret')
    def test_passages_are_bounded_exact_and_pinned(self):
        body='First selected evidence.\n\n'+'Long evidence '*1000
        sid=self.source(body)
        self.call('source','update','--id',sid,'--text-file',self.file('new.md','New unselected evidence.'))
        result=perf.passages(self.root,self.aid,sid,'evidence',2,0,200)
        self.assertEqual(result['provenance']['revision'],1)
        self.assertLessEqual(sum(len(p['text']) for p in result['passages']),200)
        self.assertTrue(result['truncated'])
        for p in result['passages']:self.assertEqual(p['text'],body[p['start']:p['end']])
        self.assertNotIn('New unselected',json.dumps(result))
        with self.assertRaises(ValueError):perf.passages(self.root,self.aid,'not-selected')
        with self.assertRaises(ValueError):perf.passages(self.root,self.aid,limit=500)
        self.assertTrue(perf.passages(self.root,self.aid,sid)['index_cache_hit'])
    def test_compact_context_pages_sources_and_excludes_history_and_bodies(self):
        for n in range(8):self.source('SOURCE BODY SECRET '+str(n))
        directory,record=studio.item(self.root,'articles',self.aid)
        record['memory']={'audience':{'revision':1,'status':'active','text':'MEMORY BODY SECRET','history':[{'text':'FORGOTTEN'}]}}
        studio.persist(directory,'articles',record)
        result=perf.compact(self.root,self.aid,3)
        self.assertTrue(result['sources_truncated']);self.assertEqual(len(result['sources']),3)
        self.assertEqual(len(perf.compact(self.root,self.aid,3,6)['sources']),2)
        self.assertNotIn('SECRET',json.dumps(result));self.assertNotIn('FORGOTTEN',json.dumps(result))
        self.assertEqual(result['memory'],[{'key':'audience','revision':1}])
        self.assertEqual(result['artifacts']['DRAFT.md'],str(directory/'DRAFT.md'))
    def test_operation_reads_invalidate_edits_identity_and_end_of_operation(self):
        file=self.base/'record.json';file.write_text('{"value":1}')
        with local_reads.operation():
            self.assertEqual(studio.read_json(file)['value'],1)
            file.write_text('{"value":2}')
            self.assertEqual(studio.read_json(file)['value'],2)
            replacement=self.base/'replacement';replacement.write_text('{"value":3}');replacement.replace(file)
            self.assertEqual(studio.read_json(file)['value'],3)
        file.write_text('{"value":4}')
        self.assertEqual(studio.read_json(file)['value'],4)
    def test_cross_member_compact_resume_keeps_pins_and_cache_private(self):
        self.source();perf.check(self.root,self.aid,{})
        provider=FakeProvider(self.base/'remotes')
        ra=Registry(self.base/'ha',provider);rb=Registry(self.base/'hb',provider)
        hid=ra.create('fixture/performance','Performance')['hub'];rb.join('fixture/performance')
        wa=Workspace(self.root,ra.hub(hid))
        reference=wa.publish_selected({'articles':[self.aid]})['items'][0]
        other=self.base/'other';studio.initialize(other);wb=Workspace(other,rb.hub(hid))
        aid=wb.checkout_selected({'articles':[reference['item']]})['items'][0]['local_id']
        with patch('hub_workspace.active',return_value=wb):result=perf.resume(other,aid)
        self.assertEqual(result['context']['source_count'],1)
        self.assertEqual(result['context']['pins']['voice'],{'mode':'preserve','tone':''})
        self.assertFalse((other/'.derived-cache').exists())
        self.assertFalse(any('derived-cache' in p for p in wa.hub.files()))
    def test_same_pin_changed_voice_bytes_and_source_bytes_invalidate(self):
        profile=self.call('profile','create','--name','Writer','--guide-file',self.file('voice.md','Plain voice'),
                          '--rules-file',self.file('rules.json','{}'),'--status','confirmed')
        self.call('article','voice','--id',self.aid,'--profile',profile['id'])
        sid=self.source()
        perf.check(self.root,self.aid,{})
        guide=self.root/'profiles'/profile['id']/'revisions/1/VOICE.md'
        guide.write_text('Changed voice')
        self.assertFalse(perf.check(self.root,self.aid,{})['cache_hit'])
        (self.root/'sources'/sid/'content.md').write_text('Changed evidence without a metadata edit.')
        self.assertFalse(perf.check(self.root,self.aid,{})['cache_hit'])

    def test_failed_check_computation_is_not_cached(self):
        with patch.object(text_checks,'lint',side_effect=ValueError('failed')):
            with self.assertRaises(ValueError):perf.check(self.root,self.aid,{})
        self.assertFalse(perf.check(self.root,self.aid,{})['cache_hit'])


if __name__=='__main__':unittest.main()
