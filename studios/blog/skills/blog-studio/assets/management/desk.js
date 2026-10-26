// The writing desk: one page per blog with a card for each part, notes that rewrite a
// section, selection edits and quiet version history. Built with runner.js's helpers; every
// text from the draft is set with textContent.
'use strict';
const DESK_SELECTION=[['rephrase','Rephrase'],['shorten','Shorten'],['expand','Expand'],['fix','Fix']];
const DESK_SOURCES={save:'Before your edit',rewrite:'Before a rewrite','revise-all':'Before a whole-draft revision',selection:'Before a selection edit','first-pass':'Before the first pass',finishing:'Before a finishing change',restore:'Before a restore',draft:'Before the draft was written',chat:'Before an edit in chat',google:'Before Google’s accepted text'};
const DESK_DOING={'desk-section':'Rewriting','desk-revise-all':'Revising the whole draft','desk-selection':'Editing a passage','desk-first-pass':'Working on the first pass','desk-outline':'Outlining','desk-draft':'Writing the draft','desk-research':'Researching','finish-copyedit':'Copy editing the draft','finish-humanize':'Finding sentences to humanize','finish-facts':'Checking facts against your sources','finish-headline':'Suggesting headlines and openings','finish-feedback':'Reading the draft for feedback','finish-voice':'Rewriting the draft in a voice guide'};
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
function deskPartName(view,part){if(part==='title')return 'the title';if(part==='opening')return 'the opening';if(part==='sections')return 'every section';const found=(view.sections||[]).find(section=>section.id===part);return found?'“'+deskHeading(found.heading)+'”':'a section';}
function deskTextOf(view,part){if(part==='title'||part==='opening')return view[part]||'';return (view.sections||[]).find(section=>section.id===part)?.text||'';}

// Images: a part's text holds only its short reference, ![][image1], as typed. The desk view
// lists the images by key without their data; the page reads the data once (desk-images),
// keeps it here, shows a thumbnail under each part that refers to one, and writes the images
// back at the end for Copy and Download. No form field or autosave ever holds the data.
const DESK_IMAGE_REF=/!\[([^\[\]\n]*)\]\[([^\[\]\n]*)\]/g;
function deskImageLabel(label){return String(label||'').split(/\s+/).filter(Boolean).join(' ').toLowerCase();}
function deskImageData(){return studio.deskImages||(studio.deskImages={});}
function deskImagesIn(view,text){
  const listed=view.images||[],out=[],seen=new Set();
  for(const found of String(text||'').matchAll(DESK_IMAGE_REF)){
    const label=deskImageLabel(found[2]||found[1]),image=listed.find(item=>deskImageLabel(item.label)===label);
    if(image&&!seen.has(image.key)){seen.add(image.key);out.push({...image,alt:found[2]?found[1]:''});}
  }
  return out;
}
// The images a part's text names that are kept nowhere, each once.
function deskImagesMissing(view,text){
  const lost=(view.missing_images||[]).map(deskImageLabel),out=[];
  for(const found of String(text||'').matchAll(DESK_IMAGE_REF)){const label=found[2]||found[1];if(lost.includes(deskImageLabel(label))&&!out.some(name=>deskImageLabel(name)===deskImageLabel(label)))out.push(label);}
  return out;
}
function sDeskThumbs(held,part){return sDeskThumbsFor(held.view,deskTextOf(held.view,part));}
function sDeskThumbsFor(view,text){
  const found=deskImagesIn(view,text),lost=deskImagesMissing(view,text);if(!found.length&&!lost.length)return null;
  const row=sNode('div','desk-images');row.setAttribute('aria-label','Images in this part');
  for(const image of found){
    const img=sNode('img','desk-thumb');img.alt=image.alt||'Image '+image.label;img.dataset.key=image.key;
    const data=deskImageData()[image.key];if(data)img.src=data;
    row.append(sAdd(sNode('figure','desk-image'),img,sNode('figcaption','quiet',image.label)));
  }
  // Named in the text, kept nowhere: said in its place, so the reference can be fixed or cut.
  for(const label of lost)row.append(sAdd(sNode('figure','desk-image desk-image-missing'),sNode('span','desk-thumb-missing','Image missing'),sNode('figcaption','quiet',label)));
  return row;
}
// Read the images not kept yet, once, then fill the thumbnails waiting for them.
async function sDeskImagesLoad(held){
  if(!(held.view.images||[]).some(image=>!deskImageData()[image.key]))return;
  if(held.imagesLoading)return held.imagesLoading;
  held.imagesLoading=(async()=>{try{
    const found=await api('desk-images?'+new URLSearchParams({id:held.id}));
    for(const image of found.images||[])deskImageData()[image.key]=image.uri;
    for(const img of $('studio-page').querySelectorAll('.desk-thumb')){const data=deskImageData()[img.dataset.key];if(data&&!img.src)img.src=data;}
  }catch(_){/* The thumbnails wait; Copy and Download ask again. */}finally{held.imagesLoading=null;}})();
  return held.imagesLoading;
}
// The Markdown as DRAFT.md keeps it: the text, then each image it refers to. An image whose
// data cannot be read is left out and named, never stopping Copy or Download.
async function sDeskMarkdown(held){
  const view=held.view,images=view.images||[],missing=[...(view.missing_images||[])];if(!images.length)return {markdown:view.markdown,missing};
  await sDeskImagesLoad(held);
  const lines=[];for(const image of images){const data=deskImageData()[image.key];if(data)lines.push('['+image.label+']: <'+data+'>'+(image.title?' '+image.title:''));else missing.push(image.label);}
  return {markdown:lines.length?view.markdown.replace(/\n$/,'')+'\n\n'+lines.join('\n\n')+'\n':view.markdown,missing};
}
function deskWithout(done,missing){return missing.length?done+' without '+missing.join(', ')+(missing.length===1?': its image could not be read.':': their images could not be read.'):done+'.';}

// A new blog: 1. the kind of post, 2. sources and settings, 3. what the person brings (a
// topic, an outline or notes, or a draft), then Start. Nothing stops for the person after it.
// A draft to polish or review is one screen instead (sDeskPolish), with no kind of post.
const DESK_HAVE=[['topic','A topic'],['outline','An outline or notes'],['draft','A draft']];
const DESK_OUTLINE_WAYS=[['outline','Write from my outline'],['shape','Shape an outline with me first']];
const DESK_START_STEPS=['Kind of post','Sources and settings','What you have'];
const DESK_START_LEDES=['Choose the kind of post. It sets the usual shape and length.','Add sources if you have them. They stay with this blog unless you keep them in the team library.','Say what you bring, then start. Nothing stops for you on the way.'];
// Settings' research for new blogs is where the start's ticks begin: Search my sites when it
// ticks your sites and the shared list has any, Search the web too when it ticks the public
// web. Your documents are always read. The person can change both for this blog.
function sDeskResearchDefault(value){const ticks=OLD_RESEARCH[value]||(value&&typeof value==='object'?value:{});return {searchSites:!!ticks.sites&&sSharedSites().length>0,searchWeb:!!ticks.web};}
function sDeskHeld(){
  if(studio.deskStart)return studio.deskStart;
  const defaults=studio.options?.settings?.defaults||{},preset=studio.deskPreset||{};studio.deskPreset=null;
  return studio.deskStart={step:0,kind:null,style:'',have:'topic',title:'',audience:'',point:'',angles:[],angle:null,angleOp:null,anglesBusy:false,anglesProblem:'',outline:'',outlineFrom:'paste',outlineFile:null,outlineWay:'outline',source:'paste',article:null,manuscript:'',url:'',file:null,preview:null,first_pass:null,files:[],role:'material',keep:false,from:{on:true,documents:true,sites:false,web:false,picked:[...sSharedSites()],added:[]},...sDeskResearchDefault(defaults.research),length:'style',tone:defaults.tone||'',operation:operationId(),upload:operationId(),...preset};
}
// Home's tasks, New blog, the library's "Write a blog from these", an interview's outline and
// a saved blog's details all start here.
function sDeskBegin(preset={}){studio.deskStart=null;studio.deskPreset=preset;return sRoute('desk-start');}
async function sDeskStart(){
  if(!studio.options)studio.options=await api('run-options');
  const held=sDeskHeld();
  if(held.have==='draft')return sDeskPolish(held);
  sFrame('New blog',[],'New writing',()=>sRoute('home'));
  const steps=sWorkflowSteps(DESK_START_STEPS,held.step,index=>{if(index&&held.kind===null)return notice('Choose a kind of post first, or Something else.',true);held.step=index;sTop();sDeskStart();});
  sPage(sNode('p','lede',DESK_START_LEDES[held.step]),steps,held.step===0?sDeskKinds(held):held.step===1?sDeskSettings(held):sDeskHave(held));
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

// 2. Sources and settings, for every way of working; research and length for new writing.
function sDeskSettings(held){
  // A refused role change is said here after the card is drawn again.
  const form=sNode('form','narrow desk-start'),problem=sNode('p','problem',held.problem||'');problem.setAttribute('role','alert');delete held.problem;
  const again=()=>sDeskStartAgain(held);
  const go=sNode('button','button button-filled','Continue');go.type='submit';go.disabled=studio.busy||!access.actions.edit;
  form.append(sFilesCard(held,problem,again,locked=>{go.disabled=locked||!access.actions.edit;}));
  if(sDeskWriting(held))form.append(sCard('Research before the writing',sCheck('desk-sites','Search my sites',held,'searchSites',null,()=>again()),held.searchSites?sSitePicker(held.from,'desk-research',()=>{}):null,sCheck('desk-web','Search the web too',held,'searchWeb'),sNode('p','quiet','Ticked as in Settings, for this blog only. It runs before the outline, with no stop for you.')));
  form.append(sCard(sDeskWriting(held)?'Length and tone':'Tone',sDeskWriting(held)?sLengthSelect(held,'desk-length'):null,sField('desk-tone','Tone',held,'tone',{max:2000,hint:'Such as clear and conversational.'})));
  form.append(sAdd(sNode('div','form-foot'),problem,sAdd(sNode('div','bar'),go)));
  form.addEventListener('submit',event=>{event.preventDefault();if(studio.busy)return;if(sDeskWriting(held)&&held.searchSites&&!sChosenSites(held.from).length){problem.textContent=sResearchWord('no_sites')||'Choose at least one of your sites, or untick Search my sites.';return;}held.step=2;sTop();sDeskStart();});
  return form;
}

// 3. What do you have? Then Start.
function sDeskHave(held){
  const form=sNode('form','narrow desk-start'),problem=sNode('p','problem');problem.setAttribute('role','alert');
  const parts=[sCard('What do you have?',sChoice('What you bring',DESK_HAVE,held,'have',()=>sDeskStart()))];
  // A draft chosen here switches to the one polishing screen.
  parts.push(...(held.have==='topic'?sDeskTopic(held):[sDeskOutlineIn(held)]));
  const go=sNode('button','button button-filled','Start');go.type='submit';go.disabled=!access.actions.edit;
  form.append(...parts,sAdd(sNode('div','form-foot'),problem,sAdd(sNode('div','bar'),go)));
  form.addEventListener('submit',async event=>{
    event.preventDefault();if(!access.actions.edit||studio.busy)return;const said=sDeskHaveProblem(held);if(said){problem.textContent=said;return;}
    await busy(go,'Starting…',async()=>{try{await sDeskGo(held);}catch(error){problem.textContent=error.message+' Your choices are kept here.';}});
  });
  return form;
}
// Polishing or reviewing a draft: the draft, what happens first, then Start. A kind of post
// is asked for only to reshape the draft; sources are optional, for the fact check.
// Check spelling and grammar is Finishing's Copy edit, opened in Review mode (sDeskReview).
const DESK_POLISH_FIRST=[['copyedit','Check spelling and grammar'],['feedback','Just give feedback'],['reshape','Reshape to fit a kind of post'],['leave','Leave it as it is']];
const DESK_POLISH_SAYS={copyedit:'See each fix marked in your text, then accept or reject it. Nothing changes until you accept.',feedback:'Comments on shape, argument, audience and claims appear beside each part. Nothing in the text changes.',reshape:'The sections and length are reshaped to the kind of post; a draft with no headings may be divided into sections. Your text is kept as a version first.',leave:'The draft opens on the desk as it is, for your own edits and notes.'};
function sDeskPolish(held){
  if(!DESK_POLISH_FIRST.some(([value])=>value===held.first_pass))held.first_pass=held.source==='saved'?'leave':'copyedit';
  // The kind of post goes with the draft only to reshape it, with a learned kind's samples.
  const style=held.first_pass==='reshape'?held.kind||'':'';if(held.style!==style){held.style=style;sStyleSamples(held);}
  sFrame('Polish a draft',[],'Writing desk',()=>sRoute('home'));
  const form=sNode('form','narrow desk-start'),problem=sNode('p','problem',held.problem||'');problem.setAttribute('role','alert');delete held.problem;
  const again=()=>sDeskStartAgain(held),reading=held.source==='google'&&!held.preview;
  const go=sNode('button','button button-filled',reading?'Read Google Doc':'Start');go.type='submit';go.disabled=studio.busy||!access.actions.edit;
  const first=sCard('What should happen first',sChoice('When the desk opens',DESK_POLISH_FIRST,held,'first_pass',()=>again()),sNode('p','quiet field-hint',DESK_POLISH_SAYS[held.first_pass]));
  if(held.first_pass==='reshape'){const kinds=(studio.options?.styles||[]).filter(kind=>kind.status!=='retired');first.append(sField('desk-kind','Kind of post',held,'kind',{options:[['','Choose a kind of post'],...kinds.map(kind=>[kind.id,kind.name])],changed:()=>again()}),sNode('p','quiet field-hint',kinds.length?'Its usual shape and length.':'No kinds of post yet. Set them up from Home, under Kinds of post.'));}
  const fold=(label,open,remember,...content)=>{const box=sAdd(sNode('details','card desk-fold'),sAdd(sNode('summary',''),sNode('span','card-title',label)),...content);box.open=open;box.addEventListener('toggle',()=>remember(box.open));return box;};
  const tone=fold('Tone (optional)',!!held.toneOpen,open=>{held.toneOpen=open;},sField('desk-tone','Tone',held,'tone',{max:2000,hint:'Such as clear and conversational. It guides any rewriting.'}));
  const facts=fold('Check facts against your sources (optional)',held.factsOpen??held.files.length>0,open=>{held.factsOpen=open;},sNode('p','quiet','Finishing’s fact check reads these. They stay with this blog unless you keep them in the team library.'),...[...sFilesCard(held,problem,again,locked=>{go.disabled=locked||!access.actions.edit;}).children].slice(1));
  const instead=sButton('Writing something new? Start from a topic or an outline',()=>{held.have='topic';if(held.kind===null)held.step=0;else{held.style=held.kind;sStyleSamples(held);}sTop();sDeskStart();});instead.className+=' desk-instead';
  sAdd(form,...sDeskDraftIn(held),first,tone,facts,sAdd(sNode('div','form-foot'),problem,sAdd(sNode('div','bar'),go)),held.source==='saved'?null:instead);
  form.addEventListener('submit',async event=>{
    event.preventDefault();if(!access.actions.edit||studio.busy)return;const said=sDeskHaveProblem(held);if(said){problem.textContent=said;return;}
    await busy(go,reading?'Reading…':'Starting…',async()=>{try{if(reading)await sDeskReadGoogle(held);else await sDeskGo(held);}catch(error){problem.textContent=error.message+' Your choices are kept here.';}});
  });
  sPage(sNode('p','lede','Bring your draft and choose what happens first. No kind of post needed.'),form);
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
    if(held.first_pass==='reshape'&&!held.kind)return 'Choose a kind of post to reshape the draft to.';
  }
  return '';
}
// A topic: the point typed, or three angles from the sources chosen, to pick and edit.
function sDeskTopic(held){
  const card=sCard('Your topic',sField('desk-title','Working title',held,'title',{required:true,max:500}),sField('desk-audience','Who is it for?',held,'audience',{max:500}),sField('desk-point','The point to make',held,'point',{long:true,max:2000,hint:'What the reader should understand or do afterward.'}));
  const ready=held.files.filter(file=>file.state==='ready').length;
  const ask=sButton(held.angles.length?'Suggest three more':'Suggest three angles',button=>sDeskAskAngles(held,button));ask.disabled=!access.actions.edit||held.anglesBusy;
  card.append(sAdd(sNode('div','bar'),ask),sNode('p','quiet field-hint',ready?'Angles read your '+ready+(ready===1?' source.':' sources.'):'With no sources, angles work from the title and point.'));
  if(held.anglesBusy){const working=sNode('p','desk-working-note','Finding three angles…');working.setAttribute('role','status');card.append(working);}
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
// Files with Keep ticked: the server moves them to the team library once the blog is made
// (or the source is added), never before, and a repeated request keeps nothing twice.
function sDeskKept(files){const kept=sDeskUploads(files.filter(file=>file.kept));return kept.length?{keep:kept}:{};}
async function sDeskAskAngles(held,button){
  const operation=operationId(),replaces=held.angleOp;held.angleOp=operation;held.anglesProblem='';
  await busy(button,'Asking…',async()=>{try{
    const shown=await api('desk-angles',{operation,title:held.title.trim(),point:held.point.trim(),audience:held.audience.trim(),style:held.kind||'',tone:held.tone,sources:sDeskUploads(held.files),library:sDeskLibraryPicks(held.files),...(replaces?{replaces}:{})});
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
  if(held.outlineFrom==='paste')card.append(sField('desk-outline','Paste your outline or notes',held,'outline',{long:true,max:200000,required:true,hint:'Headings or a list make the sections.'}));
  else{const file=sNode('input','input');file.type='file';file.accept='.txt,.md,.docx,.pdf,.html,.htm';file.setAttribute('aria-label','Upload an outline');const note=sNode('p','quiet field-hint',held.outlineFile?'Selected: '+held.outlineFile.name:'Text, Markdown, Word or PDF.');file.addEventListener('change',()=>{held.outlineFile=file.files?.[0]||null;note.textContent=held.outlineFile?'Selected: '+held.outlineFile.name:'Choose an outline.';});card.append(file,note);}
  card.append(sField('desk-title','Title (optional)',held,'title',{max:500,hint:'Blank uses the outline’s # heading.'}),sChoice('Then',DESK_OUTLINE_WAYS,held,'outlineWay',()=>sDeskStart()),sNode('p','quiet field-hint',held.outlineWay==='shape'?'The outline opens on the desk for you to shape first.':'The draft is written from your outline.'));
  return card;
}
// A draft: paste, upload or a Google Doc (every tab). A start opened from a saved blog's
// details also offers that blog's own draft, brought as it is.
function sDeskDraftIn(held){
  const saved=held.article?sCheck('desk-saved','Use this blog’s saved draft',{on:held.source==='saved'},'on','It comes to the desk as it is, in the same blog. Its history is kept.',on=>{held.source=on?'saved':'paste';held.preview=null;sDeskStart();}):null;
  const card=sCard('Your draft',saved,held.source==='saved'?null:sChoice('Where is your draft?',[['paste','Paste text'],['file','Upload a file'],['google','Google Doc']],held,'source',()=>{held.preview=null;sDeskStart();}));
  if(held.source==='saved'){/* The blog's own draft: nothing to paste or read. */}
  else if(held.source==='paste')card.append(sField('desk-manuscript','Paste your draft',held,'manuscript',{long:true,max:1000000,required:true,hint:'Its headings start the sections, at whatever level it uses.'}));
  else if(held.source==='file'){
    const file=sNode('input','input');file.type='file';file.accept='.txt,.md,.docx,.pdf,.html,.htm';file.setAttribute('aria-label','Upload a draft');
    const note=sNode('p','quiet field-hint',held.file?'Selected: '+held.file.name:'Text, Markdown, Word or PDF.');
    file.addEventListener('change',()=>{held.file=file.files?.[0]||null;note.textContent=held.file?'Selected: '+held.file.name:'Choose a draft.';});
    card.append(file,note);
  }else{
    card.append(sField('desk-google','Google Doc link or document ID',held,'url',{required:true,max:2000,hint:'Every tab is read; the Doc is not changed.',changed:()=>{held.preview=null;}}));
    if(held.preview){const paper=sNode('article','paper doc');paper.setAttribute('aria-label','Google Doc preview');paper.append(window.TrainingStudioMarkdown?window.TrainingStudioMarkdown.render(held.preview.content):sNode('p','',held.preview.content));card.append(sNode('p','','Check the text below, then start.'),paper);}
  }
  card.append(sField('desk-title','Title (optional)',held,'title',{max:500,hint:'Blank uses the draft’s # heading or the Doc’s name.'}));
  return [card];
}
async function sDeskReadGoogle(held){
  const turn=studio.turn,found=await api('google-preview',{url:held.url.trim()});if(turn!==studio.turn)return;
  if(found?.status==='already-linked'&&found.id){
    // The Doc is already a blog here: open it on the desk, or bring it there.
    let made=null,created=false;try{made=await api('desk?id='+encodeURIComponent(found.id));}catch(_){made=null;}
    if(!made){created=true;made=await api('desk-create',{operation:held.operation,style:held.style,tone:held.tone,first_pass:held.first_pass,sources:sDeskUploads(held.files),library:sDeskLibraryPicks(held.files),...sDeskKept(held.files),article:found.id});}
    if(turn!==studio.turn)return;studio.deskStart=null;studio.desk={id:made.id,view:made,session:operationId()};return sRoute('desk',made.id,created&&held.first_pass==='copyedit'?'review':null);
  }
  held.preview=sGooglePreview(found);if(!held.title.trim())held.title=found.title;sDeskStart();
}
async function sDeskGo(held){
  if(held.have!=='draft'&&held.kind===null){held.step=0;sDeskStart();throw new Error('Choose a kind of post first.');}
  const turn=studio.turn;
  // A draft takes a kind of post only to be reshaped to it (sDeskPolish keeps held.style so).
  const common={operation:held.operation,style:held.have==='draft'?held.style:held.kind||'',tone:held.tone,sources:sDeskUploads(held.files),library:sDeskLibraryPicks(held.files),...sDeskKept(held.files),...(held.title.trim()?{title:held.title.trim()}:{})};
  let made;
  if(held.have==='draft'){
    const settings={...common,first_pass:held.first_pass};
    if(held.source==='saved')made=await api('desk-create',{...settings,article:held.article});
    else if(held.source==='paste')made=await api('desk-create',{...settings,manuscript:held.manuscript});
    else if(held.source==='file'){
      if(held.file.size>10*1024*1024)throw new Error('Choose a file up to 10 MiB.');
      const uploaded=await api('upload',{operation:held.upload,filename:held.file.name,title:held.title.trim()||held.file.name.replace(/\.[^.]+$/,''),content:await encodeImportFile(held.file),purpose:'manuscript',analyze:false});
      if(uploaded.state&&uploaded.state!=='ready')throw new Error('This file needs its text extracted before it can be edited. Paste the text instead.');
      made=await api('desk-create',{...settings,source:uploaded.source.id});
    }else{
      if(!held.preview)throw new Error('Read the Google Doc first.');
      const started=await api('google-start',{preview:held.preview.preview,expected:held.preview.expected,title:held.title.trim()||held.preview.title,confirmed:true});
      made=await api('desk-create',{...settings,title:undefined,article:started.id});
    }
  }else{
    const research=held.searchSites||held.searchWeb?{research_from:{sites:held.searchSites?sChosenSites(held.from):[],web:!!held.searchWeb}}:{};
    const writing={...common,way:held.have==='topic'?'topic':held.outlineWay,length:held.length||'style',...research,...(held.have==='topic'&&held.angleOp?{angles:held.angleOp}:{})};
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
  if(made.keep_problem)sToast(made.keep_problem);
  // Check spelling and grammar lands in Review mode; every other start on the full desk.
  studio.desk={id:made.id,view:made,session:operationId()};await sRoute('desk',made.id,held.have==='draft'&&held.first_pass==='copyedit'?'review':null);
}

// Add a source on the desk: the same files card, saved with this blog; a kept one goes to
// the team library when it is added.
function sDeskSourcesSheet(held){
  const adding=held.adding||(held.adding={files:[],role:'material',keep:false,style:held.view.style?.style_id||''});
  const problem=sNode('p','sheet-error',adding.problem||'');problem.setAttribute('role','alert');delete adding.problem;
  let done;
  const files=sFilesCard(adding,problem,()=>sDeskSourcesSheet(held),locked=>{if(done)done.disabled=locked||!access.actions.edit;},{keepWhen:'Ticked ones go to the team library when you add them.'});
  done=sButton('Add to this draft',async button=>{
    const ready=adding.files.filter(file=>file.state==='ready');if(!ready.length){problem.textContent='Add a file, a link, a Google Doc or a library post with text first.';return;}
    await busy(button,'Adding…',async()=>{try{await sDeskFlush(held);const before=held.view;held.view=await api('desk-sources',{id:held.id,sources:sDeskUploads(ready),library:sDeskLibraryPicks(ready),...sDeskKept(ready)});held.adding=null;sCloseSheet();sToast(ready.length===1?'Added. Later rewrites read it.':'Added. Later rewrites read them.');sDeskRefresh(held,before);}catch(error){problem.textContent=error.message;}});
  },'filled');
  done.disabled=!access.actions.edit;
  sOpenSheet('Add a source',sNode('p','quiet','Later rewrites read it; nothing already written changes.'),files,problem,sAdd(sNode('div','bar'),done,sButton('Cancel',sCloseSheet)));
}

// The desk.
async function sDesk(ident){
  const turn=studio.turn;
  const view=await api('desk?id='+encodeURIComponent(ident));if(turn!==studio.turn)return;
  const held=studio.desk&&studio.desk.id===ident?studio.desk:(studio.desk={id:ident,session:operationId()});
  // Coming back reads the desk afresh: nothing typed before leaving is saved over it.
  for(const pending of Object.values(held.pending||{}))if(pending?.timer&&typeof clearTimeout==='function')clearTimeout(pending.timer);
  held.view=view;held.pending={};held.stale=false;held.outline=null;if(held.review)held.review.editing=null;
  // Review mode is in the address (stage=review), so a reload or Back keeps it.
  held.mode=studio.stage==='review'?'review':null;
  if(sDeskStarting(view))return sDeskProgress(held);
  if(!held.tab)held.tab=view.start?.open==='outline'&&!sDeskHasText(view)?'outline':'draft';
  sDeskRender(held);
  sDeskWatch(held);
}
function sDeskStarting(view){return !!view?.start&&!view.start.ended_at;}
function sDeskHasText(view){return !!view.opening||(view.sections||[]).some(section=>section.text);}

// A start under way: nothing is needed from the person; the draft opens on its own.
function sDeskElapsed(start){const then=Date.parse(start.started_at||'');return then?Math.max(0,(Date.now()-then)/60000):0;}
function sDeskSpent(start){const minutes=Math.floor(sDeskElapsed(start));return minutes<1?'under a minute':minutes+(minutes===1?' minute':' minutes');}
function sDeskClock(start){const spent=sDeskSpent(start);return spent.charAt(0).toUpperCase()+spent.slice(1)+' so far, for the whole start.';}
// About how long is left, from recent runs of each step here; an overrun step says so.
function sDeskEstimate(start,what){if(start.over)return 'Nothing needed from you. Taking longer than usual; still working, '+sDeskSpent(start)+' so far. '+what+' opens here when it is ready.';const left=Math.max(1,start.minutes_left||start.minutes||1);return 'Nothing needed from you. '+what+' opens here when it is ready, in about '+left+(left===1?' minute.':' minutes.');}
function sDeskProgress(held){
  const view=held.view,start=view.start,problem=start.problem,what=start.open==='outline'?'The outline':'The draft';
  const stop=start.busy?sButton('Stop',async button=>{await busy(button,'Stopping…',async()=>{try{held.view=await api('desk-stop',{id:held.id,job:start.job});sDeskProgress(held);}catch(error){notice(error.message,true);}});}):null;
  if(stop)stop.disabled=!access.actions.edit;
  sFrame(view.title,[stop],problem?'Stopped':'Writing on its own',()=>sRoute('blogs'));
  const first=sNode('p','lede',problem?'This start stopped before '+what.toLowerCase()+' was ready. Retry the step when you are ready.':sDeskEstimate(start,what));
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
function sDeskWorkingIn(view,part){const job=view?.working;if(!job)return false;return job.part===part||job.part==='sections'&&part!=='title'&&(part!=='opening'||job.kind==='desk-first-pass');}
function sDeskWorking(held,part){return sDeskWorkingIn(held.view,part);}
function sDeskStatusWords(held){const job=held.view.working;if(!job)return '';if(job.kind==='desk-revise-all'&&job.part==='opening')return 'Revising the opening…';if(job.kind==='desk-revise-all'&&job.total)return 'Revising section '+(job.index+1)+' of '+job.total+'…';return (DESK_DOING[job.kind]||'Working')+(job.kind==='desk-section'||job.kind==='desk-selection'?' '+deskPartName(held.view,job.part):'')+'…';}
function sDeskTabs(held){return sChoice('Work on',[['draft','Draft'],['outline','Outline']],held,'tab',async()=>{await sDeskOutlineFlush(held);held.outline=null;sDeskRender(held);});}
function sDeskToolbar(held){
  const view=held.view,editable=access.actions.edit;
  const copy=sButton('Copy',async()=>{if(typeof navigator==='undefined'||!navigator.clipboard?.writeText)throw new Error('Download the draft and copy it from there.');const found=await sDeskMarkdown(held);await navigator.clipboard.writeText(found.markdown);sToast(deskWithout('Markdown copied',found.missing));});
  const download=sButton('Download',async()=>{const found=await sDeskMarkdown(held);await sDownload({content:found.markdown,name:'DRAFT.md'});if(found.missing.length)sToast(deskWithout('Downloaded',found.missing));});
  const google=view.google?.url?link(view.google.url,'Google Doc ↗'):null;if(google)google.className='button';
  const publish=sButton(view.publication?'Published':'Mark as published',()=>sDeskPublish(held));publish.disabled=!editable;
  const finishing=sButton('Finishing',()=>held.finish?sDeskFinishClose(held):sDeskFinishOpen(held));finishing.setAttribute('aria-pressed',String(!!held.finish));
  const review=held.review?sButton('Review fixes',async()=>{await sDeskFlush(held);await sDeskOutlineFlush(held);held.finish=null;held.mode='review';sDeskRender(held);sDeskWatch(held);}):null;
  const stop=held.view.working?sButton('Stop',async button=>{await busy(button,'Stopping…',async()=>{const before=held.view;held.view=await api('desk-stop',{id:held.id,job:held.view.working.id});sDeskRefresh(held,before);});}):null;
  sFrame(view.title,sFold([stop,review,copy,download,google,publish,finishing]),held.view.working?sDeskStatusWords(held):'On the desk',()=>sRoute('blogs'));
}
function sDeskRender(held){
  if(held.mode==='review')return sDeskReview(held);
  const view=held.view;sDeskToolbar(held);held.layout=sDeskLayout();
  const status=sNode('p','quiet desk-save-state');status.setAttribute('role','status');status.setAttribute('aria-live','polite');held.status=status;
  if(held.stale)sDeskStale(held);else status.textContent=held.saved||'Changes save as you type.';
  const column=sNode('div','desk-column');held.tab=held.tab||'draft';held.shownTab=held.tab;
  held.problemSlot=sNode('div','desk-problem-slot');const problem=sDeskProblem(held);if(problem)held.problemSlot.append(problem);
  held.cards={};
  held.column=column;held.outlineStale=false;
  if(held.tab==='outline'){held.wholeCard=null;held.wholeGo=null;column.append(held.problemSlot,...sDeskOutline(held));column.addEventListener('focusout',()=>setTimeout(()=>{if(held.outlineStale&&held.column===column&&!held.outlineTimer&&!sDeskTyping(column)&&sDeskCurrent(held)){held.outline=null;sDeskRender(held);}},0));}
  else{
    held.wholeCard=sDeskWhole(held);
    for(const part of ['title','opening',...view.sections.map(section=>section.id)])held.cards[part]=sDeskPart(held,part);
    column.append(held.problemSlot,held.wholeCard,...Object.values(held.cards));
    held.noSections=view.sections.length?null:sDeskNoSections();if(held.noSections)column.append(held.noSections);
  }
  held.bar=sDeskSelectionBar(held);held.aside=sDeskAside(held);
  // Finishing sits beside the draft in place of the sources; on a phone it is a full-screen sheet.
  const finishing=!!held.finish,sheet=finishing&&sNarrow();
  held.panel=finishing?sDeskPanel(held):null;held.panelKey=finishing?sDeskPanelKey(held):null;
  const lede=held.tab==='outline'?'Rename, reorder, add and remove sections and say what each must do. Write the draft from the outline, or one section at a time.':'Edit any part in place, give a section a note to rewrite it, or select text for a quick change. Every change keeps the earlier text in History.';
  sPage(sNode('p','lede',lede),status,sDeskTabs(held),sAdd(sNode('div','desk-layout'+(finishing&&!sheet?' desk-finishing':'')),column,finishing&&!sheet?held.panel:held.aside),sheet?held.panel:null,held.bar);
  sDeskImagesLoad(held);
}
// After a job starts, moves on or ends: redraw only the cards it changed, so the part the
// person is typing in keeps its focus and caret.
// A field the person is typing in is never drawn again under them: its card is brought up to
// date in place, and drawn again once focus leaves it.
function sDeskFocused(){return typeof document.activeElement==='object'?document.activeElement:null;}
function sDeskTyping(node){const focused=sDeskFocused();return !!(node&&focused&&['INPUT','TEXTAREA','SELECT'].includes(String(focused.tagName).toUpperCase())&&typeof node.contains==='function'&&node.contains(focused));}
function sDeskRefresh(held,before){
  if(held.mode==='review')return sDeskReviewRefresh(held,before);
  const view=held.view,order=found=>(found?.sections||[]).map(section=>section.id).join(',');
  if(held.tab==='outline'||held.shownTab!==held.tab){if((held.outlineTimer||held.tab==='outline'&&sDeskTyping(held.column))&&sDeskCurrent(held)){if(!held.outlineTimer)held.outlineStale=true;sDeskToolbar(held);const aside=sDeskAside(held);held.aside.replaceWith(aside);held.aside=aside;sDeskPanelSync(held);return;}held.outline=null;return sDeskRender(held);}
  if(!held.cards||!before||!sDeskCurrent(held))return sDeskRender(held);
  if(order(before)!==order(view))return sDeskReorder(held,before);
  sDeskToolbar(held);
  held.problemSlot.replaceChildren(...[sDeskProblem(held)].filter(Boolean));
  sDeskWholeState(held);
  for(const part of Object.keys(held.cards)){
    const was=sDeskWorkingIn(before,part),now=sDeskWorking(held,part),old=held.cards[part];
    const changed=was!==now||deskTextOf(before,part)!==deskTextOf(view,part)||(before.versions||{})[part]!==(view.versions||{})[part]||sDeskCommentKey(before,part)!==sDeskCommentKey(view,part);
    if(changed&&!sDeskTyping(old)){const card=sDeskPart(held,part);old.replaceWith(card);held.cards[part]=card;}
    else{if(changed)old.deskStale=true;sDeskPartState(held,part,old,was&&!now);}
  }
  const aside=sDeskAside(held);held.aside.replaceWith(aside);held.aside=aside;
  sDeskPanelSync(held);
  sDeskImagesLoad(held);
}
// A card brought up to date in place: whether its part is being worked on, its text when it
// is not the field typed in, and whether its notes can start a job now. When a job on this
// part has just ended (`landed`), its text is set even in a focused field: the field was
// read-only while the job worked, so nothing typed is lost, and the next keystroke must
// build on the job's text, never save the text from before it.
function sDeskPartState(held,part,card,landed=false){
  const view=held.view,working=sDeskWorking(held,part),focused=sDeskFocused(),input=card.deskInput;
  card.className='card desk-part'+(working?' desk-working':'');
  if(input){input.readOnly=working||!access.actions.edit;if(landed)delete held.pending[part];if(landed||input!==focused&&!held.pending[part]){const text=deskTextOf(view,part);if(input.value!==text)input.value=text;}}
  if(card.deskGo)card.deskGo.disabled=!access.actions.edit||!!view.working;
  if(!working&&card.deskWorkingNotes){for(const note of card.deskWorkingNotes)note.remove();card.deskWorkingNotes=null;}
}
// Sections added, removed or moved by a job while the person types: the card they are typing
// in stays where it is, brought up to date in place, and the other cards are drawn in the new
// order around it. With nothing being typed, the desk is drawn again whole.
function sDeskReorder(held,before){
  const view=held.view,parts=['title','opening',...(view.sections||[]).map(section=>section.id)];
  const keep=Object.values(held.cards).find(card=>sDeskTyping(card))||null;
  if(keep?!parts.includes(keep.dataset.part):!sDeskTyping(held.wholeCard))return sDeskRender(held);
  sDeskToolbar(held);
  held.problemSlot.replaceChildren(...[sDeskProblem(held)].filter(Boolean));
  sDeskWholeState(held);
  const cards={};
  for(const part of parts){
    if(keep&&keep.dataset.part===part){const was=sDeskWorkingIn(before,part),now=sDeskWorking(held,part);if(was!==now||deskTextOf(before,part)!==deskTextOf(view,part))keep.deskStale=true;sDeskPartState(held,part,keep,was&&!now);cards[part]=keep;}
    else cards[part]=sDeskPart(held,part);
  }
  for(const old of Object.values(held.cards))if(old!==keep)old.remove();
  if(held.noSections){held.noSections.remove();held.noSections=null;}
  const order=parts.map(part=>cards[part]);
  if(keep){const at=parts.indexOf(keep.dataset.part);keep.before(...order.slice(0,at));keep.after(...order.slice(at+1));}
  else held.column.append(...order);
  held.cards=cards;
  if(!view.sections.length){held.noSections=sDeskNoSections();held.column.append(held.noSections);}
  const aside=sDeskAside(held);held.aside.replaceWith(aside);held.aside=aside;
  sDeskPanelSync(held);
  sDeskImagesLoad(held);
}
function sDeskNoSections(){return sCard('No sections yet',sNode('p','','This draft has no headings, so it is one opening. Add sections on the Outline tab.'));}
// Drawn again once focus leaves a card brought up to date in place.
function sDeskPartLeft(held,part,card){
  setTimeout(()=>{if(!card.deskStale||held.cards?.[part]!==card||sDeskTyping(card)||!sDeskCurrent(held)||held.mode==='review')return;const fresh=sDeskPart(held,part);card.replaceWith(fresh);held.cards[part]=fresh;sDeskImagesLoad(held);},0);
}
// What the last job left: a result not applied, or a job that failed.
function sDeskProblem(held){
  const last=(held.view.jobs||[]).at(-1);if(!last||held.dismissed===last.id)return null;
  const chain=held.view.chain;
  if(last.chain&&chain){if(chain.working||!chain.problems.length)return null;return sAdd(sNode('div','decision-notice desk-problem'),sAdd(sNode('div',''),sNode('p','',chain.total===1&&chain.problems[0].part==='opening'?'Your note was not applied:':'Revised '+chain.revised+' of '+chain.total+' sections for your note. These were not:'),sAdd(sNode('ul','gap-items'),...chain.problems.map(problem=>sNode('li','',(problem.part==='opening'?'The opening':'“'+problem.heading+'”')+': '+problem.error)))),sButton('Dismiss',()=>{held.dismissed=last.id;sDeskRender(held);}));}
  const failed=last.status==='failed'||last.status==='ready'&&last.applied===false;if(!failed||!last.error)return null;
  const tool=DESK_TOOLS.find(([key])=>'finish-'+key===last.kind);
  return sAdd(sNode('div','decision-notice desk-problem'),sNode('p','',(tool?tool[1]+' did not finish: ':last.status==='failed'?'The last change could not finish: ':'The last change was not applied: ')+last.error),sButton('Dismiss',()=>{held.dismissed=last.id;sDeskRender(held);}));
}
function sDeskWhole(held){
  const card=sCard('Note for the whole draft');
  const box=sNode('textarea','input');box.id='desk-whole-note';box.rows=2;box.maxLength=4000;box.setAttribute('aria-label','Note for the whole draft');box.value=held.wholeNote||'';box.placeholder='For example: tighten throughout, or make it more casual.';
  box.addEventListener('input',()=>{held.wholeNote=box.value;});
  const go=sButton('Revise the draft',async button=>{const text=(held.wholeNote||'').trim();if(!text){notice('Write the note for the whole draft.',true);return;}await sDeskJob(held,button,'desk-revise',{note:text},()=>{held.wholeNote='';});},'filled');
  go.disabled=!access.actions.edit||!!held.view.working;held.wholeGo=go;
  return sAdd(card,box,sNode('p','quiet field-hint','Each section is revised for the note with the whole draft in view. Your text is kept as a version first.'),sAdd(sNode('div','bar'),go));
}
// The note for the whole draft is never drawn again by a poll: only its button follows the job.
function sDeskWholeState(held){if(held.wholeGo)held.wholeGo.disabled=!access.actions.edit||!!held.view.working;}
function sDeskPart(held,part){
  const view=held.view,section=(view.sections||[]).find(row=>row.id===part),working=sDeskWorking(held,part);
  const card=sNode('section','card desk-part'+(working?' desk-working':''));card.dataset.part=part;
  const heading=sNode('h2','card-title',part==='title'?'Title':part==='opening'?'Opening':deskHeading(section.heading));
  const count=(view.versions||{})[part]||0,history=sButton(count?'History ('+count+')':'History',()=>sDeskHistory(held,part));history.disabled=!count;
  card.append(sAdd(sNode('div','desk-part-head'),heading,history));
  const text=held.pending[part]?.text??deskTextOf(view,part);
  const input=sNode(part==='title'?'input':'textarea','input desk-text');input.value=text;input.setAttribute('aria-label',part==='title'?'Title':part==='opening'?'Opening':'Text of '+deskHeading(section.heading));
  if(part==='title'){input.type='text';input.maxLength=500;}else{input.rows=Math.min(24,Math.max(3,Math.ceil(text.length/90)+text.split('\n').length));}
  input.readOnly=working||!access.actions.edit;card.deskInput=input;
  input.addEventListener('input',()=>sDeskTyped(held,part,input.value));
  if(part!=='title'){for(const kind of ['select','mouseup','keyup'])input.addEventListener(kind,()=>sDeskSelected(held,part,input));}
  else input.addEventListener('select',()=>sDeskSelected(held,part,input));
  card.append(input);
  const thumbs=part==='title'?null:sDeskThumbs(held,part);if(thumbs)card.append(thumbs);
  const comments=sDeskComments(held,part);if(comments)card.append(comments);
  if(working){const note=sNode('p','desk-working-note','Working on this section');note.setAttribute('role','status');card.append(note);card.deskWorkingNotes=[note];if(view.working.note){const said=sNode('p','quiet','Your note: '+view.working.note);card.append(said);card.deskWorkingNotes.push(said);}}
  if(section){
    const typed=(held.notes||{})[part]||'',row=sNode('div','desk-note');
    const box=sNode('textarea','input desk-note-text');box.rows=typed.includes('\n')?4:1;box.maxLength=4000;box.value=typed;box.placeholder='How should this change?';box.setAttribute('aria-label','How should '+deskHeading(section.heading)+' change?');
    const go=sButton(typed.trim()?'Rewrite':'Write again',async button=>{const note=((held.notes||{})[part]||'').trim();await sDeskJob(held,button,'desk-note',{part,note},()=>{if(held.notes)delete held.notes[part];});});
    go.disabled=!access.actions.edit||!!view.working;card.deskGo=go;
    box.addEventListener('input',()=>{held.notes=held.notes||{};held.notes[part]=box.value;go.textContent=box.value.trim()?'Rewrite':'Write again';});
    card.append(sAdd(row,box,go));
  }
  card.addEventListener('focusout',()=>sDeskPartLeft(held,part,card));
  return card;
}
function sDeskAside(held){
  const view=held.view,aside=sNode('aside','desk-aside');aside.setAttribute('aria-label','Sources and gaps');
  const sources=sCard('Sources');
  if((view.source_names||[]).length){const list=sNode('ul','rows');for(const source of view.source_names)list.append(sAdd(sNode('li','row'),sNode('span','row-title',source.name)));sources.append(list);}
  else sources.append(sNode('p','quiet','No sources were given for this draft. Rewrites keep to what the draft already says.'));
  const add=sButton('Add a source',()=>sDeskSourcesSheet(held));add.disabled=!access.actions.edit;sources.append(sAdd(sNode('div','bar'),add));
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
    // An image pasted as data is kept beside the text: its card shows the reference instead.
    if(/data:image\//i.test(text)&&!held.pending[part]&&held.cards?.[part]&&sDeskCurrent(held)){const card=sDeskPart(held,part);held.cards[part].replaceWith(card);held.cards[part]=card;await sDeskImagesLoad(held);}
    if(!!before.working!==!!view.working&&sDeskCurrent(held))sDeskRefresh(held,before);
  }catch(error){
    if(/changed since/.test(error.message)){held.stale=true;sDeskStale(held);}
    else if(held.status)held.status.textContent=error.message+' Your text is kept here.';
  }finally{held.saving=null;}})();
  await held.saving;
  if(held.pending[part]&&held.pending[part].text!==text&&!held.stale)return sDeskSave(held,part);
}
async function sDeskFlush(held){if(held.review?.editing?.dirty)await sReviewSave(held);for(const part of Object.keys(held.pending)){if(held.pending[part]?.timer&&typeof clearTimeout==='function')clearTimeout(held.pending[part].timer);await sDeskSave(held,part);}}
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
      if(ended){held.watching=false;const last=(view.jobs||[]).at(-1);if(last?.applied)sToast(held.mode==='review'&&last.kind==='finish-copyedit'?'The fixes are marked in your text.':/^finish-/.test(last.kind)?'Suggestions are ready in Finishing.':'Done. The earlier text is in History.');if(held.finish?.tool==='proofread'&&!/^finish-/.test(last?.kind||''))await sDeskProofread(held);return;}
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
// A version from before a first pass divided the draft brings the draft back as it was.
function deskVersionNote(version){const added=(version.divided||[]).length;return added?'Restoring this also takes out the '+added+(added===1?' section':' sections')+' the first pass added. They can be brought back on the Outline tab.':'';}
async function sDeskHistory(held,part){
  await sDeskFlush(held);
  const found=await api('desk-versions?'+new URLSearchParams({id:held.id,part}));
  const current=deskTextOf(held.view,part),list=sNode('div','desk-versions'),compare=sNode('div','desk-compare-area');
  found.versions.forEach((version,index)=>{
    const row=sAdd(sNode('div','desk-version'),sAdd(sNode('div','row-text'),sNode('h3','row-title',DESK_SOURCES[version.source]||'Earlier text'),sNode('p','quiet',[deskAge(version.at),version.words+(version.words===1?' word':' words')].filter(Boolean).join(' · ')),deskVersionNote(version)?sNode('p','quiet',deskVersionNote(version)):null));
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
  // Sections taken out, with their text and History, to bring back.
  if((view.removed||[]).length){const list=sNode('ul','rows');view.removed.forEach((item,index)=>{const back=sButton('Bring back',async button=>{await busy(button,'Bringing back…',async()=>{try{await sDeskOutlineFlush(held);held.view=await api('desk-unremove',{id:held.id,seen:held.view.revision,index});held.outline=null;sDeskRender(held);}catch(error){if(/changed since/.test(error.message)){held.stale=true;sDeskStale(held);}else notice(error.message,true);}});});back.setAttribute('aria-label','Bring back '+item.heading);back.disabled=!editable;list.append(sAdd(sNode('li','row'),sAdd(sNode('div','row-text'),sNode('span','row-title',item.heading),sNode('span','row-says',(item.words?item.words+(item.words===1?' word':' words'):'No text')+(item.at?' · removed '+deskAge(item.at):''))),back));});cards.push(sCard('Removed sections',list));}
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
  const remove=sButton('Remove',()=>{const gone=rows=>rows.splice(index,1);if(!words)return sDeskOutlineChange(held,gone);const confirm=sButton('Remove the section',async button=>{await busy(button,'Removing…',async()=>{sCloseSheet();await sDeskOutlineChange(held,gone);});},'danger');sOpenSheet('Remove “'+name+'”?',sNode('p','','Its '+words+(words===1?' word goes':' words go')+' with it. Bring it back from Removed sections under the outline.'),sAdd(sNode('div','bar'),confirm,sButton('Cancel',sCloseSheet)));});
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

// Finishing: an optional side panel of tools that propose. Each proposal is previewed before
// and after, side by side, then applied, edited or skipped; nothing changes until Apply, and
// each Apply keeps the earlier text in History. On a phone the panel is a full-screen sheet.
// Quick check keeps the key proofread, as its route desk-proofread does.
const DESK_TOOLS=[
  ['copyedit','Copy edit','Grammar, spelling, punctuation, consistency and wordy sentences, each fix marked in your text to accept or reject. Voice, facts, quotes and links are kept.'],
  ['humanize','Humanize','Sentences that read as machine-written, each with a rewrite. Numbers, names, quotes and links are kept.'],
  ['proofread','Quick check','Dashes, words that often read as machine-written, and repetition, checked at once with no assistant.'],
  ['facts','Check facts against sources','Each claim marked supported, not in your sources, or contradicted, with the passage.'],
  ['headline','Headline and opening','Alternatives for the title and the opening, to use or adjust.'],
  ['feedback','Feedback without a rewrite','Comments on shape, argument, audience and claims. Nothing in the text changes.'],
  ['voice','Apply a voice','The draft rewritten in one of your voice guides, section by section. Its facts, quotes, links and shape are kept.'],
  ['publish','Before publishing','The pre-publish check, Repurpose, and Send to Google Doc as suggestions.'],
];
const DESK_LEVELS=[['light','Light'],['medium','Medium'],['strong','Strong']];
const DESK_RUN={copyedit:['Find fixes','Finding grammar, spelling and wording fixes…'],humanize:['Find sentences','Finding sentences that read as machine-written…'],facts:['Check facts','Checking each claim against your sources…'],headline:['Suggest alternatives','Suggesting headlines and openings…'],feedback:['Get feedback','Reading the draft for feedback…'],voice:['Apply the voice','Rewriting the draft in the voice guide, section by section…']};
const DESK_VERDICTS={supported:'Supported','not-in-sources':'Not in your sources',contradicted:'Contradicted'};
const DESK_ASPECTS={shape:'Shape',argument:'Argument',audience:'Audience',claims:'Claims'};
const DESK_FORMATS=[['linkedin','LinkedIn feed copy'],['newsletter','Newsletter introduction'],['email','Announcement email'],['summary','Short summary'],['thread','Short thread']];
function sDeskFinishOpen(held,tool=null){if(tool==='copyedit')return sDeskCopyEdit(held);held.finish=held.finish||{tool:null,level:'light',editing:{},noted:{}};held.finish.tool=tool;sDeskRender(held);if(tool==='proofread')return sDeskProofread(held);if(tool==='voice')return sDeskGuides(held);}
function sDeskFinishClose(held){held.finish=null;sDeskRender(held);}
// Copy edit is reviewed in the text itself: it opens Review mode, where the check starts.
async function sDeskCopyEdit(held){await sDeskFlush(held);await sDeskOutlineFlush(held);held.finish=null;held.mode='review';sDeskRender(held);sDeskWatch(held);}
function sDeskFinishTool(held,tool){if(tool==='copyedit')return sDeskCopyEdit(held);held.finish.tool=tool;sDeskPanelShow(held);if(tool==='proofread'&&!held.finish.proof)return sDeskProofread(held);if(tool==='voice')return sDeskGuides(held);}
// The voice guides Apply a voice can use, read when the tool opens.
async function sDeskGuides(held){
  const f=held.finish;try{const found=await api('voice-guides');if(held.finish!==f)return;f.guides=found.guides.filter(guide=>guide.status!=='retired');f.guidesProblem='';}catch(error){if(held.finish!==f)return;f.guides=f.guides||[];f.guidesProblem=error.message;}
  const used=(held.view.finishing||{}).voice?.items&&f.guides.find(guide=>guide.name===(held.view.finishing||{}).voice.guide_name);
  if(!f.guides.some(guide=>guide.id===f.guide))f.guide=(used||f.guides[0]||{}).id||'';
  if(f.tool==='voice')sDeskPanelSync(held,true);
}
function sDeskPanel(held){
  const f=held.finish,tool=DESK_TOOLS.find(([key])=>key===f.tool);
  const panel=sNode('aside','desk-finish'+(sNarrow()?' desk-finish-sheet':''));panel.setAttribute('aria-label','Finishing');
  const head=sNode('div','desk-finish-head glass');
  if(tool)head.append(sButton('All tools',()=>{f.tool=null;sDeskPanelShow(held);}));
  head.append(sNode('h2','desk-finish-title',tool?tool[1]:'Finishing'),sButton('Close',()=>sDeskFinishClose(held)));
  const body=sNode('div','desk-finish-body');body.append(...(tool?sDeskToolView(held,f.tool):sDeskToolList(held)));
  panel.addEventListener('focusout',()=>setTimeout(()=>{if(held.panelStale&&held.panel===panel)sDeskPanelSync(held,true);},0));
  panel.hidden=!!held.panelUnder;  // Under a sheet opened from it, on a narrower screen.
  return sAdd(panel,head,body);
}
// What the panel shows, so a poll redraws it only when that changed.
function sDeskPanelKey(held){const view=held.view,f=held.finish||{};return JSON.stringify([f.tool,view.finishing||{},view.working&&[view.working.id,view.working.kind,view.working.status],(view.jobs||[]).filter(job=>/^finish-/.test(job.kind)).slice(-4).map(job=>[job.id,job.status,job.error]),view.google_suggestions,view.revision,view.source_names?.length]);}
function sDeskPanelShow(held){if(!held.finish||!held.panel)return;const panel=sDeskPanel(held);held.panel.replaceWith(panel);held.panel=panel;held.panelKey=sDeskPanelKey(held);held.panelStale=false;}
// A redraw the person did not ask for waits while they use a control in the panel, and
// happens as soon as focus leaves it.
function sDeskPanelSync(held,force=false){
  if(!held.finish||!held.panel||(!force&&sDeskPanelKey(held)===held.panelKey))return true;
  const focused=typeof document.activeElement==='object'?document.activeElement:null;
  if(focused&&['INPUT','TEXTAREA','SELECT','BUTTON','SUMMARY'].includes(String(focused.tagName).toUpperCase())&&typeof held.panel.contains==='function'&&held.panel.contains(focused)){held.panelStale=true;return false;}
  sDeskPanelShow(held);return true;
}
function sDeskToolList(held){
  const list=sNode('div','pick-cards desk-finish-tools');
  for(const [key,name,says] of DESK_TOOLS){const card=sPickCard(name,sDeskToolSays(held,key)||says,()=>sDeskFinishTool(held,key));list.append(card);}
  return [sNode('p','quiet','Each tool proposes changes. Preview each one, then apply, edit or skip it. Nothing changes until you apply, and the earlier text stays in History.'),list];
}
function sDeskToolSays(held,key){
  const job=held.view.working;if(job&&job.kind==='finish-'+key)return 'Working on it…';
  const set=(held.view.finishing||{})[key];if(!set)return '';
  const open=set.items.filter(item=>item.state==='open').length;
  return open?open+(open===1?' to review.':' to review.'):'Nothing left to review.';
}
function sDeskToolView(held,key){
  if(key==='proofread')return sDeskProofView(held);
  if(key==='publish')return sDeskPublishView(held);
  const view=held.view,f=held.finish,kind='finish-'+key,set=(view.finishing||{})[key],working=view.working,[label,doing]=DESK_RUN[key];
  const parts=[sNode('p','quiet',DESK_TOOLS.find(([name])=>name===key)[2])];
  if(key==='humanize')parts.push(sChoice('Intensity',DESK_LEVELS,f,'level'));
  if(key==='voice'){
    if(!f.guides)parts.push(sNode('p','quiet','Reading your voice guides…'));
    else if(!f.guides.length){parts.push(sAdd(sNode('div','decision-notice'),sNode('p','','No voice guides yet. Write one, or make one from a few samples of the writing you want to sound like.'),sButton('Open voice guides',()=>sRoute('guides'))));}
    else{const says=sNode('p','quiet desk-guide-says',(f.guides.find(guide=>guide.id===f.guide)||{}).says||'');parts.push(sField('desk-voice-guide','Voice guide',f,'guide',{options:f.guides.map(guide=>[guide.id,guide.name]),changed:value=>{says.textContent=(f.guides.find(guide=>guide.id===value)||{}).says||'';}}),says);}
    if(f.guidesProblem)parts.push(sNode('p','problem',f.guidesProblem));
  }
  if(key==='facts'&&!(view.source_names||[]).length){const add=sButton('Add a source',()=>sDeskSourcesSheet(held));add.disabled=!access.actions.edit;parts.push(sAdd(sNode('div','decision-notice desk-problem'),sNode('p','','Facts are checked against your sources, and this draft has none yet.'),add));}
  const run=sButton(set?label+' again':label,button=>sDeskJob(held,button,'desk-finish',{tool:key,...(key==='humanize'?{level:f.level}:{}),...(key==='voice'?{guide:f.guide}:{})}),'filled');run.disabled=!access.actions.edit||!!working||key==='voice'&&!f.guide;
  parts.push(sAdd(sNode('div','bar'),run));
  if(working&&working.kind===kind){const note=sNode('p','desk-working-note',doing);note.setAttribute('role','status');parts.push(note);}
  else if(working)parts.push(sNode('p','quiet','Another change is under way. This can run when it ends.'));
  const last=(view.jobs||[]).filter(job=>job.kind===kind).at(-1);
  if(last&&!last.busy&&last.error&&(!set||set.job!==last.id))parts.push(sNode('p','problem',last.error));
  if(set)parts.push(...sDeskProposals(held,key,set));
  return parts;
}
function sDeskProposals(held,key,set){
  const items=set.items,open=items.filter(item=>item.state==='open'),out=[];
  if(key==='feedback'){
    if(set.summary)out.push(sCard('Overall',sNode('p','',set.summary)));
    if(!items.length)out.push(sNode('p','','No comments.'));
    const order=['whole','title','opening',...(held.view.sections||[]).map(section=>section.id)];
    for(const item of [...items].sort((a,b)=>order.indexOf(a.part)-order.indexOf(b.part)))out.push(sDeskComment(held,set,item,true));
    return out;
  }
  const facts=key==='facts',voice=key==='voice',checked=facts?open.filter(item=>item.verdict!=='supported'):open;
  const said=[items.length+(facts?(items.length===1?' claim checked':' claims checked'):voice?(items.length===1?' part rewritten':' parts rewritten'):items.length===1?' suggestion':' suggestions'),checked.length+' to review'];
  if(set.level)said.unshift('Found at '+set.level);
  if(voice&&set.guide_name)said.unshift('In the voice of '+set.guide_name);
  if(voice&&set.kept)said.push(set.kept+(set.kept===1?' part already reads':' parts already read')+' in this voice');
  if(set.dropped)said.push(set.dropped+' left out because '+(set.dropped===1?'it did not':'they did not')+' match the text');
  out.push(sNode('p','quiet',said.join(' · ')+'.'));
  if(!items.length){out.push(sNode('p','',key==='facts'?'No claims to check.':key==='copyedit'?'Nothing to fix.':voice?'Nothing to change: the draft already reads in this voice.':'Nothing to change at this level.'));return out;}
  // Apply all: every open proposal that still fits; flagged ones wait to be checked one by one.
  const ready=open.filter(item=>item.present&&!item.flag&&'after' in item);
  if((key==='copyedit'||key==='humanize'||voice)&&ready.length>1){
    const flagged=open.filter(item=>item.flag).length;
    const all=sButton('Apply all ('+ready.length+')',button=>sDeskApply(held,set,ready.map(item=>({id:item.id})),button));all.disabled=!access.actions.edit||!!held.view.working;
    out.push(sAdd(sNode('div','bar'),all),flagged?sNode('p','quiet',voice?flagged+(flagged===1?' part that changes a fact, code or the part’s shape is':' parts that change a fact, code or a part’s shape are')+' left for you to check one by one.':flagged+(flagged===1?' flagged suggestion is':' flagged suggestions are')+' left for you to check one by one.'):null);
  }
  if(key==='headline'){
    for(const [part,name] of [['title','Title'],['opening','Opening']]){const group=items.filter(item=>item.part===part);if(group.length)out.push(sNode('h3','sheet-part',name+' alternatives'),...group.map(item=>sDeskProposal(held,set,item,key)));}
    return out.filter(Boolean);
  }
  const supported=items.filter(item=>item.verdict==='supported');
  out.push(...items.filter(item=>item.verdict!=='supported').map(item=>sDeskProposal(held,set,item,key)));
  if(supported.length)out.push(disclosure('Supported ('+supported.length+')',...supported.map(item=>sDeskProposal(held,set,item,key))));
  return out.filter(Boolean);
}
// Before and after side by side: struck words only before, marked words only after.
function deskSides(before,after){
  const found=diffWords(before,after),box=sNode('div','desk-sides');
  const side=(title,words)=>sAdd(sNode('div','paper desk-side'),sNode('h4','sheet-part',title),words);
  const was=sNode('p','desk-plain'),now=sNode('p','desk-plain');
  if(!found){was.textContent=before;now.textContent=after;}
  else{let a=0,b=0;for(const piece of found){
    if(piece.op!=='added'){if(a++)was.append(document.createTextNode(' '));was.append(piece.op==='removed'?sNode('del','diff-remove',piece.text):sNode('span','',piece.text));}
    if(piece.op!=='removed'){if(b++)now.append(document.createTextNode(' '));now.append(piece.op==='added'?sNode('ins','diff-add',piece.text):sNode('span','',piece.text));}
  }}
  if(!String(before).trim())was.textContent='(Nothing yet)';
  if(!String(after).trim())now.textContent='(Removed)';
  return sAdd(box,side('Before',was),side('After',now));
}
function sDeskProposal(held,set,item,key){
  const f=held.finish,card=sNode('section','card desk-proposal');card.dataset.item=item.id;
  const head=sAdd(sNode('div','desk-part-head'),sNode('h3','row-title',key==='headline'?'Alternative':'In '+deskPartName(held.view,item.part)));
  if(item.verdict)head.append(sNode('span','tag',DESK_VERDICTS[item.verdict]));
  card.append(head);
  if(item.flag)card.append(sNode('p','decision-notice',item.flag));
  const editing=f.editing[item.id],hasAfter='after' in item;
  let sides=null;
  if(hasAfter||editing!==undefined){sides=deskSides(item.before,editing!==undefined?editing:item.after);card.append(sides);}
  else card.append(sNode('blockquote','desk-quote',item.before));
  if(item.note)card.append(sNode('p','quiet',item.note));
  if(item.verdict&&item.verdict!=='supported'&&!item.passage)card.append(sNode('p','quiet','No passage in your sources says this.'));
  if(item.passage)card.append(sNode('p','quiet','From '+(item.source||'your sources')+': “'+item.passage+'”'));
  if(item.state!=='open'){card.append(sNode('p','quiet',item.state==='applied'?'Applied. The earlier text is in History.':item.verdict?'Kept as it is.':'Skipped.'));return card;}
  const skip=sButton(item.verdict?'Keep it':'Skip',button=>sDeskSkip(held,set,[item.id],button));skip.disabled=!access.actions.edit;
  if(!item.present){card.append(sNode('p','quiet','The text changed since this was suggested, so it no longer fits.'),sAdd(sNode('div','bar'),skip));return card;}
  if(item.verdict==='supported')return card;
  const editable=access.actions.edit&&!held.view.working;
  if(editing!==undefined){
    const box=sNode('textarea','input desk-edit');box.id='desk-edit-'+item.id;box.rows=Math.min(12,Math.max(3,Math.ceil(editing.length/60)));box.value=editing;box.setAttribute('aria-label','Your wording');
    box.addEventListener('input',()=>{f.editing[item.id]=box.value;const next=deskSides(item.before,box.value);if(sides)sides.replaceWith(next);sides=next;});
    const use=sButton('Apply this',button=>sDeskApply(held,set,[{id:item.id,after:f.editing[item.id]}],button),'filled');use.disabled=!editable;
    card.append(box,sAdd(sNode('div','bar'),use,sButton('Cancel',()=>{delete f.editing[item.id];sDeskPanelShow(held);})));
    return card;
  }
  const edit=sButton(hasAfter?'Edit':'Fix the wording',()=>{f.editing[item.id]=hasAfter?item.after:item.before;sDeskPanelShow(held);});edit.disabled=!editable;
  const apply=hasAfter?sButton(key==='headline'?'Use this':'Apply',button=>sDeskApply(held,set,[{id:item.id}],button),'filled'):null;if(apply)apply.disabled=!editable;
  const source=item.verdict?sButton('Add a source',()=>sDeskSourcesSheet(held)):null;if(source)source.disabled=!access.actions.edit;
  card.append(sAdd(sNode('div','bar'),apply,edit,source,skip));
  return card;
}
async function sDeskApply(held,set,items,button){
  await busy(button,'Applying…',async()=>{try{
    await sDeskFlush(held);if(held.stale)return;
    const before=held.view;held.view=await api('desk-apply',{id:held.id,seen:held.view.revision,job:set.job,items});
    for(const item of items)delete held.finish.editing[item.id];
    const done=held.view.finished||{applied:items.length,left:[]},left=(done.left||[]).length;
    sToast((done.applied===1?'Applied.':'Applied '+done.applied+'.')+' The earlier text is in History.'+(left?' '+left+(left===1?' no longer fits and is':' no longer fit and are')+' left for you.':''));
    sDeskRefresh(held,before);sDeskPanelShow(held);
  }catch(error){if(/changed since/.test(error.message)){held.stale=true;sDeskStale(held);}else notice(error.message,true);}});
}
async function sDeskSkip(held,set,ids,button){
  await busy(button,'Setting aside…',async()=>{try{const before=held.view;held.view=await api('desk-skip',{id:held.id,job:set.job,items:ids});sDeskRefresh(held,before);sDeskPanelShow(held);}catch(error){notice(error.message,true);}});
}
// Feedback: comments shown in the panel and in their section cards, each a note in one click.
function sDeskCommentKey(view,part){const set=(view?.finishing||{}).feedback;return set?JSON.stringify(set.items.filter(item=>item.part===part&&item.state==='open').map(item=>item.id)):'';}
function sDeskComments(held,part){
  const set=(held.view.finishing||{}).feedback;if(!set)return null;
  const items=set.items.filter(item=>item.part===part&&item.state==='open');if(!items.length)return null;
  const box=sNode('div','desk-comments');box.setAttribute('aria-label','Feedback on this part');
  box.append(sNode('h3','sheet-part','Feedback'),...items.map(item=>sDeskComment(held,set,item,false)));
  return box;
}
function sDeskComment(held,set,item,inPanel){
  const card=sNode(inPanel?'section':'div',inPanel?'card desk-proposal desk-comment':'desk-comment');card.dataset.item=item.id;
  if(inPanel)card.append(sAdd(sNode('div','desk-part-head'),sNode('h3','row-title',item.part==='whole'?'The whole draft':'In '+deskPartName(held.view,item.part)),sNode('span','tag',DESK_ASPECTS[item.aspect]||'Shape')));
  if(item.quote)card.append(sNode('blockquote','desk-quote',item.quote));
  card.append(sNode('p','',item.comment));
  if(item.state!=='open'){card.append(sNode('p','quiet','Dismissed.'));return card;}
  const section=(held.view.sections||[]).some(found=>found.id===item.part),noted=(held.finish?.noted||{})[item.id];
  const make=sButton(noted?'In the note':section?'Make it a note':'Make it the whole-draft note',()=>sDeskToNote(held,item));make.disabled=!access.actions.edit;
  const dismiss=sButton('Dismiss',button=>sDeskSkip(held,set,[item.id],button));dismiss.disabled=!access.actions.edit;
  card.append(sAdd(sNode('div','bar'),make,dismiss));
  return card;
}
function sDeskToNote(held,item){
  const section=(held.view.sections||[]).find(found=>found.id===item.part);
  // Added to whatever note is there already, never over it.
  const comment=item.comment+(item.quote?' (About: “'+item.quote+'”)':''),join=had=>(had.trim()?had.replace(/\s+$/,'')+'\n\n':'')+comment;
  if(section){held.notes=held.notes||{};held.notes[item.part]=join(held.notes[item.part]||'').slice(0,4000);}else held.wholeNote=join(held.wholeNote||'').slice(0,4000);
  if(held.finish)held.finish.noted[item.id]=true;
  if(held.finish&&sNarrow())held.finish=null;  // On a phone the sheet steps aside for the note.
  if(held.tab!=='draft'||!held.cards||(section&&!held.cards[item.part])||sNarrow()){held.tab='draft';sDeskRender(held);}
  else{
    if(section){const card=sDeskPart(held,item.part);held.cards[item.part].replaceWith(card);held.cards[item.part]=card;}
    else{const whole=sDeskWhole(held);held.wholeCard.replaceWith(whole);held.wholeCard=whole;}
    sDeskPanelShow(held);
  }
  const target=section?held.cards?.[item.part]?.querySelector('.desk-note-text'):held.wholeCard?.querySelector('textarea');
  if(target){target.focus();if(typeof target.scrollIntoView==='function')target.scrollIntoView({block:'center'});}
  sToast(section?'Now the note for “'+section.heading+'”. Choose Rewrite when you are ready.':'Now the note for the whole draft. Choose Revise the draft when you are ready.');
}
// Quick check (proofread): in place, at once; Fix rewrites only the sentence a finding is in.
async function sDeskProofread(held,button){
  const go=async()=>{try{await sDeskFlush(held);const found=await api('desk-proofread?'+new URLSearchParams({id:held.id}));if(!held.finish)return;held.finish.proof=found;held.finish.proofProblem='';}catch(error){if(held.finish)held.finish.proofProblem=error.message;}sDeskPanelShow(held);};
  if(button)await busy(button,'Checking…',go);else await go();
}
function sDeskProofView(held){
  const f=held.finish,found=f.proof;
  const again=sButton(found?'Check again':'Check now',button=>sDeskProofread(held,button),'filled');
  const parts=[sNode('p','quiet',DESK_TOOLS.find(([key])=>key==='proofread')[2]+' Fix rewrites only the sentence a finding is in, and keeps the earlier text in History.'),sAdd(sNode('div','bar'),again)];
  if(f.proofProblem)parts.push(sNode('p','problem',f.proofProblem));
  if(!found)return parts;
  if(found.revision!==held.view.revision)parts.push(sNode('p','quiet','The draft changed since this check. Check again for the latest.'));
  if(!found.findings.length){parts.push(sNode('p','','Nothing found by these checks.'));return parts;}
  parts.push(sNode('p','quiet',found.findings.length+(found.findings.length===1?' finding':' findings')+(found.more?', and '+found.more+' more':'')+'. '+found.limitations));
  for(const finding of found.findings)parts.push(sDeskFinding(held,finding));
  return parts;
}
function sDeskFinding(held,finding){
  const card=sNode('section','card desk-proposal');
  card.append(sAdd(sNode('div','desk-part-head'),sNode('h3','row-title','In '+deskPartName(held.view,finding.part))),sNode('p','',finding.label));
  const said=sNode('p','desk-plain desk-quote'),at=finding.at-finding.start;
  if(at>=0&&finding.sentence.slice(at,at+finding.target.length)===finding.target)said.append(document.createTextNode(finding.sentence.slice(0,at)),sNode('mark','',finding.target),document.createTextNode(finding.sentence.slice(at+finding.target.length)));
  else said.textContent=finding.sentence;
  const still=deskTextOf(held.view,finding.part).slice(finding.start,finding.start+finding.sentence.length)===finding.sentence;
  const fix=sButton('Fix',button=>sDeskJob(held,button,'desk-selection',{part:finding.part,text:finding.sentence,start:finding.start,action:'fix',instruction:finding.fix}));fix.disabled=!access.actions.edit||!!held.view.working||!still;
  return sAdd(card,said,sAdd(sNode('div','bar'),fix),still?null:sNode('p','quiet','This sentence changed since the check.'));
}
// Before publishing: the pre-publish check, Repurpose into new blogs, and Google suggestions,
// each reading the desk's latest text.
function sDeskPublishView(held){
  const f=held.finish,p=f.publish||(f.publish={check:null,checkProblem:'',copy:{format:'linkedin',words:'150',audience:'',url:''},job:null,content:null,title:'',made:null,copyProblem:'',google:{mode:'auto'},plan:null,sent:null,googleProblem:''});
  return [sDeskPrepublishCard(held,p),sDeskRepurposeCard(held,p),sDeskGoogleCard(held,p)];
}
function sDeskPrepublishCard(held,p){
  const run=sButton(p.check?'Check again':'Run the check',async button=>{await busy(button,'Checking…',async()=>{try{await sDeskFlush(held);p.check=await api('prepublish?id='+encodeURIComponent(held.id));p.checkProblem='';}catch(error){p.checkProblem=error.message;}sDeskPanelShow(held);});},'filled');
  const card=sCard('Pre-publish check',sNode('p','quiet','Headings, placeholders, links and evidence references in the latest text. Report only: nothing changes.'),sAdd(sNode('div','bar'),run));
  if(p.checkProblem)card.append(sNode('p','problem',p.checkProblem));
  if(p.check){const list=sNode('ul','look');for(const item of p.check.findings)list.append(sNode('li','','Line '+item.line+': '+item.detail));card.append(p.check.findings.length?list:sNode('p','','No findings from these checks.'),sNode('p','quiet',p.check.coverage||''));}
  return card;
}
function sDeskRepurposeCard(held,p){
  const card=sCard('Repurpose',sNode('p','quiet','Prepare channel copy from the latest text; each copy you keep becomes a new blog on the desk. Nothing is posted.'));
  if(p.copyProblem)card.append(sNode('p','problem',p.copyProblem));
  if(p.made){card.append(sNode('p','','Made “'+p.made.title+'” as a new blog on the desk.'),sAdd(sNode('div','bar'),sButton('Open it',()=>sRoute('desk',p.made.id),'filled'),sButton('Prepare another',()=>{Object.assign(p,{job:null,content:null,title:'',made:null,copyProblem:''});sDeskPanelShow(held);})));return card;}
  const job=p.job;
  if(job&&['queued','working'].includes(job.status)){const note=sNode('p','desk-working-note','Preparing the copy…');note.setAttribute('role','status');card.append(note,sAdd(sNode('div','bar'),sButton('Cancel',async button=>{await busy(button,'Cancelling…',async()=>{try{p.job=await api('tool-action',{action:'job-control',job:job.id,control:'cancel'});}catch(error){p.copyProblem=error.message;}sDeskPanelShow(held);});})));sDeskRepurposeFollow(held,p);return card;}
  if(job&&job.status==='ready'){
    if(p.content===null)p.content=job.result?.content||'';
    if(!p.title)p.title=held.view.title+' ('+((DESK_FORMATS.find(([key])=>key===job.metadata?.format)||[])[1]||'copy')+')';
    const make=sButton('Make it a new blog',async button=>{await busy(button,'Making…',async()=>{try{const shown=await api('desk-repurpose',{id:held.id,job:job.id,title:p.title.trim(),content:p.content});p.made=shown.made;p.copyProblem='';held.view=shown;sToast('Made a new blog on the desk. Nothing was posted.');}catch(error){p.copyProblem=error.message;}sDeskPanelShow(held);});},'filled');make.disabled=!access.actions.edit;
    sAdd(card,sField('desk-copy','The prepared copy',p,'content',{long:true,max:200000}),sField('desk-copy-title','Title for the new blog',p,'title',{max:500}),job.result?.notes?sNode('p','quiet',job.result.notes):null,sAdd(sNode('div','bar'),make,sButton('Discard',()=>{Object.assign(p,{job:null,content:null,title:''});sDeskPanelShow(held);})));
    return card;
  }
  if(job&&job.error)card.append(sNode('p','problem',job.error));
  const prepare=sButton('Prepare copy',async button=>{await busy(button,'Starting…',async()=>{try{await sDeskFlush(held);p.job=await api('tool-action',{action:'job-create',kind:'repurpose',id:held.id,operation:operationId(),format:p.copy.format,words:Number(p.copy.words),audience:p.copy.audience,url:p.copy.url});p.content=null;p.title='';p.copyProblem='';}catch(error){p.copyProblem=error.message;}sDeskPanelShow(held);});},'filled');prepare.disabled=!access.actions.edit;
  card.append(sField('desk-copy-format','Copy format',p.copy,'format',{options:DESK_FORMATS}),sField('desk-copy-words','Target words',p.copy,'words',{type:'number',min:30,maximum:1500}),sField('desk-copy-reader','Reader (optional)',p.copy,'audience',{max:2000}),sField('desk-copy-url','Article URL (optional)',p.copy,'url',{max:2000}),sAdd(sNode('div','bar'),prepare));
  return card;
}
function sDeskRepurposeFollow(held,p){
  if(p.following)return;p.following=true;
  setTimeout(async()=>{
    p.following=false;if(!sDeskCurrent(held)||held.finish?.publish!==p||!p.job)return;
    try{p.job=await api('tool-job?job='+encodeURIComponent(p.job.id));}catch(error){p.copyProblem=error.message;}
    if(held.finish?.tool==='publish')sDeskPanelSync(held,true);
    if(['queued','working'].includes(p.job?.status))sDeskRepurposeFollow(held,p);
  },DESK_POLL);
}
function sDeskGoogleCard(held,p){
  const view=held.view,card=sCard('Send to Google Doc as suggestions');
  if(!view.google_suggestions){card.append(sNode('p','','This blog has no Google Doc to send to. A blog started from a Google Doc can send its desk changes back to that Doc as suggestions for its owner to accept.'));return card;}
  card.append(sNode('p','quiet','Your desk wording goes to the Google Doc as suggestions its owner accepts or rejects. Paragraphs added or removed stay here.'));
  if(view.google?.url){const doc=link(view.google.url,'Open the Google Doc ↗');card.append(sAdd(sNode('p',''),doc));}
  if(p.googleProblem)card.append(sNode('p','problem',p.googleProblem));
  const check=sButton(p.plan?'Check again':'Check what would be sent',async button=>{await busy(button,'Checking…',async()=>{try{await sDeskFlush(held);p.plan=await api('desk-google-plan',{id:held.id,mode:p.google.mode});p.sent=null;p.googleProblem='';}catch(error){p.plan=null;p.googleProblem=error.message;}sDeskPanelShow(held);});},p.plan?'quiet':'filled');check.disabled=!access.actions.edit;
  if(p.sent){card.append(sStatus(['verified-pending','verified-comments'].includes(p.sent.status)?'done':'late',p.sent.message));}
  if(p.plan&&!p.sent){
    const changes=sNode('ul','look');for(const item of p.plan.proposals||[])changes.append(sNode('li','','“'+item.before+'” → “'+item.after+'”'));
    const send=sButton('Send to Google Doc',async button=>{await busy(button,'Sending…',async()=>{try{const result=await api('desk-google-send',{id:held.id,plan:p.plan.plan,confirmed:true});p.sent={status:result.status,message:result.status==='verified-pending'?'Suggestions are ready for the Doc’s owner to accept or reject.':result.status==='verified-comments'?'Comments were added to the Google Doc.':'The result is not yet verified. Check delivery before trying anything else.'};p.googleProblem='';}catch(error){p.googleProblem=error.message;if(/changed/.test(error.message))p.plan=null;}sDeskPanelShow(held);});},'filled');send.disabled=!access.actions.edit;
    card.append(sNode('p','',p.plan.count+(p.plan.count===1?' wording change':' wording changes')+' checked against the Google Doc.'+(p.plan.left?' '+p.plan.left+(p.plan.left===1?' changed paragraph cannot be a suggestion and stays':' changed paragraphs cannot be suggestions and stay')+' on the desk.':'')),disclosure('What would be sent',changes),sAdd(sNode('div','bar'),send,check));
    return card;
  }
  if(p.sent&&!['verified-pending','verified-comments'].includes(p.sent.status)&&p.plan){card.append(sAdd(sNode('div','bar'),sButton('Check delivery',async button=>{await busy(button,'Checking…',async()=>{try{const result=await api('desk-google-send',{id:held.id,plan:p.plan.plan,confirmed:true});p.sent={status:result.status,message:result.status==='verified-pending'?'Suggestions are ready for the Doc’s owner to accept or reject.':result.status==='verified-comments'?'Comments were added to the Google Doc.':'The result is not yet verified. Check delivery before trying anything else.'};}catch(error){p.googleProblem=error.message;}sDeskPanelShow(held);});},'filled')));return card;}
  card.append(sField('desk-google-mode','Send as',p.google,'mode',{options:[['auto','Suggestions, with comments fallback'],['native','Suggestions only'],['comments','Comments only']]}),sAdd(sNode('div','bar'),check));
  return card;
}

// Review mode ("Check spelling and grammar"): where polishing a draft lands. Copy edit runs on
// its own; the draft then reads section by section with each fix marked in place, struck words
// out and highlighted words in, its reason under the paragraph, and Accept or Reject on each.
// Accept is Finishing's apply of that fix, keeping a version; Reject sets it aside. A flagged
// fix (it changes a fact, code or shape) waits to be checked one by one. Any paragraph can be
// clicked and edited in place; it saves after a short pause or when focus leaves it, and a fix
// whose words are no longer in the text drops out. Every text is set with textContent.
const REVIEW_CHECKING='Checking spelling and grammar…';
const REVIEW_INLINE=/(\*\*|__)(?=\S)([^\n]*?\S)\1|(?<![*\w])\*(?=[^\s*])([^*\n]*?[^\s*])\*(?![*\w])|`([^`\n]+)`|!\[[^\[\]\n]*\]\[[^\[\]\n]*\]|!\[[^\[\]\n]*\]\([^)\n]*\)|\[([^\[\]\n]+)\]\(([^)\s]+)[^)\n]*\)|\\([\\`*_{}\[\]()#+\-.!<>|~])/g;
function deskHeading(text){return String(text||'').replace(/^(\*\*|__)(.+)\1$/,'$2');}
function sReviewOn(held){held.mode='review';held.review=held.review||{editing:null,parts:{},google:null};sDeskModeUrl(held);}
// The desk's address says which view is shown, without a new history entry.
function sDeskModeUrl(held){const review=held.mode==='review';if(studio.screen!=='desk'||(studio.stage==='review')===review)return;studio.stage=review?'review':null;history.replaceState(null,'',location.pathname+'?'+new URLSearchParams({screen:'desk',id:held.id,...(review?{stage:'review'}:{})}));}
// Markdown as plain reading: bold, emphasis, code and link words shown, list marks as bullets,
// image references left to their thumbnails. `lineStart` says whether the text starts a line.
function reviewInline(text,lineStart=true){
  const out=[];
  String(text).split('\n').forEach((line,index)=>{
    if(index)out.push(document.createTextNode('\n'));
    if(index||lineStart)line=line.replace(/^([ \t]*)[*+-][ \t]+/,'$1• ').replace(/^#{1,6}[ \t]+/,'');
    let at=0;
    for(const found of line.matchAll(REVIEW_INLINE)){
      if(found.index>at)out.push(document.createTextNode(line.slice(at,found.index)));
      if(found[2]!==undefined)out.push(sNode('strong','',found[2]));
      else if(found[3]!==undefined)out.push(sNode('em','',found[3]));
      else if(found[4]!==undefined)out.push(sNode('code','',found[4]));
      else if(found[5]!==undefined){const word=sNode('span','review-link',found[5]);word.title=found[6];out.push(word);}
      else if(found[7]!==undefined)out.push(document.createTextNode(found[7]));
      at=found.index+found[0].length;
    }
    if(at<line.length)out.push(document.createTextNode(line.slice(at)));
  });
  return out;
}
// Where blocks (paragraphs) of a part's text start and end: at blank lines, but never inside
// fenced code or inside a fix's words.
function reviewBlocks(text,marks){
  const fenced=[];let open=null,offset=0;
  for(const line of text.split('\n')){if(/^ {0,3}(`{3,}|~{3,})/.test(line)){if(open===null)open=offset;else{fenced.push([open,offset+line.length]);open=null;}}offset+=line.length+1;}
  if(open!==null)fenced.push([open,text.length]);
  const inside=(at,ranges)=>ranges.some(([from,to])=>at>from&&at<to);
  const spans=marks.map(item=>[item.at,item.at+item.before.length]),blocks=[];let start=0;
  for(const found of text.matchAll(/\n[ \t]*\n\s*/g)){if(inside(found.index,fenced)||inside(found.index,spans))continue;blocks.push({start,end:found.index});start=found.index+found[0].length;}
  blocks.push({start,end:text.length});
  return blocks.filter(block=>block.end>block.start||!text).map(block=>({...block,text:text.slice(block.start,block.end)}));
}
// The newest Copy edit and what is left of it: open fixes whose words are still in the text,
// placed where they sit, in reading order and numbered; the flagged ones; the gone ones.
function sReviewState(held){
  const view=held.view,set=(view.finishing||{}).copyedit||null,working=view.working&&view.working.kind==='finish-copyedit'?view.working:null;
  const parts=['title','opening',...(view.sections||[]).map(section=>section.id)];
  const open=set?set.items.filter(item=>item.state==='open'):[],pending=[],gone=[];
  for(const item of open){const text=deskTextOf(view,item.part),at=item.present&&parts.includes(item.part)?text.indexOf(item.before):-1;if(at<0||!('after' in item))gone.push(item);else pending.push({...item,at});}
  pending.sort((a,b)=>parts.indexOf(a.part)-parts.indexOf(b.part)||a.at-b.at);pending.forEach((item,index)=>{item.number=index+1;});
  const last=(view.jobs||[]).filter(job=>job.kind==='finish-copyedit').at(-1);
  const failed=!working&&last&&!last.busy&&last.error&&(!set||set.job!==last.id)?last.error:'';
  return {set,working,parts,pending,gone,ready:pending.filter(item=>!item.flag),flagged:pending.filter(item=>item.flag),failed,applied:set?set.items.filter(item=>item.state==='applied').length:0};
}
// Drawn again only when what it shows changes, so a poll never swaps a button being pressed.
function sReviewToolbar(held,state,force=false){
  const key=JSON.stringify([held.view.title,!!state.working,!!held.view.working,access.actions.edit,sNarrow()]);
  if(!force&&held.review?.toolbarKey===key&&studio.screen==='desk')return;if(held.review)held.review.toolbarKey=key;
  const again=sButton('Check again',button=>sReviewCheck(held,button));again.disabled=!access.actions.edit||!!held.view.working;
  const full=sButton('Open the full desk',async()=>{await sReviewFlush(held);held.mode=null;sDeskModeUrl(held);held.tab='draft';sDeskRender(held);sDeskWatch(held);});
  sFrame(held.view.title,sFold([again,full]),state.working?REVIEW_CHECKING:'Check spelling and grammar',()=>sRoute('blogs'));
}
function sDeskReview(held){
  sReviewOn(held);const state=sReviewState(held);sReviewToolbar(held,state,true);held.layout=sDeskLayout();held.cards=null;held.wholeCard=null;held.wholeGo=null;
  const status=sNode('p','quiet desk-save-state');status.setAttribute('role','status');status.setAttribute('aria-live','polite');held.status=status;
  if(held.stale)sDeskStale(held);else status.textContent=held.saved||'';
  held.review.head=sReviewHead(held,state);held.review.paper=sReviewPaper(held,state);
  held.review.lede=sNode('p','lede',sReviewLede(state));
  sPage(held.review.lede,status,held.review.head,held.review.paper);
  sDeskImagesLoad(held);
}
// What needs the person first: the check under way, a problem, the count with Accept all and
// Reject all, or, once nothing is left, where the draft goes next.
function sReviewHead(held,state){
  const head=sNode('div','review-head'),editable=access.actions.edit&&!held.view.working;
  if(state.working){
    const line=sNode('p','desk-working-note',REVIEW_CHECKING);line.setAttribute('role','status');
    const stop=sButton('Stop',async button=>{await busy(button,'Stopping…',async()=>{try{const before=held.view;held.view=await api('desk-stop',{id:held.id,job:state.working.id});sDeskRefresh(held,before);}catch(error){notice(error.message,true);}});});stop.disabled=!access.actions.edit;
    return sAdd(head,sAdd(sNode('div','card review-checking'),line,sAdd(sNode('div','bar'),stop)));
  }
  if(state.failed){const again=sButton('Check again',button=>sReviewCheck(held,button),'filled');again.disabled=!access.actions.edit;return sAdd(head,sAdd(sNode('div','decision-notice desk-problem'),sNode('p','','The check did not finish: '+state.failed),again));}
  if(!state.set){const go=sButton('Check spelling and grammar',button=>sReviewCheck(held,button),'filled');go.disabled=!access.actions.edit;return sAdd(head,sCard('Check spelling and grammar',sNode('p','','Each fix is marked in your text for you to accept or reject.'),sAdd(sNode('div','bar'),go)));}
  if(state.pending.length){
    const count=sNode('p','review-count',state.pending.length+(state.pending.length===1?' fix to review':' fixes to review'));count.setAttribute('role','status');
    const all=sButton('Accept all ('+state.ready.length+')',button=>sReviewAccept(held,state.set,state.ready.map(item=>item.id),button),'filled');all.disabled=!editable||!state.ready.length;
    const none=sButton('Reject all',button=>sReviewReject(held,state.set,state.set.items.filter(item=>item.state==='open').map(item=>item.id),button));none.disabled=!access.actions.edit;
    const flagged=state.flagged.length?sNode('p','quiet',state.flagged.length+(state.flagged.length===1?' fix changes a fact, code or the shape of a part, so Accept all leaves it for you to check.':' fixes change a fact, code or the shape of a part, so Accept all leaves them for you to check.')):null;
    return sAdd(head,sAdd(sNode('div','card review-tally'),count,sAdd(sNode('div','bar'),all,none)),flagged);
  }
  return sAdd(head,sReviewDone(held,state));
}
function sReviewDone(held,state){
  const said=state.set.items.length?'Accepted '+state.applied+' of '+state.set.items.length+(state.set.items.length===1?' fix.':' fixes.'):'No fixes were needed.';
  const card=sCard('Nothing left to review',sNode('p','',said+' Every accepted fix kept the earlier text in History.'));card.className+=' review-done';
  if(held.view.google_suggestions)return sAdd(card,...sReviewGoogle(held));
  const copy=sButton('Copy',async()=>{if(typeof navigator==='undefined'||!navigator.clipboard?.writeText)throw new Error('Download the draft and copy it from there.');const found=await sDeskMarkdown(held);await navigator.clipboard.writeText(found.markdown);sToast(deskWithout('Markdown copied',found.missing));},'filled');
  const download=sButton('Download',async()=>{const found=await sDeskMarkdown(held);await sDownload({content:found.markdown,name:'DRAFT.md'});if(found.missing.length)sToast(deskWithout('Downloaded',found.missing));});
  return sAdd(card,sAdd(sNode('div','bar'),copy,download));
}
// The accepted fixes, and any paragraph edited here, go to the Google Doc as suggestions for
// its owner: the plan says how many first, and nothing is sent until Send.
function sReviewGoogle(held){
  const g=held.review.google||(held.review.google={plan:null,sent:null,problem:''}),out=[];
  if(g.problem)out.push(sNode('p','problem',g.problem));
  if(g.sent){out.push(sStatus(['verified-pending','verified-comments'].includes(g.sent.status)?'done':'late',g.sent.message));if(held.view.google?.url)out.push(sAdd(sNode('p',''),link(held.view.google.url,'Open the Google Doc ↗')));return out;}
  if(g.plan){
    const changes=sNode('ul','look');for(const item of g.plan.proposals||[])changes.append(sNode('li','','“'+item.before+'” → “'+item.after+'”'));
    const count=g.plan.count;
    const send=sButton('Send '+count+(count===1?' change':' changes'),async button=>{await busy(button,'Sending…',async()=>{try{const result=await api('desk-google-send',{id:held.id,plan:g.plan.plan,confirmed:true});g.sent={status:result.status,message:result.status==='verified-pending'?'Suggestions are ready for the Doc’s owner to accept or reject.':result.status==='verified-comments'?'Comments were added to the Google Doc.':'The result is not yet verified. Check delivery in the full desk’s Finishing before trying anything else.'};g.problem='';}catch(error){g.problem=error.message;if(/changed/.test(error.message))g.plan=null;}sReviewHeadShow(held);});},'filled');send.disabled=!access.actions.edit;
    out.push(sNode('p','',count+(count===1?' wording change goes':' wording changes go')+' to the Google Doc as suggestions for its owner to accept or reject.'+(g.plan.left?' '+g.plan.left+(g.plan.left===1?' changed paragraph cannot be a suggestion and stays':' changed paragraphs cannot be suggestions and stay')+' here.':'')),disclosure('What would be sent',changes),sAdd(sNode('div','bar'),send,sButton('Cancel',()=>{g.plan=null;sReviewHeadShow(held);})));
    return out;
  }
  const plan=sButton('Send accepted changes to Google Doc',async button=>{await busy(button,'Checking…',async()=>{try{await sReviewFlush(held);g.plan=await api('desk-google-plan',{id:held.id,mode:'auto'});g.problem='';}catch(error){g.plan=null;g.problem=error.message;}sReviewHeadShow(held);});},'filled');plan.disabled=!access.actions.edit;
  out.push(sNode('p','quiet','Sends every difference from the Google Doc as it was read: the fixes you accepted and any edits you made. Rejected fixes are never sent.'),sAdd(sNode('div','bar'),plan));
  return out;
}
function sReviewLede(state){
  if(state.working)return 'Copy edit is reading your draft for spelling, grammar and wordy sentences. Read or edit it meanwhile.';
  if(state.set&&!state.pending.length&&!state.failed)return 'Every fix is reviewed. Click any paragraph to keep editing, or Check again for the latest text.';
  return 'Each fix is marked in your text: struck words go, highlighted words come in. Accept or reject each one, or click a paragraph to edit it yourself. Nothing changes until you accept.';
}
function sReviewHeadShow(held){if(!held.review?.head)return;const head=sReviewHead(held,sReviewState(held));held.review.head.replaceWith(head);held.review.head=head;}
// The reading surface: the title, the opening and each section, every paragraph with its
// fixes marked, opaque like any document.
function sReviewPaper(held,state){
  const paper=sNode('article','paper review-paper');paper.setAttribute('aria-label','Your draft with its fixes marked');held.review.parts={};
  for(const part of state.parts){const box=sReviewPart(held,part,state);if(box){held.review.parts[part]=box;paper.append(box);}}
  return paper;
}
function sReviewKey(held,part,state){const editing=held.review.editing;return JSON.stringify([deskTextOf(held.view,part),!!state.working,state.pending.filter(item=>item.part===part).map(item=>[item.id,item.number,item.at,item.after,item.flag,item.note]),state.gone.filter(item=>item.part===part).length,editing&&editing.part===part?editing.start:null,(held.view.sections||[]).find(section=>section.id===part)?.heading||'']);}
function sReviewPart(held,part,state){
  const view=held.view,text=deskTextOf(view,part),section=(view.sections||[]).find(row=>row.id===part);
  const marks=state.working?[]:state.pending.filter(item=>item.part===part),gone=state.working?[]:state.gone.filter(item=>item.part===part);
  if(part==='opening'&&!text.trim()&&!marks.length)return null;
  const box=sNode(part==='title'?'header':'section','review-part');box.dataset.part=part;box.deskKey=sReviewKey(held,part,state);
  if(section)box.append(sNode('h3','review-heading',deskHeading(section.heading)));
  // Fixes that overlap one another are listed under the part, not marked in it.
  const placed=[],loose=[];let end=-1;
  for(const item of marks){if(item.at>=end){placed.push(item);end=item.at+item.before.length;}else loose.push(item);}
  const blocks=part==='title'?[{start:0,end:text.length,text}]:reviewBlocks(text,placed);
  for(const block of blocks)box.append(sReviewBlock(held,part,block,placed.filter(item=>item.at>=block.start&&item.at<block.end||!block.text&&item.at===block.start)));
  if(loose.length)box.append(sReviewFixes(held,state.set,loose,true));
  if(gone.length)box.append(sNode('p','quiet review-gone',gone.length+(gone.length===1?' fix no longer fits this text, so it was left out.':' fixes no longer fit this text, so they were left out.')));
  return box;
}
function sReviewBlock(held,part,block,marks){
  const view=held.view,wrap=sNode('div','review-block'),editing=held.review.editing;
  if(editing&&editing.part===part&&editing.start===block.start){const note=sNode('p','quiet review-editing',editing.said||'Saves as you type. Click outside the box to finish; its fixes come back.');note.setAttribute('aria-live','polite');editing.note=note;wrap.append(sReviewEditor(held,editing),note);return wrap;}
  const images=deskImagesIn(view,block.text),lost=deskImagesMissing(view,block.text),words=block.text.replace(DESK_IMAGE_REF,'').trim();
  if(words||!images.length&&!lost.length){
    const shown=sNode(part==='title'?'h2':'p',part==='title'?'review-title review-text':'review-text');
    let at=block.start;const text=deskTextOf(view,part);
    for(const item of marks){
      if(item.at>at)shown.append(...reviewInline(text.slice(at,item.at),at===0||text[at-1]==='\n'));
      const mark=sNode('span','review-mark'+(item.flag?' review-flagged':''));mark.dataset.item=item.id;
      const found=diffWords(item.before,item.after);
      if(!found)mark.append(sNode('del','review-old',item.before),document.createTextNode(' '),sNode('ins','review-new',item.after));
      else found.forEach((piece,index)=>{if(index)mark.append(document.createTextNode(' '));if(piece.op==='same')mark.append(...reviewInline(piece.text,false));else mark.append(sNode(piece.op==='added'?'ins':'del',piece.op==='added'?'review-new':'review-old',piece.text));});
      mark.append(sNode('sup','review-num',String(item.number)));
      shown.append(mark);at=item.at+item.before.length;
    }
    if(at<block.end)shown.append(...reviewInline(text.slice(at,block.end),at===0||text[at-1]==='\n'));
    if(!block.text)shown.append(sNode('span','quiet',part==='title'?'No title yet':'Nothing written yet'));
    if(access.actions.edit){shown.tabIndex=0;shown.title='Click to edit';shown.addEventListener('click',()=>sReviewEdit(held,part,block));shown.addEventListener('keydown',event=>{if(event.key==='Enter'&&!event.shiftKey){event.preventDefault?.();sReviewEdit(held,part,block);}});}
    wrap.append(shown);
  }
  if(part!=='title'){const thumbs=sDeskThumbsFor(view,block.text);if(thumbs)wrap.append(thumbs);}
  if(marks.length)wrap.append(sReviewFixes(held,(view.finishing||{}).copyedit,marks,false));
  return wrap;
}
// Each fix's number, reason and flag, with Accept and Reject; stacked on a phone.
function sReviewFixes(held,set,items,loose){
  const list=sNode('ol','review-fixes');list.setAttribute('aria-label',loose?'Fixes that overlap others':'Fixes in this paragraph');
  const editable=access.actions.edit&&!held.view.working;
  for(const item of items){
    const row=sNode('li','review-fix'+(item.flag?' review-flagged':''));row.dataset.item=item.id;
    const said=sAdd(sNode('div','review-why'),sNode('span','review-num',String(item.number)),sNode('span','',item.note||'A fix.'));
    if(item.flag)said.append(sNode('span','tag','Check this'));
    row.append(said);
    if(item.flag)row.append(sNode('p','quiet',item.flag));
    if(loose)row.append(deskSides(item.before,item.after));
    const accept=sButton('Accept',button=>sReviewAccept(held,set,[item.id],button));accept.disabled=!editable;accept.setAttribute('aria-label','Accept fix '+item.number);
    const reject=sButton('Reject',button=>sReviewReject(held,set,[item.id],button));reject.disabled=!access.actions.edit;reject.setAttribute('aria-label','Reject fix '+item.number);
    row.append(sAdd(sNode('div','bar'),accept,reject));list.append(row);
  }
  return list;
}
// A poll, a save or a job landing redraws only what changed, never a paragraph being edited.
function sDeskReviewRefresh(held,before){
  if(!sDeskCurrent(held)||!held.review?.paper)return;
  const state=sReviewState(held);sReviewToolbar(held,state);
  const head=sReviewHead(held,state);held.review.head.replaceWith(head);held.review.head=head;
  if(held.review.lede)held.review.lede.textContent=sReviewLede(state);
  // Sections added or taken away, or an opening that appears or goes: drawn again whole,
  // unless a paragraph is being edited, when it waits for the editor to close.
  const drawn=Object.keys(held.review.parts).join(','),wanted=state.parts.filter(part=>held.review.parts[part]||part!=='opening'||deskTextOf(held.view,part).trim()).join(',');
  if(drawn!==wanted){if(!held.review.editing)sDeskReview(held);return;}
  for(const part of state.parts){
    const old=held.review.parts[part];
    if(!old||held.review.editing?.part===part||old.deskKey===sReviewKey(held,part,state))continue;
    const box=sReviewPart(held,part,state);if(!box)continue;
    old.replaceWith(box);held.review.parts[part]=box;
  }
  sDeskImagesLoad(held);
}
function sReviewEditor(held,editing){
  const title=editing.part==='title',box=sNode(title?'input':'textarea','input review-editor');
  box.value=editing.text;box.setAttribute('aria-label',title?'Edit the title':'Edit this paragraph');
  if(title){box.type='text';box.maxLength=500;}else box.rows=Math.min(16,Math.max(3,Math.ceil(editing.text.length/80)+editing.text.split('\n').length));
  box.addEventListener('input',()=>{editing.text=box.value;editing.dirty=true;sReviewSaid(held,editing,'Saving…');if(editing.timer&&typeof clearTimeout==='function')clearTimeout(editing.timer);editing.timer=setTimeout(()=>sReviewSave(held),DESK_SAVE_WAIT);});
  // Leaving the paragraph saves it and shows it marked again; a click on Accept or Reject
  // elsewhere goes ahead first, and saves it before it acts.
  box.addEventListener('blur',()=>{setTimeout(()=>{if(held.review.editing===editing&&!sDeskTyping(held.review.paper))sReviewClose(held);},150);});
  editing.box=box;return box;
}
async function sReviewEdit(held,part,block){
  if(held.review.editing){if(held.review.editing.part===part&&held.review.editing.start===block.start)return;await sReviewClose(held);block=sReviewBlockAt(held,part,block)||block;}
  held.review.editing={part,start:block.start,original:block.text,text:block.text,dirty:false};
  const old=held.review.parts[part],box=sReviewPart(held,part,sReviewState(held));if(old&&box){old.replaceWith(box);held.review.parts[part]=box;}
  const editor=held.review.editing.box;if(editor){editor.focus();if(typeof editor.setSelectionRange==='function'){const end=editor.value.length;editor.setSelectionRange(end,end);}}
}
// The block that started at the same place, after the text around it changed.
function sReviewBlockAt(held,part,block){const text=deskTextOf(held.view,part);return part==='title'?{start:0,end:text.length,text}:reviewBlocks(text,[]).find(found=>found.text===block.text)||null;}
// Save the paragraph being edited into its part, at the place it was found.
async function sReviewSave(held){
  const editing=held.review?.editing;if(!editing||!editing.dirty||held.stale)return;
  if(editing.timer&&typeof clearTimeout==='function')clearTimeout(editing.timer);editing.timer=null;
  while(held.saving)await held.saving;
  const whole=deskTextOf(held.view,editing.part),typed=editing.part==='title'?editing.text:editing.text.replace(/\s+$/,'');
  let at=whole.slice(editing.start,editing.start+editing.original.length)===editing.original?editing.start:whole.indexOf(editing.original);
  if(at<0||editing.original&&whole.indexOf(editing.original,at+1)!==-1&&at!==editing.start){sReviewSaid(held,editing,'This paragraph changed elsewhere. Your words are kept in the box; reload to see the latest.');return;}
  const text=whole.slice(0,at)+typed+whole.slice(at+editing.original.length);editing.dirty=false;
  held.saving=(async()=>{try{
    const before=held.view;held.view=await api('desk-save',{id:held.id,seen:held.view.revision,part:editing.part,text,session:held.session});
    const now=deskTextOf(held.view,editing.part),lead=text.length-text.replace(/^\s+/,'').length;
    editing.start=Math.max(0,Math.min(at-lead,now.length));editing.original=now.slice(editing.start,editing.start+typed.length)===typed?typed:typed.trim();
    if(now.indexOf(editing.original)!==-1&&now.slice(editing.start,editing.start+editing.original.length)!==editing.original)editing.start=now.indexOf(editing.original);
    held.saved='Saved.';if(!held.stale)sReviewSaid(held,editing,'Saved. Click outside the box to finish.');
    sDeskRefresh(held,before);
  }catch(error){editing.dirty=true;if(/changed since/.test(error.message)){held.stale=true;sDeskStale(held);}else sReviewSaid(held,editing,error.message+' Your words are kept in the box.');}finally{held.saving=null;}})();
  await held.saving;
  if(editing.dirty&&!held.stale&&held.review.editing===editing&&editing.text!==typed)return sReviewSave(held);
}
// How the paragraph being edited is saving, said under it and in the page's save line.
function sReviewSaid(held,editing,words){editing.said=words;if(editing.note)editing.note.textContent=words;if(held.status&&!held.stale)held.status.textContent=words;}
async function sReviewClose(held){const editing=held.review?.editing;if(!editing)return;await sReviewSave(held);if(held.review.editing!==editing||editing.dirty)return;held.review.editing=null;if(held.status&&!held.stale&&editing.said)held.status.textContent=/^Saved/.test(editing.said)?'Saved.':editing.said;if(sDeskCurrent(held)&&held.mode==='review')sDeskReviewRefresh(held,held.view);}
async function sReviewFlush(held){if(held.review?.editing)await sReviewClose(held);}
async function sReviewCheck(held,button){
  await busy(button,'Starting…',async()=>{try{await sReviewFlush(held);await sDeskFlush(held);if(held.stale)return;const before=held.view;held.view=await api('desk-finish',{id:held.id,seen:held.view.revision,tool:'copyedit'});if(held.review)held.review.google=null;sDeskRefresh(held,before);sDeskWatch(held);}catch(error){if(/changed since/.test(error.message)){held.stale=true;sDeskStale(held);}else notice(error.message,true);}});
}
async function sReviewAccept(held,set,ids,button){
  await busy(button,'Accepting…',async()=>{try{
    await sReviewFlush(held);if(held.stale)return;
    const before=held.view;held.view=await api('desk-apply',{id:held.id,seen:held.view.revision,job:set.job,items:ids.map(id=>({id}))});
    const done=held.view.finished||{applied:ids.length,left:[]},left=(done.left||[]).length;
    if(held.review)held.review.google=null;
    sToast((done.applied===1?'Accepted.':'Accepted '+done.applied+'.')+' The earlier text is in History.'+(left?' '+left+(left===1?' no longer fits and is':' no longer fit and are')+' left for you.':''));
    sDeskRefresh(held,before);
  }catch(error){if(/changed since/.test(error.message)){held.stale=true;sDeskStale(held);}else notice(error.message,true);}});
}
async function sReviewReject(held,set,ids,button){
  await busy(button,'Rejecting…',async()=>{try{await sReviewFlush(held);const before=held.view;held.view=await api('desk-skip',{id:held.id,job:set.job,items:ids});sDeskRefresh(held,before);}catch(error){notice(error.message,true);}});
}

// A sheet opened over the desk (Add a source, History…) is always on top: on a screen too
// narrow for the panel to sit beside the draft, the panel steps aside while the sheet is open
// and comes back when it closes. runner.js calls these when any sheet opens or closes.
function sDeskFloating(){return sNarrow()||(typeof window.matchMedia==='function'&&!!window.matchMedia('(max-width: 1099px)').matches);}
function sDeskSheetOpened(){const held=studio.desk;if(studio.screen!=='desk'||!held?.finish||!held.panel||!sDeskFloating())return;held.panelUnder=true;held.panel.hidden=true;}
function sDeskSheetClosed(){const held=studio.desk;if(!held?.panelUnder)return;held.panelUnder=false;if(held.panel)held.panel.hidden=false;}
// Turning a phone or resizing the window across a layout redraws the desk in the new one.
function sDeskLayout(){return sNarrow()?'phone':sDeskFloating()?'drawer':'wide';}
function sDeskResized(){const held=studio.desk;if(!held||!sDeskCurrent(held)||held.layout===sDeskLayout())return;if(held.mode==='review'){if(!held.review?.editing){held.layout=sDeskLayout();sDeskReview(held);}return;}if(!held.cards&&held.tab!=='outline')return;held.layout=sDeskLayout();held.panelUnder=!!studio.sheet&&!!held.finish&&sDeskFloating();sDeskRender(held);}  // A sheet open across the change stays on top.
if(typeof window.addEventListener==='function')window.addEventListener('resize',()=>{if(typeof clearTimeout==='function')clearTimeout(window.deskResize);window.deskResize=setTimeout(sDeskResized,150);});
