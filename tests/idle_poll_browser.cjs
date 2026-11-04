/* Focused change-signal benchmark over the protected native page, no providers. */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
async function fixture(product,count){
 const child=spawn(process.env.PYTHON||'python3',['tests/slide_review_fixture.py',product,'--slides',String(count)],{stdio:['ignore','pipe','pipe']});let diagnostic='';child.stderr.on('data',b=>diagnostic+=b);
 const data=await new Promise((resolve,reject)=>{let raw='';const timer=setTimeout(()=>reject(Error('Fixture timeout '+diagnostic)),30000);child.stdout.on('data',b=>{raw+=b;if(raw.includes('\n')){clearTimeout(timer);resolve(JSON.parse(raw.split('\n')[0]));}});child.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exit '+code+' '+diagnostic));});});
 return {...data,stop:async()=>{child.kill('SIGTERM');await new Promise(resolve=>child.exitCode!==null?resolve():child.once('exit',resolve));assert.equal(child.exitCode,0,diagnostic);}};
}
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});try{
 for(const product of (process.env.POLL_PRODUCTS||'training,presentation').split(','))for(const count of [6,30]){
  const test=await fixture(product,count),page=await browser.newPage({viewport:{width:1280,height:950}});let samples=[];
  page.on('response',async response=>{if(response.url().includes('/api/'))try{samples.push({route:new URL(response.url()).pathname,bytes:(await response.body()).length});}catch{}});
  try{
   await page.goto(test.url+'&resume='+encodeURIComponent(path.basename(test.path)));
   await page.waitForFunction(()=>view.setup&&view.run);await page.evaluate(()=>refresh());await page.waitForTimeout(100);
   const state=await page.evaluate(()=>ask('fixture-review-state'));
   samples=[];const start=Date.now();await page.evaluate(()=>refresh());await page.waitForTimeout(100);
   const baseline={requests:samples.length,bytes:samples.reduce((n,r)=>n+r.bytes,0),ms:Date.now()-start};
   samples=[];const begun=Date.now();for(let i=0;i<5;i++)await page.evaluate(()=>refresh(true));await page.waitForTimeout(100);
   const compact={requests:samples.length,bytes:samples.reduce((n,r)=>n+r.bytes,0),ms:Date.now()-begun};
   assert.equal(samples.filter(r=>['/api/run','/api/drafts','/api/drafts/card','/api/trainings','/api/decks'].includes(r.route)).length,0,'Idle probes must skip content surveys');
   assert(compact.bytes/5<baseline.bytes*.15,'Idle probe stays below 15% of full refresh bytes');
   fs.writeFileSync(path.join(test.path,'polling-fixture.txt'),'Synthetic external edit');
   const changed=Date.now();samples=[];await page.evaluate(()=>refresh(true));await page.waitForTimeout(100);
   assert(samples.some(r=>r.route==='/api/run'),'External file change refreshes owning run');
   const visibleMs=Date.now()-changed;
   await page.evaluate(()=>Object.defineProperty(document,'hidden',{configurable:true,value:true}));assert.equal(await page.evaluate(()=>pace()),20000);
   await page.evaluate(()=>Object.defineProperty(document,'hidden',{configurable:true,value:false}));
   await page.context().setOffline(true);await page.evaluate(()=>refresh(true));assert((await page.evaluate(()=>view.pollFailures))>0);
   await page.context().setOffline(false);samples=[];await page.evaluate(()=>window.dispatchEvent(new Event('online')));await page.waitForFunction(()=>!view.refreshing&&view.pollFailures===0);await page.waitForTimeout(100);
   assert(samples.some(r=>r.route==='/api/run'),'Reconnect forces authoritative catch-up');
   assert.equal((await page.evaluate(()=>ask('fixture-review-state'))).jobs,state.jobs);
   console.log(JSON.stringify({product,count,baseline,compact,visibleMs,scope:'synthetic loopback; five explicit idle probes; no model latency claim'}));
  }finally{await page.close();await test.stop();}
 }
}finally{await browser.close();}})().catch(e=>{console.error(e.message);process.exitCode=1;});
