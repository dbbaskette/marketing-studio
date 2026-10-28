/* Infographic Studio's native editing desk. No build step, remote libraries or implicit provider calls. */
'use strict';
const {make, add} = Drafting;
const launch = new URLSearchParams(location.hash.slice(1));
let token = launch.get('token') || '';
try { if(token)sessionStorage.setItem('infographic-studio-token',token); else token=sessionStorage.getItem('infographic-studio-token')||''; }catch(f){}
function requestId(){return Array.from(crypto.getRandomValues(new Uint8Array(16)),v=>v.toString(16).padStart(2,'0')).join('');}
window.addEventListener('hashchange',()=>{const next=new URLSearchParams(location.hash.slice(1)).get('token');if(next&&next!==token)location.reload();});
function suiteHome(value){try{const u=new URL(value);return u.protocol===location.protocol&&u.hostname===location.hostname&&!u.username&&!u.password&&u.pathname==='/'&&!u.search&&!u.hash?u.origin:'';}catch(f){return '';}}
let homeLink=suiteHome(launch.get('home'));
try{homeLink=homeLink||suiteHome(sessionStorage.getItem('infographic-studio-home'));if(homeLink)sessionStorage.setItem('infographic-studio-home',homeLink);}catch(f){}
if(location.hash)history.replaceState(null,'',location.pathname);
const $ = id => document.getElementById(id);
let held = null, busy = false, picture = null, preferences = null;
const draft = {step: 0, title: '', text: '', direction: 'suggest', audience: '', purpose: '', must: '', locked: '', exclusions: '', preset: 'a4'};
const error = message => { $('notice').textContent = message; $('notice').hidden = !message; };
const toast = message => { const p = make('p', 'toast', message); $('toasts').replaceChildren(p); };
function button(label, action, primary=false) { const node = make('button', 'button' + (primary ? ' button-filled' : ''), label); node.type = 'button'; node.addEventListener('click', action); return node; }
function card(title, ...parts) { return add(make('section', 'card stack'), make('h2', 'card-title', title), ...parts); }
function detail(title, ...parts) { return add(make('details'), make('summary', '', title), ...parts); }
let fieldNumber = 0;
function field(label, value='', kind='input') { const wrap = make('label', 'field'); const input = make(kind, 'input'); input.value = value; const caption=make('span','field-label',label);caption.id='field-caption-'+(++fieldNumber);input.id='field-'+fieldNumber;wrap.htmlFor=input.id;input.setAttribute('aria-labelledby',caption.id);add(wrap, caption, input); return {wrap, input}; }
function lines(value) { return value.split('\n').map(v => v.trim()).filter(Boolean); }
function list(items) { return add(make('ul'), ...items.map(item => make('li', '', item))); }
function sheet(title, ...nodes) { $('sheet-body').replaceChildren(add(make('div', 'ig-sheet stack'), make('h2', 'sheet-title', title))); $('sheet-body').firstChild.firstChild.id = 'sheet-title'; $('sheet-body').firstChild.append(...nodes); $('sheet').showModal(); }
function closeSheet() { $('sheet').close(); }
async function request(route, data) {
  const response = await fetch(route, {method: data === undefined ? 'GET' : 'POST', headers: {'X-Infographic-Studio-Token': token, ...(data === undefined ? {} : {'Content-Type': 'application/json'})}, ...(data === undefined ? {} : {body: JSON.stringify(data)})});
  const answer = await response.json(); if (!response.ok) throw Error(answer.error || 'This request could not be completed.'); return answer;
}
async function action(verb, values={}) {
  if (busy) return; busy = true; error(''); const id = held.project.id;
  const controls = [...document.querySelectorAll('button')]; controls.forEach(b => b.disabled = true);
  toast('Working. Your saved information and earlier previews are kept.');
  const polling=setInterval(async()=>{try{const progress=await request('/api/desk?id='+encodeURIComponent(id));const pending=progress.recovery[0];if(pending){const message=make('p','',pending.state+': image request saved. Closing this page will not resubmit it.');const cancel=button('Cancel this request',async()=>{try{await request('/api/action',{action:'image-cancel',id,expected_revision:progress.project.revision,request_id:pending.attempt_id});toast('Local adoption cancelled. Remote charges may remain unknown.');}catch(f){error(f.message);}});$('toasts').replaceChildren(add(make('div','toast stack'),message,cancel));}}catch(f){}},1000);
  try {
    const answer = await request('/api/action', {action:verb, id, expected_revision:held.project.revision, ...values});
    closeSheet(); await openProject(id); if(answer.result?.state==='unknown')error('The image request outcome is uncertain. Do not repeat it; use the recovery controls.'); else if(answer.result?.state==='failed')error('The image provider could not finish. Your earlier work is kept.'); else if(answer.result?.state==='outdated')toast('The earlier result was kept privately and did not replace newer work.');else toast('Saved.'); return answer.result;
  } catch (failure) { error(failure.message); }
  finally { clearInterval(polling); busy = false; controls.forEach(b => b.disabled = false); document.querySelectorAll('#actions button').forEach(b => b.disabled = false); }
}
function heading(title, ...actions) { for(const id of ['home','settings']){if((id==='settings')===title.startsWith('Settings'))$(id).setAttribute('aria-current','page');else $(id).removeAttribute('aria-current');} $('title').textContent = title; $('actions').replaceChildren(...actions); $('title').focus({preventScroll:true}); }
function resetPicture() { if (picture) URL.revokeObjectURL(picture); picture = null; }
async function home() {
  if (busy) return; resetPicture(); held = null; error(''); heading('Infographics', button('New infographic', () => newSheet(), true));
  try { const data = await request('/api/projects'); const cards = data.projects.map(p => card(p.title || 'Unreadable infographic', make('p', 'quiet', p.problem || 'Revision ' + p.revision), button('Open ' + (p.title || p.id), () => openProject(p.id)))); $('main').replaceChildren(make('p','lede','Turn supplied information into one clear page.'), ...cards); if (!cards.length) $('main').append(card('Make your first infographic', make('p','','Add notes, choose what matters, and review the page before exporting.'))); } catch (failure) { error(failure.message); }
}
async function bytes(file) { if (file.size > 1_000_000) throw Error('The page accepts files up to 1 MB. Use the native source command for larger explicit selections.'); return new Uint8Array(await file.arrayBuffer()); }
function encoded(raw) { let binary=''; for (const v of raw) binary += String.fromCharCode(v); return btoa(binary); }
function retain(input, key) { input.addEventListener('input', () => { draft[key] = input.value; }); }
async function newSheet() {
  error('');
  const form = make('form', 'create-flow');
  const names = ['1. Add information', '2. Set the direction', '3. Choose the page'];
  add(form, make('p','lede',names[draft.step]));
  const problem = make('p', 'problem'); problem.setAttribute('role','alert');
  if (draft.step === 0) {
    const title = field('Working title',draft.title), text = field('Notes or text',draft.text,'textarea'); text.input.classList.add('ig-source-input'); title.input.required=true;
    retain(title.input,'title'); retain(text.input,'text'); add(form,title.wrap,text.wrap);
    const upload = field('Or choose a UTF-8 text, Markdown or CSV file'); upload.input.type='file'; upload.input.accept='.txt,.md,.csv';
    upload.input.addEventListener('change',async()=>{ try { const file=upload.input.files[0]; if(!file) return; const raw=await bytes(file); const suffix=file.name.toLowerCase().split('.').pop(); if(!['txt','md','csv'].includes(suffix)) throw Error('Use UTF-8 text, Markdown or CSV.'); new TextDecoder('utf-8',{fatal:true}).decode(raw); draft.upload={data:encoded(raw),kind:suffix==='md'?'markdown':suffix==='csv'?'csv':'text',name:file.name}; draft.selection=null;
      if(suffix==='csv') { draft.csv=await request('/api/csv-preview',{data:draft.upload.data}); csvSheet(); } else { draft.csv=null; toast('File selected: '+file.name); }
    } catch(failure) { problem.textContent=failure.message; } });
    add(form,upload.wrap,make('p','quiet',draft.upload?'Selected: '+draft.upload.name:'URLs remain references; nothing is fetched. Files stay in your workspace; necessary passages are sent only when you request assistant work.'));
  } else if(draft.step===1) {
    const direction = field('How should we find the story?',draft.direction,'select');
    for(const [value,label] of [['direct','I know what to show'],['suggest','Suggest the story'],['hybrid','Build on my ideas']]) { const option=make('option','',label); option.value=value; direction.input.append(option); } direction.input.value=draft.direction; retain(direction.input,'direction'); add(form,direction.wrap);
    for(const [key,label] of [['audience','Audience and prior knowledge'],['purpose','Desired takeaway or purpose'],['must','Must-show ideas — one per line']]) { const f=field(label,draft[key],key==='must'?'textarea':'input');retain(f.input,key);add(form,f.wrap); }
    const locked=field('Exact wording to preserve — one phrase per line',draft.locked,'textarea'), excluded=field('Leave out — one item per line',draft.exclusions,'textarea'); retain(locked.input,'locked');retain(excluded.input,'exclusions'); add(form,detail('Wording and exclusions',locked.wrap,excluded.wrap));
  } else {
    const preset=field('Page size',draft.preset,'select');for(const [value,label] of [['a4','A4 portrait — 210 × 297 mm'],['letter','US Letter portrait — 8.5 × 11 in'],['digital','Digital portrait — 1080 × 1350 px']]) { const option=make('option','',label);option.value=value;preset.input.append(option); }preset.input.value=draft.preset;retain(preset.input,'preset');add(form,preset.wrap);
    try { preferences=await request('/api/preferences'); const capability=await request('/api/computer'); add(form,make('p','',capability.disclosure),make('p','quiet','Brand: '+(preferences.brand.brand || 'Choose in shared settings before composing.')),make('p','quiet','Saving this brief starts no assistant, image generation or installation.')); } catch(failure) {problem.textContent=failure.message;}
  }
  const go=button(draft.step===2?'Save brief':'Continue',()=>{},true);go.type='submit';
  form.addEventListener('submit',async event=>{event.preventDefault();problem.textContent='';
    if(draft.step===0 && (!draft.title.trim() || (!draft.text.trim() && !draft.upload))) {problem.textContent='Give a title and some usable information.';return;}
    if(draft.upload?.kind==='csv' && !draft.selection) {problem.textContent='Preview and confirm the CSV selection first.';return;}
    if(draft.step<2) {draft.step++;closeSheet();newSheet();return;}
    go.disabled=true;
    try { let p=draft.created;
      if(!p) {draft.request_id=draft.request_id||requestId();p=(await request('/api/projects',{title:draft.title,preset:draft.preset,direction:draft.direction,request_id:draft.request_id})).project;draft.created=p;}
      p=(await request('/api/project',{id:p.id,expected_revision:p.revision,brief:{...p.brief,title:draft.title,preset:draft.preset,direction:draft.direction,audience:draft.audience,purpose:draft.purpose,must_show:lines(draft.must).map((text,i)=>({id:'r'+i,text})),locked_words:lines(draft.locked),exclusions:lines(draft.exclusions)}})).project;draft.created=p;
      const upload=draft.upload || {data:encoded(new TextEncoder().encode(draft.text)),kind:'text',name:'Pasted information'};
      p=(await request('/api/action',{action:'source',id:p.id,expected_revision:p.revision,...upload,...(draft.selection?{selection:draft.selection}:{})})).result;draft.created=p;
      if(draft.upload && draft.text.trim()) p=(await request('/api/action',{action:'source',id:p.id,expected_revision:p.revision,data:encoded(new TextEncoder().encode(draft.text)),kind:'text',name:'Pasted notes'})).result;
      closeSheet();Object.assign(draft,{step:0,request_id:null,created:null,upload:null,selection:null,csv:null,title:'',text:'',direction:'suggest',audience:'',purpose:'',must:'',locked:'',exclusions:'',preset:'a4'});await openProject(p.id);toast('Brief saved. Choose Find the story when you are ready to use your assistant.');
    }catch(failure){problem.textContent=failure.message+' Your answers are still here.';}finally{go.disabled=false;}
  });
  add(form,problem,draft.created||draft.request_id?button('Open the saved draft',()=>{closeSheet();openProject(draft.created?.id||draft.request_id);}):null,add(make('div','create-foot bar'),go,draft.step?button('Back',()=>{draft.step--;closeSheet();newSheet();}):null,button('Cancel',closeSheet))); sheet('New infographic',form);
}
function csvSheet() {
  const data=draft.csv, form=make('form','ig-fields'); const rows=field('Data-row numbers, separated by commas',Array.from({length:data.row_count},(_,i)=>i+1).join(','));
  add(form,make('p','',data.row_count+' data rows. Choose exact rows and column types; numbers are never inferred.'),detail('CSV preview',make('pre','ig-csv-preview',JSON.stringify({columns:data.columns,rows:data.rows.slice(0,20)},null,2)),make('p','quiet','Preview shows at most 20 rows; selected row numbers control capture.')),rows.wrap);
  const columns=data.columns.map(name=>{const type=field(name+' type','text','select');for(const k of ['text','number','date']){const option=make('option','',k);option.value=k;type.input.append(option);}const unit=field(name+' unit (required for numbers)');const use=make('input');use.type='checkbox';use.checked=true;const label=add(make('label','check'),use,document.createTextNode('Include '+name));add(form,card(name,label,type.wrap,unit.wrap));return{name,type:type.input,unit:unit.input,use};});
  const problem=make('p','problem');problem.setAttribute('role','alert');const go=button('Confirm selected rows and columns',()=>{},true);go.type='submit';
  form.addEventListener('submit',async event=>{event.preventDefault();try{const selected=rows.input.value.split(',').map(v=>Number(v.trim())); if(selected.some(n=>!Number.isInteger(n)||n<1||n>data.row_count)||new Set(selected).size!==selected.length)throw Error('Choose unique data-row numbers from 1 to '+data.row_count+'.');const chosen=columns.filter(c=>c.use.checked).map(c=>({name:c.name,type:c.type.value,unit:c.unit.value}));if(!chosen.length||chosen.some(c=>c.type==='number'&&!c.unit.trim()))throw Error('Choose columns and explicit units for numeric columns.');const selection={confirmed:true,sha256:data.sha256,rows:selected,columns:chosen};await request('/api/csv-selection',{data:draft.upload.data,selection});draft.selection=selection;closeSheet();newSheet();}catch(failure){problem.textContent=failure.message;}});
  add(form,problem,add(make('div','bar'),go,button('Back to information',()=>{closeSheet();newSheet();})));closeSheet();sheet('Select CSV data',form);
}
async function openProject(id) {
  try { resetPicture(); held=await request('/api/desk?id='+encodeURIComponent(id)); renderProject(); }
  catch(failure) {error(failure.message);}
}
async function download(manifest,format,view=false) {
  const route='/api/download?id='+encodeURIComponent(held.project.id)+'&export='+encodeURIComponent(manifest.id)+'&format='+format;
  const response=await fetch(route,{headers:{'X-Infographic-Studio-Token':token}});if(!response.ok)throw Error('This saved delivery could not be read.');
  const blob=await response.blob(),url=URL.createObjectURL(blob);if(view) return url;
  const link=make('a');link.href=url;link.download=(manifest.draft?'draft-':'')+'infographic.'+({text:'txt'}[format]||format);link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function renderProject() {
  const p=held.project, selected=p.stories.find(s=>s.id===p.selected_story);
  const currentDelivery=held.deliveries.find(d=>d.current), checked=held.review_checked&&p.checks.length&&p.checks.every(c=>c.status==='passed'), approved=p.approval&&checked, needsArtwork=p.scene?.art_regions?.length&&!p.scene.elements.some(e=>e.kind==='artwork');
  let next=['Find the story',()=>action('suggest')];
  if(p.stories.length)next=!selected?['Choose a story',()=>document.querySelector('#story-choice').scrollIntoView({behavior:'smooth'})]:!p.scene||needsArtwork?['Build page',compose]:!currentDelivery?['Create preview',()=>action('preview')]:approved?(!currentDelivery.approved_current?['Export files',()=>action('export',{draft:false})]:['Downloads',()=>document.querySelector('.ig-page-tools').scrollIntoView({behavior:'smooth'})]):checked?['Approve page',()=>action('approve')]:held.visual_review?.status==='passed'?['Run checks',()=>action('check')]:['Review page',()=>reviewSheet(currentDelivery)];
  heading(p.brief.title,button('Infographics',home),button(...next,true));
  const parts=[make('p','lede','Choose the explanation, review the actual page, then approve its exact revision.')];
  if(held.recovery.length) parts.push(card('Image work needs attention',...held.recovery.map(r=>add(make('div','stack'),make('p','',r.state+': '+r.message),button('Cancel uncertain request',()=>action('image-cancel',{request_id:r.attempt_id}))))));
  if(!p.stories.length)parts.push(card('Find a useful story',make('p','','Your supplied information is saved. The assistant proposes source-backed explanations; generation is a later explicit action.'),button('Find the story',()=>action('suggest')),detail('Author in your conversation',make('p','','Use native action JSON to save located facts and story proposals directly. A browser and nested planning assistant are not required.'))));
  if(p.stories.length){const choices=card('Choose the story',add(make('div','ig-story-grid'),...p.stories.map(s=>card(s.headline,storyThumbnail(s),make('p','',s.takeaway),make('p','quiet',s.rationale),list(s.blocks.map(b=>b.title+': '+b.text)),...(s.qualifications.length?[list(s.qualifications)]:[]),s.omissions.length?make('p','problem','Required omissions: '+s.omissions.join(', ')):null,button('Ask for a revision',()=>reviseStorySheet(s)),button(s.id===p.selected_story?'Selected':'Use this story',()=>action('select',{story_id:s.id}))))));choices.id='story-choice';parts.push(p.scene?detail('Story: '+selected.headline,choices):choices);}
  if(selected && !p.scene)parts.push(card('Make the page',make('p','',p.brand?'Using pinned '+p.brand.identity.name+'.':'Compose with your configured brand. Brand settings are pinned when you choose this action.'),button('Build page',compose)));
  const delivery=held.deliveries.find(d=>d.current) || held.deliveries[0];
  if(delivery) {
    const img=make('img','ig-preview');img.alt='Rendered '+(delivery.draft?'draft':'approved')+' infographic, revision '+delivery.revision;
    const scroll=add(make('div','ig-preview-scroll'),img);
    const tools=add(make('div','ig-page-tools'),button('Fit page',()=>img.classList.remove('ig-preview-actual')),button('Actual pixels',()=>img.classList.add('ig-preview-actual')));
    for(const format of ['png','pdf','svg','text'])tools.append(button('Download '+format.toUpperCase()+(delivery.draft?' draft':''),async()=>{try{await download(delivery,format);}catch(f){error(f.message);}}));
    parts.push(card(!delivery.current?'Earlier page — create a new preview':delivery.draft?'Draft page':delivery.approved_current?'Approved delivery':'Earlier approval — review the current revision',make('p','quiet','Saved revision '+delivery.revision+'. Earlier deliveries stay available through history; edits require a new review.'),scroll,tools));
    download(delivery,'png',true).then(url=>{if(held?.project.id===p.id && document.body.contains(img)){picture=url;img.src=url;}else URL.revokeObjectURL(url);}).catch(f=>error(f.message));
  }
  if(p.scene) {
    const edit=make('div','stack');for(const e of p.scene.elements.filter(e=>e.kind==='text')) {const f=field(e.id,e.text,'textarea');edit.append(add(make('div','stack'),f.wrap,button('Save '+e.id,()=>action('edit-text',{element_id:e.id,text:f.input.value}))));}
    parts.push(detail('Edit words directly',edit),detail('Layout alternatives',button('Stacked blocks',()=>action('layout',{arrangement:'stack'})),button('Two columns',()=>action('layout',{arrangement:'columns'}))));
    if(p.scene.art_regions?.length)parts.push(detail('Artwork and image brief',card('Explanatory artwork',button('Revise this artwork',reviseArtSheet),make('p','','Artwork is raster; labels and chart marks stay editable. Review the exact art direction before starting or editing an image.'),...p.assets.map(a=>button('Compose saved image '+a.id,()=>action('compose-image',{asset_id:a.id}))),button('Suggest precise art direction',()=>action('art-direct')),detail('Write the art direction yourself',button('Describe subjects and relationships',artSheet)),...p.image_briefs.map(b=>detail('Saved image brief',make('pre','ig-csv-preview',b.prompt),button('Generate artwork using selected provider',()=>startImage(b)))))));
    if(delivery?.current)parts.push(card('Review and finish',make('p','','Inspect the actual page at its intended size: facts and qualifications, objects and relationships, crop and resolution, label clearance and brand.'),button('Inspect page with assistant',()=>action('inspect-images')),button('Record my visual review',()=>reviewSheet(delivery)),button('Run checks',()=>action('check')),button('Repair findings',repairSheet),approved?button('Export approved files',()=>action('export',{draft:false})):checked?button('Approve this checked revision',()=>action('approve')):make('p','quiet','Approval becomes available when the current checks pass against the latest visual review.')));
  }
  if(held.visual_review)parts.push(detail('Visual review: '+held.visual_review.status,list(held.visual_review.observations),...held.visual_review.findings.map(f=>card(f.region_id+': '+(f.blocking?'Needs correction':'Suggestion'),make('p','',f.message),make('p','',f.correction)))));
  if(p.checks.length)parts.push(card('Checks for this page',...p.checks.map(c=>add(make('div','stack'),make('strong','',({'coverage':'Required content','facts':'Factual support','layout':'Page layout','brand-accessibility':'Brand and accessibility','visual':'Visual review'}[c.kind]||c.kind)+': '+c.status),list(c.findings || [])))));
  parts.push(detail('Brief and requirements',button('Edit brief',briefSheet),make('p','',p.brief.audience||'Audience not specified'),list(p.brief.must_show.map(r=>r.text))));
  parts.push(detail('Sources and facts',button('Add or update supplied information',sourceSheet),list(p.sources.map(s=>(s.name||s.id)+' — '+s.characters+' captured characters')),list(held.source_findings.map(f=>f.message)),...p.facts.map(f=>card(f.statement,make('p','quiet','Supplied assertion; not independently corroborated.'),list((f.evidence||[]).map(q=>q.source_id+' ['+q.start+'–'+q.end+']: '+(q.quote||'')))))));
  if(held.image_history?.length)parts.push(detail('Image requests and usage',...held.image_history.map(a=>add(make('div','stack'),make('p','',a.provider+' · '+a.operation+' · '+a.state),make('p','quiet',a.usage?'Reported tokens: '+(a.usage.input_tokens??'unknown')+' in / '+(a.usage.output_tokens??'unknown')+' out. Cost: '+(a.usage.cost??'not reported')+'.':'Usage not reported; no estimate was invented.'),button('Inspect saved image request',()=>imageRequestSheet(a.id))))));
  parts.push(detail('History',...held.history.map(v=>add(make('div','bar'),make('span','','Revision '+v.revision+(v.approved?' · approved then':'')),button('Compare with current',()=>compareSheet(v)),button('Restore revision '+v.revision,()=>restoreSheet(v)))),held.history.length>=100&&held.history.at(-1).revision>0?button('Older revisions',olderHistory):null));
  $('main').replaceChildren(...parts.filter(Boolean));
}
async function compose(){
  try {
    const capability=await request('/api/computer');
    sheet('Build this page',make('p','',capability.disclosure),make('p','','The selected story is composed with your pinned brand. If artwork helps explain the story, your assistant writes detailed art direction and the selected image provider generates it. Fonts and layout are checked first. Nothing is approved or published.'),add(make('div','bar'),button('Build page',async()=>{
      if(!held.project.brand){try{await request('/api/brand-current',{id:held.project.id,expected_revision:held.project.revision});await openProject(held.project.id);}catch(f){error(f.message);return;}}
      await action('build',{request_id:requestId()});
    },true),button('Cancel',closeSheet)));
  }catch(f){error(f.message);}
}
function artSheet(){const raw=field('Precise image direction JSON (advanced)','','textarea');raw.input.rows=12;raw.input.placeholder='style, reading_order, acceptance, objects [{id, region_id, count, description, relationships, preserve}]';const hint=make('pre','ig-csv-preview',JSON.stringify(held.project.scene.art_regions,null,2));const save=button('Save image brief',async()=>{try{await action('image-brief',{data:JSON.parse(raw.input.value)});}catch(f){error(f.message);}},true);sheet('Describe the explanatory artwork',make('p','','Specify concrete subjects, exact relationships and what must remain empty. The actual prompt is saved before any provider call.'),detail('Planned artwork regions',hint),raw.wrap,add(make('div','bar'),save,button('Cancel',closeSheet)));}
async function startImage(brief){
  try{preferences=await request('/api/preferences');const capability=await request('/api/computer');sheet('Generate artwork',make('p','',capability.disclosure),make('p','','This starts a provider request using the saved brief. Unknown outcomes are kept for explicit recovery; reopening never resubmits.'),add(make('div','bar'),button('Generate artwork',()=>action('image-start',{brief_id:brief.id,provider:preferences.image_provider,request_id:requestId()}),true),button('Cancel',closeSheet)));}catch(f){error(f.message);}
}
function reviewSheet(delivery){const observations=field('What did you inspect on the actual composed page?','','textarea');sheet('Review the actual page',button('Inspect page with assistant',()=>action('inspect-images')),make('p','','Or record your own visual review of the rendered revision. It does not claim automated or live-provider quality verification.'),observations.wrap,add(make('div','bar'),button('Record reviewed page',()=>action('review',{export_id:delivery.id,observations:lines(observations.input.value)}),true),button('Cancel',closeSheet)));}
function restoreSheet(version){sheet('Restore revision '+version.revision+'?',make('p','','Creates a new revision. Current sources, images and deliveries remain in history; approval is not restored.'),add(make('div','bar'),button('Restore as a new revision',()=>action('restore',{revision:version.revision,sha256:version.sha256}),true),button('Cancel',closeSheet)));}
async function showSettings() {
  if (busy) return;
  held = null;
  resetPicture();
  heading('Settings and capability', button('Infographics', home));
  try {
    preferences = await request('/api/preferences');
    const capability = await request('/api/computer');
    const sharedLink = make('a', 'button', 'Shared assistant and brand settings');
    sharedLink.href = '/onboarding/#token=' + encodeURIComponent(token) + '&view=settings';
    const model = field('Gemini image model', preferences.native.gemini_model || '');
    const renderer = field('Installed headless renderer path', preferences.native.renderer || '');
    renderer.input.placeholder = preferences.renderer || 'Use the renderer included in a prepared download';
    const messages = {
      'assistant-missing': 'Install the selected assistant CLI before starting assistant work.',
      'sign-in-required': 'Sign in to the selected assistant.',
      'gemini-key-required': 'Supply GEMINI_API_KEY in the server launch environment.',
      'gemini-model-required': 'Choose an image-capable Gemini model below.',
      'image-model-unavailable': 'Choose a Gemini image model available to your account.',
      'image-tool-unavailable': 'The installed Codex does not expose its image tool.',
      'manual-image-review-required': 'Use your own review of the actual page.',
      'sign-in-not-checked': 'Sign-in is checked when you explicitly start assistant work.',
      'image-tool-not-checked': 'Codex image-tool access awaits a live run.',
      'image-model-access-not-checked': 'Gemini model access awaits a live run.',
      'image-inspection-not-checked': 'Multimodal inspection awaits a live run.',
      'generation-and-editing-not-live-verified': 'Generation and reference editing await live acceptance.'
    };
    const imageDefaults = [];
    if (preferences.image_provider === 'gemini') imageDefaults.push(model.wrap);
    imageDefaults.push(detail('Advanced renderer setting', renderer.wrap),
      make('p', 'quiet', 'Defaults apply to new work. Your existing workspace and saved brand stay in place.'),
      button('Save defaults', async () => {
        try {
          const changes = {renderer: renderer.input.value};
          if (preferences.image_provider === 'gemini') changes.gemini_model = model.input.value;
          await request('/api/preferences', {expected: preferences.native_revision, changes});
          await showSettings();
          toast('Defaults saved.');
        } catch (failure) { error(failure.message); }
      }, true));
    $('main').replaceChildren(
      card('Assistant and image provider',
        make('p', '', capability.assistant + ' · ' + capability.image_provider),
        make('p', '', capability.state === 'unavailable' ? 'Finish these prerequisites before generating artwork.' : 'Local prerequisites detected; provider access remains unverified.'),
        make('p', '', capability.disclosure),
        list([...capability.problems, ...capability.unknown].map(code => messages[code] || code))),
      card('Page renderer', make('p', '', capability.renderer_available
        ? 'Installed renderer found. Preview checks actual fonts, layout, and output.'
        : 'Configure an installed renderer, or use a prepared download that includes it. No browser is downloaded here.')),
      card('Shared settings', sharedLink, make('p', 'quiet', 'Infographic Studio uses local supplied-information storage in this release. Team settings remain available to the other studios.')),
      card('Infographic defaults', ...imageDefaults));
  } catch (failure) { error(failure.message); }
}
$('home').addEventListener('click',home);$('settings').addEventListener('click',showSettings);
const port=Number(document.body.dataset.suitePort);homeLink=homeLink||(Number.isInteger(port)&&port>0&&port<65536?suiteHome(location.protocol+'//'+location.hostname+':'+port+'/'):'');if(homeLink){$('suite').hidden=false;$('suite').href=homeLink+'/';}
if(!token)error('Open Infographic Studio using the private link printed in your terminal.');else home();

function reviseArtSheet(){const change=field('What should change?','','textarea'),preserve=field('What should stay the same?','Keep all other subjects, relationships, brand, empty label regions and composition.','textarea');sheet('Revise the artwork',make('p','','This sends the saved original as a reference to your selected image provider. It uses provider allowance; the earlier artwork remains in history.'),change.wrap,preserve.wrap,add(make('div','bar'),button('Create referenced revision',()=>action('revise-art',{change:change.input.value,preserve:preserve.input.value,request_id:requestId()}),true),button('Cancel',closeSheet)));}
async function compareSheet(version){try{const result=await request('/api/action',{action:'compare',id:held.project.id,expected_revision:held.project.revision,before:version.revision,after:held.project.revision});sheet('Changes since revision '+version.revision,...Object.entries(result.result).map(([key,value])=>detail(key,make('h3','','Before'),make('pre','ig-csv-preview',JSON.stringify(value.before,null,2)),make('h3','','Current'),make('pre','ig-csv-preview',JSON.stringify(value.after,null,2)))),button('Done',closeSheet));}catch(f){error(f.message);}}
function sourceSheet(){const value=field('New or replacement supplied information','','textarea'),replacement=field('Source to replace (leave empty to add another)','','select');const empty=make('option','','Add as another source');empty.value='';replacement.input.append(empty);for(const source of held.project.sources){const option=make('option','',source.name);option.value=source.id;replacement.input.append(option);}sheet('Update supplied information',make('p','','Story, scene, checks and approval are refreshed when source content changes. Earlier work stays in history.'),value.wrap,replacement.wrap,add(make('div','bar'),button('Save supplied information',()=>action('source',{data:encoded(new TextEncoder().encode(value.input.value)),kind:'text',name:'Updated supplied information',...(replacement.input.value?{replace_id:replacement.input.value}:{})}),true),button('Cancel',closeSheet)));}

function reviseStorySheet(story){const scope=field('Scope','','select'),instruction=field('What should change?','','textarea');const all=make('option','','Whole story');all.value='';scope.input.append(all);for(const block of story.blocks){const option=make('option','',block.title);option.value=block.id;scope.input.append(option);}sheet('Refine this story',make('p','','Your selected assistant revises the supplied explanation. A named block preserves all other content. Review and choose the revised story before rebuilding.'),scope.wrap,instruction.wrap,add(make('div','bar'),button('Suggest revision',()=>action('revise-story',{story_id:story.id,block_id:scope.input.value||null,instruction:instruction.input.value}),true),button('Cancel',closeSheet)));}
function repairSheet(){sheet('Repair current findings',make('p','','Apply the recorded artwork correction, or try the other layout. Artwork correction uses your selected provider and the original as a reference. Layout and image repairs share a two-attempt budget; nothing is approved automatically.'),add(make('div','bar'),button('Apply bounded repair',()=>action('repair',{request_id:requestId()}),true),button('Cancel',closeSheet)));}

function storyThumbnail(story){const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');svg.setAttribute('viewBox','0 0 360 100');svg.setAttribute('class','ig-thumbnail');svg.setAttribute('role','img');svg.setAttribute('aria-label','Story structure: '+story.blocks.map(b=>b.title).join(', '));for(const [i,block]of story.blocks.entries()){const rect=document.createElementNS(ns,'rect');rect.setAttribute('x',String(i*360/story.blocks.length+3));rect.setAttribute('y','12');rect.setAttribute('width',String(360/story.blocks.length-6));rect.setAttribute('height','76');rect.setAttribute('rx','6');rect.setAttribute('class','ig-outline-block');svg.append(rect);const text=document.createElementNS(ns,'text');text.setAttribute('x',String(i*360/story.blocks.length+9));text.setAttribute('y','48');text.setAttribute('class','ig-outline-label');text.textContent=block.kind;svg.append(text);}return svg;}

async function imageRequestSheet(id){try{const saved=await request('/api/image-request?id='+encodeURIComponent(held.project.id)+'&request='+encodeURIComponent(id));sheet('Saved image request',make('p','',saved.provider+' · '+saved.operation),make('pre','ig-csv-preview',saved.brief.prompt),make('p','quiet','Remote cancellation and cost remain unknown unless the provider reported them.'),button('Done',closeSheet));}catch(f){error(f.message);}}
async function olderHistory(){try{const last=held.history.at(-1);const result=await request('/api/history-before?id='+encodeURIComponent(held.project.id)+'&before='+last.revision);held.history.push(...result.history);renderProject();document.querySelectorAll('details').forEach(d=>{if(d.firstChild.textContent==='History')d.open=true;});}catch(f){error(f.message);}}

function briefSheet(){const p=held.project,fields={};for(const[key,label,value]of[['title','Working title',p.brief.title],['audience','Audience',p.brief.audience],['purpose','Desired takeaway',p.brief.purpose],['must','Must-show ideas — one per line',p.brief.must_show.map(r=>r.text).join('\n')],['locked','Exact wording to preserve',p.brief.locked_words.join('\n')],['exclusions','Leave out',p.brief.exclusions.join('\n')]])fields[key]=field(label,value,['must','locked','exclusions'].includes(key)?'textarea':'input');sheet('Edit brief and requirements',make('p','','Changing the brief requires a fresh story/page review. Captured facts, earlier versions and exports are kept.'),...Object.values(fields).map(f=>f.wrap),add(make('div','bar'),button('Save brief',async()=>{try{await request('/api/project',{id:p.id,expected_revision:p.revision,brief:{...p.brief,title:fields.title.input.value,audience:fields.audience.input.value,purpose:fields.purpose.input.value,must_show:lines(fields.must.input.value).map((text,i)=>({id:p.brief.must_show[i]?.id||'r_'+requestId().slice(0,12),text})),locked_words:lines(fields.locked.input.value),exclusions:lines(fields.exclusions.input.value)}});closeSheet();await openProject(p.id);}catch(f){error(f.message);}},true),button('Cancel',closeSheet)));}
