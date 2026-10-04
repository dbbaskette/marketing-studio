// Exercise the actual desk functions with a disposable DOM and controlled API responses.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
class Element {
  constructor(tag='div'){this.tagName=tag;this.children=[];this.attributes={};this.listeners={};this.hidden=false;this.disabled=false;this.value='';this.textContent='';this.className='';}
  append(...children){this.children.push(...children);for(const child of children)child.parent=this;}
  replaceChildren(...children){this.children=[];this.append(...children);}
  setAttribute(key,value){this.attributes[key]=value;}
  removeAttribute(key){delete this.attributes[key];}
  addEventListener(key,fn){this.listeners[key]=fn;}
  querySelector(selector){return this.querySelectorAll(selector)[0]||null;}
  querySelectorAll(selector){return this.children.flatMap(c=>[...(selector==='.dialog-notice'&&c.className.includes('dialog-notice')?[c]:selector==='[type=submit]'&&c.type==='submit'?[c]:[]),...c.querySelectorAll(selector)]);}
  showModal(){this.open=true;}
  close(){this.open=false;}
}
function fixture(responder=()=>({items:[],total:0})){
  const nodes=new Map();const get=id=>{if(!nodes.has(id))nodes.set(id,new Element());return nodes.get(id);};
  const document={getElementById:get,createElement:t=>new Element(t),querySelector:s=>s==='dialog[open]'?[...nodes.values()].find(n=>n.open):null,querySelectorAll:s=>[...nodes.values()].flatMap(n=>n.querySelectorAll(s))};
  const context=vm.createContext({document,location:{hash:'#fixture',pathname:'/'},sessionStorage:{getItem:()=>'',setItem:()=>{}},history:{replaceState:()=>{}},URLSearchParams,crypto:{randomUUID:()=> 'a'.repeat(32)},fetch:async(url,options)=>({ok:true,json:async()=>responder(url,options)}),console});
  const source=fs.readFileSync('skills/blog-studio/assets/management/app.js','utf8').split("for(const b of document.querySelectorAll('[data-view]'))")[0];
  vm.runInContext(source,context);
  return {get,nodes,run:code=>vm.runInContext(code,context),set:(name,value)=>{context[name]=value;}};
}
async function check(){
  const f=fixture();const dialog=f.get('detail-dialog');dialog.open=true;
  f.run("notice('Reload before saving.',true)");
  assert.equal(dialog.querySelector('.dialog-notice').textContent,'Reload before saving.');
  assert.equal(dialog.querySelector('.dialog-notice').attributes.role,'alert');
  assert.equal(f.get('notice').textContent,'');
  dialog.open=false;
  f.set('result',{receipts:[{label:'Reference',message:'Shared with the Team Hub.'},{label:'Blog',message:'Saved locally; Hub sync needs attention.'}]});
  f.run('savedNotice(result)');assert.match(f.get('notice').textContent,/Blog: Saved locally/);
  const pending=fixture(()=>({items:[{id:'fixture',label:'Blog',sharing:'pending-review',message:'Waiting for contribution review.',retry:true}]}));
  await pending.run('loadReceipts()');assert.equal(pending.get('sync-status').hidden,false);
  assert.equal(pending.get('sync-status').children[0].children[1].textContent,'Retry sync');
  console.log(JSON.stringify({status:'passed',checks:'management feedback'}));
}
check().catch(e=>{console.error(e);process.exitCode=1;});
