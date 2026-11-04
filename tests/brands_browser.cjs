/* Actual protected Brands pages and Git, isolated state and fake assistant only. */
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
(async()=>{
 const child=spawn(process.env.PYTHON||'python3',['tests/brands_fixture.py'],{stdio:['ignore','pipe','pipe']});
 let diagnostics='',browser;child.stderr.on('data',b=>diagnostics+=b);
 try{
  const fixture=await new Promise((resolve,reject)=>{let raw='';const timer=setTimeout(()=>reject(Error('Fixture timeout '+diagnostics)),20000);child.stdout.on('data',b=>{raw+=b;if(raw.includes('\n')){clearTimeout(timer);resolve(JSON.parse(raw.split('\n')[0]));}});child.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exit '+code+' '+diagnostics));});});
  browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});
  const page=await browser.newPage({viewport:{width:390,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  page.on('response',async response=>{if(response.status()>=400&&response.url().includes('/api/brand-'))console.error('Brands refusal:',(await response.json()).error);});
  await page.goto(fixture.url);
  await page.getByRole('button',{name:'Brands',exact:true}).click();
  await page.getByText('No brand packs yet.',{exact:false}).waitFor();
  await page.getByRole('button',{name:'New brand',exact:true}).press('Enter');
  await page.getByLabel('Name',{exact:true}).fill('Example Co');
  await page.getByLabel('Id',{exact:true}).fill('example');
  await page.getByRole('button',{name:'Start',exact:true}).press('Enter');
  await page.getByLabel('Add files',{exact:true}).setInputFiles([fixture.source,fixture.template]);
  await page.getByRole('button',{name:'Add to sources',exact:true}).click();
  await page.locator('.brand-files').getByText('export.zip',{exact:true}).waitFor();
  await page.locator('.brand-files').getByText('example-light.pptx',{exact:true}).waitFor();
  await page.getByRole('button',{name:'Extract',exact:true}).click();
  await page.getByRole('button',{name:'Ask Claude Code for every part',exact:true}).waitFor();
  const guide=page.locator('[data-part="guide"]');
  await guide.getByLabel('guide.md',{exact:true}).fill('## Brand rules\nMy own pending edit.');
  await page.getByRole('button',{name:'Ask Claude Code for every part',exact:true}).click();
  await guide.getByLabel('guide.md',{exact:true}).focus();
  await guide.getByLabel('guide.md',{exact:true}).press('ArrowLeft');
  const caret=await guide.getByLabel('guide.md',{exact:true}).evaluate(n=>{window.editingBrandField=n;return n.selectionStart;});
  await page.waitForTimeout(2200);
  assert.equal(await guide.getByLabel('guide.md',{exact:true}).inputValue(),'## Brand rules\nMy own pending edit.');
  assert(await guide.getByLabel('guide.md',{exact:true}).evaluate((n,at)=>n===window.editingBrandField&&document.activeElement===n&&n.selectionStart===at,caret),'Polling must preserve draft/focus/caret');
  await page.locator('.brand-task').getByText('Finished',{exact:true}).waitFor();
  await guide.getByRole('button',{name:'Save my edit',exact:true}).click();
  await guide.getByText('Accepted',{exact:true}).waitFor();
  assert(await guide.getByRole('button',{name:'Save my edit',exact:true}).evaluate(n=>document.activeElement===n),'Local save returns focus to its action');
  const audit=page.locator('[data-part="audit"]');
  await audit.getByRole('button',{name:'Accept',exact:true}).press('Enter');
  assert(await audit.getByRole('button',{name:'Save my edit',exact:true}).isVisible());
  for(const part of ['roles','layouts','directions'])await page.locator(`[data-part="${part}"]`).getByRole('button',{name:'Accept',exact:true}).click();
  for(const width of [390,1280])for(const colorScheme of ['light','dark']){
   await page.setViewportSize({width,height:950});await page.emulateMedia({colorScheme,reducedMotion:'reduce'});
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Review must fit the viewport');
   assert.deepEqual(await page.locator('#brands button:visible').evaluateAll(nodes=>nodes.filter(n=>n.getBoundingClientRect().height<43.5).map(n=>n.textContent)),[]);
   if(process.env.BRANDS_UI_RESULTS){fs.mkdirSync(process.env.BRANDS_UI_RESULTS,{recursive:true});await page.locator('#brands').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(process.env.BRANDS_UI_RESULTS,`brands-review-${width}-${colorScheme}.png`)});}
  }
  await page.getByRole('button',{name:'Save',exact:true}).click();
  await page.getByRole('button',{name:'Update',exact:true}).waitFor();
  assert.equal(await page.getByRole('button',{name:/^Push /}).count(),0,'Local Save never offers or starts push');
  for(const width of [390,1280])for(const colorScheme of ['light','dark']){
   await page.setViewportSize({width,height:950});await page.emulateMedia({colorScheme,reducedMotion:'reduce'});
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Brand list must fit the viewport');
   if(process.env.BRANDS_UI_RESULTS)await page.screenshot({path:path.join(process.env.BRANDS_UI_RESULTS,`brands-list-${width}-${colorScheme}.png`)});
  }
  await page.getByRole('button',{name:'Update',exact:true}).click();
  await page.getByRole('button',{name:'Back to Brands',exact:true}).click();
  await page.reload();await page.getByRole('button',{name:'Brands',exact:true}).click();
  await page.getByRole('button',{name:'Continue',exact:true}).click();
  await page.getByRole('heading',{name:'Example Co',exact:true}).waitFor();
  assert.deepEqual(errors,[]);
  console.log('PASS Brands: create/upload/extract/review/save/update/resume, pending edits/focus/caret survive polling, keyboard, 390/1280 light/dark and reduced motion; no provider or push');
 }finally{
  if(browser)await browser.close();child.kill('SIGTERM');await new Promise(resolve=>{if(child.exitCode!==null)resolve();else{child.once('exit',resolve);setTimeout(()=>{child.kill('SIGKILL');resolve();},10000).unref();}});assert.equal(child.exitCode,0,diagnostics);
 }
})().catch(e=>{console.error(e);process.exitCode=1;});
