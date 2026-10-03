#!/usr/bin/env python3
"""Native Google review proposals. Exact anchors, fresh revisions, one submission."""
import argparse
import copy
import json
from pathlib import Path
import re
import sys

import studio
import google_roundtrip as rt
from google_drive import Client, GoogleError, ReviewUnavailable, digest, encoded, write_new
from hub_store import contained, locked, write_json


def document(client, file_id, **kwargs):
    value = client.native_read(file_id, **kwargs)
    if value.get('documentId') != file_id or not value.get('revisionId'):
        raise GoogleError('Google document identity or revision is unavailable.')
    return value


def review_read(client, file_id):
    value = document(client, file_id, inline=True, comments=True)
    if value.get('commentsViewMode') != 'COMMENTS_VIEW_MODE_INCLUDED' or value.get('suggestionsViewMode') != 'SUGGESTIONS_INLINE':
        raise ReviewUnavailable('Native Google review readback is unavailable; use readable review comments.')
    if rt.suggestions(value) and not summary(value)['pending']:
        raise GoogleError('Pending suggestion threads are unavailable; retain local work and inspect Google.')
    return value


def content(value):
    """Thread metadata is separate from manuscript text and formatting."""
    if isinstance(value, dict):
        return {k:content(v) for k,v in value.items() if k not in
                ('comments','suggestions','commentAnchors','commentsViewMode')}
    if isinstance(value, list):return [content(v) for v in value]
    return value


def signature(value):return digest(encoded(rt.semantic(content(value))))


def summary(value):
    threads = value.get('suggestions', [])
    return {'pending':sum(t.get('status') == 'OPEN' for t in threads),
            'accepted':sum(t.get('status') == 'ACCEPTED' for t in threads),
            'rejected':sum(t.get('status') == 'REJECTED' for t in threads),
            'unresolved_comments':sum(t.get('status') == 'OPEN' for t in value.get('comments', []))}


def accepted_markdown(value):
    """Readable accepted text; DOCX/native remain the formatting record.

    Fail closed on structures this bounded renderer cannot faithfully represent.
    """
    if value.get('suggestionsViewMode') != 'PREVIEW_WITHOUT_SUGGESTIONS' or rt.suggestions(value):
        raise GoogleError('A suggestions-excluded native preview is required.')
    selected = rt.tabs(value)
    if len(selected) != 1:
        raise GoogleError('Review snapshots require a single-tab document.')
    native = selected[0].get('documentTab', {})
    if any(native.get(k) for k in ('headers', 'footers', 'footnotes')):
        raise GoogleError('Review pull needs a scoped native conversion for headers, footers or footnotes.')
    def escape(text):
        return re.sub(r'([\\`*_{}\[\]<>#!|~])', r'\\\1', text)
    output = []
    for block in native.get('body', {}).get('content', []):
        if 'sectionBreak' in block:continue
        if 'paragraph' not in block:
            raise GoogleError('Review pull cannot project this structure. Use a scoped accepted-text conversion; preserve DOCX.')
        para = block['paragraph']; runs = para.get('elements', [])
        plain=''.join(e.get('textRun',{}).get('content','') for e in runs)
        if any(c in plain.rstrip('\n') for c in ('\n','\r','\u2028','\u2029')):
            raise GoogleError('Embedded line breaks need a scoped accepted-text conversion.')
        line = ''; merged=[]
        for element in runs:
            if set(element)-{'startIndex','endIndex','textRun'} or 'textRun' not in element:
                raise GoogleError('Review pull cannot project embedded objects; use a scoped accepted-text conversion.')
            run=element['textRun']; style=run.get('textStyle',{})
            if merged and merged[-1][1]==style:merged[-1][0]+=run.get('content','')
            else:merged.append([run.get('content',''),style])
        for plain,style in merged:
            # Markdown delimiters cannot include leading/trailing whitespace.
            leading=plain[:len(plain)-len(plain.lstrip())]
            trailing=plain[len(plain.rstrip()):] if plain.strip() else ''
            text=escape(plain.strip())
            if text:
                if style.get('bold'):text='**'+text+'**'
                if style.get('italic'):text='*'+text+'*'
                if style.get('link'):
                    url=style['link'].get('url','')
                    if not url.startswith(('https://','http://','mailto:')) or any(c.isspace() or c in '<>' for c in url):
                        raise GoogleError('Review pull needs inspection of an unsupported link.')
                    text='['+text+'](<'+url+'>)'
            line+=leading+text+trailing
        line = line.rstrip('\n')
        line = re.sub(r'^(\s*\d+)([.)])(?=\s)', r'\1\\\2', line)
        line = re.sub(r'^(\s*)- (?=.)', r'\1\\- ', line)
        named = para.get('paragraphStyle',{}).get('namedStyleType','NORMAL_TEXT')
        if named.startswith('HEADING_') and named[-1:] in '123456':line = '#'*int(named[-1])+ ' '+line
        if para.get('bullet'):
            bullet = para['bullet']; level = bullet.get('nestingLevel',0)
            levels = native.get('lists',{}).get(bullet.get('listId'),{}).get('listProperties',{}).get('nestingLevels',[])
            if type(level) is not int or not 0 <= level < len(levels):raise GoogleError('List structure is unavailable for accepted-text projection.')
            shape = levels[level]
            if shape.get('glyphType') not in (None,'GLYPH_TYPE_UNSPECIFIED'):
                raise GoogleError('Ordered lists need a scoped accepted-text conversion to retain numbering.')
            line = '  '*level+'- '+line
        output.append(line)
    result = '\n\n'.join(output).rstrip()+'\n'
    if not result.strip():raise GoogleError('No accepted body text to pull.')
    return result.encode()


def linked(root, article_id, kind):
    directory, record = studio.item(root, 'articles', article_id)
    target = record.get('google', {}).get('baselines', {}).get(kind, {}).get('document')
    if not target:raise GoogleError('Link the unedited manuscript to a Google Doc first, then propose the selected findings.')
    return directory, record, target


def position(text, units):
    for n in range(len(text)+1):
        if rt.utf16(text[:n]) == units:return n
    raise GoogleError('The anchor splits a character or is outside the paragraph.')


def build(document_value, findings, selected_tabs):
    if rt.suggestions(document_value) or summary(document_value)['pending']:
        raise GoogleError('Existing suggestions need review before another submission; pull accepted text and inspect pending items.')
    if not isinstance(findings, list) or not 1 <= len(findings) <= 100:
        raise GoogleError('Select 1–100 proofreading findings.')
    expected = content(copy.deepcopy(document_value))
    paragraphs = rt.paragraphs(expected)
    requests=[]; ids=set(); occupied={}; changes={}; comments=[]
    for f in findings:
        required={'id','tab_id','start_index','before','reason','kind'}
        if not isinstance(f,dict) or set(f)-required-{'after','minor'} or required-set(f):
            raise GoogleError('Each finding needs id, kind, tab_id, start_index, before, reason and optional after.')
        if not isinstance(f['id'],str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,80}',f['id']) or f['id'] in ids:
            raise GoogleError('Use unique stable finding IDs from the saved review.')
        if 'minor' in f and type(f['minor']) is not bool:raise GoogleError('minor must be true or false.')
        ids.add(f['id'])
        marker='[Blog Studio '+f['id']+']'
        if any(marker in t.get('headPost',{}).get('content','') for t in document_value.get('comments',[])):
            raise GoogleError('This finding already has a Google thread. Reconcile the existing review instead of reposting.')
        if f['kind'] not in ('edit','comment') or f['tab_id'] not in selected_tabs or type(f['start_index']) is not int:
            raise GoogleError('Choose an edit/comment anchored in a selected tab.')
        if not isinstance(f['before'],str) or not f['before'] or any(ord(c)<32 for c in f['before']):
            raise GoogleError('Anchor findings to nonempty text within a body paragraph.')
        if not isinstance(f['reason'],str) or not f['reason'].strip():raise GoogleError('Each finding needs a reason.')
        note='[Blog Studio '+f['id']+'] '+f['reason']
        if len(note.encode())>2048:raise GoogleError('Comment exceeds Google’s 2048-byte limit.')
        if f['kind']=='edit':
            if not isinstance(f.get('after'),str) or any(ord(c)<32 or c in '\u2028\u2029' for c in f['after']) or f['after']==f['before']:
                raise GoogleError('Provide a changed, single-paragraph replacement (empty means deletion).')
        elif 'after' in f:raise GoogleError('Comments cannot also replace text.')
        match=None
        for (tab,start), paragraph in paragraphs.items():
            if tab!=f['tab_id'] or start>f['start_index']:continue
            text=''.join(e.get('textRun',{}).get('content','') for e in paragraph['elements'])
            if f['start_index'] < start+rt.utf16(text):match=(tab,start,paragraph,text)
        if not match:raise GoogleError('Anchor is outside supported body paragraphs; use a native scoped review for other structures.')
        tab,start,paragraph,text=match
        if any(set(e)-{'startIndex','endIndex','textRun'} or 'textRun' not in e for e in paragraph['elements']):
            raise GoogleError('Paragraph contains unsupported objects; no proposal submitted.')
        offset=start
        for element in paragraph['elements']:
            run=element['textRun']
            if (set(run)-{'content','textStyle'} or element.get('startIndex')!=offset
                    or element.get('endIndex')!=offset+rt.utf16(run['content'])):
                raise GoogleError('Unsupported native run or inconsistent indexes; no proposal submitted.')
            offset=element['endIndex']
        a=position(text,f['start_index']-start);b=a+len(f['before'])
        if text[a:b]!=f['before'] or b>=len(text):
            raise GoogleError('Google wording changed since review. Pull/reconcile and refresh this finding first.')
        end=f['start_index']+rt.utf16(f['before'])
        for left,right in occupied.setdefault(tab,[]):
            if f['start_index']<right and end>left:raise GoogleError('Overlapping findings must be combined before submission.')
        occupied[tab].append((f['start_index'],end))
        r={'tabId':tab,'startIndex':f['start_index'],'endIndex':end}
        group=[]
        comments.append({'id':f['id'],'content':note,'quote':f['before'],'range':r})
        if f['kind']=='edit':
            styles=[e['textRun'].get('textStyle',{}) for e in paragraph['elements'] for _ in e['textRun']['content']]
            chosen=styles[a]
            if any(v!=chosen for v in styles[a:b]):raise GoogleError('Split replacements at style or link boundaries.')
            group.append({'deleteContentRange':{'range':r}})
            if f['after']:
                # Suggested deletions retain inline indexes. Insert AFTER the retained old range.
                group.extend([{'insertText':{'location':{'tabId':tab,'index':end},'text':f['after']}},
                    {'updateTextStyle':{'range':{'tabId':tab,'startIndex':end,'endIndex':end+rt.utf16(f['after'])},
                                        'textStyle':chosen,'fields':'*'}}])
            changes.setdefault((tab,start),[]).append((a,b,f['after'],chosen))
        requests.append((tab,f['start_index'],group))
    for key,items in changes.items():
        paragraph=paragraphs[key]
        chars=[(c,e['textRun'].get('textStyle',{})) for e in paragraph['elements'] for c in e['textRun']['content']]
        for a,b,replacement,style in sorted(items, key=lambda item:item[0], reverse=True):
            chars[a:b]=[(c,style) for c in replacement]
        if len(chars)==1:raise GoogleError('Deleting an entire paragraph is a structural edit; use a comment instead.')
        paragraph['elements']=[{'textRun':{'content':c,'textStyle':style}} for c,style in chars]
    native_requests=[r for _,_,group in sorted(requests,reverse=True) for r in group]
    for comment in comments:
        r=comment['range']
        shift=sum(rt.utf16(f['after']) for f in findings if f['kind']=='edit' and f['tab_id']==r['tabId']
                  and f['start_index']+rt.utf16(f['before'])<=r['startIndex'])
        comment['range']={**r,'startIndex':r['startIndex']+shift,'endIndex':r['endIndex']+shift}
        native_requests.append({'insertComment':{'content':comment['content'],'range':comment['range']}})
    return {'requests':native_requests, 'comments':comments,
            'expected_sha256':signature(expected),'before_sha256':signature(document_value)}


def plan(client, root, article_id, kind, findings, output, mode='auto'):
    directory,record,target=linked(root,article_id,kind)
    local=studio.artifact_fingerprint(directory,kind.upper()+'.md')
    if not local:raise GoogleError('Save the local manuscript before preparing review suggestions.')
    baseline=digest(encoded(record['google']['baselines'][kind]))
    from google_review_comments import build as comment_build, unavailable
    if mode not in ('auto','native','comments'):raise GoogleError('Choose auto, native or comments.')
    try:current=review_read(client,target['document_id'])
    except GoogleError as exc:
        if mode=='native' or not unavailable(exc):raise
        current=rt.clean_read(client,target['document_id']);mode='comments'
    # The proofread Google baseline must still match, including formatting.
    if not target.get('format_sha256') or signature(current)!=target['format_sha256']:
        raise GoogleError('Pull the latest Google Doc and reconcile local changes before refreshing findings and planning suggestions.')
    result={'schema':1,'article':article_id,'kind':kind,'document_id':target['document_id'],
        'tab_ids':target['tab_ids'],'revision_id':current['revisionId'],'local_sha256':local,
        'baseline_sha256':baseline,'findings':findings,'mode':mode,
        'comment_plan':comment_build(current,findings,target['tab_ids']),**build(current,findings,target['tab_ids'])}
    if local!=studio.artifact_fingerprint(directory,kind.upper()+'.md'):raise GoogleError('Local writing changed during planning.')
    write_new(output,encoded(result))
    return {'status':'planned','file':str(output),'findings':len(findings),'mode':mode,
            'next_step':'Submit only these selected findings. The helper rereads Google and requires this exact revision.'}


def ledger(root):return contained(root,'.google-review-operations')


def operation_key(saved):return digest(encoded(saved))


def apply_native(client, root, saved):
    directory,record,target=linked(root,saved['article'],saved['kind'])
    if (target['document_id']!=saved['document_id'] or target['tab_ids']!=saved['tab_ids']
            or digest(encoded(record['google']['baselines'][saved['kind']]))!=saved['baseline_sha256']
            or studio.artifact_fingerprint(directory,saved['kind'].upper()+'.md')!=saved['local_sha256']):
        raise GoogleError('Local writing or transfer baseline changed. Pull/reconcile and refresh the review.')
    store=ledger(root); key=operation_key(saved)
    with locked(store):
        receipt=contained(store,key+'.json')
        markers=[contained(store,digest(encoded([saved['document_id'],f['id']]))+'.finding') for f in saved['findings']]
        if receipt.exists() or any(p.exists() for p in markers):
            raise GoogleError('These findings were already submitted or have an uncertain attempt. Use verify; do not resubmit.')
        current=review_read(client,saved['document_id'])
        if current['revisionId']!=saved['revision_id'] or build(current,saved['findings'],saved['tab_ids'])!={k:saved[k] for k in ('requests','comments','expected_sha256','before_sha256')}:
            raise GoogleError('Google changed after planning. Pull/reconcile and refresh findings before sending.')
        if studio.artifact_fingerprint(directory,saved['kind'].upper()+'.md')!=saved['local_sha256']:
            raise GoogleError('Local writing changed during preflight.')
        write_new(receipt,encoded({'status':'submitting','operation':key,'document_id':saved['document_id']}))
        for path in markers:write_new(path,key.encode())
        try:response=client.native_review_update(saved['document_id'],saved['revision_id'],saved['requests'])
        except GoogleError as exc:
            if exc.review_unavailable:
                write_json(receipt,{'status':'native-rejected','operation':key,'document_id':saved['document_id']})
            raise
        write_json(receipt,{'status':'submitted-unverified','operation':key,'document_id':saved['document_id'],
                            'comment_update_state':response.get('commentUpdateState')})
    return verify(client,root,saved)


def apply(client, root, saved):
    from google_review_comments import apply as comments_apply, unavailable
    if saved.get('mode')=='comments':return comments_apply(client,root,saved)
    try:return apply_native(client,root,saved)
    except GoogleError as exc:
        if saved.get('mode')!='auto' or not unavailable(exc):raise
        receipt=contained(ledger(root),operation_key(saved)+'.json')
        reserved=receipt.exists()
        if reserved and json.loads(receipt.read_text()).get('status')!='native-rejected':raise
        return comments_apply(client,root,saved,reserved=reserved)


def verify(client, root, saved):
    path=contained(ledger(root),operation_key(saved)+'.json')
    if not path.is_file():raise GoogleError('No recorded attempt exists for this plan.')
    receipt=json.loads(path.read_text())
    if receipt.get('backend'):
        from google_review_comments import verify as comments_verify
        return comments_verify(client,root,saved)
    inline=review_read(client,saved['document_id'])
    before=document(client,saved['document_id'])
    after=document(client,saved['document_id'],accepted_preview=True)
    again=review_read(client,saved['document_id'])
    stable=len({v['revisionId'] for v in (inline,before,after,again)})==1
    comments=[]
    def anchors(value):
        found=[]
        if isinstance(value,dict):
            if 'anchorId' in value and 'ranges' in value:found.append(value)
            for child in value.values():found.extend(anchors(child))
        elif isinstance(value,list):
            for child in value:found.extend(anchors(child))
        return found
    located=anchors(inline)
    for expected in saved['comments']:
        matches=[t for t in inline.get('comments',[]) if t.get('headPost',{}).get('content')==expected['content']
                 and t.get('plainTextQuote')==expected['quote'] and t.get('status')=='OPEN'
                 and any(a['anchorId']==t.get('anchorId') and any(all(r.get(k)==v for k,v in expected['range'].items()) for r in a['ranges']) for a in located)]
        comments.append({'id':expected['id'],'verified':len(matches)==1,
                         'thread_id':matches[0]['commentId'] if len(matches)==1 else None})
    wants_edits=any(f['kind']=='edit' for f in saved['findings'])
    good=(stable and receipt.get('comment_update_state')=='ALL_SAVED'
          and signature(before)==saved['before_sha256'] and signature(after)==saved['expected_sha256']
          and all(v['verified'] for v in comments) and (not wants_edits or summary(inline)['pending']>0))
    result={'status':'verified-pending' if good else 'needs-reconciliation','operation':operation_key(saved),
            'document_id':saved['document_id'],'revision_id':inline['revisionId'],
            'accepted_text_unchanged':stable and signature(before)==saved['before_sha256'],
            'comments':comments,'review_state':summary(inline),'checked_at':studio.now(),
            'next_step':'Review proposals in Google Docs, then pull accepted changes.' if good else
                        'Inspect Google and the original attempt. Do not retry or accept/reject anything automatically.'}
    write_json(path,{**receipt,'verification':result})
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--root',type=Path,required=True);p.add_argument('--account')
    sub=p.add_subparsers(dest='action',required=True)
    prepare=sub.add_parser('plan');prepare.add_argument('--id',required=True);prepare.add_argument('--kind',choices=('draft','outline'),default='draft')
    prepare.add_argument('--findings',type=Path,required=True);prepare.add_argument('--output',type=Path,required=True);prepare.add_argument('--mode',choices=('auto','native','comments'),default='auto')
    for name in ('apply','verify'):
        command=sub.add_parser(name);command.add_argument('--plan',type=Path,required=True)
    show=sub.add_parser('show-review');show.add_argument('--id',required=True)
    edit=sub.add_parser('apply-edits');edit.add_argument('--plan',type=Path,required=True);edit.add_argument('--numbers',type=int,nargs='+',required=True)
    check=sub.add_parser('verify-edits');check.add_argument('--plan',type=Path,required=True)
    args=p.parse_args()
    try:
        if not args.root.is_absolute():raise GoogleError('Use an absolute writing workspace.')
        client=Client(args.account)
        if args.action=='plan':result=plan(client,args.root,args.id,args.kind,json.loads(args.findings.read_text()),args.output,args.mode)
        elif args.action in ('show-review','apply-edits','verify-edits'):
            import google_review_comments as comments
            if args.action=='show-review':result=comments.show(args.root,args.id)
            elif args.action=='apply-edits':result=comments.apply_edits(client,args.root,json.loads(args.plan.read_text()),args.numbers)
            else:result=comments.verify_edits(client,args.root,json.loads(args.plan.read_text()))
        else:result=globals()[args.action](client,args.root,json.loads(args.plan.read_text()))
        print(json.dumps(result,indent=2));return 0
    except GoogleError as exc:error=str(exc)
    except (OSError,ValueError,KeyError,TypeError):error='Invalid or unavailable local review state. Preserve the submission record and reconcile; do not retry writes.'
    print(json.dumps({'status':'unavailable','error':error}),file=sys.stderr);return 1


if __name__=='__main__':sys.exit(main())
