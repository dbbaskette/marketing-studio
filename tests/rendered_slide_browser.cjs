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
  await page.route('**/api/drafts?*',async route=>{
   const response=await route.fetch(),data=await response.json();
   const original=data.cards.find(c=>c.kind==='scenario');
   data.cards=data.cards.filter(c=>!['scenario','yoodli'].includes(c.kind));
   for(const kind of ['scenario','yoodli'])for(let i=1;i<=5;i++)data.cards.push({...original,kind,name:kind+':scenario-'+i,seen:null,state:'queued',actions:[],says:'Synthetic queued material '+i});
   await route.fulfill({response,json:data});
  });
  await page.goto(fixture.url+'&resume='+encodeURIComponent(path.basename(fixture.path)));
  const materialTabs=page.getByRole('tablist',{name:'Training material',exact:true});
  await materialTabs.getByRole('tab',{name:'Practice · 5',exact:true}).click();
  assert.equal(await materialTabs.getByRole('tab').count(),7,'Repeated scenarios do not multiply top-level tabs');
  const practice=page.getByLabel('Practice to review',{exact:true});assert.equal(await practice.locator('option').count(),5);
  await practice.focus();await practice.selectOption('scenario:scenario-4');
  assert(await practice.evaluate(n=>n===document.activeElement));
  assert.match(await page.locator('#desk-material-panel').innerText(),/Synthetic queued material 4/);
  await materialTabs.getByRole('tab',{name:'Yoodli · 5',exact:true}).click();
  await page.getByLabel('Yoodli to review',{exact:true}).selectOption('yoodli:scenario-3');
  assert.match(await page.locator('#desk-material-panel').innerText(),/Synthetic queued material 3/);
  await page.getByRole('tab',{name:/^Deck ·/}).click();
  const select=page.getByLabel('Slide to review',{exact:true});await select.waitFor();
  const options=await select.locator('option').evaluateAll(ns=>ns.map(n=>n.value));
  const jobs=(await page.evaluate(()=>ask('fixture-review-state'))).jobs;
  for(const width of [390,1280])for(const colorScheme of ['light','dark']){
   await page.setViewportSize({width,height:844});await page.emulateMedia({colorScheme,reducedMotion:'reduce'});
   await select.selectOption(options[1]);
   await page.getByRole('tab',{name:'Text & notes',exact:true}).click();
   const title=page.getByLabel('Slide 2 title',{exact:true});await title.fill('Local unsaved slide title');
   // The compact material header can put this above the viewport midpoint.
   // Position it below the toolbar so the regression still exercises scrolling.
   await select.evaluate(n=>{n.scrollIntoView({block:'start'});scrollBy(0,-120);n.focus({preventScroll:true});});
   const before=await select.evaluate(n=>({y:n.getBoundingClientRect().y,scroll:scrollY}));
   assert(before.scroll>100,'Exercise a scrolled page');
   // Keep a node identity witness: an in-place selection must not redraw the page.
   await select.evaluate(n=>n.dataset.witness='same-selector');
   await select.selectOption(options[2]);
   assert.equal(await select.getAttribute('data-witness'),'same-selector');
   assert(await select.evaluate(n=>document.activeElement===n),'Selector retains keyboard focus');
   assert(Math.abs((await select.boundingBox()).y-before.y)<2,'Selector retains viewport position');
   await select.selectOption(options[1]);
   await page.getByRole('tab',{name:'Text & notes',exact:true}).click();
   assert.equal(await title.inputValue(),'Local unsaved slide title');
   await title.focus();await title.press('ArrowLeft');const caret=await title.evaluate(n=>n.selectionStart);
   await page.evaluate(()=>{deskHeld(view.path).drawn='';return refresh();});
   assert(await title.evaluate((n,at)=>document.activeElement===n&&n.selectionStart===at,caret),'Polling keeps editing focus/caret');
   assert.equal(await select.inputValue(),options[1]);
   assert.equal(await page.getByRole('tab',{name:'Text & notes',exact:true}).getAttribute('aria-selected'),'true');
   await page.getByRole('tab',{name:'Preview',exact:true}).click();
   assert.equal(await title.isVisible(),false,'Only the chosen slide task is visible');
   await page.getByRole('tab',{name:/^Review & changes/}).click();
   assert.equal(await title.isVisible(),false);
   await page.getByRole('tab',{name:'Preview',exact:true}).click();
   assert.equal(await page.getByText('Deck actions',{exact:true}).evaluate(n=>n.parentElement.open),false);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   if(process.env.VISIBILITY_RESULTS){fs.mkdirSync(process.env.VISIBILITY_RESULTS,{recursive:true});await select.evaluate(n=>n.scrollIntoView({block:'center'}));await page.screenshot({path:path.join(process.env.VISIBILITY_RESULTS,`rendered-${width}-${colorScheme}.png`)});}
  }
  await page.emulateMedia({reducedMotion:'no-preference'});
  const tasks=page.getByRole('tablist',{name:'Slide task',exact:true});
  for(const name of ['Text & notes','Preview','Review & changes','Text & notes'])await tasks.getByRole('tab',{name:new RegExp('^'+name)}).click();
  assert.equal(await tasks.getAttribute('data-cult-at'),'1','Rapid switching keeps the final selection');
  assert.equal(await page.getByLabel('Slide 2 title',{exact:true}).inputValue(),'Local unsaved slide title','Animation retains edits');
  await page.emulateMedia({reducedMotion:'reduce'});
  await tasks.getByRole('tab',{name:'Preview',exact:true}).click();
  assert.equal(await tasks.evaluate(n=>getComputedStyle(n,'::before').transitionDuration),'0s');
  assert.equal(await page.locator('#desk-slide-task-panel').evaluate(n=>n.getAnimations({subtree:true}).length),0,'Reduced motion creates no content animation');
  assert.equal((await page.evaluate(()=>ask('fixture-review-state'))).jobs,jobs,'Selection/editing/polling schedules no workers');
  assert.deepEqual(errors,[]);
  console.log('PASS rendered slide review: stable scrolled selector/focus, retained unsaved edits/caret/selection, no jobs, 390/1280 light/dark');
 }finally{if(browser)await browser.close();child.kill('SIGTERM');await new Promise(resolve=>child.exitCode!==null?resolve():child.once('exit',resolve));assert.equal(child.exitCode,0,diagnostic);}
})().catch(e=>{console.error(e);process.exitCode=1;});
