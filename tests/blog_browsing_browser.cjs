/* Real Blog Studio browsing with disposable local data, no provider jobs. */
const {spawn}=require('node:child_process'),{chromium}=require('playwright'),assert=require('node:assert/strict');
(async()=>{
 const child=spawn(process.env.PYTHON||'python3',['tests/blog_browsing_fixture.py'],{stdio:['ignore','pipe','pipe']});
 let browser,diagnostic='';child.stderr.on('data',b=>diagnostic+=b);
 try{
  const fixture=await new Promise((resolve,reject)=>{let raw='';const timer=setTimeout(()=>reject(Error('Fixture timeout '+diagnostic)),30000);child.stdout.on('data',b=>{raw+=b;if(raw.includes('\n')){clearTimeout(timer);resolve(JSON.parse(raw.split('\n')[0]));}});child.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exit '+code+' '+diagnostic));});});
  browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[],requests=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.url().includes('/api/'))requests.push(new URL(r.url()).pathname);});
  await page.goto(fixture.url);await page.waitForFunction(()=>studio.settings&&studio.screen==='home'&&Array.isArray(studio.listing));
  await page.waitForFunction(()=>!studio.polling);
  const start=requests.length;
  await page.evaluate(async()=>{Object.defineProperty(document,'hidden',{configurable:true,value:true});document.dispatchEvent(new Event('visibilitychange'));for(let i=0;i<5;i++)await sPoll();});
  assert.equal(requests.length,start,'Five hidden interval ticks make no requests');
  await page.evaluate(()=>{Object.defineProperty(document,'hidden',{configurable:true,value:false});document.dispatchEvent(new Event('visibilitychange'));});
  await page.waitForFunction(()=>!studio.polling);assert.equal(requests.slice(start).filter(r=>r==='/api/runs').length,1);
  for(const width of [390,1280]){
   await page.setViewportSize({width,height:844});await page.evaluate(()=>sLegacy('library'));
   await page.locator('#query').fill('no-such-synthetic-reference');await page.locator('#search-go').click();
   await page.getByRole('heading',{name:'No matching items',exact:true}).waitFor();
   assert.equal(await page.locator('#page-label').innerText(),'No matches');
   await page.getByRole('button',{name:'Clear search and filters',exact:true}).click();
   await page.getByRole('heading',{name:'Build your reference shelf',exact:true}).waitFor();
   assert.equal(await page.locator('#query').inputValue(),'');
   assert(await page.locator('#query').evaluate(n=>n===document.activeElement));
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  }
  assert.deepEqual(errors,[]);
  console.log('PASS Blog Studio browsing: five hidden ticks = zero reads; visible event = one catch-up read; no-match recovery and search focus at 390/1280px');
 }finally{if(browser)await browser.close();child.kill('SIGTERM');await new Promise(resolve=>child.exitCode!==null?resolve():child.once('exit',resolve));assert.equal(child.exitCode,0,diagnostic);}
})().catch(e=>{console.error(e);process.exitCode=1;});
