"""Reading many sources in groups: bounds, saved notes, the hand-back check and who gets what."""
import json
from pathlib import Path
import tempfile
import unittest

import marketing_studio  # noqa: F401
from studio_core import research_reading as reading


def documents(count, size=200):
    return [{'file': f'sources/selected/doc-{n:04d}.txt', 'text': f'Synthetic document {n}. ' + 'x' * size,
             'title': f'Document {n}', 'origin': f'https://example.invalid/{n}', 'permission': 'selected'}
            for n in range(count)]


AREAS = [{'id': 'area-one', 'questions': [{'id': 'q1', 'question': 'How is capacity kept?'}]},
         {'id': 'area-two', 'questions': [{'id': 'q2', 'question': 'What does a restart cost?'}]}]


def notes(group, bears=lambda n: [{'area': 'a1', 'rank': 1}]):
    return {'schema': 1, 'summary': 'A synthetic group.', 'notes': [
        {'source': f's{n}', 'covers': 'Synthetic notes.', 'terms': ['capacity'], 'read': 'full', 'bears_on': bears(n)}
        for n in range(1, len(group) + 1)]}


class ReadingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()

    def test_groups_hold_at_most_fifty_documents_and_a_bounded_amount_of_text(self):
        self.assertFalse(reading.needed(documents(50)))
        self.assertTrue(reading.needed(documents(51)))
        found = reading.groups(documents(766))
        self.assertEqual((len(found), max(map(len, found)), sum(map(len, found))), (16, 50, 766))
        self.assertEqual(found, reading.groups(list(reversed(documents(766)))), 'the same groups whatever order they arrive in')
        heavy = reading.groups(documents(10, size=150_000))
        self.assertTrue(all(sum(len(d['text']) for d in group) <= reading.GROUP_CHARS for group in heavy))
        self.assertEqual(sum(map(len, heavy)), 10)
        alone = reading.groups(documents(2, size=reading.GROUP_CHARS + 1))
        self.assertEqual([len(group) for group in alone], [1, 1], 'a document too long to share is read alone')
        public = [{**documents(1)[0], 'permission': 'public'}]
        self.assertFalse(reading.needed(documents(50) + public), 'pages found during research are not counted')

    def test_notes_are_kept_per_document_so_a_retry_or_an_added_source_reads_only_what_is_new(self):
        sources = documents(120)
        waiting = reading.waiting(self.root, sources, AREAS)
        self.assertEqual([len(group) for group in waiting], [50, 50, 20])
        reading.keep(self.root, waiting[0], AREAS, notes(waiting[0]), 'reader-one')
        self.assertEqual([len(group) for group in reading.waiting(self.root, sources, AREAS)], [50, 20])
        for group in waiting[1:]:
            reading.keep(self.root, group, AREAS, notes(group), 'reader-two')
        self.assertEqual(reading.waiting(self.root, sources, AREAS), [])
        more = sources + [{**documents(1)[0], 'file': 'sources/selected/new.txt', 'text': 'A new synthetic page.'}]
        self.assertEqual([[d['file'] for d in group] for group in reading.waiting(self.root, more, AREAS)],
                         [['sources/selected/new.txt']])
        changed = [{**sources[0], 'text': 'Rewritten.'}] + sources[1:]
        self.assertEqual(sum(map(len, reading.waiting(self.root, changed, AREAS))), 1)
        other = [{'id': 'area-three', 'questions': [{'id': 'q3', 'question': 'A different question'}]}]
        self.assertEqual(sum(map(len, reading.waiting(self.root, sources, other))), 120,
                         'different research areas need their own ranking')

    def test_the_hand_back_needs_one_note_for_every_document_the_job_opened(self):
        group = documents(3)
        spec = reading.spec(group, AREAS)
        self.assertEqual(spec, {'kind': 'reading-notes', 'documents': ['s1', 's2', 's3'], 'areas': ['a1', 'a2']})
        good = notes(group)
        self.assertEqual(reading.check(json.dumps(good), spec)[0], [])
        self.assertEqual(reading.check('not json', spec)[0], ['Return the notes as one JSON object.'])
        short = {**good, 'notes': good['notes'][:2]}
        self.assertIn('Missing: s3', ' '.join(reading.check(json.dumps(short), spec)[0]))
        extra = {**good, 'notes': good['notes'] + [{**good['notes'][0], 'source': 's9'}]}
        self.assertIn('name one of the documents you were given', ' '.join(reading.check(json.dumps(extra), spec)[0]))
        twice = {**good, 'notes': good['notes'] + [good['notes'][0]]}
        self.assertIn('not two', ' '.join(reading.check(json.dumps(twice), spec)[0]))
        wrong = notes(group, bears=lambda n: [{'area': 'a7', 'rank': 9}])
        said = ' '.join(reading.check(json.dumps(wrong), spec)[0])
        self.assertIn('rank of 1, 2 or 3', said)
        self.assertEqual(said.count('bears_on'), 3, 'everything wrong is said at once')
        # Inside a job, a note counts only for a document the job's own tools opened.
        folder = self.root / 'job'; folder.mkdir()
        (folder / 'tools.log').write_text('\n'.join(json.dumps(
            {'tool': 'read_source', 'ok': True, 'given': {'source_id': ident}}) for ident in ('s1', 's2')) + '\n')
        said = reading.check(json.dumps(good), {**spec, 'folder': str(folder)})[0]
        self.assertEqual(said, ['Read each document with read_source before noting it. Not opened: s3.'])
        with (folder / 'tools.log').open('a') as log:
            log.write(json.dumps({'tool': 'read_source', 'ok': True, 'given': {'source_id': 's3'}}) + '\n')
        self.assertEqual(reading.check(json.dumps(good), {**spec, 'folder': str(folder)})[0], [])

    def test_each_area_is_given_its_best_fifty_and_the_rest_are_accounted_for(self):
        sources = documents(130)
        def bears(group):
            def of(n):
                number = int(group[n - 1]['file'][-8:-4])
                if number < 70: return [{'area': 'a1', 'rank': 1 if number < 10 else 2}]
                if number < 100: return [{'area': 'a2', 'rank': 3}, {'area': 'a1', 'rank': 3}]
                return []
            return of
        for group in reading.waiting(self.root, sources, AREAS):
            value = notes(group, bears(group))
            if group[0]['file'].endswith('0100.txt') or any(d['file'].endswith('0129.txt') for d in group):
                for note, document in zip(value['notes'], group):
                    if document['file'].endswith('0129.txt'): note['read'] = 'unreadable'
            reading.keep(self.root, group, AREAS, value, 'reader')
        plan = reading.assign(self.root, sources, AREAS)
        one, two = plan['assignment']['area-one'], plan['assignment']['area-two']
        self.assertEqual((len(one), len(two)), (50, 30))
        self.assertEqual(one[:10], [f'sources/selected/doc-{n:04d}.txt' for n in range(10)], 'the most central come first')
        self.assertEqual(plan['dropped'], {'area-one': 50})
        self.assertEqual(len(plan['unused']), 30)
        self.assertTrue(all(file.endswith(tuple(f'{n:04d}.txt' for n in range(100, 130))) for file in plan['unused']))
        self.assertEqual(plan, reading.assign(self.root, list(reversed(sources)), AREAS))


if __name__ == '__main__':
    unittest.main()
