// Training Studio's page materials and interaction patterns, with Blog Studio's modes.
'use strict';
const RUN_LABELS={desk:'On the desk','on-desk':'On the desk','waiting-for-approval':'Waiting for your review','in-chat':'In the conversation','needs-attention':'Needs attention',queued:'Waiting to start',working:'Working on its own',failed:'Stopped: something went wrong',paused:'Paused',stopped:'Stopped',complete:'Finished here'};
const STAGE_STATUSES={draft:'Waiting for you',approved:'Approved',pending:'Not started',stale:'Needs a new review'};
const BLOG_MODES=[['ideas','Explore ideas','Find three useful angles before choosing one.'],['from-files','New blog from my files','Your uploaded files, each with a role; find angles, or give the point.'],['from-outline','Use my outline','Draft from your supplied structure.'],['write','Write a blog','From a brief and selected sources to a finished draft.'],['outline','Outline only','Work out the argument and stop before drafting.'],['revise','Revise a draft','Improve a manuscript, keeping its original.'],['review','Review a draft','Give feedback without rewriting the manuscript.']];
const STUDIO_ICONS={home:['M4 11.5 12 4.5l8 7','M6.5 10.5V19.5h11V10.5'],blogs:['M12 4 3.5 8.5 12 13l8.5-4.5z','M3.5 12.5 12 17l8.5-4.5','M3.5 16.5 12 21l8.5-4.5'],status:['M3 12.5h4l2.5-6.5 4.5 12 2.5-5.5H21'],voices:['M12 4a3 3 0 0 0-3 3v5a3 3 0 0 0 6 0V7a3 3 0 0 0-3-3z','M6 11.5a6 6 0 0 0 12 0','M12 17.5V20.5'],settings:['M4.5 7.5h7','M16.5 7.5h3','M14 5.5a2 2 0 1 0 0 4 2 2 0 0 0 0-4z','M4.5 16.5h3','M12.5 16.5h7','M10 14.5a2 2 0 1 0 0 4 2 2 0 0 0 0-4z'],back:['M14.5 5.5 8 12l6.5 6.5'],check:['M5.5 12.5 10 17l8.5-10'],eye:['M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z','M12 9.2a2.8 2.8 0 1 0 0 5.6 2.8 2.8 0 0 0 0-5.6z'],warn:['M12 6v7.5','M12 17.5h.01']};
const REVIEW_WORDS={balanced:'Balanced',automatic:'Automatic draft',step_by_step:'Step by step'};
const LEVEL_CHOICES=Object.entries(REVIEW_WORDS);
// Where research may look, said one way wherever it is chosen: your documents, your sites
// (the shared list in Shared settings) and/or the public web. Older words read as they meant.
const OLD_RESEARCH={none:{documents:false,sites:false,web:false},'supplied-only':{documents:true,sites:false,web:false},'web-allowed':{documents:true,sites:false,web:true}};
// How your sites are searched, said wherever they are ticked.
const SITE_SEARCH='Your sites are searched with the assistant’s web search; only pages under them are saved.';
// The editor's research words, for a check on a saved manuscript.
const EDITOR_RESEARCH=[['supplied-only','Your documents'],['web-allowed','Your documents and the public web']];
// A file's role on the files card, as the server names it.
const FILE_ROLES={material:'facts',messaging:'messaging',inspiration:'example'};
const STAGE_WORDS={'claims-map':'the claims in your material',angles:'the angles','research-plan':'the research plan',research:'the research findings',outline:'the outline',draft:'the draft',review:'the review',package:'the handoff'};
const DOING={'claims-map':'Mapping the claims in your material',angles:'Finding angles','research-plan':'Planning research',research:'Researching',outline:'Outlining',draft:'Drafting',review:'Reviewing',package:'Writing the handoff'};
const studio={screen:'home',id:null,stage:null,turn:0,listing:[],ordinary:[],total:0,options:null,settings:null,found:null,shown:null,sheet:null,polling:false,busy:false,signature:''};
function sNode(tag,cls,text){return element(tag,text,cls);}
function sAdd(parent,...children){parent.append(...children.filter(child=>child!==null&&child!==undefined));return parent;}
function sIcon(name){const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('class','icon');svg.setAttribute('aria-hidden','true');for(const d of STUDIO_ICONS[name]||[]){const path=document.createElementNS('http://www.w3.org/2000/svg','path');path.setAttribute('d',d);svg.append(path);}return svg;}
function sButton(label,action,kind='quiet'){const node=sNode('button','button'+(kind?' button-'+kind:''),label);node.type='button';node.addEventListener('click',async()=>{try{await action(node);}catch(error){notice(error.message,true);}});return node;}
function sPickCard(title,says,action){const node=sNode('button','pick-card',title);node.type='button';node.append(sNode('span','pick-says',says));node.addEventListener('click',async()=>{try{await action(node);}catch(error){notice(error.message,true);}});return node;}
function sCard(title,...children){return sAdd(sNode('section','card'),sNode('h2','card-title',title),...children);}
function sBead(kind){const node=sNode('span','bead');node.dataset.state=kind;node.setAttribute('aria-hidden','true');if(['done','review','late'].includes(kind))node.append(sIcon({done:'check',review:'eye',late:'warn'}[kind]));return node;}
function sKind(row,found){if(row.status==='approved')return 'done';if(row.status==='draft')return 'review';if(row.status==='stale')return 'late';return found.status==='working'&&row.stage===found.next?'current':'none';}
function sStatus(kind,label){return sAdd(sNode('span','state'),sBead(kind),sNode('span','',label));}
function sStages(found,small=false){const list=sNode('ol','beads'+(small?' beads-small':''));list.setAttribute('aria-label','Writing stages');for(const row of found.stages||[]){const item=sNode('li','bead-stage');item.dataset.state=sKind(row,found);item.title=row.label+': '+(STAGE_STATUSES[row.status]||row.status);item.append(sBead(sKind(row,found)),sNode('span','bead-name',found.mode==='ideas'&&row.stage==='outline'?'Ideas':row.label));list.append(item);}return list;}
function sWords(found){if(sEditingRun(found)){if(found.status==='waiting-for-approval')return 'Suggestions ready';if(found.status==='paused'||found.status==='complete')return 'Ready to edit';if(found.status==='working')return {polish:'Polishing writing','factual-support':'Checking facts',shape:'Reviewing structure',geo:'Reviewing citation readiness',revise:'Revising draft'}[found.editor_check]||'Reviewing writing';}return RUN_LABELS[found.status]||found.status;}
function sNeeds(found){return ['waiting-for-approval','failed','needs-attention'].includes(found.status);}
function sField(id,label,held,key,about={}){
  const box=sNode('div','field'),caption=sNode('label','field-label',label),input=sNode(about.options?'select':about.long?'textarea':'input','input'+(about.short?' input-short':''));caption.htmlFor=id;input.id=id;input.name=key;
  if(about.options){for(const [value,text]of about.options){const option=sNode('option','',text);option.value=value;input.append(option);}}else{if(!about.long)input.type=about.type||'text';if(about.long)input.rows=3;if(about.max)input.maxLength=about.max;if(about.min!==undefined)input.min=String(about.min);if(about.maximum!==undefined)input.max=String(about.maximum);if(about.step)input.step=String(about.step);}
  input.value=held[key]??'';input.required=!!about.required;input.readOnly=!!about.readOnly;input.addEventListener(about.options?'change':'input',()=>{held[key]=input.value;if(about.changed)return about.changed(input.value);});box.append(caption,input);
  if(about.hint){const hint=sNode('p','quiet field-hint',about.hint);hint.id=id+'-hint';input.setAttribute('aria-describedby',hint.id);box.append(hint);}return box;
}
function sChoice(label,options,held,key,changed){const box=sNode('div','field'),group=sNode('div','segmented');group.setAttribute('role','group');group.setAttribute('aria-label',label);group.dataset.count=String(options.length);group.dataset.at=String(Math.max(0,options.findIndex(([value])=>value===held[key])));group.append(sNode('span','seg-thumb'));for(const [value,text]of options){const button=sNode('button','seg-option',text);button.type='button';button.setAttribute('aria-pressed',String(held[key]===value));button.addEventListener('click',()=>{held[key]=value;group.dataset.at=String(options.findIndex(([v])=>v===value));for(const node of group.querySelectorAll('button'))node.setAttribute('aria-pressed',String(node===button));if(changed)return changed(value);});group.append(button);}return sAdd(box,sNode('p','field-label',label),group);}
function sSeries(items){return items.length<2?items.join(''):items.slice(0,-1).join(', ')+' and '+items[items.length-1];}
function sNarrow(){return typeof window.matchMedia==='function'&&!!window.matchMedia('(max-width: 52rem)').matches;}
// A phone keeps the one decision in the toolbar; the rest open from the menu beside it.
function sFold(actions){actions=actions.filter(Boolean);if(!sNarrow()||actions.length<2)return actions;const lead=actions.find(node=>/\bbutton-filled\b/.test(node.className))||actions[0];const rest=actions.filter(node=>node!==lead);for(const node of rest)node.className='menu-item';const menu=sNode('details','menu'),opener=sNode('summary','button button-round','⋯');opener.setAttribute('aria-label','More');return [lead,sAdd(menu,opener,sAdd(sNode('div','menu-list'),...rest))];}
// Your sites: the shared list the page was sent, and the sentences an incomplete choice says.
function sSharedSites(){return studio.options?.settings?.research_sites||studio.settings?.research_sites||[];}
function sResearchWord(key){return (studio.options?.settings?.research_words||studio.settings?.research_words||{})[key]||'';}
function sSiteShown(site){return String(site).replace(/^https:\/\//,'');}
function sSiteList(from){const shared=sSharedSites();return [...shared,...(from.added||[]).filter(site=>!shared.includes(site))];}
function sChosenSites(from){return sSiteList(from).filter(site=>(from.picked||[]).includes(site));}
// Whether a stage stops for the person under a level: angles and the last stage always, every
// stage step by step, and under Balanced the first writing stage (the outline, else the draft).
function sIsStop(level,stages,stage){const last=stages[stages.length-1],first=stages.includes('outline')?'outline':'draft';return stage==='angles'||level==='step_by_step'||stage===last||level==='balanced'&&stage===first;}
// What Ask for changes said once it was sent: where the stage comes back for the person.
function sChangedSays(found,stage){const words=STAGE_WORDS[stage]||'the stage',stages=(found.stages||[]).map(row=>row.stage);if(sIsStop(found.review_level||'step_by_step',stages,stage))return 'Your changes are noted. The next '+words.replace(/^the /,'')+' comes back for your review.';const next=found.ahead?.next_gate;return 'Your changes are noted. '+words.charAt(0).toUpperCase()+words.slice(1)+' is written again and the run goes on to '+(STAGE_WORDS[next]||'its next stop')+', where you see it.';}
function sSitePicker(from,id,changed){
  const node=sNode('div','site-choices'),list=sNode('div','source-choices'),held={site:''},problem=sNode('p','problem');problem.setAttribute('role','alert');
  const draw=()=>{list.replaceChildren();const sites=sSiteList(from);sites.forEach((site,at)=>{const label=sNode('label','check'),input=sNode('input','');input.type='checkbox';input.id=id+'-site-'+at;input.checked=from.picked.includes(site);input.addEventListener('change',()=>{from.picked=from.picked.filter(one=>one!==site);if(input.checked)from.picked.push(site);changed();});label.append(input,sAdd(sNode('span',''),sNode('span','',sSiteShown(site)),from.added.includes(site)?sNode('span','quiet',' · this piece of work only'):null));list.append(label);});if(!sites.length)list.append(sNode('p','quiet','No sites are in Shared settings yet. Add one for this piece of work, or add your sites in Shared settings.'));};
  const field=sField(id+'-add','Add a site for this piece of work',held,'site',{max:2000,hint:'An https address such as docs.example.com/guide. It is used for this piece of work only; your shared list stays as it is.'}),input=field.querySelector('input');
  const adding=async button=>{const typed=held.site.trim();if(!typed||button.disabled)return;await busy(button,'Checking…',async()=>{try{const found=await api('research-site',{site:typed});if(!sSiteList(from).includes(found.site))from.added.push(found.site);if(!from.picked.includes(found.site))from.picked.push(found.site);held.site='';input.value='';problem.textContent='';draw();changed();}catch(error){problem.textContent=error.message;}});},add=sButton('Add the site',adding);
  // Return adds the site; it never starts the piece of work.
  input.addEventListener('keydown',event=>{if(event.key==='Enter'){event.preventDefault();adding(add);}});
  draw();return sAdd(node,sNode('p','quiet site-search',SITE_SEARCH),list,field,sAdd(sNode('div','bar'),add),problem);
}
// Settings: where research looks for a new blog, as three ticks; none ticked is no research.
function sResearchDefault(held){const ticks={...(OLD_RESEARCH[held.research]||held.research||OLD_RESEARCH['supplied-only'])},count=sSharedSites().length;held.research={documents:!!ticks.documents,sites:!!ticks.sites,web:!!ticks.web};const group=sNode('fieldset','research-choices');sAdd(group,sNode('legend','field-label','Research for new blogs from:'),...[['documents','your documents'],['sites','your sites ('+count+')'],['web','the public web']].map(([key,label])=>{const row=sNode('label','check'),input=sNode('input','');input.type='checkbox';input.id='settings-research-'+key;input.checked=held.research[key];input.addEventListener('change',()=>{held.research[key]=input.checked;});row.append(input,sNode('span','',label));return row;}));return sAdd(sNode('div','field research-from'),group,sNode('p','quiet field-hint','A new blog starts with Search my sites and Search the web too ticked as here, and can change them on its start. Your documents are always read. Your sites are the list in Shared settings; a new blog can tick fewer or add one of its own. '+SITE_SEARCH));}

// One line under the beads: how many steps are left, where the run next stops for the person
// under its own level, and what it has spent so far, all as the runner says them.
function sAhead(found){const ahead=found.ahead;if(!ahead||found.complete)return null;const parts=[];if(ahead.steps_left)parts.push(ahead.steps_left+' step'+(ahead.steps_left===1?'':'s')+' left');if(ahead.next_gate)parts.push('Next stop: '+(found.mode==='ideas'&&ahead.next_gate==='outline'?'the ideas':STAGE_WORDS[ahead.next_gate]||ahead.next_stop));if(ahead.spent)parts.push('So far '+(found.team?'on this computer ':'')+ahead.spent);return parts.length?sNode('p','quiet ahead-line',parts.join(' · ')):null;}
// Settings: where new work stops in every studio, saved at once, refused when another studio
// changed it since this page read it.
function sWhereNewWorkStops(){const card=sNode('section','card'),fill=said=>{const held={level:studio.settings.review_level||'step_by_step'},problem=sNode('p','problem',said);problem.setAttribute('role','alert');card.replaceChildren(sNode('h2','card-title','Where new work stops'),sNode('p','quiet','Where a new deck, a new training or a blog run step by step in chat stops for you, in every studio. A blog on the writing desk has no stops: you edit it when you choose.'),sChoice('Review level',LEVEL_CHOICES,held,'level',async value=>{let said='';try{studio.settings=await api('review-level',{level:value,seen:studio.settings.review_level});if(studio.options?.settings)studio.options.settings.review_level=studio.settings.review_level;sToast('New work in every studio now starts at '+REVIEW_WORDS[value]+'.');}catch(error){said=error.message;}fill(said);}),problem);};fill('');return card;}
// What it is doing now, and for how long: under the title while a job works.
const RESEARCH_PHASES={author:'writing the report',review:'the independent check'};
// Research says its round: 0 while public sources are found, then each author and check.
function sRound(found){const research=found.next==='research'?found.research:null;if(!research||!Number.isInteger(research.round))return null;return research.round?'Round '+research.round+' of '+research.rounds+(RESEARCH_PHASES[research.phase]?', '+RESEARCH_PHASES[research.phase]:''):'Finding public sources';}
function sNowLine(found){if(found.status!=='working'||!found.started_at||!found.next)return null;const minutes=Math.max(0,Math.round((Date.now()-Date.parse(found.started_at))/60000)),limit=Math.round(found.seconds/60);return sNode('p','now-line',[found.mode==='ideas'&&found.next==='outline'?'Exploring ideas':DOING[found.next]||'Working',sRound(found),minutes+' min of up to '+limit].filter(Boolean).join(' · '));}
function sTimeLimit(found){return found.status==='failed'&&(found.reason==='time-limit'||/time limit|time a step may take/.test(found.error||''));}
// Where the limit lives: Settings sets it for new blogs; this blog keeps the one it started with.
const LONGEST_STEP=3600;
// A step's limit in words, as the server says it: '45 seconds', '1 minute', '1.5 minutes'.
function sLimit(seconds){if(seconds<60){const whole=Math.max(1,Math.round(seconds));return whole+' second'+(whole===1?'':'s');}const minutes=Math.round(seconds/6)/10;return minutes+' minute'+(minutes===1?'':'s');}
function sLimitWord(seconds){return sLimit(seconds).replace(/ (second|minute)s?$/,'-$1');}
function sMoreTime(found){return found.seconds<LONGEST_STEP;}
function sTimeWords(found){const said='The limit is in Settings → Step time limit and applies to blogs started after a change.';if(!sMoreTime(found))return said+' '+sLimit(LONGEST_STEP)+' is the longest a step may take.';const more=Math.min(LONGEST_STEP,found.seconds*2);return said+' Try again with more time '+(more===found.seconds*2?'doubles it to ':'raises it to ')+sLimit(more)+' for this blog.';}
// A CLI that failed: where to check it, and the last lines it printed, kept on this computer.
function sCliFailure(found){if(found.status!=='failed'||!(found.reason==='cli'||/Check this computer/.test(found.error||'')))return [];return [sAdd(sNode('div','bar'),sButton('Open Status',()=>sRoute('status'))),found.said?.length?disclosure('What the assistant said',sNode('p','quiet','The last lines its command printed. They are kept on this computer only, beside this blog’s run.'),sNode('p','row-quote',found.said.join('\n'))):null];}
// What the last research attempt took, as its jobs and the assistant reported them.
function sTook(last){if(!last?.jobs)return '';const whole=Math.round(last.seconds||0),m=Math.floor(whole/60),sec=whole%60,time=[m?m+' min':null,sec||!m?sec+' s':null].filter(Boolean).join(' '),used=[last.tokens!=null?last.tokens.toLocaleString('en-US')+' tokens':null,last.dollars!=null&&last.dollars>=0.005?'about $'+last.dollars.toFixed(2):null].filter(Boolean);return ' The last attempt took '+last.jobs+' job'+(last.jobs===1?'':'s')+(last.rounds?' in '+last.rounds+' round'+(last.rounds===1?'':'s'):'')+': '+time+(used.length?', '+sSeries(used)+', as the assistant reported':last.reported?'; the assistant reported no tokens or cost for every job':'; the assistant reported no tokens or cost')+'.';}
function sRetryWords(found){const limit=sLimitWord(found.seconds);if(found.next==='research'&&found.research?.contract){const rounds=found.research.rounds||3,from={kept:'Try again continues from the kept draft: up to '+rounds+' more rounds',accepted:'Try again starts from the accepted research: up to '+rounds+' rounds'}[found.research.from]||'Try again starts the research again: up to '+rounds+' rounds';return from+' of writing and checking, within this blog’s '+limit+' limit for the whole research step.'+sTook(found.research.last);}return 'Try again makes '+STAGE_WORDS[found.next]+' again in a new job, with the same '+limit+' limit; saved work is kept.';}
function sCopyButton(content){return sButton('Copy Markdown',async()=>{if(typeof navigator==='undefined'||!navigator.clipboard?.writeText)throw new Error('Select and copy the text instead.');await navigator.clipboard.writeText(content);sToast('Markdown copied.');});}
function sFrame(title,actions=[],above='',back=null){
  $('studio-toolbar').dataset.workflow='';
  $('title').textContent=title;$('title').title=title;$('above').textContent=above;$('above').hidden=!above;$('actions').replaceChildren(...actions.filter(Boolean));$('toolbar-lead').replaceChildren();if(back){const b=sButton('Back',back);b.setAttribute('aria-label','Back');b.replaceChildren(sIcon('back'));$('toolbar-lead').append(b);}
  $('studio-page').hidden=false;$('editorial-screen').hidden=true;for(const node of document.querySelectorAll('.sidebar button'))node.removeAttribute('aria-current');const parent=['run','gate','editor','google','draft','polish','desk','desk-start'].includes(studio.screen)?'blogs':studio.screen==='setup'||studio.screen==='voices'?'settings':studio.screen;const nav=$('go-'+parent);if(nav)nav.setAttribute('aria-current','page');const needs=studio.listing.filter(sNeeds).length;$('needs-count').textContent=String(needs);$('needs-count').hidden=!needs;document.title=(needs?'('+needs+') ':'')+title+' · Blog Studio';
}
function sPage(...nodes){$('studio-page').replaceChildren(...nodes.filter(Boolean));}
function sToast(message){const toast=sNode('p','toast glass',message);$('toasts').append(toast);setTimeout(()=>toast.remove(),5000);}
function sRoute(screen,id=null,stage=null,replace=false){const query=new URLSearchParams({screen});if(id)query.set('id',id);if(stage)query.set('stage',stage);history[replace?'replaceState':'pushState'](null,'',location.pathname+'?'+query);return studioNavigate(screen,id,stage);}
async function studioNavigate(screen,id=null,stage=null){
  if(studio.screen==='desk'&&(screen!=='desk'||id!==studio.id)&&typeof sDeskShare==='function')sDeskShare(studio.desk);
  if(screen==='voices'&&studio.screen!=='voices')studio.kindsFrom=studio.screen;  // Kinds of post goes Back to where it was opened.
  // The old new-blog wizard's address opens the desk start, as New blog does.
  if(screen==='new'){history.replaceState(null,'',location.pathname+'?screen=desk-start');studio.deskStart=null;studio.deskPreset=null;screen='desk-start';}
  if(!['home','blogs','guides','voices','status','settings','setup','google','draft','polish','run','gate','editor','editorial','desk','desk-start'].includes(screen))screen='home';if(screen==='editorial')return sLegacy(id||'board',false);const sameWork=studio.id===id&&['editor','run','gate'].includes(screen)&&['editor','run','gate'].includes(studio.screen);sTop();sCloseSheet();studio.screen=screen;studio.id=id;studio.stage=stage;studio.turn++;studio.signature='';const turn=studio.turn;if(!sameWork){sFrame(screen==='desk'?'Writing desk':screen==='desk-start'?'New blog':screen==='gate'?'Review':screen==='run'?'Writing run':screen==='setup'?'Set up Blog Studio':screen==='voices'?sVoicesTitle():screen==='guides'?'Voice guides':screen[0].toUpperCase()+screen.slice(1));sPage(sNode('p','studio-loading','Reading saved work…'));}else{for(const node of [...$('actions').querySelectorAll('button'),...$('studio-page').querySelectorAll('button')])node.disabled=true;}$('studio-page').setAttribute('aria-busy','true');
  try{
    if(['home','blogs','status'].includes(screen)){await sReadList(turn);if(turn!==studio.turn)return;if(screen==='home')sHome();else if(screen==='blogs')sBlogs();else {const computer=await api('computer');if(turn!==studio.turn)return;studio.computer=computer;studio.brand=computer.brand;sStatusPage();}}
    else if(['settings','setup'].includes(screen)){const [team,settings,brand,options]=await Promise.all([api('team'),api('run-settings'),api('brand'),studio.options||api('run-options')]);if(turn===studio.turn){studio.team=team;studio.settings=settings;studio.brand=brand;studio.options=options;sSettings(screen==='setup');}}
    else if(screen==='voices'){await sVoicesPage(turn);}
    else if(screen==='guides'){await sGuidesPage(turn);}
    else if(screen==='editor'){await sEditor(id);}
    else if(screen==='desk'){await sDesk(id);}
    else if(screen==='desk-start'){await sDeskStart();}
    else if(screen==='google'){sGooglePage();}
    else if(screen==='draft'){sPolishIntake('paste');}
    else if(screen==='polish'){sPolishIntake();}
    else if(screen==='run'||screen==='gate'){const found=await api('run?id='+encodeURIComponent(id));if(turn!==studio.turn)return;studio.found=found;if(found.on_desk){if(screen!=='run')await sRoute('run',found.id,null,true);else sRun(found);return;}if(sEditingRun(found)&&!found.complete){await sRoute('editor',found.id,null,true);return;}if(screen==='run'&&stage!=='status'&&sWritingReady(found)){await sRoute('gate',found.id,found.next,true);return;}if(screen==='gate')await sReadGate(stage||found.next);else sRun(found);}
    if(turn===studio.turn&&screen==='editor')$('title').focus({preventScroll:true});
  }catch(error){if(turn===studio.turn)sPage(sCard('This view could not be read',sNode('p','problem',error.message),sButton('Try again',()=>studioNavigate(screen,id,stage))));}
  finally{if(turn===studio.turn)$('studio-page').removeAttribute('aria-busy');}
}
async function sReadList(turn=studio.turn){const results=await Promise.all([api('runs'),api('board?limit=20'),api('run-options'),api('team')]);if(turn!==studio.turn)return false;studio.listing=results[0].items;studio.deleted=results[0].deleted||[];const guided=new Set(studio.listing.map(row=>row.id));studio.ordinary=results[1].items.filter(row=>!guided.has(row.id));studio.total=results[1].total;studio.options=results[2];studio.settings=results[2].settings;studio.brand=results[2].brand;studio.team=results[3];return true;}
function sTop(){if(typeof window.scrollTo==='function')window.scrollTo({top:0,behavior:'instant'});}
function sNewButton(kind='filled'){const b=sButton('New blog',()=>sDeskBegin(),kind);b.disabled=!access.actions.edit;return b;}
function sGoogleButton(){
  const button=sButton('Open Google Doc',()=>{studio.google={url:'',preview:null,confirmed:false};return sRoute('google');});
  button.disabled=!access.actions.edit;return button;
}
function sGooglePreview(found){
  if(!found||found.status!=='preview'||typeof found.preview!=='string'||!found.preview||typeof found.expected!=='string'||!found.expected||typeof found.title!=='string'||typeof found.content!=='string'||typeof found.linked_document!=='string'||!found.summary||typeof found.summary!=='object'||!found.summary.structure||typeof found.summary.structure!=='object')throw new Error('The Google Doc preview is incomplete. Read the document again before importing.');
  return found;
}
async function sGoogleResult(held,result){
  if(result?.status==='preview'){
    sGooglePreview(result);held.preview=result;held.title=result.title;studio.google=held;studio.busy=false;return sRoute('google');
  }
  if(!['already-linked','started-from-google'].includes(result?.status)||typeof result.id!=='string'||!result.id)throw new Error('The Google Doc could not be opened. Read the document again.');
  if(result.receipts||result.team_sync)savedNotice(result);
  studio.google=null;if(held.fromPolish)studio.intake=null;studio.busy=false;
  return sRoute('editor',result.id);
}
function sGooglePage(){
  const held=studio.google||(studio.google={url:'',preview:null,confirmed:false}),found=held.preview;
  if(found)sGooglePreview(found);
  const form=sNode('form','narrow'),problem=sNode('p','problem');problem.setAttribute('role','alert');
  sFrame('Polish a document',[],found?'Check the Google Doc preview':'Open your manuscript',()=>sRoute(held.fromPolish?'polish':'blogs'));
  if(!found)form.append(sCard('Your manuscript',sNode('p','','Paste the link. Check the imported text, then polish the writing and choose what to send back.'),
    sField('google-url','Google Doc link or document ID',held,'url',{required:true,max:2000,readOnly:!!found,hint:'Preview saves a private copy on this computer. It does not change the Doc, share it, or start an assistant.'}),
    disclosure('Google access help',sNode('p','quiet','Google Cloud CLI must be installed and signed in with Drive access. If access is unavailable, your saved blogs stay intact; you can upload a downloaded manuscript instead.'))));
  if(found){
    const structure=found.summary.structure||{},labels={paragraphs:'Paragraphs',headings:'Headings',list_items:'List items',links:'Links',tables:'Tables',images:'Images',footnotes:'Footnotes'};
    form.append(sCard('Check your document',link(found.linked_document,'Open original Google Doc ↗'),sNode('p','','Compare the text below with Google before opening it for editing.'),
      found.images_omitted?sNode('p','quiet','Images are omitted from this preview. Check them in the original Google Doc; the saved manuscript and formatting history keep them.'):null,
      found.summary.projection==='google-export'?sNode('p','problem','Google supplied the Markdown export because this document contains structure the built-in renderer cannot represent. Compare it with the original before confirming.'):null,
      disclosure('Import details',sField('google-title','Working title',held,'title',{required:true,max:500}),sNode('p','quiet',Object.entries(labels).map(([key,label])=>label+': '+(structure[key]||0)).join(' · ')),sNode('p','quiet',(found.summary.pending_suggestions||0)+' pending Google suggestions. Pending suggestions stay in Google and are excluded from the imported manuscript.'),sNode('p','quiet','Import keeps the original Google Doc linked. The imported copy follows this workspace’s sharing settings.'))));
    const paper=sNode('article','paper doc');paper.setAttribute('aria-label','Google manuscript preview');paper.append(window.TrainingStudioMarkdown.render(found.content));form.append(paper);
  }
  const submit=sNode('button','button button-filled',found?'Open for editing':'Read Google Doc');submit.type='submit';
  submit.disabled=studio.busy||!access.actions.edit;
  form.append(sAdd(sNode('div','form-foot'),problem,sAdd(sNode('div','bar'),submit,
    found?sButton('Choose another document',()=>{if(held.fromPolish)return sRoute('polish');studio.google={url:'',preview:null,confirmed:false};sGooglePage();}):null)));
  form.addEventListener('submit',async event=>{
    event.preventDefault();if(studio.busy||!access.actions.edit)return;
    studio.busy=true;submit.disabled=true;problem.textContent=found?'Importing the manuscript…':'Reading the selected Google Doc…';const turn=studio.turn;
    try{
      const result=found?await api('google-start',{preview:found.preview,expected:found.expected,title:held.title.trim(),confirmed:true}):await api('google-preview',{url:held.url.trim()});
      if(turn!==studio.turn||studio.google!==held)return;
      await sGoogleResult(held,result);
    }catch(error){if(turn===studio.turn)problem.textContent=error.message+' Your link and saved blogs are kept.';}
    finally{studio.busy=false;submit.disabled=!access.actions.edit;}
  });
  sPage(sWorkflowSteps(['Choose document','Check preview','Polish'],found?1:0,null),form);
}
// A finished blog that can go on the desk opens at its Done card, where Open on the desk is.
function sReview(found){if(found.flow==='desk')return ()=>sRoute('desk',found.id);if(found.complete&&found.desk_open)return ()=>sRoute('run',found.id);if(['ideas','outline'].includes(found.mode)&&found.complete)return ()=>sRoute('gate',found.id,'outline');if(sEditingRun(found)||found.complete)return ()=>sRoute('editor',found.id);return ()=>found.next&&found.status==='waiting-for-approval'?sRoute('gate',found.id,found.next):sRoute('run',found.id);}
function sRow(found){const row=sNode('li','row'+(found.status==='working'?' working':'')),text=sAdd(sNode('div','row-text'),sNode('h3','row-title',found.title),sNode('p','row-says',found.error||sWords(found)));return sAdd(row,sBead(sNeeds(found)?'review':found.complete?'done':found.status==='working'?'current':'none'),text,sRowActions(sButton(sEditingRun(found)||found.flow==='desk'?'Continue editing':sNeeds(found)?'Continue review':'Continue',sReview(found)),found));}
// A listed blog's way in, with Delete beside it where it has one: the same sheet as its card on Blogs.
function sRowActions(go,found){const remove=sDeleteAction(found);return remove?sAdd(sNode('div','bar row-actions'),go,remove):go;}
function sGroup(title,found,kind=''){if(!found.length)return null;const rows=sNode('ul','rows');for(const item of found)rows.append(sRow(item));const card=sCard(title,rows);if(kind)card.className+=' '+kind;return card;}
function sGreeting(needs){const hour=new Date().getHours(),hello=hour<12?'Good morning.':hour<18?'Good afternoon.':'Good evening.',counted=['Nothing needs','One thing needs','Two things need','Three things need','Four things need','Five things need','Six things need','Seven things need','Eight things need','Nine things need','Ten things need'];return hello+' '+(needs<counted.length?counted[needs]:needs+' things need')+' you'+(needs?'.':' right now.');}
function sHome(){const open=studio.listing.filter(found=>!found.complete),waiting=open.filter(sNeeds),first=waiting[0];sFrame('Home',[sNewButton(first?'':'filled'),first?sButton('Review '+first.title,sReview(first),'filled'):null]);sPage(sNode('p','large-title',sGreeting(waiting.length)),sGroup('Needs you',waiting,'card-needs'),sGroup('In progress',open.filter(found=>!sNeeds(found))),studio.ordinary.length?sCard('Saved drafts',...studio.ordinary.slice(0,5).map(found=>sAdd(sNode('div','row'),sNode('h3','row-title',found.title),sRowActions(sButton('Continue editing',()=>sRoute('editor',found.id)),found)))):null,sStartTasks(),sSetupTasks(),sGroup('Finished drafts',studio.listing.filter(found=>found.complete)),sNode('p','foot quiet','Your writing is saved as you work. Google feedback is sent only when you choose Send.'));}
function sDeleteAction(found){if(found.location==='hub')return null;const remove=sButton('Delete',()=>sDeleteSheet({id:found.id,title:found.title,status:found.status||'',team:!!(found.team||studio.team?.joined)}));remove.disabled=!sCanEdit(found);return remove;}
function sBlogCard(found){return sCard(found.title,sNode('p','quiet',found.flow==='desk'?'On the writing desk':sEditingRun(found)?'Editing a manuscript':BLOG_MODES.find(([mode])=>mode===found.mode)?.[1]||'Saved draft'),sStatus(sNeeds(found)?'review':found.complete?'done':found.status==='working'?'current':'none',sWords(found)),sAdd(sNode('div','bar'),sButton(sEditingRun(found)||found.flow==='desk'?'Continue editing':found.status==='waiting-for-approval'?'Continue review':'Continue',sReview(found),'filled'),sDeleteAction(found)));}
function sTools(){sOpenSheet('Library and team tools',sButton('Tools',()=>sMoreTools()),sButton(sVoicesOn()?'Voices and styles':'Kinds of post',()=>sVoiceTools()),sButton('Add to the library',()=>sLibraryAdd()),...Object.entries({board:'All blogs',inbox:'Review findings',library:'Team library',memory:'Team memory'}).map(([name,label])=>sButton(label,()=>sLegacy(name))),sButton('Close',sCloseSheet));}
function sBlogs(){sFrame('Blogs',[sNewButton('filled'),sButton('Library and team tools',sTools)]);const grid=sNode('div','grid');for(const found of studio.listing)grid.append(sBlogCard(found));for(const found of studio.ordinary)grid.append(sCard(found.title,sNode('p','quiet',found.author||'Saved draft'),sAdd(sNode('div','bar'),sButton(found.mode==='interview'?'Resume interview':'Continue editing',()=>found.mode==='interview'?sInterview(found.id):sRoute('editor',found.id),'filled'),sDeleteAction(found))));sPage(sNode('p','lede','Every blog on this computer. Open one to keep writing; the team library, review findings and team memory are under Library and team tools.'),grid.children.length?grid:sCard('No drafts yet',sNode('p','','Choose a starting point and make your first draft.'),sButton('Choose a task',()=>sRoute('home'),'filled')),studio.total>20?sButton('Browse all saved blogs',()=>sLegacy('board')):null,sDeletedFold());}
function sStatusPage(){sFrame('Status',[sButton('Check this computer',async button=>{const turn=studio.turn;await busy(button,'Checking…',async()=>{const found=await api('computer');if(turn!==studio.turn)return;studio.computer=found;studio.brand=found.brand;sStatusPage();});})]);const rows=sNode('ul','rows');for(const check of studio.computer?.checks||[]){const text=sAdd(sNode('div','row-text'),sNode('h3','row-title',check.label),sNode('p','quiet',check.detail));if(check.next_step)text.append(sNode('p','',check.next_step));rows.append(sAdd(sNode('li','row'),sBead(check.status==='ready'?'done':check.status==='action'?'late':'none'),text));}sPage(sCard('This computer',rows,sNode('p','quiet','These are read-only checks. They do not start a model, change your sign-in, or alter Git settings.')),disclosure('Team sharing',sTeamCard()),disclosure('Brand settings',sBrandCard()||sNode('p','quiet','No brand selected.')),studio.listing.length?disclosure('Writing activity',sGroup('Every run',studio.listing)):null,sCard('Workspace',sNode('p','path',studio.settings.workspace),sNode('p','quiet',access.message),disclosure('Installation maintenance',sNode('p','','From Terminal, use marketing-studio doctor to check tools, marketing-studio update for an explicit update, marketing-studio rollback to restore the prior installation, and marketing-studio uninstall to remove managed launchers. Writing workspaces are preserved.')),sNode('p','quiet','One job works at a time here. Each job has a time limit. Usage charges and spending limits stay with your assistant account.')));}

function sSharedFailure(error,problem,reload){
  problem.textContent=error.message;
  if(!/Shared settings changed in another studio|default voice changed/.test(error.message))return;
  problem.append(sButton('Reload shared settings',async button=>{await busy(button,'Reloading…',async()=>{try{await reload();sToast('Current shared settings loaded. Review them before saving again.');}catch(failure){problem.textContent=failure.message;}});}));
}
function sSettings(setup=false,privateDraft={}){
  const draft={...studio.settings.defaults,...privateDraft},held={...draft,minutes:String(draft.seconds/60)},form=sNode('form','narrow'),problem=sNode('p','problem');problem.setAttribute('role','alert');sFrame(setup?'Set up Blog Studio':'Settings',[],setup?'Choose the defaults for this computer':'');
  const sharedSettings=sNode('a','button','Change shared settings');sharedSettings.href='/onboarding/#'+token;form.append(sCard('Shared settings',sNode('p','','Your assistant, work folder, brand and delivery choices apply across all studios.'),sharedSettings),sWhereNewWorkStops());
  const workspace=sCard('Where your blogs are kept',sNode('p','path',studio.settings.workspace),sNode('p','quiet','The page is open for this writing workspace. Existing sources, voices and its selected Team Hub stay here.'),sNode('p','quiet','To use another workspace, open Blog Studio there with your assistant or the page command.'),sNode('p','',access.message));
  // The default voice: a confirmed voice a new blog writes as unless another is chosen, or none.
  const voices=studio.settings.voices||[];held.voice=voices.some(voice=>voice.id===studio.settings.voice?.profile_id)?studio.settings.voice.profile_id:'';
  const missing=[['codex','Codex'],['claude','Claude Code']].filter(([name])=>studio.options?.agents?.[name]===false).map(([,label])=>sNode('p','quiet field-hint',label+': Not installed — see Status.'));
  const defaults=sCard('The writing defaults',sChoice('The assistant that drafts',[['codex','Codex'],['claude','Claude Code']],held,'engine'),...missing,sField('settings-author','Author (optional)',held,'author',{max:200}),sVoicesOn()?sField('settings-voice','Default voice',held,'voice',{options:[['','None'],...voices.map(voice=>[voice.id,voice.name])],hint:'A confirmed voice, chosen as Write as for every new blog unless you pick another. It is yours, on this computer.'}):null,sField('settings-tone','Default tone',held,'tone',{max:2000}),sResearchDefault(held));
  const limits=sCard('Limits',sField('settings-minutes','The longest a step may take, in minutes',held,'minutes',{type:'number',min:.5,maximum:60,step:.5,short:true,required:true}),sNode('p','quiet','Between 30 seconds and one hour per step. This runner enforces time limits; it does not enforce a spending limit.'));
  // The older voice tools, hidden for now: one switch, closed away under Advanced.
  const shownFeatures={voice:false,...(studio.settings.features||{})},features={...shownFeatures};
  const advanced=disclosure('Advanced',sCheck('settings-voice-tools','Show the older voice tools',features,'voice','Learning a voice from samples, Write as, a default voice and Change the voice. Voice guides and Apply a voice work either way; saved voices and blogs that write as one are kept.'));
  const save=sNode('button','button button-filled',setup?'Save and start writing':'Save settings');save.type='submit';const preferences=disclosure('Writing preferences',defaults);preferences.open=!!setup;sAdd(form,preferences,disclosure('Step time limit',limits),disclosure('Workspace',workspace),setup?null:advanced,sNode('p','quiet','Your author and assistant settings are shared by all studios. Saving updates studios-config.json.'),studio.settings.migration_notice?sNode('p','quiet',studio.settings.migration_notice):null,studio.settings.shared_problem?sNode('p','problem',studio.settings.shared_problem):null,sAdd(sNode('div','form-foot'),problem,sAdd(sNode('div','bar'),save)));form.addEventListener('submit',async event=>{event.preventDefault();await busy(save,'Saving…',async()=>{try{const {minutes,voice,...values}=held;values.seconds=Math.round(Number(minutes)*60);const chosen=voices.find(found=>found.id===voice);const switches=setup?{}:{features:{voice:!!features.voice},features_before:shownFeatures};const defaultVoice=sVoicesOn()&&(setup||features.voice)?{voice:chosen?{profile_id:chosen.id,revision:chosen.revision}:null,voice_before:studio.settings.voice??null}:{};studio.settings=await api('run-settings',{...values,...defaultVoice,...switches,shared_before:studio.settings.shared_before});studio.options=null;sVoiceSwitchShown();sToast('Settings saved. Shared values are available to every studio. Existing blogs keep their choices.');await sRoute('home');}catch(error){sSharedFailure(error,problem,async()=>{studio.settings=await api('run-settings');sSettings(setup,{tone:held.tone,research:held.research,seconds:Math.round(Number(held.minutes)*60)});});}});});sPage(form,sAdd(sNode('div','narrow settings-elsewhere'),setup?null:sNode('h2','sheet-part settings-part','Elsewhere in Blog Studio'),setup?null:sVoicesOn()?sCard('Voices and styles',sNode('p','','A voice is how one person sounds; a style is the shape of a kind of writing. Choose them for each blog.'),sButton('Open voices and styles',()=>sRoute('voices'))):sCard('Kinds of post',sNode('p','',KINDS_SAY),sButton('Open kinds of post',()=>sRoute('voices'))),disclosure('Brand settings',sBrandCard()||sNode('p','quiet','No brand selected.')),disclosure('Team sharing',sTeamCard())));
}
async function openBlogRun(ident){try{await api('run?id='+encodeURIComponent(ident));$('detail-dialog').close();return openRun(ident);}catch(error){if(error.status===400&&/no guided run/.test(error.message)){$('detail-dialog').close();return sOpenWithoutRun(ident);}throw error;}}
// A blog with no step-by-step run: a desk blog opens on the desk; a saved draft comes to the
// desk start as the draft to bring; anything else starts on the desk with its title.
async function sOpenWithoutRun(ident){
  let desk=null;try{desk=await api('desk?id='+encodeURIComponent(ident));}catch(_){desk=null;}
  if(desk){studio.desk={id:ident,view:desk,session:operationId()};return sRoute('desk',ident);}
  const saved=await api('article?'+new URLSearchParams({id:ident,location:'local'}));
  if(saved.view?.preview?.kind==='draft')return sDeskBegin({have:'draft',source:'saved',article:ident,title:saved.title||''});
  return sDeskBegin({title:saved.title||''});
}
async function openRun(ident){return sRoute('run',ident);}
function STAGE_LABEL(found,stage){return found.stages.find(row=>row.stage===stage)?.label||stage||'Finished';}
// Write as, on Interview me: a personal default ("My voice") sends its profile and revision,
// so the pin is exact; a team default voice sends no profile, so the server applies it; "No
// particular voice" sends an empty one, the described tone.
const VOICE_DEFAULT='*default',VOICE_LEARN='*learn';
// The older voice tools (Write as, the default voice, learning voices) show only with the
// switch in Settings → Advanced on. Voice guides and Apply a voice do not depend on it.
function sVoicesOn(){return !!studio.settings?.features?.voice;}
function sVoiceChoices(){const options=studio.options||{},mine=options.default_voice,list=[];if(mine)list.push([VOICE_DEFAULT,'My voice — '+mine.name+' · '+mine.status]);for(const profile of options.profiles||[])if(profile.status!=='retired'&&(!mine||profile.id!==mine.profile))list.push([profile.id,profile.name+' · '+profile.status]);list.push(['','No particular voice (use the described tone)']);return list;}
function sVoiceChoice(draft){if(!sVoicesOn()){draft.profile='';return draft.profile;}if(typeof draft.profile!=='string'||!sVoiceChoices().some(([value])=>value===draft.profile))draft.profile=studio.options?.default_voice?VOICE_DEFAULT:'';return draft.profile;}
function sVoiceSelect(draft,id='new-profile',changed){
  if(!sVoicesOn())return null;  // A new blog writes with its tone.
  let before=sVoiceChoice(draft);
  const box=sField(id,'Write as',draft,'profile',{options:[...sVoiceChoices(),[VOICE_LEARN,'Learn a new voice…']],hint:'Whose voice it is written in: yours, or the person you write for.',changed:value=>{if(value!==VOICE_LEARN){before=value;if(changed)changed(value);return;}draft.profile=before;select.value=before;sVoiceTools();}}),select=box.querySelector('select');return box;
}
// How long new writing runs, beside the kind of post: the usual length unless changed. The
// desk start offers it for a topic or an outline; a draft you bring keeps its own length.
function sLengthSelect(draft,id){draft.length=draft.length||'style';return sField(id,'Length',draft,'length',{options:[['style','The usual length'],['short','Short (about half)'],['deep','In depth (about twice)']],hint:'For the kind of post, or for a post like this one. In depth gives each main point a worked example or proof point from your material.'});}
// A learned kind of post brings the examples it was learned from: its style samples, up to
// eight, newest first, each ticked as an example from the library the person can untick. A
// starter brings none, and a change of kind swaps them.
function sStyleSamples(draft){draft.files=(draft.files||[]).filter(file=>!file.fromStyle);const style=(studio.options?.styles||[]).find(style=>style.id===draft.style);if(!style||style.kind==='seed')return;const known=new Map((studio.options?.sources||[]).map(source=>[source.id,source]));for(const id of [...(style.sample_ids||[])].slice(-8).reverse()){const source=known.get(id);if(!source||draft.files.some(file=>file.id===id))continue;draft.files.push({id,filename:source.name,state:source.status==='ready'?'ready':'pending',chars:0,note:'',link:'',role:'inspiration',library:true,kept:true,fromStyle:true});}}
// The editor's saved references to check against, a tick each.
function sSources(draft){if(!studio.options.sources.length)return sNode('p','quiet','No references are saved yet. The files above are used for this blog.');const node=sNode('div','source-choices');for(const source of studio.options.sources){const label=sNode('label','source-choice'),input=sNode('input','');input.type='checkbox';input.checked=draft.sources.includes(source.id);input.addEventListener('change',()=>{draft.sources=draft.sources.filter(id=>id!==source.id);if(input.checked)draft.sources.push(source.id);});label.append(input,sAdd(sNode('span',''),sNode('strong','',source.name),sNode('span','quiet',' · '+source.status)));node.append(label);}return node;}
// What Write as sends: a chosen voice its profile; My voice the default's exact pin; a team
// default nothing, so the server applies it; no particular voice an empty one.
function sVoicePayload(draft){if(!sVoicesOn())return {};const voice=sVoiceChoice(draft),me=studio.options?.default_voice;if(voice!==VOICE_DEFAULT)return {profile:voice};if(voice===VOICE_DEFAULT&&me?.profile&&Number.isInteger(me.revision))return {profile:me.profile,revision:me.revision};return {};}
// A run stopped at its research can drop it and go on; an existing draft can also be edited.
function sManuscriptOpen(found){return !!found.existing||(found.stages||[]).some(row=>row.stage==='draft'&&['draft','approved','stale'].includes(row.status));}
function sSkipsResearch(found){return found.approval==='page'&&!found.complete&&sCanEdit(found)&&['research-plan','research'].includes(found.next)&&['failed','stopped','paused','needs-attention'].includes(found.status);}
function sAfterResearch(found){const after=(found.stages||[]).find(row=>!['research-plan','research'].includes(row.stage)&&row.stage!=='angles');return after?STAGE_WORDS[after.stage]:'the next step';}
// What the independent research check objected to, grouped by what it checked and its verdict.
function sObjection(group){if(group.kind==='assessment'){const asked=group.asked?.length?group.asked:['the brief'],said=sSeries(asked);return said[0].toUpperCase()+said.slice(1)+(asked.length>1?' need':' needs')+' revision';}const nouns={facts:['fact','facts'],findings:['finding','findings'],prose:['passage of prose','passages of prose']}[group.kind]||[group.kind,group.kind];return group.count+' '+nouns[group.count===1?0:1]+(group.verdict?' marked '+group.verdict:'');}
function sResearchStop(found){const refusal=found.research?.refusal;if(!refusal)return null;const rows=sNode('ul','rows');for(const group of refusal.groups||[])rows.append(sAdd(sNode('li','row'),sAdd(sNode('div','row-text'),sNode('h3','row-title',sObjection(group)),group.note?sNode('p','row-quote',group.note):null)));return disclosure('What the research check objected to',...[refusal.cause?sNode('p','',refusal.cause):null,found.research.outside?sNode('p','research-outside',found.research.outside):null,sNode('p','quiet',refusal.count?refusal.count+' objection'+(refusal.count===1?'':'s')+' in its last review, after '+refusal.rounds+' rounds of writing and checking. Each group shows the first note.':'Its last review gave no reasons.'),rows.children.length?rows:null,sNode('p','quiet',found.research.kept?'The draft report and the check’s notes are kept on this computer, in this blog’s .studio-research-draft folder, and are not shared.':'The draft report could not be kept on this computer.')].filter(Boolean));}
function sRun(found){
  if(found.on_desk)return sRunOnDesk(found);
  studio.found=found;studio.signature=JSON.stringify(found);const actions=sManuscriptOpen(found)?[sButton('Edit manuscript',()=>sRoute('editor',found.id))]:[];if(found.next&&found.status==='waiting-for-approval')actions.push(sButton(found.next==='review'?'Read the review':'Review '+STAGE_LABEL(found,found.next),()=>sRoute('gate',found.id,found.next),'filled'));if(found.approval==='conversation'&&!found.complete&&access.actions.edit)actions.push(sButton('Run this from here',()=>sConfirm('start',found),'filled'));if(found.approval==='page'&&!found.complete&&sCanEdit(found)){if(!found.enabled){if(sTimeLimit(found)&&sMoreTime(found))actions.push(sButton('Try again with more time',()=>runAction('retry',found,{seconds:Math.min(LONGEST_STEP,found.seconds*2)}),'filled'));actions.push(sButton(found.status==='failed'?'Try again':'Resume',()=>runAction(found.status==='failed'?'retry':'resume',found),sTimeLimit(found)&&sMoreTime(found)?'quiet':'filled'));}else actions.push(sButton(found.status==='working'?'Pause after this step':'Pause',()=>runAction('pause',found)));if(found.status==='working')actions.push(sButton('Stop',()=>sConfirm('stop',found)));}if(sSkipsResearch(found))actions.push(sButton('Continue without research',()=>sConfirm('skip-research',found)));actions.push(sButton('Tools',()=>sMoreTools(found.id)));if(found.team){actions.push(sButton(found.driver?.here?'Hand over':found.driver?'Take over':'Take this blog',()=>sTeamDecision(found,found.driver?.here?'handover':found.driver?'takeover':'take')));if(found.complete&&sCanEdit(found))actions.push(sButton('Record in team repository',()=>sTeamDecision(found,'publish')));}sFrame(found.title,sFold(actions),'Writing run',()=>sRoute('blogs'));
  const intro=sAdd(sNode('div','intro'),sNowLine(found),sStatus(sNeeds(found)?'review':found.complete?'done':found.status==='working'?'current':'none',sWords(found)),sStages(found),sNode('p','beads-caption',found.next?STAGE_LABEL(found,found.next):'All stages approved'),sAhead(found));if(found.google)intro.append(link(found.google.url,'Open working Google Doc ↗'),sNode('p','quiet','Changes stay local. Open Edit manuscript to prepare suggestions or comments for the author.'));if(found.error){sAdd(intro,sNode('p','problem',found.error),sResearchStop(found),!found.research?.refusal&&found.research?.outside?sNode('p','quiet research-outside',found.research.outside):null,sTimeLimit(found)?sNode('p','quiet',sTimeWords(found)):null,...sCliFailure(found));if(found.status==='failed'&&found.next&&found.approval==='page')intro.append(sNode('p','quiet',sRetryWords(found)));if(sSkipsResearch(found))intro.append(sNode('p','quiet',sManuscriptOpen(found)?'Research is optional for editing. Open Edit manuscript to polish the writing without research.':'Research is optional. Continue without research takes this blog on to '+sAfterResearch(found)+', from your brief and selected sources; the later steps get no research findings.'));}if(found.approval==='conversation')intro.append(sNode('p','lede','This blog is being made in a conversation. Move it here to let the page run the remaining stages.'));
  const steps=sNode('ol','rows'),files=sNode('ul','rows');for(const row of found.stages){const text=sAdd(sNode('div','row-text'),sNode('h3','step-name',row.label),sNode('p','quiet',row.accepted_by==='review-policy'?'Continued automatically':STAGE_STATUSES[row.status]||row.status));if(row.request)text.append(sNode('p','row-quote',row.request));if(found.notes?.[row.stage])text.append(sNode('p','row-quote','Note: '+found.notes[row.stage]));const item=sAdd(sNode('li','row step'),sBead(sKind(row,found)),text);if(['draft','approved','stale'].includes(row.status)){item.append(sButton(row.stage===found.next?'Review':'Open',()=>sRoute('gate',found.id,row.stage)));files.append(sAdd(sNode('li','row'),sAdd(sNode('div','row-text'),sNode('h3','row-title',row.label),sNode('p','quiet',row.path)),sButton('Open',()=>sRoute('gate',found.id,row.stage))));}steps.append(item);}
  const about=sCard('About this blog',sNode('p','lede',found.brief.goal),sNode('p','quiet','For '+found.brief.audience),found.research_says?sNode('p','quiet research-said',found.research_says):null,sNode('p','quiet',(found.review_level?({balanced:'Balanced',automatic:'Automatic draft',step_by_step:'Step by step'}[found.review_level]+' review · '):'')+'Drafted by '+(found.engine==='codex'?'Codex':'Claude Code')+(found.model_mode==='by_task'?', using Quick, Main, and Complex model profiles':'')+'. Each step may take up to '+Math.round(found.seconds/60*10)/10+' minutes.'),found.brand?sNode('p','quiet','Brand: '+found.brand.skill+' · '+found.brand.brand+' · '+found.brand.variant):null,sAdd(sNode('div','bar'),sNode('p','quiet','Voice: '+(found.voice_mode==='preserve'?'the manuscript’s own voice':found.voice_mode==='profile'&&found.voice_name?found.voice_name:'none (the described tone)')+' · Kind of post: '+(found.style_name||'none')),sVoicesOn()&&sCanEdit(found)&&found.status!=='working'?sButton('Change the voice',()=>sChangeVoice(found)):null),sNode('p','path',found.directory)),history=sNode('ul','rows');for(const item of [...found.decisions].reverse())history.append(sAdd(sNode('li','row'),sAdd(sNode('div','row-text'),sNode('p','',item.event),sNode('p','quiet',new Date(item.at).toLocaleString()))));
  const note={request:''},noteBox=found.approval==='page'&&found.note_stage&&sCanEdit(found)?sCard('Note for the next step',sNode('p','quiet','It goes with the next job that starts, '+STAGE_LABEL(found,found.note_stage).toLowerCase()+', and stops nothing. It is kept beside the blog, not in its versions.'),sField('note-request','What should it keep in mind?',note,'request',{long:true,max:8000}),sButton('Add the note',async button=>{if(!note.request.trim())return;await busy(button,'Saving…',async()=>{await runAction('note',found,{request:note.request.trim()},true);sToast('Noted. It goes with the next job that starts.');});})):null;
  sPage(found.team?sNode('p','quiet',found.driver?(found.driver.name+' · '+(found.driver.here?'driving on this computer':'driving on another computer')):'Nobody is driving this blog. Take it to continue.'):null,intro,noteBox,found.complete?(['ideas','outline'].includes(found.mode)?sCard('Choose what to develop',sButton('Review the ideas or outline',()=>sRoute('gate',found.id,'outline'),'filled')):sDoneCard(found)):null,disclosure('Writing progress and saved files',steps,files),disclosure('About this blog',about),disclosure('Decisions and history',history),found.approval==='page'?(sCanEdit(found)?sAdd(sNode('div','bar'),sButton('Continue in the conversation',()=>sConfirm('handoff',found))):null):sContinuation(found));
}
function sWritingReady(found){return found.approval==='page'&&found.status==='waiting-for-approval'&&['outline','draft'].includes(found.next);}
function sContinuation(found){return continuation('Use Blog Studio. Continue guided blog '+found.id+' in workspace '+(found.team?found.directory.replace(/\/[^/]+$/,''):found.directory.replace(/\/articles\/[^/]+$/,''))+'. Show run status first.','Continue this blog in your conversation');}
async function sReadGate(stage){const turn=studio.turn;if(!stage){sRun(studio.found);return;}const shown=await api('run-file?'+new URLSearchParams({id:studio.id,stage}));if(turn!==studio.turn)return;studio.stage=stage;studio.shown=shown;studio.signature=JSON.stringify([studio.found.expected,stage]);sGate(studio.found,shown);}
// `outside`: the pages your sites kept out of this research, as the run says it.
function sResearchAccount(found,outside){
  const node=sNode('article','paper doc'),md=text=>window.TrainingStudioMarkdown.render(text||'');
  sAdd(node,md(found.brief),sNode('h2','doc-title','What the independent check said'),sNode('p','',found.check.said),found.check.note?sNode('p','',found.check.note):null,
    ...(found.check.unread||[]).map(one=>sNode('p','',(one.title||one.source)+': '+one.access_error)),
    sNode('h2','doc-title','What the research could not settle'),outside?sNode('p','research-outside',outside):null,...(found.gaps||[]).map(text=>sNode('p','',text)),
    ...(found.sources.partial||[]).map(one=>sNode('p','',one.title+': '+one.note)),sNode('p','quiet',found.read));
  const show=ids=>ids.map(id=>(found.findings||[]).find(one=>one.id===id)).filter(Boolean).map(one=>sAdd(sNode('div','card-part'),sNode('h3','row-title',one.title),sNode('p','',one.summary)));
  if(found.questions?.length)node.append(sNode('h2','doc-title','Your questions'));
  for(const q of found.questions||[])sAdd(node,sNode('h3','row-title',q.question),...(q.findings.length?show(q.findings):[sNode('p','quiet','The research did not answer this.')]));
  if(found.unplanned?.length)sAdd(node,sNode('h2','doc-title','Also found'),...show(found.unplanned));
  sAdd(node,disclosure('Read the full report',md(found.report)),disclosure('The evidence and the check’s notes',md(found.evidence)));
  return node;
}
function sGate(found,shown){
  const current=shown.stage===found.next,ideas=found.mode==='ideas'&&shown.stage==='outline',anglesGate=found.mode==='from-files'&&shown.stage==='angles',final=current&&!['ideas','outline'].includes(found.mode)&&found.stages.length>0&&found.stages[found.stages.length-1].stage===shown.stage,handoff=final&&shown.stage!=='draft'?(shown.bundle||[]).find(item=>item.stage==='draft')||null:null,develop=(['ideas','outline'].includes(found.mode)&&shown.stage==='outline'||anglesGate&&current&&shown.status==='draft')&&shown.expected===found.expected&&['draft','approved'].includes(shown.status)&&found.approval==='page'&&sCanEdit(found),actions=[];
  if(!anglesGate&&shown.expected===found.expected&&current&&shown.status==='draft'&&found.approval==='page'&&sCanEdit(found))actions.push(sButton(ideas?'Save ideas for later':final?'Finish':shown.stage==='outline'?'Use this outline':shown.stage==='draft'?'Use this draft':'Finish this review',button=>!final&&found.review_level&&found.review_level!=='step_by_step'?busy(button,'Approving…',()=>runAction('approve',found)):sConfirm('approve',found),ideas?'quiet':'filled'));
  if(current&&['review','package'].includes(shown.stage)&&shown.status==='draft'&&shown.expected===found.expected&&found.approval==='page'&&sCanEdit(found))actions.push(sButton("Apply the review's findings",()=>sConfirm('apply-review',found)));
  if(anglesGate&&develop)actions.push(sButton('None of these',()=>sNoneOfThese(found)));
  if(!anglesGate&&(found.complete||found.stages.findIndex(row=>row.stage===shown.stage)<=found.stages.findIndex(row=>row.stage===found.next))&&found.approval==='page'&&sCanEdit(found)){actions.push(sButton('Ask for changes',()=>sChanges(found,shown.stage)));if(current&&shown.status==='stale')actions.push(sButton('Review saved version',()=>sConfirm('adopt',found)));}
  if(develop)actions.unshift(sButton(anglesGate?'Choose an angle':ideas?'Develop an idea':'Write from this outline',()=>{
    const choice={request:'',angle:'',note:''},error=sNode('p','problem'),form=sNode('form','narrow'),go=sNode('button','button button-filled',anglesGate?'Write this angle':'Develop this choice'),angles=ideas||anglesGate?sAngles(shown.content):[];go.type='submit';go.disabled=true;error.setAttribute('role','alert');
    if(angles.length){const cards=angles.map(angle=>{const card=sPickCard(angle.title,angle.says,()=>{choice.angle=angle.title;for(const other of cards)other.setAttribute('aria-pressed',String(other===card));go.disabled=false;});card.setAttribute('aria-pressed','false');return card;});form.append(sNode('p','quiet',anglesGate?'Choose the angle to write. Its audience and point become the brief.':'Choose the angle to develop.'),sAdd(sNode('div','pick-cards'),...cards),sField('develop-note','Anything to keep or change? (optional)',choice,'note',{long:true,max:8000}));}
    else form.append(sField('develop-choice',ideas?'Which idea should we develop?':'What should the draft develop?',choice,'request',{long:true,required:true,max:8000,hint:ideas?'Name an angle and add anything you want to keep or change.':'Describe any changes or focus for the draft.',changed:()=>{go.disabled=!choice.request.trim();}}));
    form.append(error,sAdd(sNode('div','bar'),go,sButton('Cancel',sCloseSheet)));
    form.addEventListener('submit',async event=>{event.preventDefault();const request=angles.length?(choice.angle+(choice.note.trim()?'\n'+choice.note.trim():'')).trim():choice.request.trim();if(!request)return;if(request.length>8000){error.textContent='Keep the note under '+(8000-choice.angle.length-1)+' characters.';return;}await busy(go,'Starting…',async()=>{try{await runAction('develop',found,{request},true);sCloseSheet();}catch(failure){error.textContent=failure.message;}});});sOpenSheet(anglesGate?'Choose an angle':ideas?'Choose an idea':'Develop this outline',form);
  },'filled'));
  sFrame(ideas?'Ideas':shown.label,sFold(actions),found.title,()=>sRoute('run',found.id,'status'));
  const intro=sAdd(sNode('div','intro'),sStatus(shown.status==='draft'?'review':shown.status==='approved'?'done':'late',STAGE_STATUSES[shown.status]||shown.status),sStages(found),sNode('p','beads-caption',ideas?'Ideas':shown.label)),fresh=sNode('div','decision-notice');fresh.id='newer-version';fresh.hidden=true;intro.append(fresh);if(found.excerpted?.length)intro.append(sNode('p','quiet',sSeries(found.excerpted)+(found.excerpted.length===1?' was':' were')+' excerpted to fit one run: the assistant read the start of each and the passages that mention your note, not every page.'));
  const paper=(item,label)=>{const node=sNode('article','paper doc');node.setAttribute('aria-label',label);node.append(window.TrainingStudioMarkdown.render(item.preview_content??item.content));if(item.images_omitted)node.prepend(sNode('p','quiet','Images are omitted from this preview. The saved manuscript and download keep them.'));return node;};
  // At the final stop the approved draft is the open document; the package is its handoff notes.
  const doc=shown.research?sResearchAccount(shown.research,found.research?.outside):paper(handoff||shown,handoff?'Draft':ideas?'Ideas':shown.label);const reading=sAdd(sNode('section','reading'),doc);if(handoff){const notes=disclosure(shown.stage==='package'?'Handoff notes':shown.label,paper(shown,shown.label));notes.open=true;reading.append(notes);}for(const item of shown.bundle||[]){if(item===handoff)continue;const section=sNode('article','paper doc');section.append(sNode('h2','',item.label),window.TrainingStudioMarkdown.render(item.preview_content??item.content),sButton('Ask for changes to '+item.label,()=>sChanges(found,item.stage)));if(item.images_omitted)section.prepend(sNode('p','quiet','Images are omitted from this preview. The saved manuscript keeps them.'));reading.append(found.stages.find(row=>row.stage===item.stage)?.status==='approved'?disclosure('Approved '+item.label.toLowerCase(),section):section);}const checks=sNode('ul','check-items');for(const check of shown.checks){const item=sAdd(sNode('li',''),sStatus(check.passed?'done':'late',check.label));if(check.detail?.length)item.append(sAdd(sNode('ul','check-detail quiet'),...check.detail.map(line=>sNode('li','',line))));checks.append(item);}
  const checked=sAdd(sNode('section','paper aside-part'),sNode('h2','aside-title','Checked for you'),checks,sNode('p','quiet','These checks concern the saved file and its inputs. They do not verify its claims.'));
  const notes=shown.research?null:sAdd(sNode('section','paper aside-part review-notes'),sNode('h2','aside-title','Worth a look'),shown.notes?window.TrainingStudioMarkdown.render(shown.notes):sNode('p','quiet','No assistant note was submitted. Read the document before deciding.'),sNode('p','quiet','Assistant notes are its judgment. Missing evidence and citation checks remain yours to resolve.'));
  const changed=sAdd(sNode('section','paper aside-part'),sNode('h2','aside-title','What changed'),sNode('p','quiet',shown.previous===null?'No earlier approved version is recorded.':shown.previous===shown.content?'This is the version last approved.':'Compare this version with the one you last approved.'),shown.previous!==null?sButton('Show the comparison',()=>sComparison(shown)):null),needs=shown.gaps?.length?sAdd(sNode('section','paper aside-part'),sNode('h2','aside-title','Needs you before publishing'),sAdd(sNode('ul','gap-items'),...shown.gaps.map(gap=>sNode('li','',gap))),sNode('p','quiet','The writing leaves these out. Supply them before you publish.')):null,aside=sAdd(sNode('aside','aside'),checked,needs,notes,changed);aside.setAttribute('aria-label','The review');
  const reviewAside=disclosure('Review notes and checks',aside);studio.asideOpen||={};reviewAside.open=studio.asideOpen[found.id]??true;reviewAside.addEventListener('toggle',()=>{studio.asideOpen[found.id]=reviewAside.open;});
  sPage(sNode('p','lede',anglesGate?'Choose one of the three angles to write, or set them aside for three more.':ideas?'Choose an idea to develop into a draft, or save these angles for later.':handoff?'Read the finished draft and its handoff. Finish when it is ready; then copy it, download it or say where it was published.':shown.stage==='claims-map'?'Read the claims mapped to your supplied material. Continue with the supported claims, or ask for changes.':shown.stage==='research-plan'?'Read the questions this research will answer. Continue with this plan, or ask for changes.':shown.stage==='research'?'Read the research brief, its limits and the independent check. Continue with these findings, or ask for changes.':shown.stage==='outline'?'Read the outline. Use it to continue, or ask for changes.':shown.stage==='draft'?'Read the draft. Use it to go on, or ask for changes.':'Read the review. Its findings go to the handoff; to act on one, ask for changes to the draft.'),intro,found.approval==='conversation'?sAdd(sNode('section','paper callout'),sNode('p','','This blog is decided in your conversation.'),sContinuation(found)):null,sAdd(sNode('div','gate'),reading,reviewAside),sAdd(sNode('div','bar'),sButton(ideas?'Download ideas':handoff?'Download draft':shown.stage==='outline'?'Download outline':'Download document',()=>sDownload(handoff?{content:handoff.content,name:'DRAFT.md'}:shown)),sCopyButton(handoff?handoff.content:shown.content)));
}
function sComparison(shown){const diff=sNode('div','paper diff');if(!shown.diff.length)diff.append(sNode('p','quiet','No changes from the last approved version.'));for(const line of shown.diff){const row=sNode('div','diff-row',line);row.dataset.kind=line.startsWith('+')?'added':line.startsWith('-')?'removed':line.startsWith('@@')?'gap':'same';diff.append(row);}sOpenSheet('What changed',sNode('p','quiet','Last approved version compared with this version.'),diff,shown.diff_truncated?sNode('p','quiet','Comparison shortened; download the complete text if needed.'):null,sAdd(sNode('div','bar'),sButton('Close',sCloseSheet)));}
async function sDownload(shown){const blob=new Blob([shown.content],{type:'text/markdown;charset=utf-8'}),url=URL.createObjectURL(blob),a=sNode('a','');a.href=url;a.download=shown.name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function sOpenSheet(title,...nodes){sCloseSheet();studio.sheet={opener:document.activeElement};const sheet=$('sheet');const heading=sNode('h2','sheet-title',title);heading.id='sheet-title';const close=sButton('Close',sCloseSheet);close.setAttribute('aria-label','Close '+title);sheet.replaceChildren(sAdd(sNode('div','sheet-heading'),heading,close),...nodes.filter(Boolean));sheet.hidden=false;for(const id of ['main','sidebar','studio-toolbar'])$(id).inert=true;if(typeof sDeskSheetOpened==='function')sDeskSheetOpened();sheet.focus();}
function sCloseSheet(){const held=studio.sheet;studio.sheet=null;const sheet=$('sheet');if(sheet){sheet.hidden=true;sheet.replaceChildren();}for(const id of ['main','sidebar','studio-toolbar'])if($(id))$(id).inert=false;if(typeof sDeskSheetClosed==='function')sDeskSheetClosed();if(held?.opener?.isConnected)held.opener.focus();}
// What Finish did with the team library, from the run it returns.
function sFinished(updated){return updated?.library?.id?'Finished. Kept in the team library.':updated?.library?.reason?'Finished. Not kept in the team library: '+updated.library.reason:'Finished.';}
function sConfirm(action,found){const final=!['ideas','outline'].includes(found.mode)&&found.stages?.length>0&&found.next===found.stages[found.stages.length-1].stage;const specs={'apply-review':["Apply the review's findings?","This edits the draft for the review's findings only, then reviews it and writes the handoff notes again: three jobs."+(found.redo?.draft?.stages?.join(',')==='draft,review,package'?' '+found.redo.draft.says:''),'Apply them'],approve:final?['Finish this blog?','The version shown is approved against its current inputs.'+((found.keeps_draft??(sManuscriptOpen(found)||found.stages.some(row=>row.stage==='draft')))?' Its draft is kept in the team library as a reference and an example of its kind of post, shared like the rest of the library; finishing again updates that item.':' Nothing is kept in the team library: this blog has no saved draft.')+' The blog is then done here: copy it, download it, or say where it was published.','Finish']:['Approve '+STAGE_LABEL(found,found.next)+'?','You are approving the version shown, against its current inputs. If either changes, it needs your review again.','Approve'],adopt:['Review this saved version?','Your edited text is kept as it stands and brought back for approval. No assistant rewrites it.','Review saved version'],stop:['Stop this blog?','Its current worker is ended. Everything already saved is kept. You can resume later.','Stop'],handoff:['Continue in the conversation?','Its worker stops and decisions return to your assistant conversation. The same blog and its decisions stay saved.','Continue in chat'],start:['Run this from here?','The page takes over the remaining stages, using this blog’s selected assistant and time limit. It waits for you at each review.','Run from here'],'skip-research':['Continue without research?','The research steps leave this blog’s run, and it goes on to '+sAfterResearch(found)+' from your brief and selected sources. The later steps get no research findings, and research cannot be added back to this run.','Continue without research']};const [title,says,label]=specs[action],problem=sNode('p','sheet-error');problem.setAttribute('role','alert');const confirm=sButton(label,async button=>{await busy(button,'Saving…',async()=>{try{const updated=await runAction(action,found,{},true);sCloseSheet();sToast(action==='approve'&&final?sFinished(updated):action==='approve'?'Approved. The next stage can begin.':action==='skip-research'?'Continuing without research.':'Your choice is saved.');}catch(error){problem.textContent=error.message;}});},'filled');sOpenSheet(title,sNode('p','',says),problem,sAdd(sNode('div','bar'),confirm,sButton('Cancel',sCloseSheet)));}
function sChanges(found,stage){const held={stage,request:''},choices=found.next?found.stages.slice(0,found.stages.findIndex(row=>row.stage===found.next)+1):found.stages,options=choices.map(row=>[row.stage,row.label]);if(found.existing&&!options.some(([value])=>value==='draft'))options.unshift(['draft','Revise the draft']);const form=sNode('form','note'),problem=sNode('p','sheet-error');problem.setAttribute('role','alert');const submit=sNode('button','button button-filled','Send for changes');submit.type='submit';const price=sNode('p','quiet change-price',held.stage==='research'&&found.research_price?found.research_price.words:found.redo?.[held.stage]?.says||'');held.refresh=false;const refresh=sCheck('change-refresh','Bring the evidence up to date',held,'refresh',found.research_price?.refresh||'Re-reads the sources and checks the report again: about as long and as costly as the research was.');refresh.hidden=!(held.stage==='research'&&found.research_price);form.append(sField('change-stage','Which stage should change?',held,'stage',{options,changed:value=>{price.textContent=value==='research'&&found.research_price?found.research_price.words:found.redo?.[value]?.says||'';refresh.hidden=!(value==='research'&&found.research_price);if(refresh.hidden)held.refresh=false;}}),price,refresh,sField('change-request','What should change?',held,'request',{long:true,required:true,max:8000,hint:'Ask for changes writes this stage again with your words. Later stages are made again after it.'}),problem,sAdd(sNode('div','bar'),submit,sButton('Cancel',sCloseSheet)));form.addEventListener('submit',async event=>{event.preventDefault();await busy(submit,'Saving…',async()=>{try{const updated=await runAction('changes',found,held,true);sCloseSheet();sToast(updated.enabled?sChangedSays(updated,held.stage):'Changes saved. Choose Resume when you are ready.');}catch(error){problem.textContent=error.message;}});});sOpenSheet('Ask for changes',form);}
async function runAction(action,found,extra={},propagate=false){studio.busy=true;const turn=studio.turn;try{const updated=await api('run-'+action,{id:found.id,expected:found.expected,...extra});if(turn!==studio.turn)return updated;studio.found=updated;if(action==='approve'&&updated.complete){await sRoute(['ideas','outline'].includes(updated.mode)?'gate':'run',found.id,['ideas','outline'].includes(updated.mode)?'outline':'status');return updated;}await sRoute(action==='adopt'?'gate':'run',found.id,action==='adopt'?updated.next:null);return updated;}catch(error){if(propagate)throw error;notice(error.message,true);}finally{studio.busy=false;}}
function renderRun(found){studio.screen='run';sRun(found);}
function renderRuns(result){studio.listing=result.items;studio.screen='blogs';sBlogs();}
function sLegacy(name,push=true){sTop();if(!['board','inbox','library','memory'].includes(name))name='board';if(push)history.pushState(null,'',location.pathname+'?'+new URLSearchParams({screen:'editorial',id:name}));sCloseSheet();studio.screen='editorial';studio.turn++;view=name;offset=0;sFrame({board:'All blogs',inbox:'Review findings',library:'Team library',memory:'Team memory'}[name],[],'',()=>sRoute('blogs'));$('studio-page').hidden=true;$('editorial-screen').hidden=false;$('editorial-screen').dataset.view=name;legacyToolbar();$('go-blogs').setAttribute('aria-current','page');return load().catch(error=>notice(error.message,true));}
async function sPoll(){
  if(studio.polling||studio.busy||studio.sheet||['google','draft','polish','settings','setup','editorial','voices','guides','desk','desk-start'].includes(studio.screen))return;studio.polling=true;const turn=studio.turn;
  try{if(studio.screen==='editor'){
    if(!studio.editorWatching)return;
    const found=await api('run?id='+encodeURIComponent(studio.id));if(turn!==studio.turn)return;
    const summary={};for(const key of ['id','expected','status','error','enabled','next','editor_check'])summary[key]=found[key]??null;
    if(JSON.stringify(summary)!==studio.editorSignature&&studio.editorDraft?.content===studio.editorDraft?.baseContent)await sEditor(studio.id);
    return;
  }if(['home','status'].includes(studio.screen)){const brand=await api('brand');if(turn!==studio.turn)return;if(JSON.stringify(brand)!==JSON.stringify(studio.brand)){studio.brand=brand;if(studio.screen==='home')sHome();else sStatusPage();}}if(['run','gate'].includes(studio.screen)&&studio.id){const found=await api('run?id='+encodeURIComponent(studio.id));if(turn!==studio.turn)return;if(studio.screen==='gate'){if(found.expected!==studio.found.expected){const alert=$('newer-version');if(alert&&alert.dataset.version!==found.expected){alert.dataset.version=found.expected;alert.hidden=false;alert.replaceChildren(sNode('p','','This blog changed while you were reading. Look at the new version before deciding.'),sButton('Read the new version',()=>studioNavigate('gate',found.id,studio.stage)));for(const node of $('actions').querySelectorAll('button'))if(['Use this outline','Use this draft','Finish this review','Finish','Develop an idea','Write from this outline','Save ideas for later'].includes(node.textContent))node.disabled=true;}}}else if(JSON.stringify(found)!==studio.signature){if(studio.stage!=='status'&&sWritingReady(found))await sRoute('gate',found.id,found.next,true);else sRun(found);}else{const line=$('studio-page').querySelector('.now-line'),fresh=sNowLine(found);if(line&&fresh)line.textContent=fresh.textContent;}}else{const list=await api('runs');if(turn!==studio.turn)return;if(JSON.stringify([studio.listing,studio.deleted||[]])!==JSON.stringify([list.items,list.deleted||[]])){studio.listing=list.items;studio.deleted=list.deleted||[];if(studio.screen==='home')sHome();else if(studio.screen==='blogs')sBlogs();else sStatusPage();}}}catch(error){notice(error.message,true);}finally{studio.polling=false;}
}

function sBrandNotice(){const found=studio.brand;if(!found)return null;const wanted=found.checked;
  if(found.job?.status)return sCard('Brand skill',sNode('p',found.job.status==='failed'?'problem':'quiet',found.job.message),sButton('See brand settings',()=>sRoute('settings')));
  if(wanted&&wanted.version!==found.version)return sCard('Brand skill',sNode('p','quiet',found.name?'A different brand skill release is available.':'Your brand skill is ready to install.'),sButton('See brand settings',()=>sRoute('settings')));
  return null;
}
function sBrandCard(){
  const found=studio.brand;if(!found)return null;
  const held={repository:found.repository||'',release:found.release||''},form=sNode('form','narrow'),problem=sNode('p','problem');problem.setAttribute('role','alert');
  const node=sCard('Brand skill',sNode('p','','Your organisation’s brand skill is released from a repository of its own. Its repository and release are shared by all studios. A skill you installed yourself can also be used.'),found.problem?sNode('p','problem',found.problem):null);
  if(found.skills?.length){const choice={runtime:found.runtime||''},selection=sNode('form','narrow'),selectionProblem=sNode('p','problem');selectionProblem.setAttribute('role','alert');selection.append(sField('brand-skill','Use this brand skill',choice,'runtime',{required:true,options:[['','Choose an installed skill'],...found.skills.map(row=>[row.runtime,row.name+(row.version?' · '+row.version:'')])]}),selectionProblem);const save=sNode('button','button button-quiet','Use this skill');save.type='submit';selection.append(save);selection.addEventListener('submit',async event=>{event.preventDefault();await busy(save,'Saving…',async()=>{try{studio.brand=await api('brand-configure',{...choice,skill_before:found.skill_before});studio.options=null;sToast('Brand skill selected. Existing blogs keep their brand contract.');sCloseSheet();await sRoute(studio.screen==='setup'?'setup':'settings');}catch(error){selectionProblem.textContent=error.message;}});});node.append(selection);}
  else node.append(sNode('p','quiet','No brand skill was found. You can write without a brand.'));
  form.append(sField('brand-repository','Its repository',held,'repository',{max:2000,hint:'An https or ssh address, as Git clones it. It uses your existing Git sign-in.'}),sField('brand-release','Which release',held,'release',{max:80,short:true,hint:'Empty for the newest, or a release tag such as v1.4.0.'}),problem);
  const save=sNode('button','button button-quiet','Check and save');save.type='submit';form.append(save);form.addEventListener('submit',async event=>{event.preventDefault();await busy(save,'Checking…',async()=>{try{studio.brand=await api('brand-configure',{repository:held.repository.trim(),release:held.release.trim(),shared_before:found.shared_before});sToast(held.repository.trim()?'Saved. The selected release is ready to install.':'Repository forgotten. Installed skills are kept.');await sRoute(studio.screen==='setup'?'setup':'settings');}catch(error){sSharedFailure(error,problem,async()=>{studio.brand=await api('brand');node.replaceChildren(...sBrandCard().children);});}});});node.append(form);
  const chosen=found.checked;if(chosen){node.append(sNode('p','quiet','Installed: '+(found.version||'not found')+'. Selected release: '+chosen.tag+'.'),sNode('p','path',chosen.commit));if(chosen.version!==found.version&&found.job?.status!=='working')node.append(sButton(found.name?'Install selected release':'Install the brand skill',()=>sBrandInstall(found),'filled'));}
  if(found.job?.status)node.append(sNode('p',found.job.status==='failed'?'problem':'quiet',found.job.message));
  return node;
}
function sBrandInstall(found){const chosen=found.checked,problem=sNode('p','sheet-error');problem.setAttribute('role','alert');sOpenSheet('Install the brand skill?',sNode('p','','This downloads the selected release and runs its own installer. Install only from a repository you trust.'),sNode('p','path',found.repository),sNode('p','','Release '+chosen.tag),sNode('p','path',chosen.commit),problem,sAdd(sNode('div','bar'),sButton('Install it now',async button=>{await busy(button,'Starting…',async()=>{try{studio.brand=await api('brand-install',{confirmed:true,repository:found.repository,tag:chosen.tag,commit:chosen.commit});sCloseSheet();await sRoute('status');}catch(error){problem.textContent=error.message;}});},'filled'),sButton('Cancel',sCloseSheet)));}
function sCanEdit(found){return access.actions.edit&&(!found.team||found.driver?.here);}
function sTeamDecision(found,action){const problem=sNode('p','sheet-error');problem.setAttribute('role','alert');const title={take:'Take this blog?',takeover:'Take over this blog?',handover:'Hand this blog over?',publish:'Record in the team repository?'}[action];sOpenSheet(title,sNode('p','',action==='takeover'?'This computer becomes its driver. The other computer keeps any unshared work when it reconnects.':action==='handover'?'Stop work here and make the blog available to another computer.':action==='publish'?'Record this approved blog in the team repository. Nothing is sent to a CMS or made public.':'Share this computer’s claim before running any work.'),problem,sAdd(sNode('div','bar'),sButton('Confirm',async button=>{await busy(button,'Sharing…',async()=>{try{await api('team-'+action,{id:found.id,expected:found.expected,confirmed:true});sCloseSheet();await sRoute('run',found.id);}catch(error){problem.textContent=error.message;}});},'filled'),sButton('Cancel',sCloseSheet)));}
function sTeamCard(){const team=studio.team||{},held={repository:team.repository||'',branch:team.branch||'main',share:team.share||'decision'},form=sNode('form','narrow'),problem=sNode('p','problem');problem.setAttribute('role','alert');form.append(sField('team-repository','Team repository',held,'repository',{required:true,max:2000}),sField('team-branch','Branch',held,'branch',{required:true,max:200}),sField('team-sharing','Share decisions',held,'share',{options:[['decision','After every decision'],['asked','Only when I choose Share now']]}),problem);const submit=sNode('button','button button-filled',team.joined?'Join another team repository':'Join team repository');submit.type='submit';form.append(submit);form.addEventListener('submit',async event=>{event.preventDefault();await busy(submit,'Joining…',async()=>{try{const result=await api('team-join',{...held,shared_before:team.shared_before});await loadCapabilities();studio.settings=await api('run-settings');studio.team=result;sToast(result.shared_problem||'Team repository joined.');await sRoute('home');}catch(error){sSharedFailure(error,problem,async()=>{studio.team=await api('team');card.replaceChildren(...sTeamCard().children);});}});});const card=sCard('Team repository',sNode('p','quiet','Training, Blog and Presentation Studio can share one repository. Blog Studio keeps its own clone and writes under blogs/.'),team.workspace?sNode('p','path',team.workspace):null,!team.joined?sNode('p','quiet','Writing is saved locally. Join a repository when you want to share it.'):null,team.report?.notice?sNode('p','problem',team.report.notice):null,team.shared_problem?sNode('p','problem',team.shared_problem):null,team.migration_notice&&studio.screen==='status'?sNode('p','quiet',team.migration_notice):null,team.configuration_notice?sNode('p','problem',team.configuration_notice):null,access.actions.refresh?sAdd(sNode('div','bar'),sButton('Refresh Hub',async button=>{await busy(button,'Refreshing…',async()=>{await api('refresh',{});await loadCapabilities();sToast('Team Hub refreshed. Google Docs content is refreshed separately in chat.');});})):null,team.joined?sAdd(sNode('div','bar'),sButton('Share now',async button=>{await busy(button,'Sharing…',async()=>{const report=await api('team-sync',{});sToast(report.notice||'Work is shared.');studio.team=await api('team');await sRoute('status');});}),sButton('Use '+(team.share==='asked'?'automatic':'manual')+' sharing',async()=>{try{await api('team-share-mode',{share:team.share==='asked'?'decision':'asked',shared_before:team.shared_before});await sRoute('status');}catch(error){sSharedFailure(error,problem,async()=>{studio.team=await api('team');card.replaceChildren(...sTeamCard().children);});card.prepend(problem);}})):null,disclosure(team.joined?'Join another repository':'Join our team repository',sNode('p','quiet','Joining uses a separate workspace. Your current writing stays here; copying existing blogs remains an explicit step.'),...(team.remembered_repositories||[]).map(url=>sButton('Use remembered repository: '+url,()=>{held.repository=url;const input=$('team-repository');if(input)input.value=url;})),form));return card;}

// Setting up before writing: voices, styles and the team library, without starting a blog.
function sSetupTasks(){
  const list=sNode('div','pick-cards');
  const tasks=[sVoicesOn()?['Voices and styles','Learn how you or a colleague writes, from samples, links to posts or a LinkedIn export; set up the kinds of post you write.',()=>sRoute('voices')]:['Kinds of post','Set up the kinds of post you write, from examples or by hand.',()=>sRoute('voices')],['Team library','Add finished posts, files, links and Google Docs your team writes from, by role and author.',()=>sLegacy('library')]];
  for(const [title,description,action] of tasks)list.append(sPickCard(title,description,action));return sCard('Set up before you write',list);
}
function sStartTasks(){
  const list=sNode('div','pick-cards');
  // Every new blog starts on the writing desk's start.
  const tasks=[['Write from a topic or my documents','Add files, links or Google Docs as sources, then give the point or get three angles. The outline and draft are written for you.',()=>sDeskBegin({have:'topic'})],['Work from my outline or notes','Write the draft from your outline, or shape an outline together first.',()=>sDeskBegin({have:'outline'})],['Edit or polish a draft','Paste, upload or bring a Google Doc. Proofread and tighten it, or get feedback. No kind of post needed.',()=>sDeskBegin({have:'draft'})]];
  for(const [title,description,action] of tasks){const button=sPickCard(title,description,action);button.disabled=!access.actions.edit;list.append(button);}return sCard('What would you like to do?',list);
}
function sPolishIntake(initial='google'){
  const held=studio.intake||(studio.intake={source:initial,url:'',title:'',content:'',file:null,operation:operationId()}),form=sNode('form','narrow polish-intake'),problem=sNode('p','problem');problem.setAttribute('role','alert');
  sFrame('Polish a document',[],'Choose your document',()=>sRoute('home'));
  form.append(sChoice('Where is your document?',[['google','Google Doc'],['paste','Paste text'],['file','Upload a file']],held,'source',()=>sPolishIntake()));
  let file;
  if(held.source==='google')form.append(sField('polish-url','Google Doc link or document ID',held,'url',{required:true,max:2000,hint:'You’ll check the preview before opening the document for editing.'}));
  else{
    if(held.source==='paste')form.append(sField('draft-content','Paste your document',held,'content',{long:true,max:200000,required:true}));
    else{
      file=sNode('input','input');file.type='file';file.accept='.txt,.md,.docx,.pdf,.html,.htm';file.setAttribute('aria-label','Upload a document');
      const note=sNode('p','quiet',held.file?'Selected: '+held.file.name:'Text, Markdown, Word or PDF. Up to 10 MiB.');
      file.addEventListener('change',()=>{held.file=file.files?.[0]||null;note.textContent=held.file?'Selected: '+held.file.name:'Choose a document.';if(held.file&&!held.title.trim()){held.title=held.file.name.replace(/\.[^.]+$/,'');const field=$('draft-title');if(field)field.value=held.title;}});
      form.append(file,note);
    }
    form.append(disclosure('Name this draft (optional)',sField('draft-title','Working title',held,'title',{max:500,hint:'Leave blank to use the first line or file name.'})));
  }
  const go=sNode('button','button button-filled',held.source==='google'?'Read Google Doc':'Open for polishing');go.type='submit';go.disabled=!access.actions.edit;form.append(problem,go);
  form.addEventListener('submit',async event=>{
    event.preventDefault();if(!access.actions.edit)return;const turn=studio.turn,source=held.source;
    if(held.source==='paste'&&!held.content.trim()){problem.textContent='Paste your document first.';return;}
    if(held.source==='file'&&!held.file){problem.textContent='Choose a document to upload.';return;}
    await busy(go,'Opening…',async()=>{try{
      if(held.source==='google'){
        const preview=await api('google-preview',{url:held.url.trim()});if(turn!==studio.turn||held.source!==source)return;
        await sGoogleResult({url:held.url,preview:null,confirmed:false,fromPolish:true},preview);return;
      }
      const chosen=held.source==='file'?held.file:null;if(chosen&&chosen.size>10*1024*1024)throw new Error('Choose a file up to 10 MiB.');
      const content=chosen?await encodeImportFile(chosen):btoa(Array.from(new TextEncoder().encode(held.content),v=>String.fromCharCode(v)).join(''));
      const title=held.title.trim()||(chosen?chosen.name.replace(/\.[^.]+$/,''):held.content.split(/\r?\n/).find(line=>line.trim())?.replace(/^\s*#{1,6}\s+|\*\*/g,'').trim().slice(0,100))||'Untitled document';
      const result=await api('upload',{operation:held.operation,filename:chosen?chosen.name:'draft.md',title,content,purpose:'manuscript',as_blog:true,analyze:false});
      if(turn!==studio.turn||held.source!==source)return;studio.intake=null;await sRoute('editor',result.article.id,'prepare');
    }catch(error){if(turn===studio.turn)problem.textContent=error.message+' Your document choices are kept here.';}});
  });
  sPage(sNode('p','lede','Proofread, copy edit and humanize your writing. No research.'),form);
}

// Editing follows the same path as the skill: polish, choose changes, finish.
function sWorkflowSteps(labels,at,choose){
  const nav=sNode('nav','workflow-steps');nav.setAttribute('aria-label','Workflow progress');
  labels.forEach((label,index)=>{const button=choose?sButton((index+1)+'. '+label,()=>choose(index)):sNode('span','workflow-step',(index+1)+'. '+label);button.setAttribute('aria-current',index===at?'step':'false');nav.append(button);});return nav;
}
function sEditingRun(found){return !!found.editor_check;}
function sRememberDelivery(value){
  studio.editorDelivery=value;
  const saved={...value};if(value.plan)saved.plan={plan:value.plan.plan,expected:value.plan.expected,mode:value.plan.mode,count:value.plan.count};
  try{sessionStorage.setItem('blog-studio-delivery:'+value.id,JSON.stringify(saved));}catch(_){}
}
function sSavedDelivery(ident,expected){
  if(studio.editorDelivery?.id===ident&&studio.editorDelivery.expected===expected)return studio.editorDelivery;
  try{const saved=JSON.parse(sessionStorage.getItem('blog-studio-delivery:'+ident)||'null');if(saved?.id===ident&&saved.expected===expected&&['local','verified-pending','verified-comments','needs-check','uncertain'].includes(saved.status))return saved;}catch(_){}
  return null;
}
function sClearDelivery(ident){studio.editorDelivery=null;try{sessionStorage.removeItem('blog-studio-delivery:'+ident);}catch(_){}}
function sFreezeControls(scope){
  const controls=['input','textarea','select','button'].flatMap(tag=>[...scope.querySelectorAll(tag)]).map(node=>[node,node.disabled]);
  for(const [node]of controls)node.disabled=true;
  return ()=>{for(const [node,disabled]of controls)node.disabled=disabled;};
}

async function sEditor(ident){
  const turn=studio.turn,read=studio.editorRead=(studio.editorRead||0)+1,current=()=>studio.screen==='editor'&&studio.id===ident&&studio.turn===turn&&studio.editorRead===read;
  const found=await api('manuscript?id='+encodeURIComponent(ident));
  if(!current())return;
  studio.editorDrafts||={};studio.editorChoices||={};
  const held=studio.editorDrafts[ident]||{id:ident,content:found.content,baseContent:found.content,expected:found.expected};
  if(held.baseContent===found.content)held.expected=found.expected;
  studio.editorDraft=held;studio.editorDrafts[ident]=held;
  const operation=found.operation,active=found.working||operation?.status==='queued',ready=operation?.editor_check&&operation.next==='review'&&operation.status==='waiting-for-approval';
  studio.editorWatching=!!active;studio.editorSignature=JSON.stringify(operation);
  let phase=studio.stage;if(!['prepare','changes','finish'].includes(phase))phase=operation?.status==='failed'?'prepare':ready||found.findings.length?'changes':'prepare';
  if(active)phase='prepare';
  const problem=sNode('p','problem');problem.setAttribute('role','alert');
  const route=step=>sRoute('editor',ident,['prepare','changes','finish'][step]);
  // A finished blog, or a saved one with no run, can go on the writing desk from here too.
  const toDesk=!access.actions.edit?null:operation?.desk_open?sButton('Open on the desk',async button=>busy(button,'Opening…',async()=>{try{const made=await api('desk-open',{id:ident});studio.desk={id:made.id,view:made,session:operationId()};await sRoute('desk',made.id);}catch(error){problem.textContent=error.message;}})):!operation&&found.content.trim()?sButton('Open on the desk',()=>sDeskBegin({have:'draft',source:'saved',article:ident,title:found.title||''})):null;
  sFrame(found.title,[...(found.google?[link(found.google.url,'Open Google Doc ↗')]:[]),toDesk,sButton('Tools',()=>sMoreTools(ident))],found.google?'Google Doc review':'Improve a draft',()=>sRoute('blogs'));
  const progress=sWorkflowSteps(['Polish','Choose changes','Finish'],['prepare','changes','finish'].indexOf(phase),route);
  const steps=progress.querySelectorAll('button');steps[1].disabled=active;steps[2].disabled=active||!found.proposals.length&&!sSavedDelivery(ident,found.expected)&&!(found.google&&found.content!==found.baseline)&&!(operation?.editor_check==='revise'&&ready);
  const options=studio.editorChoices[ident]||(studio.editorChoices[ident]={check:['polish','factual-support','shape','geo','revise'].includes(operation?.editor_check)?operation.editor_check:'polish',request:'',research:'none',sources:[...(found.sources||[])]});
  const input=sNode('textarea','input manuscript-input');input.value=held.content;input.setAttribute('aria-label','Manuscript Markdown');input.rows=18;input.addEventListener('input',()=>{held.content=input.value;});
  const save=sButton('Save local edits',async button=>busy(button,'Saving…',async()=>{const content=held.content;try{const saved=await api('editor-save',{id:ident,expected:held.expected,content});if(held.content===content)delete studio.editorDrafts[ident];else{held.baseContent=saved.content;held.expected=saved.expected;}if(!current())return;sToast(saved.preservation.needs_review?'Saved. Review changed numbers, links or quotations.':'Local edits saved.');await sEditor(ident);}catch(error){if(current())problem.textContent=error.message+' Your text stays here.';}}),'filled');save.disabled=active||!access.actions.edit;
  const manuscript=disclosure('Read the document',...(found.google?[link(found.google.url,'Open Google Doc ↗')]:[]),sAdd(sNode('article','paper doc'),window.TrainingStudioMarkdown.render(found.content)),disclosure('Edit the text yourself',input,sAdd(sNode('div','bar'),save,sButton('Preview local edits',()=>sOpenSheet('Manuscript preview',sAdd(sNode('article','paper doc'),window.TrainingStudioMarkdown.render(held.content)),sButton('Close',sCloseSheet))))));
  if(phase==='prepare'){
    const form=sNode('form','narrow'),advanced=sNode('div');
    const syncOptions=()=>{advanced.hidden=options.check==='polish';if(advanced.hidden){options.research='none';const field=$('editor-research');if(field)field.value='none';}};
    advanced.append(sField('editor-research','Optional research',options,'research',{options:[['none','No new research (use saved evidence)'],...EDITOR_RESEARCH]}));
    const sources=sNode('div');advanced.append(disclosure('Choose evidence sources',sources));
    if(options.check!=='polish'){studio.options=await api('run-options');if(!current())return;sources.append(sSources(options));}
    form.append(sField('editor-request','Anything to focus on? (optional)',options,'request',{long:true,max:8000,hint:'For example: tighten long sentences; keep the technical detail.'}),disclosure('Other editing actions',sField('editor-check','Editing action',options,'check',{options:[['polish','Polish writing'],['factual-support','Check facts'],['shape','Review argument and structure'],['geo','Improve clarity and citation readiness'],['revise','Revise the draft']],changed:async()=>{syncOptions();if(options.check!=='polish'){studio.options=await api('run-options');if(current())sources.replaceChildren(sSources(options));}}})),advanced);
    syncOptions();
    const failed=operation?.status==='failed',label={polish:'Polish writing','factual-support':'Check facts',shape:'Review structure',geo:'Review citation readiness',revise:'Revise draft'},command=()=>failed&&options.check===operation.editor_check?'Try again':label[options.check]||'Start';
    const descriptions={polish:'Grammar, clarity and natural wording, using your writing rules. No research; your voice and meaning are preserved.','factual-support':'Check claims against the evidence you choose. Unverified claims stay marked as unverified.',geo:'Review clarity and citation readiness using saved evidence. Missing evidence stays marked.',shape:'Review the argument, order and relevance to your readers. Your manuscript stays unchanged.',revise:'Revise the saved draft within your instructions. Keep the author’s voice and meaningful technical detail.'};
    const explanation=sNode('p','',failed?'No new suggestions were saved. Your manuscript and any earlier feedback are kept. Try this pass again or read the document below.':descriptions[options.check]);
    const go=sNode('button','button button-filled',command());go.type='submit';go.disabled=active||!access.actions.edit;form.append(go);
    // Keep the command label aligned when the optional action changes.
    form.addEventListener('change',()=>{go.textContent=command();if(!failed){explanation.textContent=descriptions[options.check];prepareCard.firstElementChild.textContent=options.check==='polish'?'Ready to polish':label[options.check];}});
    form.addEventListener('submit',async event=>{event.preventDefault();if(held.content!==found.content){problem.textContent='Save your local edits first.';return;}await busy(go,'Starting…',async()=>{try{await api('editor-check',{id:ident,expected:found.expected,...options});if(current())await sRoute('editor',ident,null,true);}catch(error){if(current())problem.textContent=error.message;}});});
    const activity=active?sCard(operation?.editor_check==='polish'?'Polishing your document':'Working on your requested review',sNode('p','',operation?.editor_check==='polish'?'Checking grammar, clarity and natural wording. Your suggestions will appear here automatically.':'Reviewing the document in your selected scope. Results will appear here automatically.'),sNode('p','quiet','You can leave this page and come back.'),sButton('Stop this pass',async()=>{try{await api('run-stop',{id:ident,expected:operation.expected});await sEditor(ident);}catch(error){problem.textContent=error.message;}})):null;
    if(activity){activity.setAttribute('role','status');activity.setAttribute('aria-live','polite');}
    const prepareCard=sCard(failed?'This review couldn’t finish':options.check==='polish'?'Ready to polish':label[options.check],explanation,failed?disclosure('What went wrong',sNode('p','problem',operation.error)):null,form);
    sPage(progress,problem,activity,!active?prepareCard:null,found.findings.length||found.proposals.length?sButton('Continue to saved suggestions',()=>route(1)):null,manuscript);
    return;
  }
  studio.editorReviewDrafts||={};
  let review=studio.editorReviewDrafts[ident];
  if(!review||review.expected!==found.expected){const items=[...new Map([...(found.findings||[]),...found.proposals].map(item=>[item.id,{...item}])).values()];review=studio.editorReviewDrafts[ident]={expected:found.expected,items,selected:new Set((found.proposals.length?found.proposals:items.filter(item=>!items.some(other=>other.id!==item.id&&sSamePassage(item,other)))).map(item=>item.id)),manual:{kind:'edit',before:'',after:'',reason:'',context:''}};}
  const candidates=review.items,selected=review.selected;
  if(phase==='changes'){
    const manual=review.manual,form=sNode('form','narrow');
    form.append(sField('proposal-kind','Feedback type',manual,'kind',{options:[['edit','Suggested replacement'],['comment','Question or comment']]}),sField('proposal-before','Exact original wording',manual,'before',{long:true,required:true,max:10000}),sField('proposal-after','Suggested wording',manual,'after',{long:true,max:10000}),sField('proposal-reason','Reason',manual,'reason',{long:true,required:true,max:1000}),disclosure('Disambiguate a repeated quote',sField('proposal-context','Surrounding original text',manual,'context',{long:true,max:20000})));
    const add=sNode('button','button','Keep suggestion locally');add.type='submit';add.disabled=active||!access.actions.edit;form.append(add);form.addEventListener('submit',async event=>{event.preventDefault();await busy(add,'Saving…',async()=>{const unlock=sFreezeControls($('studio-page'));try{await api('editor-proposals',{id:ident,expected:found.expected,proposals:[...candidates.filter(item=>selected.has(item.id)).map(({evidence,verdict,...item})=>item),{...manual,id:operationId()}]});if(current())await sEditor(ident);}catch(error){if(current())problem.textContent=error.message;}finally{unlock();}});});
    if(!candidates.length&&!(operation?.editor_check==='revise'&&ready)){
      const failed=operation?.status==='failed';
      sPage(progress,problem,sCard(failed?'This review couldn’t finish':ready?'No changes suggested':'No suggestions yet',sNode('p','',failed?'No new suggestions were saved. Try the review again or add your own feedback below.':ready?'This pass did not suggest any wording edits. Your document is kept as it is.':'Run a polishing pass, or add your own feedback below.'),ready?(found.google?link(found.google.url,'Open Google Doc ↗'):sButton('Download document',()=>sDownload({content:found.content,name:'blog-draft.md'}),'filled')):null,sAdd(sNode('div','bar'),sButton(failed?'Try again':ready?'Try another pass':'Polish writing',()=>route(0)),sButton('Back to your blogs',()=>sRoute('blogs')))),disclosure('Add your own suggestion',form),found.review?disclosure('What was checked',sAdd(sNode('article','doc'),window.TrainingStudioMarkdown.render(found.review))):null,manuscript);return;
    }
    const list=sNode('div','writing-changes'),next=sButton('Continue with selected changes',async button=>{if(!selected.size)return;if(held.content!==found.content){problem.textContent='Save your local edits first, then review the current suggestions.';return;}await busy(button,'Saving selection…',async()=>{const unlock=sFreezeControls($('studio-page'));try{await api('editor-proposals',{id:ident,expected:found.expected,proposals:candidates.filter(item=>selected.has(item.id)).map(({evidence,verdict,...item})=>item)});if(current())await route(2);}catch(error){if(current())problem.textContent=error.message;}finally{unlock();}});},'filled');
    next.className+=' review-continue';$('studio-toolbar').dataset.workflow='review';$('actions').replaceChildren(next);
    const count=sNode('p','quiet');const boxes=[];
    const update=()=>{count.textContent=selected.size+' of '+candidates.length+' selected';next.disabled=!selected.size||active||!access.actions.edit;next.textContent=!selected.size?'Choose a change':candidates.length===1?'Use this change':selected.size===candidates.length?'Use all '+selected.size+' changes':'Use '+selected.size+' selected '+(selected.size===1?'change':'changes');for(const [box]of boxes)box.parentElement.parentElement.dataset.selected=String(box.checked);};
    candidates.forEach((item,index)=>{
      const box=sNode('input');box.type='checkbox';box.checked=selected.has(item.id);boxes.push([box,item.id]);box.addEventListener('change',()=>{if(box.checked){selected.add(item.id);for(const other of candidates)if(other.id!==item.id&&sSamePassage(item,other))selected.delete(other.id);for(const [input,id]of boxes)input.checked=selected.has(id);}else selected.delete(item.id);update();});
      const label=sAdd(sNode('label','change-select'),box,sNode('span','','Change '+(index+1)+(item.kind==='comment'?' · Question for the author':'')));
      const replacement=sNode('p','change-after',item.after||'(Remove this text)');
      const row=sAdd(sNode('section','writing-change'),label,sNode('p','change-caption','Original'),sNode('blockquote','change-before',item.before),item.kind==='edit'?sAdd(sNode('div'),sNode('p','change-caption','Suggested wording'),replacement):null,sNode('p','change-reason',item.reason),candidates.some(other=>other.id!==item.id&&sSamePassage(item,other))?sNode('p','quiet','Alternative for the same passage — choose one.'):null,item.kind==='edit'?disclosure('Adjust the suggested wording',sField('wording-'+index,'Your preferred wording',item,'after',{long:true,max:10000,changed:()=>{replacement.textContent=item.after||'(Remove this text)';}})):null,item.evidence?disclosure('Why this was flagged',sNode('p','quiet',item.evidence)):null);list.append(row);
    });
    const revised=operation?.editor_check==='revise'&&ready;
    if(revised){
      const use=sButton(found.google?'Prepare Google suggestions from this revision':'Use revised draft',async()=>{try{if(found.google){await api('editor-changes',{id:ident,expected:found.expected});await sEditor(ident);}else{sRememberDelivery({id:ident,expected:found.expected,status:'local',message:'Your revised draft is saved. Earlier versions are retained.'});await route(2);}}catch(error){problem.textContent=error.message;}},'filled');
      list.prepend(sCard('Your revised draft',sNode('p','quiet','The requested revision is saved locally. Review its wording before sending anything to Google.'),sAdd(sNode('article','paper doc'),window.TrainingStudioMarkdown.render(found.content)),use));
    }
    const chooseAll=value=>{for(const [box,id] of boxes){box.checked=value;if(value)selected.add(id);else selected.delete(id);}update();};update();
    sPage(progress,operation?.status==='failed'?sNode('p','decision-notice','The latest pass failed. These are earlier saved suggestions; no new results were added.'):null,sNode('p','lede','Uncheck anything you want to skip. Your document stays unchanged until you finish.'),problem,candidates.length?sAdd(sNode('div','bar review-selection'),count,candidates.length>1?sButton('Select all',()=>chooseAll(true)):null,candidates.length>1?sButton('Clear selection',()=>chooseAll(false)):null):revised?null:sCard(ready?'No wording changes found':'No current suggestions',sNode('p','','Read the manuscript or run a new editing pass. Questions about claims remain optional feedback.'),sButton('Back to Polish writing',()=>route(0))),list,disclosure('Add your own suggestion',form),found.review?disclosure('Full review notes',sAdd(sNode('article','doc'),window.TrainingStudioMarkdown.render(found.review))):null,manuscript);
    return;
  }
  const delivery=sSavedDelivery(ident,found.expected);
  const verified=delivery&&['verified-pending','verified-comments'].includes(delivery.status);
  const download=()=>sDownload({content:found.content,name:'blog-draft.md'});
  const comments=found.proposals.filter(item=>item.kind==='comment'),edits=found.proposals.filter(item=>item.kind==='edit');
  const feedback=()=>sDownload({name:'blog-feedback.md',content:'# '+found.title+' — selected feedback\n\n'+found.proposals.map((item,index)=>'## '+(index+1)+'. '+(item.kind==='comment'?'Comment':'Suggested edit')+'\n\n'+item.before.replace(/^/gm,'> ')+'\n\n'+(item.kind==='edit'?'Suggested wording: '+(item.after||'(Remove this text)')+'\n\n':'')+item.reason).join('\n\n')});
  if(verified){
    sPage(progress,sCard('Feedback sent',sStatus('done',delivery.message),link(found.google.url,'Open Google Doc ↗'),sNode('p','quiet','The author can review your feedback in Google Docs.'),sAdd(sNode('div','bar'),sButton('Polish another document',()=>{studio.intake=null;studio.google=null;return sDeskBegin({have:'draft'});},'filled'),sButton('Back to your blogs',()=>sRoute('blogs')))));
    return;
  }
  if(delivery?.status==='local'&&!found.google){
    sPage(progress,sCard('Your polished draft is saved',sStatus('done',delivery.message),sButton('Download polished document',download,'filled'),sCopyButton(found.content),comments.length?sButton('Download feedback',feedback):null,sAdd(sNode('div','bar'),sButton('Polish another document',()=>{studio.intake=null;studio.google=null;return sDeskBegin({have:'draft'});}),sButton('Back to your blogs',()=>sRoute('blogs')))),manuscript);
    return;
  }
  const summary=sNode('div','finish-selection');
  for(const item of found.proposals)summary.append(sAdd(sNode('div','finish-change'),sNode('p','change-caption',item.kind==='edit'?'Wording change':'Comment'),sNode('blockquote','change-before',item.before),item.kind==='edit'?sNode('p','change-after',item.after||'(Remove this text)'):sNode('p','',item.reason)));
  const apply=sButton('Save '+found.proposals.filter(p=>p.kind==='edit').length+(found.proposals.filter(p=>p.kind==='edit').length===1?' edit':' edits')+' to my draft',async button=>{if(held.content!==found.content){problem.textContent='Save your local edits first, then review the current suggestions.';return;}try{await busy(button,'Saving…',async()=>{const unlock=sFreezeControls($('studio-page'));try{const result=await api('editor-apply-selected',{id:ident,expected:found.expected,proposals:found.proposals.filter(p=>p.kind==='edit').map(p=>p.id)});if(held.content===held.baseContent)delete studio.editorDrafts[ident];sRememberDelivery({id:ident,expected:result.expected,status:'local',message:result.applied+(result.applied===1?' change saved.':' changes saved.')+' Your original and earlier versions are kept.'});if(current())await sEditor(ident);}finally{unlock();}});}catch(error){if(current())problem.textContent=error.message;}},found.google?'quiet':'filled');
  apply.disabled=!found.proposals.some(item=>item.kind==='edit')||active||!access.actions.edit;
  if(!found.google){
    sPage(progress,sNode('p','lede',edits.length?'Save the changes you chose, then download your polished document.':'Your selected comments are ready to give to the author. They don’t change the manuscript.'),problem,sCard(found.proposals.length+(found.proposals.length===1?' change ready':' changes ready'),sNode('p','quiet',edits.length+' wording '+(edits.length===1?'edit':'edits')+(comments.length?' · '+comments.length+(comments.length===1?' comment':' comments'):'')),edits.length?apply:null,comments.length?sButton('Download feedback',feedback,edits.length?'quiet':'filled'):null,!edits.length?sButton('Download document',download):null,sButton('Change my selection',()=>route(1))),disclosure('Review selected feedback',summary),manuscript);
    return;
  }
  if(!found.proposals.length){
    const changed=found.content!==found.baseline;
    sPage(progress,problem,sCard(changed?'Prepare your edits for Google':'Choose feedback first',sNode('p','',changed?'Your edits are saved locally. Turn the wording changes into suggestions for the author to review.':'Choose suggested changes or add your own quoted feedback before sending anything.'),changed?sButton('Prepare suggestions from local edits',async()=>{try{await api('editor-changes',{id:ident,expected:found.expected});await route(1);}catch(error){problem.textContent=error.message;}},'filled'):null,sButton(changed?'Add quoted feedback instead':'Choose changes',()=>route(1))),manuscript);return;
  }
  const choice=studio.editorModes||(studio.editorModes={});choice[ident]||={mode:'auto'};
  const checking=delivery&&delivery.status!=='local';
  let plan=checking?delivery.plan:null,planError='';
  if(found.proposals.length&&!plan){const checking=sCard('Checking Google Doc',sNode('p','','Checking your selected feedback against the current document. Nothing is sent during this check.'));checking.setAttribute('role','status');sPage(progress,checking);try{plan=await api('editor-google-plan',{id:ident,expected:found.expected,mode:choice[ident].mode});}catch(error){planError=error.message;}}
  if(!current()||studio.stage!=='finish')return;
  const error=sNode('p','problem',checking?delivery.message:planError);error.setAttribute('role','alert');
  const modeLabel=plan?.mode==='comments'?'comments':plan?.mode==='native'?'suggestions':'suggestions, with comments fallback';
  const send=sButton(checking?'Check delivery':'Send feedback to Google',async button=>{
    if(held.content!==found.content){error.textContent='Save your local edits before sending feedback.';return;}
    await busy(button,checking?'Checking…':'Sending…',async()=>{try{
      const result=await api('editor-google-send',{id:ident,expected:plan.expected,plan:plan.plan,confirmed:true});
      const message=result.status==='verified-pending'?'Suggestions are ready for the author to accept or reject.':result.status==='verified-comments'?'Comments were added to the original document.':'The result is not yet verified. Check delivery before trying anything else.';
      sRememberDelivery({id:ident,expected:found.expected,status:['verified-pending','verified-comments'].includes(result.status)?result.status:'needs-check',message,plan});
    }catch(failure){sRememberDelivery({id:ident,expected:found.expected,status:'needs-check',message:failure.message,plan});}});
    if(current())await sEditor(ident);
  },'filled');send.disabled=!plan||active||!access.actions.edit;
  const refresh=sButton('Check Google again',async()=>{sClearDelivery(ident);await sEditor(ident);});
  sPage(progress,sNode('p','lede','Ready to send your selected feedback. The original document stays under the author’s control.'),problem,sCard('Send to the original Google Doc',link(found.google.url,found.title+' ↗'),sNode('p','quiet',plan?plan.count+' selected '+(plan.count===1?'change':'changes')+' checked against the current Google Doc. Sending as '+modeLabel+'.':'Google needs attention before feedback can be sent.'),error,plan?send:refresh,disclosure('Delivery options',sField('google-delivery-mode','Send as',choice[ident],'mode',{options:[['auto','Suggestions, with comments fallback'],['comments','Comments only'],['native','Suggestions only']],changed:async()=>{sClearDelivery(ident);await sEditor(ident);}})),sButton('Change my selection',()=>route(1))),disclosure('Review '+found.proposals.length+' selected '+(found.proposals.length===1?'change':'changes'),summary),delivery?.status==='local'?sCard('Local copy saved',sNode('p','',delivery.message),sButton('Download polished document',download)):disclosure('Keep a revised copy locally',apply,sButton('Download current document',download)),disclosure('I edited the manuscript myself',sNode('p','quiet','Convert saved local wording edits into suggestions for this Doc.'),sButton('Prepare suggestions from local edits',async()=>{try{await api('editor-changes',{id:ident,expected:found.expected});await route(1);}catch(error){problem.textContent=error.message;}})),manuscript);
}

// Contextual tasks reuse saved article records and the existing manuscript editor.
async function sMoreTools(id=null){
  const problem=sNode('p','problem');problem.setAttribute('role','alert');
  sOpenSheet('Tools',sNode('p','','Loading available tasks…'),problem,sButton('Close',sCloseSheet));const sheet=studio.sheet;
  try{
    const found=await api('tools'+(id?'?id='+encodeURIComponent(id):''));if(studio.sheet!==sheet)return;
    const task=(title,detail,action,ready=true)=>{const button=sPickCard(title,detail,action);button.disabled=!ready;return button;};
    sOpenSheet('Tools',sNode('p','','Opening a tool starts no assistant work and changes no Google document.'),
      task('Check topic overlap','Find local reference leads before drafting; advice only.',sPlanning),
      sVoicesOn()?task('Voices and styles','Learn, audition, confirm or retire voices and kinds of writing without changing defaults.',()=>sVoiceTools(id)):task('Kinds of post','Make, edit or retire the kinds of post you write, from examples or by hand.',()=>sVoiceTools(id)),
      task('Interview me','Record expertise one question at a time and prepare an outline.',()=>id?sInterview(id):sNewInterview()),
      task('Repurpose this blog','Prepare named channel copy with honest counts; no posting.',()=>sRepurposeTool(id),!!id&&found.has_manuscript&&!found.working),
      task('Compare Google and local text','Preview accepted Google changes and reconcile locally without sending.',()=>sGoogleCompare(id),!!id&&!!found.google&&!found.working),
      task('Saved channel copies','Reopen named variants and their provenance.',()=>sVariants(id),!!id),
      task('Saved manuscript revisions','Compare a saved revision, then explicitly restore it locally.',()=>sHistoryTool(found),!!id&&found.has_manuscript),
      task('Pre-publish check','Report headings, placeholders, links and evidence references without rewriting.',()=>sPrepublishTool(id),!!id&&found.has_manuscript),
      task('Improve clarity and citation readiness','Review located passages using the saved evidence and voice.',()=>sFocusedTool(id,'geo'),!!id&&found.has_manuscript&&!found.working),
      task('Improve a title or opening','Compare focused alternatives and choose edits in the existing editor.',()=>sFocusedTool(id,'shape'),!!id&&found.has_manuscript&&!found.working),
      task('Delete this blog','Stops what is running, takes it out of your lists and keeps it for 30 days.',()=>sDeleteSheet({id,title:found.title,status:found.working?'working':''}),!!id&&access.actions.edit),
      ...(found.jobs||[]).map(job=>sButton(`Resume ${job.kind.replaceAll('-',' ')} · ${job.status}`,async()=>{const saved=await sTaskRead('Saved tool task','tool-job?job='+job.id);if(saved)sToolJob(saved);})),
      !id?sNode('p','quiet','Open a saved manuscript to use article-specific tools.'):null,
      sButton('Close',sCloseSheet));
  }catch(error){if(studio.sheet===sheet)problem.textContent=error.message;}
}
async function sHistoryTool(found){
  const list=sNode('div'),problem=sNode('p','problem');problem.setAttribute('role','alert');
  for(const row of found.history)list.append(sButton('Compare '+(row.at?new Date(row.at).toLocaleString():row.revision)+' · '+(row.action||'Earlier saved manuscript'),()=>sHistoryPreview(found,row.revision)));
  if(!found.history.length)list.append(sNode('p','','No earlier manuscript revisions are saved yet. Local edits create recoverable checkpoints.'));
  if(found.next_offset!==null)list.append(sButton('Older revisions',async()=>sHistoryTool(await api('tools?id='+encodeURIComponent(found.id)+'&offset='+found.next_offset))));
  sOpenSheet('Saved manuscript revisions',sNode('p','','Restoring saves a new text checkpoint. Sources, voice and the original Google Doc stay unchanged.'),list,problem,sButton('Tools',()=>sMoreTools(found.id)),sButton('Close',sCloseSheet));
}
async function sHistoryPreview(found,revision){
  const result=await sTaskRead('Compare saved manuscript','tool-history?'+new URLSearchParams({id:found.id,revision}));if(!result)return;
  const changes=sNode('div');for(const change of result.changes.changes)changes.append(sCard(change.section,sNode('h3','','Current text'),sNode('pre','diff',change.before||'(empty)'),sNode('h3','','Restored text'),sNode('pre','diff',change.after||'(empty)')));
  const problem=sNode('p','problem');problem.setAttribute('role','alert');
  sOpenSheet('Compare saved manuscript',sNode('p','quiet',result.scope),changes,result.changes.truncated?sNode('p','quiet','This comparison is shortened; inspect the saved file before restoring a large revision.'):null,
    sButton('Restore this revision locally',async button=>busy(button,'Restoring…',async()=>{
      const draft=studio.editorDrafts?.[found.id];if(draft&&draft.content!==draft.baseContent){problem.textContent='Save or copy your unsaved manuscript edits before restoring another revision.';return;}
      try{await api('tool-action',{action:'restore',id:found.id,expected:found.expected,revision,restore_expected:result.expected,confirmed:true});delete studio.editorDrafts?.[found.id];sCloseSheet();await sRoute('editor',found.id);sToast('Revision restored locally. Google is unchanged.');}catch(error){problem.textContent=error.message;}
    })),problem,sButton('Back to revisions',()=>sHistoryTool(found)),sButton('Cancel',sCloseSheet));
}
async function sPrepublishTool(id){
  const found=await sTaskRead('Pre-publish check','prepublish?id='+encodeURIComponent(id));if(!found)return;const list=sNode('ul','look');
  for(const item of found.findings)list.append(sNode('li','','Line '+item.line+': '+item.detail));
  sOpenSheet('Pre-publish check',sNode('p','','Report only. Nothing was changed or published.'),found.findings.length?list:sNode('p','','No findings from these local checks.'),sNode('p','quiet',found.coverage),sButton('Tools',()=>sMoreTools(id)),sButton('Close',sCloseSheet));
}
function sFocusedTool(id,check){
  const held={focus:'',part:'title'},form=sNode('form'),problem=sNode('p','problem');problem.setAttribute('role','alert');
  if(check==='shape')form.append(sField('workshop-part','What should improve?',held,'part',{options:[['title','Title'],['opening','Opening passage'],['benefit','Benefit framing'],['cta','Optional call to action']]}));
  form.append(sField('tool-focus','Anything to focus on?',held,'focus',{long:true,max:4000}),sNode('p','quiet',check==='shape'?'This changes selected manuscript wording only, not the local article label or remote Google file name. Educational articles need no sales CTA.':'No new research starts. Missing evidence should become a comment, not an invented citation.'),problem);
  const submit=sNode('button','button','Prepare suggestions');submit.type='submit';form.append(submit);
  form.addEventListener('submit',async event=>{event.preventDefault();submit.disabled=true;try{
    const found=await api('manuscript?id='+encodeURIComponent(id));const draft=studio.editorDrafts?.[id];
    if(draft&&draft.content!==draft.baseContent)throw new Error('Save your local edits before requesting suggestions.');
    const request=(check==='shape'?'Focus only on the '+held.part+'. Offer up to three meaningfully different, supported alternatives as separate located edits with brief tradeoffs. Never apply or rename anything. Preserve technical qualifiers and author voice; invent no facts, offers, urgency or URLs. ':'')+held.focus;
    await api('editor-check',{id,expected:found.expected,check,request,research:'none',sources:found.sources});sCloseSheet();await sRoute('editor',id);
  }catch(error){problem.textContent=error.message;}finally{submit.disabled=false;}});
  sOpenSheet(check==='geo'?'Improve clarity and citation readiness':'Improve a title or opening',form,sButton('Cancel',sCloseSheet));
}

async function sTaskRead(title,endpoint){
  const problem=sNode('p','problem');problem.setAttribute('role','alert');sOpenSheet(title,sNode('p','','Reading saved work…'),problem,sButton('Close',sCloseSheet));const owner=studio.sheet,turn=studio.turn;
  try{const found=await api(endpoint);return studio.sheet===owner&&studio.turn===turn?found:null;}catch(error){if(studio.sheet===owner)problem.textContent=error.message;return null;}
}
// The samples a learning reads, ticked: up to twenty. `keep` narrows the list to one author's
// writing; a ticked sample always shows.
function sToolSamples(found,held,legend='Authored samples permitted for voice analysis',keep=()=>true){
  const box=sNode('fieldset','sample-picks'),title=sNode('legend','',legend),count=sNode('p','quiet sample-count');box.append(title);
  const say=()=>{const n=held.samples.length;count.textContent=n>20?n+' ticked: untick '+(n-20)+'. A learning reads up to twenty.':n+' of up to 20 ticked.';};
  const shown=(found.samples||[]).filter(source=>held.samples.includes(source.id)||keep(source));
  for(const source of shown){const label=sNode('label','check'),input=sNode('input');input.type='checkbox';input.value=source.id;input.checked=held.samples.includes(source.id);input.addEventListener('change',()=>{held.samples=input.checked?[...held.samples,source.id]:held.samples.filter(id=>id!==source.id);say();});label.append(input,sNode('span','',source.name+(source.author?' · '+source.author:'')));box.append(label);}
  if(!shown.length)box.append(sNode('p','quiet','None yet. Writing you add above is listed here, ticked.'));else{say();box.append(count);}return box;
}
// One author's writing, as a voice sheet names it: the same words of the shorter name appear in the longer one.
function sSameAuthor(left,right){const words=value=>new Set(String(value||'').toLowerCase().normalize('NFKD').replace(/[^\p{L}\p{N}\s]/gu,' ').split(/\s+/).filter(Boolean));const a=words(left),b=words(right);if(!a.size||!b.size)return false;const [small,large]=a.size<=b.size?[a,b]:[b,a];return [...small].every(word=>large.has(word));}
// What else could be a sample: a ready source becomes one by its author (or, for a style, as
// an example); a source still waiting for text is shown but cannot be chosen; an upload here
// is a sample from the start. Returns the library list and the upload field apart, so the
// sheet can place each under its own source; `keep` narrows the list to one author.
function sSampleCandidates(found,held,purpose,reopen,keep=()=>true){
  const voice=purpose==='voice-sample',problem=sNode('p','problem'),list=sNode('ul','rows');problem.setAttribute('role','alert');
  const candidates=(found.candidates||[]).filter(keep),others=(found.candidates||[]).length-candidates.length;
  for(const source of candidates){
    const named=(source.author||'').trim(),who={author:''};
    const use=sButton(voice?(named?'Use as a sample by '+named:'Use as a sample'):'Use as an example',async button=>busy(button,'Saving…',async()=>{
      const author=named||who.author.trim();if(voice&&!author){problem.textContent='Say whose writing '+source.name+' is first.';return;}
      const mine=!voice||author.toLowerCase()===held.name.trim().toLowerCase();
      try{await api('tool-action',{action:'source-purpose',source:source.id,purpose,...(voice&&!named?{author}:{})});if(mine&&held.samples.length<20&&!held.samples.includes(source.id))held.samples=[...held.samples,source.id];await reopen();}catch(error){problem.textContent=error.message;}
    }));
    const names=author=>use.setAttribute('aria-label','Use '+source.name+(voice?' as a sample'+(author?' by '+author:''):' as an example'));names(named);
    const text=sAdd(sNode('div','row-text'),sNode('h3','row-title',source.name),sNode('p','quiet',named?'By '+named:voice?'No author saved':'In your reference library'));
    if(voice&&!named)text.append(sField('candidate-author-'+source.id,'Whose writing is this?',who,'author',{max:200,changed:value=>{use.textContent=value.trim()?'Use as a sample by '+value.trim():'Use as a sample';names(value.trim());}}));
    list.append(sAdd(sNode('li','row'),text,use));
  }
  for(const source of (found.pending||[]).filter(keep))list.append(sAdd(sNode('li','row'),sAdd(sNode('div','row-text'),sNode('p','row-title',source.name+' · needs text'),sNode('p','quiet','It has no readable text yet, so it cannot be chosen.'))));
  const library=sAdd(sNode('div','library-candidates'),list.children.length?list:sNode('p','quiet',voice?'No other posts in the library by this author.':'No other sources in the library.'),others?sNode('p','quiet',others+(others===1?' post by another author is':' posts by other authors are')+' not shown. Change the name to see theirs.'):null);
  const field=sNode('div','field'),upload=sNode('input','input'),label=sNode('label','field-label',voice?'Upload their posts':'Upload examples');upload.type='file';upload.multiple=true;upload.id=(voice?'learn-voice':'learn-style')+'-upload';upload.accept='.md,.txt,.html,.htm,.docx,.pdf';label.htmlFor=upload.id;
  const hint=sNode('p','quiet field-hint',voice?'Saved as this author’s writing, not as a reference. Up to 10 MiB each.':'Saved as style samples of this kind of post. Up to 10 MiB each.');hint.id=upload.id+'-hint';upload.setAttribute('aria-describedby',hint.id);
  upload.addEventListener('change',async()=>{const files=[...(upload.files||[])];if(!files.length)return;if(files.some(file=>file.size>10*1024*1024)){problem.textContent='Choose files up to 10 MiB each.';return;}const author=voice?held.name.trim():'';if(voice&&!author){problem.textContent='Say whose voice this is first, so the samples are saved as their writing.';return;}upload.disabled=true;problem.textContent=files.length===1?'Saving the file…':'Saving '+files.length+' files…';let ready=0;try{for(const file of files){const result=await api('upload',{filename:file.name,title:file.name,content:await encodeImportFile(file),purpose,as_blog:false,analyze:false,operation:operationId(),...(author?{author}:{})});if(result.state==='ready'){ready++;if(held.samples.length<20&&!held.samples.includes(result.source.id))held.samples=[...held.samples,result.source.id];}}problem.textContent='';await reopen();sToast(ready===files.length?(files.length===1?'Saved as a sample.':'Saved '+files.length+' samples.'):'Saved. '+(files.length-ready)+' need text before they can be samples.');}catch(error){problem.textContent=error.message;}finally{upload.disabled=false;}});
  return {library,others,upload:sAdd(field,label,upload,hint),problem};
}
function sSampleRow(title,says,...actions){for(const action of actions)if(action.textContent.startsWith('Read and manage ')){action.setAttribute('aria-label',action.textContent);action.textContent='Read and manage';}return sAdd(sNode('li','row sample-row'),sAdd(sNode('div','row-text'),sNode('h3','row-title',title),sNode('p','quiet',says)),...actions);}
// A step of a create sheet: a numbered heading and what belongs to it.
function sCreateStep(number,title,...nodes){return sAdd(sNode('section','create-step'),sNode('h3','sheet-part',number+'. '+title),...nodes.filter(Boolean));}
// Voices and styles: a screen from the navigation, and a sheet from a blog's Tools, where a
// voice can be applied to that blog. One author's voice is made with Create a voice; every
// author in the team library at once with Create voices for every author.
const VOICES_SAY='A voice is how one person sounds; a style is the shape of a kind of writing. Both stay provisional until you confirm them, and choosing either never rewrites a blog.';
const KINDS_SAY='A kind of post is the shape a blog takes, such as a product announcement: its parts, length and register. Choose one when you start a blog.';
function sVoicesTitle(){return sVoicesOn()?'Voices and styles':'Kinds of post';}
async function sVoiceData(){const found=await api('voices');let kinds={styles:[]},failure='';try{kinds=await api('styles');}catch(error){failure=error.message;}return {found,kinds,failure};}
function sVoiceCards({found,kinds,failure},article=null,sheet=false){
  const voices=sNode('ul','rows');for(const profile of found.profiles)voices.append(sSampleRow(profile.name,`Revision ${profile.revision} · ${profile.status}`,sButton('Read and manage '+profile.name,()=>sVoiceProfile(profile.id,article))));
  const styles=sNode('ul','rows');for(const style of kinds.styles||[])styles.append(sSampleRow(style.name,[style.summary,style.kind==='seed'?'Starter':null,`Revision ${style.revision} · ${style.status}`].filter(Boolean).join(' · '),sButton('Read and manage '+style.name,()=>sStyleDetail(style.id,article))));
  // On the screen the toolbar holds Create a voice and Create a style; a sheet has no toolbar.
  const kindsCard=sCard(sVoicesOn()?'Styles':'Kinds of post',sNode('p','quiet','The shape of a kind of writing, such as a product announcement. Starters can be edited like any other.'),failure?sNode('p','problem',failure):(kinds.styles||[]).length?styles:sNode('p','','No styles yet.'),sAdd(sNode('div','bar'),sheet?sButton('Create a style',()=>sLearnStyle(kinds)):null,sButton('Write a style guide',()=>sEditStyle({name:'',guide:'',status:'provisional',sample_ids:[]},kinds))));
  if(!sVoicesOn())return [kindsCard];  // Voice learning is switched off; voice guides have their own screen.
  return [sCard('Voices',sNode('p','quiet','How one person sounds: you, or someone you write for.'),found.profiles.length?voices:sNode('p','','No voices yet. Create one from an author’s posts, links, uploads or LinkedIn export.'),sAdd(sNode('div','bar'),sheet?sButton('Create a voice',()=>sLearnVoice(found),'filled'):null,sButton('Write a voice guide',()=>sEditVoice({name:'',guide:'',status:'provisional',sample_ids:[]},found)))),
    sCard('Every author in the team library',sNode('p','quiet','A voice for each author whose posts are in the team library, from up to 20 of their posts. One confirmation for all of them; each voice stays provisional until you confirm it.'),sAdd(sNode('div','bar'),sButton('Create voices for every author',()=>sVoicesForAuthors()))),
    kindsCard];
}
async function sVoiceTools(article=null){
  // Back from a voice or style sheet to the screen, when the screen is what is showing.
  if(!article&&studio.screen==='voices'){sCloseSheet();return sVoicesPage();}
  const found=await sTaskRead(sVoicesTitle(),'voices');if(!found)return;const owner=studio.sheet;
  let kinds={styles:[]},failure='';try{kinds=await api('styles');}catch(error){failure=error.message;}if(studio.sheet!==owner)return;
  sOpenSheet(sVoicesTitle(),sNode('p','',sVoicesOn()?VOICES_SAY:KINDS_SAY),...sVoiceCards({found,kinds,failure},article,true),sButton('Close',sCloseSheet));
}
async function sVoicesPage(turn=studio.turn){
  const data=await sVoiceData();if(turn!==studio.turn)return;
  if(!sVoicesOn()){sFrame('Kinds of post',[sButton('Create a style',()=>sLearnStyle(data.kinds),'filled')],'',()=>sRoute(['home','blogs','status','guides'].includes(studio.kindsFrom)?studio.kindsFrom:'settings'));sPage(sNode('p','lede',KINDS_SAY),...sVoiceCards(data));return;}
  sFrame('Voices and styles',[sButton('Create a voice',()=>sLearnVoice(data.found),'filled'),sButton('Create a style',()=>sLearnStyle(data.kinds))],'',()=>sRoute(['home','blogs','status','guides'].includes(studio.kindsFrom)?studio.kindsFrom:'settings'));
  sPage(sNode('p','lede',VOICES_SAY),...sVoiceCards(data));
}
// Voice guides: how a piece should sound, as a name and text. Written by hand or made from a
// few samples, edited, and applied to a draft from Finishing on the desk. Saved as the
// profiles voices always were, so learned voices are guides too. Not behind the voice switch.
const GUIDES_SAY='A voice guide says how a piece should sound. Apply one to a draft from Finishing on the desk: the draft keeps its facts, quotes and shape.';
const GUIDE_STATUS={provisional:'Provisional',retired:'Retired'};
async function sGuidesPage(turn=studio.turn){
  const found=await api('voice-guides');if(turn!==studio.turn)return;studio.guides=found;
  sFrame('Voice guides',[sButton('New voice guide',()=>sGuideSheet(),'filled')]);
  const active=found.guides.filter(guide=>guide.status!=='retired'),retired=found.guides.filter(guide=>guide.status==='retired');
  const card=guide=>sAdd(sNode('section','card guide-card'),sNode('h2','card-title',guide.name),guide.says?sNode('p','',guide.says):sNode('p','quiet','No text yet.'),GUIDE_STATUS[guide.status]?sNode('p','quiet',GUIDE_STATUS[guide.status]):null,sAdd(sNode('div','bar'),(()=>{const open=sButton('Open',()=>sGuideSheet(guide.id));open.setAttribute('aria-label','Open '+guide.name);return open;})()));
  const making=found.making.map(row=>sAdd(sNode('section','card guide-card'),sNode('h2','card-title',row.name||'A voice guide'),sNode('p','quiet',{queued:'Waiting to start.',working:'Being made from your samples…',ready:'Ready to read and save.',failed:'This did not finish.'}[row.status]||''),sAdd(sNode('div','bar'),sButton(row.status==='ready'?'Read and save':'Open',()=>sGuideSheet(null,row.id),row.status==='ready'?'filled':''),(()=>{const discard=sButton('Discard',async button=>{await busy(button,'Discarding…',async()=>{try{await api('tool-action',{action:'guide-discard',job:row.id});await sGuidesPage();}catch(error){notice(error.message,true);}});});discard.setAttribute('aria-label','Discard '+(row.name||'this voice guide'));discard.disabled=!access.actions.edit;return discard;})())));
  sPage(sNode('p','lede',GUIDES_SAY),making.length?sAdd(sNode('div','grid'),...making):null,active.length?sAdd(sNode('div','grid'),...active.map(card)):sCard('No voice guides yet',sNode('p','','Write one by hand, or make one from three to twenty samples of the writing you want to sound like.')),
    retired.length?disclosure('Retired ('+retired.length+')',sAdd(sNode('div','grid'),...retired.map(card))):null,
    sVoicesOn()?sCard('Learning voices',sNode('p','quiet','The older voice tools are on: learn a voice from an author’s posts, links or a LinkedIn export, and choose Write as for a blog.'),sButton('Open voices and styles',()=>sRoute('voices'))):null);
}
function sGuideNew(){return {name:'',way:'write',guide:'',samples:[{text:''},{text:''},{text:''}],files:[],job:null,operation:operationId(),problem:''};}
// New voice guide, or one already saved (`id`), or one being made from samples (`job`).
async function sGuideSheet(id=null,job=null){
  if(id){
    const found=await sTaskRead('Voice guide','voice?profile='+encodeURIComponent(id));if(!found)return;
    return sGuideEdit(found);
  }
  const held=job?{...sGuideNew(),way:'samples',job:{id:job,status:'queued'}}:studio.guideDraft||sGuideNew();studio.guideDraft=held;
  if(job){try{held.job=await api('tool-job?job='+encodeURIComponent(job));if(held.job.status==='ready'&&!held.guide)held.guide=held.job.result?.content||'';if(!held.name)held.name=held.job.metadata?.name||'';}catch(error){held.problem=error.message;}}
  sGuideDraw(held);
}
function sGuideDraw(held){
  const form=sNode('form','create-flow'),problem=sNode('p','problem',held.problem||'');problem.setAttribute('role','alert');
  const ready=held.job?.status==='ready',busyJob=['queued','working'].includes(held.job?.status);
  const how=sChoice('How to start',[['write','Write it'],['samples','From samples']],held,'way',()=>sGuideDraw(held));
  const samples=[],counted=sNode('p','quiet'),recount=()=>{const count=held.samples.filter(sample=>sample.text.trim()).length+held.files.length;counted.textContent=count+(count===1?' sample':' samples')+'. Three to twenty: posts, emails or notes in the voice you want, by one writer.';};
  if(held.way==='samples'){
    held.samples.forEach((sample,index)=>samples.push(sField('guide-sample-'+(index+1),'Sample '+(index+1),sample,'text',{long:true,max:200000,changed:recount})));
    const more=sButton('Add another sample',()=>{held.samples.push({text:''});sGuideDraw(held);});more.disabled=held.samples.length+held.files.length>=20;
    const field=sNode('div','field'),upload=sNode('input','input'),label=sNode('label','field-label','Upload samples');upload.type='file';upload.multiple=true;upload.id='guide-upload';upload.accept='.md,.txt,.html,.htm,.docx,.pdf';label.htmlFor=upload.id;
    upload.addEventListener('change',async()=>{const chosen=Array.from(upload.files||[]);if(chosen.some(file=>file.size>10*1024*1024)){held.problem='Choose files up to 10 MiB each.';return sGuideDraw(held);}for(const file of chosen)held.files.push({filename:file.name,content:await encodeImportFile(file)});held.problem='';sGuideDraw(held);});
    field.append(label,upload,sNode('p','quiet field-hint','Markdown, text, HTML or DOCX. Nothing you add here is kept in the library.'));
    const files=held.files.length?sAdd(sNode('ul','rows'),...held.files.map((file,index)=>sAdd(sNode('li','row'),sNode('span','row-title',file.filename),sButton('Remove',()=>{held.files.splice(index,1);sGuideDraw(held);})))):null;
    recount();
    const make=sButton(held.job&&!busyJob?'Make the guide again':'Make the guide',async button=>{await busy(button,'Starting…',async()=>{try{const given=[...held.samples.filter(sample=>sample.text.trim()).map(sample=>({text:sample.text})),...held.files];held.job=await api('tool-action',{action:'job-create',kind:'voice-guide',operation:held.operation,name:held.name.trim(),samples:given});held.operation=operationId();held.problem='';sGuideFollow(held);}catch(error){held.problem=error.message;}sGuideDraw(held);});},'filled');make.disabled=busyJob||!access.actions.edit;
    samples.push(more,field,files,counted,sAdd(sNode('div','bar'),make));
    if(busyJob){const note=sNode('p','desk-working-note','Making the guide from your samples…');note.setAttribute('role','status');samples.push(note);}
    if(held.job?.status==='failed')samples.push(sNode('p','problem',held.job.error||'This did not finish. Make the guide again.'));
  }
  const text=held.way==='write'||ready||held.guide?sField('guide-text','The guide',held,'guide',{long:true,max:40000,required:true,hint:held.way==='samples'?'Made from your samples. Read it and change anything that is not how this writing sounds.':'How this writing sounds: register, sentence length, openings, words to use and avoid.'}):sNode('p','quiet','The guide appears here when it is made. You can edit it before saving.');
  const guideBox=text.querySelector?.('textarea');if(guideBox)guideBox.rows=12;
  const save=sNode('button','button button-filled','Save guide');save.type='submit';save.disabled=!access.actions.edit||held.way==='samples'&&!ready&&!held.guide;
  form.append(sCreateStep(1,'Name',sField('guide-name','Name',held,'name',{required:true,max:200})),sCreateStep(2,'Write it, or make it from samples',how,...samples),sCreateStep(3,'Read and edit',text),problem,sAdd(sNode('div','bar form-actions'),save,sButton('Cancel',()=>{studio.guideDraft=null;sCloseSheet();})));
  form.addEventListener('submit',async event=>{event.preventDefault();await busy(save,'Saving…',async()=>{try{
    if(!held.name.trim()||!held.guide.trim())throw new Error('Give the guide a name and its text.');
    const fromJob=held.way==='samples'&&held.job?.status==='ready';
    const saved=await api('tool-action',fromJob?{action:'job-apply',job:held.job.id,name:held.name.trim(),content:held.guide}:{action:'profile-save',name:held.name.trim(),guide:held.guide,status:'confirmed',confirmed:true});
    studio.guideDraft=null;sCloseSheet();if(saved.team_sync)savedNotice(saved);sToast('Saved “'+held.name.trim()+'”. Apply it from Finishing on the desk.');if(studio.screen==='guides')await sGuidesPage();
  }catch(error){problem.textContent=error.message;}});});
  sOpenSheet('New voice guide',form);held.sheet=studio.sheet;
}
function sGuideFollow(held){
  if(held.following)return;held.following=true;
  setTimeout(async()=>{held.following=false;if(studio.guideDraft!==held||!held.job||studio.sheet!==held.sheet)return;
    try{held.job=await api('tool-job?job='+encodeURIComponent(held.job.id));}catch(error){held.problem=error.message;}
    if(['queued','working'].includes(held.job?.status))return sGuideFollow(held);
    if(held.job?.status==='ready'&&!held.guide.trim())held.guide=held.job.result?.content||'';
    if(studio.guideDraft===held&&studio.sheet===held.sheet)sGuideDraw(held);
  },2000);
}
function sGuideEdit(found){
  const held={name:found.name,guide:found.guide},form=sNode('form','create-flow'),problem=sNode('p','problem');problem.setAttribute('role','alert');
  const retired=found.status==='retired';
  if(retired){sOpenSheet(found.name,sNode('p','quiet','Retired. Drafts that used it keep what was applied.'),sNode('p','desk-plain',found.guide),sButton('Close',sCloseSheet));return;}
  const save=sNode('button','button button-filled','Save guide');save.type='submit';save.disabled=!access.actions.edit;
  const retire=sButton('Retire this guide',()=>sOpenSheet('Retire '+found.name+'?',sNode('p','','It leaves the list of guides you can apply. Drafts that used it keep their text, and blogs that write as it keep it.'),sAdd(sNode('div','bar'),sButton('Retire',async button=>{await busy(button,'Retiring…',async()=>{try{const saved=await api('tool-action',{action:'profile-retire',profile:found.id,expected:found.expected,confirmed:true});sCloseSheet();if(saved.team_sync)savedNotice(saved);sToast('Retired “'+found.name+'”.');if(studio.screen==='guides')await sGuidesPage();}catch(error){notice(error.message,true);}});},'danger'),sButton('Cancel',()=>sGuideEdit(found)))));retire.disabled=!access.actions.edit;
  const guideText=sField('guide-text','The guide',held,'guide',{long:true,max:40000,required:true}),guideBox=guideText.querySelector?.('textarea');if(guideBox)guideBox.rows=14;
  form.append(sField('guide-name','Name',held,'name',{required:true,max:200}),guideText,found.status==='provisional'?sNode('p','quiet','Provisional: learned from samples and not yet confirmed. Saving it here confirms it.'):null,problem,sAdd(sNode('div','bar form-actions'),save,retire));
  form.addEventListener('submit',async event=>{event.preventDefault();await busy(save,'Saving…',async()=>{try{const saved=await api('tool-action',{action:'profile-save',profile:found.id,expected:found.expected,name:held.name.trim(),guide:held.guide,status:'confirmed',confirmed:true});sCloseSheet();if(saved.team_sync)savedNotice(saved);sToast('Saved “'+held.name.trim()+'”.');if(studio.screen==='guides')await sGuidesPage();}catch(error){problem.textContent=error.message;}});});
  sOpenSheet(found.name,form);
}
// Items chosen on the library screen are not samples yet: the sheet lists them ticked beside
// the samples, and they become samples only when the learning is confirmed (`mark`).
function sWithLibraryItems(found,held){const extra=held.extra||[];if(!extra.length)return found;const known=new Set((found.samples||[]).map(source=>source.id)),added=extra.filter(source=>!known.has(source.id)),ids=new Set(extra.map(source=>source.id));return {...found,samples:[...(found.samples||[]),...added],candidates:(found.candidates||[]).filter(source=>!ids.has(source.id))};}
function sMarks(held){const ids=new Set((held.extra||[]).map(source=>source.id));return held.samples.some(id=>ids.has(id))?{mark:true}:{};}
// Create a voice: one author's voice, in the order a person works. Name the author; add their
// writing from links to their posts, uploads, a LinkedIn export or posts already in the
// library; tick up to twenty samples; then confirm the permission and build. Every source
// comes back to this sheet with what it added ticked. With a profile it updates that voice.
function sLearnVoice(found,profile=null,preselected=[],background=null,author='',extra=null,note=''){
  studio.voiceLearning||={};const held=studio.voiceLearning[profile?.id||'new']||={name:profile?.name||'',samples:[...(profile?.sample_ids||[])],background:null,operation:operationId()},form=sNode('form','create-flow'),problem=sNode('p','problem');problem.setAttribute('role','alert');
  if(preselected.length){held.samples=[...preselected].slice(0,20);held.background=background;held.extra=extra||[];held.note=note;}
  if(author)held.name=author;found=sWithLibraryItems(found,held);
  const reopen=async()=>sLearnVoice(await api('voices'),profile);
  const name=held.name.trim(),keep=source=>!name||!(source.author||'').trim()||sSameAuthor(source.author,name);
  const sources=sSampleCandidates(found,held,'voice-sample',reopen,keep);
  const links=()=>{const kept=sVoiceLinksHeld(profile);if(!kept.author.trim())kept.author=held.name.trim();return sVoiceLinks(found,profile,null);};
  const fromLibrary=disclosure('Posts already in the library',sources.library);fromLibrary.open=!!held.libraryOpen||sources.library.querySelector?.('.row')!==null&&!!name;fromLibrary.addEventListener('toggle',()=>{held.libraryOpen=fromLibrary.open;});
  form.append(
    sCreateStep(1,'Whose voice is this?',sField('learn-voice-name','Name',held,'name',{required:true,max:200,hint:'The author’s name: yours, or the person you write for. Their writing below is filtered to this name.'})),
    sCreateStep(2,'Add their writing',sNode('p','quiet','From any of these; everything lands in step 3, ticked.'),sAdd(sNode('div','bar'),sButton('Add links to posts',links),sButton('Import a LinkedIn export',()=>sLinkedInImport(held.name.trim()))),sources.upload,fromLibrary,sources.problem),
    sCreateStep(3,'Choose up to 20 samples',held.note?sNode('p','quiet',held.note):null,sToolSamples(found,held,'Authored samples permitted for voice analysis',keep)),problem);
  const check=sNode('input');check.type='checkbox';check.id='learn-voice-permission';const confirm=sNode('label','check');confirm.append(check,sNode('span','','I have permission to analyze this writing with my selected assistant.'));form.append(confirm);const submit=sNode('button','button button-filled',profile?'Update '+profile.name+'’s voice':'Build a provisional voice');submit.type='submit';form.append(sAdd(sNode('div','bar create-foot'),submit,sButton('Cancel',sCloseSheet)));
  form.addEventListener('submit',async event=>{event.preventDefault();if(!check.checked){problem.textContent='Confirm sample permissions before starting analysis.';return;}if(held.samples.length>20){problem.textContent='Untick '+(held.samples.length-20)+' samples: a learning reads up to twenty.';return;}submit.disabled=true;try{const job=await api('tool-action',sTaskPayload(held,{action:'job-create',kind:'voice-learn',operation:held.operation,name:held.name,samples:held.samples,profile:profile?.id||null,background:held.background||null,confirmed:true,...sMarks(held)}));sToolJob(job);}catch(error){problem.textContent=error.message;}finally{submit.disabled=false;}});
  sOpenSheet(profile?'Update '+profile.name+'’s voice':'Create a voice',form);
}
// Create a style: the same shape for a kind of writing. Name it, add examples, tick, build.
function sLearnStyle(kinds,style=null,preselected=[],name='',extra=null,note=''){
  studio.styleLearning||={};const held=studio.styleLearning[style?.id||'new']||={name:style?.name||'',samples:[...(style?.sample_ids||[])],operation:operationId()},form=sNode('form','create-flow'),problem=sNode('p','problem');problem.setAttribute('role','alert');
  if(preselected.length){held.samples=[...preselected].slice(0,20);held.extra=extra||[];held.note=note;}
  if(name&&!held.name.trim())held.name=name;kinds=sWithLibraryItems(kinds,held);
  const reopen=async()=>sLearnStyle(await api('styles'),style);
  const sources=sSampleCandidates(kinds,held,'style-sample',reopen);
  const fromLibrary=disclosure('Sources already in the library',sources.library);fromLibrary.open=held.libraryOpen!==false;fromLibrary.addEventListener('toggle',()=>{held.libraryOpen=fromLibrary.open;});
  form.append(
    sCreateStep(1,'What kind of writing is this?',sField('learn-style-name','Style name',held,'name',{required:true,max:200,hint:'The kind of writing, such as Product announcement, not a person.'})),
    sCreateStep(2,'Add examples',sNode('p','quiet','From any of these; everything lands in step 3, ticked.'),sAdd(sNode('div','bar'),sButton('Add links to examples',()=>sVoiceLinks(kinds,null,null,'style-sample'))),sources.upload,fromLibrary,sources.problem),
    sCreateStep(3,'Choose up to 20 examples',held.note?sNode('p','quiet',held.note):null,sToolSamples(kinds,held,'Style samples')),problem);
  const check=sNode('input');check.type='checkbox';check.id='learn-style-permission';const confirm=sNode('label','check');confirm.append(check,sNode('span','','I may analyze these examples with my selected assistant.'));form.append(confirm);const submit=sNode('button','button button-filled',style?'Update '+style.name:'Build a provisional style');submit.type='submit';form.append(sAdd(sNode('div','bar create-foot'),submit,sButton('Cancel',sCloseSheet)));
  form.addEventListener('submit',async event=>{event.preventDefault();if(!check.checked){problem.textContent='Confirm you may analyze these examples before starting.';return;}if(held.samples.length>20){problem.textContent='Untick '+(held.samples.length-20)+' examples: a learning reads up to twenty.';return;}submit.disabled=true;try{const job=await api('tool-action',sTaskPayload(held,{action:'job-create',kind:'style-learn',operation:held.operation,name:held.name,samples:held.samples,style:style?.id||null,confirmed:true,...sMarks(held)}));sToolJob(job);}catch(error){problem.textContent=error.message;}finally{submit.disabled=false;}});
  sOpenSheet(style?'Update '+style.name:'Create a style',form);
}
async function sStyleDetail(id,article){
  const found=await sTaskRead('Style','style?style='+encodeURIComponent(id));if(!found)return;
  const problem=sNode('p','problem');problem.setAttribute('role','alert');
  sOpenSheet(found.name,sNode('p','quiet',(found.kind==='seed'?'Starter style · ':'')+`Revision ${found.revision} · ${found.status}`),sAdd(sNode('article','paper doc'),window.TrainingStudioMarkdown.render(found.guide||'')),
    sButton('Edit this style guide',async()=>sEditStyle(found,await api('styles'))),
    sButton('Export style guide',()=>sDownload({name:found.id+'-style.md',content:found.guide||''})),
    found.status!=='retired'?sButton('Retire this kind of post',()=>sOpenSheet('Retire this kind of post?',sNode('p','','It leaves future choices of a kind of post. Existing blogs keep their pinned revision.'),sButton('Retire it',async button=>busy(button,'Retiring…',async()=>{await api('tool-action',{action:'style-retire',style:id,expected:found.expected,confirmed:true});await sVoiceTools(article);})),sButton('Cancel',sCloseSheet))):null,
    problem,sButton('All voices and styles',()=>sVoiceTools(article)),sButton('Close',sCloseSheet));
}
function sEditStyle(style,kinds){
  studio.styleEdits||={};const held=studio.styleEdits[(style.id||'new')+':'+(style.expected||'')]||={name:style.name,guide:style.guide||'',samples:[...(style.sample_ids||[])]},form=sNode('form'),problem=sNode('p','problem');problem.setAttribute('role','alert');
  form.append(sField('style-name','Style name',held,'name',{required:true,max:200}),sField('style-guide','Style guide',held,'guide',{long:true,max:40000,required:true}),sToolSamples(kinds,held,'Style samples'));
  const confirm=sNode('input');confirm.type='checkbox';const label=sNode('label','check');label.append(confirm,sNode('span','','I reviewed this guide and confirm it describes the intended kind of writing.'));form.append(label,problem);
  const save=confirmed=>async button=>busy(button,'Saving…',async()=>{try{if(confirmed&&!confirm.checked)throw new Error('Review and confirm the guide first.');await api('tool-action',{action:'style-save',style:style.id||null,expected:style.expected,name:held.name,guide:held.guide,samples:held.samples,status:confirmed?'confirmed':'provisional',confirmed});await sVoiceTools();}catch(error){problem.textContent=error.message;}});
  sOpenSheet('Edit style guide',form,sButton('Save provisional guide',save(false)),sButton('Confirm style guide',save(true)),sButton('Cancel',sCloseSheet));
}
function sIntakeRows(found){const list=sNode('ul','rows');for(const row of found.files)list.append(sAdd(sNode('li','row'),sAdd(sNode('div','row-text'),sNode('h3','row-title',row.filename),sNode('p','quiet',row.state==='failed'?'Not read: '+row.note:row.note||(row.state==='ready'?row.chars+' characters of text':'Saved without text')))));return list;}
// A LinkedIn export: one zip, its About text kept as background and its articles as samples.
function sLinkedInImport(author=''){
  const held={author,operation:operationId()},form=sNode('form'),problem=sNode('p','problem'),result=sNode('div');problem.setAttribute('role','alert');
  const steps=sAdd(sNode('ol',''),...['On LinkedIn, open Settings & Privacy, then Data privacy, then Get a copy of your data.','Choose Profile and Articles, request the archive and wait for LinkedIn’s email.','Download the zip and choose it here. Only Profile.csv and the articles are read; connections and messages are not.'].map(words=>sNode('li','',words)));
  const box=sNode('div','field'),label=sNode('label','field-label','LinkedIn export (.zip)'),input=sNode('input','input');input.type='file';input.accept='.zip';input.id='linkedin-file';label.htmlFor=input.id;box.append(label,input);
  const submit=sNode('button','button button-filled','Read the export');submit.type='submit';
  form.append(steps,sNode('p','','The About text and the articles are saved as sources in your reference library. With a Team Hub selected, they are shared with your team like any other source.'),box,sField('linkedin-author','Whose export is this? (optional)',held,'author',{max:200,hint:'Leave it blank to use the name in the export. Give a name when a colleague handed you theirs.'}),problem,result,submit);
  form.addEventListener('submit',async event=>{event.preventDefault();const file=input.files?.[0];if(!file){problem.textContent='Choose the downloaded zip first.';return;}if(file.size>10*1024*1024){problem.textContent='Choose an export up to 10 MiB. Request only Profile and Articles.';return;}submit.disabled=true;problem.textContent='Reading the export…';try{const found=await api('upload',{operation:held.operation,files:[{linkedin:await encodeImportFile(file)}],purpose:'voice-sample',analyze:false,...(held.author.trim()?{author:held.author.trim()}:{})});held.operation=operationId();problem.textContent='';const samples=found.files.filter(row=>row.source&&row.purpose==='voice-sample').map(row=>row.source.id),background=found.files.find(row=>row.purpose==='author-background')?.source?.id||null,who=found.files.find(row=>row.author)?.author||held.author.trim();result.replaceChildren(sNode('p','',(who?'Writing by '+who+'. ':'')+found.next_step),sIntakeRows(found),samples.length?sButton(who?'Learn '+who+'’s voice from these articles':'Learn a voice from these articles',async()=>sLearnVoice(await api('voices'),null,[...new Set([...sKeptSamples('new',who),...samples])].slice(0,20),background,who),'filled'):sNode('p','quiet','No articles were in this export, so there is nothing to learn a voice from yet. Add links to posts by this author, or upload samples.'));}catch(error){problem.textContent=error.message;}finally{submit.disabled=false;}});
  sOpenSheet('Import a LinkedIn export',form,sButton('Back to Create a voice',async()=>sLearnVoice(await api('voices'))));
}
// What a Create a voice sheet already ticked for this author, so a source adds to it.
function sKeptSamples(key,author){const kept=studio.voiceLearning?.[key];return kept&&(!kept.name.trim()||sSameAuthor(kept.name,author))?kept.samples:[];}
// Published posts as voice samples, or as examples of a kind of writing (style samples): a list
// of links, checked, then imported through the reference library.
const LINK_LIST_WORDS=['blog','blogs','link','links','post','posts','url','urls','list','articles'];
function sAuthorFromFile(name){return String(name||'').replace(/\.[^.]*$/,'').split(/[\s_.-]+/).filter(word=>word&&!/^\d+$/.test(word)&&!LINK_LIST_WORDS.includes(word.toLowerCase())).map(word=>word[0].toUpperCase()+word.slice(1)).join(' ').slice(0,200);}
function sVoiceLinksHeld(profile,purpose='voice-sample'){studio.voiceLinks||={};return studio.voiceLinks[(profile?.id||'new')+':'+purpose]||={purpose,text:'',file:'',author:purpose==='voice-sample'?profile?.name||'':'',site:'',operation:operationId(),keep:[],retry:false,shown:null,result:null};}
function sVoiceLinks(found,profile=null,article=null,purpose='voice-sample'){
  const style=purpose==='style-sample',held=sVoiceLinksHeld(profile,purpose),form=sNode('form'),problem=sNode('p','problem');problem.setAttribute('role','alert');
  const box=sNode('div','field'),label=sNode('label','field-label','Text file of links'),input=sNode('input','input');input.type='file';input.accept='.txt,text/plain';input.id='voice-links-file';label.htmlFor=input.id;
  input.addEventListener('change',async()=>{const file=input.files?.[0];if(!file)return;if(file.size>256*1024){problem.textContent='Choose a text file up to 256 KiB.';return;}try{held.text=await file.text();}catch(error){problem.textContent='This file could not be read as text.';return;}held.file=file.name;if(!style&&!held.author.trim())held.author=sAuthorFromFile(file.name);held.site='';held.shown=null;sVoiceLinks(found,profile,article,purpose);});
  box.append(label,input,sNode('p','quiet field-hint',held.file?'Read '+held.file+'. You can still edit the links below.':'One link per line. Blank lines and lines that start with # are ignored.'));
  form.append(sNode('p','',style?'Use published examples of one kind of writing, from one site, to learn its style.':profile?'Add posts '+profile.name+' published on one site as samples for this voice.':'Use posts an author published on one site as samples for learning their voice.'),box,
    sField('voice-links-text','Or paste the links',held,'text',{long:true,max:262144,changed:()=>{held.site='';held.shown=null;}}),
    style?sField('voice-links-author','What kind of writing is this?',held,'author',{required:true,max:200,hint:'For example, Product announcements.',changed:()=>{held.shown=null;}}):sField('voice-links-author','Whose posts are these?',held,'author',{required:true,max:200,hint:'Each imported post is saved as this author’s sample. A post whose page names someone else is left out unless you keep it.',changed:()=>{held.shown=null;}}),problem);
  const submit=sNode('button','button button-filled','Check these links');submit.type='submit';form.append(submit);
  form.addEventListener('submit',async event=>{event.preventDefault();if(!held.text.trim()){problem.textContent='Choose a text file or paste links first.';return;}if(!held.author.trim()){problem.textContent=style?'Name the kind of writing these posts are.':'Name the author of these posts.';return;}await sVoiceLinksCheck(found,profile,article,held,submit,problem);});
  sOpenSheet(style?'Add links to examples':profile?'Add published posts to '+profile.name:'Add published posts',form,sButton(style?'Back to Create a style':profile?'Back to '+profile.name:'Back to Create a voice',async()=>style?sLearnStyle(await api('styles')):profile?sVoiceProfile(profile.id,article):sLearnVoice(await api('voices'))));
}
async function sVoiceLinksCheck(found,profile,article,held,button,problem){
  await busy(button,'Checking…',async()=>{try{const shown=await api('voice-links-preview',{text:held.text,author:held.author.trim(),site:held.site||null,purpose:held.purpose});if(held.shown?.expected!==shown.expected||!shown.expected){held.operation=operationId();held.keep=[];held.result=null;}held.shown=shown;sVoiceLinksPreview(found,profile,article,held);}catch(error){problem.textContent=error.message;}});
}
function sVoiceLinksPreview(found,profile,article,held){
  const shown=held.shown,style=held.purpose==='style-sample',problem=sNode('p','problem');problem.setAttribute('role','alert');const back=sButton('Change the links',()=>sVoiceLinks(found,profile,article,held.purpose));
  if(shown.status==='choose-site'){const choices=sNode('div');for(const site of shown.sites)choices.append(sButton('Use '+site.shown+' ('+site.links+(site.links===1?' link)':' links)'),async button=>{held.site=site.site;await sVoiceLinksCheck(found,profile,article,held,button,problem);},'filled'));return sOpenSheet('Choose one site',sNode('p','',shown.problem),choices,problem,back);}
  const notes=sNode('ul','rows'),note=text=>notes.append(sAdd(sNode('li','row'),sNode('p','row-says',text)));
  note(shown.in_library?shown.in_library+' already in your reference library: reused, not fetched again.':'None of these posts is in your reference library yet.');
  if(shown.to_fetch)note(shown.to_fetch+(shown.to_fetch===1?' new page is':' new pages are')+' fetched once from '+shown.shown_scope+' and saved there.');
  if(shown.left_out)note(shown.left_out+' links from other sites are left out of this import.');
  if(shown.duplicates)note(shown.duplicates+' repeated links are counted once.');
  if(shown.comments)note(shown.comments+' comment lines are ignored.');
  if(shown.upgraded)note(shown.upgraded+' http:// links are read over https://.');
  const skipped=shown.unusable?disclosure(shown.unusable+' lines are not usable links',sAdd(sNode('ul','rows'),...shown.skipped.map(row=>sAdd(sNode('li','row'),sAdd(sNode('div','row-text'),sNode('p','row-title','Line '+row.line+': '+row.text),sNode('p','row-says',row.reason)))))):null;
  const posts=disclosure('The '+shown.links+' links',sAdd(sNode('ul','rows'),...shown.posts.map(post=>sAdd(sNode('li','row'),sAdd(sNode('div','row-text'),link(post.url,post.title||post.url),sNode('p','row-says',post.status==='in-library'?'Already in your library':'New'))))));
  const start=sButton('Import '+shown.links+(shown.links===1?' post':' posts'),button=>sVoiceLinksImport(found,profile,article,held,button,problem),'filled');
  const shared='Posts are saved as historical references in this workspace'+(access.status==='local-only'?'':' and shared like other references')+'.';
  sOpenSheet('Check before importing',sCard(shown.links+(shown.links===1?' post from ':' posts from ')+shown.shown_scope,sNode('p','',style?'Examples of '+shown.author:'By '+shown.author+(profile?' · for the voice '+profile.name:''))),notes,skipped,posts,
    sNode('p','quiet',shared+(style?'':' Where a page names its author, a post by someone else is listed for you to keep or leave out.')+' Nothing is analyzed yet.'),problem,start,back);
}
async function sVoiceLinksImport(found,profile,article,held,button,problem){
  const owner=studio.sheet,payload=()=>({operation:held.operation,text:held.text,author:held.author.trim(),site:held.site||null,expected:held.shown.expected,keep:held.keep,retry:held.retry,purpose:held.purpose});
  await busy(button,'Importing…',async()=>{try{let result=await api('voice-links-import',payload());held.retry=false;for(let turns=0;result.remaining>0&&turns<25&&studio.sheet===owner;turns++){button.textContent='Imported '+(result.links-result.remaining)+' of '+result.links+'…';result=await api('voice-links-import',payload());}held.result=result;if(studio.sheet===owner)sVoiceLinksResult(found,profile,article,held);}catch(error){held.retry=false;problem.textContent=error.message;}});
}
function sVoiceLinksWords(row,style=false){
  const byline=(row.byline||[]).join(', ');
  if(row.status==='failed')return 'Not imported: '+row.reason;
  if(row.status==='pending')return 'Not imported yet';
  const where=row.status==='in-library'?'Already in your library':'Imported';
  if(row.no_text)return where+' · no readable text, so not '+(style?'an example':'a sample');
  if(style)return where+' · example';
  if(row.kept)return where+' · byline '+byline+' · kept as a sample';
  if(row.mismatch)return where+' · byline names '+byline+', so it is left out';
  return where+' · voice sample'+(byline?' · byline '+byline:' · no byline on the page');
}
function sVoiceLinksResult(found,profile,article,held){
  const result=held.result,style=held.purpose==='style-sample',problem=sNode('p','problem');problem.setAttribute('role','alert');const keep=new Set(held.keep);
  const list=sNode('ul','rows');for(const row of result.results){const text=sAdd(sNode('div','row-text'),link(row.url,row.title||row.url),sNode('p','row-says',sVoiceLinksWords(row,style)));const item=sAdd(sNode('li','row'),text);if(!style&&row.mismatch&&!row.sample){const label=sNode('label','check'),box=sNode('input','');box.type='checkbox';box.checked=keep.has(row.url);box.addEventListener('change',()=>{if(box.checked)keep.add(row.url);else keep.delete(row.url);});label.append(box,sNode('span','','Keep as '+result.author+'’s sample'));text.append(label);}list.append(item);}
  const again=extra=>async button=>{Object.assign(held,extra());await sVoiceLinksImport(found,profile,article,held,button,problem);};
  const learn=!result.samples.length?null:style?sButton('Learn a style from these',async()=>sLearnStyle(await api('styles'),null,result.samples.slice(0,20),result.author),'filled'):sButton(profile?'Update '+profile.name+' from these samples':'Learn '+result.author+'’s voice',async()=>{const voices=await api('voices');studio.voiceLearning||={};studio.voiceLearning[profile?.id||'new']={name:profile?.name||result.author,samples:[...new Set([...(profile?.sample_ids||[]),...sKeptSamples(profile?.id||'new',result.author),...result.samples])].slice(0,20),background:null,operation:operationId()};sLearnVoice(voices,profile);},'filled');
  sOpenSheet(style?'Examples imported':'Published posts imported',sCard(result.counts.samples+' of '+result.links+(style?' posts are examples of '+result.author:' posts are '+result.author+'’s voice samples'),sNode('p','quiet',result.counts.imported+' imported · '+result.counts['in-library']+' already in your library · '+result.counts.failed+' failed'+(style?'':' · '+result.counts.mismatch+' by someone else')),result.sharing_message?sNode('p','quiet',result.sharing_message):null),list,
    !style&&result.counts.mismatch?sButton('Keep the ticked posts as samples',again(()=>({keep:[...keep]}))):null,
    !style&&result.counts.mismatch>1?sButton('Keep all '+result.counts.mismatch+' posts by someone else',again(()=>({keep:result.results.filter(r=>r.mismatch&&!r.sample).map(r=>r.url)}))):null,
    result.counts.failed?sButton('Try the failed links again',again(()=>({retry:true}))):null,
    sNode('p','',result.next_step),result.samples.length?sNode('p','quiet',style?'Style learning reads up to twenty examples; the first twenty are ticked for you. You confirm they may be analyzed, then review the provisional style before confirming it.':'Voice learning reads up to twenty samples; the first twenty are ticked for you. You confirm they may be analyzed, then audition the provisional voice before confirming it.'):null,
    problem,learn,sButton('All voices and styles',()=>sVoiceTools(article)));
}
async function sVoiceProfile(id,article){
  const found=await sTaskRead('Voice profile','voice?profile='+encodeURIComponent(id));if(!found)return;
  const problem=sNode('p','problem');problem.setAttribute('role','alert');
  sOpenSheet(found.name,sNode('p','quiet',`Revision ${found.revision} · ${found.status}`),sAdd(sNode('article','paper doc'),window.TrainingStudioMarkdown.render(found.guide)),
    sButton('Edit this voice guide',async()=>{const all=await api('voices');sEditVoice(found,all);}),
    sButton('Export voice guide',()=>sDownload({name:found.id+'-voice.md',content:found.guide})),
    sNode('p','quiet','Sample references: '+(found.sample_ids||[]).join(', ')),
    disclosure('Explicit author rules',sNode('pre','diff',JSON.stringify(found.rules||{},null,2))),
    sButton('Audition this voice',()=>sVoiceAudition(found)),
    found.status!=='retired'?sButton('Add published posts to this voice',async()=>sVoiceLinks(await api('voices'),found,article)):null,
    article&&found.status!=='retired'?sButton('Use this revision for this article',async button=>busy(button,'Selecting…',async()=>{try{await sApplyVoice(article,found);}catch(error){problem.textContent=error.message;}})):null,
    found.status!=='retired'?sButton('Retire this profile',()=>sOpenSheet('Retire this voice?',sNode('p','','It leaves future voice choices. Existing pinned articles and all profile revisions remain available.'),sButton('Retire it',async button=>busy(button,'Retiring…',async()=>{await api('tool-action',{action:'profile-retire',profile:id,expected:found.expected,confirmed:true});await sVoiceTools(article);})),sButton('Cancel',sCloseSheet))):null,
    problem,sButton('All voices and styles',()=>sVoiceTools(article)),sButton('Close',sCloseSheet));
}
// Changing a blog's voice is a decision: on a blog with an outline or a draft it is confirmed
// first, since its reviews will need a new look. Afterwards the editor reopens when that is
// where the change was made; otherwise the run opens when the blog has one.
function sHasWriting(found){return !!found.existing||(found.stages||[]).some(row=>['outline','draft'].includes(row.stage)&&['draft','approved','stale'].includes(row.status));}
async function sApplyVoice(article,profile,written=false){
  const from=studio.screen,current=await api('manuscript?id='+encodeURIComponent(article));
  const apply=async confirmed=>{const result=await api('tool-action',{action:'voice-apply',id:article,profile:profile.id,expected:current.expected,...(confirmed?{confirmed:true}:{})});sCloseSheet();sToast('This blog now writes as '+profile.name+'. Nothing was rewritten.');if(from==='editor')await sRoute('editor',article);else if(result.run)await sRoute('run',article,'status');};
  const ask=()=>{const problem=sNode('p','problem');problem.setAttribute('role','alert');sOpenSheet('Change this blog’s voice?',sNode('p','','It will write as '+profile.name+' · '+profile.status+'.'),sNode('p','','Its reviews will need a new look; nothing is rewritten.'),problem,sButton('Change to '+profile.name,async button=>busy(button,'Changing…',async()=>{try{await apply(true);}catch(error){problem.textContent=error.message;}}),'filled'),sButton('Cancel',sCloseSheet));};
  if(written||String(current.content||'').trim()){ask();return;}
  try{await apply(false);}catch(error){if(/Confirm the change of voice/.test(error.message)){ask();return;}throw error;}
}
async function sChangeVoice(found){
  const all=await sTaskRead('Change the voice','voices');if(!all)return;
  const profiles=all.profiles.filter(profile=>profile.status!=='retired');
  if(!profiles.length){sOpenSheet('Change the voice',sNode('p','','No voice is saved yet. Learn one first; this blog keeps its voice until you choose another.'),sButton('Open voices and styles',()=>sVoiceTools(found.id)),sButton('Cancel',sCloseSheet));return;}
  const held={profile:(profiles.find(profile=>profile.id===found.voice_profile)||profiles[0]).id};
  // The same voice at a newer revision is a change: the blog keeps the revision it pinned.
  const problem=sNode('p','problem');problem.setAttribute('role','alert');const chosen=()=>profiles.find(profile=>profile.id===held.profile);
  const use=sButton('Use this voice',button=>busy(button,'Changing…',async()=>{problem.textContent='';try{await sApplyVoice(found.id,chosen(),sHasWriting(found));}catch(error){problem.textContent=error.message;}}),'filled'),same=()=>{use.disabled=chosen().id===found.voice_profile&&chosen().revision===found.voice_revision;};same();
  sOpenSheet('Change the voice',sField('change-voice','Write as',held,'profile',{options:profiles.map(profile=>[profile.id,profile.name+' · '+profile.status]),hint:'Choosing a voice never rewrites what is already written. To write in no particular voice, ask in the conversation; it is not offered here.',changed:same}),problem,use,sButton('Cancel',sCloseSheet));
}
function sEditVoice(profile,all){
  studio.voiceEdits||={};const held=studio.voiceEdits[(profile.id||'new')+':'+(profile.expected||'')]||={name:profile.name,guide:profile.guide,status:profile.status==='confirmed'?'confirmed':'provisional',samples:[...(profile.sample_ids||[])],rules:JSON.stringify(profile.rules||{},null,2)},form=sNode('form'),problem=sNode('p','problem');problem.setAttribute('role','alert');
  form.append(sField('voice-name','Profile name',held,'name',{required:true,max:200}),sField('voice-guide','Voice guide',held,'guide',{long:true,max:40000,required:true}),sToolSamples(all,held),disclosure('Explicit author rules',sNode('p','quiet','These rules are separate from inferred style. Existing rules are preserved; use valid JSON with banished_words, banished_phrases, no_em_dashes or no_ascii_double_hyphen.'),sField('voice-rules','Author rules (JSON)',held,'rules',{long:true,max:40000})));
  const confirm=sNode('input');confirm.type='checkbox';const label=sNode('label','check');label.append(confirm,sNode('span','','I reviewed this guide and confirm it represents the intended author voice.'));form.append(label,problem);
  const save=confirmed=>async button=>busy(button,'Saving…',async()=>{try{if(confirmed&&!confirm.checked)throw new Error('Review and confirm the guide first.');const saved=await api('tool-action',{action:'profile-save',profile:profile.id||null,expected:profile.expected,name:held.name,guide:held.guide,rules:JSON.parse(held.rules),samples:held.samples,status:confirmed?'confirmed':'provisional',confirmed});await sVoiceTools();}catch(error){problem.textContent=error.message;}});
  sOpenSheet('Edit voice guide',form,sButton('Save provisional guide',save(false)),sButton('Confirm voice guide',save(true)),sButton('Cancel',sCloseSheet));
}
function sVoiceAudition(profile){
  studio.voiceAuditions||={};const held=studio.voiceAuditions[profile.id+':'+profile.revision]||={content:'',operation:operationId()},form=sNode('form'),problem=sNode('p','problem');problem.setAttribute('role','alert');form.append(sField('audition-text','Short passage to audition',held,'content',{long:true,max:10000,required:true}),problem);const submit=sNode('button','button','Generate audition');submit.type='submit';form.append(submit);
  form.addEventListener('submit',async event=>{event.preventDefault();submit.disabled=true;try{sToolJob(await api('tool-action',sTaskPayload(held,{action:'job-create',kind:'voice-audition',profile:profile.id,content:held.content,operation:held.operation})));}catch(error){problem.textContent=error.message;}finally{submit.disabled=false;}});sOpenSheet('Audition '+profile.name,form,sButton('Cancel',sCloseSheet));
}
function sRepurposeTool(id){
  studio.copyDrafts||={};const held=studio.copyDrafts[id]||={format:'linkedin',words:'150',audience:'',url:'',operation:operationId()},form=sNode('form'),problem=sNode('p','problem');problem.setAttribute('role','alert');
  form.append(sField('copy-format','Copy format',held,'format',{options:[['linkedin','LinkedIn feed copy'],['newsletter','Newsletter introduction'],['email','Announcement email'],['summary','Short summary'],['thread','Short thread']]}),sField('copy-reader','Reader (optional)',held,'audience',{max:2000}),sField('copy-words','Target words',held,'words',{type:'number',min:30,maximum:1500,required:true}),sField('copy-url','Actual article URL (optional)',held,'url',{max:2000}),sNode('p','quiet','Prepared copy only. Nothing is sent, posted or scheduled. Counts are editorial targets, not a claim about current platform limits.'),problem);
  const submit=sNode('button','button','Prepare channel copy');submit.type='submit';form.append(submit);form.addEventListener('submit',async event=>{event.preventDefault();submit.disabled=true;try{const draft=studio.editorDrafts?.[id];if(draft&&draft.content!==draft.baseContent)throw new Error('Save the source manuscript before preparing channel copy.');const job=await api('tool-action',sTaskPayload(held,{action:'job-create',kind:'repurpose',id,operation:held.operation,format:held.format,words:Number(held.words),audience:held.audience,url:held.url}));held.operation=operationId();sToolJob(job);}catch(error){problem.textContent=error.message;}finally{submit.disabled=false;}});sOpenSheet('Repurpose this blog',form,sButton('Cancel',sCloseSheet));
}
async function sToolJob(initial){
  studio.toolDrafts||={};const held=studio.toolDrafts[initial.id]||={content:null,name:'',confirmed:false};
  const paint=job=>{
    const problem=sNode('p','problem');problem.setAttribute('role','alert');const body=sNode('div');body.append(sNode('p','state',job.status==='ready'?'Ready for your review':job.status==='working'?'Working with your selected assistant':job.status));
    if(job.error)body.append(sNode('p','problem',job.error));
    if(job.source_changed)body.append(sNode('p','decision-notice','The source or its saved choices changed. Keep this result for comparison; regenerate before applying it.'));
    if(job.result){
      if(held.content===null)held.content=job.saved_content||job.result.content;
      const count=sNode('p','quiet'),counts=()=>{const words=(held.content.match(/[\p{L}\p{N}_]+(?:['’-][\p{L}\p{N}_]+)*/gu)||[]).length;count.textContent=`${words} words · ${Array.from(held.content).length} characters`+(job.metadata.words?` · requested about ${job.metadata.words} words`:'');};counts();
      body.append(sField('tool-result','Review and adjust the prepared text',held,'content',{long:true,max:200000,changed:counts}),count,sNode('p','quiet',job.result.notes||''),
        sButton('Copy prepared text',async()=>{if(!navigator.clipboard?.writeText)throw new Error('Select and copy the prepared text above.');await navigator.clipboard.writeText(held.content);sToast('Prepared text copied.');}),sButton('Download Markdown',()=>sDownload({name:(held.name||job.kind)+'.md',content:held.content})));
      if(job.kind==='repurpose')body.append(sField('variant-name','Name for this variant',held,'name',{max:80,hint:'A short ID such as launch-newsletter. Saved separately from the blog.'}));
      if(job.kind==='voice-learn')body.append(sNode('p','quiet','Generated voice guides stay provisional until you explicitly confirm them. No default changes automatically.'));
      if(job.kind==='style-learn')body.append(sNode('p','quiet','A learned style stays provisional until you confirm it. It describes a kind of writing, not a person.'));
      const apply=extra=>async button=>busy(button,'Saving…',async()=>{try{const saved=await api('tool-action',{action:'job-apply',job:job.id,id:job.metadata.article||null,content:held.content,name:held.name,...extra});if(job.kind.startsWith('interview-'))await sInterview(saved.id);else if(job.kind==='voice-learn'){if(sInBatch(job.id))await sVoicesBatch();else await sVoiceTools();}else if(job.kind==='style-learn')await sVoiceTools();else{sToast('Prepared copy saved. Nothing was posted.');await sMoreTools(saved.id);}}catch(error){problem.textContent=error.message;}});
      if(job.applied)body.append(sNode('p','quiet','This result was already saved. Create a new task for another variant or revision.'));
      else if(job.source_changed)body.append(sButton('Return to current source',()=>job.metadata.article?sMoreTools(job.metadata.article):sVoiceTools()));
      else if(job.kind==='style-learn')body.append(sButton('Save provisional style guide',apply({status:'provisional'})),sButton('Confirm this style guide',()=>sOpenSheet('Confirm this style?',sNode('p','','Confirm that you reviewed the guide and it describes the intended kind of writing. Existing blogs keep their pinned revision.'),sButton('Confirm and save',apply({status:'confirmed',confirmed:true})),sButton('Cancel',sCloseSheet))));
      else if(job.kind==='voice-learn')body.append(sButton('Save provisional voice guide',apply({status:'provisional'})),sButton('Confirm this voice guide',()=>sOpenSheet('Confirm this voice?',sNode('p','','Confirm that you reviewed the guide and it represents the intended author. This saves a confirmed profile; existing article pins stay unchanged.'),sButton('Confirm and save',apply({status:'confirmed',confirmed:true})),sButton('Cancel',sCloseSheet))));
      else if(job.kind!=='voice-audition')body.append(sButton(job.kind==='repurpose'?'Save named copy':job.kind==='interview-question'?'Continue with this question':'Save outline for review',apply({})));
    }else if(['queued','working'].includes(job.status))body.append(sButton('Cancel task',async()=>paint(await api('tool-action',{action:'job-control',job:job.id,control:'cancel'}))));
    if(['failed','cancelled'].includes(job.status)&&job.attempts<3)body.append(sButton('Retry task',async()=>paint(await api('tool-action',{action:'job-control',job:job.id,control:'retry'}))));
    body.append(problem);sOpenSheet({repurpose:'Prepared channel copy','voice-learn':'Learn an author voice','style-learn':'Learn a style','voice-audition':'Voice audition','interview-question':'Next interview question','interview-outline':'Interview outline'}[job.kind],body,sInBatch(job.id)?sButton('Back to every author',()=>sVoicesBatch()):null,sButton('Close',sCloseSheet));
    if(['queued','working'].includes(job.status)){const owner=studio.sheet;setTimeout(async()=>{if(studio.sheet!==owner)return;try{const next=await api('tool-job?job='+job.id);if(studio.sheet===owner)paint(next);}catch(error){if(studio.sheet===owner)problem.textContent=error.message+' Close and reopen the saved task to resume.';}},1000);}
  };paint(initial);
}
// Interview me: the interview's blog is written as the voice chosen here, with the same Write
// as a new blog has; the choice travels with the blog to the outline and the draft.
async function sNewInterview(){
  if(!studio.options)studio.options=await api('run-options');
  studio.interviewDraft||={title:'',audience:'',goal:'',profile:null,operation:operationId()};const held=studio.interviewDraft,form=sNode('form'),problem=sNode('p','problem');problem.setAttribute('role','alert');
  for(const [key,label]of [['title','Working title'],['audience','Who is it for?'],['goal','What should readers understand?']])form.append(sField('interview-'+key,label,held,key,{required:true,max:key==='title'?200:2000}));sAdd(form,sVoiceSelect(held,'interview-voice'));const submit=sNode('button','button','Start interview');submit.type='submit';form.append(problem,submit);form.addEventListener('submit',async event=>{event.preventDefault();submit.disabled=true;try{const {profile,...fields}=held;const found=await api('tool-action',{action:'interview-start',...fields,...sVoicePayload(held)});studio.interviewDraft=null;await sInterview(found.id);}catch(error){problem.textContent=error.message;}finally{submit.disabled=false;}});sOpenSheet('Interview me',form,sButton('Cancel',sCloseSheet));
}
async function sInterview(id){
  const found=await sTaskRead('Author interview','interview?id='+encodeURIComponent(id));if(!found)return;
  studio.interviewAnswers||={};const held=studio.interviewAnswers[id]||={answer:''},body=sNode('div'),form=sNode('form'),problem=sNode('p','problem');problem.setAttribute('role','alert');
  body.append(sNode('p','quiet','Answers are saved locally. Experience stays author-reported; evidence gaps are not filled with invented facts. Pause by closing and resume from this article’s tools.'));
  for(const answer of found.answers){const edit={answer:answer.answer},form=sNode('div');form.append(sField('answer-'+answer.id,'Revise this answer',edit,'answer',{long:true,max:12000}),sButton('Save revised answer',async button=>busy(button,'Saving…',async()=>{await api('tool-action',{action:'interview-answer',id,expected:found.expected,question_id:answer.id,answer:edit.answer,skip:!edit.answer.trim()});await sInterview(id);})));body.append(disclosure(answer.question,sNode('p','',answer.answer||'(Skipped)'),form));}
  form.append(sNode('h3','',found.question),sField('interview-answer','Your answer',held,'answer',{long:true,max:12000}),problem);const submit=sNode('button','button','Save answer');submit.type='submit';form.append(submit);
  const save=skip=>async button=>busy(button,'Saving…',async()=>{try{await api('tool-action',{action:'interview-answer',id,expected:found.expected,answer:held.answer,skip});held.answer='';await sInterview(id);}catch(error){problem.textContent=error.message;}});form.addEventListener('submit',async event=>{event.preventDefault();await save(false)(submit);});
  const generate=kind=>async button=>busy(button,'Starting…',async()=>{try{sToolJob(await api('tool-action',{action:'job-create',id,kind,operation:operationId()}));}catch(error){problem.textContent=error.message;}});
  body.append(form,sButton('Skip this question',save(true)),sButton('Ask a focused next question',generate('interview-question')),sButton('I have enough — prepare an outline',generate('interview-outline')));
  // The outline the interview prepared starts a new blog on the desk, written from it.
  if(found.outline)body.append(sButton('Review outline and start a draft',()=>{sCloseSheet();return sDeskBegin({have:'outline',outlineFrom:'paste',outlineWay:'outline',outline:found.outline_content||'',title:found.title||''});}));
  sOpenSheet(found.title+' · Interview',body,sButton('Pause interview',sCloseSheet));
}

async function sVariants(id){
  const found=await sTaskRead('Saved channel copies','variants?id='+encodeURIComponent(id));if(!found)return;
  const body=sNode('div');for(const variant of found.variants)body.append(sButton('Open '+variant.name,()=>sVariant(id,variant.name)));
  sOpenSheet('Saved channel copies',body,found.variants.length?null:sNode('p','','No named copy variants yet.'),sButton('Prepare another variant',()=>sRepurposeTool(id)),sButton('Close',sCloseSheet));
}
async function sVariant(id,name){
  const found=await sTaskRead('Saved channel copy','variant?'+new URLSearchParams({id,name}));if(!found)return;
  studio.variantEdits||={};const key=id+':'+name;let held=studio.variantEdits[key];
  if(!held||held.content===held.baseContent)held=studio.variantEdits[key]={expected:found.expected,content:found.content,baseContent:found.content};
  let blocked=held.expected!==found.expected;const body=sNode('div'),problem=sNode('p','problem');problem.setAttribute('role','alert');
  body.append(sNode('p','quiet',found.provenance.format+' · source '+found.provenance.source_sha256.slice(0,12)),found.source_changed?sNode('p','decision-notice','The source manuscript has changed since this copy was prepared. These edits keep the original provenance.'):sNode('p','quiet','Saved separately from the manuscript. Nothing is posted.'),sField('saved-copy-text','Prepared copy',held,'content',{long:true,max:200000}));
  const save=sButton('Save this copy locally',async button=>busy(button,'Saving…',async()=>{try{await api('tool-action',{action:'variant-save',id,name,expected:held.expected,content:held.content});held.baseContent=held.content;await sVariant(id,name);}catch(error){problem.textContent=error.message;}}));save.disabled=blocked;
  if(blocked)body.append(sNode('p','decision-notice','This copy changed. Your proposed text is kept. Compare the latest text before resubmitting.'),disclosure('Latest saved text',sNode('pre','diff',found.content)),sButton('Keep my text for resubmission',()=>{held.expected=found.expected;blocked=false;save.disabled=false;problem.textContent='Latest base selected. Review your text, then save it explicitly.';}));
  sOpenSheet(name,body,problem,save,sButton('Download Markdown',()=>sDownload({name:name+'.md',content:held.content})),sButton('All channel copies',()=>sVariants(id)),sButton('Close',sCloseSheet));
}
function sTaskPayload(held,data){const signature=JSON.stringify({...data,operation:undefined});if(held.requestSignature!==signature){held.operation=operationId();held.requestSignature=signature;}return {...data,operation:held.operation};}
async function sGoogleCompare(id){
  const current=await sTaskRead('Compare Google and local text','manuscript?id='+encodeURIComponent(id));if(!current)return;
  const held=studio.editorDrafts?.[id];if(held&&held.content!==held.baseContent){sOpenSheet('Save your edits first',sNode('p','','Save or copy your unsaved manuscript edits before comparing Google.'),sButton('Close',sCloseSheet));return;}
  const problem=sNode('p','problem');problem.setAttribute('role','alert');sOpenSheet('Checking the linked Google Doc',sNode('p','','Reading accepted text, formatting and pending review state. Nothing is sent to Google.'),problem,sButton('Cancel',sCloseSheet));const owner=studio.sheet;
  try{const found=await api('tool-action',{action:'google-compare',id,expected:current.expected});if(studio.sheet!==owner)return;
    const draft={resolution:found.resolution||found.local},review=sNode('div');review.append(sNode('p','quiet','These previews show text only. Saved image references are preserved.'),disclosure('Saved common baseline',sNode('pre','diff',found.baseline_preview||'(Unavailable on this computer)')),disclosure('Local manuscript',sNode('pre','diff',found.local_preview)),disclosure('Accepted Google text',sNode('pre','diff',found.remote_preview)));
    if(found.status==='conflict')review.append(sField('google-resolution','Review the combined local text',draft,'resolution',{long:true,max:200000,hint:'Choose the wording in every marked conflict; keep Google-only edits unless you explicitly decide to drop them.'}));
    const discard=sNode('input');discard.type='checkbox';const label=sNode('label','check');label.append(discard,sNode('span','','I explicitly chose to drop Google-only passages in my resolution.'));
    const save=sButton('Accept compared text locally',async button=>busy(button,'Checking and saving…',async()=>{try{await api('tool-action',{action:'google-accept',id,expected:found.expected,preview:found.preview,comparison:found.comparison,confirmed:true,...(found.status==='conflict'?{resolution:draft.resolution,discard_remote:discard.checked}:{})});delete studio.editorDrafts?.[id];sCloseSheet();await sRoute('editor',id);sToast('Compared text saved locally. Nothing was written to Google.');}catch(error){problem.textContent=error.message;}}));save.disabled=found.has_proposals;
    sOpenSheet('Compare Google and local text',sNode('p','state',found.status.replaceAll('-',' ')),sNode('p','quiet','Google account: '+(found.account||'current configured account')+'. Pending suggestions stay under the author’s control. This accepts only the compared local text; it sends no edits, resolves no comments and makes no approval decision.'),found.has_proposals?sNode('p','decision-notice','Review or clear saved wording suggestions before accepting a new baseline. They are kept.'):null,review,found.status==='conflict'?label:null,problem,save,sButton('Compare again',()=>sGoogleCompare(id)),sButton('Cancel',sCloseSheet));
  }catch(error){if(studio.sheet===owner)problem.textContent=error.message;}
}

function sPlanning(){
  studio.planningDraft||={topic:''};const held=studio.planningDraft,form=sNode('form'),problem=sNode('p','problem');problem.setAttribute('role','alert');form.append(sField('planning-topic','Proposed topic',held,'topic',{required:true,max:500}),sNode('p','quiet','Searches this workspace’s active readable references. Historical matches are leads to inspect, not current factual evidence.'),problem);const submit=sNode('button','button','Find related posts');submit.type='submit';form.append(submit);
  form.addEventListener('submit',async event=>{event.preventDefault();submit.disabled=true;const owner=studio.sheet;try{const result=await api('planning?'+new URLSearchParams({topic:held.topic}));if(studio.sheet!==owner)return;const list=sNode('div');for(const item of result.items)list.append(sCard(item.title,sNode('p','quiet',item.author||'Unknown author'),item.origin?.startsWith('https://')?link(item.origin,'Read original ↗'):sNode('p','quiet','Read this saved source in the reference library.')));sOpenSheet('Related topic leads',result.items.length?list:sNode('p','','No matches for this exact local search.'),sNode('p','quiet',result.next_step),sButton('Search another topic',sPlanning),sButton('Close',sCloseSheet));}catch(error){if(studio.sheet===owner)problem.textContent=error.message;}finally{submit.disabled=false;}});sOpenSheet('Check topic overlap',form,sButton('Cancel',sCloseSheet));
}

function sSamePassage(left,right){return left.kind==='edit'&&right.kind==='edit'&&left.before===right.before&&(left.context||'')===(right.context||'');}

// The finish: a finished run's Done card, deleting with the typed title, what was recently
// deleted, and the ideas a gate offers as picks.
function sDoneCard(found){
  // The draft is a stage of a written blog; a reviewed or revised manuscript is read as one.
  const read=async()=>{if((found.stages||[]).some(row=>row.stage==='draft')){const shown=await api('run-file?'+new URLSearchParams({id:found.id,stage:'draft'}));return {content:shown.content,name:shown.name||'DRAFT.md'};}const manuscript=await api('manuscript?id='+encodeURIComponent(found.id));return {content:manuscript.content,name:'DRAFT.md'};};
  const held={url:''},problem=sNode('p','problem');problem.setAttribute('role','alert');
  const copy=sButton('Copy Markdown',async()=>{const shown=await read();if(typeof navigator==='undefined'||!navigator.clipboard?.writeText)throw new Error('Download the draft and copy it from there.');await navigator.clipboard.writeText(shown.content);sToast('Markdown copied.');});
  const download=sButton('Download',async()=>sDownload(await read()));
  const publish=sButton('Mark as published',async button=>{const url=held.url.trim();if(!/^https:\/\/\S+$/.test(url)){problem.textContent='Add the public https address where it was published.';return;}await busy(button,'Saving…',async()=>{try{const detail=await api('article?'+new URLSearchParams({id:found.id,location:'local'}));await api('schedule',{id:found.id,expected:detail.expected,stage:'published',confirm_stage:true,publication_url:url});sToast('Recorded as published. Nothing was posted anywhere.');const updated=await api('run?id='+encodeURIComponent(found.id));if(studio.screen==='run'&&studio.id===found.id)sRun(updated);}catch(error){problem.textContent=error.message;}});});
  publish.disabled=!sCanEdit(found);
  const prepublish=sButton('Pre-publish check',()=>sPrepublishTool(found.id));prepublish.disabled=!sCanEdit(found);
  const repurpose=sButton('Repurpose',()=>sRepurposeTool(found.id));repurpose.disabled=!sCanEdit(found);
  const pendingWords='The existing Google Doc is kept. Inspect it, then check it again after reconciling its content with the approved draft. No second Doc is made.';
  const google=found.google?.url?link(found.google.url,'Open the Google Doc ↗'):sButton(found.google_pending?.url?'Check the existing Google Doc':'Open as a Google Doc',()=>{
    const error=sNode('p','sheet-error');error.setAttribute('role','alert');
    const intro=sNode('p','',found.google_pending?.url?pendingWords:'This makes a new Google Doc of the approved draft in your Google Drive, private to you. Nothing is shared.');
    if(found.google_pending?.url)error.append(link(found.google_pending.url,'Inspect the existing Google Doc ↗'));
    sOpenSheet(found.google_pending?.url?'Check the existing Google Doc?':'Open as a Google Doc?',intro,error,
      sAdd(sNode('div','bar'),sButton(found.google_pending?.url?'Check the existing Google Doc':'Make the Google Doc',async button=>busy(button,'Checking…',async()=>{
        try{const result=await api('google-open',{id:found.id,expected:found.expected,confirmed:true});found.google={url:result.url};sCloseSheet();sToast('The private Google Doc is ready.');if(studio.screen==='run'&&studio.id===found.id)sRun(found);}catch(failure){
          error.textContent=failure.message;
          try{const latest=await api('run?id='+encodeURIComponent(found.id));if(latest.google_pending?.url){found.google_pending=latest.google_pending;found.expected=latest.expected;intro.textContent=pendingWords;button.textContent='Check the existing Google Doc';error.append(link(latest.google_pending.url,'Inspect the existing Google Doc ↗'));}}catch(readFailure){/* The original failure remains visible; the durable receipt is kept. */}
        }
      }).then(()=>{if(found.google_pending?.url&&!found.google?.url)button.textContent='Check the existing Google Doc';}),'filled'),sButton('Cancel',sCloseSheet)));
  });
  if(!found.google?.url)google.disabled=!sCanEdit(found);
  const remove=sButton('Delete this blog',()=>sDeleteSheet(found),'danger');remove.disabled=!sCanEdit(found);
  // Finish keeps the blog in the team library; the card says so, or why not.
  const kept=found.library?.id?sNode('p','quiet','Kept in the team library, where the next blog can pick it as an example.'):found.library?.reason?sNode('p','quiet','Not kept in the team library: '+found.library.reason):null;
  // A finished blog opens on the writing desk for further editing; the run stays readable here.
  const desk=found.desk_open?sButton('Open on the desk',async button=>{await busy(button,'Opening…',async()=>{try{const made=await api('desk-open',{id:found.id});studio.desk={id:made.id,view:made,session:operationId()};await sRoute('desk',made.id);}catch(error){problem.textContent=error.message;}});},'filled'):null;
  if(desk)desk.disabled=!sCanEdit(found);
  return sCard('Done',sNode('p','',found.publication?'Published at '+found.publication:'The draft is approved. Take it where it goes, then say where it was published.'),kept,found.publication?link(found.publication,'Open the published blog ↗'):null,desk?sAdd(sNode('div','bar'),desk,sNode('span','quiet','Notes per section, selection edits and versions.')):null,
    sAdd(sNode('div','bar'),copy,download,google,prepublish,repurpose,sButton('Polish or edit the draft',()=>sRoute('editor',found.id))),
    found.publication?null:sAdd(sNode('div'),sField('published-url','Where was it published?',held,'url',{type:'url',max:2000,hint:'The public https address. Recording it posts nothing.'}),publish),
    problem,sAdd(sNode('div','bar'),remove));
}
// The same match the server makes. The page may be stricter for a few letters (ß, final ς): it lower-cases where the server case-folds, so it never enables Delete for a title the server refuses.
function sPlainTitle(value){return value.normalize('NFKC').replace(/[‘’‚]/g,"'").replace(/[“”„]/g,'"').replace(/[–—]/g,'-').replace(/\s+/g,' ').trim().toLowerCase();}
function sDeleteSheet(found){
  const title=found.title||'this blog',running=['working','queued'].includes(found.status),held={title:''},problem=sNode('p','sheet-error');problem.setAttribute('role','alert');
  const matches=()=>sPlainTitle(held.title)===sPlainTitle(title);
  const confirm=sButton('Delete '+title,async button=>{if(!matches())return;await busy(button,'Deleting…',async()=>{try{const expected=found.expected||(await api('article?'+new URLSearchParams({id:found.id,location:'local'}))).expected;const result=await api('blog-delete',{id:found.id,expected,title:held.title.trim()});sCloseSheet();studio.found=null;sToast('Deleted '+title+'.'+(result?.notice?' '+result.notice:''));await sRoute(studio.screen==='home'?'home':'blogs');}catch(error){problem.textContent=error.message+(/deleted/.test(error.message)?'':' Nothing was deleted.');}});},'danger');confirm.disabled=true;
  const hint=sNode('p','quiet field-hint','Not the title yet.');hint.id='delete-title-hint';hint.hidden=true;
  const field=sField('delete-title','Type the title to confirm',held,'title',{required:true,max:500,changed:()=>{const same=matches();confirm.disabled=!same;hint.hidden=same||!held.title.trim();}});field.children[1].setAttribute('aria-describedby',hint.id);field.append(hint);
  const goes=[running?'What’s running will stop, and nothing more of it is kept.':null,'It leaves your lists, and its folder goes'+(found.team?' from the team repository as one recorded change.':'.'),'What only this computer kept for it: its run state, receipts and tool jobs.'].filter(Boolean);
  sOpenSheet('Delete '+title+'?',running?sStatus('late','It is working now. What’s running will stop.'):null,
    sNode('h3','sheet-part','What goes'),sAdd(sNode('ul',''),...goes.map(words=>sNode('li','',words))),
    sNode('h3','sheet-part','What stays'),sAdd(sNode('ul',''),sNode('li','','It is kept for 30 days under Recently deleted on the Blogs page, where Restore brings it back.'),sNode('li','','Anything published elsewhere, or shared with a Team Hub, is not touched.')),
    field,problem,sAdd(sNode('div','bar'),confirm,sButton('Cancel',sCloseSheet)));
}
function sDeletedFold(){
  const rows=studio.deleted||[];if(!rows.length)return null;const list=sNode('ul','rows');
  for(const row of rows){const restore=sButton('Restore',async button=>{await busy(button,'Restoring…',async()=>{const result=await api('blog-restore',{id:row.id});sToast('Restored '+(result.title||row.title)+'. It stays stopped until you resume it.');await sRoute('run',row.id,'status');});});restore.disabled=!access.actions.edit;
    list.append(sAdd(sNode('li','row'),sAdd(sNode('div','row-text'),sNode('h3','row-title',row.title),sNode('p','quiet','Deleted '+new Date(row.deleted_at).toLocaleDateString()+' · kept until '+new Date(row.until).toLocaleDateString())),restore));}
  return disclosure('Recently deleted ('+rows.length+')',sNode('p','quiet','A deleted blog is kept for 30 days, then let go of.'),list);
}
// Add to the library: files, a list of links and a Google Doc in one sheet, with their role,
// author (one name, none, or each post's own) and kind of post. With each post's own author
// the posts are imported first, since a byline is read from the fetched page, and the result
// groups them by author to rename, merge or complete, mark as voice samples and learn from.
function sLibraryAddHeld(){return studio.libraryAdd||={files:[],links:'',file:'',google:'',role:'facts',who:'*each',author:'',kind:'',operation:operationId(),shown:null,result:null,mark:true};}
function sLibraryAddPayload(held){const files=[...held.files];if(held.google.trim())files.push({google:held.google.trim()});return {files,links:held.links,role:held.role,author:held.who==='named'?held.author.trim():held.who,kind:held.kind};}
async function sLibraryAdd(){
  const held=sLibraryAddHeld(),form=sNode('form'),problem=sNode('p','problem');problem.setAttribute('role','alert');let kinds={styles:[]};try{kinds=await api('styles');}catch(error){problem.textContent=error.message;}
  const forget=()=>{held.shown=null;};
  const box=sNode('div','field'),label=sNode('label','field-label','Files'),input=sNode('input','input');input.type='file';input.multiple=true;input.accept='.md,.txt,.html,.htm,.docx,.pdf';input.id='library-add-files';label.htmlFor=input.id;
  input.addEventListener('change',async()=>{const chosen=[...(input.files||[])];if(!chosen.length)return;if(chosen.some(file=>file.size>10*1024*1024)){problem.textContent='Choose files up to 10 MiB each.';return;}if(chosen.length>20){problem.textContent='Add up to 20 files at once.';return;}held.files=[];for(const file of chosen)held.files.push({filename:file.name,content:await encodeImportFile(file)});forget();await sLibraryAdd();});
  box.append(label,input,sNode('p','quiet field-hint',held.files.length?held.files.length+' chosen: '+held.files.map(file=>file.filename).join(', '):'Markdown, text, HTML, Word or PDF: up to 20 files of 10 MiB each.'));
  const linksBox=sNode('div','field'),linksLabel=sNode('label','field-label','Text file of links'),linksInput=sNode('input','input');linksInput.type='file';linksInput.accept='.txt,text/plain';linksInput.id='library-add-links-file';linksLabel.htmlFor=linksInput.id;
  linksInput.addEventListener('change',async()=>{const file=linksInput.files?.[0];if(!file)return;if(file.size>256*1024){problem.textContent='Choose a text file up to 256 KiB.';return;}try{held.links=await file.text();}catch(error){problem.textContent='This file could not be read as text.';return;}held.file=file.name;forget();await sLibraryAdd();});
  linksBox.append(linksLabel,linksInput,sNode('p','quiet field-hint',held.file?'Read '+held.file+'. You can still edit the links below.':'One link per line. Links from several sites are fine: each site is read in its own scope.'));
  sAdd(form,sNode('p','','Each post’s text, title, author and date are read and kept in the team library. Nothing is analyzed.'),
    sCreateStep(1,'What to add',box,linksBox,sField('library-add-links','Or paste the links',held,'links',{long:true,max:262144,changed:forget}),
      sField('library-add-google','Google Doc link (optional)',held,'google',{max:2000,hint:'Read with this computer’s Google sign-in, so the Doc does not need to be shared.',changed:forget})),
    sCreateStep(2,'What they are',sChoice('Use these as',[['facts','Facts (may be quoted)'],['messaging','Approved messaging (the product’s own claims)'],['example','Example of the kind of post']],held,'role',forget),
      sField('library-add-who','Author',held,'who',{options:[['*each','Each post’s own author'],['named','One author'],['','No author']],hint:'Each post’s own author reads the byline of every fetched page; the posts are then grouped by author for you to check.',changed:()=>{forget();return sLibraryAdd();}}),
      held.who==='named'?sField('library-add-author','Whose writing is this?',held,'author',{required:true,max:200,changed:forget}):null,
      sField('library-add-kind','Kind of post',held,'kind',{options:[['','No particular kind of post'],...(kinds.styles||[]).filter(style=>style.status!=='retired').map(style=>[style.id,style.name+(style.kind==='seed'?' (starter)':'')])],changed:forget})),problem);
  const submit=sNode('button','button button-filled','Check these items');submit.type='submit';form.append(sAdd(sNode('div','bar create-foot'),submit,sButton('Cancel',sCloseSheet)));
  // The larger sources keep their own previews: a whole blog, site, feed or export, and one
  // file with the upload's extra choices.
  const more=sAdd(sNode('ul','rows more-ways'),
    sAdd(sNode('li','row'),sAdd(sNode('div','row-text'),sNode('h3','row-title','A whole blog, site or feed'),sNode('p','row-says','A folder, website archive, RSS or Atom feed, sitemap or JSON export, previewed before anything is saved.')),sButton('Import a blog or site',()=>{sCloseSheet();openImport();})),
    sAdd(sNode('li','row'),sAdd(sNode('div','row-text'),sNode('h3','row-title','One file, summarized and tagged'),sNode('p','row-says','Summarize and tag it with your analysis CLI, or start an editable blog from it.')),sButton('Upload one file',()=>{sCloseSheet();openUpload();})));
  form.append(sNode('h3','sheet-part','More ways to add'),more);
  form.addEventListener('submit',async event=>{event.preventDefault();if(!held.files.length&&!held.links.trim()&&!held.google.trim()){problem.textContent='Choose files, paste links or add a Google Doc link first.';return;}if(held.who==='named'&&!held.author.trim()){problem.textContent='Name the author, or choose each post’s own author.';return;}await busy(submit,'Checking…',async()=>{try{const shown=await api('library-add-preview',sLibraryAddPayload(held));if(held.shown?.expected!==shown.expected){held.operation=operationId();held.result=null;}held.shown=shown;sLibraryAddPreview(held);}catch(error){problem.textContent=error.message;}});});
  sOpenSheet('Add to the library',form);
}
function sLibraryAddItemWords(item){const by=(item.bylines||[]).length?' · byline '+item.bylines.join(', '):'';if(item.kind==='link')return (item.state==='in-library'?'Already in the library':'New · fetched from '+item.site)+by;return (item.link?'Google Doc · ':'')+(item.state==='ready'?item.chars.toLocaleString('en-US')+' characters':'Needs text · '+(item.note||''))+by;}
function sLibraryAddPreview(held){
  const shown=held.shown,problem=sNode('p','problem');problem.setAttribute('role','alert');
  const list=sNode('ul','rows');for(const item of shown.items)list.append(sAdd(sNode('li','row'),sAdd(sNode('div','row-text'),item.url?link(item.url,item.title||item.url):sNode('h3','row-title',item.filename||item.title),sNode('p','row-says',sLibraryAddItemWords(item)))));
  const notes=[];if(shown.in_library)notes.push(shown.in_library+' already in the library: reused, not fetched again.');if(shown.to_fetch)notes.push(shown.to_fetch+(shown.to_fetch===1?' new page is':' new pages are')+' fetched once'+(shown.sites.length?' from '+shown.sites.map(site=>site.shown).join(', '):'')+'.');if(shown.duplicates)notes.push(shown.duplicates+' repeated links are counted once.');if(shown.unusable)notes.push(shown.unusable+' lines are not usable links.');
  const who=shown.author==='*each'?'Each post’s own author':shown.author||'No author',count=shown.items.length+(shown.items.length===1?' item':' items');
  const start=sButton('Add '+count,button=>sLibraryAddSave(held,button,problem),'filled');
  sOpenSheet('Check before adding',sCard(count,sNode('p','',(shown.role==='example'?'Example of the kind of post':shown.role==='messaging'?'Approved messaging':'Facts')+' · '+who+(shown.kind_name?' · '+shown.kind_name:''))),notes.length?sAdd(sNode('ul','rows'),...notes.map(words=>sAdd(sNode('li','row'),sNode('p','row-says',words)))):null,list,sNode('p','quiet','Nothing is analyzed. With a Team Hub selected, the items are shared like other references.'),problem,start,sButton('Change the items',sLibraryAdd));
}
// `retry` fetches the links that failed once more, on the first request only; nothing else is fetched twice.
async function sLibraryAddSave(held,button,problem,retry=false){
  const owner=studio.sheet,payload=()=>({...sLibraryAddPayload(held),operation:held.operation,expected:held.shown.expected});
  await busy(button,retry?'Trying again…':'Adding…',async()=>{try{let result=await api('library-add',{...payload(),...(retry?{retry:true}:{})});for(let turns=0;result.remaining>0&&turns<40&&studio.sheet===owner;turns++){button.textContent='Added '+(result.items.length-result.remaining)+' of '+result.items.length+'…';result=await api('library-add',payload());}held.result=result;if(studio.screen==='editorial')load().catch(()=>{});if(studio.sheet===owner)sLibraryAddResult(held);}catch(error){problem.textContent=error.message;}});
}
function sLibraryAddResult(held){
  const result=held.result,problem=sNode('p','problem');problem.setAttribute('role','alert');
  const again=async(route,data)=>{try{held.result=await api(route,{operation:held.operation,...data});if(studio.screen==='editorial')load().catch(()=>{});sLibraryAddResult(held);}catch(error){problem.textContent=error.message;}};
  const list=sNode('ul','rows');for(const item of result.items)list.append(sAdd(sNode('li','row'),sAdd(sNode('div','row-text'),item.url?link(item.url,item.title||item.url):sNode('h3','row-title',item.filename||item.title),sNode('p','row-says',item.status==='failed'?'Not added: '+item.reason:item.status==='pending'?'Not added yet':(item.status==='in-library'?'Already in the library':'Added')+(item.author?' · by '+item.author:'')+(item.sample?' · voice sample':'')))));
  const names=result.groups.map(group=>group.author),groups=sNode('div');
  result.groups.forEach((group,n)=>{const edit={name:group.author,into:names.find(name=>name!==group.author)||''};groups.append(sCard(group.author+' · '+group.count+(group.count===1?' post':' posts'),
    sAdd(sNode('div','bar'),sField('library-add-rename-'+n,'Rename this author',edit,'name',{max:200,short:true}),sButton('Rename',()=>edit.name.trim()&&edit.name.trim()!==group.author?again('library-add-author',{ids:group.ids,author:edit.name.trim()}):null)),
    names.length>1?sAdd(sNode('div','bar'),sField('library-add-merge-'+n,'Merge into',edit,'into',{options:names.filter(name=>name!==group.author).map(name=>[name,name])}),sButton('Merge',()=>edit.into?again('library-add-author',{ids:group.ids,author:edit.into}):null)):null,
    !sVoicesOn()?null:group.learnable.length?sButton('Learn '+group.author+'’s voice',async()=>{const voices=await api('voices');studio.voiceLearning||={};studio.voiceLearning.new={name:group.author,samples:[...group.learnable],background:null,operation:operationId()};sLearnVoice(voices,null);},'filled'):sNode('p','quiet','Not voice samples yet.')));});
  const held_=sNode('div');for(const item of result.held){const who={author:''};held_.append(sCard(item.title||item.url||'Untitled',sNode('p','quiet',item.reason+' It is a reference, counted for nobody.'),sAdd(sNode('div','bar'),sField('library-add-held-'+item.id,'Whose post is this?',who,'author',{max:200,short:true}),sButton('Set author',()=>who.author.trim()?again('library-add-author',{ids:[item.id],author:who.author.trim()}):null))));}
  const unmarked=result.groups.some(group=>group.samples.length<group.count),mark=sButton('Mark as samples',()=>again('library-add-samples',{}),'filled');mark.disabled=!held.mark;
  const samples=unmarked&&sVoicesOn()?sAdd(sNode('div'),sCheck('library-add-mark','Mark the posts as voice samples by their authors',held,'mark','On, every post in a named group becomes that author’s voice sample, in a new source revision that changes no blog. Held posts stay references.',on=>{mark.disabled=!on;}),mark):null;
  const retry=result.counts.failed&&held.shown?sButton('Try the failed links again',button=>sLibraryAddSave(held,button,problem,true)):null;
  sOpenSheet('Added to the library',sCard(result.counts.imported+' added · '+result.counts['in-library']+' already there · '+result.counts.failed+' failed',sNode('p','quiet',result.sharing_message||''),sNode('p','',result.next_step),retry),list,result.groups.length?sNode('h3','sheet-part','By author'):null,result.groups.length&&sVoicesOn()?sAdd(sNode('div','bar'),sButton('Create voices for every author',()=>sVoicesForAuthors())):null,groups,result.held.length?sNode('h3','sheet-part','Held: no single byline'):null,held_,samples,problem,sButton('Add more',()=>{studio.libraryAdd=null;sLibraryAdd();}),sButton('Close',sCloseSheet));
}
// The library screen's selection: learn a style or a voice from the ticked items, or start a
// blog with them as examples. Learning marks them as samples first, then opens the learn sheet,
// which still asks for permission before any analysis.
async function sLibrarySelection(action,ids,author=null){
  if(!ids.length)throw new Error('Tick some library items first.');
  if(ids.length>LIBRARY_SELECTION_LIMIT)throw new Error('A selection holds at most '+LIBRARY_SELECTION_LIMIT+' items, and '+ids.length+' are ticked. Clear some first.');
  if(action==='blog'&&ids.length>50)throw new Error('A blog takes up to 50 examples, and '+ids.length+' are ticked. Clear some, or learn a voice or a style from them.');
  let result;
  try{result=await api('library-selection',{action,ids,...(author?{author}:{})});}
  catch(error){if(action!=='voice-learn'||author!==null||!/whose writing/.test(error.message))throw error;
    const held={author:''},problem=sNode('p','problem'),form=sNode('form'),go=sNode('button','button button-filled','Continue');problem.setAttribute('role','alert');go.type='submit';
    form.append(sField('library-voice-author','Whose writing are these?',held,'author',{required:true,max:200,hint:'Items without an author become this author’s voice samples, but only once you confirm the learning. An item by someone else is not.'}),problem,go);
    form.addEventListener('submit',async event=>{event.preventDefault();if(!held.author.trim())return;await busy(go,'Checking…',async()=>{try{await sLibrarySelection(action,ids,held.author.trim());}catch(failure){problem.textContent=failure.message;}});});
    sOpenSheet('Learn a voice from these',form,sButton('Cancel',sCloseSheet));return;}
  if(action==='blog'){librarySelection.clear();await sDeskBegin({files:result.files.map(file=>({...file,note:'',link:'',kept:true}))});return;}
  // Nothing is marked yet: the learn sheet shows the items ticked, and marks them when confirmed.
  const words=[result.left_out?.length?sSeries(result.left_out.map(item=>item.name))+(result.left_out.length===1?' is':' are')+' left out: a learning reads up to twenty.':'',result.skipped?.length?sSeries(result.skipped.map(item=>item.name))+(result.skipped.length===1?' has':' have')+' no readable text yet, so '+(result.skipped.length===1?'it is':'they are')+' skipped.':''].filter(Boolean).join(' '),ids_=result.candidates.map(item=>item.id);
  if(action==='style-learn'){sLearnStyle(await api('styles'),null,ids_,'',result.candidates,words);return;}
  sLearnVoice(await api('voices'),null,ids_,null,result.author,result.candidates,words);
}
// Create voices for every author: each author in the team library with their posts. Two
// readable posts make a voice, so an author with fewer is listed, unticked, with the reason;
// an author who has a voice gets a new provisional revision of it. One permission for the
// batch queues one learning job per ticked author; the sheet then follows each job.
// Authors whose voice from an earlier batch on this page is still waiting or being learned.
function sQueuedAuthors(){return new Set([...(studio.voiceBatch?.jobs||[]),...(studio.voicesQueued?.jobs||[])].filter(row=>['queued','working'].includes(row.job.status)).map(row=>row.author));}
function sInBatch(ident){return !!studio.voiceBatch?.jobs?.some(row=>row.job.id===ident);}
async function sVoicesForAuthors(listing=null){
  if(!listing&&studio.voiceBatch?.jobs?.length)return sVoicesBatch();
  const found=listing||await sTaskRead('Create voices for every author','library-authors');if(!found)return;
  // An earlier batch's jobs are read again, so an author whose learning finished can be ticked.
  for(const row of studio.voicesQueued?.jobs||[])if(['queued','working'].includes(row.job.status)){try{row.job=await api('tool-job?job='+row.job.id);}catch(error){/* shown as it was */}}
  // A batch names at most the server's limit: the first that many ready authors are ticked.
  const most=found.batch_limit||100,queued=sQueuedAuthors(),ready=found.authors.filter(row=>row.ready&&!queued.has(row.author));
  const held={operation:operationId(),ticked:new Set(ready.slice(0,most).map(row=>row.author))};
  const form=sNode('form','create-flow'),problem=sNode('p','problem'),list=sNode('ul','rows author-rows');problem.setAttribute('role','alert');
  const submit=sNode('button','button button-filled','Create voices');submit.type='submit';
  const words=()=>{const chosen=found.authors.filter(row=>held.ticked.has(row.author)),fresh=chosen.filter(row=>!row.profile).length,updates=chosen.length-fresh;
    if(chosen.length>most){submit.textContent='Tick at most '+most+' authors';submit.disabled=true;return;}
    submit.textContent=!chosen.length?'Create voices':fresh&&updates?'Create '+fresh+(fresh===1?' voice':' voices')+' and update '+updates:fresh?'Create '+fresh+(fresh===1?' voice':' voices'):'Update '+updates+(updates===1?' voice':' voices');submit.disabled=!chosen.length;};
  found.authors.forEach((row,n)=>{
    const box=sNode('input','');box.type='checkbox';box.id='voices-author-'+n;box.value=row.author;box.checked=held.ticked.has(row.author);box.disabled=!row.ready||queued.has(row.author);
    box.addEventListener('change',()=>{if(box.checked)held.ticked.add(row.author);else held.ticked.delete(row.author);words();});
    const label=sNode('label','check author-pick');label.htmlFor=box.id;label.append(box,sAdd(sNode('span','row-text'),sNode('strong','row-title',row.profile?'Update '+row.profile.name+'’s voice':row.author),sNode('span','row-says',row.posts+(row.posts===1?' post':' posts')+' · '+row.readable+' readable'+(queued.has(row.author)?' · Queued: its voice is already being learned':row.ready?' · reads '+Math.min(row.readable,20)+', newest first':' · '+row.reason))));
    list.append(sAdd(sNode('li','row author-row'+(row.ready?'':' row-needs')),label,(row.suggestions||[]).length?sAuthorClarify(row):null));});
  words();
  const check=sNode('input');check.type='checkbox';check.id='voices-permission';const confirm=sNode('label','check');confirm.append(check,sNode('span','','I have permission to analyze this writing with my selected assistant.'));
  sAdd(form,sNode('p','','A voice for each ticked author, from up to 20 of their readable posts in the team library, newest first. Those posts become the author’s voice samples. Each voice stays provisional until you review and confirm it.'),
    found.authors.length?list:sNode('p','quiet','No post in the team library names its author yet. Add posts with Add to library: each post’s own author is read from its byline.'),
    ready.length>most?sNode('p','quiet',ready.length+' authors can have a voice; a batch takes '+most+', so the first '+most+' are ticked. Create voices for the rest in another batch.'):null,
    found.unnamed?sNode('p','quiet',found.unnamed+(found.unnamed===1?' post has':' posts have')+' no author and '+(found.unnamed===1?'is':'are')+' not counted. Set an author in Add to library to include '+(found.unnamed===1?'it':'them')+'.'):null,
    sNode('p','quiet','One job runs at a time, with your selected assistant and time limit.'),confirm,problem,sAdd(sNode('div','bar create-foot'),submit,sButton('Cancel',sCloseSheet)));
  form.addEventListener('submit',async event=>{event.preventDefault();if(!held.ticked.size)return;if(!check.checked){problem.textContent='Confirm you have permission to analyze this writing before creating the voices.';return;}
    await busy(submit,'Starting…',async()=>{try{const result=await api('library-voices',{operation:held.operation,authors:[...held.ticked],confirmed:true});studio.voiceBatch=result;await sVoicesBatch();}catch(error){problem.textContent=error.message;}});});
  sOpenSheet('Create voices for every author',form);
}
// A name that could be someone's fuller name: the person says whether it is. Same person
// names this author's posts by the fuller name, once confirmed; Different person stops the
// suggestion. Nothing changes until they choose, and each post's author stays editable in
// Review details.
function sAuthorClarify(row){
  const says=row.suggestions.map(other=>other.name+(other.voice?' (a voice)':' ('+other.posts+(other.posts===1?' post)':' posts)'))),problem=sNode('p','problem');problem.setAttribute('role','alert');
  const same=other=>sButton('Same person as '+other.name,()=>sOpenSheet('Same person?',sNode('p','','Name '+other.name+' as the author of '+row.author+'’s '+row.posts+(row.posts===1?' post':' posts')+'? '+(row.posts===1?'It then counts':'They then count')+' toward '+other.name+'’s voice.'),sNode('p','quiet','Each post’s author can be changed back in its Review details on the Team library.'),problem,
    sAdd(sNode('div','bar create-foot'),sButton('Yes, same person',async button=>busy(button,'Saving…',async()=>{try{const listing=await api('library-author-same',{author:row.author,into:other.name,expected:row.expected});sToast(row.author+'’s posts now name '+other.name+'.');await sVoicesForAuthors(listing);}catch(error){problem.textContent=error.message;}}),'filled'),sButton('Cancel',()=>sVoicesForAuthors()))));
  const different=sButton('Different person',async button=>busy(button,'Saving…',async()=>{try{await sVoicesForAuthors(await api('library-author-different',{author:row.author,others:row.suggestions.map(other=>other.name)}));}catch(error){problem.textContent=error.message;}}));
  return sAdd(sNode('div','author-clarify'),sNode('p','quiet','Might be the same person as '+(says.length<2?says.join(''):says.slice(0,-1).join(', ')+' or '+says[says.length-1])+'.'),sAdd(sNode('div','bar'),...row.suggestions.map(same),different),problem);
}
function sJobWords(job){if(job.applied)return 'Saved: '+job.applied.status;return {queued:'Waiting to start',working:'Working with your selected assistant',ready:'Ready for your review',failed:'Stopped: '+(job.error||'something went wrong'),cancelled:'Cancelled'}[job.status]||job.status;}
async function sVoicesBatch(){
  const batch=studio.voiceBatch;if(!batch)return sVoicesForAuthors();
  for(const row of batch.jobs)if(!row.job.applied){try{row.job=await api('tool-job?job='+row.job.id);}catch(error){/* shown as it was */}}
  const list=sNode('ul','rows'),paint=()=>{list.replaceChildren();for(const row of batch.jobs){const job=row.job,open=['queued','working'].includes(job.status);
    const item=sAdd(sNode('li','row'),sBead(job.applied?'done':job.status==='ready'?'review':['failed','cancelled'].includes(job.status)?'late':job.status==='working'?'current':'none'),sAdd(sNode('div','row-text'),sNode('h3','row-title',row.update?'Update '+(row.profile?.name||row.author)+'’s voice':row.author),sNode('p','row-says',sJobWords(job)+' · '+row.samples+(row.samples===1?' post':' posts')+(row.already?' · from an earlier batch':''))));
    if(!open)item.append(sButton(job.status==='ready'&&!job.applied?'Review '+row.author+'’s voice':'Open',async()=>sToolJob(await api('tool-job?job='+job.id)),job.status==='ready'&&!job.applied?'filled':'quiet'));
    list.append(item);}};
  paint();
  const failed=(batch.failed||[]).length?sAdd(sNode('div','context-note batch-failed'),sNode('p','problem',(batch.jobs.length?'Queued: '+sSeries(batch.jobs.map(row=>row.author))+'. ':'Nothing was queued. ')+'Not queued:'),sAdd(sNode('ul','rows'),...batch.failed.map(row=>sAdd(sNode('li','row'),sAdd(sNode('div','row-text'),sNode('h3','row-title',row.author),sNode('p','row-says',row.reason)))))):null;
  sOpenSheet('Create voices for every author',sNode('p','','Each voice is learned in its own job. Review each one when it is ready: save it as provisional, or confirm it.'),failed,list,
    sNode('p','quiet','You can close this sheet; the jobs keep their place in the queue. Reopen it from Create voices for every author.'),
    sAdd(sNode('div','bar create-foot'),sButton('Start another batch',()=>{const batch=studio.voiceBatch;studio.voiceBatch=null;studio.voicesQueued=batch;return sVoicesForAuthors(null);}),sButton('Close',sCloseSheet)));
  // Follow the jobs in place while this sheet stays open.
  const owner=studio.sheet,follow=async()=>{if(studio.sheet!==owner||!batch.jobs.some(row=>['queued','working'].includes(row.job.status)))return;try{for(const row of batch.jobs)if(['queued','working'].includes(row.job.status))row.job=await api('tool-job?job='+row.job.id);if(studio.sheet===owner){paint();setTimeout(follow,2000);}}catch(error){}};
  setTimeout(follow,2000);
}
// The headings of a saved ideas document, each with the line that follows it.
// New blog from my files: every file goes up at once and says what it has; the run starts from the readable ones.
function sCheck(id,label,held,key,hint,changed){const box=sNode('div','field'),row=sNode('label','check'),input=sNode('input','');input.type='checkbox';input.id=id;input.checked=!!held[key];input.addEventListener('change',()=>{held[key]=input.checked;if(changed)changed(input.checked);});row.append(input,sNode('span','',label));box.append(row);if(hint){const note=sNode('p','quiet field-hint',hint);note.id=id+'-hint';input.setAttribute('aria-describedby',note.id);box.append(note);}return box;}
// The page takes at most 15 MiB a request; files are sent base64-encoded (4/3 larger), so
// they go up in groups under 14 MiB encoded, each group its own operation.
function sUploadGroups(files,limit=14*1024*1024){const groups=[];let current=[],size=0;for(const file of files){const encoded=Math.ceil(file.size/3)*4+512;if(current.length&&size+encoded>limit){groups.push(current);current=[];size=0;}current.push(file);size+=encoded;}if(current.length)groups.push(current);return groups;}
// Your files, on the desk's start and its Add a source: every file goes up at once and is
// listed with how much text it has and what it is for; a Google Doc or a public link can be
// added beside them, and posts from the team library. They are saved with this blog only; one
// with Keep ticked goes to the team library at Start or Add, so a start left unfinished puts
// nothing in the library. `lock` holds Start while a role changes.
function sFilesCard(draft,problem,again,lock,about={}){
  draft.files=draft.files||[];draft.role=draft.role||'material';if(draft.keep===undefined)draft.keep=false;const ready=()=>draft.files.filter(file=>file.state==='ready');
  const roles=[['material','Facts (may be quoted)'],['messaging','Approved messaging (the product’s own claims)'],['inspiration','Example of the kind of post']];
  // Each file says what it is for. Facts may be quoted and cited; approved messaging is the product's own claims; an example shows the kind of post wanted and supplies no fact.
  const remember=result=>{for(const row of result.files||[])if(!draft.files.some(file=>file.id===row.source.id))draft.files.push({id:row.source.id,filename:row.filename,state:row.state,chars:row.chars||0,note:row.note||'',link:row.link||'',role:draft.role,kept:!!draft.keep});};
  const meaning='Facts may be quoted and cited. Approved messaging, such as a messaging document, launch brief or release notes, is stated as the product’s own claims. An example shows the shape, length and register of the post you want; nothing in it is used as a fact.';
  const roleField=sField('files-role','Add these files as',draft,'role',{options:roles});
  const picker=sNode('input','input');picker.id='files-input';picker.type='file';picker.multiple=true;picker.accept='.md,.txt,.html,.htm,.docx,.pdf';
  const label=sNode('label','field-label',draft.files.length?'Add more files':'Choose files');label.htmlFor=picker.id;
  picker.addEventListener('change',async()=>{const chosen=[...(picker.files||[])];if(!chosen.length)return;if(chosen.some(file=>file.size>10*1024*1024)){problem.textContent='Choose files up to 10 MiB each.';return;}if(chosen.length+draft.files.length>20){problem.textContent='Use up to 20 files for one blog.';return;}picker.disabled=true;studio.busy=true;problem.textContent=chosen.length===1?'Reading the file…':'Reading '+chosen.length+' files…';
    try{for(const group of sUploadGroups(chosen)){const files=[];for(const file of group)files.push({filename:file.name,content:await encodeImportFile(file),purpose:draft.role});remember(await api('upload',{operation:operationId(),files,purpose:'material',keep:false,analyze:false}));}studio.busy=false;const readable=ready().length;sToast(readable===draft.files.length?'Every file has text.':readable+' of '+draft.files.length+' files have text.');again();}
    catch(error){problem.textContent=error.message;}finally{studio.busy=false;picker.disabled=false;}});
  const list=sNode('ul','rows');list.setAttribute('aria-label','Your files');
  const where=file=>file.kept?' · To the team library':' · Just this blog';
  for(const file of draft.files){const row=sNode('li','row file-row'+(file.state==='ready'?'':' row-needs'));row.append(sBead(file.state==='ready'?'done':'late'),sAdd(sNode('div','row-text'),sNode('span','row-title',file.filename),sNode('span','row-says',file.library?'From the library'+(file.state==='ready'?(file.chars?' · '+file.chars.toLocaleString('en-US')+' characters':''):' · needs text, so it is not read'):(file.link?(/^https:\/\/docs\.google\.com\//.test(file.link)?'Google Doc · ':'Link · '):'')+(file.state==='ready'?file.chars.toLocaleString('en-US')+' characters'+(file.note?' · '+file.note:''):'Needs text · '+(file.note||'No text was found in this file.'))+where(file))));
    // A library item's role is for this blog only; an uploaded file's role is saved with it.
    {const was=file.role||'material';row.append(sField('files-role-'+file.id,'Used as',file,'role',{options:roles,short:true,changed:async value=>{if(file.library)return;let failed=false;studio.busy=true;lock(true);try{await api('source-role',{id:file.id,role:FILE_ROLES[value]||'facts'});problem.textContent='';}catch(error){failed=true;file.role=was;draft.problem=error.message;}finally{studio.busy=false;lock(false);}if(failed)again();}}));}
    if(!file.library){const title=file.kept?'Keep it to this blog':'Keep in the team library';const move=sButton(title,()=>{if(studio.busy)return;file.kept=!file.kept;again();});move.setAttribute('aria-label',title+' · '+file.filename);row.append(move);}
    {const drop=sButton('Remove',()=>{draft.files=draft.files.filter(other=>other!==file);again();});drop.setAttribute('aria-label','Remove '+file.filename);row.append(drop);}
    list.append(row);}
  const docInput=sNode('input','input');docInput.id='files-google';docInput.type='url';docInput.inputMode='url';docInput.autocomplete='off';docInput.placeholder='https://docs.google.com/document/d/…';docInput.setAttribute('aria-describedby','files-google-hint');const docLabel=sNode('label','field-label','Or add a Google Doc');docLabel.htmlFor=docInput.id;const docAdd=sButton('Add the Doc',async button=>{const link=docInput.value.trim();if(!link){problem.textContent='Paste a Google Doc link first.';docInput.focus();return;}if(draft.files.length>=20){problem.textContent='Use up to 20 files for one blog.';return;}await busy(button,'Reading the Doc…',async()=>{studio.busy=true;try{const result=await api('upload',{operation:operationId(),files:[{google:link,purpose:draft.role}],purpose:'material',keep:false,analyze:false});const added=(result.files||[])[0];remember(result);problem.textContent='';studio.busy=false;sToast(added?'Added '+added.filename+'.':'Added the Doc.');again();}catch(error){problem.textContent=error.message;docInput.focus();}finally{studio.busy=false;}});});docAdd.id='files-google-add';const docHint=sNode('p','quiet field-hint','Read with this computer’s Google sign-in.');docHint.id='files-google-hint';const docField=sAdd(sNode('div','field'),docLabel,sAdd(sNode('div','bar'),docInput,docAdd),docHint);
  // A public page, read now and saved with this blog like a file.
  let linkField;
  {const linkInput=sNode('input','input');linkInput.id='files-link';linkInput.type='url';linkInput.inputMode='url';linkInput.autocomplete='off';linkInput.placeholder='https://…';const linkLabel=sNode('label','field-label','Or add a link');linkLabel.htmlFor=linkInput.id;const linkAdd=sButton('Add the link',async button=>{const link=linkInput.value.trim();if(!/^https:\/\/\S+$/.test(link)){problem.textContent='Paste a public https link first.';linkInput.focus();return;}if(draft.files.length>=20){problem.textContent='Use up to 20 files for one blog.';return;}await busy(button,'Reading the page…',async()=>{studio.busy=true;try{const result=await api('upload',{operation:operationId(),files:[{link,purpose:draft.role}],purpose:'material',keep:false,analyze:false});const added=(result.files||[])[0];remember(result);problem.textContent='';studio.busy=false;sToast(added?'Added '+added.filename+'.':'Added the page.');again();}catch(error){problem.textContent=error.message;linkInput.focus();}finally{studio.busy=false;}});});linkAdd.id='files-link-add';linkField=sAdd(sNode('div','field'),linkLabel,sAdd(sNode('div','bar'),linkInput,linkAdd),sNode('p','quiet field-hint','A public page, read once.'));}
  const fromLibrary=sAdd(sNode('div','field'),sAdd(sNode('div','bar'),sButton('From the library',()=>sLibraryPicker(draft,again))),sNode('p','quiet field-hint','Posts already in the team library, each with its role.'));
  // Keep comes before the picker: it applies to the files added next, and each row says where its file went.
  const keep=sCheck('files-keep','Keep in the team library',draft,'keep',about.keepWhen||'Ticked ones go to the team library when you start.');
  return sCard('Your files',roleField,disclosure('What the roles mean',sNode('p','quiet',meaning)),keep,sAdd(sNode('div','field'),label,picker),docField,linkField,fromLibrary,draft.files.length?list:null);
}

async function sLibraryPicker(draft,again){
  const held={role:'',kind:'',author:'',query:'',chosen:new Set()},problem=sNode('p','problem'),form=sNode('form'),list=sNode('ul','rows');problem.setAttribute('role','alert');let rows=[];
  const kinds=(studio.options?.styles||[]).filter(style=>style.status!=='retired');
  const add=sButton('Add 0 to this blog',()=>{for(const item of rows)if(held.chosen.has(item.id)&&!draft.files.some(file=>file.id===item.id))draft.files.push({id:item.id,location:item.location==='hub'?'hub':'local',filename:item.title,state:item.status==='ready'?'ready':'pending',chars:0,note:'',link:'',role:item.role==='example'?'inspiration':item.role==='messaging'?'messaging':'material',library:true,kept:true});sCloseSheet();again();},'filled');add.disabled=true;
  const search=async()=>{const query=new URLSearchParams({limit:'50',query:held.query.trim()});for(const key of ['role','kind','author'])if(held[key].trim())query.set(key,held[key].trim());rows=(await api('library?'+query)).items;list.replaceChildren();
    for(const item of rows){if(draft.files.some(file=>file.id===item.id))continue;const pick=sNode('input','');pick.type='checkbox';pick.id='pick-'+item.id;pick.setAttribute('aria-label','Pick '+item.title);pick.addEventListener('change',()=>{if(pick.checked)held.chosen.add(item.id);else held.chosen.delete(item.id);add.textContent='Add '+held.chosen.size+' to this blog';add.disabled=!held.chosen.size;});
      const label=sNode('label','check');label.append(pick,sAdd(sNode('span',''),sNode('strong','',item.title),sNode('span','quiet',' · '+(item.author||'no author')+(item.library?.published?' · '+item.library.published:'')+' · '+(LIBRARY_ROLES[item.role]||'Facts').toLowerCase()+(item.kind_name?' · '+item.kind_name:'')+(item.status==='ready'?'':' · needs text'))));list.append(sAdd(sNode('li','row'),label));}
    if(!list.children.length)list.append(sAdd(sNode('li','row'),sNode('p','quiet',rows.length?'Every match is already among the files.':'Nothing in the library matches.')));};
  form.append(sField('pick-query','Search',held,'query',{max:200}),sField('pick-role','Role',held,'role',{options:[['','Any role'],['facts','Facts'],['messaging','Approved messaging'],['example','Examples'],...(sVoicesOn()?[['voice-sample','Voice samples']]:[]),['style-sample','Style samples']]}),sField('pick-kind','Kind of post',held,'kind',{options:[['','Any kind'],...kinds.map(style=>[style.id,style.name])]}),sField('pick-author','Author',held,'author',{max:200}));
  const go=sNode('button','button','Search');go.type='submit';form.append(go);form.addEventListener('submit',async event=>{event.preventDefault();await busy(go,'Searching…',async()=>{try{await search();}catch(error){problem.textContent=error.message;}});});
  sOpenSheet('From the library',sNode('p','quiet','Each item keeps the role it has in the library unless you change it for this blog; the library record stays as it is. Nothing is copied.'),form,list,problem,add,sButton('Cancel',sCloseSheet));
  try{await search();}catch(error){problem.textContent=error.message;}
}
function sNoneOfThese(found){const held={request:''},form=sNode('form','note'),problem=sNode('p','problem'),go=sNode('button','button button-filled','Ask for three more');go.type='submit';problem.setAttribute('role','alert');
  form.append(sNode('p','','The next three will be different from these.'),sField('angles-note','What should they be closer to? (optional)',held,'request',{long:true,max:8000}),problem,sAdd(sNode('div','bar'),go,sButton('Cancel',sCloseSheet)));
  form.addEventListener('submit',async event=>{event.preventDefault();await busy(go,'Asking…',async()=>{try{await runAction('changes',found,{request:held.request.trim()||'None of these angles fit. Propose three different ones.',stage:'angles'},true);sCloseSheet();}catch(error){problem.textContent=error.message;}});});sOpenSheet('None of these',form);}
function sAngles(text){const lines=String(text||'').split(/\r?\n/),found=[];for(let i=0;i<lines.length;i++){const match=/^##\s+(.+?)\s*#*\s*$/.exec(lines[i]);if(!match)continue;let says='';for(let j=i+1;j<lines.length&&!/^#/.test(lines[j]);j++){if(lines[j].trim()){says=lines[j].trim().replace(/^[-*]\s+/,'');break;}}found.push({title:match[1].replace(/^\d+[.)]\s*/,'').replace(/\*\*/g,''),says});}return found.slice(0,8);}

// The parts of the page drawn once that belong to the older voice tools: the Voices item,
// the library's "Learn a voice from these", and the voice-sample choices in the upload
// dialog and the library filter. Shown or hidden as the switch is; called after Settings.
function sVoiceSwitchShown(){
  const on=sVoicesOn();
  const learn=$('library-learn-voice');if(learn)learn.hidden=!on;
  studio.voiceOptions||=[];
  if(!on){for(const id of ['upload-purpose','library-role']){const select=$(id);if(!select)continue;for(const option of [...(select.children||[])])if(option.value==='voice-sample'){if(select.value==='voice-sample')select.value=select.children[0]?.value||'';option.remove();studio.voiceOptions.push({select,option});}}return;}
  for(const {select,option} of studio.voiceOptions.splice(0)){const style=[...select.children].find(node=>node.value==='style-sample');if(style&&typeof select.insertBefore==='function')select.insertBefore(option,style);else select.append(option);}
}

// Keep initialization below this marker so the same controller can be exercised with a DOM fixture.
STUDIO_ICONS.studio=['M5 3h10l4 4v14H5z','M14 3v5h5','M8 12h8','M8 16h6'];
STUDIO_ICONS.suite=['M4 4h6v6H4z','M14 4h6v6h-6z','M4 14h6v6H4z','M14 14h6v6h-6z'];
{const back=$('go-suite');if(back&&suite){back.href=suite+'/';if(suiteTab)back.removeAttribute('target');back.prepend(sIcon('suite'));back.hidden=false;}}
$('studio-symbol')?.append(sIcon('studio'));
for(const [id,screen,icon]of [['go-home','home','home'],['go-blogs','blogs','blogs'],['go-status','status','status'],['go-settings','settings','settings']]){const node=$(id);node.prepend(sIcon(icon));node.addEventListener('click',()=>sRoute(screen));}
{const node=$('go-guides');if(node){node.prepend(sIcon('voices'));node.addEventListener('click',()=>sRoute('guides'));}}
for(const node of document.querySelectorAll('[data-view]'))node.addEventListener('click',()=>sLegacy(node.dataset.view));
document.querySelector('.skip').addEventListener('click',event=>{event.preventDefault();$('main').focus();});
// A new link opened in a tab that already shows this page changes only the fragment, which does
// not reload it. Start again with the new key.
window.addEventListener('hashchange',()=>{const next=location.hash.slice(1).split('&')[0];if(next&&/^(token=)?[A-Za-z0-9_-]{32,128}$/.test(next)&&next.replace(/^token=/,'')!==token.replace(/^token=/,''))location.reload();});
window.addEventListener('popstate',()=>{const query=new URLSearchParams(location.search);studioNavigate(query.get('screen')||'home',query.get('id'),query.get('stage'));});
document.addEventListener('keydown',event=>{if(!studio.sheet)return;if(event.key==='Escape'){event.preventDefault();sCloseSheet();return;}if(event.key==='Tab'){const nodes=[...$('sheet').querySelectorAll('button,input,textarea,select,[tabindex="0"]')].filter(node=>!node.disabled);if(!nodes.length){event.preventDefault();return;}const first=nodes[0],last=nodes[nodes.length-1];if(event.shiftKey&&(document.activeElement===first||document.activeElement===$('sheet'))){event.preventDefault();last.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus();}}});
document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='hidden'&&studio.screen==='desk')sDeskShare(studio.desk);});
setInterval(sPoll,3000);
(async()=>{await loadCapabilities();studio.settings=await api('run-settings');sVoiceSwitchShown();const query=new URLSearchParams(location.search);await studioNavigate(query.get('screen')||(studio.settings.configured?'home':'setup'),query.get('id'),query.get('stage'));})().catch(error=>notice(error.message,true));


window.addEventListener('beforeunload',event=>{if(Object.values(studio.editorDrafts||{}).some(draft=>draft.content!==draft.baseContent)){event.preventDefault();event.returnValue='';}});
