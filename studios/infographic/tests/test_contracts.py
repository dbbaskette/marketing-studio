from copy import deepcopy
import unittest
import struct

from helpers import approved_project, project
from runner.contracts import Invalid, advance, basis, can_land, digest, new_project
from runner.validation import image_size, validate_image_result, validate_project
from graphics_fixtures import png


class ContractTests(unittest.TestCase):
    def test_provider_handoffs_preserve_unknown_outcomes_and_require_actual_assets(self):
        result = {'schema': 1, 'provider': 'gemini', 'operation': 'generate', 'attempt_id': 'try1',
                  'state': 'unknown', 'reason': 'timeout', 'request_id': None, 'assets': [],
                  'inspection': 'unknown',
                  'usage': {'cost': None, 'currency': None, 'input_tokens': None, 'output_tokens': None}}
        validate_image_result(result)
        with self.assertRaisesRegex(Invalid, 'actual saved assets'):
            validate_image_result({**result, 'state': 'complete', 'reason': None})
        for invalid in [{'schema': 2}, {'provider': 'other'}, {'attempt_id': None}, {'api_key': 'sentinel'}]:
            with self.subTest(invalid=invalid), self.assertRaises(Invalid):
                validate_image_result({**result, **invalid})
        result['usage']['cost'] = .02
        with self.assertRaisesRegex(Invalid, 'currency'):
            validate_image_result(result)

    def test_complete_contract_and_empty_draft_are_valid(self):
        validate_project(new_project('owner1', 'Working title'))
        validate_project(project())
        validate_project(approved_project())

    def test_unknown_schema_fields_and_unsafe_values_are_refused(self):
        for change in [{'schema': 2}, {'schema': True}, {'revision': True}, {'owner': '../other'},
                       {'unexpected': {}}, {'brief': []}]:
            with self.subTest(change=change), self.assertRaises(Invalid):
                validate_project({**project(), **change})
        p = project()
        p['brief']['api_key'] = 'sentinel'
        with self.assertRaisesRegex(Invalid, 'Credentials'):
            validate_project(p)
        p = project()
        p['facts'][0]['value'] = float('nan')
        with self.assertRaises(Invalid):
            validate_project(p)

    def test_evidence_and_references_must_exist_within_the_source(self):
        for field, value in [('source_id', 'missing'), ('source_id', []), ('start', -1), ('end', 99999)]:
            p = project()
            p['facts'][0]['evidence'][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaises(Invalid):
                validate_project(p)
        p = project()
        p['stories'][0]['blocks'][0]['fact_ids'] = ['missing']
        with self.assertRaises(Invalid):
            validate_project(p)
        for file in ('../private', '/private', 'sources/../../private', 'sources\\private', 'sources/./private'):
            p = project()
            p['sources'][0]['file'] = file
            with self.subTest(file=file), self.assertRaises(Invalid):
                validate_project(p)

    def test_calculations_reject_wrong_units_values_denominators_and_cycles(self):
        p = project()
        total = {'id': 'f3', 'statement': 'Derived synthetic sum', 'value': 36, 'unit': 'count',
                 'status': 'supplied', 'evidence': [], 'calculation': {'operator': 'sum', 'operands': ['f1', 'f2']}}
        p['facts'].append(total)
        validate_project(p)
        for change in [('value', 37), ('unit', '%')]:
            broken = deepcopy(p)
            broken['facts'][-1][change[0]] = change[1]
            with self.subTest(change=change), self.assertRaises(Invalid):
                validate_project(broken)
        p['facts'][0]['unit'] = 'seconds'
        with self.assertRaisesRegex(Invalid, 'conflicting units'):
            validate_project(p)
        p = project()
        p['facts'].append({**total, 'calculation': {'operator': 'sum', 'operands': ['f3', 'f1']}})
        with self.assertRaisesRegex(Invalid, 'cycle'):
            validate_project(p)

    def test_scene_and_image_brief_have_exact_geometry_and_ownership(self):
        for field, value in [('width', 1), ('unit', 'mm'), ('elements', [{'id': 'x', 'kind': 'shape', 'bounds': [0, 0, 9999, 10]}])]:
            p = project()
            p['scene'][field] = value
            with self.subTest(field=field), self.assertRaises(Invalid):
                validate_project(p)
        p = project()
        p['image_briefs'][0]['regions'][0]['bounds'] = [.9, 0, .2, .3]
        with self.assertRaises(Invalid):
            validate_project(p)
        p = project()
        del p['image_briefs'][0]['style']
        with self.assertRaises(Invalid):
            validate_project(p)

    def test_charts_cannot_change_values_or_mix_source_units(self):
        p = project()
        chart = {'id': 'chart1', 'kind': 'chart', 'bounds': [20, 100, 250, 150],
                 'fact_ids': ['f1', 'f2'], 'values': [12, 24], 'unit': 'count'}
        p['scene']['elements'].append(chart)
        validate_project(p)
        chart['values'][1] = 23
        with self.assertRaisesRegex(Invalid, 'Chart values'):
            validate_project(p)
        chart['values'][1] = 24
        p['facts'][1]['unit'] = 'seconds'
        with self.assertRaisesRegex(Invalid, 'different units'):
            validate_project(p)

    def test_encoded_image_size_is_bounded_before_decode(self):
        raw = png()
        self.assertEqual(image_size(raw, 'image/png'), (4, 4))
        for width, height in [(0, 4), (20001, 4), (10000, 10000)]:
            altered = raw[:16] + struct.pack('>II', width, height) + raw[24:]
            with self.subTest(width=width, height=height), self.assertRaises(Invalid):
                image_size(altered, 'image/png')
        jpeg = b'\xff\xd8\xff\xc0\x00\x08\x08\x00\x04\x00\x05\x01'
        self.assertEqual(image_size(jpeg, 'image/jpeg'), (5, 4))
        for bad in (b'', b'\xff\xd8\xff\xc0\x00\x00', b'\xff\xd8\xff\xda\x00\x02'):
            with self.subTest(bad=bad), self.assertRaises(Invalid):
                image_size(bad, 'image/jpeg')
    def test_new_content_clears_approval_and_derived_state_without_changing_original(self):
        p = approved_project()
        brief = {**p['brief'], 'title': 'Changed title'}
        changed = advance(p, {'brief': brief}, expected_revision=0, owner='owner1')
        self.assertEqual(changed['revision'], 1)
        self.assertIsNone(changed['approval'])
        self.assertIsNone(changed['scene'])
        self.assertEqual(changed['stories'], [])
        self.assertIsNotNone(p['approval'])
        with self.assertRaises(Invalid):
            advance(changed, {'brief': brief}, expected_revision=0, owner='owner1')
        with self.assertRaises(Invalid):
            advance(p, {'brief': brief}, expected_revision=0, owner='someone-else')

    def test_approval_requires_complete_current_checks_and_exact_inputs(self):
        for alter in ('scene', 'check', 'missing', 'incomplete'):
            p = approved_project()
            if alter == 'scene':
                p['scene']['elements'][0]['text'] = 'Changed'
            elif alter == 'missing':
                p['checks'].pop()
            elif alter == 'check':
                p['checks'][0]['basis']['sources'] = 'b' * 64
            else:
                p['checks'][0]['status'] = 'incomplete'
            with self.subTest(alter=alter), self.assertRaises(Invalid):
                validate_project(p)

    def test_worker_must_own_a_current_running_attempt(self):
        p = project()
        expected = basis(p)
        p['attempts'] = [{'id': 'try1', 'provider': 'gemini', 'state': 'running', 'revision': 0,
                          'image_brief_id': 'image1', 'basis': expected, 'asset_ids': [], 'cost': None}]
        args = dict(attempt_id='try1', expected_revision=0, input_basis=expected, owner='owner1')
        self.assertTrue(can_land(p, **args))
        p['attempts'][0]['state'] = 'cancelled'
        self.assertFalse(can_land(p, **args))
        p['attempts'][0]['state'] = 'running'
        self.assertFalse(can_land(p, **{**args, 'expected_revision': 1}))
        self.assertFalse(can_land(p, **{**args, 'owner': 'owner2'}))
        self.assertEqual(digest({'a': 1, 'b': 2}), digest({'b': 2, 'a': 1}))
