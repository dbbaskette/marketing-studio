/* Four focused native fixtures: six/thirty slides, no live authors or providers. */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
async function fixture(product,count){
 const child=spawn(process.env.PYTHON||'python3',['tests/slide_review_fixture.py',product,'--slides',String(count)],{stdio:['ignore','pipe','pipe']});let diagnostic='';child.stderr.on('data',b=>diagnostic+=b);
 const data=await new Promise((resolve,reject)=>{let raw='';const timer=setTimeout(()=>reject(Error('Fixture timeout '+diagnostic)),30000);child.stdout.on('data',b=>{raw+=b;if(raw.includes('\n')){clearTimeout(timer);resolve(JSON.parse(raw.split('\n')[0]));}});child.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exit '+code+' '+diagnostic));});});
 return {...data,stop:async()=>{child.kill('SIGTERM');await new Promise(resolve=>child.exitCode!==null?resolve():child.once('exit',resolve));assert.equal(child.exitCode,0,diagnostic);}};
}
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});try{
 for(const product of (process.env.SLIDE_REVIEW_PRODUCTS||'training,presentation').split(','))for(const count of (process.env.SLIDE_REVIEW_COUNTS||'6,30').split(',').map(Number)){
  const test=await fixture(product,count);const page=await browser.newPage({viewport:{width:390,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  try{
   await page.goto(test.url+'&resume='+encodeURIComponent(path.basename(test.path)));
   if(product==='training')await page.getByRole('button',{name:'Review slide text',exact:true}).first().click();
   const review=page.locator('#slide-text-review');await review.waitFor();
   await review.getByLabel('Slide to review',{exact:true}).waitFor({state:'visible'});
   const title=review.getByLabel('Title of slide 1',{exact:true});await title.fill('Private corrected heading');
   await review.getByRole('button',{name:'Save corrections',exact:true}).click();
   await review.getByText('Review draft saved privately. No design work started.',{exact:true}).waitFor();
   const jobs=await page.evaluate(()=>ask('fixture-review-state'));
   await review.getByRole('button',{name:'Next slide',exact:true}).press('Enter');
   await review.getByLabel('Title of slide 2',{exact:true}).fill('Second local correction');
   await review.getByText('Speaker notes and delivery',{exact:true}).click();
   await review.getByLabel('Speaker notes of slide 2',{exact:true}).fill('Retained speaker notes');
   await review.getByRole('button',{name:'Save corrections',exact:true}).click();
   await review.getByText('Review draft saved privately. No design work started.',{exact:true}).waitFor();
   await page.reload();
   if(product==='training'&&await page.getByRole('button',{name:'Review slide text',exact:true}).count())await page.getByRole('button',{name:'Review slide text',exact:true}).first().click();
   await review.getByLabel('Title of slide 2',{exact:true}).waitFor();
   assert.equal(await review.getByLabel('Title of slide 2',{exact:true}).inputValue(),'Second local correction');
   assert.equal(await review.getByLabel('Speaker notes of slide 2',{exact:true}).inputValue(),'Retained speaker notes');
   const after=await page.evaluate(()=>ask('fixture-review-state'));assert.equal(after.jobs,jobs.jobs,'Private saves/reload must not schedule pipeline work');
   await review.getByLabel('Title of slide 2',{exact:true}).focus();await review.getByLabel('Title of slide 2',{exact:true}).press('ArrowLeft');
   const caret=await review.getByLabel('Title of slide 2',{exact:true}).evaluate(n=>n.selectionStart);
   await page.waitForTimeout(5200);
   assert(await review.getByLabel('Title of slide 2',{exact:true}).evaluate((n,at)=>document.activeElement===n&&n.selectionStart===at,caret),'Polling retains focus/caret');
   for(const width of [390,1280])for(const colorScheme of ['light','dark']){
    await page.setViewportSize({width,height:950});await page.emulateMedia({colorScheme,reducedMotion:'reduce'});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    assert.equal(await review.locator('.slide-text-item').count(),1,'Only selected slide gets an editor');
    assert.equal(await review.getByLabel('Slide to review',{exact:true}).locator('option').count(),count);
    assert((await review.locator('input,textarea').count())<12,'Controls remain bounded for a long deck');
    if(process.env.SLIDE_REVIEW_RESULTS){fs.mkdirSync(process.env.SLIDE_REVIEW_RESULTS,{recursive:true});await review.scrollIntoViewIfNeeded();await page.screenshot({path:path.join(process.env.SLIDE_REVIEW_RESULTS,`${product}-${count}-${width}-${colorScheme}.png`)});}
   }
   if(count===6){
    await page.locator('body').click({position:{x:2,y:2}});await page.waitForTimeout(650);
    await page.evaluate(async path=>{const held=await ask('slide-text-draft',{path,level:''});await send('slide-text-draft',{path,level:null,action:'save',expected:held.revision,patch:{...held.draft,basis:'earlier-outline-fixture'}});},test.path);
    await page.reload();if(product==='training')await page.getByRole('button',{name:'Review slide text',exact:true}).first().click();
    await review.getByLabel('Earlier saved corrections',{exact:true}).waitFor();
    assert((await review.getByLabel('Earlier saved corrections',{exact:true}).inputValue()).includes('Private corrected heading'));
    assert(await review.getByRole('button',{name:'Save corrections',exact:true}).isDisabled());
    page.once('dialog',dialog=>dialog.accept());await review.getByRole('button',{name:'Discard corrections',exact:true}).click();
    await review.getByText('No local corrections yet. Design waits for approval.',{exact:true}).waitFor();
    assert.equal((await page.evaluate(()=>ask('fixture-review-state'))).jobs,jobs.jobs);
   }
   assert.deepEqual(errors,[]);console.log(`PASS ${product} ${count} slides: local edits/notes, saved reload/selection, no pipeline work, stable polling focus, bounded controls, 390/1280 light/dark`);
  }finally{await page.close();await test.stop();}
 }
}finally{await browser.close();}})().catch(e=>{console.error(e.message);process.exitCode=1;});
