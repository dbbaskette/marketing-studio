"""A research author learns inside its job when its dossier cites a source the job did not
save, so it can correct the citation instead of losing the whole research step afterwards."""
import json
import copy
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import marketing_studio  # Puts the shared core on the import path.
from studio_core.research_contract import check_json, citation_sources
from synthesis_fixture import TEXT, dossier as fixture_dossier

RUNTIME = os.environ.get('STUDIO_TEST_RESEARCH_RUNTIME')
TASK = {'topic': 'Synthetic restart', 'audience': 'Operators',
        'purpose': 'Teach a fictional example', 'scope': 'Synthetic only', 'source_mode': 'public'}
# A stand-in for the helper's save: it needs every cited capture in the case, the task's own
# fields and the worker, and refuses sections that are not an array, as the real one does.
STUB = """import fs from 'node:fs';
import path from 'node:path';
const args = process.argv.slice(2), get = name => args[args.indexOf(name) + 1];
const project = get('--project'), worker = get('--worker');
const d = JSON.parse(fs.readFileSync(path.join(project, get('--file')), 'utf8'));
for (const s of d.sources) if (!fs.existsSync(path.join(project, s.file))) { console.error('Missing ' + s.file); process.exit(1); }
if (d.topic !== 'Synthetic restart' || worker !== 'author-1') { console.error('Wrong task or worker.'); process.exit(1); }
if (!Array.isArray(d.sections)) { console.error('harness-research refused: sections must be an array.'); process.exit(1); }
console.log(JSON.stringify({status: 'draft'}));
"""

SAVED = 'sources/docs-example-com-0123456789ab.txt'
CAPTURES = [
    {'file': SAVED, 'url': 'https://docs.example.com/guide', 'offered': False},
    {'file': 'sources/handbook.txt', 'url': 'Supplied by the team', 'offered': True,
     'permission': 'selected'},
]


def dossier(*sources):
    return json.dumps({'schema': 2, 'facts': [], 'sources': list(sources)})


def source(file, origin, permission):
    return {'id': 's1', 'title': 'A source', 'file': file, 'origin': origin,
            'permission': permission}


class CaptureCheckTests(unittest.TestCase):
    def problems(self, text, captures=CAPTURES):
        return check_json(text, {'kind': 'research-json', 'captures': captures})[0]

    def test_sources_the_job_saved_pass(self):
        self.assertEqual(self.problems(dossier(
            source(SAVED, 'https://docs.example.com/guide', 'public'),
            source('sources/handbook.txt', 'Supplied by the team', 'selected'))), [])

    def test_an_unsaved_file_is_named_beside_the_files_that_may_be_cited(self):
        found = self.problems(dossier(
            source('research/sources/edb.md', 'https://www.example.org/', 'public')))
        self.assertEqual(len(found), 1)
        self.assertIn('research/sources/edb.md', found[0])
        self.assertIn(SAVED, found[0])
        self.assertIn('save_source', found[0])

    def test_a_changed_origin_or_permission_is_refused(self):
        moved = self.problems(dossier(source(SAVED, 'https://docs.example.com/other', 'public')))
        self.assertEqual(len(moved), 1)
        self.assertIn('https://docs.example.com/guide', moved[0])
        widened = self.problems(dossier(
            source('sources/handbook.txt', 'Supplied by the team', 'public')))
        self.assertEqual(len(widened), 1)
        self.assertIn('selected', widened[0])

    def test_a_job_that_saved_nothing_says_so(self):
        found = self.problems(dossier(source(SAVED, 'https://docs.example.com/guide', 'public')),
                              captures=[])
        self.assertIn('none yet', found[0])

    def test_reviews_and_jobs_without_captures_keep_the_schema_check_alone(self):
        self.assertEqual(self.problems(json.dumps({'schema': 2, 'originals': []})), [])
        self.assertEqual(check_json(dossier(source('anything.txt', 'x', 'public')),
                                    {'kind': 'research-json'})[0], [])
        self.assertEqual(self.problems('{"schema": 1}'), ['Return a schema-2 JSON object.'])


class CitationIdentityTests(unittest.TestCase):
    def setUp(self):
        self.value = fixture_dossier('author-1')
        self.captures = [{'id': 's1', 'file': 'sources/source.txt',
                          'url': 'https://example.invalid/docs', 'offered': False}]

    def check(self, value=None, captures=None):
        return check_json(json.dumps(value or self.value), {
            'captures': self.captures if captures is None else captures})

    def test_exact_capture_handle_is_repaired_without_changing_evidence(self):
        self.value['facts'][0]['citations'][0]['source'] = 's1'
        original = copy.deepcopy(self.value)
        problems, checks, warnings, kept = self.check()
        self.assertEqual(problems, [])
        self.assertEqual(checks[0]['status'], 'passed')
        self.assertEqual(len(warnings), 1)
        self.assertIn('Claims and quotations are unchanged', warnings[0])
        self.assertEqual(json.loads(kept), fixture_dossier('author-1'))
        self.assertEqual(self.value, original)

    def test_unknown_reference_names_fact_field_and_valid_ids_before_helper(self):
        self.value['facts'][0]['id'] = 'f01'
        self.value['facts'][0]['citations'][0]['source'] = 'missing'
        with patch('studio_core.research_contract.subprocess.run') as helper:
            problems, _, warnings, _ = check_json(json.dumps(self.value), {
                'captures': self.captures, 'runtime': '/not-used'})
        helper.assert_not_called()
        self.assertEqual(len(problems), 1)
        self.assertIn("facts['f01'].citations[0].source 'missing'", problems[0])
        self.assertIn("Available source IDs: 'source-a'", problems[0])
        self.assertEqual(warnings, [])

    def test_valid_dossier_ids_are_not_reinterpreted_as_handles(self):
        self.captures[0]['id'] = 'source-a'
        sent = json.dumps(self.value, indent=2)
        self.assertEqual(check_json(sent, {'captures': self.captures})[3], sent)
        self.assertEqual(self.check()[2], [])

    def test_quote_url_or_file_is_never_used_to_guess_a_source(self):
        for ref in ('s99', 'SOURCE-A', 'sources/source.txt', 'https://example.invalid/docs',
                    None, ['s1']):
            with self.subTest(ref=ref):
                self.value['facts'][0]['citations'][0]['source'] = ref
                self.assertTrue(self.check()[0])

    def test_a_capture_omitted_from_the_dossier_is_not_inserted(self):
        self.captures.append(dict(self.captures[0], id='s2', file='sources/another.txt'))
        self.value['facts'][0]['citations'][0]['source'] = 's2'
        _, problems, matched = citation_sources(self.value, self.captures)
        self.assertTrue(problems)
        self.assertEqual(matched, 0)

    def test_ambiguous_source_rows_or_handles_are_not_repaired(self):
        self.value['facts'][0]['citations'][0]['source'] = 's1'
        for value, captures in (
            ({**self.value, 'sources': [*self.value['sources'],
                                      dict(self.value['sources'][0], id='second')]}, self.captures),
            (self.value, [*self.captures, dict(self.captures[0], file='sources/another.txt')]),
        ):
            with self.subTest(value=value, captures=captures):
                kept, problems, matched = citation_sources(value, captures)
                self.assertTrue(problems)
                self.assertEqual(matched, 0)
                self.assertEqual(kept, value)

    def test_wrong_origin_or_permission_is_never_mapped(self):
        self.value['facts'][0]['citations'][0]['source'] = 's1'
        for changed in ({'origin': 'https://example.invalid/other'}, {'permission': 'selected'}):
            value = copy.deepcopy(self.value)
            value['sources'][0].update(changed)
            self.assertTrue(self.check(value)[0])
            self.assertEqual(citation_sources(value, self.captures)[2], 0)

    def test_id_bridge_leaves_malformed_source_ids_for_validation_without_crashing(self):
        self.value['sources'][0]['id'] = ['not-an-id']
        self.value['facts'][0]['citations'][0]['source'] = 's1'
        self.assertTrue(self.check()[0])



@unittest.skipUnless(shutil.which('node'), 'needs Node.js')
class HelperCheckTests(unittest.TestCase):
    """The author's dossier is saved with the helper inside the job, as the parent will save it,
    so the author can correct what the helper refuses before its job ends."""

    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.base = Path(holder.name)
        self.job = self.base / 'job'
        (self.job / 'sources').mkdir(parents=True)
        (self.job / 'sources' / 'source.txt').write_text(TEXT)
        self.captures = [{'file': 'sources/source.txt', 'local': 'sources/source.txt',
                          'url': 'https://example.invalid/docs', 'offered': False}]

    def spec(self, runtime):
        return {'kind': 'research-json', 'captures': self.captures, 'folder': str(self.job),
                'runtime': str(runtime), 'node': shutil.which('node'), 'worker': 'author-1',
                'task': TASK}

    def stub(self):
        runtime = self.base / 'runtime'
        (runtime / 'scripts').mkdir(parents=True, exist_ok=True)
        (runtime / 'scripts' / 'harness-research.mjs').write_text(STUB)
        (runtime / 'references').mkdir(exist_ok=True)
        (runtime / 'references/synthesis.schema.json').write_text(json.dumps({'$defs': {'source': {'properties': {
            key: {} for key in ('id', 'origin', 'title', 'publisher', 'file', 'permission', 'context',
                               'context_note', 'source_date', 'accessed_at', 'version', 'original_file')}}}}))
        return runtime

    def test_what_the_helper_refuses_is_said_in_the_job(self):
        value = fixture_dossier('author-1')
        value['topic'] = 'Rewritten by the author'
        self.assertEqual(check_json(json.dumps(value), self.spec(self.stub()))[0], [])
        value['sections'] = {'explain': value['sections'][0]}
        found = check_json(json.dumps(value), self.spec(self.stub()))[0]
        self.assertEqual(len(found), 1)
        self.assertIn('sections must be an array', found[0])
        self.assertIn('hand the whole dossier back', found[0])

    def test_facts_must_name_the_author_of_this_job(self):
        found = check_json(json.dumps(fixture_dossier('author-2')), self.spec(self.stub()))[0]
        self.assertEqual(found, ['Set every fact author to author-1.'])

    @unittest.skipUnless(RUNTIME, 'set STUDIO_TEST_RESEARCH_RUNTIME to a Harness Research runtime')
    def test_the_real_helper_accepts_a_valid_dossier_and_refuses_a_broken_one(self):
        self.assertEqual(check_json(json.dumps(fixture_dossier('author-1')), self.spec(RUNTIME))[0], [])
        broken = fixture_dossier('author-1')
        broken['sections'] = {'explain': broken['sections'][0]}
        found = check_json(json.dumps(broken), self.spec(RUNTIME))[0]
        self.assertEqual(len(found), 1)
        self.assertIn('Harness Research refused this dossier', found[0])

    @unittest.skipUnless(RUNTIME, 'set STUDIO_TEST_RESEARCH_RUNTIME to a Harness Research runtime')
    def test_real_helper_rechecks_the_quote_after_exact_handle_repair(self):
        self.captures[0]['id'] = 's1'
        value = fixture_dossier('author-1')
        value['facts'][0]['citations'][0]['source'] = 's1'
        checked = check_json(json.dumps(value), self.spec(RUNTIME))
        self.assertEqual(checked[0], [])
        self.assertEqual(json.loads(checked[3]), fixture_dossier('author-1'))
        value['facts'][0]['citations'][0]['quote'] = 'Words this source never said.'
        checked = check_json(json.dumps(value), self.spec(RUNTIME))
        self.assertTrue(checked[0])
        self.assertIn('Exact quote not found', checked[0][0])
        self.assertEqual(checked[2], [], 'a refused dossier is not described as repaired')


if __name__ == '__main__':
    unittest.main()
