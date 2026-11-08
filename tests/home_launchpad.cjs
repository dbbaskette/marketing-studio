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
  let homeFailed=false;
  await page.route('**/api/home',async route=>{
   if(homeFailed){await route.abort();return;}
   const response=await route.fetch(),data=await response.json();
   data.shared.local.root='~/Studios';
   data.work_overview={training:{state:'saved',items:[{id:'scope',title:'Synthetic outline',state:'needs-you',action:'Review the training outline',observed_at:'2026-11-04T12:00:00Z'}]},presentation:{state:'saved',items:[{id:'slides',title:'Synthetic deck',state:'in-progress',action:'Open saved progress',observed_at:'2026-11-04T11:00:00Z'}]},infographic:{state:'saved',items:[{id:'page',title:'Synthetic infographic',state:'recent',action:'Open saved work',observed_at:'2026-11-04T10:00:00Z'}]}};
   if(variant==='updated')data.work_overview.training.items[0]={...data.work_overview.training.items[0],title:'Changed saved outline',action:'Answer the pending question'};
   if(variant==='removed')data.work_overview.training.items=[];
   if(['empty','unavailable','limited'].includes(variant))data.work_overview=Object.fromEntries(data.studios.map(studio=>[studio.id,{state:variant==='unavailable'&&studio.id==='training'?'unavailable':'empty',items:[],limited:variant==='limited'}]));
   for(const studio of data.studios){
    studio.readiness={state:'done',label:'Can open',detail:'Synthetic local prerequisite check.',action:null};studio.running=true;
    studio.workspace=studio.id==='infographic'?{state:'local',summary:'Local workspace',detail:'Share selected files through Team library.'}:{state:'connected',summary:'Connected to https://example.invalid/team/a-long-reference-repository-for-layout-checking (main)',detail:null};
    if(variant==='attention'&&studio.id==='blog'){studio.installed=false;studio.version=null;studio.running=false;studio.workspace=null;studio.readiness={state:'off',label:'Not installed',detail:'Install explicitly.'};}
    if(variant==='attention'&&studio.id==='presentation')studio.workspace={state:'disconnected',summary:'Shared settings changed',detail:'Connect to the configured repository. Your local work is kept.',connect:true};
    if(variant==='setup'&&studio.id==='training')studio.readiness={state:'review',label:'Needs setup',detail:'Choose an assistant before opening.',action:{label:'Open shared settings',view:'settings'}};
   }
   await route.fulfill({response,json:data});
  });
  async function fit(){assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Home overflow');}
  async function capture(name){if(process.env.HOME_LAUNCHPAD_RESULTS){fs.mkdirSync(process.env.HOME_LAUNCHPAD_RESULTS,{recursive:true});await page.evaluate(()=>{document.activeElement?.blur();scrollTo(0,0);});await page.screenshot({path:path.join(process.env.HOME_LAUNCHPAD_RESULTS,name+'.png')});}}
  await page.goto(url);await page.getByRole('button',{name:'Return to Infographic Studio',exact:true}).waitFor();
  await page.getByRole('heading',{name:'Needs you',exact:true}).waitFor();
  assert.equal(await page.locator('.studio-card.cult-launch-card').count(),4,'All launch cards use the source-adapted frame');
  await page.getByRole('heading',{name:'In progress',exact:true}).waitFor();
  await page.getByRole('heading',{name:'Recent work',exact:true}).waitFor();
  const recent=page.locator('.work-recent'),recentSummary=recent.locator('summary');
  assert.equal(await recent.evaluate(n=>n.open),false,'Recent completed work starts collapsed');
  await recentSummary.focus();await recentSummary.press('Space');
  await recent.getByRole('button',{name:'Open saved work',exact:true}).waitFor();
  await page.evaluate(()=>refreshHomeStatus());assert.equal(await recent.evaluate(n=>n.open),true,'Polling keeps Recent work open');
  await recentSummary.press('Space');
  assert.equal(await page.locator('.studio-preview[aria-hidden="true"] svg').count(),4);
  // Healthy explanations remain in each card's keyboard-accessible Details. Problems
  // stay beside the state and recovery action, never only in a tooltip.
  assert.deepEqual(await page.locator('.studio-readiness-detail').allTextContents(),Array(4).fill('Synthetic local prerequisite check.'));
  assert.equal(await page.locator('.studio-readiness-detail:visible').count(),0);
  assert.equal(await page.locator('.studio-readiness[title]').count(),0);
  let cards=await page.locator('.studio-card').evaluateAll(nodes=>nodes.map(n=>{const r=n.getBoundingClientRect();return {x:r.x,y:r.y,height:r.height};}));
  assert.equal(cards[0].y,cards[1].y);assert.ok(cards[2].y>cards[0].y);
  assert.ok(cards.every(c=>c.height<270),'Desktop cards should be compact without a forced empty row');
  const resume=page.locator('[data-work-key="training:scope"] button');await resume.focus();
  await resume.evaluate(n=>window.originalResume=n);
  await page.evaluate(()=>refreshHomeStatus());
  assert(await resume.evaluate(n=>n===window.originalResume&&document.activeElement===n),'Unchanged poll preserves the resume button');
  variant='updated';
  await page.getByRole('heading',{name:'Changed saved outline',exact:true}).waitFor({timeout:8000});
  assert(await resume.evaluate(n=>n===window.originalResume&&document.activeElement===n),'Changed summary preserves focused action');
  assert.equal(await resume.textContent(),'Answer the pending question');
  homeFailed=true;await page.evaluate(()=>refreshHomeStatus());
  await page.getByText(/Saved work shown may be out of date/).waitFor();
  homeFailed=false;variant='removed';await page.evaluate(()=>refreshHomeStatus());
  await resume.waitFor({state:'detached'});
  variant='ready';await page.evaluate(()=>refreshHomeStatus());
  const details=page.locator('.studio-repository').first(),summary=details.locator('summary');
  await summary.focus();await summary.press('Space');assert.equal(await details.evaluate(n=>n.open),true);
  await details.getByText(/a-long-reference-repository-for-layout-checking/).waitFor();await fit();
  assert(await details.getByText('Synthetic local prerequisite check.',{exact:true}).isVisible());
  await summary.press('Space');assert.equal(await details.evaluate(n=>n.open),false);
  await capture('marketing-home-desktop');
  for(const width of [1920,1440,800,390,320])for(const colorScheme of ['light','dark']){
   await page.setViewportSize({width,height:1000});await page.emulateMedia({colorScheme,reducedMotion:'reduce'});await fit();
   assert.deepEqual(await page.locator('.work-summary button:visible').evaluateAll(nodes=>nodes.filter(n=>n.getBoundingClientRect().height<43.5).map(n=>n.textContent)),[]);
   const positions=await page.locator('.studio-card').evaluateAll(nodes=>nodes.map(n=>n.getBoundingClientRect().y));
   if(width===1920)assert.ok(positions.every(y=>y===positions[0]),'Wide home uses four peers');
   if(width<=800)assert.ok(positions[1]>positions[0],'Narrow home uses one column');
   assert.deepEqual(await page.locator('.studio-open, .studio-repository > summary').evaluateAll(nodes=>nodes.filter(n=>n.getBoundingClientRect().height<43.5).map(n=>n.textContent)),[]);
   const contrast=await page.locator('.studio-open.button-filled, .nav-item[aria-current="page"]').evaluateAll(nodes=>{
    const luminance=color=>{const values=color.match(/[\d.]+/g).slice(0,3).map(Number).map(n=>{n/=255;return n<=.04045?n/12.92:((n+.055)/1.055)**2.4;});return values[0]*.2126+values[1]*.7152+values[2]*.0722;};
    return nodes.map(node=>{const style=getComputedStyle(node),a=luminance(style.color),b=luminance(style.backgroundColor);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);});
   });assert(contrast.every(ratio=>ratio>=4.5),'Studio launch and selected navigation labels meet text contrast');
   if([1920,390].includes(width))await capture(`marketing-home-${width}-${colorScheme}`);
  }
  await page.setViewportSize({width:1280,height:950});await page.emulateMedia({colorScheme:'light'});
  const zoom=await page.context().newCDPSession(page);
  await page.setViewportSize({width:640,height:475});
await zoom.send('Emulation.setDeviceMetricsOverride',{width:640,height:475,deviceScaleFactor:2,mobile:false});assert.equal(await page.evaluate(()=>innerWidth),640,'200% equivalent CSS viewport');await fit();await capture('marketing-home-200-percent-equivalent');
  await zoom.send('Emulation.clearDeviceMetricsOverride');await zoom.detach();await page.setViewportSize({width:1280,height:950});
  variant='setup';await page.evaluate(()=>refreshHomeStatus());
  await page.getByText('Choose an assistant before opening.',{exact:true}).waitFor();
  assert(await page.getByRole('button',{name:'Open shared settings',exact:true}).isVisible());
  variant='empty';await page.evaluate(()=>refreshHomeStatus());
  await page.getByText('No saved work yet. Choose a studio to get started.',{exact:true}).waitFor();await capture('marketing-home-empty');
  variant='unavailable';await page.evaluate(()=>refreshHomeStatus());
  await page.getByText(/Some saved work could not be read/).waitFor();assert.equal(await page.getByText(/No saved work yet/).count(),0);
  variant='limited';await page.evaluate(()=>refreshHomeStatus());
  await page.getByText('No recent work found. Open a studio to see all saved work.',{exact:true}).waitFor();
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
