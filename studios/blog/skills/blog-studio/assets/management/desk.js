// The writing desk: one page per blog with a card for each part, notes that rewrite a
// section, selection edits and quiet version history. Built with runner.js's helpers; every
// text from the draft is set with textContent.
'use strict';
const DESK_FIRST_PASSES=[['tighten','Tighten and proofread'],['reshape','Reshape to fit this kind of post'],['leave','Leave it as it is']];
const DESK_SELECTION=[['rephrase','Rephrase'],['shorten','Shorten'],['expand','Expand'],['fix','Fix']];
const DESK_SOURCES={save:'Before your edit',rewrite:'Before a rewrite','revise-all':'Before a whole-draft revision',selection:'Before a selection edit','first-pass':'Before the first pass',finishing:'Before a finishing change',restore:'Before a restore',draft:'Before the draft was written'};
const DESK_DOING={'desk-section':'Rewriting','desk-revise-all':'Revising the whole draft','desk-selection':'Editing a passage','desk-first-pass':'Working on the first pass','desk-outline':'Outlining','desk-draft':'Writing the draft','desk-research':'Researching'};
// A start's steps, as the progress screen names them.
const DESK_STEPS={research:'Researching',outline:'Outlining',draft:'Drafting'};
const DESK_SAVE_WAIT=1000,DESK_POLL=3000,DESK_DIFF_LIMIT=4000;

// Words compared by a longest common subsequence, after the words both texts start and end
// with are set aside; a comparison over about four million word pairs is shown side by side.
function deskWords(text){return String(text||'').split(/\s+/).filter(Boolean);}
function diffWords(before,after){
  const a=deskWords(before),b=deskWords(after);
  if(a.length>DESK_DIFF_LIMIT||b.length>DESK_DIFF_LIMIT)return null;
  let head=0;while(head<a.length&&head<b.length&&a[head]===b[head])head++;
  let tail=0;while(tail<a.length-head&&tail<b.length-head&&a[a.length-1-tail]===b[b.length-1-tail])tail++;
  const x=a.slice(head,a.length-tail),y=b.slice(head,b.length-tail);
  if(x.length*y.length>DESK_DIFF_LIMIT*1000)return null;
  const cols=y.length+1,table=new Uint16Array((x.length+1)*cols);
  for(let i=x.length-1;i>=0;i--)for(let j=y.length-1;j>=0;j--)table[i*cols+j]=x[i]===y[j]?table[(i+1)*cols+j+1]+1:Math.max(table[(i+1)*cols+j],table[i*cols+j+1]);
  const out=[],push=(op,word)=>{const last=out[out.length-1];if(last&&last.op===op)last.text+=' '+word;else out.push({op,text:word});};
  for(const word of a.slice(0,head))push('same',word);
  let i=0,j=0;
  while(i<x.length&&j<y.length){if(x[i]===y[j]){push('same',x[i]);i++;j++;}else if(table[(i+1)*cols+j]>=table[i*cols+j+1]){push('removed',x[i]);i++;}else{push('added',y[j]);j++;}}
  while(i<x.length)push('removed',x[i++]);while(j<y.length)push('added',y[j++]);
  for(const word of a.slice(a.length-tail))push('same',word);
  return out;
}
function deskCompare(before,after){
  const found=diffWords(before,after),box=sNode('div','paper desk-compare');
  if(!found){box.append(sAdd(sNode('div','desk-side'),sNode('h3','sheet-part','Before'),sNode('p','desk-plain',before)),sAdd(sNode('div','desk-side'),sNode('h3','sheet-part','Now'),sNode('p','desk-plain',after)));return box;}
  const text=sNode('p','desk-plain');text.setAttribute('aria-label','Changes from this version to the current text');
  found.forEach((piece,index)=>{if(index)text.append(document.createTextNode(' '));text.append(sNode(piece.op==='same'?'span':piece.op==='added'?'ins':'del',piece.op==='same'?'':piece.op==='added'?'diff-add':'diff-remove',piece.text));});
  return sAdd(box,text);
}
function deskAge(at){const then=Date.parse(at||'');if(!then)return '';const minutes=Math.round((Date.now()-then)/60000);if(minutes<1)return 'just now';if(minutes<60)return minutes+(minutes===1?' minute ago':' minutes ago');const hours=Math.round(minutes/60);if(hours<24)return hours+(hours===1?' hour ago':' hours ago');const days=Math.round(hours/24);return days+(days===1?' day ago':' days ago');}
function deskPartName(view,part){if(part==='title')return 'the title';if(part==='opening')return 'the opening';if(part==='sections')return 'every section';const found=(view.sections||[]).find(section=>section.id===part);return found?'“'+found.heading+'”':'a section';}
function deskTextOf(view,part){if(part==='title'||part==='opening')return view[part]||'';return (view.sections||[]).find(section=>section.id===part)?.text||'';}

// A new blog: 1. the kind of post, 2. what the person brings (a topic, an outline or notes,
// or a draft), 3. sources and settings, then Start. Nothing stops for the person after it.
const DESK_HAVE=[['topic','Just a topic'],['outline','An outline or notes'],['draft','A draft']];
const DESK_OUTLINE_WAYS=[['outline','Write from my outline'],['shape','Shape an outline with me first']];
const DESK_START_STEPS=['Kind of post','What you have','Sources and settings'];
const DESK_START_LEDES=['Choose the kind of post. It sets the usual shape and length.','Say what you bring: a topic, an outline or notes, or a draft.','Add sources if you have them, then start. Nothing stops for you on the way.'];
function sDeskHeld(){
  if(studio.deskStart)return studio.deskStart;
  const defaults=studio.options?.settings?.defaults||{},preset=studio.deskPreset||{};studio.deskPreset=null;
  return studio.deskStart={step:0,kind:null,style:'',have:'topic',title:'',audience:'',point:'',angles:[],angle:null,angleOp:null,anglesBusy:false,anglesProblem:'',outline:'',outlineFrom:'paste',outlineFile:null,outlineWay:'outline',source:'paste',manuscript:'',url:'',file:null,preview:null,first_pass:'leave',files:[],role:'material',keep:true,link:'',from:{on:true,documents:true,sites:false,web:false,picked:[...sSharedSites()],added:[]},searchSites:false,searchWeb:false,length:'style',tone:defaults.tone||'',operation:operationId(),upload:operationId(),...preset};
}
// Home's tasks, New blog and the library's "Write a blog from these" all start here.
function sDeskBegin(preset={}){studio.deskStart=null;studio.deskPreset=preset;return sRoute('desk-start');}
async function sDeskStart(){
  if(!studio.options)studio.options=await api('run-options');
  const held=sDeskHeld();
  sFrame('New blog',[],'New writing',()=>sRoute('home'));
  const steps=sWorkflowSteps(DESK_START_STEPS,held.step,index=>{if(index&&held.kind===null)return notice('Choose a kind of post first, or Something else.',true);held.step=index;sTop();sDeskStart();});
  sPage(sNode('p','lede',DESK_START_LEDES[held.step]),steps,held.step===0?sDeskKinds(held):held.step===1?sDeskHave(held):sDeskSettings(held));
}
function sDeskStartAgain(held){if(studio.screen==='desk-start'&&studio.deskStart===held)sDeskStart();}
function sDeskWriting(held){return held.have!=='draft';}

// 1. What are you writing? A card per kind of post, with its usual shape.
function sDeskKinds(held){
  const list=sNode('div','pick-cards'),pick=kind=>{held.kind=kind;held.style=kind;sStyleSamples(held);held.step=1;sTop();sDeskStart();};
  for(const style of (studio.options?.styles||[]).filter(style=>style.status!=='retired')){const card=sPickCard(style.name,style.summary||(style.kind==='seed'?'A starter kind of post.':'A kind of post saved here.'),()=>pick(style.id));card.setAttribute('aria-pressed',String(held.kind===style.id));card.disabled=!access.actions.edit;list.append(card);}
  const other=sPickCard('Something else','No particular kind of post: the shape follows your point and material.',()=>pick(''));other.setAttribute('aria-pressed',String(held.kind===''));other.disabled=!access.actions.edit;list.append(other);
  return sCard('What are you writing?',list);
}

// 2. What do you have?
function sDeskHave(held){
  const form=sNode('form','narrow desk-start'),problem=sNode('p','problem');problem.setAttribute('role','alert');
  const parts=[sCard('What do you have?',sChoice('What you bring',DESK_HAVE,held,'have',()=>sDeskStart()))];
  if(held.have==='topic')parts.push(...sDeskTopic(held));else if(held.have==='outline')parts.push(sDeskOutlineIn(held));else parts.push(...sDeskDraftIn(held));
  const reading=held.have==='draft'&&held.source==='google'&&!held.preview;
  const go=sNode('button','button button-filled',reading?'Read Google Doc':'Continue');go.type='submit';go.disabled=!access.actions.edit;
  form.append(...parts,sAdd(sNode('div','form-foot'),problem,sAdd(sNode('div','bar'),go)));
  form.addEventListener('submit',async event=>{
    event.preventDefault();if(!access.actions.edit)return;const said=sDeskHaveProblem(held);if(said){problem.textContent=said;return;}
    if(reading)return busy(go,'Reading…',async()=>{try{await sDeskReadGoogle(held);}catch(error){problem.textContent=error.message+' Your choices are kept here.';}});
    held.step=2;sTop();sDeskStart();
  });
  return form;
}
function sDeskHaveProblem(held){
  if(held.have==='topic'&&!(held.title.trim()&&held.point.trim()))return 'Add a working title and the point to make, or pick an angle.';
  if(held.have==='outline'){
    if(held.outlineFrom==='paste'&&!held.outline.trim())return 'Paste your outline or notes first.';
    if(held.outlineFrom==='file'&&!held.outlineFile)return 'Choose your outline to upload.';
    if(held.outlineFrom==='paste'&&!held.title.trim()&&!/^# \S/.test(held.outline.trim()))return 'Give the blog a title, or start your outline with a # title line.';
  }
  if(held.have==='draft'){
    if(held.source==='paste'&&!held.manuscript.trim())return 'Paste your draft first.';
    if(held.source==='file'&&!held.file)return 'Choose a draft to upload.';
    if(held.source==='google'&&!held.url.trim())return 'Paste the Google Doc link first.';
    if(held.first_pass==='reshape'&&!held.kind)return 'Choose a kind of post to reshape the draft to, on step 1.';
  }
  return '';
}
// Just a topic: the point typed, or three angles suggested on this screen to pick and edit.
function sDeskTopic(held){
  const card=sCard('Your topic',sField('desk-title','Working title',held,'title',{required:true,max:500}),sField('desk-audience','Who is it for?',held,'audience',{max:500,hint:'For example: platform engineers new to the product.'}),sField('desk-point','The point to make',held,'point',{long:true,max:2000,hint:'What the reader should understand or do afterward. Type it, or suggest three angles and pick one.'}));
  const ready=held.files.filter(file=>file.state==='ready').length;
  const ask=sButton(held.angles.length?'Suggest three more':'Suggest three angles',button=>sDeskAskAngles(held,button));ask.disabled=!access.actions.edit||held.anglesBusy;
  const sources=sButton(ready?'Add more sources':'Add sources first',()=>sDeskSourcesSheet(held,'start'));sources.disabled=!access.actions.edit;
  card.append(sAdd(sNode('div','bar'),ask,sources),sNode('p','quiet field-hint',ready?'Angles read your '+ready+(ready===1?' source.':' sources.'):'Angles read the sources you add; with none, they work from the title and point.'));
  if(held.anglesBusy){const working=sNode('p','desk-working-note','Finding three angles… Keep typing if you like; they appear here.');working.setAttribute('role','status');card.append(working);}
  if(held.anglesProblem)card.append(sNode('p','problem',held.anglesProblem));
  if(!held.angles.length)return [card];
  const cards=sNode('div','desk-angles');cards.setAttribute('aria-label','Three angles');
  held.angles.forEach((angle,index)=>{
    const picked=held.angle===index,box=sNode('section','card desk-angle'+(picked?' desk-angle-picked':''));
    const follow=()=>{if(held.angle===index)Object.assign(held,{title:angle.headline,point:angle.point,audience:angle.audience});};
    box.append(sNode('h2','card-title','Angle '+(index+1)),sField('desk-angle-'+index+'-headline','Headline',angle,'headline',{max:300,changed:follow}),sField('desk-angle-'+index+'-point','The point it makes',angle,'point',{long:true,max:2000,changed:follow}),sField('desk-angle-'+index+'-audience','Who it is for',angle,'audience',{max:500,changed:follow}));
    const use=sButton(picked?'Using this angle':'Use this angle',()=>{held.angle=index;follow();sDeskStart();});use.setAttribute('aria-pressed',String(picked));
    box.append(sAdd(sNode('div','bar'),use));cards.append(box);
  });
  return [card,cards];
}
function sDeskLibraryPicks(files){return files.filter(file=>file.library&&file.state==='ready').map(file=>({id:file.id,role:FILE_ROLES[file.role]||'facts',...(file.location==='hub'?{location:'hub'}:{})}));}
function sDeskUploads(files){return [...new Set(files.filter(file=>!file.library&&file.state==='ready').map(file=>file.id))];}
async function sDeskAskAngles(held,button){
  const operation=operationId();held.angleOp=operation;held.anglesProblem='';
  await busy(button,'Asking…',async()=>{try{
    const shown=await api('desk-angles',{operation,title:held.title.trim(),point:held.point.trim(),audience:held.audience.trim(),style:held.kind||'',tone:held.tone,sources:sDeskUploads(held.files),library:sDeskLibraryPicks(held.files)});
    sDeskAnglesShown(held,shown);
  }catch(error){held.anglesProblem=error.message;sDeskStartAgain(held);}});
}
function sDeskAnglesShown(held,shown){
  if(held.angleOp!==shown.operation)return;
  held.anglesBusy=!!shown.busy;
  if(!shown.busy){if(shown.error)held.anglesProblem=shown.error;else{held.angles=shown.angles.map(angle=>({...angle}));held.angle=null;}}
  sDeskStartAgain(held);
  if(shown.busy)setTimeout(async()=>{if(held.angleOp!==shown.operation||studio.deskStart!==held)return;try{sDeskAnglesShown(held,await api('desk-angles?'+new URLSearchParams({operation:shown.operation})));}catch(error){held.anglesBusy=false;held.anglesProblem=error.message;sDeskStartAgain(held);}},DESK_POLL);
}
// An outline or notes: pasted or uploaded, then written from, or shaped together first.
function sDeskOutlineIn(held){
  const card=sCard('Your outline or notes',sChoice('Where is it?',[['paste','Paste'],['file','Upload a file']],held,'outlineFrom',()=>sDeskStart()));
  if(held.outlineFrom==='paste')card.append(sField('desk-outline','Paste your outline or notes',held,'outline',{long:true,max:200000,required:true,hint:'Headings or a list make sections, with what is under each as its brief. Notes without them are outlined first.'}));
  else{const file=sNode('input','input');file.type='file';file.accept='.txt,.md,.docx,.pdf,.html,.htm';file.setAttribute('aria-label','Upload an outline');const note=sNode('p','quiet field-hint',held.outlineFile?'Selected: '+held.outlineFile.name:'Text, Markdown, Word or PDF. Up to 10 MiB.');file.addEventListener('change',()=>{held.outlineFile=file.files?.[0]||null;note.textContent=held.outlineFile?'Selected: '+held.outlineFile.name:'Choose an outline.';});card.append(file,note);}
  card.append(sField('desk-title','Title (optional)',held,'title',{max:500,hint:'Leave blank to use the outline’s # heading.'}),sChoice('Then',DESK_OUTLINE_WAYS,held,'outlineWay',()=>sDeskStart()),sNode('p','quiet field-hint',held.outlineWay==='shape'?'An outline is proposed from your notes and opens on the desk, where you shape it and write the draft when you are ready.':'Your outline becomes the desk’s outline and the draft is written from it.'));
  return card;
}
// A draft: paste, upload or a Google Doc (every tab), with an optional first pass.
function sDeskDraftIn(held){
  const card=sCard('Your draft',sChoice('Where is your draft?',[['paste','Paste text'],['file','Upload a file'],['google','Google Doc']],held,'source',()=>{held.preview=null;sDeskStart();}));
  if(held.source==='paste')card.append(sField('desk-manuscript','Paste your draft',held,'manuscript',{long:true,max:1000000,required:true,hint:'Markdown or plain text. Each ## heading starts a section; text before the first one is the opening.'}));
  else if(held.source==='file'){
    const file=sNode('input','input');file.type='file';file.accept='.txt,.md,.docx,.pdf,.html,.htm';file.setAttribute('aria-label','Upload a draft');
    const note=sNode('p','quiet field-hint',held.file?'Selected: '+held.file.name:'Text, Markdown, Word or PDF. Up to 10 MiB.');
    file.addEventListener('change',()=>{held.file=file.files?.[0]||null;note.textContent=held.file?'Selected: '+held.file.name:'Choose a draft.';});
    card.append(file,note);
  }else{
    card.append(sField('desk-google','Google Doc link or document ID',held,'url',{required:true,max:2000,hint:'Every tab is read. The Doc is not changed or shared.',changed:()=>{held.preview=null;}}));
    if(held.preview){const paper=sNode('article','paper doc');paper.setAttribute('aria-label','Google Doc preview');paper.append(window.TrainingStudioMarkdown?window.TrainingStudioMarkdown.render(held.preview.content):sNode('p','',held.preview.content));card.append(sNode('p','','Check the text below, then continue.'),paper);}
  }
  card.append(sField('desk-title','Title (optional)',held,'title',{max:500,hint:'Leave blank to use the draft’s # heading or the Doc’s name.'}));
  return [card,sCard('A first pass',sChoice('Before you edit',DESK_FIRST_PASSES,held,'first_pass'),sNode('p','quiet','Optional. It runs once on the desk and keeps your text as a version first.'))];
}
async function sDeskReadGoogle(held){
  const turn=studio.turn,found=await api('google-preview',{url:held.url.trim()});if(turn!==studio.turn)return;
  if(found?.status==='already-linked'&&found.id){
    // The Doc is already a blog here: open it on the desk, or bring it there.
    let made=null;try{made=await api('desk?id='+encodeURIComponent(found.id));}catch(_){made=null;}
    made=made||await api('desk-create',{operation:held.operation,style:held.kind||'',tone:held.tone,first_pass:held.first_pass,article:found.id});
    if(turn!==studio.turn)return;studio.deskStart=null;studio.desk={id:made.id,view:made,session:operationId()};return sRoute('desk',made.id);
  }
  held.preview=sGooglePreview(found);if(!held.title.trim())held.title=found.title;sDeskStart();
}

// 3. Sources and settings, for every way of working; research and length for new writing.
function sDeskSettings(held){
  const form=sNode('form','narrow desk-start'),problem=sNode('p','problem');problem.setAttribute('role','alert');
  const again=()=>sDeskStartAgain(held);
  const go=sNode('button','button button-filled','Start');go.type='submit';go.disabled=studio.busy||!access.actions.edit;
  const files=sFilesCard(held,problem,again,locked=>{go.disabled=locked||!access.actions.edit;});
  sDeskWithLink(files,held,problem,again);
  form.append(files);
  if(sDeskWriting(held)){
    form.append(sCard('Research before the writing',
      sCheck('desk-sites','Search my sites',held,'searchSites','The sites in Shared settings; tick the ones to search.',()=>again()),
      held.searchSites?sSitePicker(held.from,'desk-research',()=>{}):null,
      sCheck('desk-web','Search the web too',held,'searchWeb','Public pages found with the assistant’s web search.'),
      sNode('p','quiet','Both are off unless you tick them. With either, research runs before the outline, with no stop for you; your sources are read either way.')));
  }
  const length={mode:'write',get length(){return held.length;},set length(value){held.length=value;}};
  form.append(sCard(sDeskWriting(held)?'Length and tone':'Tone',sDeskWriting(held)?sLengthSelect(length,'desk-length'):null,sField('desk-tone','Tone',held,'tone',{max:2000,hint:'How it should sound, such as clear and conversational.'})));
  form.append(sAdd(sNode('div','form-foot'),problem,sAdd(sNode('div','bar'),go)));
  form.addEventListener('submit',async event=>{event.preventDefault();if(!access.actions.edit||studio.busy)return;await busy(go,'Starting…',async()=>{try{await sDeskGo(held);}catch(error){problem.textContent=error.message+' Your choices are kept here.';}});});
  return form;
}
async function sDeskGo(held){
  if(held.kind===null){held.step=0;sDeskStart();throw new Error('Choose a kind of post first.');}
  const unfinished=sDeskHaveProblem(held);if(unfinished){held.step=1;sDeskStart();throw new Error(unfinished);}
  if(held.searchSites&&!sChosenSites(held.from).length)throw new Error(sResearchWord('no_sites')||'Choose at least one of your sites, or untick Search my sites.');
  const turn=studio.turn,common={operation:held.operation,style:held.kind||'',tone:held.tone,sources:sDeskUploads(held.files),library:sDeskLibraryPicks(held.files),...(held.title.trim()?{title:held.title.trim()}:{})};
  let made;
  if(held.have==='draft'){
    const settings={...common,first_pass:held.first_pass};
    if(held.source==='paste')made=await api('desk-create',{...settings,manuscript:held.manuscript});
    else if(held.source==='file'){
      if(held.file.size>10*1024*1024)throw new Error('Choose a file up to 10 MiB.');
      const uploaded=await api('upload',{operation:held.upload,filename:held.file.name,title:held.title.trim()||held.file.name.replace(/\.[^.]+$/,''),content:await encodeImportFile(held.file),purpose:'manuscript',analyze:false});
      if(uploaded.state&&uploaded.state!=='ready')throw new Error('This file needs its text extracted before it can be edited. Paste the text instead.');
      made=await api('desk-create',{...settings,source:uploaded.source.id});
    }else{
      if(!held.preview){held.step=1;sDeskStart();throw new Error('Read the Google Doc first, on step 2.');}
      const started=await api('google-start',{preview:held.preview.preview,expected:held.preview.expected,title:held.title.trim()||held.preview.title,confirmed:true});
      made=await api('desk-create',{...settings,title:undefined,article:started.id});
    }
  }else{
    const research=held.searchSites||held.searchWeb?{research_from:{sites:held.searchSites?sChosenSites(held.from):[],web:!!held.searchWeb}}:{};
    const writing={...common,way:held.have==='topic'?'topic':held.outlineWay,length:held.length||'style',...research};
    if(held.have==='topic')made=await api('desk-create',{...writing,point:held.point.trim(),...(held.audience.trim()?{audience:held.audience.trim()}:{})});
    else if(held.outlineFrom==='paste')made=await api('desk-create',{...writing,outline:held.outline});
    else{
      if(held.outlineFile.size>10*1024*1024)throw new Error('Choose a file up to 10 MiB.');
      const uploaded=await api('upload',{operation:held.upload,filename:held.outlineFile.name,title:held.title.trim()||held.outlineFile.name.replace(/\.[^.]+$/,''),content:await encodeImportFile(held.outlineFile),purpose:'manuscript',analyze:false});
      if(uploaded.state&&uploaded.state!=='ready')throw new Error('This file needs its text extracted first. Paste the outline instead.');
      made=await api('desk-create',{...writing,outline_source:uploaded.source.id});
    }
  }
  if(turn!==studio.turn)return;studio.deskStart=null;
  if(made.first_pass_problem)sToast('The first pass did not start: '+made.first_pass_problem);
  studio.desk={id:made.id,view:made,session:operationId()};await sRoute('desk',made.id);
}

// Sources: the files card (files, Google Docs, the library, each with its role), and a link
// read into the team library through its own intake, then picked like a library post.
function sDeskWithLink(card,held,problem,again){const kids=[...card.children],at=Math.min(5,kids.length);card.replaceChildren(...kids.slice(0,at),sDeskLinkField(held,problem,again),...kids.slice(at));return card;}
function sDeskLinkField(held,problem,again){
  const box=sNode('div','field'),label=sNode('label','field-label','Or add a link'),input=sNode('input','input');input.id='desk-link';input.type='url';input.inputMode='url';input.autocomplete='off';input.placeholder='https://…';input.value=held.link||'';label.htmlFor=input.id;input.addEventListener('input',()=>{held.link=input.value;});
  const add=sButton('Add the link',async button=>{const url=(held.link||'').trim();if(!/^https:\/\/\S+$/.test(url)){problem.textContent='Paste a public https link first.';return;}await busy(button,'Reading the page…',async()=>{try{const item=await sDeskAddLink(held,url);held.link='';problem.textContent='';sToast('Added '+(item.title||url)+'.');again();}catch(error){problem.textContent=error.message;}});});
  add.disabled=!access.actions.edit;
  return sAdd(box,label,sAdd(sNode('div','bar'),input,add),sNode('p','quiet field-hint','The page is read and kept in the team library with the role above, like a kept file.'));
}
async function sDeskAddLink(held,url){
  const payload={files:[],links:url,role:FILE_ROLES[held.role]||'facts',author:'*each',kind:held.style||''},operation=operationId();
  const shown=await api('library-add-preview',payload);
  let result=await api('library-add',{...payload,operation,expected:shown.expected});
  for(let turns=0;result.remaining>0&&turns<10;turns++)result=await api('library-add',{...payload,operation,expected:shown.expected});
  const item=(result.items||[]).find(row=>row.id);
  if(!item)throw new Error((result.items||[])[0]?.reason||'This page could not be read. Try another link, or upload it as a file.');
  if(!held.files.some(file=>file.id===item.id))held.files.push({id:item.id,location:'local',filename:item.title||url,state:item.text?'ready':'pending',chars:0,note:'',link:url,role:held.role||'material',library:true,kept:true});
  return item;
}
// A sheet of sources: on the start (added to the start's files) or on the desk (Add a source).
function sDeskSourcesSheet(held,where){
  const desk=where==='desk',adding=desk?(held.adding||(held.adding={files:[],role:'material',keep:true,link:'',style:held.view.style?.style_id||''})):held;
  const problem=sNode('p','sheet-error');problem.setAttribute('role','alert');
  const again=()=>sDeskSourcesSheet(held,where);
  let done;
  const files=sDeskWithLink(sFilesCard(adding,problem,again,locked=>{if(done)done.disabled=locked||!access.actions.edit;}),adding,problem,again);
  if(desk)done=sButton('Add to this draft',async button=>{
    const ready=adding.files.filter(file=>file.state==='ready');if(!ready.length){problem.textContent='Add a file, a link, a Google Doc or a library post with text first.';return;}
    await busy(button,'Adding…',async()=>{try{await sDeskFlush(held);const before=held.view;held.view=await api('desk-sources',{id:held.id,sources:sDeskUploads(ready),library:sDeskLibraryPicks(ready)});held.adding=null;sCloseSheet();sToast(ready.length===1?'Added. Later rewrites read it.':'Added. Later rewrites read them.');sDeskRefresh(held,before);}catch(error){problem.textContent=error.message;}});
  },'filled');
  else done=sButton('Done',()=>{sCloseSheet();sDeskStartAgain(held);},'filled');
  done.disabled=!access.actions.edit;
  sOpenSheet(desk?'Add a source':'Sources',sNode('p','quiet',desk?'Files, links, Google Docs and team library posts, each with its role. Later rewrites read them; nothing already written changes.':'Files, links, Google Docs and team library posts, each with its role. The angles read them, and so does the writing.'),files,problem,sAdd(sNode('div','bar'),done,sButton('Cancel',sCloseSheet)));
}

// The desk.
async function sDesk(ident){
  const turn=studio.turn;
  const view=await api('desk?id='+encodeURIComponent(ident));if(turn!==studio.turn)return;
  const held=studio.desk&&studio.desk.id===ident?studio.desk:(studio.desk={id:ident,session:operationId()});
  // Coming back reads the desk afresh: nothing typed before leaving is saved over it.
  for(const pending of Object.values(held.pending||{}))if(pending?.timer&&typeof clearTimeout==='function')clearTimeout(pending.timer);
  held.view=view;held.pending={};held.stale=false;held.outline=null;
  if(sDeskStarting(view))return sDeskProgress(held);
  if(!held.tab)held.tab=view.start?.open==='outline'&&!sDeskHasText(view)?'outline':'draft';
  sDeskRender(held);
  sDeskWatch(held);
}
function sDeskStarting(view){return !!view?.start&&!view.start.ended_at;}
function sDeskHasText(view){return !!view.opening||(view.sections||[]).some(section=>section.text);}

// A start under way: nothing is needed from the person; the draft opens on its own.
function sDeskElapsed(start){const then=Date.parse(start.started_at||'');return then?Math.max(0,(Date.now()-then)/60000):0;}
function sDeskMinutesLeft(start){const left=Math.max(1,Math.round((start.minutes||1)-sDeskElapsed(start)));return left+(left===1?' minute':' minutes');}
function sDeskClock(start){const minutes=Math.floor(sDeskElapsed(start));return (minutes<1?'Under a minute':minutes+' min')+' so far, for the whole start.';}
function sDeskProgress(held){
  const view=held.view,start=view.start,problem=start.problem,what=start.open==='outline'?'The outline':'The draft';
  const stop=start.busy?sButton('Stop',async button=>{await busy(button,'Stopping…',async()=>{try{held.view=await api('desk-stop',{id:held.id,job:start.job});sDeskProgress(held);}catch(error){notice(error.message,true);}});}):null;
  if(stop)stop.disabled=!access.actions.edit;
  sFrame(view.title,[stop],problem?'Stopped':'Writing on its own',()=>sRoute('blogs'));
  const first=sNode('p','lede',problem?'This start stopped before '+what.toLowerCase()+' was ready. Retry the step when you are ready.':'Nothing needed from you. '+what+' opens here when it is ready, in about '+sDeskMinutesLeft(start)+'.');
  first.setAttribute('role','status');
  const steps=sNode('ol','rows desk-steps'),at=start.steps.indexOf(start.step);steps.setAttribute('aria-label','Steps of this start');
  start.steps.forEach((step,index)=>{
    const state=index<at?'done':index===at?(problem?'late':'current'):'none';
    const now=index===at&&!problem?(start.phase||(start.status==='queued'?'Reading your sources':'Under way')):'';
    steps.append(sAdd(sNode('li','row step'),sBead(state),sAdd(sNode('div','row-text'),sNode('h3','row-title',DESK_STEPS[step]||step),now?sNode('p','row-says',now):null)));
  });
  const parts=[first];
  if(problem){const retry=sButton('Retry',async button=>{await busy(button,'Starting…',async()=>{try{held.view=await api('desk-retry',{id:held.id});sDeskProgress(held);}catch(error){notice(error.message,true);}});},'filled');retry.disabled=!access.actions.edit;parts.push(sAdd(sNode('div','decision-notice desk-problem'),sNode('p','',problem),retry));}
  parts.push(sCard('Progress',steps,sNode('p','quiet desk-clock',sDeskClock(start))));
  sPage(...parts);
  if(!problem)sDeskFollowStart(held);
}
function sDeskFollowStart(held){
  if(held.startWatching)return;held.startWatching=true;
  setTimeout(async()=>{
    held.startWatching=false;if(!sDeskCurrent(held))return;
    try{
      const view=await api('desk?id='+encodeURIComponent(held.id));if(!sDeskCurrent(held))return;held.view=view;
      if(sDeskStarting(view))return sDeskProgress(held);
      held.tab=view.start?.open==='outline'?'outline':'draft';held.outline=null;
      sDeskRender(held);sDeskWatch(held);sToast(held.tab==='outline'?'The outline is ready. Shape it here, then write the draft.':'The draft is ready. Edit it here.');
    }catch(error){notice(error.message,true);sDeskFollowStart(held);}
  },DESK_POLL);
}
function sDeskCurrent(held){return studio.screen==='desk'&&studio.desk===held;}
// Whether the job under way changes this part: its own section, or every section.
function sDeskWorkingIn(view,part){const job=view?.working;if(!job)return false;return job.part===part||job.part==='sections'&&part!=='title'&&part!=='opening';}
function sDeskWorking(held,part){return sDeskWorkingIn(held.view,part);}
function sDeskStatusWords(held){const job=held.view.working;if(!job)return '';if(job.kind==='desk-revise-all'&&job.total)return 'Revising section '+(job.index+1)+' of '+job.total+'…';return (DESK_DOING[job.kind]||'Working')+(job.kind==='desk-section'||job.kind==='desk-selection'?' '+deskPartName(held.view,job.part):'')+'…';}
function sDeskTabs(held){return sChoice('Work on',[['draft','Draft'],['outline','Outline']],held,'tab',async()=>{await sDeskOutlineFlush(held);held.outline=null;sDeskRender(held);});}
function sDeskToolbar(held){
  const view=held.view,editable=access.actions.edit;
  const copy=sButton('Copy',async()=>{if(typeof navigator==='undefined'||!navigator.clipboard?.writeText)throw new Error('Download the draft and copy it from there.');await navigator.clipboard.writeText(held.view.markdown);sToast('Markdown copied.');});
  const download=sButton('Download',()=>sDownload({content:held.view.markdown,name:'DRAFT.md'}));
  const google=view.google?.url?link(view.google.url,'Google Doc ↗'):null;if(google)google.className='button';
  const publish=sButton(view.publication?'Published':'Mark as published',()=>sDeskPublish(held));publish.disabled=!editable;
  const finishing=sButton('Finishing',()=>{});finishing.disabled=true;finishing.title='Finishing tools arrive in a later update.';
  const stop=held.view.working?sButton('Stop',async button=>{await busy(button,'Stopping…',async()=>{const before=held.view;held.view=await api('desk-stop',{id:held.id,job:held.view.working.id});sDeskRefresh(held,before);});}):null;
  sFrame(view.title,sFold([stop,copy,download,google,publish,finishing]),held.view.working?sDeskStatusWords(held):'On the desk',()=>sRoute('blogs'));
}
function sDeskRender(held){
  const view=held.view;sDeskToolbar(held);
  const status=sNode('p','quiet desk-save-state');status.setAttribute('role','status');status.setAttribute('aria-live','polite');held.status=status;
  if(held.stale)sDeskStale(held);else status.textContent=held.saved||'Changes save as you type.';
  const column=sNode('div','desk-column');held.tab=held.tab||'draft';held.shownTab=held.tab;
  held.problemSlot=sNode('div','desk-problem-slot');const problem=sDeskProblem(held);if(problem)held.problemSlot.append(problem);
  held.cards={};
  if(held.tab==='outline'){held.wholeCard=null;column.append(held.problemSlot,...sDeskOutline(held));}
  else{
    held.wholeCard=sDeskWhole(held);
    for(const part of ['title','opening',...view.sections.map(section=>section.id)])held.cards[part]=sDeskPart(held,part);
    column.append(held.problemSlot,held.wholeCard,...Object.values(held.cards));
    if(!view.sections.length)column.append(sCard('No sections yet',sNode('p','','This draft has no ## headings, so it is one opening. Add headings in the text, or add sections on the Outline tab.')));
  }
  held.bar=sDeskSelectionBar(held);held.aside=sDeskAside(held);
  const lede=held.tab==='outline'?'Rename, reorder, add and remove sections and say what each must do. Write the draft from the outline, or one section at a time.':'Edit any part in place, give a section a note to rewrite it, or select text for a quick change. Every change keeps the earlier text in History.';
  sPage(sNode('p','lede',lede),status,sDeskTabs(held),sAdd(sNode('div','desk-layout'),column,held.aside),held.bar);
}
// After a job starts, moves on or ends: redraw only the cards it changed, so the part the
// person is typing in keeps its focus and caret.
function sDeskRefresh(held,before){
  const view=held.view,order=found=>(found?.sections||[]).map(section=>section.id).join(',');
  if(held.tab==='outline'||held.shownTab!==held.tab){if(held.outlineTimer&&sDeskCurrent(held)){sDeskToolbar(held);const aside=sDeskAside(held);held.aside.replaceWith(aside);held.aside=aside;return;}held.outline=null;return sDeskRender(held);}
  if(!held.cards||!before||order(before)!==order(view)||!sDeskCurrent(held))return sDeskRender(held);
  sDeskToolbar(held);
  held.problemSlot.replaceChildren(...[sDeskProblem(held)].filter(Boolean));
  const whole=sDeskWhole(held);if(held.wholeCard)held.wholeCard.replaceWith(whole);held.wholeCard=whole;
  const focused=typeof document.activeElement==='object'?document.activeElement:null;
  for(const part of Object.keys(held.cards)){
    const was=sDeskWorkingIn(before,part),now=sDeskWorking(held,part),old=held.cards[part];
    const changed=was!==now||deskTextOf(before,part)!==deskTextOf(view,part)||(before.versions||{})[part]!==(view.versions||{})[part];
    const typing=focused&&typeof old.contains==='function'&&old.contains(focused);
    if(changed&&(!typing||was||now)){const card=sDeskPart(held,part);old.replaceWith(card);held.cards[part]=card;}
  }
  const aside=sDeskAside(held);held.aside.replaceWith(aside);held.aside=aside;
}
// What the last job left: a result not applied, or a job that failed.
function sDeskProblem(held){
  const last=(held.view.jobs||[]).at(-1);if(!last||held.dismissed===last.id)return null;
  const chain=held.view.chain;
  if(last.chain&&chain){if(chain.working||!chain.problems.length)return null;return sAdd(sNode('div','decision-notice desk-problem'),sAdd(sNode('div',''),sNode('p','','Revised '+chain.revised+' of '+chain.total+' sections for your note. These were not:'),sAdd(sNode('ul','gap-items'),...chain.problems.map(problem=>sNode('li','','“'+problem.heading+'”: '+problem.error)))),sButton('Dismiss',()=>{held.dismissed=last.id;sDeskRender(held);}));}
  const failed=last.status==='failed'||last.status==='ready'&&last.applied===false;if(!failed||!last.error)return null;
  return sAdd(sNode('div','decision-notice desk-problem'),sNode('p','',(last.status==='failed'?'The last change could not finish: ':'The last change was not applied: ')+last.error),sButton('Dismiss',()=>{held.dismissed=last.id;sDeskRender(held);}));
}
function sDeskWhole(held){
  const card=sCard('Note for the whole draft');
  const box=sNode('textarea','input');box.id='desk-whole-note';box.rows=2;box.maxLength=4000;box.setAttribute('aria-label','Note for the whole draft');box.value=held.wholeNote||'';box.placeholder='For example: tighten throughout, or make it more casual.';
  box.addEventListener('input',()=>{held.wholeNote=box.value;});
  const go=sButton('Revise the draft',async button=>{const text=(held.wholeNote||'').trim();if(!text){notice('Write the note for the whole draft.',true);return;}await sDeskJob(held,button,'desk-revise',{note:text},()=>{held.wholeNote='';});},'filled');
  go.disabled=!access.actions.edit||!!held.view.working;
  return sAdd(card,box,sNode('p','quiet field-hint','Each section is revised for the note with the whole draft in view. Your text is kept as a version first.'),sAdd(sNode('div','bar'),go));
}
function sDeskPart(held,part){
  const view=held.view,section=(view.sections||[]).find(row=>row.id===part),working=sDeskWorking(held,part);
  const card=sNode('section','card desk-part'+(working?' desk-working':''));card.dataset.part=part;
  const heading=sNode('h2','card-title',part==='title'?'Title':part==='opening'?'Opening':section.heading);
  const count=(view.versions||{})[part]||0,history=sButton(count?'History ('+count+')':'History',()=>sDeskHistory(held,part));history.disabled=!count;
  card.append(sAdd(sNode('div','desk-part-head'),heading,history));
  const text=held.pending[part]?.text??deskTextOf(view,part);
  const input=sNode(part==='title'?'input':'textarea','input desk-text');input.value=text;input.setAttribute('aria-label',part==='title'?'Title':part==='opening'?'Opening':'Text of '+section.heading);
  if(part==='title'){input.type='text';input.maxLength=500;}else{input.rows=Math.min(24,Math.max(3,Math.ceil(text.length/90)+text.split('\n').length));}
  input.readOnly=working||!access.actions.edit;
  input.addEventListener('input',()=>sDeskTyped(held,part,input.value));
  if(part!=='title'){for(const kind of ['select','mouseup','keyup'])input.addEventListener(kind,()=>sDeskSelected(held,part,input));}
  else input.addEventListener('select',()=>sDeskSelected(held,part,input));
  card.append(input);
  if(working){const note=sNode('p','desk-working-note','Working on this section');note.setAttribute('role','status');card.append(note);if(view.working.note)card.append(sNode('p','quiet','Your note: '+view.working.note));}
  if(section){
    const typed=(held.notes||{})[part]||'',row=sNode('div','desk-note');
    const box=sNode('input','input');box.type='text';box.maxLength=4000;box.value=typed;box.placeholder='How should this change?';box.setAttribute('aria-label','How should '+section.heading+' change?');
    const go=sButton(typed.trim()?'Rewrite':'Write again',async button=>{const note=((held.notes||{})[part]||'').trim();await sDeskJob(held,button,'desk-note',{part,note},()=>{if(held.notes)delete held.notes[part];});});
    go.disabled=!access.actions.edit||!!view.working;
    box.addEventListener('input',()=>{held.notes=held.notes||{};held.notes[part]=box.value;go.textContent=box.value.trim()?'Rewrite':'Write again';});
    card.append(sAdd(row,box,go));
  }
  return card;
}
function sDeskAside(held){
  const view=held.view,aside=sNode('aside','desk-aside');aside.setAttribute('aria-label','Sources and gaps');
  const sources=sCard('Sources');
  if((view.source_names||[]).length){const list=sNode('ul','rows');for(const source of view.source_names)list.append(sAdd(sNode('li','row'),sNode('span','row-title',source.name)));sources.append(list);}
  else sources.append(sNode('p','quiet','No sources were given for this draft. Rewrites keep to what the draft already says.'));
  const add=sButton('Add a source',()=>sDeskSourcesSheet(held,'desk'));add.disabled=!access.actions.edit;sources.append(sAdd(sNode('div','bar'),add));
  if(view.style_name)sources.append(sNode('p','quiet','Kind of post: '+view.style_name));
  if(view.tone)sources.append(sNode('p','quiet','Tone: '+view.tone));
  aside.append(sources);
  const gaps=view.gaps||[];
  const list=sNode('ul','gap-items');for(const gap of gaps)list.append(sNode('li','',gap));
  aside.append(sAdd(sNode('section','paper aside-part'),sNode('h2','aside-title','Needs you before publishing'),gaps.length?list:sNode('p','quiet','Nothing yet. What a rewrite cannot support from your sources is listed here, never in the text.')));
  if(view.run)aside.append(sAdd(sNode('p','quiet'),sButton('Open the step-by-step run',()=>sRoute('run',view.id))));
  if(!sNarrow())return aside;
  // On a phone the sources and gaps fold under the draft.
  const folded=disclosure('Sources and what needs you'+(gaps.length?' ('+gaps.length+')':''),...aside.children);folded.className='desk-aside desk-aside-folded';return folded;
}

// Saving as you type: one second after the last keystroke, against the revision last seen.
function sDeskTyped(held,part,text){
  held.pending[part]={text,timer:held.pending[part]?.timer};
  if(held.pending[part].timer&&typeof clearTimeout==='function')clearTimeout(held.pending[part].timer);
  held.pending[part].timer=setTimeout(()=>sDeskSave(held,part),DESK_SAVE_WAIT);
  if(held.status)held.status.textContent='Saving…';
}
async function sDeskSave(held,part){
  if(!held.pending[part]||held.stale)return;
  while(held.saving)await held.saving;  // One save at a time, each against the latest revision.
  const pending=held.pending[part];if(!pending||held.stale)return;
  const text=pending.text;
  held.saving=(async()=>{try{
    const view=await api('desk-save',{id:held.id,seen:held.view.revision,part,text,session:held.session});
    if(held.pending[part]?.text===text)delete held.pending[part];
    const before=held.view;held.view=view;held.saved='Saved.';
    if(held.status&&!held.stale)held.status.textContent='Saved.';
    sDeskCounts(held);
    if(!!before.working!==!!view.working&&sDeskCurrent(held))sDeskRefresh(held,before);
  }catch(error){
    if(/changed since/.test(error.message)){held.stale=true;sDeskStale(held);}
    else if(held.status)held.status.textContent=error.message+' Your text is kept here.';
  }finally{held.saving=null;}})();
  await held.saving;
  if(held.pending[part]&&held.pending[part].text!==text&&!held.stale)return sDeskSave(held,part);
}
async function sDeskFlush(held){for(const part of Object.keys(held.pending)){if(held.pending[part]?.timer&&typeof clearTimeout==='function')clearTimeout(held.pending[part].timer);await sDeskSave(held,part);}}
function sDeskCounts(held){for(const card of $('studio-page').querySelectorAll('.desk-part')){const count=(held.view.versions||{})[card.dataset.part]||0,button=card.querySelectorAll('button')[0];if(button&&/^History/.test(button.textContent)){button.textContent=count?'History ('+count+')':'History';button.disabled=!count;}}}
function sDeskStale(held){
  if(!held.status)return;held.status.className='desk-save-state decision-notice desk-stale';held.status.replaceChildren(sNode('span','','This draft changed in another window or job. Reload to see the latest; your unsaved text is shown until you do. '),sButton('Reload',async()=>{held.pending={};held.stale=false;held.saved='';await sDesk(held.id);},'filled'));
}

// Leaving the desk, or hiding its tab, shares the edits typing kept on this computer.
// keepalive lets the request finish while the tab goes away.
async function sDeskShare(held){if(!held)return;try{await sDeskFlush(held);await fetch('/api/desk-share',{method:'POST',keepalive:true,headers:{'X-Blog-Studio-Token':token,'Content-Type':'application/json'},body:JSON.stringify({id:held.id})});}catch(_){/* Shared with the next change instead. */}}

// Notes and selection edits start a job; the desk follows it until it ends.
async function sDeskJob(held,button,route,data,done){
  await busy(button,'Starting…',async()=>{try{
    await sDeskFlush(held);await sDeskOutlineFlush(held);if(held.stale)return;
    const before=held.view;held.view=await api(route,{id:held.id,seen:held.view.revision,...data});if(done)done();
    sDeskRefresh(held,before);sDeskWatch(held);
  }catch(error){if(/changed since/.test(error.message)){held.stale=true;sDeskStale(held);}else notice(error.message,true);}});
}
function sDeskWatch(held){
  if(!held.view.working||held.watching)return;held.watching=true;
  const follow=async()=>{
    if(!sDeskCurrent(held)){held.watching=false;return;}
    try{await sDeskFlush(held);const view=await api('desk?id='+encodeURIComponent(held.id));if(!sDeskCurrent(held)){held.watching=false;return;}
      const ended=!view.working,before=held.view;held.view=view;sDeskRefresh(held,before);
      if(ended){held.watching=false;const last=(view.jobs||[]).at(-1);if(last?.applied)sToast('Done. The earlier text is in History.');return;}
    }catch(error){if(held.status)held.status.textContent=error.message;}
    setTimeout(follow,DESK_POLL);
  };
  setTimeout(follow,DESK_POLL);
}

// A small bar for the selected passage: Rephrase, Shorten, Expand, Fix and Ask….
function sDeskSelected(held,part,input){
  // The selection without the spaces around it, and where it starts in the saved text (the
  // server keeps a part without its leading spaces), so a repeated word is the one chosen.
  const value=input.value;let start=input.selectionStart,end=input.selectionEnd;
  if(typeof start!=='number'||typeof end!=='number')start=end=0;
  while(start<end&&/\s/.test(value[start]))start++;while(end>start&&/\s/.test(value[end-1]))end--;
  const text=value.slice(start,end),lead=value.length-value.replace(/^\s+/,'').length;
  if(!text||held.view.working||!access.actions.edit){if(held.bar&&!held.asking)held.bar.hidden=true;return;}
  held.selection={part,text,start:start-lead};held.asking=false;sDeskBarContent(held);held.bar.hidden=false;
}
function sDeskSelectionBar(held){const bar=sNode('div','desk-selection glass');bar.setAttribute('role','toolbar');bar.setAttribute('aria-label','Change the selected text');bar.hidden=true;held.bar=bar;sDeskBarContent(held);return bar;}
function sDeskBarContent(held){
  const bar=held.bar;if(!bar)return;
  const run=(action,instruction='')=>async button=>{const chosen=held.selection;if(!chosen)return;await sDeskJob(held,button,'desk-selection',{part:chosen.part,text:chosen.text,start:chosen.start,action,...(action==='ask'?{instruction}:{})},()=>{held.selection=null;held.asking=false;});};
  if(held.asking){
    const box=sNode('input','input');box.type='text';box.maxLength=2000;box.placeholder='What should change?';box.setAttribute('aria-label','What should change in the selected text?');
    bar.replaceChildren(box,sButton('Go',async button=>{const instruction=box.value.trim();if(!instruction){notice('Say what to do with the passage.',true);return;}await run('ask',instruction)(button);},'filled'),sButton('Cancel',()=>{held.asking=false;bar.hidden=true;}));
    return;
  }
  bar.replaceChildren(...DESK_SELECTION.map(([action,label])=>sButton(label,run(action))),sButton('Ask…',()=>{held.asking=true;sDeskBarContent(held);}));
}

// History: each kept version with its words compared to the current text, and Restore.
async function sDeskHistory(held,part){
  await sDeskFlush(held);
  const found=await api('desk-versions?'+new URLSearchParams({id:held.id,part}));
  const current=deskTextOf(held.view,part),list=sNode('div','desk-versions'),compare=sNode('div','desk-compare-area');
  found.versions.forEach((version,index)=>{
    const row=sAdd(sNode('div','desk-version'),sAdd(sNode('div','row-text'),sNode('h3','row-title',DESK_SOURCES[version.source]||'Earlier text'),sNode('p','quiet',[deskAge(version.at),version.words+(version.words===1?' word':' words')].filter(Boolean).join(' · '))));
    const restore=sButton('Restore',async button=>{await busy(button,'Restoring…',async()=>{try{held.view=await api('desk-restore',{id:held.id,seen:held.view.revision,part,index});delete held.pending[part];sCloseSheet();sToast('Restored. The text it replaced is in History.');sDeskRender(held);}catch(error){if(/changed since/.test(error.message)){sCloseSheet();held.stale=true;sDeskStale(held);}else notice(error.message,true);}});});
    restore.disabled=!access.actions.edit||!!held.view.working;
    row.append(sAdd(sNode('div','bar'),sButton('Compare',()=>{compare.replaceChildren(sNode('h3','sheet-part','This version compared with now'),sNode('p','quiet','Struck words are in this version only; marked words were added since.'),deskCompare(version.text,current));}),restore));
    list.append(row);
  });
  sOpenSheet('History of '+deskPartName(held.view,part),found.versions.length?list:sNode('p','','Nothing kept yet.'),compare);
}

// Mark as published: where it went, said by the person. Nothing is posted.
function sDeskPublish(held){
  const draft={url:held.view.publication||''},problem=sNode('p','sheet-error');problem.setAttribute('role','alert');
  const save=sButton('Mark as published',async button=>{const url=draft.url.trim();if(!/^https:\/\/\S+$/.test(url)){problem.textContent='Add the public https address where it was published.';return;}await busy(button,'Saving…',async()=>{try{await sDeskFlush(held);await api('schedule',{id:held.id,expected:held.view.expected,stage:'published',confirm_stage:true,publication_url:url});sCloseSheet();sToast('Recorded as published. Nothing was posted anywhere.');await sDesk(held.id);}catch(error){problem.textContent=error.message;}});},'filled');
  sOpenSheet('Mark as published',sNode('p','','Record where this blog was published. The current text is the published one.'),sField('desk-publication','Public address',draft,'url',{max:2000,required:true}),problem,sAdd(sNode('div','bar'),save,sButton('Cancel',sCloseSheet)));
}

// A finished step-by-step blog once it is on the desk: its run is read as it ended, with
// nothing to resume, approve or ask for; the desk is where it is edited now.
function sRunOnDesk(found){
  studio.found=found;studio.signature=JSON.stringify(found);
  const open=sButton('Open on the desk',()=>sRoute('desk',found.id),'filled');
  sFrame(found.title,[open],'Writing run',()=>sRoute('blogs'));
  const steps=sNode('ol','rows');for(const row of found.stages||[])steps.append(sAdd(sNode('li','row step'),sBead('done'),sAdd(sNode('div','row-text'),sNode('h3','step-name',row.label))));
  sPage(sCard('This blog is on the writing desk',sNode('p','','It was finished here and then opened on the desk, where its notes, selection edits and versions are. This run is kept as it ended, to read.')),disclosure('How it was written',steps));
}

// The Outline tab: each section's heading and brief, in order, saved as they are edited with
// the stale check; reordering keeps each section's id, so its text and History go with it.
function sDeskOutlineRows(held){return held.outline||(held.outline=(held.view.sections||[]).map(section=>({id:section.id,heading:section.heading,brief:section.brief||''})));}
function sDeskOutline(held){
  const view=held.view,rows=sDeskOutlineRows(held),editable=access.actions.edit,whole=!!view.working;
  const write=sButton('Write the draft',button=>sDeskWriteDraft(held,button),'filled');write.disabled=!editable||whole||!rows.length;
  const add=sButton('Add a section',()=>sDeskOutlineChange(held,rows=>rows.push({heading:'New section',brief:''})));add.disabled=!editable;
  const head=sCard('Outline',sNode('p','','Each brief says what its section must do. The draft is written from the outline, section by section, with your sources.'),sAdd(sNode('div','bar'),write,add));
  const cards=rows.map((row,index)=>sDeskOutlineCard(held,row,index,rows.length));
  if(!rows.length)cards.push(sCard('No sections yet',sNode('p','','Add a section to start the outline.')));
  return [head,...cards];
}
function sDeskOutlineCard(held,row,index,count){
  const view=held.view,section=(view.sections||[]).find(found=>found.id===row.id),working=!!row.id&&sDeskWorking(held,row.id),editable=access.actions.edit&&!working;
  const card=sNode('section','card desk-part desk-outline-part'+(working?' desk-working':''));if(row.id)card.dataset.part=row.id;
  const words=section?.text?section.text.split(/\s+/).filter(Boolean).length:0;
  card.append(sAdd(sNode('div','desk-part-head'),sNode('h2','card-title','Section '+(index+1)),sNode('span','quiet',words?words+(words===1?' word written':' words written'):'Not written yet')));
  const heading=sField('desk-outline-heading-'+index,'Heading',row,'heading',{max:200,changed:()=>sDeskOutlineTyped(held)}),brief=sField('desk-outline-brief-'+index,'What it must do',row,'brief',{long:true,max:4000,changed:()=>sDeskOutlineTyped(held)});
  for(const box of [heading,brief])box.querySelector(box===heading?'input':'textarea').readOnly=!editable;
  card.append(heading,brief);
  if(working){const note=sNode('p','desk-working-note','Working on this section');note.setAttribute('role','status');card.append(note);}
  const name=row.heading||'this section',move=(by,label)=>{const button=sButton(label,()=>sDeskOutlineChange(held,rows=>{const [moved]=rows.splice(index,1);rows.splice(index+by,0,moved);}));button.setAttribute('aria-label',label+' · '+name);button.disabled=!access.actions.edit||index+by<0||index+by>=count;return button;};
  const remove=sButton('Remove',()=>{const gone=rows=>rows.splice(index,1);if(!words)return sDeskOutlineChange(held,gone);const confirm=sButton('Remove the section',async button=>{await busy(button,'Removing…',async()=>{sCloseSheet();await sDeskOutlineChange(held,gone);});},'danger');sOpenSheet('Remove “'+name+'”?',sNode('p','','Its '+words+(words===1?' word goes':' words go')+' with it, and its History.'),sAdd(sNode('div','bar'),confirm,sButton('Cancel',sCloseSheet)));});
  remove.setAttribute('aria-label','Remove '+name);remove.disabled=!access.actions.edit||working;
  const write=sButton(words?'Write it again':'Write this section',async button=>{await sDeskJob(held,button,'desk-note',{part:row.id,note:''});});
  write.disabled=!access.actions.edit||!!view.working||!row.id;
  card.append(sAdd(sNode('div','bar'),move(-1,'Move up'),move(1,'Move down'),remove,write));
  return card;
}
function sDeskOutlineTyped(held){
  if(held.outlineTimer&&typeof clearTimeout==='function')clearTimeout(held.outlineTimer);
  held.outlineTimer=setTimeout(()=>sDeskOutlineSave(held),DESK_SAVE_WAIT);
  if(held.status)held.status.textContent='Saving…';
}
async function sDeskOutlineFlush(held){if(held.outlineTimer)await sDeskOutlineSave(held);}
async function sDeskOutlineChange(held,change){await sDeskFlush(held);change(sDeskOutlineRows(held));await sDeskOutlineSave(held,true);}
async function sDeskOutlineSave(held,redraw=false){
  if(held.outlineTimer&&typeof clearTimeout==='function')clearTimeout(held.outlineTimer);held.outlineTimer=null;
  if(held.stale||!held.outline)return;
  while(held.saving)await held.saving;
  const rows=held.outline.map(row=>({...(row.id?{id:row.id}:{}),heading:row.heading,brief:row.brief}));
  if(rows.some(row=>!row.heading.trim())){if(held.status)held.status.textContent='Give each section a heading; it saves once it has one.';return;}
  held.saving=(async()=>{try{
    held.view=await api('desk-outline-save',{id:held.id,seen:held.view.revision,sections:rows});
    held.saved='Saved.';if(held.status)held.status.textContent='Saved.';
    if(redraw||rows.some(row=>!row.id)){held.outline=null;if(sDeskCurrent(held))sDeskRender(held);}
  }catch(error){
    if(/changed since/.test(error.message)){held.stale=true;sDeskStale(held);}
    else if(held.status)held.status.textContent=error.message+' Your outline is kept here.';
  }finally{held.saving=null;}})();
  await held.saving;
}
async function sDeskWriteDraft(held,button){
  const go=async pressed=>{await sDeskOutlineFlush(held);await sDeskJob(held,pressed,'desk-draft',{},()=>{held.tab='draft';held.outline=null;});};
  if(!sDeskHasText(held.view))return go(button);
  const confirm=sButton('Write the draft',async pressed=>{sCloseSheet();await go(pressed);},'filled');
  sOpenSheet('Write the whole draft?',sNode('p','','Every section is written from its brief, and the opening too. The text there now is kept in History first.'),sAdd(sNode('div','bar'),confirm,sButton('Cancel',sCloseSheet)));
}
