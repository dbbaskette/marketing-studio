"""Dropdown/approval import and original-index round trips; synthetic Docs only."""

import isolation  # noqa: F401
import copy
import json
from unittest.mock import patch
import unittest

import desk_finish
import google_drive
import google_intake
import google_manuscript as manuscript
import google_model as gm
import google_reconcile
import google_roundtrip as rt
import google_suggestions as gs
import google_workflow as workflow
import manuscript_editor
import studio
from test_google_pending_read import PendingDocCase, small_doc


def dropdown(text='Ada Example'):
    return {
        'dropdown': {
            'dropdownProperties': {
                'displayValue': text,
                'selectedOptionId': 'chosen',
                'dropdownDefinitionId': 'people',
            }
        }
    }


def paragraph(*elements):
    return {'paragraph': {'elements': [*elements, gm.run('\n')]}}


def document(*blocks):
    value = small_doc(([('The blog body.\n', {})], None))
    value['tabs'][0]['documentTab']['body']['content'] = [
        {'sectionBreak': {}},
        *blocks,
        paragraph(gm.run('The blog body.')),
    ]
    return value


class ApprovalProjectionTests(unittest.TestCase):
    def render(self, value):
        return gs.accepted_markdown(value, images=[], manuscript=True).decode()

    def test_labelled_approval_fields_skip_but_unknown_names_do_not(self):
        for label in ('Approvers:', 'Reviewer', 'Technical reviewer:', 'Approval status:'):
            with self.subTest(label=label):
                value = document(paragraph(gm.run(label + ' '), dropdown()))
                before = copy.deepcopy(value)
                self.assertEqual(self.render(value), 'The blog body.')
                self.assertEqual(value, before, 'raw capture is unchanged')
                self.assertEqual(manuscript.summary(value), {'excluded_approval_blocks': 1})
        for label in ('Author:', 'By ', 'Reviewer experience improves when ', ''):
            with self.subTest(label=label):
                self.assertIn(
                    'Ada Example', self.render(document(paragraph(gm.run(label), dropdown())))
                )

    def test_label_heading_and_multiple_chip_rows_skip_together(self):
        value = document(
            paragraph(gm.run('Approvers')),
            paragraph(dropdown()),
            paragraph(dropdown('Lee Example')),
            paragraph(gm.run('')),
        )
        self.assertEqual(self.render(value), 'The blog body.')
        self.assertEqual(manuscript.summary(value)['excluded_approval_blocks'], 3)

    def test_unfinished_label_and_ambiguous_fields_stay_visible(self):
        for blocks in (
            [paragraph(gm.run('Approvers'))],
            [paragraph(gm.run('Approver: '), dropdown(), gm.run(' explains why latency matters.'))],
            [paragraph(gm.run('Approver: '), dropdown(), {'equation': {}})],
        ):
            value = document(*blocks)
            self.assertEqual(manuscript.view(value), value)

    def test_approval_table_only_skips_when_every_cell_is_administrative(self):
        cell = lambda block: {'content': [block]}  # noqa: E731
        table = {
            'table': {
                'tableRows': [
                    {
                        'tableCells': [
                            cell(paragraph(gm.run('Approvers'))),
                            cell(paragraph(dropdown())),
                        ]
                    },
                ]
            }
        }
        value = document(table)
        self.assertEqual(self.render(value), 'The blog body.')
        table['table']['tableRows'].append(
            {
                'tableCells': [
                    cell(paragraph(gm.run('Our product reduces setup time.'))),
                    cell(paragraph(dropdown())),
                ]
            }
        )
        value = document(table)
        self.assertIn('Our product reduces setup time.', self.render(value))
        self.assertEqual(manuscript.view(value), value)

    def test_article_dropdown_and_later_reviewer_label_remain_text(self):
        value = document(
            paragraph(gm.run('Our process begins here.')),
            paragraph(gm.run('Review status: '), dropdown('In review')),
        )
        self.assertIn('Review status: In review', self.render(value))
        self.assertIn('In review', gs.accepted_markdown(value, images=[]).decode())

    def test_display_value_is_literal_escaped_text_and_one_native_slot(self):
        value = document(paragraph(gm.run('Pick '), dropdown('A * B [C]'), gm.run(' now.')))
        self.assertIn('A \\* B [C]', self.render(value))
        text, indexes = desk_finish._base_of(
            paragraph(dropdown('Ada Example'), gm.run(' ok'))['paragraph'], 5
        )
        self.assertEqual(text, 'Ada Example ok')
        self.assertEqual(indexes[:11], [5] * 11)
        self.assertEqual(indexes[11:], [6, 7, 8])
        self.assertEqual(self.render(document(paragraph(dropdown('')))), 'The blog body.')

    def test_missing_dropdown_value_and_unsupported_objects_are_not_silently_lost(self):
        for element in ({'dropdown': {}}, {'equation': {}}):
            with self.subTest(element=element), self.assertRaises(google_drive.GoogleError):
                self.render(document(paragraph(gm.run('Approver: '), element)))


class ApprovalRoundtripTests(PendingDocCase):
    def setUp(self):
        super().setUp()
        doc = gm.objects_doc()
        doc['tabs'][0]['documentTab']['body']['content'].insert(
            1, paragraph(gm.run('Approvers: '), dropdown())
        )
        self.client = gm.Model(doc)

    def test_import_keeps_raw_source_and_the_editing_copy_excludes_approvers(self):
        found = self.read()
        self.assertEqual(found['summary']['excluded_approval_blocks'], 1)
        self.assertNotIn('Ada Example', found['content'])
        snapshot = google_drive.staging_root(self.root) / ('desk-' + found['preview']) / 'snapshot'
        native = json.loads((snapshot / 'native.json').read_text())
        self.assertIn('Ada Example', json.dumps(native))
        observation, body = workflow.observed(
            type(
                'Args',
                (),
                {
                    'snapshot': str(snapshot),
                    'observation': None,
                    'file': None,
                },
            )()
        )
        self.assertEqual(observation['projection'], manuscript.PROJECTION)
        workflow.formatted_snapshot(snapshot, observation, body)
        self.assertEqual(self.client.writes, 0)
        # Replacing projected text and its hashes is insufficient to forge a native snapshot.
        altered = body.replace('An opening paragraph', 'A changed opening paragraph')
        (snapshot / 'document.md').write_text(altered)
        meta = json.loads((snapshot / 'snapshot.json').read_text())
        meta['content_sha256'] = observation['content_sha256'] = studio.digest(altered.encode())
        meta['files']['document.md'] = observation['content_sha256']
        studio.write_json(snapshot / 'snapshot.json', meta)
        with self.assertRaisesRegex(ValueError, 'not the accepted text'):
            workflow.formatted_snapshot(snapshot, observation, altered)

    def test_suggestions_and_comment_fallback_leave_approval_chips_untouched(self):
        self.start()
        self.edit(
            [('An opening paragraph about harbours.', 'An opening paragraph about safe harbours.')]
        )
        plan = self.act('google-plan', mode='auto')
        self.assertEqual(len(plan['proposals']), 1)
        self.assertNotIn('Ada Example', json.dumps(plan['proposals']))
        result = self.act('google-send', plan=plan['plan'], confirmed=True)
        self.assertEqual(result['status'], 'verified-pending')
        raw = self.client.native_read('fixture-doc', inline=True)
        first = rt.tabs(raw)[0]['documentTab']['body']['content'][1]
        self.assertEqual(first['paragraph']['elements'][1]['dropdown'], dropdown()['dropdown'])
        self.assertIn(
            'safe harbours',
            gs.accepted_markdown(
                self.client.native_read('fixture-doc', accepted_preview=True), images=[]
            ).decode(),
        )

    def test_recompare_retains_scope_and_old_baselines_keep_full_content(self):
        found = self.read()
        with patch.object(google_drive, 'Client', return_value=self.client):
            made = google_intake.start(
                self.root,
                {
                    'preview': found['preview'],
                    'expected': found['expected'],
                    'title': 'Harbour notes',
                    'confirmed': True,
                },
            )
        self.ident = made['id']
        current = manuscript_editor.read(self.root, self.ident)
        with patch.object(google_drive, 'Client', return_value=self.client):
            found = google_reconcile.preview(
                self.root,
                {
                    'id': self.ident,
                    'expected': current['expected'],
                },
            )
        self.assertNotIn('Ada Example', found['remote'])
        self.assertEqual(found['summary']['excluded_approval_blocks'], 1)
        directory, record = studio.item(self.root, 'articles', self.ident)
        record['google']['baselines']['draft']['document']['projection'] = rt.OBJECTS_PROJECTION
        studio.persist(directory, 'articles', record)
        self.assertFalse(google_reconcile._manuscript(self.root, self.ident))

    def test_native_send_anchor_search_never_uses_the_excluded_fields(self):
        raw = self.client.native_read('fixture-doc', inline=True)
        full = desk_finish._paragraph_texts(raw, ['t.0'])
        selected = desk_finish._paragraph_texts(raw, ['t.0'], manuscript=True)
        self.assertTrue(any('Ada Example' in row[2] for row in full))
        self.assertFalse(any('Ada Example' in row[2] for row in selected))
        by_key = {row[0]: row.positions for row in full}
        self.assertTrue(all(row.positions == by_key[row[0]] for row in selected))

    def test_comments_fallback_does_not_anchor_on_the_approval_form(self):
        self.start()
        self.client.teammate('new ', 'opening paragraph', ident='teammate', delete='opening')
        self.edit(
            [('An opening paragraph about harbours.', 'An introductory paragraph about harbours.')]
        )
        plan = self.act('google-plan', mode='auto')
        self.assertTrue(plan['proposals'])
        self.assertTrue(all(p['kind'] == 'comment' for p in plan['proposals']))
        raw = self.client.native_read('fixture-doc', inline=True)
        end = rt.tabs(raw)[0]['documentTab']['body']['content'][1]['endIndex']
        self.assertTrue(all(p['start_index'] >= end for p in plan['proposals']))
        self.act('google-send', plan=plan['plan'], confirmed=True)
        self.assertEqual(len(self.client.comments), 1)
        first = rt.tabs(self.client.native_read('fixture-doc', inline=True))[0]['documentTab'][
            'body'
        ]['content'][1]
        self.assertEqual(first['paragraph']['elements'][1]['dropdown'], dropdown()['dropdown'])

    def test_cli_cannot_silently_change_a_linked_manuscript_scope(self):
        self.start()
        _, record = studio.item(self.root, 'articles', self.ident)
        baseline = record['google']['baselines']['draft']['document']
        different = dict(baseline, projection=rt.OBJECTS_PROJECTION)
        for left, right in ((baseline, different), (different, baseline)):
            with self.assertRaisesRegex(ValueError, 'approval-field scope changed'):
                workflow.same_target(left, right)

    def test_reference_tab_keeps_the_approval_values_and_never_reads_other_tabs(self):
        with patch.object(google_drive, 'Client', return_value=self.client):
            found = google_intake.material(
                self.root, 'https://docs.google.com/document/d/fixture-doc/edit?tab=t.0'
            )
        self.assertIn('Ada Example', str(found))
        self.assertEqual(self.client.writes, 0)


if __name__ == '__main__':
    unittest.main()
