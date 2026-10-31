/* Real protected Marketing Studio home, synthetic metadata, no studio/provider launches. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 const renderer=process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER;
 const child=spawn(process.env.PYTHON||'python3',['studios/infographic/tests/ui/fixture_server.py','--renderer',renderer,'--suite'],{stdio:['ignore','pipe','pipe']});
 let browser,diagnostics='';child.stderr.on('data',b=>diagnostics+=b);
 try{
  const url=await new Promise((resolve,reject)=>{let raw='';const timer=setTimeout(()=>reject(Error('Fixture timeout '+diagnostics)),20000);child.stdout.on('data',b=>{raw+=b;if(raw.startsWith('http://')&&raw.includes('\n')){clearTimeout(timer);resolve(raw.split('\n')[0]);}});child.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exit '+code+' '+diagnostics));});});
  browser=await chromium.launch({headless:true,executablePath:renderer});
  const page=await browser.newPage({viewport:{width:1440,height:1000},colorScheme:'light'}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));let variant='ready';
  await page.route('**/api/home',async route=>{
   const response=await route.fetch(),data=await response.json();
   data.shared.local.root='~/Studios';
   for(const studio of data.studios){
    studio.readiness={state:'done',label:'Can open',detail:'Synthetic local prerequisite check.',action:null};studio.running=true;
    studio.workspace=studio.id==='infographic'?{state:'local',summary:'Local workspace',detail:'Share selected files through Team library.'}:{state:'connected',summary:'Connected to https://example.invalid/team/a-long-reference-repository-for-layout-checking (main)',detail:null};
    if(variant==='attention'&&studio.id==='blog'){studio.installed=false;studio.version=null;studio.running=false;studio.workspace=null;studio.readiness={state:'off',label:'Not installed',detail:'Install explicitly.'};}
    if(variant==='attention'&&studio.id==='presentation')studio.workspace={state:'disconnected',summary:'Shared settings changed',detail:'Connect to the configured repository. Your local work is kept.',connect:true};
   }
   await route.fulfill({response,json:data});
  });
  async function fit(){assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Home overflow');}
  async function capture(name){if(process.env.HOME_LAUNCHPAD_RESULTS){fs.mkdirSync(process.env.HOME_LAUNCHPAD_RESULTS,{recursive:true});await page.evaluate(()=>{document.activeElement?.blur();scrollTo(0,0);});await page.screenshot({path:path.join(process.env.HOME_LAUNCHPAD_RESULTS,name+'.png')});}}
  await page.goto(url);await page.getByRole('button',{name:'Return to Infographic Studio',exact:true}).waitFor();
  assert.equal(await page.locator('.studio-preview[aria-hidden="true"] svg').count(),4);
  // Readiness is explained in words on each card, not only in a tooltip (issue 215).
  assert.deepEqual(await page.locator('.studio-readiness-detail').allTextContents(),Array(4).fill('Synthetic local prerequisite check.'));
  assert.equal(await page.locator('.studio-readiness[title]').count(),0);
  let cards=await page.locator('.studio-card').evaluateAll(nodes=>nodes.map(n=>{const r=n.getBoundingClientRect();return {x:r.x,y:r.y,height:r.height};}));
  assert.equal(cards[0].y,cards[1].y);assert.ok(cards[2].y>cards[0].y);
  assert.ok(cards.every(c=>c.height<270),'Desktop cards should be compact without a forced empty row');
  const details=page.locator('.studio-repository').first(),summary=details.locator('summary');
  await summary.focus();await summary.press('Space');assert.equal(await details.evaluate(n=>n.open),true);
  await details.getByText(/a-long-reference-repository-for-layout-checking/).waitFor();await fit();
  await summary.press('Space');assert.equal(await details.evaluate(n=>n.open),false);
  await capture('marketing-home-desktop');
  for(const width of [1920,1440,800,390,320])for(const colorScheme of ['light','dark']){
   await page.setViewportSize({width,height:1000});await page.emulateMedia({colorScheme,reducedMotion:'reduce'});await fit();
   const positions=await page.locator('.studio-card').evaluateAll(nodes=>nodes.map(n=>n.getBoundingClientRect().y));
   if(width===1920)assert.ok(positions.every(y=>y===positions[0]),'Wide home uses four peers');
   if(width<=800)assert.ok(positions[1]>positions[0],'Narrow home uses one column');
   assert.deepEqual(await page.locator('.studio-open, .studio-repository > summary').evaluateAll(nodes=>nodes.filter(n=>n.getBoundingClientRect().height<43.5).map(n=>n.textContent)),[]);
   if([1920,390].includes(width))await capture(`marketing-home-${width}-${colorScheme}`);
  }
  await page.setViewportSize({width:1280,height:950});await page.emulateMedia({colorScheme:'light'});
  variant='attention';await page.reload();await page.getByRole('link',{name:'Install Blog Studio',exact:true}).waitFor();
  await page.getByRole('button',{name:'Connect Presentation Studio to the shared storage',exact:true}).waitFor();
  await page.locator('[data-studio="presentation"] .studio-warning').getByText('Shared settings changed',{exact:true}).waitFor();
  await page.waitForTimeout(5200);
  assert.equal(await page.getByRole('link',{name:'Install Blog Studio',exact:true}).textContent(),'Install','Status polling must preserve installation links');
  await fit();await capture('marketing-home-attention');
  const cdp=await page.context().newCDPSession(page);await cdp.send('Emulation.setEmulatedMedia',{features:[{name:'prefers-reduced-transparency',value:'reduce'},{name:'prefers-contrast',value:'more'}]});
  assert.equal(await page.locator('.toolbar').evaluate(n=>getComputedStyle(n).backdropFilter),'none');
  assert.deepEqual(errors,[]);
  console.log('PASS compact Marketing Studio home: real page, format visuals, readiness, version/repository disclosure, connection/install states, keyboard, 320–1920 widths, light/dark and reduced effects; no launches');
 }catch(e){console.error(e);throw e;}
 finally{if(browser)await browser.close();child.kill('SIGTERM');await new Promise(resolve=>{if(child.exitCode!==null)resolve();else{child.once('exit',resolve);setTimeout(()=>{child.kill('SIGKILL');resolve();},10000).unref();}});}
})().catch(e=>{console.error(e);process.exitCode=1;});
