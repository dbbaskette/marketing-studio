"""Creator choices preserve independent verdicts and conservative dependencies."""
import copy
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
