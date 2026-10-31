"""One explicit Google Doc of a guide or brief from the desk, for a training made with local
copies only (issue #222): a new Doc of exactly the version shown, an update of the Doc it is
then linked to, and no second Doc after an uncertain answer unless the person asks. Ready
stays the person's local approval and never sends anything by itself here. A pretend Drive
and the stand-ins of the runner tests; nothing reaches Google. Tests named row_197 to
row_199 cover those rows of the state-transition matrix in
docs/superpowers/plans/2026-10-12-training-studio-core-pipeline.md."""
import helpers  # noqa: F401  the path-setting imports must come before runner
import gdocs
import workspace
from test_runner_deck import PageCase
from workspace import WorkspaceError

from runner import copies, drafts

NAME = 'document'


class DocDeliveryTests(PageCase):

    def local_training(self, **changes):
        root = self.start(**changes)
        self.assertEqual(self.to_end(root), [])
        return root

    def seen(self, root, name=NAME):
        session = workspace.load(root)
        return workspace.sha256_file(root / workspace.artifact(root, session, name)['file'])

    def type_into(self, root, name=NAME, line='One line more.'):
        session = workspace.load(root)
        file = root / workspace.artifact(root, session, name)['file']
        typed = self.base / 'typed.md'
        typed.write_text(file.read_text(encoding='utf-8') + f'\n{line}\n', encoding='utf-8')
        workspace.save(root, name, source=typed, edit=True, via='save')
        workspace.accept_desk(root, name)
        self.engine._commit(root, 'typed on the desk')

    def person(self, root):
        return workspace.person_statuses(root, workspace.load(root))

    def test_row_197_a_local_training_makes_one_doc_of_the_version_shown(self):
        root = self.local_training()
        self.assertEqual(workspace.load(root)['settings']['copies'], [])
        offered = self.get('drafts', path=str(root))['docs'][NAME]
        self.assertEqual((offered['action'], offered['automatic'], offered['problem'],
                          offered['url']), ('create', False, None, None))
        self.assertEqual(offered, self.get('drafts/doc-preview', path=str(root), name=NAME))
        before, jobs, person = self.seen(root), len(self.workers.jobs), self.person(root)
        sent = self.post('drafts/doc', {'path': str(root), 'name': NAME, 'seen': before})
        receipt = sent['doc']
        self.assertEqual((receipt['result'], receipt['sha256']), ('created', before))
        self.assertTrue(receipt['url'].startswith('https://docs.example.com/d/'))
        self.assertEqual(len(self.copies.drive.docs), 1)
        # Exactly what was shown went, and nothing else changed: no Ready, no job, the file
        # as it was, and the training still keeps local copies only.
        self.assertEqual(self.seen(root), before)
        self.assertEqual(self.person(root), person)
        self.assertEqual(len(self.workers.jobs), jobs)
        self.assertEqual(workspace.load(root)['settings']['copies'], [])
        self.assertEqual(self.git('status', '--porcelain'), '')
        self.assertIn('make the Google Doc of the learner guide, as asked on the desk',
                      self.log()[-1])
        shown = sent['docs'][NAME]
        self.assertEqual((shown['action'], shown['current'], shown['receipt']),
                         ('update', True, receipt))
        # Marking it Ready sends nothing by itself: the Doc stays as it was sent.
        docs = dict(self.copies.drive.docs)
        self.type_into(root)
        self.engine.mark_ready(root, NAME, seen=self.seen(root))
        self.assertEqual(self.copies.drive.docs, docs)
        self.assertFalse(self.get('drafts', path=str(root))['docs'][NAME]['current'])

    def test_row_198_a_changed_version_updates_the_same_doc_only_when_asked(self):
        root = self.local_training()
        first = self.seen(root)
        self.engine.deliver_doc(root, NAME, first)
        self.type_into(root)
        with self.assertRaisesRegex(WorkspaceError, 'has changed since it was opened'):
            self.engine.deliver_doc(root, NAME, first)
        done = self.engine.deliver_doc(root, NAME, self.seen(root))['doc']
        self.assertEqual(done['result'], 'updated')
        self.assertEqual(len(self.copies.drive.docs), 1, 'the same Doc, never a second')
        self.assertIn('One line more.', next(iter(self.copies.drive.docs.values())))
        # Someone changed the Doc in Google: it is never written over.
        ident = next(iter(self.copies.drive.docs))
        self.copies.drive.docs[ident] += '\nTheir edit.\n'
        self.type_into(root, line='And another.')
        with self.assertRaisesRegex(WorkspaceError, 'Someone has changed the Google Doc'):
            self.engine.deliver_doc(root, NAME, self.seen(root))
        self.assertIn('Their edit.', self.copies.drive.docs[ident])

    def test_row_199_an_uncertain_answer_never_makes_a_second_doc_unasked(self):
        root = self.local_training()
        seen = self.seen(root)
        self.copies.drive.fail = 'lost'
        with self.assertRaisesRegex(copies.Uncertain, 'It is not known whether Google made '
                                                      'the Doc'):
            self.engine.deliver_doc(root, NAME, seen)
        self.assertEqual(len(self.copies.drive.docs), 1, 'Google made it, and said nothing')
        self.assertEqual(self.git('status', '--porcelain'), '')
        offered = self.engine.doc_preview(root, NAME)
        self.assertTrue(offered['uncertain'])
        reply = self.post('drafts/doc', {'path': str(root), 'name': NAME, 'seen': seen},
                          expect=409)
        self.assertIn('Look in Google Drive first', reply['error'])
        self.assertEqual(len(self.copies.drive.docs), 1)
        # Only the person's explicit Make the Doc anyway makes another.
        done = self.post('drafts/doc', {'path': str(root), 'name': NAME, 'seen': seen,
                                        'again': True})
        self.assertEqual(done['doc']['result'], 'created')
        self.assertEqual(len(self.copies.drive.docs), 2)
        self.assertFalse(done['docs'][NAME]['uncertain'])

    def test_a_sign_in_refused_is_actionable_and_can_be_tried_again(self):
        root = self.local_training()
        self.copies.drive.fail = 'refused'
        with self.assertRaisesRegex(WorkspaceError, 'gcloud auth login') as caught:
            self.engine.deliver_doc(root, NAME, self.seen(root))
        self.assertNotIsInstance(caught.exception, copies.Uncertain)
        self.assertEqual(self.copies.drive.docs, {})
        self.assertFalse(self.engine.doc_preview(root, NAME)['uncertain'])
        self.assertEqual(self.engine.deliver_doc(root, NAME, self.seen(root))['doc']['result'],
                         'created')

    def test_without_google_the_reason_is_said_and_the_local_download_remains(self):
        root = self.local_training()
        self.copies.refuse['google'] = copies.NOT_SET_UP
        offered = self.get('drafts', path=str(root))['docs'][NAME]
        self.assertEqual(offered['problem'], copies.NOT_SET_UP)
        reply = self.post('drafts/doc', {'path': str(root), 'name': NAME,
                                         'seen': self.seen(root)}, expect=409)
        self.assertEqual(reply['error'], copies.NOT_SET_UP)
        self.assertEqual(self.copies.drive.docs, {})
        given = self.page.download(str(root), NAME, None)
        self.assertEqual(int(given[0]), 200)

    def test_a_training_that_keeps_google_docs_keeps_its_own_send(self):
        root = self.local_training(copies=['google'])
        offered = self.engine.doc_preview(root, NAME)
        self.assertEqual((offered['action'], offered['automatic']), ('send', True))
        with self.assertRaisesRegex(WorkspaceError, 'keeps its Google Docs up to date'):
            self.engine.deliver_doc(root, NAME, self.seen(root))

    def test_only_a_guide_or_brief_goes_to_a_doc(self):
        root = self.local_training()
        with self.assertRaisesRegex(WorkspaceError, drafts.DOC_ONLY):
            self.engine.doc_preview(root, 'blueprint')
        self.assertEqual(sorted(gdocs.SYNCED), ['brief', 'document'])
