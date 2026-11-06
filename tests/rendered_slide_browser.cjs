/* Rendered Training Studio deck; disposable workspace, scripted authors only. */
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
(async()=>{
 const child=spawn(process.env.PYTHON||'python3',['tests/slide_review_fixture.py','training','--rendered'],{stdio:['ignore','pipe','pipe']});
 let diagnostic='',browser;child.stderr.on('data',b=>diagnostic+=b);
 try{
  const fixture=await new Promise((resolve,reject)=>{let raw='';const timer=setTimeout(()=>reject(Error('Fixture timeout '+diagnostic)),40000);child.stdout.on('data',b=>{raw+=b;if(raw.includes('\n')){clearTimeout(timer);resolve(JSON.parse(raw.split('\n')[0]));}});child.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exit '+code+' '+diagnostic));});});
  browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(fixture.url+'&resume='+encodeURIComponent(path.basename(fixture.path)));
  await page.getByRole('tab',{name:/^Deck ·/}).click();
  const select=page.getByLabel('Slide to review',{exact:true});await select.waitFor();
  const options=await select.locator('option').evaluateAll(ns=>ns.map(n=>n.value));
  const jobs=(await page.evaluate(()=>ask('fixture-review-state'))).jobs;
  for(const width of [390,1280])for(const colorScheme of ['light','dark']){
   await page.setViewportSize({width,height:844});await page.emulateMedia({colorScheme,reducedMotion:'reduce'});
   await select.selectOption(options[1]);
   await page.getByText('Edit slide text and speaker notes',{exact:true}).click();
   const title=page.getByLabel('Slide 2 title',{exact:true});await title.fill('Local unsaved slide title');
   await select.evaluate(n=>{n.scrollIntoView({block:'center'});n.focus({preventScroll:true});});
   const before=await select.evaluate(n=>({y:n.getBoundingClientRect().y,scroll:scrollY}));
   assert(before.scroll>100,'Exercise a scrolled page');
   // Keep a node identity witness: an in-place selection must not redraw the page.
   await select.evaluate(n=>n.dataset.witness='same-selector');
   await select.selectOption(options[2]);
   assert.equal(await select.getAttribute('data-witness'),'same-selector');
   assert(await select.evaluate(n=>document.activeElement===n),'Selector retains keyboard focus');
   assert(Math.abs((await select.boundingBox()).y-before.y)<2,'Selector retains viewport position');
   await select.selectOption(options[1]);
   await page.getByText('Edit slide text and speaker notes',{exact:true}).click();
   assert.equal(await title.inputValue(),'Local unsaved slide title');
   await title.focus();await title.press('ArrowLeft');const caret=await title.evaluate(n=>n.selectionStart);
   await page.evaluate(()=>refresh());
   assert(await title.evaluate((n,at)=>document.activeElement===n&&n.selectionStart===at,caret),'Polling keeps editing focus/caret');
   assert.equal(await select.inputValue(),options[1]);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   if(process.env.VISIBILITY_RESULTS){fs.mkdirSync(process.env.VISIBILITY_RESULTS,{recursive:true});await select.evaluate(n=>n.scrollIntoView({block:'center'}));await page.screenshot({path:path.join(process.env.VISIBILITY_RESULTS,`rendered-${width}-${colorScheme}.png`)});}
  }
  assert.equal((await page.evaluate(()=>ask('fixture-review-state'))).jobs,jobs,'Selection/editing/polling schedules no workers');
  assert.deepEqual(errors,[]);
  console.log('PASS rendered slide review: stable scrolled selector/focus, retained unsaved edits/caret/selection, no jobs, 390/1280 light/dark');
 }finally{if(browser)await browser.close();child.kill('SIGTERM');await new Promise(resolve=>child.exitCode!==null?resolve():child.once('exit',resolve));assert.equal(child.exitCode,0,diagnostic);}
})().catch(e=>{console.error(e);process.exitCode=1;});
