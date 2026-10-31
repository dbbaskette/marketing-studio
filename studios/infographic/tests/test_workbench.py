"""The visual editor's names, revision history and readiness, from disposable desks.

Rendering is the structural fake renderer; no assistant or provider runs.
"""
from helpers import Isolated
import test_desk_engine as desk
from runner import exports, history, labels, progress
from runner.contracts import Invalid


class WorkbenchTests(Isolated):
    current = desk.DeskEngineTests.current
    review_and_approve = desk.DeskEngineTests.review_and_approve

    def setUp(self):
        super().setUp()
        desk.setup_desk(self)

    def test_elements_have_human_labels_locations_and_page_bounds(self):
        found = labels.elements(self.current())
        names = [e['label'] for e in found]
        self.assertEqual(names[:2], ['Page heading', 'Page takeaway'])
        self.assertIn('Section 1 heading', names)
        self.assertIn('Source note', names)
        self.assertFalse(any('_' in name for name in names), 'Element IDs are advanced detail, not labels.')
        heading = next(e for e in found if e['label'] == 'Section 1 heading')
        self.assertEqual(heading['id'], 'b1_heading')
        self.assertTrue(heading['location'].startswith('Section 1 of 1, '))
        self.assertTrue(heading['location'].endswith(' of the page'))
        for element in found:
            x, y, w, h = element['bounds']
            self.assertTrue(0 <= x < 1 and 0 <= y < 1 and 0 < w <= 1 and 0 < h <= 1)
        top = next(e for e in found if e['label'] == 'Page heading')
        self.assertTrue(top['location'].startswith('Top'))
        # Visual items are named by section and step or item.
        project = self.current()
        story = next(s for s in project['stories'] if s['id'] == project['selected_story'])
        if any((b.get('visual') or {}).get('nodes') for b in story['blocks']):
            self.assertTrue(any(', item 1 label' in n or ', step 1 label' in n for n in names))

    def test_process_items_are_named_as_steps(self):
        project = self.current()
        story = next(s for s in project['stories'] if s['id'] == project['selected_story'])
        block = story['blocks'][0]
        block['kind'] = 'process'
        block['visual'] = {'nodes': [{'id': 'n_0', 'label': 'Drain'}, {'id': 'n_1', 'label': 'Restart'}], 'links': []}
        project['scene']['elements'].append({**project['scene']['elements'][0], 'id': 'b1_node_n_1_label', 'text': 'Restart'})
        found = {e['id']: e['label'] for e in labels.elements(project)}
        self.assertEqual(found['b1_node_n_1_label'], 'Section 1, step 2 label')

    def test_history_says_what_each_revision_did_with_exact_identity_and_time(self):
        approved = self.review_and_approve()
        edited = self.engine.edit_text(self.ident, 'b1_heading', 'One instance', expected_revision=approved['revision'])
        again = self.engine.edit_text(self.ident, 'headline', 'Restart safely', expected_revision=edited['revision'])
        entries = history.entries(self.store, self.ident)
        newest, middle = entries[0], entries[1]
        self.assertEqual((newest['revision'], newest['summary'], newest['affected']),
                         (again['revision'], 'Edited words', ['Page heading']))
        self.assertEqual((middle['summary'], middle['affected']),
                         ('Edited words; approval cleared', ['Section 1 heading']))
        approval = next(e for e in entries if e['revision'] == approved['revision'])
        self.assertEqual(approval['summary'], 'Approved this exact revision')
        checks = next(e for e in entries if e['revision'] == approved['revision'] - 1)
        self.assertEqual(checks['summary'], 'Ran checks: all passed')
        self.assertEqual(entries[-1]['summary'], 'Created the infographic')
        for entry in entries:
            self.assertEqual(len(entry['sha256']), 64)
            self.assertRegex(entry['saved_at'], r'^\d{4}-\d\d-\d\dT')
        restored = history.restore(self.store, self.ident, approved['revision'], expected_revision=again['revision'],
                                   fingerprint=approval['sha256'])
        latest = history.entries(self.store, self.ident)[0]
        self.assertEqual(latest['revision'], restored['revision'])
        self.assertTrue(latest['summary'].startswith('Restored an earlier revision as new work'))
        self.assertIsNone(restored['approval'], 'Restore never inherits approval.')

    def test_edits_never_inherit_approval_and_earlier_approved_exports_stay_unchanged(self):
        approved = self.review_and_approve()
        manifest = self.engine.preview(self.ident, expected_revision=approved['revision'], draft=False)
        before = {kind: exports.read(self.store, self.ident, manifest['id'], kind) for kind in ('png', 'pdf', 'svg', 'text')}
        edited = self.engine.edit_text(self.ident, 'b1_heading', 'One instance', expected_revision=approved['revision'])
        self.assertIsNone(edited['approval'])
        with self.assertRaises(Invalid):
            self.engine.edit_text(self.ident, 'headline', 'Stale', expected_revision=approved['revision'])
        listed = {d['id']: d for d in self.engine.deliveries(self.ident)}
        earlier = listed[manifest['id']]
        self.assertEqual((earlier['draft'], earlier['current'], earlier['approved_current']), (False, False, False))
        for kind, value in before.items():
            self.assertEqual(exports.read(self.store, self.ident, manifest['id'], kind), value)

    def test_desk_and_home_report_readiness_with_the_exact_revision(self):
        inspected = self.engine.inspect(self.ident)
        self.assertEqual(inspected['readiness']['summary'], 'Page built: review the preview')
        self.assertEqual([e['id'] for e in inspected['elements']], [e['id'] for e in labels.elements(inspected['project'])])
        approved = self.review_and_approve()
        listed = self.store.listing()[0]
        self.assertEqual((listed['revision'], listed['readiness']['summary']),
                         (approved['revision'], 'Approved: ready to export and deliver'))
        fresh = self.store.create('Synthetic empty brief')
        self.assertEqual(progress.readiness(fresh)['summary'], 'Brief saved: add information')
