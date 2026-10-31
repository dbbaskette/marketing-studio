/* Shared source editor behavior with synthetic authenticated adapter calls only. */
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
let document;
class Node{
 constructor(tag){this.tagName=tag;this.children=[];this.parent=null;this.dataset={};this.listeners={};this.value='';this.className='';this.scrollTop=0;this.disabled=false;this.textContent='';}
 append(...nodes){for(let n of nodes){if(typeof n==='string')n=Object.assign(new Node('#text'),{textContent:n});if(n.parent)n.parent.children=n.parent.children.filter(c=>c!==n);n.parent=this;this.children.push(n);}}
 setAttribute(k,v){this[k]=v;}
 addEventListener(k,fn){this.listeners[k]=fn;}
 replaceChildren(...nodes){this.children=[];this.append(...nodes);}
 replaceWith(n){const i=this.parent.children.indexOf(this);this.parent.children[i]=n;n.parent=this.parent;}
 contains(n){return this===n||this.children.some(c=>c.contains(n));}
 get childNodes(){return this.children;}
 querySelectorAll(selector){return all(this).filter(n=>selector.split(',').some(s=>s.trim()==='[data-key]'?!!n.dataset.key:s.trim()==='details[open][data-key]'?n.tagName==='details'&&n.open&&n.dataset.key:s.trim()==='details[data-key]'?n.tagName==='details'&&n.dataset.key:n.tagName===s.trim()));}
 focus(){document.activeElement=this;}
}
function all(n){return n.children.flatMap(c=>[c,...all(c)]);}
document={createElement:t=>new Node(t),createTextNode:t=>Object.assign(new Node('#text'),{textContent:t}),body:new Node('body'),activeElement:null};document.activeElement=document.body;
const context=vm.createContext({document,URL,URLSearchParams,JSON,Object,Array,String,Number,Math,Set,Promise,Error,module:{exports:{}},btoa:t=>Buffer.from(t,'binary').toString('base64')});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../ui-kit/research.js'),'utf8'),context);
const kit=context.module.exports;
const settle=async()=>{for(let n=0;n<30;n++)await Promise.resolve();};
const key=(editor,k)=>all(editor.node).find(n=>n.dataset.key===k);
(async()=>{
 let revision=0,state={id:'synthetic',revision:'0',external:false,restricted:false,workers:3,focus:'',sites:['https://example.invalid/docs'],sources:[]},requests=[];
 const request=async sent=>{requests.push(sent);if(sent.action==='capture'){state.sources.push({id:String(state.sources.length+1),name:sent.name||sent.url,kind:sent.kind,origin:sent.url,status:'ready'});}if(sent.action==='configure')Object.assign(state,Object.fromEntries(Object.entries(sent).filter(([k])=>['external','restricted','workers','focus'].includes(k))));state.revision=String(++revision);return JSON.parse(JSON.stringify(state));};
 const ready=[]; const editor=new kit.Editor({request,onChange:()=>ready.push(editor.valid())});document.body.append(editor.node);await settle();
 assert.equal(requests[0].action,'create');assert.equal(editor.valid(),false);assert.equal(editor.choice().web,false);
 const filePicker=all(editor.node).find(n=>n.type==='file');
 assert.ok(filePicker.accept.split(',').includes('.pdf'));assert.ok(filePicker.accept.split(',').includes('application/pdf'));
 await editor.files([{name:'synthetic.pdf',size:5,arrayBuffer:async()=>Buffer.from('%PDF-')}]);
 const pdf=requests.find(r=>r.action==='capture'&&r.name==='synthetic.pdf');
 assert.equal(pdf.kind,'file');assert.equal(Buffer.from(pdf.content,'base64').toString(),'%PDF-');
 assert.equal('keep' in pdf,false,'Keep in library is off unless the studio turns it on');assert.equal(key(editor,'research-keep-0'),undefined);
 state.sources=[];requests.length=0;
 editor.urls='https://example.invalid/a\nhttps://example.invalid/b';await editor.links();assert.equal(editor.value.sources.length,2);assert.equal(editor.urls,'');assert.equal(editor.valid(),true);assert.equal(ready.at(-1),true,'Parent form is notified only after capture unlocks');
 assert.equal(requests.filter(r=>r.action==='capture').length,2);
 editor.urls='http://unsafe.invalid';await editor.links();assert.match(editor.problem,/HTTPS/);assert.equal(requests.filter(r=>r.action==='capture').length,2);
 editor.problem='';editor.urls='draft link stays';editor.pasting=true;editor.text='Unsubmitted source text';editor.render();
 const external=key(editor,'research-external');external.focus();await editor.act('configure',{external:true});
 assert.equal(editor.urls,'draft link stays');assert.equal(editor.text,'Unsubmitted source text');assert.equal(editor.choice().web,true);assert.equal(document.activeElement.dataset.key,'research-external');
 assert.ok(!requests.some(r=>['start','generate','publish','google-write'].includes(r.action)));
 state.sources[0].status='needs-attention';editor.value=state;assert.equal(editor.valid(),false);state.sources[0].status='excluded';assert.equal(editor.valid(),true);
 // A native inventory can own intake while this adapter retains shared policy.
 const policy=new kit.Editor({request,value:{...state,sources:[],external:false},policyOnly:true});
 assert.equal(all(policy.node).some(n=>n.type==='file'),false,'policy-only adapters have no duplicate upload picker');
 assert.equal(key(policy,'research-urls'),undefined);assert.equal(key(policy,'research-paste'),undefined);
 assert.ok(key(policy,'research-external'));assert.ok(key(policy,'research-workers'));
 assert.equal(policy.valid(true),true);assert.equal(policy.choice(true).documents,true);
 assert.equal(policy.valid(false),false,'external-only policy cannot invent a primary source');
 // Add from library, for a studio whose adapter turns it on: its button beside the others, and what it chose under the list in place of the empty line.
 assert.equal(key(editor,'research-library'),undefined,'Add from library is off unless the studio turns it on');
 let opened=0,chosen=null;
 const library=new kit.Editor({request,value:{...state,sources:[]},library:()=>{opened+=1;},extra:()=>chosen});
 key(library,'research-library').listeners.click();assert.equal(opened,1);
 assert.ok(all(library.node).some(n=>n.textContent==='Add material here, or allow external search below.'));
 chosen=Object.assign(new Node('ul'),{className:'research-source-list'});chosen.append('Synthetic library brief');library.render();
 assert.ok(all(library.node).some(n=>n.textContent==='Synthetic library brief'));
 assert.equal(all(library.node).some(n=>n.textContent==='Add material here, or allow external search below.'),false);
 let full=false;const capped=new kit.Editor({request,value:{...state,sources:[]},library:()=>{},libraryFull:()=>full});
 assert.equal(key(capped,'research-library').disabled,false);full=true;capped.render();assert.equal(key(capped,'research-library').disabled,true,'Add from library waits once the studio says its choices are full');
 // A studio may say the search choice in its own words; without them the shared summary stands.
 assert.ok(all(editor.node).some(n=>n.textContent===kit.summary(editor.value)));
 const worded=new kit.Editor({request,value:{...state,sources:[],external:false},policyHint:value=>value.external?'Searching too.':'Yours only.'});
 assert.ok(all(worded.node).some(n=>n.textContent==='Yours only.'));
 assert.equal(all(worded.node).some(n=>n.textContent===kit.summary(worded.value)),false);
 // Keep in library, for a studio whose adapter turns it on: Keep in library first, Only this project on request, a retry when the library refused.
 const kept=[];let keepState={id:'keeping',revision:'0',external:false,restricted:false,workers:3,focus:'',sites:[],sources:[]};
 const keeping=new kit.Editor({keepChoice:true,request:async sent=>{kept.push(sent);if(sent.action==='capture')keepState.sources.push({id:'k'+keepState.sources.length,name:sent.name,kind:'file',status:'ready'});
  const answer=JSON.parse(JSON.stringify(keepState));if(sent.action==='capture'&&sent.keep)answer.library_kept={state:'failed',problem:'The library is busy.',source:'k'+(keepState.sources.length-1)};
  if(sent.action==='library-keep')answer.library_kept={state:'kept',source:sent.source};return answer;}});
 await settle();
 assert.equal(key(keeping,'research-keep-0')['aria-pressed'],'true');
 await keeping.files([{name:'kept.md',size:3,arrayBuffer:async()=>Buffer.from('# K')}]);
 assert.equal(kept.find(r=>r.action==='capture').keep,true);assert.equal('library_kept' in keeping.value,false,'the library answer is not part of the draft');
 assert.ok(all(keeping.node).some(n=>n.textContent==='Not kept in the Document Library: The library is busy.'));
 key(keeping,'library-keep-k0').listeners.click();await settle();
 assert.deepEqual(JSON.parse(JSON.stringify(kept.at(-1))),{action:'library-keep',id:'keeping',expected:'0',source:'k0'});
 assert.ok(all(keeping.node).some(n=>n.textContent==='Kept in the Document Library too.'));
 key(keeping,'research-keep-1').listeners.click();await settle();assert.equal(key(keeping,'research-keep-1')['aria-pressed'],'true');
 await keeping.files([{name:'only.md',size:3,arrayBuffer:async()=>Buffer.from('# O')}]);
 assert.equal(kept.filter(r=>r.action==='capture').at(-1).keep,false);
 const progress=kit.progress({phase:'review',streams:[{id:'area1',questions:['Synthetic area'],status:'kept'}]}, {stop:()=>{}});assert.ok(all(progress).some(n=>n.textContent==='Independent check'));assert.ok(all(progress).some(n=>n.dataset.key==='research-stop'));
 for(const [phase,current] of [['investigate',0],['synthesize',1],['review',2],['complete',-1],['paused',-1],['stopped',-1],['needs-attention',-1]]){
  const controls=new Node('div');controls.append(new Node('button'));
  const box=kit.progress({phase,streams:[{id:'kept',questions:['First question','Second question'],status:'kept'},{id:'busy',questions:['Another question'],status:'working'},{id:'failed',questions:['Retry question'],status:'failed'}]}, {controls,timing:{elapsed_seconds:60,active_seconds:1,assistant_seconds:null}});
  const nodes=all(box),stages=nodes.find(n=>n.className==='research-stages');
  assert.equal(stages.children.findIndex(n=>n['aria-current']==='step'),current);
  if(current>=0)assert.ok(nodes.some(n=>n.textContent==='Research · Stage '+(current+1)+' of 3'));
  assert.equal(nodes.filter(n=>n.className==='research-stage-state'&&n.textContent==='Working now').length,current>=0?1:0);
  assert.ok(nodes.some(n=>n.className.split(' ').includes('research-next')),'Every phase explains what remains');
  assert.ok(nodes.some(n=>n.textContent==='1 minute elapsed · 1 second actively working'));
  assert.ok(nodes.some(n=>n.textContent==='Evidence kept'));assert.ok(nodes.some(n=>n.textContent==='Needs retry'));
  assert.ok(nodes.some(n=>n.dataset.key==='research-area-kept-toggle'));
  assert.ok(nodes.some(n=>n.textContent==='Second question'),'Full questions remain available');
  assert.ok(nodes.includes(controls),'Native controls belong to the same progress surface');
  assert.equal(nodes.some(n=>n.className==='research-collected'),['synthesize','review'].includes(phase),'Keep completed evidence subordinate while report/check work continues');
  const meter=nodes.find(n=>n.tagName==='progress');
  assert.equal(Boolean(meter),phase==='investigate');if(meter){assert.equal(meter.value,1);assert.equal(meter.max,3);}
 }
 for(const [count,phase] of [[3,'investigate'],[1,'synthesize'],[1,'review'],[0,'complete']]){
  const nodes=all(kit.progress({phase,agents:{count,active:count?[{phase,id:'synthetic',stream:phase==='investigate'?'area1':null}]:[]}}));
  assert.equal(nodes.find(n=>n.className==='research-agent-count').textContent,String(count));
  assert.equal(nodes.filter(n=>n.className==='research-agent-robot').length,Math.max(1,count));
  assert.ok(nodes.some(n=>n.dataset.key==='research-agents-toggle'));
 }
 for(const agents of [undefined,{count:null,unconfirmed:1,active:[{phase:'investigate',status:'termination-unconfirmed'}]}]){
  const nodes=all(kit.progress({phase:'needs-attention',agents}));
  assert.equal(nodes.find(n=>n.className==='research-agent-count').textContent,'—','Unknown activity must not be displayed as zero');
 }
 const corrected=all(kit.progress({phase:'synthesize',round:2,round_limit:3,agents:{count:1},correction:{areas:[],notes:['Synthetic prose correction']}}));
 assert.ok(corrected.some(n=>n.textContent==='Correction round 2 of 3'));
 assert.ok(corrected.some(n=>n.textContent.includes('sources are not being researched again')));
 assert.ok(corrected.some(n=>n.textContent==='Synthetic prose correction'));
 console.log('PASS shared source editor: explicit scope, mixed links, validation, draft/focus preservation, progress, no provider actions');
})().catch(error=>{console.error(error);process.exitCode=1;});
