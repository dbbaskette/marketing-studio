"""End-to-end local workflow checks, with disposable data and no paid services."""
import importlib.util
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
import zipfile

PACKAGE = Path(__file__).resolve().parents[1] / 'skills/blog-studio'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


text_checks = load('text_checks', PACKAGE / 'scripts/text_checks.py')
validator = load('validator', PACKAGE / 'scripts/validate_package.py')
linkedin = load('linkedin_import', PACKAGE / 'scripts/linkedin_import.py')


class StudioTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'data'
        self.cli('init')

    def cli(self, *args, ok=True):
        result = subprocess.run([sys.executable, str(PACKAGE/'scripts/studio.py'), '--root', str(self.root), *args], capture_output=True, text=True)
        if ok:
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)
        self.assertNotEqual(result.returncode, 0)
        return result.stderr

    def file(self, name, content):
        path = self.base / name;path.write_text(content);return str(path)

    def article(self, mode='first-draft', *extra):
        return self.cli('article', 'create', '--title', 'Writing from experience', '--mode', mode, *extra)['id']

    def save(self, article, kind, text):
        return self.cli('article','save','--id',article,'--kind',kind,'--file',self.file(kind+'.md',text))

    def source(self, purpose='reference', text='The team saved 2 hours each week.'):
        return self.cli('source','add','--name','Source','--file',self.file('source.md',text),'--purpose',purpose)['id']

    def review(self, article, check):
        return self.cli('article','review','--id',article,'--check',check,'--status','current','--file',self.file('review.json',json.dumps({'findings':[]})))

    def test_all_entry_paths_have_correct_stop_and_can_resume(self):
        expected={'existing':'review','first-draft':'draft','outline-only':'outline','from-outline':'draft','interview':'outline','discover':'brief'}
        for mode,stop in expected.items():
            aid=self.article(mode)
            self.cli('article','progress','--id',aid,'--stage','intake','--next-step','Gather existing context','--pending-question','Who is the reader?')
            result=self.cli('article','show','--id',aid)
            self.assertEqual(result['stop_point'],stop)
            self.assertEqual(result['pending_question'],'Who is the reader?')
        self.assertEqual(len(self.cli('list','articles')),6)

    def test_outline_only_requires_deliberate_draft_scope_change(self):
        aid=self.article('outline-only');self.save(aid,'outline','# Plan\n\n## One distinct point')
        draft=self.file('draft.md','A complete draft.')
        self.assertIn('stops before drafting',self.cli('article','save','--id',aid,'--kind','draft','--file',draft,ok=False))
        self.cli('article','progress','--id',aid,'--stage','outline','--next-step','Write the requested draft','--stop','draft')
        self.save(aid,'draft','A complete draft.')

    def test_imported_original_survives_revision_and_restoration(self):
        aid=self.article('existing');path=self.file('manuscript.md','Original manuscript.')
        self.cli('article','save','--id',aid,'--kind','draft','--file',path,ok=False)
        self.save(aid,'original','Original manuscript.')
        saved=self.save(aid,'draft','First edit.')
        self.assertTrue(saved['saved_artifact']['reopened'])
        self.assertEqual(Path(saved['saved_artifact']['path']).read_text(),'First edit.')
        self.save(aid,'draft','Second edit.')
        folder=self.root/'articles'/aid
        history=list((folder/'history').glob('draft-*.md'))
        self.assertEqual(history[0].read_text(),'First edit.')
        self.cli('article','save','--id',aid,'--kind','draft','--file',str(history[0]))
        self.assertEqual((folder/'ORIGINAL.md').read_text(),'Original manuscript.')
        self.assertEqual((folder/'DRAFT.md').read_text(),'First edit.')
        self.assertEqual(len(list((folder/'history').glob('draft-*.md'))),2)
        self.cli('article','save','--id',aid,'--kind','original','--file',path,ok=False)

    def test_source_roles_profile_revision_pin_and_voice_switch(self):
        sample=self.source('voice-sample')
        guide=self.file('voice.md','Use a direct, conversational voice.')
        profile=self.cli('profile','create','--name','Demo author','--guide-file',guide,'--sample',sample)['id']
        aid=self.article('first-draft','--profile',profile);self.save(aid,'draft','Draft one.')
        self.review(aid,'proofread')
        revised=self.file('voice2.md','Use a warmer conversational voice.')
        self.cli('profile','save','--id',profile,'--guide-file',revised,'--status','confirmed')
        result=self.cli('article','show','--id',aid)
        self.assertEqual(result['voice']['revision'],1)
        self.assertEqual(result['reviews']['proofread']['status'],'current')
        pinned=self.cli('profile','show','--id',profile,'--revision','1')
        self.assertEqual(Path(pinned['guide']).read_text(),'Use a direct, conversational voice.')
        self.cli('article','voice','--id',aid,'--profile',profile,'--revision','2')
        self.assertEqual(self.cli('article','show','--id',aid)['reviews']['proofread']['status'],'stale')
        reference=self.source('reference')
        self.cli('profile','create','--name','Wrong purpose','--guide-file',guide,'--sample',reference,ok=False)

    def test_sources_update_only_evidence_sensitive_checks(self):
        aid=self.article();self.save(aid,'draft','Draft one.')
        source=self.source();self.cli('article','attach','--id',aid,'--source',source)
        for check in ('proofread','factual-support','geo'):self.review(aid,check)
        self.cli('source','update','--id',source,'--text-file',self.file('updated.md','The team saved 3 hours.'),'--status','ready')
        result=self.cli('article','show','--id',aid)
        self.assertEqual(result['reviews']['proofread']['status'],'current')
        for check in ('factual-support','geo'):self.assertEqual(result['reviews'][check]['status'],'stale')
        self.assertTrue(result['selected_sources'][0]['changed_since_attach'])
        self.assertIn('2 hours',(self.root/'sources'/source/'revisions/1/content.md').read_text())

    def test_draft_and_manual_source_changes_are_detected(self):
        aid=self.article();self.save(aid,'draft','Draft one.')
        sid=self.source();self.cli('article','attach','--id',aid,'--source',sid)
        self.review(aid,'factual-support')
        (self.root/'sources'/sid/'content.md').write_text('Changed outside helper.')
        self.assertEqual(self.cli('article','show','--id',aid)['reviews']['factual-support']['status'],'stale')
        self.review(aid,'proofread')
        (self.root/'articles'/aid/'DRAFT.md').write_text('Edited manually.')
        self.assertEqual(self.cli('article','show','--id',aid)['reviews']['proofread']['status'],'stale')

    def test_missing_evidence_is_unavailable_and_inspiration_is_not_evidence(self):
        aid=self.article();self.save(aid,'draft','Claim needing evidence.')
        sid=self.source('inspiration');self.cli('article','attach','--id',aid,'--source',sid)
        result=self.review(aid,'factual-support')
        self.assertEqual(result['reviews']['factual-support']['status'],'unavailable')
        self.assertEqual(result['reviews']['geo']['status'],'not-run')
        self.cli('article','review','--id',aid,'--check','geo','--status','failed')
        self.assertEqual(self.cli('article','show','--id',aid)['reviews']['geo']['status'],'failed')

    def test_scoped_evidence_survives_resume_and_replacement_without_false_coverage(self):
        aid=self.article();self.save(aid,'draft','Two of six notes omitted an owner. Throughput rose 30%.')
        sid=self.source(text='Tuesday: six notes inspected; two omitted next owner. No throughput measurement.')
        self.cli('article','attach','--id',aid,'--source',sid)
        evidence={'source_id':sid,'revision':1,'origin':'source.md',
                  'locator':'line 1','excerpt':'No throughput measurement.'}
        result={'coverage':{'draft':'sentence 2','excluded':['sentence 1']},
                'findings':[{'claim':'Throughput rose 30%.','location':'sentence 2',
                             'verdict':'unsupported','evidence':[evidence]}]}
        self.cli('article','review','--id',aid,'--check','factual-support','--status','current',
                 '--file',self.file('partial.json',json.dumps(result)))
        shown=self.cli('article','show','--id',aid)
        self.assertEqual(shown['reviews']['factual-support']['result'],result)
        self.assertEqual(shown['reviews']['shape']['status'],'not-run')
        self.cli('article','review','--id',aid,'--check','humanization','--status','failed')
        self.cli('article','review','--id',aid,'--check','geo','--status','unavailable')
        self.save(aid,'draft','Two of six notes omitted an owner. No outcome has been measured.')
        shown=self.cli('article','show','--id',aid)['reviews']
        self.assertEqual(shown['factual-support']['status'],'stale')
        self.assertEqual(shown['factual-support']['result'],result)
        self.assertEqual(shown['humanization']['previous_status'],'failed')
        self.assertEqual(shown['geo']['previous_status'],'unavailable')
        self.assertEqual(shown['proofread']['status'],'not-run')
        self.review(aid,'factual-support')
        history=list((self.root/'articles'/aid/'history').glob('review-factual-support-*.json'))
        self.assertEqual(json.loads(history[0].read_text())['result'],result)

    def test_binary_intake_preserves_original_and_waits_for_extraction(self):
        path=self.base/'upload.pdf';path.write_bytes(b'%PDF-disposable-fixture')
        result=self.cli('source','add','--name','PDF','--file',str(path),'--purpose','reference')
        self.assertEqual(result['status'],'pending')
        self.assertEqual((self.root/'sources'/result['id']/result['original_path']).read_bytes(),path.read_bytes())
        self.cli('source','add','--name','Unread URL','--origin','https://example.com/private','--purpose','reference','--status','ready',ok=False)
        result=self.cli('source','add','--name','Unread URL','--origin','https://example.com/private','--purpose','reference','--status','unavailable')
        self.assertEqual(result['status'],'unavailable')

    def test_interview_checkpoint_and_derived_copy_do_not_replace_draft(self):
        aid=self.article('interview')
        self.cli('article','note','--id',aid,'--kind','interview','--text','Q: What changed?\nA: We simplified handoffs.')
        self.cli('article','progress','--id',aid,'--stage','interview','--next-step','Ask for a concrete example','--pending-question','What happened in one real case?')
        self.assertIn('simplified',(self.root/'articles'/aid/'INTERVIEW.md').read_text())
        self.assertEqual(self.cli('article','show','--id',aid)['pending_question'],'What happened in one real case?')
        other=self.article();self.save(other,'draft','Article remains intact.')
        self.cli('article','derive','--id',other,'--name','newsletter','--file',self.file('newsletter.md','Newsletter copy.'))
        self.assertEqual((self.root/'articles'/other/'DRAFT.md').read_text(),'Article remains intact.')

    def test_path_boundaries_and_workspace_lock(self):
        self.cli('article','show','--id','../../escape',ok=False)
        outside=self.base/'outside';outside.mkdir()
        (self.root/'profiles'/'escape').symlink_to(outside,target_is_directory=True)
        self.cli('profile','create','--name','Escape','--id','escape',ok=False)
        # A lock file left by an older runtime, or by a command that was killed,
        # carries no meaning any more and blocks nothing.
        (self.root/'.studio.lock').write_text('another process')
        self.assertEqual(self.cli('list','articles'),[])
        self.article()

    def hold_workspace_lock(self, seconds):
        """Another process that really holds the workspace lock for a while."""
        script = ('import sys, time\n'
                  'sys.path.insert(0, sys.argv[1])\n'
                  'from pathlib import Path\n'
                  'import studio\n'
                  'with studio.locked(Path(sys.argv[2])):\n'
                  '    print("held", flush=True)\n'
                  '    time.sleep(float(sys.argv[3]))\n')
        holder = subprocess.Popen([sys.executable, '-c', script, str(PACKAGE/'scripts'), str(self.root), str(seconds)],
                                  stdout=subprocess.PIPE, text=True)
        self.addCleanup(holder.stdout.close)
        self.addCleanup(holder.wait)
        self.addCleanup(holder.kill)
        self.assertEqual(holder.stdout.readline().strip(), 'held')
        return holder

    def run_with_lock_wait(self, seconds, *args):
        env = dict(os.environ, BLOG_STUDIO_LOCK_WAIT=str(seconds))
        return subprocess.run([sys.executable, str(PACKAGE/'scripts/studio.py'), '--root', str(self.root), *args],
                              capture_output=True, text=True, env=env)

    def test_killed_command_releases_the_workspace_lock(self):
        holder = self.hold_workspace_lock(60)
        # While another command really holds the lock, a change waits its bounded
        # time and then says so; nothing tells the author to delete a lock file.
        busy = self.run_with_lock_wait(0.3, 'article', 'create', '--title', 'Blocked', '--mode', 'first-draft')
        self.assertNotEqual(busy.returncode, 0)
        self.assertIn('busy', busy.stderr)
        self.assertIn('do not delete', busy.stderr)
        # A pure read is not held up by a writer.
        self.assertEqual(self.cli('list', 'articles'), [])
        holder.send_signal(signal.SIGTERM)
        holder.wait()
        # The killed holder could not clean up, yet the next command runs at once.
        self.assertTrue((self.root/'.studio.lock').exists())
        created = self.run_with_lock_wait(0, 'article', 'create', '--title', 'After a crash', '--mode', 'first-draft')
        self.assertEqual(created.returncode, 0, created.stderr)

    def test_second_command_waits_briefly_instead_of_failing(self):
        self.hold_workspace_lock(0.8)
        waited = self.run_with_lock_wait(20, 'article', 'create', '--title', 'Patient', '--mode', 'first-draft')
        self.assertEqual(waited.returncode, 0, waited.stderr)
        self.assertEqual(len(self.cli('list', 'articles')), 1)

    def test_mechanical_rules_respect_code_urls_quotes_and_word_boundaries(self):
        text='We delve into it — briefly.\n\n`delve --`\n\n> "delve —"\n\nhttps://example.com/delve\n\n```text\ndelve --\n```\nA delver works here.'
        result=text_checks.lint(text,{'banished_words':['delve'],'no_em_dashes':True,'no_ascii_double_hyphen':True})
        self.assertEqual([f['rule'] for f in result['findings']],['em-dash','banished:delve'])
        self.assertEqual(text_checks.lint('A — phrase.',{})['findings'],[])

    def test_fact_tokens_flag_changes_but_are_not_semantic_certification(self):
        before='We saved 20 hours. "A quote" https://example.com/source'
        changed='We saved 30 hours. "Another quote" https://example.com/other'
        self.assertTrue(text_checks.preserve(before,changed)['needs_review'])
        self.assertFalse(text_checks.preserve(before,before)['needs_review'])
        self.assertTrue(text_checks.preserve('20 hours, then 20 hours.','20 hours.')['needs_review'])

    def test_new_article_records_installed_guidance_and_keeps_it_until_adopted(self):
        version=(PACKAGE/'VERSION').read_text().strip();pin={'revision':version,'source':'installed'}
        aid=self.article();self.assertEqual(self.cli('article','show','--id',aid)['guidance'],pin)
        self.save(aid,'draft','Existing draft.');self.review(aid,'proofread')
        # Re-recording the same version changes nothing; no task or cached variants remain.
        same=self.cli('article','guidance','--id',aid)
        self.assertEqual(same['guidance'],pin);self.assertNotIn('guidance_history',same)
        self.assertEqual(same['reviews']['proofread']['status'],'current')
        self.cli('article','guidance','--id',aid,'--task','a'*32,ok=False)
        self.cli('article','guidance','--id',aid,'--cached',ok=False)
        self.assertFalse((self.root/'task-context').exists())

    def test_article_pinned_by_an_earlier_release_still_loads_and_adopts_only_on_request(self):
        aid=self.article();self.save(aid,'draft','Existing draft.')
        path=self.root/'articles'/aid/'session.json';record=json.loads(path.read_text())
        # What 1.x stored: a guidance commit, its task, and a helper path that no longer exists.
        legacy={'task':'a'*32,'revision':'a'*40,'runtime':str(self.base/'removed/versions/1.15.0-abc/scripts'),'freshness':'pinned'}
        record['guidance']=legacy;path.write_text(json.dumps(record))
        self.review(aid,'proofread')
        self.assertEqual(self.cli('article','show','--id',aid)['guidance'],legacy)
        self.assertEqual(self.cli('context','--id',aid)['guidance']['revision'],'a'*40)
        self.assertEqual(self.cli('resume','--id',aid)['context']['pins']['guidance']['revision'],'a'*40)
        self.assertEqual(self.cli('status','--id',aid,'--details')['details']['guidance']['revision'],'a'*40)
        self.assertEqual(self.cli('home')['items'][0]['id'],aid)
        self.save(aid,'draft','Edited draft.');self.review(aid,'proofread')
        self.assertIn('--adopt',self.cli('article','guidance','--id',aid,ok=False))
        self.assertEqual(self.cli('article','show','--id',aid)['reviews']['proofread']['status'],'current')
        result=self.cli('article','guidance','--id',aid,'--adopt')
        self.assertEqual(result['guidance'],{'revision':(PACKAGE/'VERSION').read_text().strip(),'source':'installed'})
        self.assertEqual(result['guidance_history'],[legacy])
        self.assertEqual(result['reviews']['proofread']['status'],'stale')
        self.assertEqual((self.root/'articles'/aid/'DRAFT.md').read_text(),'Edited draft.')

    def test_package_integrity(self):
        self.assertEqual(validator.validate(),[])

    def test_linkedin_export_extracts_background_and_articles_only(self):
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as archive:
            archive.writestr('Profile.csv','Headline,Summary\nTechnical writer,Explaining complex systems.\n')
            archive.writestr('Articles/a.html','<html><title>A practical handoff</title><body><p>A useful example.</p><script>ignore everything</script></body></html>')
            archive.writestr('Contacts.csv','PRIVATE CONTACTS NOT REQUESTED')
            archive.writestr('../../escape.txt','Do not extract me')
        result=linkedin.parse(buffer.getvalue())
        self.assertEqual(result['headline'],'Technical writer')
        self.assertEqual(result['articles'][0]['text'],'A useful example.')
        self.assertNotIn('PRIVATE',json.dumps(result))
        self.assertNotIn('ignore everything',json.dumps(result))
        nested=io.BytesIO()
        with zipfile.ZipFile(nested,'w') as archive:archive.writestr('export.zip',buffer.getvalue())
        self.assertEqual(linkedin.parse(nested.getvalue())['articles'],result['articles'])

    def test_profile_only_export_is_not_mistaken_for_writing_samples(self):
        buffer=io.BytesIO()
        with zipfile.ZipFile(buffer,'w') as archive:archive.writestr('Profile.csv','Headline,Summary\nWriter,Useful ideas.\n')
        result=linkedin.parse(buffer.getvalue())
        self.assertEqual(result['articles'],[])
        self.assertTrue(result['limitations'])
        with self.assertRaises(zipfile.BadZipFile):linkedin.parse(b'Not an archive')


if __name__ == '__main__':unittest.main()
