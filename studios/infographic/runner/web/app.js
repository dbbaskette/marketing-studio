/* Infographic Studio's native editing desk. No build step, remote libraries or implicit provider calls. */
'use strict';
const {make, add} = Drafting;
const launch = new URLSearchParams(location.hash.slice(1));
let token = launch.get('token') || '';
try { if(token)sessionStorage.setItem('infographic-studio-token',token); else token=sessionStorage.getItem('infographic-studio-token')||''; }catch(f){}
function requestId(){return Array.from(crypto.getRandomValues(new Uint8Array(16)),v=>v.toString(16).padStart(2,'0')).join('');}
window.addEventListener('hashchange',()=>{const next=new URLSearchParams(location.hash.slice(1)).get('token');if(next&&next!==token)location.reload();});
function suiteHome(hash, here) {
  const named = new URLSearchParams(String(hash).replace(/^#/, '')).get('home') || '';
  const found = /^(https?:)\/\/([^/:?#@\s]+):(\d{1,5})\/?$/.exec(named);
  return found && found[1] === here.protocol && found[2] === here.hostname && found[3] !== here.port
    && Number(found[3]) > 0 && Number(found[3]) < 65536
    ? found[1] + '//' + found[2] + ':' + found[3] : '';
}
// Marketing Studio says when it opened this studio in its own tab, as it does on a phone: the
// way back then stays in this tab, where Marketing Studio still holds its key.
// The return key stays in a fragment and tab memory, bound to the validated home origin.
// A phone's network home port can differ from the native server's loopback home port.
function rememberedSuiteHome(here) {
  try {
    const saved = JSON.parse(sessionStorage.getItem('marketing-studio-return') || 'null');
    if (saved && /^[A-Za-z0-9_-]{8,256}$/.test(saved.token || '')
        && suiteHome('#home=' + encodeURIComponent(saved.home), here) === saved.home) return saved.home;
  } catch (failure) {}
  return '';
}
function suiteReturn(home, hash, here) {
  if (!home || suiteHome('#home=' + encodeURIComponent(home), here) !== home) return '';
  const offered = suiteHome(hash, here) === home
    ? new URLSearchParams(String(hash).replace(/^#/, '')).get('homeToken') || '' : '';
  const valid = value => typeof value === 'string' && /^[A-Za-z0-9_-]{8,256}$/.test(value);
  let key = valid(offered) ? offered : '';
  try {
    const saved = JSON.parse(sessionStorage.getItem('marketing-studio-return') || 'null');
    if (!key && saved?.home === home && valid(saved.token)) key = saved.token;
    if (key) sessionStorage.setItem('marketing-studio-return', JSON.stringify({home, token: key}));
  } catch (failure) {
    // The current private link still works when tab storage is unavailable.
  }
  return home + '/' + (key ? '#token=' + encodeURIComponent(key) : '');
}
function suitePort(port, here) {
  return /^[1-9][0-9]{0,4}$/.test(String(port || ''))
    ? suiteHome('#home=' + encodeURIComponent(here.protocol + '//' + here.hostname + ':' + port), here) : '';
}
function suiteBack(hash) {
  return new URLSearchParams(String(hash).replace(/^#/, '')).get('back') === 'tab';
}
const launchHash = '#' + launch.toString();
let homeLink = suiteHome(launchHash, location) || rememberedSuiteHome(location) || suitePort(document.body?.dataset?.suitePort, location);
let sameTab = suiteBack(launchHash);
try {
  homeLink = homeLink || suiteHome('#home=' + encodeURIComponent(sessionStorage.getItem('infographic-studio-home') || ''), location);
  if (homeLink) sessionStorage.setItem('infographic-studio-home', homeLink);
  if (launch.has('home')) sessionStorage.setItem('marketing-studio-back', sameTab ? 'tab' : 'window');
  else sameTab = sessionStorage.getItem('marketing-studio-back') === 'tab';
} catch (failure) {}
if(location.hash)history.replaceState(null,'',location.pathname);
const $ = id => document.getElementById(id);
let held = null, busy = false, picture = null, preferences = null;
const draft = {research_first:false, materials: [], library: [], imported: [], step: 0, title: '', text: '', direction: 'suggest', audience: '', purpose: '', must: '', locked: '', exclusions: '', preset: 'a4'};
const error = message => { $('notice').textContent = message; $('notice').hidden = !message; for(const node of document.querySelectorAll('[data-work-error]')){node.textContent=$('sheet').open?message:'';node.hidden=!message||!$('sheet').open;} };
const toast = message => { const p = make('p', 'toast', message); $('toasts').replaceChildren(p); };
function button(label, action, primary=false) { const node = make('button', 'button' + (primary ? ' button-filled' : ''), label); node.type = 'button'; node.addEventListener('click', action); return node; }
function card(title, ...parts) { return add(make('section', 'card stack'), make('h2', 'card-title', title), ...parts); }
function detail(title, ...parts) { return add(make('details'), make('summary', '', title), ...parts); }
let fieldNumber = 0;
function field(label, value='', kind='input') { const wrap = make('label', 'field'); const input = make(kind, 'input'); input.value = value; const caption=make('span','field-label',label);caption.id='field-caption-'+(++fieldNumber);input.id='field-'+fieldNumber;wrap.htmlFor=input.id;input.setAttribute('aria-labelledby',caption.id);add(wrap, caption, input); return {wrap, input}; }
function stateLine(kind,words){const bead=make('span','bead');bead.dataset.state=kind;bead.setAttribute('aria-hidden','true');return add(make('p','state'),bead,document.createTextNode(words));}
function lines(value) { return value.split('\n').map(v => v.trim()).filter(Boolean); }
function list(items) { return add(make('ul'), ...items.map(item => make('li', '', item))); }
function sheet(title, ...nodes) { $('sheet-body').replaceChildren(add(make('div', 'ig-sheet stack'), make('h2', 'sheet-title', title))); $('sheet-body').firstChild.firstChild.id = 'sheet-title'; const status=make('section','callout ig-work');status.dataset.workStatus='';status.setAttribute('role','status');status.setAttribute('aria-live','polite');const problem=make('p','problem');problem.dataset.workError='';problem.hidden=true;problem.setAttribute('role','alert');$('sheet-body').firstChild.append(status,problem,...nodes); if (!$('sheet').open) $('sheet').showModal(); paintWork(); }
function closeSheet() { $('sheet').close(); paintWork(); }
let work = null, workTimer = null;
const workLabels = {'suggest':'Finding the story','build':'Building the page','art-direct':'Writing the art direction','image-start':'Generating artwork','inspect-images':'Inspecting the page','revise-story':'Revising the story','revise-art':'Revising the artwork','repair':'Repairing the page','preview':'Rendering the preview','export':'Preparing your files','google-deliver':'Delivering the Google Doc'};
workLabels['image-recover']='Recovering saved artwork locally';
workLabels['visual-layout']='Building the visual diagram layout';
workLabels['approve']='Approving and preparing your files';
workLabels['review']='Recording your review and running checks';
function paintWork() {
  $('main').setAttribute('aria-busy',String(!!work));
  for(const surface of document.querySelectorAll('[data-work-status]')) {
    const inSheet=$('sheet').contains(surface),show=!!work&&(!$('sheet').open||inSheet);
    surface.hidden=!show;if(!show)continue;
    const signature=work.label+'|'+work.detail+'|'+(work.pending||'');
    if(surface.dataset.message!==signature) {
      surface.dataset.message=signature;
      const bead=make('span','bead');bead.dataset.state=work.connected?'current':'review';bead.setAttribute('aria-hidden','true');
      const clock=make('span','quiet ig-work-clock');clock.dataset.workClock='';clock.setAttribute('aria-hidden','true');
      surface.replaceChildren(add(make('div','ig-work-heading'),bead,make('strong','',work.label),clock),make('p','quiet',work.detail));
      if(work.cancel)surface.append(button('Cancel this request',work.cancel));
    }
    const seconds=Math.max(0,Math.floor((Date.now()-work.started)/1000));
    surface.querySelector('[data-work-clock]').textContent=Math.floor(seconds/60)+':'+String(seconds%60).padStart(2,'0')+' elapsed';
  }
}
function beginWork(label, elapsed=0) {
  clearInterval(workTimer);
  $('toasts').replaceChildren();
  work={label,started:Date.now()-elapsed*1000,connected:true,detail:'This can take a few minutes. Your saved work is kept.'};
  workTimer=setInterval(paintWork,1000);paintWork();return work;
}
function endWork(owner) { if(work===owner){clearInterval(workTimer);workTimer=null;work=null;paintWork();} }
function connectionUncertain(owner) { if(work===owner){owner.connected=false;owner.label='Checking the connection';owner.detail='The connection was interrupted. Work may still be running on this computer. No request was repeated.';paintWork();} }
function lockControls() {
  const controls=[...document.querySelectorAll('button')].map(node=>[node,node.disabled]);controls.forEach(([node])=>node.disabled=true);
  return ()=>controls.forEach(([node,disabled])=>node.disabled=disabled);
}
function progressNotice(progress,owner,id) {
  if(work!==owner)return;
  const current=progress.activity;
  if(work===owner&&current?.state==='running'){owner.label=current.label;owner.started=Date.now()-current.elapsed_seconds*1000;owner.connected=true;owner.detail='Working on this computer. This can take a few minutes. Your saved work is kept.';paintWork();}
  const pending=progress.recovery?.find(r=>!r.local_artwork_available&&['queued','running','unknown'].includes(r.state));
  if(pending&&owner.pending!==pending.attempt_id){owner.pending=pending.attempt_id;
    owner.cancel=async()=>{try{const latest=await request('/api/activity?id='+encodeURIComponent(id));await request('/api/action',{action:'image-cancel',id,expected_revision:latest.revision,request_id:pending.attempt_id});toast('Local adoption cancelled. Remote charges may remain unknown.');}catch(f){error(f.message);}};
    paintWork();
  }
}
async function recoverActivity(id,owner) {
  let failures=0;
  for(;;){
    try{const progress=await request('/api/activity?id='+encodeURIComponent(id));failures=0;progressNotice(progress,owner,id);
      if(progress.activity?.state!=='running')return progress.activity;
    }catch(f){connectionUncertain(owner);if(++failures>=5)throw Error('The connection could not be restored. Work may still be running. Reopen this infographic to check before retrying.');}
    await new Promise(resolve=>setTimeout(resolve,2000));
  }
}
function recoveredNotice(result) {
  if(result?.state==='complete')toast('Finished. Your saved work is ready to review.');
  else if(result?.state==='outdated')toast('The earlier result was kept and did not replace newer work.');
  else error(result?.state==='failed'?(result.problem||'The operation could not finish. Your saved work is kept.'):result?.state==='cancelled'?'The image request was cancelled. Remote charges may remain unknown.':'The earlier outcome could not be confirmed. Check the saved work and recovery controls before retrying.');
}
async function resumeActivity(id,current) {
  busy=true;const unlock=lockControls(),owner=beginWork(current.label,current.elapsed_seconds);
  try{const result=await recoverActivity(id,owner);await openProject(id);recoveredNotice(result);
  }catch(f){error(f.message);}finally{endWork(owner);busy=false;unlock();}
}
async function request(route, data) {
  const labels={'/api/remote-preview':'Reading the linked document','/api/source-preview':'Reading the uploaded file','/api/research-preview':'Reading the selected research'};
  const owner=!work&&data!==undefined&&labels[route]?beginWork(labels[route]):null;
  try{const response = await fetch(route, {method: data === undefined ? 'GET' : 'POST', headers: {'X-Infographic-Studio-Token': token, ...(data === undefined ? {} : {'Content-Type': 'application/json'})}, ...(data === undefined ? {} : {body: JSON.stringify(data)})});
    const answer = await response.json(); if (!response.ok){const failure=Error(answer.error || 'This request could not be completed.');failure.status=response.status;throw failure;}return answer;
  }finally{if(owner)endWork(owner);}
}
// Normalized image outcomes. Each says what happened and the next safe step; nothing is retried.
const imageProblems={
  'image-tool-unavailable':'The image worker finished without handing back a usable image. Your installed Codex may not offer its image tool here. Check Image work needs attention for local recovery.',
  'sign-in-required':'Sign in to your selected assistant on this computer, then start the image request again. Your earlier work is kept.',
  'quota':'The image provider reported a usage or rate limit. Your earlier work is kept. Try again when your allowance resets.',
  'invalid-asset':'The returned image was not a usable PNG, so it was not added. Your earlier work is kept.',
  'gemini-key-required':'Set GEMINI_API_KEY in the server launch environment before starting image work.',
  'image-model-unavailable':'Choose a Gemini image model available to your account in Settings.'
};
async function action(verb, values={}, revision=null, options={}) {
  if (busy) return; busy = true; error(''); const id = held.project.id;
  const label=verb==='suggest'&&held.planning_response?.available&&!values.fresh?'Checking the saved proposal':workLabels[verb];
  const unlock=lockControls(),owner=beginWork(label||'Saving your changes');
  let checking=false;
  const polling=setInterval(async()=>{if(checking)return;checking=true;try{progressNotice(await request('/api/activity?id='+encodeURIComponent(id)),owner,id);}catch(f){connectionUncertain(owner);}finally{checking=false;}},2000);
  try {
    const answer = await request('/api/action', {action:verb, id, expected_revision:revision??held.project.revision, ...values});
    closeSheet(); await openProject(id); if(options.quiet)return answer.result; if(answer.result?.state==='unknown')error('The image worker did not confirm completion. Check Image work needs attention for saved artwork or cancellation. No request was repeated.'); else if(answer.result?.state==='failed')error(imageProblems[answer.result.reason]||'The image provider could not finish. Your earlier work is kept.'); else if(answer.result?.state==='outdated')toast('The earlier result was kept privately and did not replace newer work.');else toast('Saved.'); return answer.result;
  } catch (failure) {
    if(workLabels[verb]&&(!failure.status||failure.status>=500)){
      clearInterval(polling);connectionUncertain(owner);
      try{const result=await recoverActivity(id,owner);await openProject(id);if(result)recoveredNotice(result);else error(failure.message);}catch(f){error(f.message);}
    }else{await openProject(id);error(failure.message);}
  }
  finally { clearInterval(polling); endWork(owner);busy = false;unlock(); }
}
function heading(title, ...actions) { for(const id of ['home','settings']){if((id==='settings')===title.startsWith('Settings'))$(id).setAttribute('aria-current','page');else $(id).removeAttribute('aria-current');} $('title').textContent = title; $('actions').replaceChildren(...actions); $('title').focus({preventScroll:true}); }
function resetPicture() { if (picture) URL.revokeObjectURL(picture); picture = null; pictureFor = ''; }
function reviewCapturedSources(){
  const section=[...$('main').querySelectorAll('details')].find(node=>node.firstElementChild?.textContent==='Sources and facts');
  if(section){error('');section.open=true;section.scrollIntoView({block:'start'});section.firstElementChild.focus();}
}
async function home() {
  if (busy) return; resetPicture(); held = null; error(''); heading('Infographics', button('New infographic', () => newSheet(), true),button('Team library',teamSheet));
  try {
    const data = await request('/api/projects');
    const cards = data.projects.map(p => {
      const node=card(p.title || 'Unreadable infographic', ...(p.problem?[make('p','problem',p.problem)]:[stateLine(p.readiness?.state||'current',p.readiness?.summary||'Saved'),make('p','quiet','Revision '+p.revision)]), button('Open ' + (p.title || p.id), () => openProject(p.id)));
      node.classList.add('ig-project-card'); return node;
    });
    const intro=add(make('div','intro'),make('h2','large-title','Your infographics'),make('p','lede','Turn supplied information into one clear page.'));
    $('main').replaceChildren(intro, add(make('div','ig-project-list'),...cards));
    if (!cards.length) $('main').append(card('Make your first infographic', make('p','','Add notes, choose what matters, and review the page before exporting.')));
  } catch (failure) { error(failure.message); }
}
async function bytes(file) { if (file.size > 16_000_000) throw Error('Choose a source no larger than 16 MB.'); return new Uint8Array(await file.arrayBuffer()); }
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
    const upload = field('Upload files — text, Markdown, CSV, PDF, Word or HTML');
    upload.input.type = 'file'; upload.input.accept = '.txt,.md,.csv,.pdf,application/pdf,.docx,.html,.htm'; upload.input.multiple = true;
    upload.input.addEventListener('change', async () => {
      problem.textContent = '';
      try {
        const files = [...upload.input.files];
        if (!files.length) return;
        if (files.length > 12 || files.reduce((n,f) => n + f.size, 0) > 64_000_000) throw Error('Choose at most 12 files and 64 MB in one selection.');
        if (files.some(f => f.name.toLowerCase().endsWith('.csv')) && files.length !== 1) throw Error('Add a CSV on its own so you can confirm its rows, columns and units.');
        const prepared = [];
        for (const file of files) {
          const raw = await bytes(file), suffix = file.name.toLowerCase().split('.').pop();
          const kinds = {txt:'text', md:'markdown', csv:'csv', pdf:'pdf', docx:'docx', html:'html', htm:'html'};
          if (!kinds[suffix]) throw Error('Choose text, Markdown, CSV, PDF, Word (.docx) or HTML.');
          if (suffix === 'csv') {
            new TextDecoder('utf-8',{fatal:true}).decode(raw);
            draft.upload = {data:encoded(raw),kind:'csv',name:file.name}; draft.selection = null;
            draft.csv = await request('/api/csv-preview',{data:draft.upload.data}); csvSheet(); return;
          }
          const preview = await request('/api/source-preview',{data:encoded(raw),kind:kinds[suffix],name:file.name});
          prepared.push({preview, acknowledged:false});
        }
        draft.materials.push(...prepared);
        closeSheet(); await newSheet();
      } catch (failure) { problem.textContent = failure.message; }
    });
    add(form,upload.wrap,make('p','quiet',draft.upload?'Selected: '+draft.upload.name:'Files are read locally. No OCR, linked-resource fetch or assistant work starts during this preview.'));
    const researchFirst=make('input');researchFirst.type='checkbox';researchFirst.checked=!!draft.research_first;researchFirst.addEventListener('change',()=>{draft.research_first=researchFirst.checked;});
    form.append(add(make('label','check'),researchFirst,document.createTextNode('Research this topic first')),make('p','quiet','You can save a topic and brief without source material, then choose references and optional external search.'));
    form.append(button('Import selected studio material',()=>handoffSheet(preview=>{draft.materials.push({preview,acknowledged:false});newSheet();})));
    const fromLibrary=button('Add from library',()=>libraryPick(draftLibrary).then(done=>{if(done){closeSheet();newSheet();}}));fromLibrary.dataset.key='ig-new-library';form.append(fromLibrary);
    for(const chosen of draft.library){
      const kept=card(chosen.title,make('p','quiet','From the Document Library, revision '+chosen.revision+' · '+chosen.characters+' readable characters. It becomes a source when you save the brief.'),list(chosen.gaps));
      if(chosen.gaps.length){const ack=make('input');ack.type='checkbox';ack.checked=chosen.acknowledged;ack.addEventListener('change',()=>{chosen.acknowledged=ack.checked;});kept.append(add(make('label','check'),ack,document.createTextNode('I reviewed these gaps. Use only the readable text.')));}
      kept.append(button('Remove '+chosen.title,()=>{draft.library=draft.library.filter(one=>one!==chosen);closeSheet();newSheet();}));
      form.append(kept);
    }
    form.append(button('Add a Google Doc, Slides or public page',()=>remoteSheet(preview=>{draft.materials.push({preview,acknowledged:false});newSheet();})));
    if(draft.upload)form.append(button('Remove selected CSV',()=>{draft.upload=null;draft.csv=null;draft.selection=null;newSheet();}));
    for (const material of draft.materials) {
      const preview = material.preview;
      const coverage = card(preview.name,make('p','quiet',preview.characters+' readable characters · '+preview.locations.length+' located parts'),
        detail('Preview readable text',make('pre','ig-csv-preview',preview.excerpt)),list(preview.warnings));
      if (!preview.readable) coverage.append(make('p','problem','No readable text was found. Remove this file and supply an accessible text or Word version.'));
      if (preview.warnings.length && preview.readable) {
        const ack = make('input'); ack.type = 'checkbox'; ack.checked = material.acknowledged;
        ack.addEventListener('change',()=>{material.acknowledged=ack.checked;});
        coverage.append(add(make('label','check'),ack,document.createTextNode('I reviewed these gaps. Use only the readable text.')));
      }
      coverage.append(button('Remove '+preview.name,()=>{draft.materials=draft.materials.filter(m=>m!==material);closeSheet();newSheet();}));
      form.append(coverage);
    }
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
    if(draft.step===0 && (!draft.title.trim() || (!draft.research_first && !draft.text.trim() && !draft.upload && !draft.materials.length && !draft.library.length))) {problem.textContent='Give a title and some usable information.';return;}
    if(draft.materials.some(m=>!m.preview.readable || (m.preview.warnings.length&&!m.acknowledged)) || draft.library.some(one=>one.gaps.length&&!one.acknowledged)) {problem.textContent='Review the file previews and acknowledge readable-only coverage, or remove unreadable files.';return;}
    if(draft.step===0 && draft.materials.reduce((n,m)=>n+m.preview.characters, draft.library.reduce((n,one)=>n+one.characters,draft.text.length))>120000){problem.textContent='Choose smaller files or explicit excerpts within 120,000 readable characters for one story-planning job. Nothing was sent to an assistant.';return;}
    if(draft.upload?.kind==='csv' && !draft.selection) {problem.textContent='Preview and confirm the CSV selection first.';return;}
    if(draft.step<2) {draft.step++;closeSheet();newSheet();return;}
    go.disabled=true;
    try { let p=draft.created;
      if(!p) {draft.request_id=draft.request_id||requestId();p=(await request('/api/projects',{title:draft.title,preset:draft.preset,direction:draft.direction,request_id:draft.request_id})).project;draft.created=p;}
      p=(await request('/api/project',{id:p.id,expected_revision:p.revision,brief:{...p.brief,title:draft.title,preset:draft.preset,direction:draft.direction,audience:draft.audience,purpose:draft.purpose,must_show:lines(draft.must).map((text,i)=>({id:'r'+i,text})),locked_words:lines(draft.locked),exclusions:lines(draft.exclusions)}})).project;draft.created=p;
      for (const material of draft.materials) {
        if (draft.imported.includes(material.preview.id)) continue;
        p=(await request('/api/action',{action:'source-import',id:p.id,expected_revision:p.revision,capture_id:material.preview.id,acknowledge_warnings:material.acknowledged})).result;
        draft.created=p; draft.imported.push(material.preview.id);
      }
      if (draft.library.length && !draft.library_added) {
        p=(await request('/api/action',{action:'library',id:p.id,expected_revision:p.revision,picks:draft.library.map(({id,revision})=>({id,revision})),acknowledge_warnings:draft.library.some(one=>one.gaps.length)})).result;
        draft.created=p; draft.library_added=true;
      }
      if (draft.upload) {
        p=(await request('/api/action',{action:'source',id:p.id,expected_revision:p.revision,...draft.upload,selection:draft.selection})).result;
        draft.created=p;
      }
      if (draft.text.trim() && draft.notes_text !== draft.text) {
        p=(await request('/api/action',{action:'source',id:p.id,expected_revision:p.revision,data:encoded(new TextEncoder().encode(draft.text)),kind:'text',name:'Pasted notes',...(draft.notes_source?{replace_id:draft.notes_source}:{})})).result;
        draft.created=p; draft.notes_text=draft.text; draft.notes_source=p.sources.find(source=>source.name==='Pasted notes').id;
      }
      const researchFirst=draft.research_first;
      closeSheet();Object.assign(draft,{research_first:false, materials:[],library:[],library_added:false,imported:[],notes_text:null,notes_source:null,step:0,request_id:null,created:null,upload:null,selection:null,csv:null,title:'',text:'',direction:'suggest',audience:'',purpose:'',must:'',locked:'',exclusions:'',preset:'a4'});await openProject(p.id);if(researchFirst)await researchSheet();else toast('Brief saved. Choose Find the story when you are ready to use your assistant.');
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
  try { if(held?.project.id!==id)resetPicture(); held=await request('/api/desk?id='+encodeURIComponent(id)); renderProject();
    try{sessionStorage.setItem('infographic-studio-project',id);}catch(f){}
    if(!busy&&held.activity?.state==='running')void resumeActivity(id,held.activity);
    else if(!busy&&held.activity?.state==='failed'&&held.activity.problem)error(held.activity.problem);
  }
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
  const nativeReady=selected&&selected.blocks.every(b=>b.visual||b.kind==='numbers'||b.quantitative===true||(b.quantitative!==false&&b.fact_ids.every(id=>typeof p.facts.find(f=>f.id===id)?.value==='number'))||(b.fact_ids.length<=4&&b.fact_ids.every(id=>(p.facts.find(f=>f.id===id)?.statement||'').split(/\s+/).length<=8)));
  const currentDelivery=held.deliveries.find(d=>d.current), checked=held.review_checked&&p.checks.length&&p.checks.every(c=>c.status==='passed'), approved=p.approval&&checked, needsArtwork=p.scene?.art_regions?.length&&!p.scene.elements.some(e=>e.kind==='artwork');
  const savedPlan=held.planning_response?.available;
  const stage=held.roadmap?.stage, approvedFiles=held.deliveries.find(d=>d.approved_current);
  let next={
    story:[savedPlan?'Check saved proposal':'Find the story',()=>action('suggest')],
    choose:['Choose a story',()=>document.querySelector('#story-choice').scrollIntoView({behavior:'smooth'})],
    build:['Build page',compose],
    preview:[held.deliveries.length?'Update preview':'Create preview',()=>action('preview')],
    review:['Review page',()=>reviewSheet(currentDelivery)],
    check:['Run checks',()=>action('check')],
    approve:['Approve revision '+p.revision,approveRevision],
    export:['Prepare approved files',()=>action('export',{draft:false})],
    deliver:['Deliver or download',()=>approvedFiles&&deliverySheet(approvedFiles)]
  }[stage]||[savedPlan?'Check saved proposal':'Find the story',()=>action('suggest')];
  if(p.scene&&needsArtwork)next=['Build page',compose];
  if(selected&&!nativeReady&&(!p.scene||!p.scene.visual_version))next=['Make this story visual',()=>reviseStorySheet(selected,true)];
  else if(selected&&p.scene&&!p.scene.visual_version)next=['Rebuild visual layout',()=>action('visual-layout')];
  const recoverable=held.recovery.find(r=>r.local_artwork_available);
  if(recoverable)next=['Recover saved artwork',()=>action('image-recover',{request_id:recoverable.attempt_id})];
  heading(p.brief.title,button('Infographics',home),button(...next,true));
  const parts=[make('p','lede','Choose the explanation, review the actual page, then approve its exact revision.'),roadmapView(held.roadmap)];
  if(held.recovery.length) parts.push(card('Image work needs attention',...held.recovery.map(r=>add(make('div','stack'),make('p','',r.message),r.local_artwork_available?button('Recover saved artwork',()=>action('image-recover',{request_id:r.attempt_id}),true):button('Cancel uncertain request',()=>action('image-cancel',{request_id:r.attempt_id}))))));
  if(selected&&((p.scene&&!p.scene.visual_version)||!nativeReady)){
    parts.push(card('Make this a visual infographic',make('p','','Earlier versions and captured facts are kept. A visual plan uses concise labels, diagrams and comparisons rather than paragraph blocks.'),
      button('Make this story visual',()=>reviseStorySheet(selected,true),true),
      nativeReady?button('Rebuild visual layout',()=>action('visual-layout')):make('p','quiet','This older plan uses sentence-length labels. Make a visual plan first so the diagrams remain readable.')));
  }
  if(!p.stories.length)parts.push(savedPlan?card('Planning response saved',make('p','','Check the saved response locally, without using assistant allowance. Asking for a new plan starts a new assistant request.'),held.planning_response.detail?detail('What needs attention',make('p','',held.planning_response.detail)):null,button('Check saved proposal',()=>action('suggest')),button('Review source material',reviewCapturedSources),button('Ask for a new plan',()=>action('suggest',{fresh:true}))):card('Find a useful story',make('p','','Your supplied information is saved. The assistant proposes source-backed explanations; generation is a later explicit action.'),button('Find the story',()=>action('suggest')),detail('Author in your conversation',make('p','','Use native action JSON to save located facts and story proposals directly. A browser and nested planning assistant are not required.'))));
  if(held.planning_response?.problem)parts.push(card('Saved planning response needs attention',make('p','problem',held.planning_response.problem)));
  if(p.stories.length){
    const stories=p.stories.map(s=>card(s.headline,storyThumbnail(s),make('p','',s.takeaway),make('p','quiet',s.rationale),list(s.blocks.map(b=>b.title+': '+b.text)),...(s.qualifications.length?[list(s.qualifications)]:[]),s.omissions.length?make('p','problem','Required omissions: '+s.omissions.join(', ')):null,add(make('div','bar'),button('Ask for a revision',()=>reviseStorySheet(s)),button(s.id===p.selected_story?'Selected':'Use this story',()=>action('select',{story_id:s.id}),true))));
    const choices=add(make('section','stack'),make('h2','card-title','Choose the story'),add(make('div','ig-story-grid'),...stories));
    choices.id='story-choice';parts.push(p.scene?detail('Story: '+selected.headline,choices):choices);
  }
  if(selected && !p.scene)parts.push(card('Make the page',make('p','',p.brand?'Using pinned '+p.brand.identity.name+'.':'Compose with your configured brand. Brand settings are pinned when you choose this action.'),button('Build page',compose)));
  const delivery=held.deliveries.find(d=>d.current) || held.deliveries[0];
  if(delivery||p.scene)parts.push(workbench(p,delivery));
  if(p.scene) {
    parts.push(detail('Layout alternatives',button('Visual infographic',()=>nativeReady?action('visual-layout'):reviseStorySheet(selected,true)),button('Stacked blocks',()=>action('layout',{arrangement:'stack'})),button('Two columns',()=>action('layout',{arrangement:'columns'}))));
    if(p.scene.art_regions?.length)parts.push(detail('Artwork and image brief',card('Explanatory artwork',button('Revise this artwork',reviseArtSheet),make('p','','Artwork is raster; labels and chart marks stay editable. Review the exact art direction before starting or editing an image.'),...p.assets.map(a=>button('Compose saved image '+a.id,()=>action('compose-image',{asset_id:a.id}))),button('Suggest precise art direction',()=>action('art-direct')),detail('Write the art direction yourself',button('Describe subjects and relationships',artSheet)),...p.image_briefs.map(b=>detail('Saved image brief',make('pre','ig-csv-preview',b.prompt),button('Generate artwork using selected provider',()=>startImage(b)))))));
    if(delivery?.current)parts.push(finishCard(p,delivery,checked,approved));
  }
  for(const sent of held.google_deliveries||[])parts.push(card((sent.current?'Google delivery':'Earlier Google delivery')+' · revision '+sent.revision,sent.url?googleLink(sent.url,'Open delivered Google Doc'):make('p','quiet','Outcome uncertain. Read-only reconciliation checks for the saved request; it never resends.'),sent.url?null:button('Reconcile Google delivery',()=>action('google-deliver',{export_id:sent.export_id,request_id:sent.request_id,account:sent.account,folder:sent.folder,reconcile:true},sent.revision))));
  if(held.visual_review)parts.push(detail('Visual review: '+held.visual_review.status,list(held.visual_review.observations),...held.visual_review.findings.map(f=>card(f.region_id+': '+(f.blocking?'Needs correction':'Suggestion'),make('p','',f.message),make('p','',f.correction)))));
  if(p.checks.length)parts.push(card('Checks for this page',...p.checks.map(c=>add(make('div','stack'),make('strong','',({'coverage':'Required content','facts':'Factual support','layout':'Page layout','brand-accessibility':'Brand and accessibility','visual':'Visual review'}[c.kind]||c.kind)+': '+c.status),list(c.findings || [])))));
  parts.push(detail('Brief and requirements',button('Edit brief',briefSheet),make('p','',p.brief.audience||'Audience not specified'),list(p.brief.must_show.map(r=>r.text))));
  parts.push(detail('Sources and facts',button('Add or update supplied information',sourceSheet),button('Import selected studio material',()=>handoffSheet(preview=>sourceImportSheet(preview))),libraryAddButton(),make('p','quiet',LIBRARY_CLEARS),button('Research this topic',researchSheet),...p.sources.map(s=>card(s.name||s.id,make('p','quiet',s.characters+' captured characters'),...libraryNote(s),button('Review '+(s.name||s.id),()=>sourceTextSheet(s)))),list(held.source_findings.map(f=>f.message)),...p.facts.map(f=>card(f.statement,make('p','quiet','Supplied assertion; not independently corroborated.'),list((f.evidence||[]).map(q=>q.source_id+' ['+q.start+'–'+q.end+']: '+(q.quote||'')))))));
  if(held.image_history?.length)parts.push(detail('Image requests and usage',...held.image_history.map(a=>add(make('div','stack'),make('p','',a.provider+' · '+a.operation+' · '+a.state),make('p','quiet',a.usage?'Reported tokens: '+(a.usage.input_tokens??'unknown')+' in / '+(a.usage.output_tokens??'unknown')+' out. Cost: '+(a.usage.cost??'not reported')+'.':'Usage not reported; no estimate was invented.'),button('Inspect saved image request',()=>imageRequestSheet(a.id))))));
  if(held.deliveries.length)parts.push(detail('Saved files',make('p','quiet','Every rendered revision keeps its files. Approved files never change; an edit makes a new draft.'),...held.deliveries.map(savedFiles)));
  parts.push(detail('History',make('p','quiet','Each saved revision is kept. Restoring makes new work and never brings back an approval.'),add(make('div','desk-versions'),...held.history.map((v,i)=>historyEntry(v,i===0))),held.history.length>=100&&held.history.at(-1).revision>0?button('Older revisions',olderHistory):null));
  $('main').replaceChildren(...parts.filter(Boolean));
  restoreBench();
}
// The visual editor keeps its place across saves, reloads and other actions in this tab:
// the selected element, unsaved words for each element, and the last saved confirmation.
let bench={project:'',element:'',drafts:{},saved:null,failed:'',unchanged:false,focus:false,scroll:null};
// Every infographic's unsaved words and selected element, by project then element.
let benchStore={drafts:{},elements:{}};
try{const kept=JSON.parse(sessionStorage.getItem('infographic-studio-bench')||'null');
  if(kept&&typeof kept==='object'&&kept.drafts&&typeof kept.drafts==='object'&&!Array.isArray(kept.drafts))benchStore={drafts:kept.drafts,elements:kept.elements&&typeof kept.elements==='object'?kept.elements:{}};}catch(f){}
function keepBench(){
  if(bench.project){benchStore.elements[bench.project]=bench.element;if(Object.keys(bench.drafts).length)benchStore.drafts[bench.project]=bench.drafts;else delete benchStore.drafts[bench.project];}
  try{sessionStorage.setItem('infographic-studio-bench',JSON.stringify(benchStore));}catch(f){}
}
function unsavedFor(id){return Object.keys(benchStore.drafts[id]||{}).length>0;}
function when(value){const date=value?new Date(value):null;return date&&!isNaN(date)?date.toLocaleString([], {dateStyle:'medium',timeStyle:'short'}):'';}
function ledgerItem(name,words,state,detail){
  const bead=make('span','bead');bead.dataset.state=state;bead.setAttribute('aria-hidden','true');
  return add(make('div','ig-ledger-item'),make('span','quiet',name),add(make('strong','state'),bead,document.createTextNode(words)),detail?make('span','quiet ig-ledger-detail',detail):null);
}
function workbench(p,delivery){
  if(bench.project!==p.id){keepBench();bench={project:p.id,element:String(benchStore.elements[p.id]||''),drafts:{...(benchStore.drafts[p.id]||{})},saved:null,failed:'',unchanged:false,focus:false,scroll:null};}
  const names=held.elements||[];
  const approvedFiles=held.deliveries.find(d=>!d.draft);
  const ledger=add(make('div','ig-ledger'),
    ledgerItem('Current work','Revision '+p.revision,'current',held.readiness?.summary),
    ledgerItem('Preview',delivery?'Revision '+delivery.revision:'Not rendered yet',delivery?.current?'done':'review',delivery?(delivery.current?(delivery.revision===p.revision?'Shows your current work.':'Shows your current content; later revisions only recorded checks or approval.'):'Outdated: it does not show your latest changes.'):'Create a preview to see the page.'),
    ledgerItem('Approved delivery',approvedFiles?'Revision '+approvedFiles.revision:'None yet',approvedFiles?.approved_current?'done':'review',approvedFiles?(approvedFiles.approved_current?'Matches your current work.':'Earlier files, kept unchanged.'):'Approve a checked revision to deliver it.'));
  ledger.setAttribute('aria-label','Revisions');ledger.setAttribute('role','group');
  const view=make('section','card stack ig-view');view.append(make('h2','card-title',!delivery?'Page preview':!delivery.current?'Earlier preview: update it to see your changes':delivery.draft&&p.approval?'Approved revision '+p.revision+': prepare its files':delivery.draft?'Draft page':delivery.approved_current?'Approved delivery':'Earlier approval: review the current revision'));
  const mark=make('div','ig-mark');mark.hidden=true;mark.setAttribute('aria-hidden','true');
  let img=null,figure=null;
  if(delivery){
    img=make('img','ig-preview');img.alt='Rendered '+(delivery.draft?'draft':'approved')+' infographic, revision '+delivery.revision;
    if(p.scene){img.width=Math.round(p.scene.width);img.height=Math.round(p.scene.height);}
    figure=add(make('div','ig-figure'),img,mark);
    const scroll=add(make('div','ig-preview-scroll'),figure);
    const fit=button('Fit page',()=>zoom(false)),actual=button('Actual pixels',()=>zoom(true));
    function zoom(original){img.classList.toggle('ig-preview-actual',original);figure.classList.toggle('ig-actual',original);fit.setAttribute('aria-pressed',String(!original));actual.setAttribute('aria-pressed',String(original));}
    zoom(false);
    const tools=add(make('div','ig-page-tools'),fit,actual);
    for(const format of ['png','pdf','svg','text'])tools.append(button('Download '+format.toUpperCase()+(delivery.draft?' draft':''),async()=>{try{await download(delivery,format);}catch(f){error(f.message);}}));
    if(delivery.approved_current)tools.append(button('Deliver Google Doc or PDF',()=>deliverySheet(delivery)),button('Share selected files with team',()=>shareSheet(delivery)));
    const kept=delivery.approved_current?keptPart(delivery):null;
    view.append(make('p','quiet',delivery.current?'Shows revision '+delivery.revision+'. Select words on the page to edit them.':'Shows revision '+delivery.revision+'. Your current work is revision '+p.revision+'.'));
    if(!delivery.current&&p.scene)view.append(button('Update preview',()=>action('preview'),true));
    view.append(scroll,tools);
    if(kept)view.append(kept);
    showPicture(delivery,img,p.id);
  }else if(p.scene)view.append(make('p','','No preview yet. Rendering is local and starts no assistant or image request.'),button('Create preview',()=>action('preview'),true));
  const parts=[ledger,view];
  if(p.scene&&names.length)parts.push(inspector(p,names,img,mark));
  return add(make('div','ig-workbench'),...parts);
}
function inspector(p,names,img,mark){
  if(!names.some(n=>n.id===bench.element))bench.element=names[0].id;
  const panel=make('section','card stack ig-inspector');panel.setAttribute('aria-labelledby','ig-inspector-title');
  const title=make('h2','card-title','Edit words');title.id='ig-inspector-title';
  const choice=field('Element','','select');choice.input.id='ig-element';choice.wrap.htmlFor='ig-element';
  const where=make('p','quiet');where.id='ig-element-where';
  const words=field('Words','','textarea');words.input.id='ig-words';words.wrap.htmlFor='ig-words';words.input.rows=4;words.input.setAttribute('aria-describedby','ig-element-where ig-save-state');
  const state=make('p','ig-save-state');state.id='ig-save-state';state.setAttribute('role','status');state.setAttribute('aria-live','polite');
  const advanced=make('p','quiet');
  const save=button('Save words',()=>saveWords(),true);save.id='ig-save-words';
  function options(){choice.input.replaceChildren(...names.map(n=>{const o=make('option','',n.label+(bench.drafts[n.id]!==undefined&&bench.drafts[n.id]!==n.text?' (unsaved)':''));o.value=n.id;return o;}));choice.input.value=bench.element;}
  function show(){
    const chosen=names.find(n=>n.id===bench.element);
    words.wrap.querySelector('.field-label').textContent='Words for '+chosen.label;
    words.input.value=bench.drafts[chosen.id]??chosen.text;where.textContent=chosen.location+'.';advanced.textContent='Element ID: '+chosen.id;
    const [x,y,w,h]=chosen.bounds;Object.assign(mark.style,{left:x*100+'%',top:y*100+'%',width:w*100+'%',height:h*100+'%'});mark.hidden=!img;
    pending();
  }
  function pending(){
    const chosen=names.find(n=>n.id===bench.element),unsaved=words.input.value!==chosen.text;
    if(bench.failed){state.className='ig-save-state problem';state.textContent=bench.failed+' Your words are kept here.';return;}
    if(bench.unchanged&&!unsaved){state.className='ig-save-state';state.textContent='Nothing changed, so no revision was made. These words are already in revision '+held.project.revision+'.';return;}
    if(bench.saved&&!unsaved&&bench.saved.revision===held.project.revision){
      const stale=!held.deliveries.find(d=>d.current);state.className='ig-save-state';
      state.replaceChildren(document.createTextNode('Saved '+bench.saved.label+' as revision '+bench.saved.revision+'. '+(stale?'The preview still shows an earlier revision. Update it to see this change before review.':'')));
      if(stale)state.append(button('Update preview',()=>action('preview')));
      return;
    }
    state.className='ig-save-state quiet';state.textContent=unsaved?'Unsaved words. Saving makes a new revision; approval is never carried over.':'Saving makes a new revision. Approval is never carried over.';
  }
  choice.input.addEventListener('change',()=>{bench.element=choice.input.value;bench.saved=null;bench.failed='';bench.unchanged=false;keepBench();show();});
  words.input.addEventListener('input',()=>{const chosen=names.find(n=>n.id===bench.element);if(words.input.value===chosen.text)delete bench.drafts[chosen.id];else bench.drafts[chosen.id]=words.input.value;bench.failed='';bench.unchanged=false;keepBench();options();pending();});
  if(img){
    img.addEventListener('click',event=>{
      const box=img.getBoundingClientRect(),x=(event.clientX-box.left)/box.width,y=(event.clientY-box.top)/box.height;
      const hit=names.filter(n=>x>=n.bounds[0]&&x<=n.bounds[0]+n.bounds[2]&&y>=n.bounds[1]&&y<=n.bounds[1]+n.bounds[3]).sort((a,b)=>a.bounds[2]*a.bounds[3]-b.bounds[2]*b.bounds[3])[0];
      if(!hit)return;bench.element=hit.id;bench.saved=null;bench.failed='';bench.unchanged=false;keepBench();options();show();words.input.focus();
    });
    img.title='Select words on the page to edit them';
  }
  options();show();
  panel.append(title,make('p','quiet','Choose an element here or select it on the page. Each save keeps your place.'),choice.wrap,where,words.wrap,add(make('div','bar'),save),state,detail('Advanced',advanced));
  return panel;
}
async function saveWords(){
  const chosen=(held.elements||[]).find(n=>n.id===bench.element),input=$('ig-words');if(!chosen||!input)return;
  const text=input.value;bench.scroll=window.scrollY;bench.saved=null;bench.failed='';bench.unchanged=false;
  if(text===chosen.text){delete bench.drafts[chosen.id];bench.unchanged=true;keepBench();bench.focus=true;renderProject();return;}
  const before=held.project.revision,result=await action('edit-text',{element_id:chosen.id,text});
  if(result&&typeof result.revision==='number'){delete bench.drafts[chosen.id];if(result.revision>before)bench.saved={revision:result.revision,label:chosen.label};else bench.unchanged=true;}
  else{bench.drafts[chosen.id]=text;bench.failed=$('notice').textContent||'These words could not be saved.';}
  keepBench();bench.focus=true;if(held?.project.id===bench.project)renderProject();
}
function restoreBench(){
  if(!bench.focus)return;bench.focus=false;
  const target=$('ig-words');if(!target)return;
  target.focus({preventScroll:true});
  if(typeof bench.scroll==='number'){const y=bench.scroll;requestAnimationFrame(()=>window.scrollTo(0,y));}
}
// One preview download per saved delivery; re-rendering the page reuses it.
let pictureFor='';
function showPicture(delivery,img,id){
  if(picture&&pictureFor===delivery.id){img.src=picture;return;}
  download(delivery,'png',true).then(url=>{if(held?.project.id===id&&document.body.contains(img)){resetPicture();picture=url;pictureFor=delivery.id;img.src=url;}else URL.revokeObjectURL(url);}).catch(f=>error(f.message));
}
function savedFiles(d){
  const words=(d.draft?'Draft':'Approved')+' · revision '+d.revision+(d.approved_current?' · current approval':d.current?' · matches current work':' · earlier');
  return add(make('div','desk-version'),make('span','',words),add(make('div','ig-page-tools'),...['png','pdf','svg','text'].map(format=>{const node=button(format==='text'?'Text':format.toUpperCase(),async()=>{try{await download(d,format);}catch(f){error(f.message);}});node.setAttribute('aria-label','Download '+(format==='text'?'accessible text':format.toUpperCase())+', '+(d.draft?'draft':'approved')+' revision '+d.revision);return node;})));
}
function historyEntry(v,current){
  const facts=[when(v.saved_at),'Revision '+v.revision+(current?' (current)':''),v.affected?.length?'Changed: '+v.affected.join(', '):'',v.approved?'Approved at this revision':''].filter(Boolean).join(' · ');
  return add(make('div','desk-version'),add(make('div','ig-entry'),make('strong','',v.summary||'Saved revision '+v.revision),make('span','quiet',facts),make('span','quiet','Exact identity '+v.sha256.slice(0,12))),
    current?null:add(make('div','bar'),button('Compare revision '+v.revision+' with current',()=>compareSheet(v)),button('Restore revision '+v.revision,()=>restoreSheet(v))));
}
function roadmapView(map){
  if(!map)return null;
  const steps=add(make('ol','workflow-steps ig-roadmap'),...map.steps.map(step=>{
    const item=make('li','workflow-step');const bead=make('span','bead');bead.dataset.state=step.state==='done'?'done':step.state==='current'?'current':'none';bead.setAttribute('aria-hidden','true');
    item.append(bead,document.createTextNode(' '+step.label+(step.state==='done'?' (done)':'')));if(step.state==='current')item.setAttribute('aria-current','step');return item;}));
  steps.setAttribute('aria-label','Steps to an approved delivery');
  const line=(name,words)=>add(make('p',''),make('strong','',name+' '),document.createTextNode(words));
  return add(make('section','card stack ig-standing'),make('h2','card-title','Where this stands'),steps,line('Complete:',map.complete),line('Needs you:',map.needs),line('Downloads:',map.downloads));
}
function finishCard(p,delivery,checked,approved){
  const prepared=held.deliveries.some(d=>d.approved_current);
  const step=(title,words,...controls)=>add(make('div','stack ig-finish-step'),make('strong','',title),make('p','',words),...controls.filter(Boolean));
  return card('Review and finish',
    step('1. Review the page (required)','Look at the actual page for revision '+delivery.revision+' at its intended size: facts and qualifications, objects and relationships, crop and resolution, label clearance and brand. Recording your review runs the checks straight after.',
      add(make('div','bar'),button('Record my review and run checks',()=>reviewSheet(delivery)),button('Inspect page with assistant (optional)',()=>action('inspect-images',{then_check:true})))),
    step('2. Checks (on this computer)','Required content, factual support, page layout, brand and accessibility, and your latest review. They start no assistant or image request.',
      add(make('div','bar'),button('Run checks again',()=>action('check')),p.checks.some(c=>c.status!=='passed')?button('Repair findings',repairSheet):null)),
    step('3. Approve (your decision)',approved?(prepared?'You approved revision '+p.approval.revision+'. Its files are ready below and in Saved files.':'You approved revision '+p.approval.revision+'. Prepare its files on this computer; nothing is sent anywhere.'):checked?'Approval applies to revision '+p.revision+' only. Its final files are prepared on this computer straight after; a later change needs a new review.':'Approval becomes available when the current checks pass against your latest review.',
      approved?(prepared?null:button('Prepare approved files',()=>action('export',{draft:false}),true)):checked?button('Approve revision '+p.revision+' and prepare files',approveRevision,true):null));
}
async function approveRevision(){
  const result=await action('approve',{then_export:true});
  if(result?.approved&&result.problem)error('Revision '+result.revision+' is approved, but its files are not ready: '+result.problem+' Choose Prepare approved files to try again on this computer.');
  else if(result?.approved&&result.library?.state==='failed')error('Revision '+result.revision+' is approved and its files are ready, but they were not kept in the Document Library: '+result.library.problem+' Choose Keep in library again.');
}
// The shared Document Library (library.js). Add from library makes chosen revisions sources
// of this infographic, Use revision N takes a newer one only when pressed, and approved files
// say whether their text and PDF were kept there. Choosing documents starts no research,
// assistant or image work and changes no research setting.
function libraryPick(use){
  if(!window.StudioLibrary){error('The library could not be loaded. Reload the page.');return Promise.resolve(false);}
  return window.StudioLibrary.pick({studio:'infographic',max:40,post:(route,body)=>request('/api/'+route,body),use,
    refocus:()=>{const found=document.querySelector('[data-key="ig-library-add"]')||document.querySelector('[data-key="ig-new-library"]');if(found)found.closest('details')?.setAttribute('open','');return found;}});
}
async function libraryRows(picks){
  // Each choice is read once to show its title and extraction gaps before anything changes.
  const rows=[];
  for(const pick of picks){
    const found=await request('/api/library-document',{id:pick.id,revision:pick.revision});
    if(!found.readable)throw Error('"'+found.title+'" cannot be added: '+(found.problem||'it has no readable text.'));
    rows.push({id:pick.id,revision:pick.revision,title:found.title,characters:found.characters,gaps:found.gaps||[]});
  }
  return rows;
}
async function draftLibrary(picks){
  // Before there is an infographic nothing can be cleared; choices are checked again, all or
  // none, when the brief is saved.
  if(picks.some(pick=>draft.library.some(one=>one.id===pick.id)))throw Error('A chosen document is already listed for this infographic.');
  draft.library.push(...(await libraryRows(picks)).map(row=>({...row,acknowledged:false})));
}
const LIBRARY_CLEARS='Adding or updating a source clears the facts, story, page and approval built from the earlier sources. Earlier work stays in History, and nothing starts by itself.';
function libraryClears(){
  const p=held.project;
  return [p.facts.length?'facts':'',p.stories.length?'story':'',p.scene?'page':'',p.approval?'approval':''].filter(Boolean);
}
// Says what will be cleared and asks first when there is work to clear, and asks the person
// to confirm readable-only coverage when a document has extraction gaps; otherwise runs.
function libraryConfirm(title,label,rows,run){
  const clears=libraryClears(),gaps=rows.some(row=>row.gaps.length);
  if(!clears.length&&!gaps){run(false);return;}
  const problem=make('p','problem');problem.setAttribute('role','alert');
  const ack=make('input');ack.type='checkbox';
  const parts=[];
  if(clears.length)parts.push(make('p','','This clears this infographic’s '+clears.join(', ')+'. Earlier work stays in History. Nothing starts by itself; find the story again when you are ready.'));
  for(const row of rows)parts.push(card(row.title,make('p','quiet','Revision '+row.revision+' · '+row.characters+' readable characters'),row.gaps.length?list(row.gaps):make('p','quiet','No extraction gaps.')));
  if(gaps)parts.push(add(make('label','check'),ack,document.createTextNode('I reviewed these gaps. Use only the readable text.')));
  sheet(title,...parts,problem,add(make('div','create-foot bar'),button(label,()=>{if(gaps&&!ack.checked){problem.textContent='Review the gaps and confirm using only the readable text first.';return;}run(gaps);},true),button('Cancel',closeSheet)));
}
function libraryAddButton(){
  let rows=null;
  const node=button('Add from library',()=>libraryPick(async picks=>{
    if(busy)throw Error('This infographic is still working. Add from the library once it has finished.');
    rows=await libraryRows(picks);
  }).then(done=>{
    if(!done||!rows)return;
    const chosen=rows;rows=null;
    libraryConfirm(chosen.length===1?'Add '+chosen[0].title:'Add '+chosen.length+' documents','Add as sources',chosen,async acknowledged=>{
      const result=await action('library',{picks:chosen.map(({id,revision})=>({id,revision})),acknowledge_warnings:acknowledged},null,{quiet:true});
      if(result)toast((chosen.length===1?'The document is a source now.':chosen.length+' documents are sources now.')+' Nothing was started; find the story again when you are ready.');
      const again=document.querySelector('[data-key="ig-library-add"]');if(again){again.closest('details')?.setAttribute('open','');again.focus();}
    });
  }));
  node.dataset.key='ig-library-add';return node;
}
function libraryNote(s){
  const pinned=held.library?.sources?.[s.id];
  if(!pinned)return [];
  const from='From the Document Library'+(s.provenance?.studio?' ('+s.provenance.studio+')':'')+', revision '+pinned.revision;
  const words=pinned.update?from+'. Revision '+pinned.head+' is available.':pinned.note?from+'. '+pinned.note:from+'.';
  const parts=[make('p','quiet',words),list(s.coverage?.warnings||[])];
  if(pinned.update)parts.push(button('Use revision '+pinned.head+' of '+(s.name||s.id),async()=>{
    try{
      const rows=await libraryRows([{id:pinned.id,revision:pinned.head}]);
      libraryConfirm('Use revision '+pinned.head+' of '+(s.name||s.id),'Use revision '+pinned.head,rows,async acknowledged=>{
        const result=await action('library-update',{document:pinned.id,revision:pinned.head,acknowledge_warnings:acknowledged},null,{quiet:true});
        if(result)toast('Revision '+pinned.head+' is the source now. Nothing was started.');
      });
    }catch(failure){error(failure.message);}
  }),make('p','quiet',LIBRARY_CLEARS));
  return parts;
}
function keptPart(delivery){
  const kept=held.library?.kept;
  if(kept&&kept.export===delivery.id&&kept.state==='kept')return make('p','quiet','Kept in the Document Library with its text and PDF (library revision '+kept.library_revision+').');
  const again=button(kept&&kept.export===delivery.id?'Keep in library again':'Keep in Document Library',async()=>{
    const result=await action('library-keep',{export_id:delivery.id},null,{quiet:true});
    if(result?.state==='kept')toast('Kept in the Document Library.');else if(result?.problem)error('Not kept in the Document Library: '+result.problem);
  });
  if(kept&&kept.export===delivery.id)return add(make('div','stack'),make('p','problem','Not kept in the Document Library: '+kept.problem),again);
  return add(make('div','stack'),make('p','quiet','These approved files are not in the Document Library yet.'),again);
}
function receiptCard(title,state,words,...controls){
  const bead=make('span','bead');bead.dataset.state=state;bead.setAttribute('aria-hidden','true');
  return add(make('section','card stack'),make('h3','card-title',title),add(make('p','state'),bead,document.createTextNode(words)),...controls.filter(Boolean));
}
function receiptSheet(delivery,receipts){
  const parts=receipts.map(r=>{
    if(r.kind==='pdf')return receiptCard('PDF',r.ok?'done':'late',r.ok?'Downloaded: approved revision '+delivery.revision+'.':'Not downloaded: '+r.message,
      button(r.ok?'Download PDF again':'Retry PDF download',async()=>{try{await download(delivery,'pdf');toast('PDF downloaded again.');}catch(f){error(f.message);}}));
    const result=r.result||{};
    if(result.url)return receiptCard('Google Doc','done','Delivered: approved revision '+delivery.revision+'.',googleLink(result.url,'Open Google Doc'));
    const saved=(held?.google_deliveries||[]).some(g=>g.request_id===r.request_id);
    const uncertain=saved&&(!r.result||result.state==='unknown');
    const resend=async()=>{const request_id=requestId();const again=await action('google-deliver',{export_id:delivery.id,request_id,folder:r.folder},delivery.revision,{quiet:true});receiptSheet(delivery,receipts.map(x=>x===r?{...r,request_id,result:again,problem:again?null:$('notice').textContent}:x));};
    const check=async()=>{const again=await action('google-deliver',{export_id:delivery.id,request_id:r.request_id,folder:r.folder,reconcile:true},delivery.revision,{quiet:true});receiptSheet(delivery,receipts.map(x=>x===r?{...r,result:again}:x));};
    if(!saved)return receiptCard('Google Doc','late','Not delivered: '+(result.message||r.problem||'The request did not start.')+' No Google request was saved.',button('Send again',resend));
    return receiptCard('Google Doc',uncertain?'review':'late',(uncertain?'Not confirmed: ':'Not delivered: ')+(result.message||r.problem||'The outcome could not be confirmed.')+' Nothing was resent.',
      button('Check again without resending',check),uncertain?null:button('Send again',resend));
  });
  const partial=receipts.some(r=>r.kind==='pdf'?!r.ok:!r.result?.url)&&receipts.some(r=>r.kind==='pdf'?r.ok:!!r.result?.url);
  sheet('Delivery receipt',make('p','','Approved revision '+delivery.revision+'. Each format you chose is listed with what happened.'),...parts,
    partial?make('p','quiet','What succeeded is kept. Retrying the PDF is a download on this computer and sends nothing to Google.'):null,add(make('div','create-foot bar'),button('Done',closeSheet,true)));
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
function reviewSheet(delivery){const observations=field('What did you inspect on the actual composed page?','','textarea');sheet('Review the actual page',make('p','','Look at the rendered page for revision '+delivery.revision+' at its intended size, then say what you checked. Recording your review runs the local checks straight after; nothing is approved.'),observations.wrap,add(make('div','bar'),button('Record review and run checks',()=>action('review',{export_id:delivery.id,observations:lines(observations.input.value),then_check:true}),true),button('Cancel',closeSheet)),detail('Optional: ask your assistant to inspect it',make('p','quiet','Your assistant looks at the actual page and artwork and records located findings. It uses your assistant allowance and never approves.'),button('Inspect page with assistant',()=>action('inspect-images',{then_check:true}))));}
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
    const teamEmail=field('Team Git email',preferences.native.team_email||'');
    const googleAccount=field('Google account email',preferences.native.google_account||''),googleFolder=field('Google Drive destination folder ID (optional)',preferences.native.google_folder||'');
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
    imageDefaults.push(teamEmail.wrap,detail('Advanced Google account override',make('p','quiet','Leave empty to use the same existing Google sign-in as Blog Studio.'),googleAccount.wrap,googleFolder.wrap),make('p','quiet','Uses the selected existing gcloud sign-in only when you explicitly read or deliver a Google Doc. No login or account access starts here.'),detail('Advanced renderer setting', renderer.wrap),
      make('p', 'quiet', 'Defaults apply to new work. Your existing workspace and saved brand stay in place.'),
      button('Save defaults', async () => {
        try {
          const changes = {renderer: renderer.input.value,team_email:teamEmail.input.value,google_account:googleAccount.input.value,google_folder:googleFolder.input.value};
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
      card('Shared settings', sharedLink, make('p', 'quiet', 'Your infographic workspace stays local. Team connection and sharing happen only through explicit Team library actions.')),
      card('Infographic defaults', ...imageDefaults));
  } catch (failure) { error(failure.message); }
}
$('home').addEventListener('click',home);$('settings').addEventListener('click',showSettings);
if (homeLink) {
  $('go-suite').hidden = false;
  $('go-suite').href = suiteReturn(homeLink, launchHash, location);
  if (sameTab) $('go-suite').removeAttribute('target');
}
async function startDesk() {
  // Back from shared settings: reopen the same infographic and sheet. Connecting stays a choice.
  let back=null;try{back=JSON.parse(sessionStorage.getItem('infographic-studio-return')||'null');sessionStorage.removeItem('infographic-studio-return');}catch(f){}
  if(back&&typeof back==='object'&&!Array.isArray(back)){
    if(typeof back.project==='string'&&/^[A-Za-z0-9_-]{1,64}$/.test(back.project))await openProject(back.project);else await home();
    if(back.sheet==='team')await teamSheet();
    return;
  }
  let id='';try{id=sessionStorage.getItem('infographic-studio-project')||'';}catch(f){}
  if(id){try{const progress=await request('/api/activity?id='+encodeURIComponent(id)),desk=await request('/api/desk?id='+encodeURIComponent(id));const unsaved=unsavedFor(id);if(progress.activity?.state==='running'||desk.planning_response?.available||desk.recovery?.length||unsaved){await openProject(id);return;}}catch(f){}}
  await home();
}
$('sheet').addEventListener('close',paintWork);
if(!token)error('Open Infographic Studio using the private link printed in your terminal.');else void startDesk();
// Back from shared settings with the browser's Back button restores this page from its cache,
// without running startDesk: drop the return marker and re-read an open Team library sheet.
window.addEventListener('pageshow',event=>{
  if(!event.persisted||!token)return;
  try{sessionStorage.removeItem('infographic-studio-return');}catch(f){}
  if($('sheet').open&&$('sheet-title')?.textContent==='Team library')void teamSheet();
});

function reviseArtSheet(){const change=field('What should change?','','textarea'),preserve=field('What should stay the same?','Keep all other subjects, relationships, brand, empty label regions and composition.','textarea');sheet('Revise the artwork',make('p','','This sends the saved original as a reference to your selected image provider. It uses provider allowance; the earlier artwork remains in history.'),change.wrap,preserve.wrap,add(make('div','bar'),button('Create referenced revision',()=>action('revise-art',{change:change.input.value,preserve:preserve.input.value,request_id:requestId()}),true),button('Cancel',closeSheet)));}
async function compareSheet(version){try{const result=await request('/api/action',{action:'compare',id:held.project.id,expected_revision:held.project.revision,before:version.revision,after:held.project.revision});sheet('Changes since revision '+version.revision,...Object.entries(result.result).map(([key,value])=>detail(key,make('h3','','Before'),make('pre','ig-csv-preview',JSON.stringify(value.before,null,2)),make('h3','','Current'),make('pre','ig-csv-preview',JSON.stringify(value.after,null,2)))),button('Done',closeSheet));}catch(f){error(f.message);}}
function sourceSheet() {
  const value=field('New or replacement supplied information','','textarea');
  const replacement=field('Source to replace (leave empty to add another)','','select');
  const empty=make('option','','Add as another source'); empty.value=''; replacement.input.append(empty);
  for(const source of held.project.sources){const option=make('option','',source.name);option.value=source.id;replacement.input.append(option);}
  const upload=field('Or upload a source file'); upload.input.type='file'; upload.input.accept='.txt,.md,.pdf,application/pdf,.docx,.html,.htm';
  const shown=make('div','stack'),problem=make('p','problem'); problem.setAttribute('role','alert');
  let preview=null,acknowledged=false;
  const go=button('Save supplied information',async()=>{
    problem.textContent='';
    if(preview){
      if(value.input.value.trim()){problem.textContent='Use either a file or pasted text for this source.';return;}
      if(!preview.readable || (preview.warnings.length&&!acknowledged)){problem.textContent='Review the readable coverage before importing this source.';return;}
      await action('source-import',{capture_id:preview.id,acknowledge_warnings:acknowledged,...(replacement.input.value?{replace_id:replacement.input.value}:{})});
    }else{
      if(!value.input.value.trim()){problem.textContent='Paste source text or choose a readable file.';return;}
      await action('source',{data:encoded(new TextEncoder().encode(value.input.value)),kind:'text',name:'Updated supplied information',...(replacement.input.value?{replace_id:replacement.input.value}:{})});
    }
  },true);
  upload.input.addEventListener('change',async()=>{
    const file=upload.input.files[0]; if(!file)return; go.disabled=true; problem.textContent='';
    try{
      const kinds={txt:'text',md:'markdown',pdf:'pdf',docx:'docx',html:'html',htm:'html'},kind=kinds[file.name.toLowerCase().split('.').pop()];
      if(!kind)throw Error('Choose text, Markdown, PDF, Word (.docx) or HTML. Add selected CSV through a new information preview.');
      preview=await request('/api/source-preview',{data:encoded(await bytes(file)),kind,name:file.name}); acknowledged=false;
      shown.replaceChildren(make('p','',preview.characters+' readable characters'),make('pre','ig-csv-preview',preview.excerpt),list(preview.warnings));
      if(preview.warnings.length){const ack=make('input');ack.type='checkbox';ack.addEventListener('change',()=>{acknowledged=ack.checked;});shown.append(add(make('label','check'),ack,document.createTextNode('I reviewed these gaps. Use only the readable text.')));}
      if(!preview.readable)problem.textContent='No readable text was found. Supply an accessible Word or text version.';
    }catch(failure){preview=null;problem.textContent=failure.message;}finally{go.disabled=false;}
  });
  sheet('Update supplied information',make('p','','Import keeps a new source revision and clears dependent story/page approval. Earlier work remains in history.'),replacement.wrap,value.wrap,upload.wrap,button('Use a Google Doc, Slides or public page',()=>remoteSheet(result=>{preview=result;acknowledged=false;sourceImportSheet(result,replacement.input.value);})),shown,problem,add(make('div','bar'),go,button('Cancel',closeSheet)));
}
async function sourceTextSheet(source,start=0){
  try{
    const found=await request('/api/source?id='+encodeURIComponent(held.project.id)+'&source='+encodeURIComponent(source.id)+'&start='+start);
    sheet('Captured source: '+source.name,make('p','quiet','Saved text '+found.start+'–'+found.end+' of '+found.total+' characters. This view does not fetch a newer source.'),list(source.coverage?.warnings||[]),make('pre','ig-csv-preview',found.text),add(make('div','bar'),start?button('Previous text',()=>sourceTextSheet(source,Math.max(0,start-20000))):null,found.end<found.total?button('More text',()=>sourceTextSheet(source,found.end)):null,button('Done',closeSheet)));
  }catch(failure){error(failure.message);}
}

function reviseStorySheet(story,visual=false){const scope=field('Scope','','select'),instruction=field('What should change?',visual?'Make this an infographic with concise labels, diagrams, component maps and visual comparisons. Keep the meaning and required wording. Use charts only for supplied numbers.':'','textarea');const all=make('option','','Whole story');all.value='';scope.input.append(all);for(const block of story.blocks){const option=make('option','',block.title);option.value=block.id;scope.input.append(option);}scope.wrap.hidden=visual;sheet(visual?'Make this story visual':'Refine this story',make('p','',visual?'Uses your configured assistant to revise the saved facts into a visual plan. No new research or image generation. Review and choose the result before rebuilding.':'Your selected assistant revises the supplied explanation. A named block preserves all other content. Review and choose the revised story before rebuilding.'),scope.wrap,instruction.wrap,add(make('div','bar'),button(visual?'Suggest visual plan':'Suggest revision',()=>action('revise-story',{story_id:story.id,block_id:scope.input.value||null,instruction:instruction.input.value}),true),button('Cancel',closeSheet)));}
function repairSheet(){sheet('Repair current findings',make('p','','Apply the recorded artwork correction, or try the other layout. Artwork correction uses your selected provider and the original as a reference. Layout and image repairs share a two-attempt budget; nothing is approved automatically.'),add(make('div','bar'),button('Apply bounded repair',()=>action('repair',{request_id:requestId()}),true),button('Cancel',closeSheet)));}

function storyThumbnail(story){
  const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');
  const node=(tag,attrs)=>{const e=document.createElementNS(ns,tag);for(const[k,v]of Object.entries(attrs))e.setAttribute(k,String(v));svg.append(e);return e;};
  svg.setAttribute('viewBox','0 0 360 150');svg.setAttribute('class','ig-thumbnail');svg.setAttribute('role','img');
  svg.setAttribute('aria-label','Visual story: '+story.blocks.map(b=>b.title+': '+(b.visual?.nodes||[]).map(n=>n.label).join(', ')).join('; '));
  const names={process:'Process flow',timeline:'Timeline',parts:'Component map',comparison:'Visual comparison',numbers:'Number callouts',concept:'Concept diagram'};
  for(const[i,b]of story.blocks.entries()){
    const x=i*360/story.blocks.length+3,w=360/story.blocks.length-6;
    node('rect',{x,y:8,width:w,height:132,rx:12,class:'ig-outline-block'});
    const label=node('text',{x:x+8,y:30,class:'ig-outline-label'});label.textContent=names[b.kind];
    const boxes=b.visual?.nodes||b.fact_ids.slice(0,3).map((id,j)=>({id:'n'+j,label:''}));
    if(b.kind==='numbers'){
      const f=held.project.facts.find(f=>f.id===b.fact_ids[0]);
      const value=node('text',{x:x+8,y:90,class:'ig-outline-value'});value.textContent=f?String(f.literal??f.value)+' '+f.unit:'Exact values';
    }else{
      const count=Math.min(4,boxes.length), positions=[];
      for(let j=0;j<count;j++)positions.push([x+10+(j%2)*(w-20)/2,48+Math.floor(j/2)*42]);
      for(let j=1;j<count;j++)if(['process','timeline','parts'].includes(b.kind)){
        const a=positions[j-1],c=positions[j];node('line',{x1:a[0]+(w-28)/4,y1:a[1]+15,x2:c[0]+(w-28)/4,y2:c[1]+15,class:'ig-outline-link'});
      }
      for(const[px,py]of positions){node('rect',{x:px,y:py,width:(w-28)/2,height:30,rx:7,class:'ig-outline-node'});node('circle',{cx:px+12,cy:py+15,r:5,class:'ig-outline-dot'});}
    }
  }
  return svg;
}

async function imageRequestSheet(id){try{const saved=await request('/api/image-request?id='+encodeURIComponent(held.project.id)+'&request='+encodeURIComponent(id));sheet('Saved image request',make('p','',saved.provider+' · '+saved.operation),make('pre','ig-csv-preview',saved.brief.prompt),make('p','quiet','Remote cancellation and cost remain unknown unless the provider reported them.'),button('Done',closeSheet));}catch(f){error(f.message);}}
async function olderHistory(){try{const last=held.history.at(-1);const result=await request('/api/history-before?id='+encodeURIComponent(held.project.id)+'&before='+last.revision);held.history.push(...result.history);renderProject();document.querySelectorAll('details').forEach(d=>{if(d.firstChild.textContent==='History')d.open=true;});}catch(f){error(f.message);}}

function briefSheet(){const p=held.project,fields={};for(const[key,label,value]of[['title','Working title',p.brief.title],['audience','Audience',p.brief.audience],['purpose','Desired takeaway',p.brief.purpose],['must','Must-show ideas — one per line',p.brief.must_show.map(r=>r.text).join('\n')],['locked','Exact wording to preserve',p.brief.locked_words.join('\n')],['exclusions','Leave out',p.brief.exclusions.join('\n')]])fields[key]=field(label,value,['must','locked','exclusions'].includes(key)?'textarea':'input');sheet('Edit brief and requirements',make('p','','Changing the brief requires a fresh story/page review. Captured facts, earlier versions and exports are kept.'),...Object.values(fields).map(f=>f.wrap),add(make('div','bar'),button('Save brief',async()=>{try{await request('/api/project',{id:p.id,expected_revision:p.revision,brief:{...p.brief,title:fields.title.input.value,audience:fields.audience.input.value,purpose:fields.purpose.input.value,must_show:lines(fields.must.input.value).map((text,i)=>({id:p.brief.must_show[i]?.id||'r_'+requestId().slice(0,12),text})),locked_words:lines(fields.locked.input.value),exclusions:lines(fields.exclusions.input.value)}});closeSheet();await openProject(p.id);}catch(f){error(f.message);}},true),button('Cancel',closeSheet)));}

function googleLink(url,label){const link=make('a','button',label);link.href=url;link.target='_blank';link.rel='noopener noreferrer';return link;}
async function remoteSheet(done){
  const url=field('Document or page link'),tabs=field('Tab or slide IDs, comma separated (optional; otherwise all)');
  url.input.type='url';url.input.placeholder='Paste a Google Docs, Google Slides or public HTTPS link';
  const problem=make('p','problem');problem.setAttribute('role','alert');
  const go=button('Read and preview',async()=>{go.disabled=true;problem.textContent='';try{
    const value=url.input.value.trim();let parsed;try{parsed=new URL(value);}catch(f){throw Error('Paste the full https link copied from Share or the address bar.');}
    const sent={kind:parsed.hostname==='docs.google.com'?'google-doc':'url',url:value};
    if(sent.kind==='google-doc'&&tabs.input.value.trim())sent.tabs=tabs.input.value.split(',').map(t=>t.trim());
    const preview=await request('/api/remote-preview',sent);done(preview);
  }catch(f){problem.textContent=f.message;}finally{go.disabled=false;}},true);
  sheet('Add a document or page',make('p','','Paste a Google Docs, Google Slides or public page link. Uses your existing Google sign-in, just like Blog Studio. Review captured text before importing.'),url.wrap,detail('Choose specific tabs or slides',tabs.wrap),problem,add(make('div','bar'),go,button('Cancel',()=>{closeSheet();if(!held)newSheet();})));
}

function sourceImportSheet(preview,replaceId){
  let acknowledged=false;const problem=make('p','problem'),ack=make('input');ack.type='checkbox';ack.addEventListener('change',()=>{acknowledged=ack.checked;});
  sheet('Review captured information',make('p','',preview.name+' · '+preview.characters+' readable characters'),make('pre','ig-csv-preview',preview.excerpt),list(preview.warnings),preview.warnings.length?add(make('label','check'),ack,document.createTextNode('I reviewed these gaps. Use only readable text.')):make('p','quiet','Captured text is stored locally; import does not read the remote document again.'),problem,add(make('div','bar'),button('Import this capture',()=>{if(!preview.readable||(preview.warnings.length&&!acknowledged)){problem.textContent='Review readable coverage and acknowledge gaps before import.';return;}action('source-import',{capture_id:preview.id,acknowledge_warnings:acknowledged,...(replaceId?{replace_id:replaceId}:{})});},true),button('Cancel',closeSheet)));
}
async function deliverySheet(delivery){
  try{preferences=await request('/api/preferences');}catch(f){error(f.message);return;}
  const format=field('Output',preferences.delivery_default||'pdf','select');for(const[value,label]of[['both','Google Doc and PDF'],['google','Google Doc'],['pdf','PDF']]){const option=make('option','',label);option.value=value;format.input.append(option);}format.input.value=preferences.delivery_default||'pdf';
  const folder=field('Destination folder ID (optional)',preferences.google?.folder||'');
  const problem=make('p','problem'),savedRequest=requestId();
  format.input.addEventListener('change',()=>{folder.wrap.hidden=format.input.value==='pdf';});
  const go=button('Deliver approved page',async()=>{go.disabled=true;problem.textContent='';
    const choice=format.input.value,receipts=[];
    try{
      if(choice!=='google'){try{await download(delivery,'pdf');receipts.push({kind:'pdf',ok:true});}catch(f){receipts.push({kind:'pdf',ok:false,message:f.message});}}
      if(choice!=='pdf'){const result=await action('google-deliver',{export_id:delivery.id,request_id:savedRequest,folder:folder.input.value},null,{quiet:true});receipts.push({kind:'google',result,request_id:savedRequest,folder:folder.input.value,problem:result?null:$('notice').textContent});}
      receiptSheet(delivery,receipts);
    }finally{go.disabled=false;}},true);
  sheet('Deliver this approved revision',make('p','','PDF preserves the exact approved one-page render. A new Google Doc contains that page as an image, plus editable text and source notes. Your original document is kept. Google conversion layout requires visual review in Docs.'),make('p','quiet','Starts with your shared Marketing Studio delivery choice and existing Google sign-in.'),format.wrap,detail('Choose a destination folder',folder.wrap),problem,add(make('div','bar'),go,button('Cancel',closeSheet)));
}

async function handoffSheet(done){
  try{preferences=await request('/api/preferences');}catch(f){error(f.message);return;}
  const studio=field('Originating studio','blog','select');for(const[value,label]of[['blog','Blog Studio'],['presentation','Presentation Studio'],['training','Training Studio']]){const option=make('option','',label);option.value=value;studio.input.append(option);}studio.input.value='blog';
  const root=field('Studio materials folder',preferences.material_folders.blog),results=make('div','stack'),problem=make('p','problem');
  studio.input.addEventListener('change',()=>{root.input.value=preferences.material_folders[studio.input.value];results.replaceChildren();});
  const scan=button('List available materials',async()=>{scan.disabled=true;problem.textContent='';try{
    const found=await request('/api/handoff-inventory',{root:root.input.value,studio:studio.input.value});
    results.replaceChildren(...found.files.map(file=>button(file.file+' · '+file.bytes+' bytes',async()=>{try{scan.disabled=true;const preview=await request('/api/handoff-preview',{root:found.root,studio:found.studio,file:file.file,expected_sha256:file.sha256});done(preview);}catch(f){problem.textContent=f.message;}finally{scan.disabled=false;}})));
    if(!found.files.length)problem.textContent='No supported materials are available in this studio folder.';
  }catch(f){problem.textContent=f.message;}finally{scan.disabled=false;}});
  sheet('Import a selected studio material',make('p','','Lists readable materials from the studio-owned folder. Select one file to preview; nothing else is imported or shared.'),studio.wrap,root.wrap,scan,problem,results,button('Cancel',()=>{closeSheet();if(!held)newSheet();}));
}
async function researchSheet(){
  const ident=held.project.id,revision=held.project.revision;
  const problem=make('p','problem'),status=make('div','stack');
  const primary=held.project.sources.length>0;
  const editor=new StudioResearch.Editor({request:sent=>request('/api/research-sources',sent),primarySummary:primary?'Your captured infographic material is included. Add any additional references here.':''});
  const control=async action=>{try{const result=await request('/api/research-control',{id:ident,action});if(action==='preview'){sourceImportSheet(result);return;}await poll();}catch(f){problem.textContent=f.message;}};
  async function poll(){
    if(!$('sheet').open||!$('sheet-body').contains(status))return;
    try{
      const state=await request('/api/research-status?id='+encodeURIComponent(ident));
      status.replaceChildren();
      if(state){
        const hooks={};
        if(['working','pausing','stopping'].includes(state.state)){
          if(state.state==='working')hooks.pause=()=>control('pause');
          if(state.state!=='stopping')hooks.stop=()=>control('stop');
        }else if(state.state==='complete')hooks.use=()=>control('preview');
        else if(state.state==='paused')hooks.resume=()=>control('resume');
        else if(['failed','stopped'].includes(state.state))hooks.retry=()=>control('retry');
        status.append(StudioResearch.progress({...state.progress,phase:state.state==='complete'?'complete':state.state==='working'?state.progress.phase:state.state,timing:{...state.progress.timing,elapsed_seconds:state.elapsed_seconds}},hooks));
        if(state.problem)status.append(make('p','problem',state.problem));
        if(['working','pausing','stopping'].includes(state.state))setTimeout(poll,1500);
      }
    }catch(f){problem.textContent=f.message;}
  }
  const start=button('Start research',async()=>{
    if(!editor.valid(primary)){problem.textContent='Add readable sources or allow additional external search first.';return;}
    start.disabled=true;problem.textContent='';
    try{await request('/api/research-job',{id:ident,expected_revision:revision,research_inputs:editor.spec()});await poll();}
    catch(f){problem.textContent=f.message;}finally{start.disabled=false;}
  },true);
  sheet('Research this topic',make('p','quiet','Optional: collect evidence, combine findings, then independently check the report. Your infographic stays unchanged until you choose Use research and import the preview.'),editor.node,start,status,problem,detail('Already have reviewed research?',button('Import a reviewed case',researchImportSheet)),button('Done',closeSheet));
  await poll();
}
async function researchImportSheet(){
  const mode=field('Research source mode','selected','select');for(const[value,label]of[['selected','Supplied documents only'],['mixed','Supplied documents and public sources'],['public','Public sources']]){const option=make('option','',label);option.value=value;mode.input.append(option);}mode.input.value='selected';
  const task=make('pre','ig-csv-preview'),path=field('Reviewed Harness Research case folder'),problem=make('p','problem');
  async function show(){try{task.textContent=JSON.stringify(await request('/api/research-task?id='+encodeURIComponent(held.project.id)+'&source_mode='+mode.input.value),null,2);}catch(f){problem.textContent=f.message;}}
  mode.input.addEventListener('change',show);await show();
  const go=button('Verify and preview reviewed research',async()=>{go.disabled=true;try{const preview=await request('/api/research-preview',{id:held.project.id,expected_revision:held.project.revision,case:path.input.value,source_mode:mode.input.value});sourceImportSheet(preview);}catch(f){problem.textContent=f.message;}finally{go.disabled=false;}},true);
  sheet('Use reviewed research',make('p','','Optional: give this purpose-led task to Harness Research, then import its complete independently reviewed case. This screen starts no research or public search.'),mode.wrap,detail('Infographic research task',task),path.wrap,problem,add(make('div','bar'),go,button('Cancel',closeSheet)));
}
// Shared settings own the team repository. Going there keeps this infographic and this
// sheet to come back to; nothing connects until the person asks again.
function sharedSettingsLink(label,part){
  const link=make('a','button',label);
  link.href='/onboarding/#token='+encodeURIComponent(token)+'&view=settings'+(part?'&part='+encodeURIComponent(part):'');
  link.addEventListener('click',()=>{try{sessionStorage.setItem('infographic-studio-return',JSON.stringify({project:held?.project.id||'',sheet:part==='workspace-part'?'team':''}));}catch(f){}});
  return link;
}
function syncedWords(value){
  const when=value?new Date(value):null;
  return when&&!isNaN(when)?'Last synced '+when.toLocaleString([], {dateStyle:'medium',timeStyle:'short'})+'.':'Not synced yet.';
}
async function teamSheet(){
  const problem=make('p','problem'),items=make('div','stack'),summary=make('div','stack');problem.setAttribute('role','alert');
  const explain=detail('What connecting and sharing do',list(['Connect or sync copies the team library into a private folder on this computer. Nothing of yours is sent.','Share selected files, from an approved infographic, sends only the files you review and confirm.','Opening this library or changing its repository never shares a draft, source or artwork.']));
  const configure=sharedSettingsLink('Configure shared repository','workspace-part');
  const failed=failure=>{problem.textContent=failure.message;problem.hidden=false;};
  let sync=null;
  async function connect(){sync.disabled=true;problem.hidden=true;try{await request('/api/team',{operation:'connect'});await show();toast('Team library synced.');}catch(f){failed(f);sync.textContent='Retry connection';}finally{sync.disabled=false;}}
  async function show(){
    let state;
    try{state=await request('/api/team');}catch(f){failed(f);return;}
    items.replaceChildren();
    if(!state.configured){
      configure.classList.add('button-filled');
      summary.replaceChildren(stateLine('review','No shared repository yet'),
        make('p','','The Team library uses the shared repository in shared settings. Choose Shared repository under Your workspace, save, and come back here to connect.'),
        make('p','quiet','Other studios keep their work in that repository too. Infographic Studio keeps its own work in your local workspace.'),
        ...(state.problem?[make('p','problem',state.problem)]:[]),add(make('div','bar'),configure),explain);
      return;
    }
    configure.classList.remove('button-filled');configure.textContent='Change shared repository';
    sync=button(state.connected?'Sync team library':'Connect team library',connect,true);
    summary.replaceChildren(stateLine(state.connected?'done':'review',state.connected?'Connected':'Not connected yet'),
      make('p','','Repository: '+state.repository+' · branch '+state.branch),
      make('p','quiet',state.connected?syncedWords(state.synced_at)+' The list below is your last synced copy; syncing again is explicit.':'Connect to copy the team library to this computer.'),
      add(make('div','bar'),sync,configure),explain);
    if(state.workspace_owner)items.append(make('p','quiet','Your workspace owner ID: '+state.workspace_owner));
    if(state.pending)items.append(add(make('div','stack'),make('p','',state.pending===1?'One shared commit has not reached the team repository.':state.pending+' shared commits have not reached the team repository.'),button('Retry pending team push',async()=>{try{await request('/api/team',{operation:'retry',expected_commit:state.head});await show();}catch(f){failed(f);}})));
    if(state.connected&&!state.items.length)items.append(make('p','quiet','No infographics are shared yet. Share one from an approved delivery.'));
    for(const entry of state.items){
      const cardNode=card(entry.title,make('p','quiet','Shared revision '+entry.revision+' · driver '+entry.claim.owner),list([...entry.missing.map(f=>'Missing or changed: '+f),...(entry.unshared_sources||[]).map(f=>'Private source not shared: '+f),...(entry.unshared_assets||[]).map(f=>'Private artwork not shared: '+f)]));
      const pdf=entry.files.find(f=>f.file==='delivery/page.pdf');if(pdf)cardNode.append(button('Download shared PDF',()=>downloadShared(entry,'pdf')));
      cardNode.append(button('Take over this shared infographic',async()=>{try{await request('/api/team',{operation:'claim',id:entry.id,expected_head:state.head,expected_claim:entry.claim});await show();}catch(f){failed(f);}}));
      if(entry.editable)cardNode.append(button('Import claimed editable copy',async()=>{try{const result=await request('/api/team',{operation:'take',id:entry.id,expected_head:state.head,expected_claim:entry.claim});closeSheet();await openProject(result.project.id);if(result.missing_sources.length||result.missing_assets.length)error('Editable copy imported without approval. Some private sources or artwork were not shared; supply them before rebuilding.');}catch(f){failed(f);}}));
      const owner=field('New driver workspace owner ID');cardNode.append(detail('Hand over to a teammate',owner.wrap,button('Hand over shared driver',async()=>{try{await request('/api/team',{operation:'claim',id:entry.id,expected_head:state.head,expected_claim:entry.claim,new_owner:owner.input.value});await show();}catch(f){failed(f);}})));items.append(cardNode);
    }
  }
  problem.hidden=true;
  sheet('Team library',summary,problem,items,add(make('div','create-foot bar'),button('Done',closeSheet)));await show();
}
async function shareSheet(delivery){
  const editable=make('input');editable.type='checkbox';const include=add(make('label','check'),editable,document.createTextNode('Include editable project (private brief, facts and source metadata)'));
  const picks=make('div','stack'),sourceIds=new Set(),assetIds=new Set();
  for(const[kind,records,selected]of[['source',held.project.sources,sourceIds],['artwork',held.project.assets,assetIds]])for(const record of records){const check=make('input');check.type='checkbox';check.disabled=true;editable.addEventListener('change',()=>{check.disabled=!editable.checked;if(!editable.checked){check.checked=false;selected.clear();}});check.addEventListener('change',()=>{if(check.checked)selected.add(record.id);else selected.delete(record.id);});picks.append(add(make('label','check'),check,document.createTextNode('Include private '+kind+': '+(record.name||record.id))));}
  const problem=make('p','problem');const preview=button('Review exact files to share',async()=>{preview.disabled=true;try{
    const selection={export_id:delivery.id,include_editable:editable.checked,source_ids:[...sourceIds],asset_ids:[...assetIds]};
    const result=(await request('/api/action',{action:'team-preview',id:held.project.id,expected_revision:held.project.revision,...selection})).result;
    const confirm=make('input');confirm.type='checkbox';const send=button('Share these files',()=>{if(selection.include_editable&&!confirm.checked){error('Confirm the displayed private inventory before sharing.');return;}action('team-share',{...selection,inventory_digest:result.inventory_digest,expected_head:result.expected_head,expected_claim:result.expected_claim,expected_connection:result.expected_connection,confirm_private:confirm.checked});},true);
    sheet('Confirm team sharing',make('p','','Only these files are committed and pushed to the configured team repository. Prompts and image job records are excluded.'),list(result.files.map(f=>f.file+' · '+f.bytes+' bytes')),selection.include_editable?add(make('label','check'),confirm,document.createTextNode('I am allowed to share the selected private project, sources and artwork.')):make('p','quiet','Approved delivery and title only.'),add(make('div','bar'),send,button('Cancel',closeSheet)));
  }catch(f){problem.textContent=f.message;}finally{preview.disabled=false;}},true);
  sheet('Select files to share',make('p','','Default: the approved delivery and its title. Optional editable content needs separate selection. Connect the team library first.'),include,picks,problem,add(make('div','bar'),preview,button('Open team library',teamSheet),button('Cancel',closeSheet)));
}
async function downloadShared(entry,format){try{const response=await fetch('/api/team-download?id='+encodeURIComponent(entry.id)+'&format='+format,{headers:{'X-Infographic-Studio-Token':token}});if(!response.ok)throw Error('This shared delivery is unavailable.');const url=URL.createObjectURL(await response.blob());const link=make('a');link.href=url;link.download=entry.title+'.'+format;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(f){error(f.message);}}
