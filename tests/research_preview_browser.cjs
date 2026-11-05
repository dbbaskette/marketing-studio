/* Saved draft UI and private concerns, scripted native state, no live research. */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
async function fixture(product){
 const child=spawn(process.env.PYTHON||'python3',['tests/slide_review_fixture.py',product,'--research-preview'],{stdio:['ignore','pipe','pipe']});let diagnostic='';child.stderr.on('data',b=>diagnostic+=b);
 const data=await new Promise((resolve,reject)=>{let raw='';const timer=setTimeout(()=>reject(Error('Fixture timeout '+diagnostic)),30000);child.stdout.on('data',b=>{raw+=b;if(raw.includes('\n')){clearTimeout(timer);resolve(JSON.parse(raw.split('\n')[0]));}});child.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exit '+code+' '+diagnostic));});});
 return {...data,stop:async()=>{child.kill('SIGTERM');await new Promise(resolve=>child.exitCode!==null?resolve():child.once('exit',resolve));assert.equal(child.exitCode,0,diagnostic);}};
}
async function openPreview(page){const panel=page.getByRole('region',{name:'Research progress',exact:true});await panel.waitFor();await panel.locator('summary').filter({hasText:'1 of 2 section drafts kept'}).click();await panel.getByText('Read saved section draft',{exact:true}).click();return panel;}
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});try{
 for(const product of (process.env.RESEARCH_PREVIEW_PRODUCTS||'training,presentation').split(',')){
  const test=await fixture(product),page=await browser.newPage({viewport:{width:390,height:950}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  try{
   await page.goto(test.url+'&resume='+encodeURIComponent(path.basename(test.path)));
   await page.getByText('Read working draft · 1 section available',{exact:true}).click();
   if(process.env.RESEARCH_PREVIEW_RESULTS){fs.mkdirSync(process.env.RESEARCH_PREVIEW_RESULTS,{recursive:true});for(const width of [390,1280]){await page.setViewportSize({width,height:950});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.screenshot({path:path.join(process.env.RESEARCH_PREVIEW_RESULTS,`${product}-working-draft-${width}.png`)});}}
   const downloaded=page.waitForEvent('download');await page.getByRole('button',{name:'Download working draft (.md)',exact:true}).click();
   const download=await downloaded;const text=fs.readFileSync(await download.path(),'utf8');assert.match(text,/independent check pending/);assert.match(text,/Synthetic section prose/);assert.match(text,/Section pending/);
   await page.getByText('Read working draft · 1 section available',{exact:true}).click();let panel=await openPreview(page);
   await panel.getByText('Draft—independent check pending',{exact:true}).waitFor();await panel.getByText('Synthetic section prose is available before final checking.',{exact:true}).last().waitFor();
   const before=await page.evaluate(()=>ask('fixture-review-state'));
   await panel.getByLabel('Note for the next research change',{exact:true}).fill('Retain this concern for the next explicit change.');await panel.getByRole('button',{name:'Save queued note',exact:true}).click();await panel.getByText('Queued privately. Evidence and scope are unchanged.',{exact:true}).waitFor();
   await page.reload();panel=await openPreview(page);await panel.getByLabel('Note for the next research change',{exact:true}).waitFor();await page.waitForFunction(()=>document.querySelector('[data-key="research-queued-note-area1"]')?.value==='Retain this concern for the next explicit change.');
   await page.evaluate(()=>ask('fixture-research-stage',{phase:'changed'}));await page.evaluate(()=>refresh());
   await panel.getByText(/This note belongs to an earlier section revision/).waitFor();
   await page.evaluate(()=>ask('fixture-research-stage',{phase:'complete'}));await page.evaluate(()=>refresh());
   await panel.getByText('Superseded by the checked research report.',{exact:true}).waitFor();
   for(const width of [390,1280])for(const colorScheme of ['light','dark']){await page.setViewportSize({width,height:950});await page.emulateMedia({colorScheme,reducedMotion:'reduce'});assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));if(process.env.RESEARCH_PREVIEW_RESULTS){fs.mkdirSync(process.env.RESEARCH_PREVIEW_RESULTS,{recursive:true});await panel.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(process.env.RESEARCH_PREVIEW_RESULTS,`${product}-${width}-${colorScheme}.png`)});}}
   assert.equal((await page.evaluate(()=>ask('fixture-review-state'))).jobs,before.jobs);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);
   console.log(`PASS ${product}: saved read-only section, failed sibling, private queued note/reload, earlier revision warning, checked-result replacement, zero jobs`);
  }finally{await page.close();await test.stop();}
 }
}finally{await browser.close();}})().catch(e=>{console.error(e.message);process.exitCode=1;});
