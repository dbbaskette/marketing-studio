const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 const child=spawn(process.env.PYTHON||'python3',[path.join(__dirname,'recovery_fixture.py')],{stdio:['ignore','pipe','pipe']});
 let diagnostic='',browser;child.stderr.on('data',b=>diagnostic+=b);
 try{
  const data=await new Promise((resolve,reject)=>{let raw='';const timer=setTimeout(()=>reject(Error(diagnostic||'Fixture timeout')),20000);child.stdout.on('data',b=>{raw+=b;if(raw.includes('\n')){clearTimeout(timer);resolve(JSON.parse(raw.split('\n')[0]));}});child.once('exit',code=>reject(Error('Fixture exit '+code+' '+diagnostic)));});
  browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});
  const page=await browser.newPage({viewport:{width:390,height:844}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(data.url+'&resume='+data.id);
  await page.getByRole('heading',{name:'Restart one instance',exact:true}).waitFor();
  await page.evaluate(()=>compose());
  await page.getByRole('dialog',{name:'Build this page',exact:true}).getByRole('button',{name:'Build page',exact:true}).click();
  const recovery=page.getByRole('dialog',{name:'Continue from the saved step',exact:true});await recovery.waitFor();
  await recovery.getByText('Completed: Page composition.',{exact:true}).waitFor();
  await page.reload();
  await page.getByRole('heading',{name:'Work kept after a failed step',exact:true}).waitFor();
  for(const width of [320,390,1280])for(const colorScheme of ['light','dark']){
   await page.setViewportSize({width,height:900});await page.emulateMedia({colorScheme,reducedMotion:'reduce'});
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   if(process.env.INFOGRAPHIC_UI_RESULTS){fs.mkdirSync(process.env.INFOGRAPHIC_UI_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.INFOGRAPHIC_UI_RESULTS,`build-recovery-${width}-${colorScheme}.png`)});}
  }
  await page.getByRole('button',{name:'Retry preview',exact:true}).click();
  await page.getByRole('heading',{name:'Work kept after a failed step',exact:true}).waitFor({state:'detached'});
  assert.deepEqual(errors,[]);console.log('PASS persisted preview recovery: correct dialog, reload, local-only retry, no assistant/image calls, 320/390/1280 light/dark and reduced motion');
 }finally{
  if(browser)await browser.close();child.kill('SIGTERM');
  const code=await new Promise(resolve=>child.exitCode!==null?resolve(child.exitCode):child.once('exit',resolve));
  assert.equal(code,0,diagnostic);
 }
})().catch(e=>{console.error(e);process.exitCode=1;});
