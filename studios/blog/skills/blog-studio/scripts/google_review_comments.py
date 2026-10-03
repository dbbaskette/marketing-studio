"""Readable review comments and explicitly selected, revision-guarded edits."""
import json

import google_roundtrip as rt
import google_suggestions as gs
import studio
from google_drive import GoogleError, digest, encoded, write_new
from hub_store import contained, locked, write_json


def unavailable(error):
    return isinstance(error, GoogleError) and error.review_unavailable


def build(doc, findings, selected_tabs):
    # Reuse exact-quote, overlap, scope, style and native-index validation.
    gs.build(gs.content(doc), findings, selected_tabs)
    paragraphs=rt.paragraphs(doc); sections={}; titles={}
    for tab in rt.tabs(doc):
        tid=tab['tabProperties']['tabId']; section='Opening'; titles[tid]=tab['tabProperties'].get('title',tid)
        for (pid,start),para in paragraphs.items():
            if pid!=tid:continue
            text=''.join(e.get('textRun',{}).get('content','') for e in para['elements'])[:-1]
            if para.get('paragraphStyle',{}).get('namedStyleType','').startswith('HEADING_'):section=text
            sections[(tid,start)]=section
    entries=[]; groups=[]
    for number,f in enumerate(findings,1):
        key=next((key for key,para in paragraphs.items() if key[0]==f['tab_id']
            and key[1]<=f['start_index']<key[1]+rt.utf16(''.join(e['textRun']['content'] for e in para['elements']))),None)
        para=paragraphs[key]; text=''.join(e.get('textRun',{}).get('content','') for e in para['elements'])[:-1]
        entry={'number':number,'finding':f,'paragraph':text,'paragraph_start':key[1],
               'section':sections[key], 'tab_title':titles[key[0]]}
        entries.append(entry)
        group=next((g for g in groups if f.get('minor') and f['kind']=='edit' and g['minor'] and g['key']==key and len(g['entries'])<4),None)
        if group is None:
            group={'key':key,'minor':f.get('minor',False) and f['kind']=='edit','entries':[]};groups.append(group)
        group['entries'].append(entry)
    comments=[]
    def render(items):
        first=items[0]; numbers=[e['number'] for e in items]
        title=('Edits '+', '.join(map(str,numbers)) if len(items)>1 else 'Edit '+str(numbers[0]))
        body=title+' · '+first['section']+'\nTab: '+first['tab_title']+'\n'
        for e in items:
            f=e['finding'];body+='\n'+('Edit '+str(e['number'])+'\n' if len(items)>1 else '')
            body+='Current: '+f['before']+'\n'
            if f['kind']=='edit':body+='Proposed: '+(f['after'] or '(delete this text)')+'\n'
            body+='Why: '+f['reason']+'\n'
        editable=[e['number'] for e in items if e['finding']['kind']=='edit']
        body+=('\nReview in Blog Studio: “Apply edits '+', '.join(map(str,editable))+'.”\n' if editable
               else '\nDiscuss this feedback before deciding on wording.\n')
        body+='\n'.join('[Blog Studio '+e['finding']['id']+']' for e in items)
        if len(body.encode())>2048:
            if len(items)>1:
                for e in items:render([e])
                return
            raise GoogleError('This review comment is too long; shorten the finding before posting.')
        f=first['finding']; quote=first['paragraph'] if len(items)>1 else f['before']
        start=first['paragraph_start'] if len(items)>1 else f['start_index']
        comments.append({'numbers':numbers,'content':body,'quote':quote,
            'range':{'tabId':f['tab_id'],'startIndex':start,'endIndex':start+rt.utf16(quote)}})
    for group in groups:render(group['entries'])
    return {'entries':entries,'comments':comments}


def path(root, saved):return contained(gs.ledger(root),gs.operation_key(saved)+'.json')


def current(client, saved):
    doc=rt.clean_read(client,saved['document_id'])
    if gs.signature(doc)!=saved['before_sha256']:
        raise GoogleError('Google changed; refresh the review before posting comments.')
    if build(doc,saved['findings'],saved['tab_ids'])!=saved['comment_plan']:
        raise GoogleError('The comment plan differs from current Google content; no comments posted.')
    return doc


def read_threads(client, saved, backend):
    if backend=='native-comments':
        doc=gs.review_read(client,saved['document_id']);anchors=[]
        def walk(v):
            if isinstance(v,dict):
                if 'anchorId' in v and 'ranges' in v:anchors.append(v)
                for x in v.values():walk(x)
            elif isinstance(v,list):
                for x in v:walk(x)
        walk(doc)
        return [{'id':t.get('commentId'),'content':t.get('headPost',{}).get('content'),
                 'quote':t.get('plainTextQuote'),'resolved':t.get('status')=='RESOLVED',
                 'ranges':[r for a in anchors if a['anchorId']==t.get('anchorId') for r in a['ranges']]}
                for t in doc.get('comments',[])]
    return [{'id':t.get('id'),'content':t.get('content'),'quote':t.get('quotedFileContent',{}).get('value'),
             'resolved':t.get('resolved',False),'deleted':t.get('deleted',False),'mine':t.get('author',{}).get('me',False)}
            for t in client.review_comments(saved['document_id'])]


def matches(thread, expected, backend):
    return (thread.get('id') and not thread.get('deleted') and thread.get('content')==expected['content']
        and thread.get('quote')==expected['quote'] and (backend!='native-comments'
        or any(all(r.get(k)==v for k,v in expected['range'].items()) for r in thread.get('ranges',[]))))


def apply(client, root, saved, reserved=False):
    directory,record,target=gs.linked(root,saved['article'],saved['kind'])
    if (target['document_id']!=saved['document_id'] or target['tab_ids']!=saved['tab_ids']
        or digest(encoded(record['google']['baselines'][saved['kind']]))!=saved['baseline_sha256']
        or studio.artifact_fingerprint(directory,saved['kind'].upper()+'.md')!=saved['local_sha256']):
        raise GoogleError('Local writing or linked baseline changed; refresh before sending review comments.')
    store=gs.ledger(root);key=gs.operation_key(saved)
    with locked(store):
        receipt_path=path(root,saved)
        markers=[contained(store,digest(encoded([saved['document_id'],f['id']]))+'.finding') for f in saved['findings']]
        if reserved:
            receipt=json.loads(receipt_path.read_text())
            if receipt.get('status')!='native-rejected' or receipt.get('operation')!=key:
                raise GoogleError('An uncertain submission cannot switch to comments.')
        elif receipt_path.exists() or any(p.exists() for p in markers):
            raise GoogleError('Review already attempted; verify the existing result instead of reposting.')
        doc=current(client,saved)
        if doc['revisionId']!=saved['revision_id']:
            raise GoogleError('Google changed after planning; refresh findings before posting.')
        backend='native-comments'
        try:gs.review_read(client,saved['document_id'])
        except GoogleError as exc:
            if not unavailable(exc):raise
            backend='drive-comments'
        # List the selected surface before sending, including resolved findings.
        existing=read_threads(client,saved,backend)
        if any('[Blog Studio '+f['id']+']' in (t.get('content') or '') for f in saved['findings'] for t in existing):
            raise GoogleError('These findings already have review comments. Reconcile instead of reposting.')
        if backend=='drive-comments' and client.metadata(saved['document_id']).get('capabilities',{}).get('canComment') is not True:
            raise GoogleError('Google has not confirmed comment permission. Keep the review locally.')
        if studio.artifact_fingerprint(directory,saved['kind'].upper()+'.md')!=saved['local_sha256']:
            raise GoogleError('Local writing changed during preflight.')
        receipt={'status':'submitting-comments','operation':key,'document_id':saved['document_id'],
                 'backend':backend,'posted':[], 'applied':[]}
        if not reserved:
            write_new(receipt_path,encoded(receipt))
            for marker in markers:write_new(marker,key.encode())
        else:write_json(receipt_path,receipt)
        plan_path=contained(store,key+'.plan.json')
        if not plan_path.exists():write_new(plan_path,encoded(saved))
        write_json(studio.inside(directory,'.google-review.json'),{'operation':key})
        if backend=='native-comments':
            requests=[{'insertComment':{'content':c['content'],'range':c['range']}} for c in saved['comment_plan']['comments']]
            try:
                response=client.native_comments_update(saved['document_id'],doc['revisionId'],requests)
                receipt['native_ack']=response.get('commentUpdateState')
                receipt['status']='comments-submitted';write_json(receipt_path,receipt)
            except GoogleError as exc:
                if not unavailable(exc):raise
                # Definite rejection only. No fallback following timeout/partial success.
                current(client,saved)
                backend='drive-comments';receipt['backend']=backend
                existing=read_threads(client,saved,backend)
                if any('[Blog Studio '+f['id']+']' in (t.get('content') or '') for f in saved['findings'] for t in existing):
                    raise GoogleError('A review comment already exists; reconcile before continuing.')
                write_json(receipt_path,receipt)
        if backend=='drive-comments':
            if client.metadata(saved['document_id']).get('capabilities',{}).get('canComment') is not True:
                raise GoogleError('Google has not confirmed comment permission. Keep the review locally.')
            for c in saved['comment_plan']['comments']:
                current(client,saved)
                receipt['pending_comment']=c['numbers'];write_json(receipt_path,receipt)
                response=client.create_review_comment(saved['document_id'],c['content'],c['quote'])
                if not response.get('id'):raise GoogleError('Comment result is uncertain; verify instead of reposting.')
                receipt['posted'].append({'id':response['id'],'numbers':c['numbers']})
                receipt.pop('pending_comment',None);write_json(receipt_path,receipt)
            receipt['status']='comments-submitted';write_json(receipt_path,receipt)
    return verify(client,root,saved)


def verify(client, root, saved):
    receipt_path=path(root,saved);receipt=json.loads(receipt_path.read_text());backend=receipt['backend']
    before=rt.clean_read(client,saved['document_id']);threads=read_threads(client,saved,backend)
    after=rt.clean_read(client,saved['document_id'])
    stable=before['revisionId']==after['revisionId'] and gs.signature(after)==saved['before_sha256']
    results=[]
    for c in saved['comment_plan']['comments']:
        found=[t for t in threads if matches(t,c,backend)]
        results.append({'numbers':c['numbers'],'verified':len(found)==1,
            'thread_id':found[0]['id'] if len(found)==1 else None,
            'resolved':found[0].get('resolved',False) if len(found)==1 else False})
    good=stable and all(r['verified'] for r in results) and receipt.get('native_ack') not in ('ALL_FAILED_UNKNOWN_REASON','NO_UPDATES_REQUESTED')
    editable=[str(i) for i,f in enumerate(saved['findings'],1) if f['kind']=='edit'][:2]
    next_action=('Then say “Apply '+('edits ' if len(editable)>1 else 'edit ')+' and '.join(editable)+'” for the items you choose.') if editable else 'Discuss the feedback before deciding on wording.'
    result={'status':'verified-comments' if good else 'needs-reconciliation','mode':backend,
            'accepted_text_unchanged':stable,'comments':results,'operation':gs.operation_key(saved),
            'message':('Added '+str(len(saved['findings']))+' proposed edits in '+str(len(results))+
                       ' comments. Your document text is unchanged.') if good else
                       'Review posting is incomplete or Google changed. Inspect existing comments; do not repost.',
            'next_step':'Open Google Docs'+(' → All Comments' if backend=='drive-comments' else '')+
                        '. '+next_action}
    receipt['verification']=result;write_json(receipt_path,receipt)
    return result


def show(root, article_id):
    directory,_=studio.item(root,'articles',article_id)
    pointer=studio.read_json(studio.inside(directory,'.google-review.json'))
    plan_path=contained(gs.ledger(root),pointer['operation']+'.plan.json')
    saved=studio.read_json(plan_path);receipt=studio.read_json(path(root,saved))
    return {'plan':str(plan_path),'operation':gs.operation_key(saved),'mode':receipt.get('backend'),
            'status':receipt.get('verification',{}).get('status',receipt.get('status')),
            'applied':receipt.get('applied',[]),'edits':[{'number':e['number'],'section':e['section'],
            'current':e['finding']['before'],'proposed':e['finding'].get('after'),
            'reason':e['finding']['reason']} for e in saved['comment_plan']['entries']]}


def apply_edits(client, root, saved, numbers):
    """Caller supplies the user's explicit selection; thread resolution is not approval."""
    if not numbers or len(set(numbers))!=len(numbers) or any(type(n) is not int for n in numbers):
        raise GoogleError('Select unique edit numbers from this review.')
    receipt_path=path(root,saved)
    with locked(gs.ledger(root)):
        receipt=json.loads(receipt_path.read_text())
        if receipt.get('verification',{}).get('status')!='verified-comments':
            raise GoogleError('Verify the posted review comments before applying selected edits.')
        if receipt.get('edit_attempt'):
            raise GoogleError('An edit attempt needs reconciliation; use verify-edits, never repeat the write.')
        directory,_,target=gs.linked(root,saved['article'],saved['kind'])
        if target['document_id']!=saved['document_id'] or target['tab_ids']!=saved['tab_ids']:
            raise GoogleError('The linked Google document changed.')
        local=studio.artifact_fingerprint(directory,saved['kind'].upper()+'.md')
        entries=saved['comment_plan']['entries'];selected=[e for e in entries if e['number'] in numbers]
        if len(selected)!=len(numbers) or any(e['finding']['kind']!='edit' for e in selected):
            raise GoogleError('Choose text-edit numbers; broader feedback needs an explicit wording decision.')
        if any(n in receipt.get('applied',[]) for n in numbers):raise GoogleError('An edit was already applied.')
        doc=rt.clean_read(client,saved['document_id']);threads=read_threads(client,saved,receipt['backend'])
        verified_ids={tuple(c['numbers']):c['thread_id'] for c in receipt['verification']['comments']}
        for c in saved['comment_plan']['comments']:
            if set(c['numbers']) & set(numbers) and len([t for t in threads if t.get('id')==verified_ids.get(tuple(c['numbers'])) and t.get('content')==c['content'] and not t.get('deleted')])!=1:
                raise GoogleError('A selected review comment changed or disappeared; refresh the review.')
        edits=[]
        for key in dict.fromkeys((e['finding']['tab_id'],e['paragraph_start']) for e in selected):
            group=[e for e in entries if (e['finding']['tab_id'],e['paragraph_start'])==key]
            original=group[0]['paragraph']
            def projected(chosen):
                text=original
                for e in sorted(group,key=lambda e:e['finding']['start_index'],reverse=True):
                    if e['number'] not in chosen:continue
                    f=e['finding'];start=gs.position(original,f['start_index']-key[1]);text=text[:start]+f['after']+text[start+len(f['before']):]
                return text
            before=projected(receipt.get('applied',[]));after=projected(set(receipt.get('applied',[]))|set(numbers))
            found=[(k,p) for k,p in rt.paragraphs(doc).items() if k[0]==key[0]
                   and ''.join(x.get('textRun',{}).get('content','') for x in p['elements'])==before+'\n']
            if len(found)!=1:raise GoogleError('Google wording moved ambiguously or changed; refresh these findings.')
            edits.append({'tab_id':key[0],'start_index':found[0][0][1],'before':before,'after':after})
        planned=rt.build_plan(doc,edits)
        if studio.artifact_fingerprint(directory,saved['kind'].upper()+'.md')!=local:
            raise GoogleError('Local writing changed during preflight.')
        receipt['edit_attempt']={'numbers':numbers,'expected_sha256':planned['expected_sha256']}
        write_json(receipt_path,receipt)
        try:client.native_update(saved['document_id'],doc['revisionId'],planned['requests'])
        except GoogleError as exc:
            if exc.status in (400,403,404,409,412):
                receipt.pop('edit_attempt');write_json(receipt_path,receipt)
            raise
        if rt.verify(client,planned)['status']!='verified':
            raise GoogleError('Google wording or formatting could not be verified. Keep the comments open; do not retry.')
        receipt['applied']=sorted(set(receipt.get('applied',[]))|set(numbers))
        receipt.pop('edit_attempt');write_json(receipt_path,receipt)
        # Resolve only fully applied groups, never comments containing pending edits.
        resolved=[]
        for c in saved['comment_plan']['comments']:
            if not set(c['numbers'])<=set(receipt['applied']):continue
            try:live=read_threads(client,saved,receipt['backend'])
            except GoogleError:
                return {'status':'applied-comments-unresolved','applied':numbers,'next_step':'Edits are verified, but comments could not be read. Do not repeat the edits.'}
            matches_now=[t for t in live if t.get('id')==verified_ids.get(tuple(c['numbers'])) and t.get('content')==c['content'] and not t.get('deleted')]
            if len(matches_now)!=1:
                return {'status':'applied-comments-unresolved','applied':numbers,'next_step':'Edits are verified; inspect changed or missing comments. Do not repeat the edits.'}
            t=matches_now[0]
            if t.get('resolved'):continue
            if receipt.get('resolving')==t['id']:
                return {'status':'applied-comments-unresolved','applied':numbers,'next_step':'An earlier resolution is uncertain; inspect it without repeating the request.'}
            if receipt['backend']=='drive-comments' and not t.get('mine'):
                return {'status':'applied-comments-unresolved','applied':numbers,
                        'next_step':'Edits are verified; this account cannot resolve another author’s comment. Pull the latest document.'}
            receipt['resolving']=t['id'];write_json(receipt_path,receipt)
            try:
                if receipt['backend']=='drive-comments':
                    client.resolve_review_comment(saved['document_id'],t['id'])
                else:
                    latest=rt.clean_read(client,saved['document_id'])
                    client.resolve_native_comment(saved['document_id'],t['id'],latest['revisionId'])
                check=read_threads(client,saved,receipt['backend'])
                if any(x['id']==t['id'] and x.get('resolved') for x in check):resolved.append(t['id'])
                else:raise GoogleError('Resolution could not be verified.')
            except GoogleError:
                return {'status':'applied-comments-unresolved','applied':numbers,'resolved_comments':resolved,
                        'next_step':'Edits are verified. Inspect unresolved comments and pull the latest document; do not repeat the edits.'}
            receipt.pop('resolving',None);write_json(receipt_path,receipt)
        return {'status':'applied','applied':numbers,'resolved_comments':resolved,
                'next_step':'Pull from Google Docs to save the verified wording and formatting locally and to the selected Hub.'}


def verify_edits(client, root, saved):
    receipt_path=path(root,saved);receipt=json.loads(receipt_path.read_text())
    attempt=receipt.get('edit_attempt')
    if not attempt:raise GoogleError('No uncertain edit attempt to verify.')
    current=rt.clean_read(client,saved['document_id'])
    good=gs.signature(current)==attempt['expected_sha256']
    return {'status':'applied-text-verified' if good else 'needs-reconciliation',
            'numbers':attempt['numbers'],'next_step':'Inspect the original attempt and comments; never repeat the write.'}
