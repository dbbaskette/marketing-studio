"""Creator choices preserve independent verdicts and conservative dependencies."""
import copy
import hashlib
import json
import tempfile
from pathlib import Path
import unittest
import marketing_studio
from studio_core import research_decisions as decisions, research_contract as rc
from synthesis_fixture import dossier


def flagged():
    value = dossier('synthetic-author')
    value.update(owner=rc.OWNER, digest='base', status='needs-revision')
    value['facts'].append({**copy.deepcopy(value['facts'][0]), 'id': 'fact-b', 'statement': 'A separate retained claim.'})
    value['findings'][1].update(support=['fact-b'], conditions=[], summary={'text':'Retained finding.', 'refs':['fact-b'], 'kind':'summary'})
    value['review'] = {'digest':'base', 'accepted':False, 'originals':[{'source':'source-a','read_original':True}],
        'facts':[{'id':'fact-a','verdict':'unsupported','note':'Could not independently confirm.'},
                 {'id':'fact-b','verdict':'supported','note':'Confirmed.'}],
        'findings':[], 'prose':[], 'assessment':{'coverage':'accurate','usefulness':'adequate','note':'Bounded.'}}
    return value


class DecisionsTests(unittest.TestCase):
    def test_plain_inclusion_keeps_original_prose_and_citations_with_separate_audit(self):
        base = flagged()
        value, files = decisions.build(base, {'facts:fact-a': 'include-plain'}, {})
        for key in ('facts', 'findings', 'sections', 'brief', 'review'):
            self.assertEqual(value[key], base[key])
        self.assertIn('fact-a', value['creator_review']['uncertain'])
        self.assertEqual(value['creator_review']['warned'], [])
        for name in ('report.md', 'brief.md'):
            self.assertNotIn('warning', files[name])
            self.assertNotIn('independent-check notes', files[name])
        self.assertIn('**Included**', files['evidence.md'])
        self.assertIn('Could not independently confirm', files['evidence.md'])
        self.assertEqual(json.loads(files['creator.json'])['schema'], 2)

    def test_plain_unreviewed_draft_and_mixed_dependency_choices(self):
        base = flagged(); base['review'] = None
        value = decisions.resolve(base, {'assessment:unreviewed': 'include-plain'})
        self.assertEqual(value['facts'], base['facts'])
        self.assertIsNone(value['review'])
        base = flagged()
        base['review']['originals'][0].update(read_original=False, access_error='Not read.')
        for source_choice, fact_choice in [('include', 'include-plain'), ('include-plain', 'include')]:
            value = decisions.resolve(base, {'originals:source-a': source_choice, 'facts:fact-a': fact_choice})
            self.assertIn('warning', value['facts'][0]['statement'])
            self.assertIn('warning', value['sections'][0]['blocks'][0]['text'])
        value = decisions.resolve(base, {'originals:source-a': 'include-plain', 'facts:fact-a': 'exclude'})
        self.assertEqual([f['id'] for f in value['facts']], ['fact-b'])
        self.assertEqual(value['facts'][0], base['facts'][1])

    def test_legacy_receipts_rebuild_byte_for_byte(self):
        # Captured from the previous implementation, including the unreviewed flag's old wording.
        hashes = [
            ['8620ab3b5f844f9c242b081d206f510665d832f4f24193b05564a6a9ddbf0308', '12ec01e760abaf52cfc28b93f5b11f70a8e97d20280a0beaa468a61e7492e68a', '86ad967af590bd9455c2ec006a913ab6b25085196787758ba5e6c48f9daf2f26', '2e07c9429fdea4f2ae62796dc4424d97cc215bbef95945970fb3baf3e471d831', '50a2534da081e46edec07129990021bfc51d543b75e98d74fea61b2db92c5be8'],
            ['b709d4a82141253e70cc0523f78d6a98d54a21c9a621eb4e627be59f49f715d8', '37fa60d58123fd3ce50bba33eb69d364d8a19da00e107df43c063d7dfd00d96b', 'f65f4538d807b40855ca1530658c814fabdf2bd248ea835394ef359f6993cb24', 'cdeb4250f505344bdac1475801facf1a55c31ff33e2fe683d76cdeabe4bcfe6b', '99708e341a1313f33a9c570f51a0407543fb23a3d62ad34b19856774bc1e10bb']]
        for unreviewed in (False, True):
            base = flagged()
            if unreviewed: base['review'] = None
            choices = {row['id']: 'include' for row in decisions.flags(base)}
            value, files = decisions.build(base, choices, {'schema': 1}, schema=1)
            self.assertEqual([hashlib.sha256(text.encode()).hexdigest() for text in files.values()], hashes[unreviewed])
            with tempfile.TemporaryDirectory() as temp:
                for name, text in files.items(): (Path(temp)/name).write_text(text)
                decisions.validate(Path(temp), value, {'status': decisions.STATUS})
        with self.assertRaises(ValueError):
            decisions.build(flagged(), {'facts:fact-a': 'include-plain'}, {}, schema=1)

    def test_excluding_fact_omits_dependent_finding_and_both_prose_surfaces(self):
        value = decisions.resolve(flagged(), {'facts:fact-a':'exclude'})
        self.assertEqual([f['id'] for f in value['facts']], ['fact-b'])
        self.assertEqual([f['id'] for f in value['findings']], ['health-checks'])
        self.assertIn('Omitted', value['sections'][0]['blocks'][0]['text'])
        self.assertIn('Omitted', value['brief'][0]['blocks'][0]['text'])
        self.assertFalse(value['review']['accepted'])

    def test_including_flags_marks_fact_finding_and_dependent_prose(self):
        value = decisions.resolve(flagged(), {'facts:fact-a':'include'})
        for text in [value['facts'][0]['statement'], value['findings'][0]['summary']['text'],
                     value['sections'][0]['blocks'][0]['text'], value['brief'][0]['blocks'][0]['text']]:
            self.assertIn('Creator included with warning', text)
        self.assertEqual(value['review']['facts'][0]['verdict'], 'unsupported')

    def test_no_default_missing_or_unknown_decisions(self):
        for choices in ({}, {'facts:fact-a':'accept'}, {'facts:fact-a':'include','unknown':'include'}):
            with self.assertRaises(ValueError): decisions.resolve(flagged(), choices)

    def test_missing_verdict_is_explicitly_unreviewed_and_marks_all_claims(self):
        base=flagged();base['review']=None
        value=decisions.resolve(base,{'assessment:unreviewed':'include'})
        self.assertTrue(all('warning' in fact['statement'] for fact in value['facts']))
        self.assertTrue(all('warning' in finding['summary']['text'] for finding in value['findings']))
        self.assertIsNone(value['review'])

    def test_unread_source_include_warns_every_dependent_claim(self):
        base = flagged(); base['review']['originals'][0].update(read_original=False,access_error='Not read before allowance ended.')
        choices = {row['id']:'include' for row in decisions.flags(base)}
        result = decisions.resolve(base, choices)
        self.assertTrue(all('warning' in fact['statement'] for fact in result['facts']))
        choices['originals:source-a'] = 'exclude'
        with self.assertRaisesRegex(ValueError, 'no usable'): decisions.resolve(base, choices)

    def test_comparison_cell_exclusion_and_markdown_escape(self):
        base = flagged(); base['review']['facts'][0]['verdict'] = 'supported'
        base['comparisons'] = [{'title':'Comparison', 'subjects':['One','Two'], 'rows':[{'criterion':'Scope','cells':[
            {'subject':'One','text':'<script>no</script>', 'refs':['fact-a']}, {'subject':'Two','text':'Limited.', 'refs':['fact-b']}]}]}]
        base['review']['prose'] = [{'id':'comparison:0:0:0','verdict':'narrow','note':'Too broad.'}]
        result = decisions.resolve(base, {'prose:comparison:0:0:0':'exclude'})
        self.assertNotIn('<script>', decisions.render(result)['report.md'])
        self.assertIn('Omitted', result['comparisons'][0]['rows'][0]['cells'][0]['text'])

    def test_bundle_uses_separate_owner_and_refuses_changed_receipt_even_with_rehashed_manifest(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp); source = root/'source'; source.mkdir(); target=root/'target'
            base = flagged()
            files={'facts.json':json.dumps(base), 'report.md':'Draft', 'brief.md':'Draft', 'evidence.md':'Evidence'}
            entries=[]
            import hashlib
            for name,text in files.items():
                (source/name).write_text(text); entries.append({'file':name,'sha256':hashlib.sha256(text.encode()).hexdigest()})
            (source/'output.json').write_text(json.dumps({'owner':rc.OWNER,'schema':2,'digest':'base','status':'needs-revision','artifacts':entries}))
            value, manifest=decisions.publish(source,target,{'facts:fact-a':'include'}, {'schema':1})
            self.assertEqual(manifest['owner'], decisions.OWNER)
            self.assertFalse(value['review']['accepted'])
            self.assertEqual(rc.read_bundle(source,complete=False)[0],base)
            receipt=json.loads((target/'creator.json').read_text());receipt['choices']['facts:fact-a']='exclude'
            (target/'creator.json').write_text(json.dumps(receipt))
            for entry in manifest['artifacts']:
                entry['sha256']=hashlib.sha256((target/entry['file']).read_bytes()).hexdigest()
            (target/'output.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'different revisions'):rc.read_bundle(target)
