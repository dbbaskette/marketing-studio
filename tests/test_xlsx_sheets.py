"""Spreadsheet workbooks are read sheet by sheet from synthetic .xlsx files built with zipfile."""
import base64
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import marketing_studio  # noqa: F401
from studio_core import research_sources, xlsx_sheets
from studio_core.research_sources import Sources
import xlsx_fixture


class WorkbookTests(unittest.TestCase):
    def test_every_sheet_is_read_under_its_name_in_workbook_order(self):
        found = xlsx_sheets.extract(xlsx_fixture.workbook(xlsx_fixture.SAMPLE))
        self.assertEqual(found['text'], xlsx_fixture.SAMPLE_TEXT)
        self.assertEqual(found['warnings'], [])
        self.assertEqual(found['extractor'], 'xlsx-sheets-v1')
        self.assertEqual([place['label'] for place in found['locations']], ['Sheet 1: Pipeline', 'Sheet 2: Dates & notes'])
        for place in found['locations']:
            self.assertTrue(found['text'][place['start']:place['end']].startswith('# '))
        self.assertNotIn('PHONETIC', found['text'], 'a phonetic guide is not part of a cell')
        self.assertNotIn('A1&B1', found['text'], 'a formula is read as its kept result')

    def test_a_cut_sheet_says_so_and_names_the_sheet(self):
        wide = [[f'cell {row}-{at}' for at in range(4)] for row in range(6)]
        book = xlsx_fixture.workbook([('Wide', wide), ('Small', [['only']]), ('Third', [['left out']])])
        with mock.patch.object(xlsx_sheets, 'MOST_ROWS', 4), mock.patch.object(xlsx_sheets, 'MOST_COLUMNS', 3), \
                mock.patch.object(xlsx_sheets, 'MOST_SHEETS', 2):
            found = xlsx_sheets.extract(book)
        self.assertEqual(found['warnings'], ['Only the first 2 of 3 sheets were read.',
                                             'Sheet “Wide” was cut after its first 4 rows.',
                                             'Sheet “Wide” was cut after its first 3 columns.'])
        self.assertEqual(found['text'], '# Wide\n' + ''.join(f'cell {row}-0,cell {row}-1,cell {row}-2\n' for row in range(4))
                         + '# Small\nonly\n')
        self.assertEqual((xlsx_sheets.MOST_SHEETS, xlsx_sheets.MOST_ROWS, xlsx_sheets.MOST_COLUMNS), (50, 5000, 200))

    def test_a_chart_sheet_is_named_and_blank_rows_and_gaps_are_kept_in_place(self):
        book = xlsx_fixture.workbook([('Chart', []), ('Gaps', [[None, 'second column'], [], ['after a blank row', None, 3]])],
                                     charts=('Chart',))
        found = xlsx_sheets.extract(book)
        self.assertEqual(found['warnings'], ['Sheet “Chart” holds a chart or a macro, not cells, and was not read.'])
        self.assertEqual(found['text'], '# Gaps\n,second column\nafter a blank row,,3\n')

    def test_an_unsafe_or_broken_workbook_is_refused_in_plain_words(self):
        entity = '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e "boom">]><workbook/>'
        for data in (b'not a workbook', b'', xlsx_fixture.workbook(xlsx_fixture.SAMPLE, replace={'xl/workbook.xml': entity}),
                     xlsx_fixture.workbook([])):
            with self.assertRaises(ValueError) as refused:
                xlsx_sheets.extract(data)
            self.assertEqual(str(refused.exception), xlsx_sheets.UNREADABLE)
        self.assertNotIn('PowerPoint', xlsx_sheets.UNREADABLE)

    def test_an_uploaded_workbook_is_a_source_and_a_workbook_with_no_cells_is_not(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        sources = Sources(Path(temp.name).resolve() / 'store')
        value = sources.create()
        value = sources.mutate(value['id'], value['revision'], 'capture', kind='file', name='Pipeline.XLSX',
                               content=base64.b64encode(xlsx_fixture.workbook(xlsx_fixture.SAMPLE)).decode())
        source = value['sources'][0]
        self.assertEqual((source['status'], source['kind'], source['warnings']), ('ready', 'file', []))
        self.assertEqual(sources.preview(value['id'], source['id'])['text'], xlsx_fixture.SAMPLE_TEXT)
        self.assertIn('.xlsx', value['formats'])
        value = sources.mutate(value['id'], value['revision'], 'capture', kind='file', name='blank.xlsx',
                               content=base64.b64encode(xlsx_fixture.workbook([('Empty', [])])).decode())
        self.assertEqual(value['sources'][-1]['status'], 'needs-attention')
        self.assertIn('no readable text', value['sources'][-1]['problem'])
        value = sources.mutate(value['id'], value['revision'], 'capture', kind='file', name='notes.csv', content='AA==')
        self.assertEqual(value['sources'][-1]['problem'], 'Choose PDF, DOCX, PPTX, XLSX, text, Markdown or HTML.')
        self.assertEqual(research_sources.TYPES['.xlsx'], 'xlsx')
