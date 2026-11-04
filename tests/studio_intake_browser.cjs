/* Real authenticated intake pages and private drafts; all studio dependencies are fixtures. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const root=path.join(__dirname,'..');
async function fixture(product,args=[]){
 const script=product==='training'?'studios/training/tests/ui/training_plan_fixture.py':'studios/presentation/tests/ui/intake_fixture.py';
 const child=spawn(process.env.PYTHON||'python3',[path.join(root,script),...args],{stdio:['ignore','pipe','pipe']});
 let diagnostic='';child.stderr.on('data',b=>diagnostic+=b);
 const found=await new Promise((resolve,reject)=>{let out='';const timer=setTimeout(()=>reject(Error(diagnostic||'Fixture timeout')),30000);child.stdout.on('data',b=>{out+=b;if(out.includes('\n')){clearTimeout(timer);try{resolve(JSON.parse(out.split('\n')[0]));}catch(e){reject(e);}}});child.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code+': '+diagnostic));});});
 return {...found,stop:async()=>{child.kill('SIGTERM');await new Promise(resolve=>{if(child.exitCode!==null)resolve();else child.once('exit',resolve);});}};
}
(async()=>{
 let browser;
 try{
  browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});
  if(process.env.STUDIO_AUDIT_BROWSER_MODE!=='desks')for(const product of ['training','presentation'])for(const width of [390,1280]){
   const test=await fixture(product,product==='training'?['--new','--library','--desk']:[]);
   try{
    const page=await browser.newPage({viewport:{width,height:844},colorScheme:'light'}),errors=[],jobs=[];
    page.on('pageerror',e=>errors.push(e.stack||e.message));
    page.on('requestfailed',r=>console.error('Failed resource '+r.url()+': '+JSON.stringify(r.failure())));
    page.on('response',r=>{if(r.status()>=400)console.error('Resource '+r.status()+' '+r.url());});
    page.on('request',r=>{if(r.method()==='POST'&&['/api/trainings','/api/decks'].includes(new URL(r.url()).pathname))jobs.push(r);});
    await page.goto(test.url);
    await page.waitForFunction(()=>!view.refreshing && view.setup);
    const title=product==='training'?'New training':'New deck';
    await page.getByRole('button',{name:title,exact:true}).first().click();
    const dialog=page.getByRole('dialog',{name:title,exact:true});
    try{await dialog.waitFor();}catch(error){console.error(product+' '+width+' initial UI: '+await page.locator('body').innerText());console.error(errors);console.error(await page.evaluate(()=>({lists:typeof window.StudioLists,scripts:[...document.scripts].map(n=>n.src)})));throw error;}
    if(product==='presentation'){await dialog.getByRole('button',{name:'An idea',exact:false}).click();await dialog.getByRole('button',{name:'Next',exact:true}).click();}
    await dialog.getByLabel('A short title',{exact:true}).fill('Synthetic resumable intake');
    await dialog.getByLabel(product==='training'?'What should it teach?':'What should they take away?',{exact:true}).fill('Explain safe rolling restarts.');
    await dialog.getByLabel('Who is it for?',{exact:true}).fill('New platform engineers');
    await dialog.getByRole('button',{name:'Next',exact:true}).click();
    if(product==='presentation')await dialog.getByLabel('Research the approved story',{exact:true}).check();
    await dialog.getByRole('button',{name:'Paste text',exact:true}).click();
    await dialog.getByLabel('Source name',{exact:true}).fill('Synthetic restart notes');
    await dialog.getByLabel('Source text',{exact:true}).fill('A rolling restart replaces instances in batches. Keep capacity for the remaining workload.');
    await dialog.getByRole('button',{name:'Add text',exact:true}).click();
    await dialog.getByText('Synthetic restart notes',{exact:true}).first().waitFor();
    await dialog.getByRole('button',{name:'Add from library',exact:true}).click();
    const picker=page.getByRole('dialog',{name:'Add from library',exact:true});
    await picker.locator('input[data-key^="library-tick-"]').first().check();
    await picker.getByRole('button',{name:'Use selected',exact:true}).click();
    await picker.waitFor({state:'detached'});
    assert.equal(await page.evaluate(()=>document.activeElement?.dataset.key),'research-library');
    if(product==='training')await dialog.getByRole('button',{name:'Next',exact:true}).click();
    await dialog.getByRole('status').filter({hasText:'Intake saved on this computer.'}).waitFor();
    const saved=await page.evaluate(()=>ask('intake-draft'));
    assert.equal(saved.draft.step,2);assert.equal(saved.draft.library.length,1);assert.ok(saved.draft.sourceDraft.id);
    assert.equal(jobs.length,0,'all intake actions start zero projects/jobs');
    await page.reload();await dialog.waitFor();await dialog.getByRole('button',{name:'Start',exact:true}).waitFor();
    const resumed=await page.evaluate(()=>ask('intake-draft'));
    assert.equal(resumed.draft.title,saved.draft.title);assert.deepEqual(resumed.draft.library,saved.draft.library);
    assert.equal(resumed.draft.sourceDraft.id,saved.draft.sourceDraft.id);
    await dialog.getByRole('button',{name:'Back',exact:true}).click();
    if(product==='training')await dialog.getByRole('button',{name:'Back',exact:true}).click();
    assert.equal(await dialog.getByLabel('A short title',{exact:true}).inputValue(),'Synthetic resumable intake');
    await dialog.getByRole('button',{name:'Next',exact:true}).click();
    if(product==='training')await dialog.getByRole('button',{name:'Next',exact:true}).click();
    for(const scheme of ['light','dark']){
     await page.emulateMedia({colorScheme:scheme,reducedMotion:'reduce'});
     assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
     const geometry=await dialog.evaluate(n=>{const r=n.getBoundingClientRect(),s=getComputedStyle(n),b=n.querySelector('[data-key="continue"]').getBoundingClientRect();return {left:r.left,right:r.right,center:(r.left+r.right)/2,background:s.backgroundColor,blur:s.backdropFilter,buttonBottom:b.bottom};});
     assert(Math.abs(geometry.center-width/2)<2,'creation sheet is centered');
     assert(geometry.left>=0&&geometry.right<=width,'sheet fits');
     assert(geometry.buttonBottom<=844-(width<600?64:0),'primary action clears bottom navigation');
     assert.equal(geometry.blur,'none');
     assert(!geometry.background.endsWith(', 0)'),'form is opaque');
     if(process.env.STUDIO_INTAKE_RESULTS){fs.mkdirSync(process.env.STUDIO_INTAKE_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.STUDIO_INTAKE_RESULTS,`${product}-intake-${width}-${scheme}.png`)});}
    }
    await dialog.getByRole('button',{name:'Discard draft',exact:true}).focus();await page.keyboard.press('Tab');
    assert(await page.evaluate(()=>!!document.activeElement?.closest('#sheet')),'Tab stays in the sheet');
    await dialog.getByRole('button',{name:'Save and close',exact:true}).click();await dialog.waitFor({state:'hidden'});
    await page.reload();await page.getByRole('heading',{name:'Home',exact:true}).waitFor();assert.equal(await dialog.isVisible(),false);
    await page.getByRole('button',{name:title,exact:true}).first().click();await dialog.waitFor();
    await dialog.getByRole('button',{name:'Discard draft',exact:true}).click();await dialog.getByRole('button',{name:'Discard this draft',exact:true}).click();await dialog.waitFor({state:'hidden'});
    assert.equal((await page.evaluate(()=>ask('intake-draft'))).draft,null);
    const sources=await page.evaluate(id=>send('research-sources',{action:'read',id}),saved.draft.sourceDraft.id);
    assert.equal(sources.sources.length,1,'discard keeps captured sources');
    assert.equal(jobs.length,0);assert.deepEqual(errors,[]);console.log('PASS '+product+' '+width);await page.close();
   }finally{await test.stop();}
  }
  for(const product of ['training','presentation'])for(const width of [390,1280]){
   const test=await fixture(product,['--desk']);
   try{
    const page=await browser.newPage({viewport:{width,height:844}}),errors=[];
    page.on('pageerror',e=>errors.push(e.stack||e.message));
    page.on('requestfailed',r=>console.error('Failed resource '+r.url()+': '+JSON.stringify(r.failure())));
    page.on('response',r=>{if(r.status()>=400)console.error('Resource '+r.status()+' '+r.url());});
    await page.addInitScript(({root,screen})=>history.replaceState({screen,path:root},''),{root:test.path,screen:product==='training'?'run':'deck'});
    await page.goto(test.url);
    if(product==='training')await page.getByRole('tab',{name:/^Guide ·/}).first().click();
    const content=product==='training'?page.locator('article.desk-reading'):page.getByRole('region',{name:/^Slide 1 ·/});
    await content.waitFor();
    for(const colorScheme of ['light','dark']){
     await page.emulateMedia({colorScheme,reducedMotion:'reduce'});
     const box=await content.boundingBox();assert(box.y<780,'selected content starts within the first phone screen');
     assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
     if(product==='presentation')assert.equal(await page.locator('details.desk-summary').evaluate(n=>n.open),false);
     if(process.env.STUDIO_INTAKE_RESULTS)await page.screenshot({path:path.join(process.env.STUDIO_INTAKE_RESULTS,`${product}-desk-${width}-${colorScheme}.png`)});
    }
    if(width<600){await page.locator('#actions summary[aria-label="More"]').click();await page.locator('.menu-item').filter({hasText:'Finishing'}).click();}
    else await page.getByRole('button',{name:'Finishing',exact:true}).click();
    await page.getByRole('heading',{name:'Finishing',exact:true}).waitFor();
    await page.getByRole('button',{name:'Close',exact:true}).click();
    if(width<600)assert.equal(await page.evaluate(()=>document.activeElement?.dataset.key),product==='training'?'more':'desk-more');
    assert.deepEqual(errors,[]);console.log('PASS '+product+' '+width);await page.close();
   }finally{await test.stop();}
  }
  console.log('PASS native Training Studio and Presentation Studio intake: real steps, source pins, reload/reopen/discard, zero jobs, centered opaque sheets, keyboard and visible footer, 390/1280 light/dark');
 }finally{if(browser)await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
