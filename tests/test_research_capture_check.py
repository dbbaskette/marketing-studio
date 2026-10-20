"""A research author learns inside its job when its dossier cites a source the job did not
save, so it can correct the citation instead of losing the whole research step afterwards."""
import json
import unittest

import marketing_studio  # Puts the shared core on the import path.
from studio_core.research_contract import check_json

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


if __name__ == '__main__':
    unittest.main()
