"""Scripted timing only. Set STUDIO_TEST_RESEARCH_RUNTIME to the pinned disposable helper."""
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path[:0]=[str(ROOT),str(ROOT/"tests"),str(ROOT/"core")]
import json, time
from test_research_sections import SectionWorkflowTests
case=SectionWorkflowTests();case.setUp()
from studio_core import research_session
fast=research_session.section_streams(case.task)[0]["id"]
original=case.invoke
started=time.monotonic();events={}
def invoke(phase,guidance,payload,offered,fetch):
    if phase=='investigate' and payload['_execution']['stream']!=fast:time.sleep(.6)
    return original(phase,guidance,payload,offered,fetch)
case.invoke=invoke
from studio_core import research_sections
try:
    def progress(state):
        case.states.append(state)
        if any(r.get('evidence') for r in state['streams']):events.setdefault('first_finding',round(time.monotonic()-started,3))
        if state.get('first_readable_seconds') is not None:events.setdefault('first_section',round(time.monotonic()-started,3))
        if state['phase']=='complete':events['checked_final']=round(time.monotonic()-started,3)
    case.workflow.run(case.root,case.task,case.invoke,progress=progress,section_policy=research_sections.pin(),section_context={'combining':'synthetic-medium'})
    print(json.dumps({**events,'calls':case.calls,'section_calls':len(case.section_calls)}))
finally:case.doCleanups()
