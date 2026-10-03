"""Compact local context and exact-input reuse. No provider/model observations cached."""
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import studio
from local_cache import reuse, maintain

EXTRACTOR_VERSION = 'utf8-html-text-v1'
PASSAGE_VERSION = 'paragraph-offsets-v1'
CHECK_VERSION = 'mechanical-lint-v1'


class PlainHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True);self.parts=[];self.hidden=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'): self.hidden += 1
        if not self.hidden and tag in ('p','div','br','h1','h2','h3','li','section'): self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style'): self.hidden=max(0,self.hidden-1)
        if not self.hidden and tag in ('p','div','h1','h2','h3','li','section'): self.parts.append('\n')
    def handle_data(self,data):
        if not self.hidden:self.parts.append(data)


def extract(root, data, suffix):
    suffix=suffix.lower()
    if suffix not in ('.txt','.md','.html','.htm'): raise ValueError('Use host extraction for this file format.')
    def compute():
        text=data.decode('utf-8')
        if suffix in ('.html','.htm'):
            parser=PlainHTML();parser.feed(text);parser.close()
            text='\n\n'.join(line.strip() for line in ''.join(parser.parts).splitlines() if line.strip())
        return {'text':text,'extractor':EXTRACTOR_VERSION,'source_sha256':studio.digest(data)}
    return reuse(root,'extraction',{'bytes':studio.digest(data),'format':suffix,'version':EXTRACTOR_VERSION},compute)


def compact(root, article_id, limit=5, offset=0):
    if not 1 <= limit <= 50 or offset < 0: raise ValueError('Use limit 1–50 and nonnegative offset.')
    directory,record=studio.item(root,'articles',article_id)
    selected=record['sources'][offset:offset+limit]
    sources=[]
    for pin in selected:
        source_dir,source=studio.item(root,'sources',pin['source_id'])
        sources.append({**pin,'name':source['name'],'current_revision':source['revision'],
            'changed':pin['revision']!=source['revision'],'status':source['status'],
            'record':str(source_dir/'record.json')})
    artifacts={name:str(studio.inside(directory,name)) for name in ('BRIEF.md','ORIGINAL.md','OUTLINE.md','DRAFT.md','INTERVIEW.md','DECISIONS.md') if studio.inside(directory,name).is_file()}
    return {'id':record['id'],'title':record['title'],'stage':record['stage'],
        'next_step':record['next_step'],'pending_question':record['pending_question'],
        'stop_point':record['stop_point'],'research_policy':record['research_policy'],
        'pins':{'voice':record['voice'],'guidance':record.get('guidance'),'team':record.get('hub_context')},
        'memory':[{'key':k,'revision':v['revision']} for k,v in record.get('memory',{}).items() if v['status']=='active'],
        'record':str(directory/'session.json'),'artifacts':artifacts,'sources':sources,
        'source_count':len(record['sources']),'source_offset':offset,'sources_truncated':offset+limit<len(record['sources']),
        'reviews':{k:v['status'] for k,v in studio.freshness(root,directory,record).items()},
        'gaps':{'voice_unconfigured':record['voice']['mode']=='preserve','no_sources':not record['sources'],
                'no_guidance_pin':not record.get('guidance')},
        'coverage':'Selected metadata only. Open active memory/rules and needed artifacts before writing; page remaining sources.'}


def resume(root, article_id):
    from author_workflow import status
    from local_reads import operation
    with operation():
        return {'context':compact(root,article_id),'status':status(root,article_id)}


def passage_index(text):
    # Preserve exact offsets, including fenced code and quotations. These are data, not instructions.
    return [{'start':m.start(),'end':m.end()} for m in re.finditer(r'\S[\s\S]*?(?=\n\s*\n|\Z)',text)]


def passages(root, article_id, source=None, query='', limit=3, offset=0, max_chars=4000):
    if not 1 <= limit <= 20 or offset < 0 or not 100 <= max_chars <= 16000:
        raise ValueError('Use limit 1–20, nonnegative offset, and 100–16000 characters.')
    directory,record=studio.item(root,'articles',article_id)
    provenance={'article':article_id,'kind':'draft'}
    path=studio.inside(directory,'DRAFT.md')
    if source:
        pin=next((x for x in record['sources'] if x['source_id']==source),None)
        if not pin:raise ValueError('Source is not selected for this article.')
        directory,current=studio.item(root,'sources',source)
        revision=pin['revision']
        if revision!=current['revision']:
            directory=studio.inside(directory,'revisions',str(revision))
            current=studio.read_json(directory/'record.json')
        path=studio.inside(directory,'content.md')
        if current['status']!='ready':raise ValueError('Selected source revision is not readable evidence.')
        provenance={'article':article_id,'source':source,'revision':revision,'origin':current['origin'],'roles':pin['purposes']}
    data=path.read_bytes();text=data.decode('utf-8');digest=studio.digest(data)
    index,hit=reuse(root,'passages',{'hash':digest,'version':PASSAGE_VERSION},lambda:passage_index(text))
    terms=query.casefold().split()
    matches=[v for v in index if all(term in text[v['start']:v['end']].casefold() for term in terms)]
    rows=[];remaining=max_chars
    for span in matches[offset:offset+limit]:
        if remaining<=0:break
        end=min(span['end'],span['start']+remaining)
        excerpt=text[span['start']:end];remaining-=len(excerpt)
        rows.append({'start':span['start'],'end':end,'line':text.count('\n',0,span['start'])+1,
                     'text':excerpt,'truncated':end<span['end']})
    return {'provenance':provenance,'sha256':digest,'path':str(path),'passages':rows,'matching_passages':len(matches),
        'offset':offset,'truncated':offset+len(rows)<len(matches) or any(v['truncated'] for v in rows),
        'index_cache_hit':hit,'coverage':'Exact excerpts, not a summary or a completed whole-article review. Read original context for claims and cross-section reasoning.'}


def check(root, article_id, rules):
    from text_checks import lint
    studio.validate_rules(rules)
    directory,record=studio.item(root,'articles',article_id)
    path=studio.inside(directory,'DRAFT.md');text=path.read_text()
    inputs=studio.fingerprints(root,directory,record)
    # Check the bytes actually reviewed, not a second read's draft hash.
    inputs['draft']=studio.digest(text.encode())
    if record['voice'].get('mode')=='profile':
        pin=record['voice'];folder=studio.inside(root,'profiles',studio.identifier(pin['profile_id']),'revisions',str(pin['revision']))
        inputs['voice_files']={name:studio.digest(studio.inside(folder,name).read_bytes()) for name in ('VOICE.md','rules.json')}
    inputs.update(rules=rules,selected_sources=studio.digest(json.dumps(record['sources'],sort_keys=True).encode()),check_version=CHECK_VERSION)
    result,hit=reuse(root,'mechanical-review',inputs,lambda:lint(text,rules))
    return {'result':result,'cache_hit':hit,'inputs':inputs,'coverage':'Mechanical whole-article checks only; does not mark an editorial review current.'}


def add_parser(groups):
    resume_parser=groups.add_parser('resume',help='Compact context and cached status in one operation')
    resume_parser.add_argument('--id',required=True)
    passages_parser=groups.add_parser('passages',help='Exact bounded excerpts from the draft or a pinned selected source')
    passages_parser.add_argument('--id',required=True);passages_parser.add_argument('--source');passages_parser.add_argument('--query',default='')
    passages_parser.add_argument('--limit',type=int,default=3);passages_parser.add_argument('--offset',type=int,default=0)
    passages_parser.add_argument('--max-chars',type=int,default=4000)
    check_parser=groups.add_parser('check',help='Reuse exact-input mechanical diagnostics')
    check_parser.add_argument('--id',required=True);check_parser.add_argument('--rules-file')
    cache=groups.add_parser('cache',help='Inspect or remove local derived data')
    cache.add_argument('--clear',action='store_true')


def command(root,args):
    if args.group=='resume':return resume(root,args.id)
    if args.group=='passages':return passages(root,args.id,args.source,args.query,args.limit,args.offset,args.max_chars)
    if args.group=='cache':return maintain(root,args.clear)
    rules=studio.read_json(Path(args.rules_file)) if args.rules_file else {}
    return check(root,args.id,rules)
