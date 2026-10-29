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
 const editor=new kit.Editor({request});document.body.append(editor.node);await settle();
 assert.equal(requests[0].action,'create');assert.equal(editor.valid(),false);assert.equal(editor.choice().web,false);
 editor.urls='https://example.invalid/a\nhttps://example.invalid/b';await editor.links();assert.equal(editor.value.sources.length,2);assert.equal(editor.urls,'');assert.equal(editor.valid(),true);
 assert.equal(requests.filter(r=>r.action==='capture').length,2);
 editor.urls='http://unsafe.invalid';await editor.links();assert.match(editor.problem,/HTTPS/);assert.equal(requests.filter(r=>r.action==='capture').length,2);
 editor.problem='';editor.urls='draft link stays';editor.pasting=true;editor.text='Unsubmitted source text';editor.render();
 const external=key(editor,'research-external');external.focus();await editor.act('configure',{external:true});
 assert.equal(editor.urls,'draft link stays');assert.equal(editor.text,'Unsubmitted source text');assert.equal(editor.choice().web,true);assert.equal(document.activeElement.dataset.key,'research-external');
 assert.ok(!requests.some(r=>['start','generate','publish','google-write'].includes(r.action)));
 state.sources[0].status='needs-attention';editor.value=state;assert.equal(editor.valid(),false);state.sources[0].status='excluded';assert.equal(editor.valid(),true);
 const progress=kit.progress({phase:'review',streams:[{id:'area1',questions:['Synthetic area'],status:'kept'}]}, {stop:()=>{}});assert.ok(all(progress).some(n=>n.textContent==='Independent check'));assert.ok(all(progress).some(n=>n.dataset.key==='research-stop'));
 console.log('PASS shared source editor: explicit scope, mixed links, validation, draft/focus preservation, progress, no provider actions');
})().catch(error=>{console.error(error);process.exitCode=1;});
