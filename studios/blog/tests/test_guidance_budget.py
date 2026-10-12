"""Guidance budgets: wording edits pass, growth past the margin fails, the inventory stays current."""

import copy
import importlib.util
import json
from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location(
    'measure_guidance', REPO / 'scripts/measure_guidance.py'
)
guidance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guidance)


def inventory(entry=1000, route=4000, small=300, library=200000):
    return {
        'library_tokens': library,
        'entry_guidance': {'files': ['SKILL.md'], 'estimated_tokens': entry},
        'conditional_privacy_reference': {'files': ['privacy.md'], 'estimated_tokens': 1000},
        'routes': {'first_draft': {'files': ['SKILL.md'], 'estimated_tokens': route}},
        'team_hub_routes': {'sync': {'files': ['hub.md'], 'estimated_tokens': 1500}},
        'workspace_operations': {'readiness': {'files': ['ready.md'], 'estimated_tokens': small}},
    }


class GuidanceBudgetTests(unittest.TestCase):
    def test_unchanged_and_smaller_guidance_is_within_budget(self):
        recorded = inventory()
        self.assertEqual(guidance.over_budget(recorded, copy.deepcopy(recorded)), [])
        self.assertEqual(
            guidance.over_budget(recorded, inventory(entry=400, route=100, library=9)), []
        )

    def test_wording_edits_pass_without_refreshing_the_inventory(self):
        recorded = inventory()
        # A reworded sentence moves a file by a few tokens; hashes and character counts differ.
        measured = inventory(entry=1012, route=4030, small=318, library=200060)
        self.assertEqual(guidance.over_budget(recorded, measured), [])

    def test_margin_is_five_percent_or_fifty_tokens_whichever_is_larger(self):
        recorded = inventory()
        at_limit = inventory(entry=1050, route=4200, small=350, library=210000)
        self.assertEqual(guidance.over_budget(recorded, at_limit), [])
        for label, measured in (
            ('entry_guidance', inventory(entry=1051)),
            ('routes.first_draft', inventory(route=4201)),
            ('workspace_operations.readiness', inventory(small=351)),
            ('library', inventory(library=210001)),
        ):
            problems = guidance.over_budget(recorded, measured)
            self.assertEqual(len(problems), 1, problems)
            self.assertTrue(problems[0].startswith(label + ': '), problems)

    def test_a_route_added_since_the_inventory_was_recorded_has_no_budget_yet(self):
        measured = inventory()
        measured['routes']['new_route'] = {'files': ['new.md'], 'estimated_tokens': 9000}
        self.assertEqual(guidance.over_budget(inventory(), measured), [])

    def test_recorded_inventory_passes_and_names_only_existing_files(self):
        recorded = json.loads(guidance.INVENTORY.read_text())
        measured = guidance.refreshed(recorded)
        self.assertEqual(guidance.over_budget(recorded, measured), [])
        self.assertEqual(guidance.missing_files(recorded), [])

    def test_a_route_that_lists_a_removed_file_is_reported_by_name(self):
        recorded = json.loads(guidance.INVENTORY.read_text())
        recorded['routes']['quick_edit']['files'].append('references/no-such-guide.md')
        self.assertEqual(
            guidance.missing_files(recorded), ['routes.quick_edit: references/no-such-guide.md']
        )


if __name__ == '__main__':
    unittest.main()
