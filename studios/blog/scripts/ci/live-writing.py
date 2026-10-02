#!/usr/bin/env python3
"""Opt-in real CLI acceptance using fictional material and isolated local skills."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

REPO = Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--harness',choices=('codex','claude'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    if sys.version_info < (3,11):parser.error('Run this test with Python 3.11+, as selected by the installer.')
    root=args.output.expanduser().resolve()
    if root.exists():parser.error('Choose a new empty output directory; existing work is preserved.')
    if not shutil.which(args.harness):parser.error('The selected CLI is not installed.')
    root.mkdir(parents=True)
    local=root/('.agents' if args.harness=='codex' else '.claude')/'skills/blog-studio'
    shutil.copytree(REPO/'skills/blog-studio',local,ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    (root/'source-notes.md').write_text('Fictional pilot: six handoff notes were reviewed. Two omitted the next owner. No delivery-speed or revenue outcome was measured.\n')
    (root/'original.md').write_text('# Better handoffs\n\nWe reviewed six notes. Two did not name the next owner. We have no measurement of delivery speed. Name the next owner before handing work over.\n')
    skill='Use Blog Studio.'
    intro=(f'{skill}\nUse the project-local full skill in {local}/SKILL.md for this candidate acceptance test. '
           f'This is the full offline package, with no bootstrap or guidance task. Its runtime is {local}/scripts. '
           f'Run helpers using {sys.executable} {local}/scripts/studio.py with the needed arguments, without shell variables or command chaining. Use file tools to read/write files. '
           'Work only inside this disposable directory and its .blog-studio workspace. '
           'Do not access external services, research, account settings, other user files, or other agents. '
           'Use the supplied fictional material and save requested work locally. ')
    prompts=[
        'Create an outline titled Handoff pilot from source-notes.md for engineering managers. Use a plain conversational tone, supplied sources only. Stop at the outline and save it.',
        'Continue Handoff pilot. Write the first draft, about 250 words, using its saved sources and tone. Remember for this article: use short headings. Save the draft and that preference.',
        'Show my blogs, then continue Handoff pilot. Correct its short-headings preference to descriptive headings. Tell me what context you have saved for this article. Do not rewrite the draft.',
        'Continue Handoff pilot. Forget the descriptive-headings preference for this article, show the active context, and leave the draft unchanged.',
        'Improve the wording of original.md and save it as a separate article titled Original preservation. Preserve its facts and original manuscript. Use its existing voice; no research or new claims.'
    ]
    fingerprint=hashlib.sha256()
    for path in sorted(local.rglob('*')):
        if path.is_file() and '__pycache__' not in path.parts:
            fingerprint.update(path.relative_to(local).as_posix().encode()+b'\0'+path.read_bytes())
    evidence={'harness':args.harness,'skill_tree_sha256':fingerprint.hexdigest(),'runs':[]}
    for index,prompt in enumerate(prompts,1):
        request=intro+prompt
        if args.harness=='codex':
            command=['codex','exec','--skip-git-repo-check','--sandbox','workspace-write','--ephemeral','--json','-C',str(root),request]
        else:
            runtime=str(local/'scripts/studio.py')
            allowed=['Read','Write','Edit','Glob','Grep',f'Bash(python3 {runtime} *)',f'Bash({sys.executable} {runtime} *)']
            command=['claude','--print','--output-format','json','--no-session-persistence','--strict-mcp-config','--tools','Read,Write,Edit,Glob,Grep,Bash','--allowedTools',','.join(allowed),'--',request]
        try:
            result=subprocess.run(command,cwd=root,text=True,capture_output=True,timeout=300)
            (root/f'turn-{index}.stdout').write_text(result.stdout)
            (root/f'turn-{index}.stderr').write_text(result.stderr)
            evidence['runs'].append({'turn':index,'exit_code':result.returncode})
        except subprocess.TimeoutExpired:
            evidence['runs'].append({'turn':index,'status':'timeout'})
            break
        if result.returncode:
            (root/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
            print(json.dumps(evidence['runs'][-1]),flush=True)
            break
        sessions=list((root/'.blog-studio/articles').glob('*/session.json'))
        records=[json.loads(path.read_text()) for path in sessions]
        observations={'article_count':len(records)}
        selected=next((record for record in records if record.get('title')=='Handoff pilot'),None)
        if selected:
            folder=root/'.blog-studio/articles'/selected['id']
            observations.update({'stop':selected['stop_point'],'outline_saved':(folder/'OUTLINE.md').is_file(),
                'draft_saved':(folder/'DRAFT.md').is_file(),
                'draft_hash':hashlib.sha256((folder/'DRAFT.md').read_bytes()).hexdigest() if (folder/'DRAFT.md').exists() else None,
                'memory_revisions':{key:value['revision'] for key,value in selected.get('memory',{}).items()},
                'active_memory':sum(value['status']=='active' for value in selected.get('memory',{}).values())})
        if index==5:
            original=next((record for record in records if record.get('title')=='Original preservation'),None)
            if original:
                folder=root/'.blog-studio/articles'/original['id']
                observations['original_preserved']=(folder/'ORIGINAL.md').is_file() and (folder/'ORIGINAL.md').read_bytes()==(root/'original.md').read_bytes()
                observations['revision_saved']=(folder/'DRAFT.md').is_file()
        evidence['runs'][-1]['observations']=observations
        (root/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
        print(json.dumps(evidence['runs'][-1]),flush=True)
    (root/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
    runs=evidence['runs']
    observed=[run.get('observations',{}) for run in runs]
    checks={}
    if len(observed)==5:
        checks={'outline_stop':observed[0].get('outline_saved') is True and observed[0].get('draft_saved') is False,
                'draft_adoption':observed[1].get('draft_saved') is True and observed[1].get('active_memory')==1,
                'memory_correction':observed[2].get('active_memory')==1 and any(value>=2 for value in observed[2].get('memory_revisions',{}).values()),
                'forget_preserves_draft':observed[3].get('active_memory')==0 and all(observed[i].get('draft_hash')==observed[1].get('draft_hash') for i in (2,3)),
                'original_preserved':observed[4].get('original_preserved') is True and observed[4].get('revision_saved') is True}
    evidence['checks']=checks
    (root/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n')
    print(json.dumps({'checks':checks}),flush=True)
    print('Review local transcripts and evidence: '+str(root/'evidence.json'))
    return 0 if len(evidence['runs'])==len(prompts) and all(run.get('exit_code')==0 for run in evidence['runs']) and checks and all(checks.values()) else 1

if __name__=='__main__':sys.exit(main())
