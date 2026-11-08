/* Source-adapted controls on real disposable desks; no live providers. */
const {spawn}=require('node:child_process'),{chromium}=require('playwright');
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
async function fixture(args){
 const child=spawn(process.env.PYTHON||'python3',args,{stdio:['ignore','pipe','pipe']});let diagnostic='';
 child.stderr.on('data',b=>diagnostic+=b);
 const data=await new Promise((resolve,reject)=>{let raw='';const timer=setTimeout(()=>reject(Error('Fixture timeout '+diagnostic)),30000);child.stdout.on('data',b=>{raw+=b;if(raw.includes('\n')){clearTimeout(timer);resolve(JSON.parse(raw.split('\n')[0]));}});child.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exit '+code+' '+diagnostic));});});
 return {...data,stop:async()=>{child.kill('SIGTERM');await new Promise(resolve=>child.exitCode!==null?resolve():child.once('exit',resolve));assert.equal(child.exitCode,0,diagnostic);}};
}
async function checkRail(page,names){
 const rail=page.locator('.cult-tab-rail');
 for(const name of [...names,...names.slice().reverse()]){
  await rail.locator('button').filter({hasText:new RegExp('^'+name+'$')}).click();
  await page.waitForFunction(at=>document.querySelector('.cult-tab-rail')?.dataset.cultAt===String(at),names.indexOf(name));
  assert.equal(await rail.locator('[aria-pressed="true"]').innerText(),name);
 }
 const geometry=await rail.evaluate(n=>({width:n.getBoundingClientRect().width,heights:[...n.querySelectorAll('button')].map(b=>b.getBoundingClientRect().height)}));
 assert(geometry.width>200&&geometry.heights.every(h=>h>=44),'Full-size pointer targets');
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No horizontal overflow');
 await page.emulateMedia({reducedMotion:'reduce'});
 assert.equal(await rail.evaluate(n=>getComputedStyle(n,'::before').transitionDuration),'0s','Reduced motion removes pill movement');
 await rail.locator('button').last().press('Enter');
 assert.equal(await rail.locator('[aria-pressed="true"]').innerText(),names.at(-1),'Keyboard activation works');
 await page.emulateMedia({reducedMotion:'no-preference'});
}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});
 try{for(const product of ['blog','presentation']){
  const test=await fixture(product==='blog'?['tests/blog_browsing_fixture.py']:['tests/slide_review_fixture.py','presentation','--rendered']);
  const page=await browser.newPage(),errors=[],work=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST'&&/\/api\/(tool-action|desk-rewrite|desk-finish|desk-note|slide-note)/.test(r.url()))work.push(r.url());});
  try{
   if(product==='blog'){const url=new URL(test.url);url.searchParams.set('screen','desk');url.searchParams.set('id',test.id);url.searchParams.set('view','full');await page.goto(url.href);}
   else await page.goto(test.url+'&resume='+encodeURIComponent(path.basename(test.path)));
   await page.locator('.cult-tab-rail').waitFor();
   const before=product==='presentation'?(await page.evaluate(()=>ask('fixture-review-state'))).jobs:0;
   for(const width of [390,1280])for(const colorScheme of ['light','dark']){
    await page.setViewportSize({width,height:900});await page.emulateMedia({colorScheme,reducedMotion:'no-preference'});
    if(product==='blog'&&width===390){
     const fold=page.locator('.desk-tools-fold.cult-expandable');await fold.waitFor();
     if(!await fold.evaluate(n=>n.open))await fold.locator('summary').press('Enter');
     assert(await fold.evaluate(n=>n.open),'Phone tools open with keyboard');
    }
    await checkRail(page,product==='blog'?['Read','Edit section','Full desk']:['Slides','Outline']);
    if(process.env.CULT_RESULTS){fs.mkdirSync(process.env.CULT_RESULTS,{recursive:true});await page.locator('.cult-tab-rail').scrollIntoViewIfNeeded();await page.screenshot({path:path.join(process.env.CULT_RESULTS,`${product}-${width}-${colorScheme}.png`)});}
   }
   if(product==='presentation')assert.equal((await page.evaluate(()=>ask('fixture-review-state'))).jobs,before,'Tab navigation schedules no jobs');
   assert.deepEqual(work,[]);assert.deepEqual(errors,[]);
   console.log('PASS '+product+': real source-adapted controls, keyboard, rapid selection, reduced motion, 390/1280 light/dark, no work scheduled');
  }finally{await page.close();await test.stop();}
 }}finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
