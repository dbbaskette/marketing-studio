const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 const child=spawn(process.env.PYTHON||'python3',[path.join(__dirname,'recovery_fixture.py')],{stdio:['ignore','pipe','pipe']});
 let diagnostic='',browser,page,errors=[];child.stderr.on('data',b=>diagnostic+=b);
 try{
  const data=await new Promise((resolve,reject)=>{let raw='';const timer=setTimeout(()=>reject(Error(diagnostic||'Fixture timeout')),20000);child.stdout.on('data',b=>{raw+=b;if(raw.includes('\n')){clearTimeout(timer);resolve(JSON.parse(raw.split('\n')[0]));}});child.once('exit',code=>reject(Error('Fixture exit '+code+' '+diagnostic)));});
  browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});
  page=await browser.newPage({viewport:{width:390,height:844}});page.on('pageerror',e=>{errors.push(e.message);console.error('PAGE ERROR',e.message);});
  await page.goto(data.url+'&resume='+data.id);
  await page.getByRole('heading',{name:'Restart one instance',exact:true,level:1}).waitFor();
  await page.evaluate(()=>compose());
  await page.getByRole('dialog',{name:'Build this page',exact:true}).getByRole('button',{name:'Build page',exact:true}).click();
  const recovery=page.getByRole('dialog',{name:'Continue from the saved step',exact:true});await recovery.waitFor();
  await recovery.getByText('Completed: Page composition.',{exact:true}).waitFor();
  await recovery.getByText('The local preview could not finish.',{exact:true}).waitFor();
  await recovery.getByText(/Check the renderer and fonts in Settings/).waitFor();
  await page.keyboard.press('Escape');await recovery.waitFor({state:'hidden'});
  await page.evaluate(()=>home());
  await page.getByText('Preview failed: retry the saved preview',{exact:true}).waitFor();
  await page.goto(data.url+'&resume='+data.id);
  await page.reload();
  await page.getByRole('heading',{name:'Work kept after a failed step',exact:true}).waitFor();
  for(const width of [320,390,1280])for(const colorScheme of ['light','dark']){
   await page.setViewportSize({width,height:900});await page.emulateMedia({colorScheme,reducedMotion:'reduce'});
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   if(process.env.INFOGRAPHIC_UI_RESULTS){fs.mkdirSync(process.env.INFOGRAPHIC_UI_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.INFOGRAPHIC_UI_RESULTS,`build-recovery-${width}-${colorScheme}.png`)});}
  }
  assert.equal(await page.locator('#actions').getByRole('button',{name:'Retry preview',exact:true}).count(),1);
  const zoom=await page.context().newCDPSession(page);
  await page.setViewportSize({width:640,height:450});
await zoom.send('Emulation.setDeviceMetricsOverride',{width:640,height:450,deviceScaleFactor:2,mobile:false});assert.equal(await page.evaluate(()=>innerWidth),640,'200% equivalent CSS viewport');
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'200% equivalent layout overflow');
  await zoom.send('Emulation.clearDeviceMetricsOverride');await zoom.detach();await page.setViewportSize({width:1280,height:900});
  const retry=page.locator('#actions').getByRole('button',{name:'Retry preview',exact:true});await retry.focus();await retry.press('Enter');
  await page.getByRole('heading',{name:'Work kept after a failed step',exact:true}).waitFor({state:'detached'});
  assert.deepEqual(errors,[]);console.log('PASS persisted preview recovery: correct dialog, reload, local-only retry, no assistant/image calls, 320/390/1280 light/dark keyboard, 200% equivalent layout and reduced motion');
 }catch(error){console.error(error);if(page&&process.env.INFOGRAPHIC_UI_RESULTS){fs.mkdirSync(process.env.INFOGRAPHIC_UI_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.INFOGRAPHIC_UI_RESULTS,'recovery-failure.png')});}throw error;}finally{
  if(browser)await browser.close();child.kill('SIGTERM');
  const code=await new Promise(resolve=>{if(child.exitCode!==null)return resolve(child.exitCode);child.once('exit',resolve);setTimeout(()=>{child.kill('SIGKILL');resolve(-1);},10000).unref();});
  assert.equal(code,0,diagnostic);
 }
})().catch(e=>{console.error(e);process.exitCode=1;});
