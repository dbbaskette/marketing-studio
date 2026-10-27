"""The shared list kit (core/studio_core/deck_web/lists.js), drawn on an empty page by
page_harness.js: the filter row, a tick, Select all on this page and the selection bar.

Each part is handed functions that write down what they were called with, so a test sees
exactly what the page would be told. Nothing here starts a server.
"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_desk import HARNESS, NODE

ROW = {'key': 'decks',
       'search': {'id': 'text', 'label': 'Search', 'hint': 'By its title', 'value': ''},
       'choices': [{'id': 'stands', 'label': 'Where it stands', 'value': 'needs',
                    'options': [['', 'Any'], ['needs', 'Needs you'], ['done', 'Finished']]},
                   {'id': 'began', 'label': 'How it began', 'value': '',
                    'options': [['', 'Any'], ['idea', 'From an idea']]}]}


@unittest.skipUnless(NODE, 'Node is needed to run the page scripts without a browser')
class ListsKitTests(unittest.TestCase):
    def kit(self, steps: list, **plan) -> dict:
        with tempfile.TemporaryDirectory() as folder:
            file = Path(folder) / 'plan.json'
            file.write_text(json.dumps({'kit': True, 'steps': steps, **plan}), encoding='utf-8')
            done = subprocess.run([NODE, str(HARNESS), 'kit', str(file)], text=True,
                                  capture_output=True, timeout=60)
        self.assertEqual(done.returncode, 0, done.stderr)
        result = json.loads(done.stdout)
        self.assertEqual(result['errors'], [])
        return result['snapshots']

    def test_the_filter_row_puts_search_first_and_counts_hidden_filters(self):
        phone = self.kit([{'build': 'filterRow', 'spec': ROW}, {'snapshot': 'row'}],
                         narrow=True)['row']
        names = [(control['tag'], control['name']) for control in phone['controls']]
        # On a phone only the search shows, with Filters, which counts the one that is set.
        self.assertEqual(names, [('input', 'Search'), ('button', 'Filters (1)'),
                                 ('button', 'Search')])
        opened = self.kit([{'build': 'filterRow', 'spec': ROW}, {'click': 'Filters (1)'},
                           {'snapshot': 'row'}], narrow=True)['row']
        self.assertEqual([(control['tag'], control['name']) for control in opened['controls']
                          if control['name'] != 'Filters (1)'],
                         [('input', 'Search'), ('select', 'Where it stands'), ('select', 'How it began'),
                          ('button', 'Search')])
        self.assertEqual(opened['calls'], [['toggled', True]])
        desktop = self.kit([{'build': 'filterRow', 'spec': ROW}, {'snapshot': 'row'}])['row']
        self.assertEqual([control['tag'] for control in desktop['controls']],
                         ['input', 'select', 'select', 'button'])
        self.assertNotIn('Filters', desktop['text'])
        self.assertTrue(desktop['text'].startswith('Search'))

    def test_a_choice_applies_on_change_and_search_on_submit(self):
        shot = self.kit([{'build': 'filterRow', 'spec': ROW},
                         {'fill': 'Where it stands', 'value': 'done'}, {'snapshot': 'chosen'},
                         {'fill': 'Search', 'value': ' capacity '}, {'snapshot': 'typed'},
                         {'click': 'Search'}, {'snapshot': 'searched'}])
        self.assertEqual(shot['chosen']['calls'], [['changed', 'stands', 'done']])
        self.assertEqual(shot['typed']['calls'], [['changed', 'stands', 'done']])
        self.assertEqual(shot['searched']['calls'],
                         [['changed', 'stands', 'done'], ['searched', 'capacity']])
        entered = self.kit([{'build': 'filterRow', 'spec': ROW},
                            {'fill': 'Search', 'value': 'rollback'}, {'enter': 'Search'},
                            {'snapshot': 'entered'}])['entered']
        self.assertEqual(entered['calls'], [['searched', 'rollback']])

    def test_rarely_used_filters_fold_under_more_filters(self):
        spec = {**ROW, 'more': [{'id': 'by', 'label': 'Published by', 'value': '',
                                 'options': [['', 'Anyone'], ['Sam', 'Sam']]}]}
        shot = self.kit([{'build': 'filterRow', 'spec': spec}, {'snapshot': 'closed'},
                         {'click': 'More filters'}, {'snapshot': 'open'}])
        self.assertEqual([control['tag'] for control in shot['closed']['controls']],
                         ['input', 'select', 'select', 'button', 'summary'])
        self.assertEqual([control['tag'] for control in shot['open']['controls']],
                         ['input', 'select', 'select', 'button', 'summary', 'select'])

    def test_the_bar_counts_what_is_out_of_view_and_offers_the_page(self):
        spec = {'ticked': ['a', 'b', 'c'], 'shown': ['a', 'd'], 'noun': ['deck', 'decks'],
                'actions': [{'label': 'Delete 3 decks', 'kind': 'danger', 'key': 'delete'}]}
        shot = self.kit([{'build': 'selectionBar', 'spec': spec}, {'snapshot': 'bar'},
                         {'click': 'Select all 2 on this page'}, {'click': 'Clear'},
                         {'click': 'Delete 3 decks'}, {'snapshot': 'after'}])
        bar = shot['bar']
        self.assertIn('3 selected', bar['bar'])
        self.assertIn('2 of them are not in this view.', bar['bar'])
        self.assertEqual([control['name'] for control in bar['controls']],
                         ['Select all 2 on this page', 'Clear', 'Delete 3 decks'])
        danger = [control for control in bar['controls'] if control['name'] == 'Delete 3 decks']
        self.assertIn('button-danger', danger[0]['classes'])
        self.assertNotIn('button-filled', ' '.join(c['classes'] for c in bar['controls']))
        self.assertEqual(shot['after']['calls'], [['selectShown'], ['clear'], ['Delete 3 decks']])
        one = self.kit([{'build': 'selectionBar', 'spec': {**spec, 'ticked': ['a', 'b'],
                                                            'shown': ['a']}},
                        {'snapshot': 'bar'}])['bar']
        self.assertIn('1 of them is not in this view.', one['bar'])
        self.assertNotIn('Select all', one['bar'])
        empty = self.kit([{'build': 'selectionBar', 'spec': {**spec, 'ticked': []}},
                          {'snapshot': 'none'}])['none']
        self.assertTrue(empty['empty'])

    def test_select_all_on_this_page_is_mixed_when_some_are_ticked(self):
        shot = self.kit([{'build': 'selectPage', 'spec': {'id': 'all', 'shown': ['a', 'b'],
                                                          'ticked': ['a']}},
                         {'snapshot': 'some'}, {'tick': 'Select all on this page'},
                         {'snapshot': 'ticked'}])
        box, = shot['some']['controls']
        self.assertEqual((box['name'], box['checked'], box['indeterminate']),
                         ('Select all on this page', False, True))
        self.assertEqual(shot['ticked']['calls'], [['flip', True]])
        every = self.kit([{'build': 'selectPage', 'spec': {'id': 'all', 'shown': ['a'],
                                                           'ticked': ['a']}},
                          {'snapshot': 'all'}])['all']
        self.assertEqual((every['controls'][0]['checked'], every['controls'][0]['indeterminate']),
                         (True, False))

    def test_a_tick_is_a_labelled_check_box(self):
        shot = self.kit([{'build': 'tick', 'spec': {'id': 'web', 'label': 'the public web',
                                                    'on': True}},
                         {'snapshot': 'on'}, {'tick': 'the public web'}, {'snapshot': 'off'}])
        box, = shot['on']['controls']
        self.assertEqual((box['type'], box['name'], box['checked']),
                         ('checkbox', 'the public web', True))
        self.assertEqual(shot['off']['calls'], [['flip', False]])


if __name__ == '__main__':
    unittest.main()
