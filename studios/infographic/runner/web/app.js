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
// The open infographic's toolbar primary action: the page shows that control at most once more.
let primary = '';
const draft = {research_first:false, materials: [], library: [], imported: [], step: 0, title: '', text: '', direction: 'suggest', audience: '', purpose: '', must: '', locked: '', exclusions: '', preset: 'a4'};
// One problem, said once: in the open sheet when there is one, otherwise in the notice above
// the page, which sits in the page's flow (so it covers nothing) and has its own Dismiss.
let lastError = '';
function error(message) {
  lastError = message || '';
  const inSheet = !!message && $('sheet').open;
  for (const node of document.querySelectorAll('[data-work-error]')) { node.textContent = inSheet ? message : ''; node.hidden = !inSheet; }
  const notice = $('notice');
  if (!message || inSheet) { notice.hidden = true; notice.replaceChildren(); return; }
  const dismiss = button('Dismiss', () => error('')); dismiss.dataset.free = '';
  notice.replaceChildren(make('span', 'ig-notice-text', message), dismiss);
  notice.hidden = false;
  showNotice();
}
// Bring the notice fully into view below the sticky toolbar, never under it.
function showNotice() {
  const notice = $('notice'); if (notice.hidden) return;
  const box = notice.getBoundingClientRect(), below = document.querySelector('.toolbar-wrap').getBoundingClientRect().bottom;
  if (box.top < below + 8 || box.bottom > innerHeight) scrollTo(0, Math.max(0, scrollY + box.top - below - 12));
}
// The shared toast: it slides in, is read out once and leaves by itself after 4.2 seconds,
// straight away when motion is reduced, as in Presentation Studio and shared setup.
const calm = () => matchMedia('(prefers-reduced-motion: reduce)').matches;
function toast(message) {
  const node = make('p', 'toast glass', message); $('toasts').append(node);
  while ($('toasts').children.length > 3) $('toasts').firstElementChild.remove();
  setTimeout(() => { node.classList.add('toast-leaving'); setTimeout(() => node.remove(), calm() ? 0 : 260); }, 4200);
}
function button(label, action, primary=false) { const node = make('button', 'button' + (primary ? ' button-filled' : ''), label); node.type = 'button'; node.addEventListener('click', action); return node; }
// A field's own problem: beside it, announced once, with the field marked invalid and
// described by it. An empty message clears it. Returns false when a problem is shown.
function invalid(f, message) {
  f.wrap.querySelector('.ig-field-error')?.remove();
  const described = (f.input.getAttribute('aria-describedby') || '').split(' ').filter(id => id && id !== f.input.id + '-error');
  if (!message) { f.input.removeAttribute('aria-invalid'); if (described.length) f.input.setAttribute('aria-describedby', described.join(' ')); else f.input.removeAttribute('aria-describedby'); return true; }
  const note = make('span', 'problem ig-field-error', message); note.id = f.input.id + '-error'; note.setAttribute('role', 'alert');
  f.wrap.append(note); f.input.setAttribute('aria-invalid', 'true'); f.input.setAttribute('aria-describedby', [...described, note.id].join(' '));
  f.input.focus(); return false;
}
function card(title, ...parts) { return add(make('section', 'card stack'), make('h2', 'card-title', title), ...parts); }
function detail(title, ...parts) { return add(make('details'), make('summary', '', title), ...parts); }
let fieldNumber = 0;
function field(label, value='', kind='input') { const wrap = make('label', 'field'); const input = make(kind, 'input'); input.value = value; const caption=make('span','field-label',label);caption.id='field-caption-'+(++fieldNumber);input.id='field-'+fieldNumber;wrap.htmlFor=input.id;input.setAttribute('aria-labelledby',caption.id);add(wrap, caption, input); return {wrap, input}; }
function stateLine(kind,words){const bead=make('span','bead');bead.dataset.state=kind;bead.setAttribute('aria-hidden','true');return add(make('p','state'),bead,document.createTextNode(words));}
function lines(value) { return value.split('\n').map(v => v.trim()).filter(Boolean); }
function list(items) { return add(make('ul'), ...items.map(item => make('li', '', item))); }
// A sheet: the shared sticky heading at its top and, when its last part is a bar of actions,
// a sticky foot, so the main action and Cancel stay in reach on a phone.
function foot(...controls) { return add(make('div', 'ig-sheet-foot'), add(make('div', 'create-foot bar'), ...controls.filter(Boolean))); }
function sheet(title, ...nodes) {
  const heading = make('h2', 'sheet-title', title); heading.id = 'sheet-title';
  const status=make('section','callout ig-work');status.dataset.workStatus='';status.setAttribute('role','status');status.setAttribute('aria-live','polite');
  const problem=make('p','problem');problem.dataset.workError='';problem.hidden=true;problem.setAttribute('role','alert');
  const parts = nodes.filter(node => node != null && node !== false);
  const last = parts.at(-1);
  if (last?.classList?.contains('bar') && !last.closest?.('.ig-sheet-foot')) parts[parts.length - 1] = add(make('div', 'ig-sheet-foot'), last);
  $('sheet-body').replaceChildren(add(make('div', 'ig-sheet stack'), add(make('div', 'ig-sheet-top'), add(make('div', 'sheet-heading'), heading)), status, problem, ...parts));
  if (!$('sheet').open) $('sheet').showModal(); paintWork();
}
// The one number a person is told for a saved revision: its page revision (history.Pages).
// Checks, reviews and approvals save revisions of their own but leave the page as it was.
function pageOf(saved){return saved?.page_revision??saved?.revision;}
function closeSheet() { $('sheet').close(); paintWork(); }
// Long work belongs to one infographic. While it runs, only that infographic's conflicting
// controls are locked: the sidebar, Home, Settings and other infographics stay usable, and
// Stop waiting leaves the work running on this computer. `running` holds the work this tab is
// waiting on, by infographic ID; `reading` is a sheet's own short read (a linked document).
const running = new Map();
let reading = null, workTimer = null;
// Which screen is showing, so finished work never pulls the person back to it.
let screen = 'home';
function shownWork() { return reading || (held && running.get(held.project.id)) || null; }
const workLabels = {'suggest':'Finding the story','build':'Building the page','art-direct':'Writing the art direction','image-start':'Generating artwork','inspect-images':'Inspecting the page','revise-story':'Revising the story','revise-art':'Revising the artwork','repair':'Repairing the page','preview':'Rendering the preview','export':'Preparing your files','google-deliver':'Delivering the Google Doc'};
workLabels['image-recover']='Recovering saved artwork locally';
workLabels['visual-layout']='Building the visual diagram layout';
workLabels['approve']='Approving and preparing your files';
workLabels['review']='Recording your review and running checks';
const WAITING='This can take a few minutes. You can stop waiting and come back: the work keeps running on this computer, and your saved work is kept.';
function paintWork() {
  const work=shownWork();
  $('main').setAttribute('aria-busy',String(!!work));
  for(const surface of document.querySelectorAll('[data-work-status]')) {
    const inSheet=$('sheet').contains(surface),show=!!work&&(!$('sheet').open||inSheet);
    surface.hidden=!show;if(!show)continue;
    const signature=work.label+'|'+work.detail+'|'+(work.pending||'')+'|'+(work.id||'');
    if(surface.dataset.message!==signature) {
      surface.dataset.message=signature;
      const bead=make('span','bead');bead.dataset.state=work.connected?'current':'review';bead.setAttribute('aria-hidden','true');
      const clock=make('span','quiet ig-work-clock');clock.dataset.workClock='';clock.setAttribute('aria-hidden','true');
      surface.replaceChildren(add(make('div','ig-work-heading'),bead,make('strong','',work.label),clock),make('p','quiet',work.detail));
      const controls=make('div','bar');
      // Stop waiting leaves the work running; nothing is cancelled or repeated.
      if(work.id&&!work.quiet){const stop=button('Stop waiting',()=>{closeSheet();void home();});stop.dataset.free='';controls.append(stop);}
      if(work.cancel){const cancel=button('Cancel this request',work.cancel);cancel.dataset.free='';controls.append(cancel);}
      if(controls.childElementCount)surface.append(controls);
    }
    const seconds=Math.max(0,Math.floor((Date.now()-work.started)/1000));
    surface.querySelector('[data-work-clock]').textContent=Math.floor(seconds/60)+':'+String(seconds%60).padStart(2,'0')+' elapsed';
  }
  guard();
}
// Lock the open infographic's own controls while its work runs, and release them after.
// Navigation, Stop waiting, the view controls and the downloads (immutable files) stay free.
function guard() {
  const busyHere=!!(held&&running.has(held.project.id));
  for(const node of document.querySelectorAll('#actions button, #main button, #sheet button')){
    if(node.dataset.free!==undefined)continue;
    if(busyHere&&node.dataset.locked===undefined){node.dataset.locked=node.disabled?'1':'';node.disabled=true;}
    else if(!busyHere&&node.dataset.locked!==undefined){node.disabled=node.dataset.locked==='1';delete node.dataset.locked;}
  }
}
function free(node){node.dataset.free='';return node;}
// `id` names the infographic the work belongs to; without one it is a sheet's own read.
function beginWork(label, elapsed=0, id=null) {
  const owner={label,id,started:Date.now()-elapsed*1000,connected:true,detail:id?WAITING:'This can take a few minutes. Your saved work is kept.',title:held?.project.id===id?held.project.brief.title:''};
  if(id)running.set(id,owner);else reading=owner;
  if(!workTimer)workTimer=setInterval(paintWork,1000);
  paintWork();return owner;
}
function endWork(owner) {
  if(owner.id&&running.get(owner.id)===owner)running.delete(owner.id);
  if(reading===owner)reading=null;
  if(!running.size&&!reading){clearInterval(workTimer);workTimer=null;}
  paintWork();
}
function connectionUncertain(owner) { owner.connected=false;owner.label='Checking the connection';owner.detail='The connection was interrupted. Work may still be running on this computer. No request was repeated.';paintWork(); }
// Briefly locks every control, navigation too, for a short sheet-bound request.
function lockControls() {
  const controls=[...document.querySelectorAll('button')].map(node=>[node,node.disabled]);controls.forEach(([node])=>node.disabled=true);
  return ()=>controls.forEach(([node,disabled])=>node.disabled=disabled);
}
// Finished work for an infographic the person has left: say so where they are, and
// refresh Home's cards. They open it themselves to see the result.
function elsewhere(owner,problem) {
  const name='“'+(owner.title||'Your infographic')+'”';
  if(problem)error(name+' could not finish: '+problem);else toast(name+' is ready. Open it to see the result.');
  if(screen==='home')void drawHome();
}
function progressNotice(progress,owner,id) {
  if(running.get(id)!==owner)return;
  const current=progress.activity;
  if(current?.state==='running'){owner.label=current.label;owner.started=Date.now()-current.elapsed_seconds*1000;owner.connected=true;owner.detail=WAITING;paintWork();}
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
function here(id){return screen==='project'&&held?.project.id===id;}
async function resumeActivity(id,current) {
  if(running.has(id))return;
  const owner=beginWork(current.label,current.elapsed_seconds,id);
  try{const result=await recoverActivity(id,owner);
    if(here(id)){await openProject(id);recoveredNotice(result);}
    else elsewhere(owner,['complete','outdated'].includes(result?.state)?'':(result?.problem||'The earlier outcome could not be confirmed. Open it to check the saved work.'));
  }catch(f){if(here(id))error(f.message);else elsewhere(owner,f.message);}finally{endWork(owner);}
}
async function request(route, data) {
  const labels={'/api/remote-preview':'Reading the linked document','/api/source-preview':'Reading the uploaded file','/api/research-preview':'Reading the selected research'};
  const owner=!shownWork()&&data!==undefined&&labels[route]?beginWork(labels[route]):null;
  try{const response = await fetch(route, {method: data === undefined ? 'GET' : 'POST', headers: {'X-Infographic-Studio-Token': token, ...(data === undefined ? {} : {'Content-Type': 'application/json'})}, ...(data === undefined ? {} : {body: JSON.stringify(data)})});
    const answer = await response.json(); if (!response.ok){const failure=Error(answer.error || 'This request could not be completed.');failure.status=response.status;throw failure;}return answer;
  }finally{if(owner)endWork(owner);}
}
// Normalized image outcomes. Each says what happened and the next safe step; nothing is retried.
// When saved artwork was found, every surface leads with that (image_jobs.FOUND): the notice,
// Image work needs attention, Where this stands and the usage row.
const imageFound='The image was made but not handed back. Choose Recover saved artwork to place it on the page on this computer, without a new image request.';
const imageUncertain='This image request has not said how it ended, and no saved artwork was found on this computer. Nothing was resent. Cancel it under Image work needs attention before starting new image work.';
const imageProblems={
  'image-tool-unavailable':'The image worker finished without handing back an image, and no saved artwork was found on this computer. Your installed Codex may not offer its image tool here. Nothing was resent.',
  'sign-in-required':'Sign in to your selected assistant on this computer, then start the image request again. Your earlier work is kept.',
  'quota':'The image provider reported a usage or rate limit. Your earlier work is kept. Try again when your allowance resets.',
  'invalid-asset':'The returned image was not a usable PNG, so it was not added. Your earlier work is kept.',
  'gemini-key-required':'Set GEMINI_API_KEY in the server launch environment before starting image work.',
  'image-model-unavailable':'Choose a Gemini image model available to your account in Settings.'
};
// One image request in words: which provider did what, and how it ended. Saved artwork that
// was found or recovered is said first, as Image work needs attention says it.
function usageWords(a){
  const who=({codex:'Codex',gemini:'Gemini'}[a.provider]||a.provider)+' '+({generate:'image generation',edit:'reference edit'}[a.operation]||'image request');
  const how=a.recovered?'recovered from saved artwork on this computer, without a new request'
    :a.local_artwork_available?'the image was made but not handed back; saved artwork was found on this computer'
    :({queued:'waiting to start',running:'running now',complete:'finished',failed:'did not hand back an image',cancelled:'cancelled','cancelled locally':'cancelled on this computer',unknown:'has not said how it ended','pending or interrupted':'pending or interrupted'}[a.state]||'outcome not recorded');
  return who+': '+how+'.';
}
// What a finished action did, in words, once the infographic has been read again.
function finished(verb){
  const n=held?.page_revision;
  return {'image-recover':'Recovered the saved artwork on this computer and placed it on the page, revision '+n+'. No new image request was made.',
    'preview':'Preview updated: it shows revision '+n+'.','check':'Checks ran for revision '+n+'.',
    'review':'Review recorded and checks ran for revision '+n+'.','inspect-images':'Your assistant inspected revision '+n+' and the checks ran.',
    'export':'Approved files are ready for revision '+n+'.','approve':'You approved revision '+n+'.','build':'Page built: revision '+n+'.',
    'visual-layout':'Visual layout rebuilt: revision '+n+'.','layout':'Layout changed: revision '+n+'.',
    'select':'Story chosen. Build the page when you are ready.','suggest':'Stories proposed. Choose one to build.',
    'restore':'Restored as revision '+n+'. Approval is not restored.','image-cancel':'The image request was cancelled on this computer. Remote charges may remain unknown.'}[verb]||'Saved.';
}
async function action(verb, values={}, revision=null, options={}) {
  const id = held.project.id; if (running.has(id)) return; error('');
  const label=verb==='suggest'&&held.planning_response?.available&&!values.fresh?'Checking the saved proposal':workLabels[verb];
  // A quiet action is short and belongs to an open sheet that reads its result, so it keeps
  // every control still until it returns.
  const unlock=options.quiet?lockControls():()=>{},owner=beginWork(label||'Saving your changes',0,id);
  if(options.quiet){owner.quiet=true;owner.detail='This can take a moment. Your saved work is kept.';paintWork();}
  let checking=false;
  const polling=setInterval(async()=>{if(checking)return;checking=true;try{progressNotice(await request('/api/activity?id='+encodeURIComponent(id)),owner,id);}catch(f){connectionUncertain(owner);}finally{checking=false;}},2000);
  try {
    const answer = await request('/api/action', {action:verb, id, expected_revision:revision??held.project.revision, ...values});
    if(!options.quiet&&!here(id)){const result=answer.result,state=result?.state;elsewhere(owner,['unknown','failed'].includes(state)?(imageProblems[result.reason]||imageUncertain):'');return result;}
    clearInterval(polling);
    closeSheet(); await openProject(id); if(options.quiet)return answer.result;
    const found=held?.recovery?.some(r=>r.local_artwork_available);
    if(['unknown','failed'].includes(answer.result?.state)&&found)error(imageFound);
    else if(answer.result?.state==='unknown')error(imageUncertain);
    else if(answer.result?.state==='failed')error(imageProblems[answer.result.reason]||'The image provider could not finish. Your earlier work is kept.');
    else if(answer.result?.state==='outdated')toast('The earlier result was kept privately and did not replace newer work.');
    else toast(finished(verb));
    return answer.result;
  } catch (failure) {
    if(workLabels[verb]&&(!failure.status||failure.status>=500)){
      clearInterval(polling);connectionUncertain(owner);
      try{const result=await recoverActivity(id,owner);
        if(!here(id))elsewhere(owner,['complete','outdated'].includes(result?.state)?'':(result?.problem||failure.message));
        else{await openProject(id);if(result)recoveredNotice(result);else error(failure.message);}
      }catch(f){if(here(id))error(f.message);else elsewhere(owner,f.message);}
    }else if(here(id)||options.quiet){await openProject(id);error(failure.message);}
    else elsewhere(owner,failure.message);
  }
  finally { clearInterval(polling); endWork(owner);unlock(); }
}
function heading(title, ...actions) { for(const id of ['home','settings']){if((id==='settings')===title.startsWith('Settings'))$(id).setAttribute('aria-current','page');else $(id).removeAttribute('aria-current');} $('title').textContent = title; $('actions').replaceChildren(...actions); $('title').focus({preventScroll:true}); }
function resetPicture() { if (picture) URL.revokeObjectURL(picture); picture = null; pictureFor = ''; }
function reviewCapturedSources(){
  const section=[...$('main').querySelectorAll('details')].find(node=>node.firstElementChild?.textContent==='Sources and facts');
  if(section){error('');section.open=true;section.scrollIntoView({block:'start'});section.firstElementChild.focus();}
}
// Where the person is, kept in this tab so a reload returns there: the screen, the open
// infographic, its scroll position and open sections.
function remember(where){screen=where;try{sessionStorage.setItem('infographic-studio-screen',where);}catch(f){}}
function keepPlace(){
  if(screen!=='project'||!held)return;
  const open=[...$('main').querySelectorAll('details[open] > summary')].map(s=>s.textContent);
  try{sessionStorage.setItem('infographic-studio-place',JSON.stringify({id:held.project.id,y:Math.round(scrollY),open}));}catch(f){}
}
let placeTimer=null;
window.addEventListener('scroll',()=>{clearTimeout(placeTimer);placeTimer=setTimeout(keepPlace,250);},{passive:true});
window.addEventListener('pagehide',keepPlace);
function returnToPlace(id){
  let place=null;try{place=JSON.parse(sessionStorage.getItem('infographic-studio-place')||'null');}catch(f){}
  if(!place||place.id!==id)return;
  const open=new Set(Array.isArray(place.open)?place.open:[]);
  for(const summary of $('main').querySelectorAll('details > summary'))if(open.has(summary.textContent))summary.parentElement.open=true;
  if(typeof place.y==='number')requestAnimationFrame(()=>requestAnimationFrame(()=>scrollTo(0,place.y)));
}
let homeTimer=null;
async function home() {
  resetPicture(); held = null; error(''); remember('home');
  heading('Infographics', button('New infographic', () => newSheet(), true),button('Team repository',teamSheet));
  delete $('main').dataset.home;
  await drawHome();
}
// Home's cards, with the work each infographic is doing now. While any runs, the cards are
// read again every few seconds; reading starts and repeats nothing.
async function drawHome() {
  clearTimeout(homeTimer);
  if (screen !== 'home') return;
  try {
    const data = await request('/api/projects');
    if (screen !== 'home') return;
    // Redraw only when something a card says has changed, so focus and place stay put.
    const said = JSON.stringify(data.projects.map(p => [p.id, p.title, p.problem, p.page_revision, p.readiness, p.activity?.state, p.activity?.label, running.has(p.id)]));
    if ($('main').dataset.home === said) { if (data.projects.some(p => p.activity?.state === 'running' || running.has(p.id))) homeTimer = setTimeout(drawHome, 2000); return; }
    $('main').dataset.home = said;
    const cards = data.projects.map(p => {
      const working=p.activity?.state==='running'||running.has(p.id);
      const state=working?stateLine('current','Working now: '+(p.activity?.label||running.get(p.id)?.label||'Working')):stateLine(p.readiness?.state||'current',p.readiness?.summary||'Saved');
      const node=card(p.title || 'Unreadable infographic', ...(p.problem?[make('p','problem',p.problem)]:[state,make('p','quiet','Revision '+pageOf(p))]), button('Open ' + (p.title || p.id), () => openProject(p.id)));
      node.classList.add('ig-project-card'); if(working)node.dataset.working=''; return node;
    });
    const intro=add(make('div','intro'),make('h2','large-title','Your infographics'),make('p','lede','Turn supplied information into one clear page.'));
    $('main').replaceChildren(intro, add(make('div','ig-project-list'),...cards));
    if (!cards.length) $('main').append(card('Make your first infographic', make('p','','Add notes, choose what matters, and review the page before exporting.')));
    if (cards.some(node => node.dataset.working !== undefined)) homeTimer = setTimeout(drawHome, 2000);
  } catch (failure) { error(failure.message); }
}
async function bytes(file) { if (file.size > 16_000_000) throw Error('Choose a source no larger than 16 MB.'); return new Uint8Array(await file.arrayBuffer()); }
function encoded(raw) { let binary=''; for (const v of raw) binary += String.fromCharCode(v); return btoa(binary); }
function retain(input, key) { input.addEventListener('input', () => { draft[key] = input.value; }); }
async function newSheet() {
  error('');
  // Two steps, each headed as a part of the sheet. The studio says what is missing beside the
  // field itself, rather than leaving it to the browser's own check.
  if (draft.step > 1) draft.step = 1;
  const form = make('form', 'create-flow'); form.noValidate = true;
  const names = ['1. Add information', '2. Set the direction and page'];
  add(form, make('h3','sheet-part',names[draft.step]));
  const problem = make('p', 'problem'); problem.setAttribute('role','alert');
  let title = null;
  if (draft.step === 0) {
    title = field('Working title',draft.title); const text = field('Notes or text',draft.text,'textarea'); text.input.classList.add('ig-source-input');
    retain(title.input,'title'); retain(text.input,'text'); add(form,title.wrap,text.wrap);
    title.input.addEventListener('input',()=>{if(title.input.value.trim())invalid(title,'');});
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
    const fromLibrary=button('Add from Document Library',()=>libraryPick(draftLibrary).then(done=>{if(done){closeSheet();newSheet();}}));fromLibrary.dataset.key='ig-new-library';form.append(fromLibrary);
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
    const preset=field('Page size',draft.preset,'select');for(const [value,label] of [['a4','A4 portrait — 210 × 297 mm'],['letter','US Letter portrait — 8.5 × 11 in'],['digital','Digital portrait — 1080 × 1350 px']]) { const option=make('option','',label);option.value=value;preset.input.append(option); }preset.input.value=draft.preset;retain(preset.input,'preset');add(form,preset.wrap);
    try { preferences=await request('/api/preferences'); const capability=await request('/api/computer'); add(form,make('p','',capability.disclosure),make('p','quiet','Brand: '+(preferences.brand.brand || 'Choose in shared settings before composing.')),make('p','quiet','Saving this brief starts no assistant, image generation or installation.')); } catch(failure) {problem.textContent=failure.message;}
  }
  const go=button(draft.step===1?'Save brief':'Continue',()=>{},true);go.type='submit';
  form.addEventListener('submit',async event=>{event.preventDefault();problem.textContent='';
    if(draft.step===0 && !draft.title.trim()) {invalid(title,'Give this infographic a working title.');return;}
    if(draft.step===0 && !draft.research_first && !draft.text.trim() && !draft.upload && !draft.materials.length && !draft.library.length) {problem.textContent='Add some information: paste notes, upload a file, add a document, or choose Research this topic first.';return;}
    if(draft.materials.some(m=>!m.preview.readable || (m.preview.warnings.length&&!m.acknowledged)) || draft.library.some(one=>one.gaps.length&&!one.acknowledged)) {problem.textContent='Review the file previews and acknowledge readable-only coverage, or remove unreadable files.';return;}
    if(draft.step===0 && draft.materials.reduce((n,m)=>n+m.preview.characters, draft.library.reduce((n,one)=>n+one.characters,draft.text.length))>120000){problem.textContent='Choose smaller files or explicit excerpts within 120,000 readable characters for one story-planning job. Nothing was sent to an assistant.';return;}
    if(draft.upload?.kind==='csv' && !draft.selection) {problem.textContent='Preview and confirm the CSV selection first.';return;}
    if(draft.step<1) {draft.step++;closeSheet();newSheet();return;}
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
  add(form,problem,draft.created||draft.request_id?button('Open the saved draft',()=>{closeSheet();openProject(draft.created?.id||draft.request_id);}):null,foot(go,draft.step?button('Back',()=>{draft.step--;closeSheet();newSheet();}):null,button('Cancel',closeSheet))); sheet('New infographic',form);
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
  try { if(held?.project.id!==id)resetPicture(); const found=await request('/api/desk?id='+encodeURIComponent(id));
    clearTimeout(homeTimer);held=found;remember('project');renderProject();
    try{sessionStorage.setItem('infographic-studio-project',id);}catch(f){}
    // Work this tab is already waiting on shows its own progress; work found running after a
    // reload, or started elsewhere, is followed without being started again.
    if(!running.has(id)&&held.activity?.state==='running')void resumeActivity(id,held.activity);
    else if(!running.has(id)&&held.activity?.state==='failed'&&held.activity.problem)error(held.activity.problem);
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
  // One rule picks the toolbar's primary action, and Needs you always names it: the stage's
  // action from the roadmap, unless saved artwork, an older plan or layout comes first.
  const run={
    story:()=>action('suggest'),
    choose:()=>document.querySelector('#story-choice').scrollIntoView({behavior:'smooth'}),
    build:compose, preview:()=>action('preview'), review:()=>reviewSheet(currentDelivery),
    check:()=>action('check'), approve:approveRevision, export:()=>action('export',{draft:false}),
    deliver:()=>approvedFiles&&deliverySheet(approvedFiles)};
  let next=[held.roadmap?.action||'Find the story',run[stage]||run.story],needs=held.roadmap?.needs||'Find the story: your assistant proposes source-backed explanations.';
  if(savedPlan&&(!stage||stage==='story')){next=['Check saved proposal',()=>action('suggest')];needs='Check saved proposal: it is checked on this computer, without using assistant allowance.';}
  if(p.scene&&needsArtwork){next=['Build page',compose];needs='Build page: this page still needs its artwork.';}
  if(selected&&!nativeReady&&(!p.scene||!p.scene.visual_version)){next=['Make this story visual',()=>reviseStorySheet(selected,true)];needs='Make this story visual: its labels are too long for diagrams, so your assistant suggests a visual plan first.';}
  else if(selected&&p.scene&&!p.scene.visual_version){next=['Rebuild visual layout',()=>action('visual-layout')];needs='Rebuild visual layout: this page uses an older layout. Rebuilding runs on this computer.';}
  const recoverable=held.recovery.find(r=>r.local_artwork_available),uncertain=held.recovery.find(r=>!r.local_artwork_available);
  // New image work is refused while a request is uncertain, so cancelling it comes first.
  if(uncertain&&!recoverable){next=['Cancel uncertain request',()=>action('image-cancel',{request_id:uncertain.attempt_id})];needs='Cancel uncertain request: '+imageUncertain.charAt(0).toLowerCase()+imageUncertain.slice(1).replace(' Cancel it under Image work needs attention before starting new image work.',' New image work can start once it is cancelled.');}
  if(recoverable){next=['Recover saved artwork',()=>action('image-recover',{request_id:recoverable.attempt_id})];needs='Recover saved artwork: '+imageFound.charAt(0).toLowerCase()+imageFound.slice(1).replace(' Choose Recover saved artwork to place',' Recovering places');}
  primary=next[0];
  heading(p.brief.title,free(button('Infographics',home)),button(...next,true));
  const delivery=held.deliveries.find(d=>d.current) || held.deliveries[0];
  const parts=[make('p','lede','Choose the explanation, review the actual page, then approve its exact revision.'),standing(held.roadmap,p,delivery,needs)];
  if(held.recovery.length) parts.push(card('Image work needs attention',...held.recovery.map(r=>add(make('div','stack'),make('p','',r.message),r.local_artwork_available?button('Recover saved artwork',()=>action('image-recover',{request_id:r.attempt_id})):button('Cancel uncertain request',()=>action('image-cancel',{request_id:r.attempt_id}))))));
  if(selected&&((p.scene&&!p.scene.visual_version)||!nativeReady)){
    parts.push(card('Make this a visual infographic',make('p','','Earlier versions and captured facts are kept. A visual plan uses concise labels, diagrams and comparisons rather than paragraph blocks.'),
      button('Make this story visual',()=>reviseStorySheet(selected,true),true),
      nativeReady?button('Rebuild visual layout',()=>action('visual-layout')):make('p','quiet','This older plan uses sentence-length labels. Make a visual plan first so the diagrams remain readable.')));
  }
  if(!p.stories.length)parts.push(savedPlan?card('Planning response saved',make('p','','Check the saved response locally, without using assistant allowance. Asking for a new plan starts a new assistant request.'),held.planning_response.detail?detail('What needs attention',make('p','',held.planning_response.detail)):null,button('Check saved proposal',()=>action('suggest')),button('Review source material',reviewCapturedSources),button('Ask for a new plan',()=>action('suggest',{fresh:true}))):card('Find a useful story',make('p','','Your supplied information is saved. The assistant proposes source-backed explanations; generation is a later explicit action.'),button('Find the story',()=>action('suggest')),detail('Advanced: author in your conversation',make('p','','Your assistant can save located facts and story proposals directly from a conversation, using Infographic Studio’s action JSON, without this page or a nested planning assistant. See docs/conversation.md.'))));
  if(held.planning_response?.problem)parts.push(card('Saved planning response needs attention',make('p','problem',held.planning_response.problem)));
  let chosenStory=null;
  if(p.stories.length){
    const stories=p.stories.map(s=>card(s.headline,storyThumbnail(s),make('p','',s.takeaway),make('p','quiet',s.rationale),list(s.blocks.map(b=>b.title+': '+b.text)),...(s.qualifications.length?[list(s.qualifications)]:[]),s.omissions.length?make('p','problem','Required omissions: '+s.omissions.join(', ')):null,add(make('div','bar'),button('Ask for a revision',()=>reviseStorySheet(s)),button(s.id===p.selected_story?'Selected':'Use this story',()=>action('select',{story_id:s.id}),true))));
    const choices=add(make('section','stack'),make('h2','card-title','Choose the story'),add(make('div','ig-story-grid'),...stories));
    choices.id='story-choice';if(!p.scene)parts.push(choices);else chosenStory=detail('Story: '+selected.headline,choices);
  }
  if(selected && !p.scene)parts.push(card('Make the page',make('p','',p.brand?'Using pinned '+p.brand.identity.name+'.':'Compose with your configured brand. Brand settings are pinned when you choose this action.'),button('Build page',compose)));
  // With a page built, the page comes first and the chosen story waits below it.
  if(delivery||p.scene)parts.push(workbench(p,delivery));
  parts.push(chosenStory);
  if(p.scene) {
    parts.push(detail('Layout alternatives',button('Visual infographic',()=>nativeReady?action('visual-layout'):reviseStorySheet(selected,true)),button('Stacked blocks',()=>action('layout',{arrangement:'stack'})),button('Two columns',()=>action('layout',{arrangement:'columns'}))));
    if(p.scene.art_regions?.length)parts.push(detail('Artwork and image brief',card('Explanatory artwork',button('Revise this artwork',reviseArtSheet),make('p','','Artwork is raster; labels and chart marks stay editable. Review the exact art direction before starting or editing an image.'),...p.assets.map(a=>button('Compose saved image '+a.id,()=>action('compose-image',{asset_id:a.id}))),button('Suggest precise art direction',()=>action('art-direct')),detail('Advanced: write the art direction yourself',button('Describe subjects and relationships',artSheet)),...p.image_briefs.map(b=>detail('Saved image brief',make('pre','ig-csv-preview',b.prompt),button('Generate artwork using selected provider',()=>startImage(b)))))));
    if(delivery?.current)parts.push(finishCard(p,delivery,checked,approved));
  }
  for(const sent of held.google_deliveries||[])parts.push(card((sent.current?'Google delivery':'Earlier Google delivery')+' · revision '+pageOf(sent),sent.url?googleLink(sent.url,'Open delivered Google Doc'):make('p','quiet','Outcome uncertain. Read-only reconciliation checks for the saved request; it never resends.'),sent.url?null:button('Reconcile Google delivery',()=>action('google-deliver',{export_id:sent.export_id,request_id:sent.request_id,account:sent.account,folder:sent.folder,reconcile:true},sent.revision))));
  if(held.visual_review)parts.push(detail('Visual review: '+held.visual_review.status,list(held.visual_review.observations),...held.visual_review.findings.map(f=>card(f.region_id+': '+(f.blocking?'Needs correction':'Suggestion'),make('p','',f.message),make('p','',f.correction)))));
  if(p.checks.length)parts.push(card('Checks for this page',...p.checks.map(c=>add(make('div','stack'),make('strong','',({'coverage':'Required content','facts':'Factual support','layout':'Page layout','brand-accessibility':'Brand and accessibility','visual':'Visual review'}[c.kind]||c.kind)+': '+c.status),list(c.findings || [])))));
  const editBrief=button('Edit brief',()=>briefSheet());editBrief.dataset.key='ig-edit-brief';
  const updateSources=button('Add or update supplied information',()=>sourceSheet());updateSources.dataset.key='ig-source-update';
  const importMaterial=button('Import selected studio material',()=>handoffSheet(preview=>sourceImportSheet(preview,'','ig-source-material')));importMaterial.dataset.key='ig-source-material';
  const research=button('Research this topic',researchSheet);research.dataset.key='ig-research';
  parts.push(detail('Brief and requirements',editBrief,make('p','',p.brief.audience||'Audience not specified'),list(p.brief.must_show.map(r=>r.text))));
  parts.push(detail('Sources and facts',updateSources,importMaterial,libraryAddButton(),make('p','quiet',LIBRARY_CLEARS),research,...p.sources.map(s=>card(s.name||s.id,make('p','quiet',s.characters+' captured characters'),...libraryNote(s),button('Review '+(s.name||s.id),()=>sourceTextSheet(s)))),list(held.source_findings.map(f=>f.message)),...p.facts.map(f=>card(f.statement,make('p','quiet','Supplied assertion; not independently corroborated.'),list((f.evidence||[]).map(q=>q.source_id+' ['+q.start+'–'+q.end+']: '+(q.quote||'')))))));
  if(held.image_history?.length)parts.push(detail('Image requests and usage',...held.image_history.map(a=>add(make('div','stack'),make('p','',usageWords(a)),make('p','quiet',a.usage?'Reported tokens: '+(a.usage.input_tokens??'unknown')+' in / '+(a.usage.output_tokens??'unknown')+' out. Cost: '+(a.usage.cost??'not reported')+'.':'Usage not reported; no estimate was invented.'),button('Inspect saved image request',()=>imageRequestSheet(a.id))))));
  if(held.deliveries.length)parts.push(detail('Saved files',make('p','quiet','Every rendered revision keeps its files. Approved files never change; an edit makes a new draft.'),...held.deliveries.map(savedFiles)));
  parts.push(detail('History',make('p','quiet','Each saved revision is kept. Restoring makes new work and never brings back an approval.'),add(make('div','desk-versions'),...historyGroups(held.history).map((g,i)=>historyGroup(g,i===0))),held.history.length>=100&&held.history.at(-1).revision>0?button('Older revisions',olderHistory):null));
  $('main').replaceChildren(...parts.filter(Boolean));
  paintWork();     // this infographic's running work, and its locked controls
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
function when(value){const date=value?new Date(value):null;return date&&!isNaN(date)?date.toLocaleString([], {dateStyle:'medium',timeStyle:'short'}):'';}
function ledgerItem(name,words,state,detail){
  const bead=make('span','bead');bead.dataset.state=state;bead.setAttribute('aria-hidden','true');
  return add(make('div','ig-ledger-item'),make('span','quiet',name),add(make('strong','state'),bead,document.createTextNode(words)),detail?make('span','quiet ig-ledger-detail',detail):null);
}
function workbench(p,delivery){
  if(bench.project!==p.id){keepBench();bench={project:p.id,element:String(benchStore.elements[p.id]||''),drafts:{...(benchStore.drafts[p.id]||{})},saved:null,failed:'',unchanged:false,focus:false,scroll:null};}
  const names=held.elements||[],n=held.page_revision;
  // With no current page there is nothing to update: say which page this is and the next step.
  const stage=held.roadmap?.stage,again=stage==='build'?'Build the page again to edit or approve it.':(stage==='choose'?'Choose a story':held.planning_response?.available?'Check the saved proposal':'Find the story')+' and build the page again to edit or approve it.';
  const kept=delivery&&!delivery.current&&p.approval;      // a rename kept the approval
  const view=make('section','card stack ig-view');view.append(make('h2','card-title',!delivery?'Page preview':!p.scene?'Earlier page (revision '+pageOf(delivery)+')':kept?'Approved revision '+n+': prepare its files':!delivery.current?'Earlier preview: update it to see your changes':delivery.draft&&p.approval?'Approved revision '+n+': prepare its files':delivery.draft?'Draft page':delivery.approved_current?'Approved delivery':pageOf(delivery)===n?'Approval withdrawn: approve revision '+n+' again':'Earlier approval: review the current revision'));
  const mark=make('div','ig-mark');mark.hidden=true;mark.setAttribute('aria-hidden','true');
  let img=null,figure=null;
  if(delivery){
    img=make('img','ig-preview');img.alt='Rendered '+(delivery.draft?'draft':'approved')+' infographic, revision '+pageOf(delivery);
    if(p.scene){img.width=Math.round(p.scene.width);img.height=Math.round(p.scene.height);}
    figure=add(make('div','ig-figure'),img,mark);
    // The page's scroll region takes focus, so a keyboard can pan the page at actual pixels
    // with the arrow keys, Page Up/Down, Home and End. The zoom controls sit just before it.
    const scroll=add(make('div','ig-preview-scroll'),figure);scroll.tabIndex=0;scroll.setAttribute('role','region');
    const fit=free(button('Fit page',()=>zoom(false))),actual=free(button('Actual pixels',()=>zoom(true)));
    function zoom(original){img.classList.toggle('ig-preview-actual',original);figure.classList.toggle('ig-actual',original);fit.setAttribute('aria-pressed',String(!original));actual.setAttribute('aria-pressed',String(original));scroll.setAttribute('aria-label',original?'Page at actual pixels':'Page preview');}
    zoom(false);
    const zooming=add(make('div','ig-page-tools'),fit,actual);
    const tools=make('div','ig-page-tools');
    const which=delivery.draft?' draft':delivery.approved_current?'':' (earlier approved)';
    for(const format of ['png','pdf','svg','text'])tools.append(free(button('Download '+FORMAT_NAMES[format]+which,async()=>{try{await download(delivery,format);}catch(f){error(f.message);}})));
    if(delivery.approved_current){if(primary!=='Deliver approved page')tools.append(button('Deliver approved page',()=>deliverySheet(delivery)));tools.append(button('Share to team repository',()=>shareSheet(delivery)));}
    const library=delivery.approved_current?keptPart(delivery):null;
    if(!p.scene)view.append(make('p','','Your current work, revision '+n+', has no page yet. '+again),make('p','quiet','This is revision '+pageOf(delivery)+(delivery.draft?', a draft.':'. Its approved files stay downloadable and unchanged.')));
    else if(kept)add(view,make('p','quiet','Shows approved revision '+pageOf(delivery)+'. Prepare the approved files for revision '+n+' on this computer so they carry its title. Nothing is sent anywhere.'),primary==='Prepare approved files'?null:button('Prepare approved files',()=>action('export',{draft:false}),true));
    else view.append(make('p','quiet',delivery.current?'Shows revision '+pageOf(delivery)+'. Select words on the page to edit them.':'Shows revision '+pageOf(delivery)+'. Your current work is revision '+n+'.'));
    if(!delivery.current&&p.scene&&!kept&&primary!=='Update preview')view.append(button('Update preview',()=>action('preview'),true));
    view.append(zooming,scroll,tools);
    if(library)view.append(library);
    showPicture(delivery,img,p.id);
  }else if(p.scene)add(view,make('p','','No preview yet. Rendering is local and starts no assistant or image request.'),primary==='Create preview'?null:button('Create preview',()=>action('preview'),true));
  const parts=[view];
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
    if(bench.unchanged&&!unsaved){state.className='ig-save-state';state.textContent='Nothing changed, so no revision was made. These words are already in revision '+held.page_revision+'.';return;}
    if(bench.saved&&!unsaved&&bench.saved.revision===held.project.revision){
      // The toolbar's Update preview is the one control for this; the words say so.
      const stale=!held.deliveries.find(d=>d.current);state.className='ig-save-state';
      state.textContent='Saved '+bench.saved.label+' as revision '+held.page_revision+'. '+(stale?'The preview still shows an earlier revision. Choose Update preview to see this change before review.':'');
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
  const id=held.project.id,before=held.project.revision,result=await action('edit-text',{element_id:chosen.id,text});
  // The person moved to another screen meanwhile: this result belongs to that infographic's
  // own saved state, never to whatever is open now. Typed words stay in its kept drafts.
  if(!here(id)||bench.project!==id)return;
  if(result&&typeof result.revision==='number'){delete bench.drafts[chosen.id];if(result.revision>before)bench.saved={revision:result.revision,label:chosen.label};else bench.unchanged=true;}
  else{bench.drafts[chosen.id]=text;bench.failed=lastError||'These words could not be saved.';}
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
// One label per format, everywhere a file is offered.
const FORMAT_NAMES={png:'PNG',pdf:'PDF',svg:'SVG',text:'text'};
function savedFiles(d){
  const words=(d.draft?'Draft':'Approved')+' · revision '+pageOf(d)+(d.approved_current?' · current approval':d.current?' · matches current work':' · earlier');
  return add(make('div','desk-version'),make('span','',words),add(make('div','ig-page-tools'),...['png','pdf','svg','text'].map(format=>{const node=free(button(format==='text'?'Text':FORMAT_NAMES[format],async()=>{try{await download(d,format);}catch(f){error(f.message);}}));node.setAttribute('aria-label','Download '+FORMAT_NAMES[format]+', '+(d.draft?'draft':'approved')+' revision '+pageOf(d));return node;})));
}
// History by page revision: each group is the revision that changed the page, then what the
// revisions after it recorded (checks, a review, an approval, art direction, image requests).
// Compare and Restore belong to the group, so a bookkeeping entry offers neither.
function historyGroups(entries){
  const groups=[];
  for(const v of entries){const page=pageOf(v);let group=groups.at(-1);if(!group||group.page!==page){group={page,entries:[]};groups.push(group);}group.entries.push(v);}
  return groups;
}
function historyGroup(group,current){
  const newest=group.entries[0],oldest=group.entries.at(-1),head=oldest.revision===group.page?oldest:null;
  const later=(head?group.entries.slice(0,-1):group.entries).slice().reverse();
  const facts=[when((head||oldest).saved_at),'Revision '+group.page+(current?' (current)':''),head?.affected?.length?'Changed: '+head.affected.join(', '):'',newest.approved?'Approved':''].filter(Boolean).join(' · ');
  return add(make('div','desk-version'),add(make('div','ig-entry'),make('strong','',head?.summary||'Revision '+group.page),make('span','quiet',facts),
      later.length?make('span','quiet','Then: '+[...new Set(later.map(v=>v.summary))].join('; ')+'.'):null),
    current?null:add(make('div','bar'),button('Compare revision '+group.page+' with current',()=>compareSheet(newest,group.page)),button('Restore revision '+group.page,()=>restoreSheet(newest,group.page))));
}
// Where this stands: the one status surface. The route, the one next step (named as the
// toolbar names it), the three revisions that matter, and what can be downloaded.
function standing(map,p,delivery,needs){
  if(!map)return null;
  const steps=add(make('ol','workflow-steps ig-roadmap'),...map.steps.map(step=>{
    const item=make('li','workflow-step');const bead=make('span','bead');bead.dataset.state=step.state==='done'?'done':step.state==='current'?'current':'none';bead.setAttribute('aria-hidden','true');
    item.append(bead,document.createTextNode(' '+step.label+(step.state==='done'?' (done)':'')));if(step.state==='current')item.setAttribute('aria-current','step');return item;}));
  steps.setAttribute('aria-label','Steps to an approved delivery');
  const line=(name,words,cls='')=>add(make('p',cls),make('strong','',name+' '),document.createTextNode(words));
  let ledger=null;
  if(delivery||p.scene){
    const n=held.page_revision,approvedFiles=held.deliveries.find(d=>d.approved_current)||held.deliveries.find(d=>!d.draft);
    ledger=add(make('div','ig-ledger'),
      ledgerItem('Current work','Revision '+n,'current',held.readiness?.summary),
      ledgerItem('Preview',delivery?'Revision '+pageOf(delivery):'Not rendered yet',delivery?.current?'done':'review',delivery?(delivery.current?(pageOf(delivery)===n?'Shows your current work.':'Shows the same page as your current work, saved earlier as revision '+pageOf(delivery)+'.'):'Outdated: it does not show your latest changes.'):'Create a preview to see the page.'),
      ledgerItem('Approved delivery',approvedFiles?'Revision '+pageOf(approvedFiles)+(!approvedFiles.approved_current&&pageOf(approvedFiles)===n?' (withdrawn)':''):'None yet',approvedFiles?.approved_current?'done':'review',approvedFiles?(approvedFiles.approved_current?'Matches your current work.':pageOf(approvedFiles)===n?'Approval withdrawn by a new review until you approve again. The files are kept unchanged.':'Earlier files, kept unchanged.'):'Approve a checked revision to deliver it.'));
    ledger.setAttribute('aria-label','Revisions');ledger.setAttribute('role','group');
  }
  return add(make('section','card stack ig-standing'),make('h2','card-title','Where this stands'),steps,line('Needs you:',needs,'ig-needs'),ledger,line('Downloads:',map.downloads));
}
// Review and finish: the steps still to do, with finished ones folded into one line and
// Review again behind a disclosure. Nothing here reads as required once it is done.
function finishCard(p,delivery,checked,approved){
  const n=held.page_revision,prepared=held.deliveries.some(d=>d.approved_current);
  const step=(title,words,...controls)=>add(make('div','stack ig-finish-step'),make('strong','',title),make('p','',words),...controls.filter(Boolean));
  const reviewing=()=>add(make('div','bar'),button('Review page',()=>reviewSheet(delivery)),button('Inspect page with assistant',()=>action('inspect-images',{then_check:true})));
  const checking=()=>add(make('div','bar'),button('Run checks again',()=>action('check')),p.checks.some(c=>c.status!=='passed')?button('Repair findings',repairSheet):null);
  const again=(words)=>detail('Review again',make('p','quiet',words),reviewing(),checking());
  if(approved)return card('Review and finish',stateLine('done',held.approval_words+' '+(prepared?'Download its files from the page above, or from Saved files further down.':'Prepare its files on this computer; nothing is sent anywhere.')),
    prepared||primary==='Prepare approved files'?null:button('Prepare approved files',()=>action('export',{draft:false}),true),
    again('A new review, or running the checks again, withdraws this approval until you approve again. The approved files stay unchanged in Saved files.'));
  if(checked)return card('Review and finish',stateLine('done','Reviewed and checked: revision '+n+'. The checks passed against your latest review.'),
    again('Review the page again or rerun the checks if something changed outside this page. Approval still waits for you.'),
    step('Approve (your decision)','Approval applies to revision '+n+' only. Its final files are prepared on this computer straight after; a later change needs a new review.',button('Approve revision '+n,approveRevision,true)));
  return card('Review and finish',
    step('1. Review the page (required)','Look at the actual page for revision '+n+' at its intended size: facts and qualifications, objects and relationships, crop and resolution, label clearance and brand. Recording your review runs the checks straight after. Asking your assistant to inspect it is optional.',reviewing()),
    step('2. Checks (on this computer)','Required content, factual support, page layout, brand and accessibility, and your latest review. They start no assistant or image request.',checking()),
    step('3. Approve (your decision)','Approval becomes available when the current checks pass against your latest review.'));
}
async function approveRevision(){
  const id=held.project.id,result=await action('approve',{then_export:true});
  if(!here(id))return;     // said where the person is now (elsewhere)
  if(result?.approved&&result.problem)error('Revision '+pageOf(result)+' is approved, but its files are not ready: '+result.problem+' Choose Prepare approved files to try again on this computer.');
  else if(result?.approved&&result.library?.state==='failed')error('Revision '+pageOf(result)+' is approved and its files are ready, but they were not kept in the Document Library: '+result.library.problem+' Choose Keep in Document Library again.');
}
// The shared Document Library (library.js). Add from library makes chosen revisions sources
// of this infographic, Use revision N takes a newer one only when pressed, and approved files
// say whether their text and PDF were kept there. Choosing documents starts no research,
// assistant or image work and changes no research setting.
function libraryPick(use){
  if(!window.StudioLibrary){error('The library could not be loaded. Reload the page.');return Promise.resolve(false);}
  // This infographic's own kept export cannot be a source for itself; the server refuses it too.
  const own=held?.library?.own||null;
  return window.StudioLibrary.pick({title:'Add from Document Library',studio:'infographic',noun:'infographic',max:40,post:(route,body)=>request('/api/'+route,body),use,
    unavailable:row=>own&&row.id===own?{label:'This infographic',detail:'Its own approved page cannot be a source for it.'}:null,
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
// 'a', 'a and b', 'a, b and c'.
function joined(words){return words.length<3?words.join(' and '):words.slice(0,-1).join(', ')+' and '+words.at(-1);}
// What a source change clears: everything built from the earlier sources.
function libraryClears(){
  const p=held.project;
  return [p.facts.length?'facts':'',p.stories.length?'story':'',p.scene?'page':'',p.approval?'approval':''].filter(Boolean);
}
// What a brief change clears. Captured facts come from the sources, so they stay.
function briefClears(){
  const p=held.project;
  return [p.stories.length?'story':'',p.scene?'page':'',p.approval?'approval':''].filter(Boolean);
}
// Back to the control that started an action, opening its section, once the page is drawn.
function refocus(key){const found=key&&document.querySelector('[data-key="'+key+'"]');if(found){found.closest('details')?.setAttribute('open','');found.focus();}return found;}
// Says what an action will clear and asks first; with nothing to clear, it simply runs.
// Cancel changes nothing: `cancel` returns to the sheet that asked, with what was typed;
// otherwise focus returns to `back`, the control that started the action.
function clearsConfirm(title,label,{clears,kept='',run,back,parts=[],check=()=>true,cancel=null}){
  if(!clears.length&&!parts.length){run();return;}
  const problem=make('p','problem');problem.setAttribute('role','alert');
  const said=clears.length?[make('p','','This clears this infographic’s '+joined(clears)+'.'+(kept?' '+kept:'')+' Earlier work stays in History. Nothing starts by itself; find the story again when you are ready.')]:[];
  const go=button(label,async()=>{
    if(go.disabled)return;
    const refused=check();if(refused!==true){problem.textContent=refused;return;}
    go.disabled=true;try{await run();}finally{go.disabled=false;}
  },true);
  sheet(title,...said,...parts,problem,add(make('div','create-foot bar'),go,button('Cancel',cancel||(()=>{closeSheet();refocus(back);}))));
}
// Says what will be cleared and asks first when there is work to clear, and asks the person
// to confirm readable-only coverage when a document has extraction gaps; otherwise runs.
function libraryConfirm(title,label,rows,run,back='ig-library-add'){
  const gaps=rows.some(row=>row.gaps.length);
  const ack=make('input');ack.type='checkbox';
  const clears=libraryClears();
  if(!clears.length&&!gaps){run(false);return;}
  const parts=rows.map(row=>card(row.title,make('p','quiet','Revision '+row.revision+' · '+row.characters+' readable characters'),row.gaps.length?list(row.gaps):make('p','quiet','No extraction gaps.')));
  if(gaps)parts.push(add(make('label','check'),ack,document.createTextNode('I reviewed these gaps. Use only the readable text.')));
  clearsConfirm(title,label,{clears,parts,back,run:()=>run(gaps),
    check:()=>!gaps||ack.checked||'Review the gaps and confirm using only the readable text first.'});
}
// Every route that changes sources asks first when facts, a story, a page or an approval exist.
function sourceConfirm(name,replacing,run,back,cancel){
  const label=replacing?'Replace source':'Add as a source';
  clearsConfirm(replacing?'Replace '+(held.project.sources.find(s=>s.id===replacing)?.name||'this source'):'Add '+name,label,
    {clears:libraryClears(),back,cancel,run:async()=>{await run();refocus(back);}});
}
function libraryAddButton(){
  let rows=null;
  const node=button('Add from Document Library',()=>libraryPick(async picks=>{
    if(running.has(held.project.id))throw Error('This infographic is still working. Add from the Document Library once it has finished.');
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
  if(pinned.update){
    const use=button('Use revision '+pinned.head+' of '+(s.name||s.id),async()=>{
      try{
        const rows=await libraryRows([{id:pinned.id,revision:pinned.head}]);
        libraryConfirm('Use revision '+pinned.head+' of '+(s.name||s.id),'Use revision '+pinned.head,rows,async acknowledged=>{
          const result=await action('library-update',{document:pinned.id,revision:pinned.head,acknowledge_warnings:acknowledged},null,{quiet:true});
          if(result)toast('Revision '+pinned.head+' is the source now. Nothing was started.');
          refocus('ig-library-add');
        },use.dataset.key);
      }catch(failure){error(failure.message);}
    });
    use.dataset.key='ig-library-use-'+s.id;parts.push(use,make('p','quiet',LIBRARY_CLEARS));
  }
  return parts;
}
function keptPart(delivery){
  const kept=held.library?.kept;
  if(kept&&kept.export===delivery.id&&kept.state==='kept')return make('p','quiet','Kept in the Document Library: approved revision '+pageOf(kept)+', with its text and PDF (library revision '+kept.library_revision+').');
  const again=button(kept&&kept.export===delivery.id?'Keep in Document Library again':'Keep in Document Library',async()=>{
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
    if(r.kind==='pdf')return receiptCard('PDF',r.ok?'done':'late',r.ok?'Downloaded: approved revision '+pageOf(delivery)+'.':'Not downloaded: '+r.message,
      button(r.ok?'Download PDF again':'Retry PDF download',async()=>{try{await download(delivery,'pdf');toast('PDF downloaded again.');}catch(f){error(f.message);}}));
    const result=r.result||{};
    if(result.url)return receiptCard('Google Doc','done','Delivered: approved revision '+pageOf(delivery)+'.',googleLink(result.url,'Open Google Doc'));
    const saved=(held?.google_deliveries||[]).some(g=>g.request_id===r.request_id);
    const uncertain=saved&&(!r.result||result.state==='unknown');
    const resend=async()=>{const request_id=requestId();const again=await action('google-deliver',{export_id:delivery.id,request_id,folder:r.folder},delivery.revision,{quiet:true});receiptSheet(delivery,receipts.map(x=>x===r?{...r,request_id,result:again,problem:again?null:lastError}:x));};
    const check=async()=>{const again=await action('google-deliver',{export_id:delivery.id,request_id:r.request_id,folder:r.folder,reconcile:true},delivery.revision,{quiet:true});receiptSheet(delivery,receipts.map(x=>x===r?{...r,result:again}:x));};
    if(!saved)return receiptCard('Google Doc','late','Not delivered: '+(result.message||r.problem||'The request did not start.')+' No Google request was saved.',button('Send again',resend));
    return receiptCard('Google Doc',uncertain?'review':'late',(uncertain?'Not confirmed: ':'Not delivered: ')+(result.message||r.problem||'The outcome could not be confirmed.')+' Nothing was resent.',
      button('Check again without resending',check),uncertain?null:button('Send again',resend));
  });
  const partial=receipts.some(r=>r.kind==='pdf'?!r.ok:!r.result?.url)&&receipts.some(r=>r.kind==='pdf'?r.ok:!!r.result?.url);
  sheet('Delivery receipt',make('p','','Approved revision '+pageOf(delivery)+'. Each format you chose is listed with what happened.'),...parts,
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
// What the person inspected is required: an empty review is refused beside the field, once.
function reviewSheet(delivery){
  const observations=field('What did you inspect on the actual composed page?','','textarea');
  observations.input.addEventListener('input',()=>{if(lines(observations.input.value).length)invalid(observations,'');});
  const record=()=>{const seen=lines(observations.input.value);if(!seen.length){invalid(observations,'Record what you inspected on the actual page.');return;}return action('review',{export_id:delivery.id,observations:seen,then_check:true});};
  sheet('Review page',make('p','','Look at the rendered page for revision '+pageOf(delivery)+' at its intended size, then say what you checked. Recording your review runs the local checks straight after; nothing is approved.'),observations.wrap,detail('Optional: ask your assistant to inspect it',make('p','quiet','Your assistant looks at the actual page and artwork and records located findings. It uses your assistant allowance and never approves.'),button('Inspect page with assistant',()=>action('inspect-images',{then_check:true}))),add(make('div','bar'),button('Record review and run checks',record,true),button('Cancel',closeSheet)));
}
// `page` is the page revision the person chose; `version` is its newest saved revision.
function restoreSheet(version,page=pageOf(version)){sheet('Restore revision '+page+'?',make('p','','Creates a new revision with this page. Current sources, images and deliveries remain in history; approval is not restored.'),detail('Advanced',make('p','quiet','Restores saved revision '+version.revision+', exact identity '+version.sha256.slice(0,12)+'.')),add(make('div','bar'),button('Restore as a new revision',()=>action('restore',{revision:version.revision,sha256:version.sha256}),true),button('Cancel',closeSheet)));}
async function showSettings() {
  remember('settings');
  held = null;
  resetPicture();
  // A sidebar screen: its title as the sidebar names it, a lede, and no Back.
  heading('Settings');
  try {
    preferences = await request('/api/preferences');
    const capability = await request('/api/computer');
    const sharedLink = make('a', 'button', 'Shared assistant and brand settings');
    sharedLink.href = '/onboarding/#token=' + encodeURIComponent(token) + '&view=settings';
    const model = field('Gemini image model', preferences.native.gemini_model || '');
    const teamEmail=field('Team Git email',preferences.native.team_email||'');
    teamEmail.wrap.append(make('span','field-hint','The email your shared infographics are committed under in the team repository. Leave empty to use your Git email.'));
    const googleAccount=field('Google account email',preferences.native.google_account||''),googleFolder=field('Google Drive destination folder ID (optional)',preferences.native.google_folder||'');
    const renderer = field('Installed headless renderer path', preferences.native.renderer || '');
    renderer.input.placeholder = preferences.renderer || 'Use the renderer included in a prepared download';
    // Provider status in the team's words: what is ready, what to do, and when the rest is
    // checked. Nothing here signs in, generates or reads a credential.
    const messages = {
      'assistant-missing': 'Install the selected assistant on this computer before starting assistant work.',
      'sign-in-required': 'Sign in to the selected assistant on this computer.',
      'gemini-key-required': 'Supply GEMINI_API_KEY in the server launch environment.',
      'gemini-model-required': 'Choose an image-capable Gemini model below.',
      'image-model-unavailable': 'Choose a Gemini image model available to your account.',
      'image-tool-unavailable': 'The installed Codex does not offer its image tool on this computer.',
      'manual-image-review-required': 'Review the actual page yourself; your assistant cannot inspect images here.',
      'sign-in-not-checked': 'Sign-in is checked the first time you start assistant work.',
      'image-tool-not-checked': 'Image generation hasn’t been tried on this computer yet. It’s checked the first time you build artwork.',
      'image-model-access-not-checked': 'Your Gemini image model hasn’t been tried on this computer yet. It’s checked the first time you build artwork.',
      'image-inspection-not-checked': 'Assistant page inspection hasn’t been tried on this computer yet. It’s checked the first time you ask your assistant to inspect a page.',
      'generation-and-editing-not-live-verified': 'Artwork generation and artwork revisions are checked the first time you use them.'
    };
    const imageDefaults = [];
    if (preferences.image_provider === 'gemini') imageDefaults.push(model.wrap);
    const save = async (changes, said) => {
      try {
        await request('/api/preferences', {expected: preferences.native_revision, changes});
        await showSettings();
        toast(said);
      } catch (failure) { error(failure.message); }
    };
    imageDefaults.push(detail('Advanced Google account override',make('p','quiet','Leave empty to use the same existing Google sign-in as Blog Studio.'),googleAccount.wrap,googleFolder.wrap),make('p','quiet','Uses the selected existing gcloud sign-in only when you explicitly read or deliver a Google Doc. No login or account access starts here.'),detail('Advanced renderer setting', renderer.wrap),
      make('p', 'quiet', 'Defaults apply to new work. Your existing workspace and saved brand stay in place.'),
      button('Save defaults', () => {
        const changes = {renderer: renderer.input.value,google_account:googleAccount.input.value,google_folder:googleFolder.input.value};
        if (preferences.image_provider === 'gemini') changes.gemini_model = model.input.value;
        return save(changes, 'Defaults saved.');
      }, true));
    $('main').replaceChildren(
      add(make('div','page-head'),make('p','lede','How Infographic Studio works on this computer: your assistant, the page renderer, the team repository and the defaults for new infographics.')),
      card('Assistant and image provider',
        make('p', '', capability.assistant + ' · ' + capability.image_provider),
        make('p', '', capability.state === 'unavailable' ? 'Finish these steps before building artwork.' : 'Ready on this computer. Your assistant and image provider are checked the first time you use them.'),
        make('p', '', capability.disclosure),
        list([...capability.problems, ...capability.unknown].map(code => messages[code] || code))),
      card('Page renderer', make('p', '', capability.renderer_available
        ? 'Installed renderer found. Preview checks actual fonts, layout, and output.'
        : 'Configure an installed renderer, or use a prepared download that includes it. No browser is downloaded here.')),
      card('Shared settings', sharedLink, make('p', 'quiet', 'Your infographic workspace stays local. Team connection and sharing happen only when you choose them in the team repository.')),
      card('Team repository', make('p','quiet','Shared infographics live in the team repository set in shared settings. It is separate from the Document Library on this computer.'),
        teamEmail.wrap, button('Save team email', () => save({team_email: teamEmail.input.value}, 'Team email saved.'))),
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
  // A reload returns to the same screen: the last infographic, at the same place, in any
  // state, unless the person had gone back to Home or Settings.
  let id='',where='';try{id=sessionStorage.getItem('infographic-studio-project')||'';where=sessionStorage.getItem('infographic-studio-screen')||'';}catch(f){}
  if(where==='settings'){await showSettings();return;}
  if(id&&where!=='home'){await openProject(id);if(held?.project.id===id){returnToPlace(id);return;}error('');}
  await home();
}
$('sheet').addEventListener('close',paintWork);
if(!token)error('Open Infographic Studio using the private link printed in your terminal.');else void startDesk();
// Back from shared settings with the browser's Back button restores this page from its cache,
// without running startDesk: drop the return marker and re-read an open Team repository sheet.
window.addEventListener('pageshow',event=>{
  if(!event.persisted||!token)return;
  try{sessionStorage.removeItem('infographic-studio-return');}catch(f){}
  if($('sheet').open&&$('sheet-title')?.textContent==='Team repository')void teamSheet();
});

function reviseArtSheet(){const change=field('What should change?','','textarea'),preserve=field('What should stay the same?','Keep all other subjects, relationships, brand, empty label regions and composition.','textarea');sheet('Revise the artwork',make('p','','This sends the saved original as a reference to your selected image provider. It uses provider allowance; the earlier artwork remains in history.'),change.wrap,preserve.wrap,add(make('div','bar'),button('Create referenced revision',()=>action('revise-art',{change:change.input.value,preserve:preserve.input.value,request_id:requestId()}),true),button('Cancel',closeSheet)));}
// Compare shows what a person can see: words by element, sources, story, layout and a
// thumbnail of each side. The saved fields themselves wait behind Advanced.
async function compareSheet(version,page=pageOf(version)){
  try{
    const found=(await request('/api/action',{action:'compare',id:held.project.id,expected_revision:held.project.revision,before:version.revision,after:held.project.revision})).result;
    const parts=[];
    if(found.same){
      parts.push(make('p','','No changes to the page. Revision '+page+' and the current revision show the same page.'));
      if(found.since.length)parts.push(make('p','quiet','The revisions in between only recorded: '+found.since.join('; ')+'.'));
    }else{
      const urls=[];
      const side=(label,which)=>{
        const shown=held.deliveries.find(d=>d.id===which?.export);if(!shown)return null;
        const img=make('img','ig-compare-thumb');img.alt=label+': rendered revision '+pageOf(shown);
        download(shown,'png',true).then(url=>{urls.push(url);img.src=url;}).catch(()=>{img.replaceWith(make('p','quiet','The '+label.toLowerCase()+' page could not be shown.'));});
        return add(make('figure','ig-compare-side'),img,make('figcaption','quiet',label+' · revision '+pageOf(shown)));
      };
      const before=side('Before',found.before),after=side('Now',found.after);
      if(before||after)parts.push(add(make('div','ig-compare'),before,after));
      $('sheet').addEventListener('close',()=>urls.forEach(url=>URL.revokeObjectURL(url)),{once:true});
      parts.push(add(make('div','stack'),...found.changes.map(c=>add(make('div','stack ig-change'),make('strong','',c.what),
        c.before!=null?make('p','','Before: '+c.before):null,c.after!=null?make('p','','Now: '+c.after):null))));
    }
    parts.push(detail('Advanced',make('p','quiet','The saved fields that differ, exactly as stored.'),...Object.entries(found.advanced).map(([key,value])=>detail(key,make('pre','ig-csv-preview',JSON.stringify(value,null,2))))));
    sheet('Changes since revision '+page,...parts,add(make('div','create-foot bar'),button('Done',closeSheet,true)));
  }catch(f){error(f.message);}
}
// `kept` brings back what was typed or chosen when a confirmation is cancelled.
function sourceSheet(kept=null) {
  const value=field('New or replacement supplied information',kept?.text||'','textarea');
  const replacement=field('Source to replace (leave empty to add another)','','select');
  const empty=make('option','','Add as another source'); empty.value=''; replacement.input.append(empty);
  for(const source of held.project.sources){const option=make('option','',source.name);option.value=source.id;replacement.input.append(option);}
  const upload=field('Or upload a source file'); upload.input.type='file'; upload.input.accept='.txt,.md,.pdf,application/pdf,.docx,.html,.htm';
  const shown=make('div','stack'),problem=make('p','problem'); problem.setAttribute('role','alert');
  replacement.input.value=kept?.replace||'';
  let preview=kept?.preview||null,acknowledged=Boolean(kept?.acknowledged);
  const again=()=>sourceSheet({text:value.input.value,replace:replacement.input.value,preview,acknowledged});
  function showPreview(){
    shown.replaceChildren(make('p','',preview.name+' · '+preview.characters+' readable characters'),make('pre','ig-csv-preview',preview.excerpt),list(preview.warnings));
    if(preview.warnings.length){const ack=make('input');ack.type='checkbox';ack.checked=acknowledged;ack.addEventListener('change',()=>{acknowledged=ack.checked;});shown.append(add(make('label','check'),ack,document.createTextNode('I reviewed these gaps. Use only the readable text.')));}
    if(!preview.readable)problem.textContent='No readable text was found. Supply an accessible Word or text version.';
  }
  const go=button('Save supplied information',async()=>{
    problem.textContent='';const replace=replacement.input.value;
    if(preview){
      if(value.input.value.trim()){problem.textContent='Use either a file or pasted text for this source.';return;}
      if(!preview.readable || (preview.warnings.length&&!acknowledged)){problem.textContent='Review the readable coverage before importing this source.';return;}
      const sent={capture_id:preview.id,acknowledge_warnings:acknowledged,...(replace?{replace_id:replace}:{})};
      sourceConfirm(preview.name,replace,()=>action('source-import',sent),'ig-source-update',again);
    }else{
      if(!value.input.value.trim()){problem.textContent='Paste source text or choose a readable file.';return;}
      const sent={data:encoded(new TextEncoder().encode(value.input.value)),kind:'text',name:'Updated supplied information',...(replace?{replace_id:replace}:{})};
      sourceConfirm('supplied information',replace,()=>action('source',sent),'ig-source-update',again);
    }
  },true);
  upload.input.addEventListener('change',async()=>{
    const file=upload.input.files[0]; if(!file)return; go.disabled=true; problem.textContent='';
    try{
      const kinds={txt:'text',md:'markdown',pdf:'pdf',docx:'docx',html:'html',htm:'html'},kind=kinds[file.name.toLowerCase().split('.').pop()];
      if(!kind)throw Error('Choose text, Markdown, PDF, Word (.docx) or HTML. Add selected CSV through a new information preview.');
      preview=await request('/api/source-preview',{data:encoded(await bytes(file)),kind,name:file.name}); acknowledged=false;
      showPreview();
    }catch(failure){preview=null;problem.textContent=failure.message;}finally{go.disabled=false;}
  });
  sheet('Update supplied information',make('p','',LIBRARY_CLEARS+' You are asked first when there is work to clear.'),replacement.wrap,value.wrap,upload.wrap,button('Use a Google Doc, Slides or public page',()=>remoteSheet(result=>{preview=result;acknowledged=false;sourceImportSheet(result,replacement.input.value,'ig-source-update');})),shown,problem,add(make('div','bar'),go,button('Cancel',closeSheet)));
  if(preview)showPreview();
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

// The working title alone is a rename that clears nothing. Any other change clears the story,
// page and approval built from the earlier brief, so it asks first when they exist.
// `typed` brings back what was typed when the confirmation is cancelled.
function briefSheet(typed=null){
  const p=held.project,fields={};
  for(const[key,label,value]of[['title','Working title',p.brief.title],['audience','Audience',p.brief.audience],['purpose','Desired takeaway',p.brief.purpose],['must','Must-show ideas — one per line',p.brief.must_show.map(r=>r.text).join('\n')],['locked','Exact wording to preserve',p.brief.locked_words.join('\n')],['exclusions','Leave out',p.brief.exclusions.join('\n')]])fields[key]=field(label,typed?typed[key]:value,['must','locked','exclusions'].includes(key)?'textarea':'input');
  const save=async()=>{
    const brief={...p.brief,title:fields.title.input.value,audience:fields.audience.input.value,purpose:fields.purpose.input.value,must_show:lines(fields.must.input.value).map((text,i)=>({id:p.brief.must_show[i]?.id||'r_'+requestId().slice(0,12),text})),locked_words:lines(fields.locked.input.value),exclusions:lines(fields.exclusions.input.value)};
    const rest=b=>JSON.stringify({...b,title:undefined}),story=rest(brief)!==rest(p.brief),renamed=brief.title!==p.brief.title;
    if(!story&&!renamed){closeSheet();refocus('ig-edit-brief');toast('Nothing changed, so no revision was made.');return;}
    const clears=story?briefClears():[];
    const said=!story?(p.approval?'Renamed. The story, page and approval are kept. Prepare the approved files again so they carry the new title.':p.stories.length||p.scene?'Renamed. The story and page are kept.':'Renamed.')
      :clears.length?'Brief saved. Find the story again when you’re ready.':'Brief saved.';
    // One save at a time: a second click would only meet the revision the first one made.
    const send=async()=>{
      if(busy)return;busy=true;const unlock=lockControls();
      try{await request('/api/project',{id:p.id,expected_revision:p.revision,brief});closeSheet();unlock();busy=false;await openProject(p.id);toast(said);refocus('ig-edit-brief');}
      catch(f){error(f.message);}
      finally{if(busy){unlock();busy=false;}}
    };
    const typedNow=Object.fromEntries(Object.entries(fields).map(([key,f])=>[key,f.input.value]));
    clearsConfirm('Save the brief','Save brief',{clears,kept:p.facts.length?'Captured facts stay.':'',run:send,back:'ig-edit-brief',cancel:()=>briefSheet(typedNow)});
  };
  sheet('Edit brief and requirements',make('p','','Renaming keeps the story, page and approval. Changing anything else clears the story, page and approval built from the earlier brief, and asks first. Captured facts, earlier versions and saved files are kept.'),...Object.values(fields).map(f=>f.wrap),add(make('div','bar'),button('Save brief',save,true),button('Cancel',()=>{closeSheet();refocus('ig-edit-brief');})));
}

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

function sourceImportSheet(preview,replaceId,back='ig-research',acknowledgedBefore=false){
  let acknowledged=acknowledgedBefore;const problem=make('p','problem'),ack=make('input');ack.type='checkbox';ack.checked=acknowledged;ack.addEventListener('change',()=>{acknowledged=ack.checked;});
  sheet('Review captured information',make('p','',preview.name+' · '+preview.characters+' readable characters'),make('pre','ig-csv-preview',preview.excerpt),list(preview.warnings),preview.warnings.length?add(make('label','check'),ack,document.createTextNode('I reviewed these gaps. Use only readable text.')):make('p','quiet','Captured text is stored locally; import does not read the remote document again.'),problem,add(make('div','bar'),button('Import this capture',()=>{if(!preview.readable||(preview.warnings.length&&!acknowledged)){problem.textContent='Review readable coverage and acknowledge gaps before import.';return;}const sent={capture_id:preview.id,acknowledge_warnings:acknowledged,...(replaceId?{replace_id:replaceId}:{})};sourceConfirm(preview.name,replaceId||'',()=>action('source-import',sent),back,()=>sourceImportSheet(preview,replaceId,back,acknowledged));},true),button('Cancel',()=>{closeSheet();refocus(back);})));
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
      if(choice!=='pdf'){const result=await action('google-deliver',{export_id:delivery.id,request_id:savedRequest,folder:folder.input.value},null,{quiet:true});receipts.push({kind:'google',result,request_id:savedRequest,folder:folder.input.value,problem:result?null:lastError});}
      receiptSheet(delivery,receipts);
    }finally{go.disabled=false;}},true);
  sheet('Deliver approved page',make('p','','Approved revision '+pageOf(delivery)+'. To download its PNG, SVG or text instead, use the Download buttons beside the page.'),make('p','','PDF preserves the exact approved one-page render. A new Google Doc contains that page as an image, plus editable text and source notes. Your original document is kept. Google conversion layout requires visual review in Docs.'),make('p','quiet','Starts with your shared Marketing Studio delivery choice and existing Google sign-in.'),format.wrap,detail('Choose a destination folder',folder.wrap),problem,add(make('div','bar'),go,button('Cancel',closeSheet)));
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
  const explain=detail('What connecting and sharing do',list(['Connect or sync copies the team repository’s shared infographics into a private folder on this computer. Nothing of yours is sent.','Share to team repository, from an approved infographic, sends only the files you review and confirm.','Opening the team repository or changing it never shares a draft, source or artwork. The Document Library on this computer is separate.']));
  const configure=sharedSettingsLink('Configure shared repository','workspace-part');
  const failed=failure=>{problem.textContent=failure.message;problem.hidden=false;};
  let sync=null;
  async function connect(){sync.disabled=true;problem.hidden=true;try{await request('/api/team',{operation:'connect'});await show();toast('Team repository synced.');}catch(f){failed(f);sync.textContent='Retry connection';}finally{sync.disabled=false;}}
  async function show(){
    let state;
    try{state=await request('/api/team');}catch(f){failed(f);return;}
    items.replaceChildren();
    if(!state.configured){
      configure.classList.add('button-filled');
      summary.replaceChildren(stateLine('review','No shared repository yet'),
        make('p','','Sharing uses the team repository set in shared settings. Choose Shared repository under Your workspace, save, and come back here to connect.'),
        make('p','quiet','Other studios keep their work in that repository too. Infographic Studio keeps its own work in your local workspace.'),
        ...(state.problem?[make('p','problem',state.problem)]:[]),add(make('div','bar'),configure),explain);
      return;
    }
    configure.classList.remove('button-filled');configure.textContent='Change shared repository';
    sync=button(state.connected?'Sync team repository':'Connect team repository',connect,true);
    summary.replaceChildren(stateLine(state.connected?'done':'review',state.connected?'Connected':'Not connected yet'),
      make('p','','Repository: '+state.repository+' · branch '+state.branch),
      make('p','quiet',state.connected?syncedWords(state.synced_at)+' The list below is your last synced copy; syncing again is explicit.':'Connect to copy the team repository’s shared infographics to this computer.'),
      add(make('div','bar'),sync,configure),explain);
    if(state.workspace_owner)items.append(make('p','quiet','Your workspace owner ID: '+state.workspace_owner));
    if(state.pending)items.append(add(make('div','stack'),make('p','',state.pending===1?'One shared commit has not reached the team repository.':state.pending+' shared commits have not reached the team repository.'),button('Retry pending team push',async()=>{try{await request('/api/team',{operation:'retry',expected_commit:state.head});await show();}catch(f){failed(f);}})));
    if(state.connected&&!state.items.length)items.append(make('p','quiet','No infographics are shared yet. Share one from an approved delivery.'));
    for(const entry of state.items){
      const cardNode=card(entry.title,make('p','quiet',(typeof entry.page_revision==='number'?'Shared approved revision '+entry.page_revision:'Shared approved infographic')+' · driver '+entry.claim.owner),list([...entry.missing.map(f=>'Missing or changed: '+f),...(entry.unshared_sources||[]).map(f=>'Private source not shared: '+f),...(entry.unshared_assets||[]).map(f=>'Private artwork not shared: '+f)]));
      const pdf=entry.files.find(f=>f.file==='delivery/page.pdf');if(pdf)cardNode.append(button('Download shared PDF',()=>downloadShared(entry,'pdf')));
      cardNode.append(button('Take over this shared infographic',async()=>{try{await request('/api/team',{operation:'claim',id:entry.id,expected_head:state.head,expected_claim:entry.claim});await show();}catch(f){failed(f);}}));
      if(entry.editable)cardNode.append(button('Import claimed editable copy',async()=>{try{const result=await request('/api/team',{operation:'take',id:entry.id,expected_head:state.head,expected_claim:entry.claim});closeSheet();await openProject(result.project.id);if(result.missing_sources.length||result.missing_assets.length)error('Editable copy imported without approval. Some private sources or artwork were not shared; supply them before rebuilding.');}catch(f){failed(f);}}));
      const owner=field('New driver workspace owner ID');cardNode.append(detail('Hand over to a teammate',owner.wrap,button('Hand over shared driver',async()=>{try{await request('/api/team',{operation:'claim',id:entry.id,expected_head:state.head,expected_claim:entry.claim,new_owner:owner.input.value});await show();}catch(f){failed(f);}})));items.append(cardNode);
    }
  }
  problem.hidden=true;
  sheet('Team repository',summary,problem,items,add(make('div','create-foot bar'),button('Done',closeSheet)));await show();
}
// Share to team repository. Its primary action never has to fail: with no repository set it
// is Configure shared repository, and with one set but not connected it is Connect.
async function shareSheet(delivery){
  let state;
  try{state=await request('/api/team');}catch(f){error(f.message);return;}
  if(!state.configured){
    const configure=sharedSettingsLink('Configure shared repository','workspace-part');configure.classList.add('button-filled');
    sheet('Share to team repository',stateLine('review','No shared repository yet'),make('p','','Sharing sends reviewed files to the team repository set in shared settings, and none is set up yet. Choose Shared repository under Your workspace, save, and come back to share.'),make('p','quiet','Nothing is shared until you review the exact files. The Document Library on this computer is separate.'),add(make('div','bar'),configure,button('Cancel',closeSheet)));
    return;
  }
  if(!state.connected){
    const problem=make('p','problem');problem.setAttribute('role','alert');
    const connect=button('Connect team repository',async()=>{connect.disabled=true;problem.textContent='';try{await request('/api/team',{operation:'connect'});toast('Team repository synced.');await shareSheet(delivery);}catch(f){problem.textContent=f.message;connect.textContent='Retry connection';}finally{connect.disabled=false;}},true);
    sheet('Share to team repository',stateLine('review','Not connected yet'),make('p','','Repository: '+state.repository+' · branch '+state.branch),make('p','','Connect first: it copies the team repository’s shared infographics to this computer and sends nothing of yours. Then choose the files to share.'),problem,add(make('div','bar'),connect,button('Cancel',closeSheet)));
    return;
  }
  const editable=make('input');editable.type='checkbox';const include=add(make('label','check'),editable,document.createTextNode('Include editable project (private brief, facts and source metadata)'));
  const picks=make('div','stack'),sourceIds=new Set(),assetIds=new Set();
  for(const[kind,records,selected]of[['source',held.project.sources,sourceIds],['artwork',held.project.assets,assetIds]])for(const record of records){const check=make('input');check.type='checkbox';check.disabled=true;editable.addEventListener('change',()=>{check.disabled=!editable.checked;if(!editable.checked){check.checked=false;selected.clear();}});check.addEventListener('change',()=>{if(check.checked)selected.add(record.id);else selected.delete(record.id);});picks.append(add(make('label','check'),check,document.createTextNode('Include private '+kind+': '+(record.name||record.id))));}
  const problem=make('p','problem');const preview=button('Review exact files to share',async()=>{preview.disabled=true;try{
    const selection={export_id:delivery.id,include_editable:editable.checked,source_ids:[...sourceIds],asset_ids:[...assetIds]};
    const result=(await request('/api/action',{action:'team-preview',id:held.project.id,expected_revision:held.project.revision,...selection})).result;
    const confirm=make('input');confirm.type='checkbox';const send=button('Share these files',()=>{if(selection.include_editable&&!confirm.checked){error('Confirm the displayed private inventory before sharing.');return;}action('team-share',{...selection,inventory_digest:result.inventory_digest,expected_head:result.expected_head,expected_claim:result.expected_claim,expected_connection:result.expected_connection,confirm_private:confirm.checked});},true);
    sheet('Confirm team sharing',make('p','','Only these files are committed and pushed to the configured team repository. Prompts and image job records are excluded.'),list(result.files.map(f=>f.file+' · '+f.bytes+' bytes')),selection.include_editable?add(make('label','check'),confirm,document.createTextNode('I am allowed to share the selected private project, sources and artwork.')):make('p','quiet','Approved delivery and title only.'),add(make('div','bar'),send,button('Cancel',closeSheet)));
  }catch(f){problem.textContent=f.message;}finally{preview.disabled=false;}},true);
  sheet('Share to team repository',make('p','','Default: the approved delivery and its title, shared to '+state.repository+'. Optional editable content needs separate selection.'),include,picks,problem,detail('More team repository actions',button('Open team repository',teamSheet)),add(make('div','bar'),preview,button('Cancel',closeSheet)));
}
async function downloadShared(entry,format){try{const response=await fetch('/api/team-download?id='+encodeURIComponent(entry.id)+'&format='+format,{headers:{'X-Infographic-Studio-Token':token}});if(!response.ok)throw Error('This shared delivery is unavailable.');const url=URL.createObjectURL(await response.blob());const link=make('a');link.href=url;link.download=entry.title+'.'+format;link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}catch(f){error(f.message);}}
