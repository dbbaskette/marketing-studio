import tempfile
import unittest
from studio_core import intake_drafts, research_notes


class ResearchNoteTests(unittest.TestCase):
    def test_private_note_conflicts_and_keeps_earlier_basis_without_evidence_changes(self):
        with tempfile.TemporaryDirectory() as data:
            read=lambda:research_notes.dispatch(data,'known-project','area1',{'action':'read'})
            self.assertEqual(read(),{'revision':0,'draft':None})
            request={'action':'save','expected':0,'patch':{'basis':'earlier-section','note':'Check the direction.'}}
            held=research_notes.dispatch(data,'known-project','area1',request)
            self.assertEqual(held,{'revision':1})
            self.assertEqual(read()['draft']['basis'],'earlier-section')
            with self.assertRaises(intake_drafts.Conflict):research_notes.dispatch(data,'known-project','area1',request)
            with self.assertRaises(ValueError):research_notes.dispatch(data,'known-project','area1',{'action':'save','expected':1,'patch':{'scope':'broader'}})
            self.assertEqual(read()['revision'],1)
