/* Actual new-training source handoff; synthetic progress, no live provider jobs. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 const child=spawn(process.env.PYTHON||'python3',[path.join(__dirname,'training_plan_fixture.py'),'--new'],{stdio:['ignore','pipe','pipe']});
 let browser,diagnostics='';child.stderr.on('data',b=>diagnostics+=b);
 try{
  const fixture=await new Promise((resolve,reject)=>{let raw='';const timer=setTimeout(()=>reject(Error('Fixture timeout '+diagnostics)),30000);child.stdout.on('data',b=>{raw+=b;if(raw.includes('\n')){clearTimeout(timer);try{resolve(JSON.parse(raw.split('\n')[0]));}catch(e){reject(e);}}});child.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exit '+code+' '+diagnostics));});});
  browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});
  const page=await browser.newPage({viewport:{width:1280,height:950}}),errors=[],writes=[];
  page.on('pageerror',e=>errors.push(e.message));page.on('request',r=>{if(r.method()==='POST')writes.push({url:new URL(r.url()).pathname,body:r.postDataJSON()});});
  page.setDefaultTimeout(15000);
  await page.goto(fixture.url);await page.getByRole('button',{name:'New training',exact:true}).click();
  await page.locator('#new-title').fill('Synthetic source handoff');
  await page.locator('#new-topic').fill('Teach rolling restart order, capacity, and health checks.');
  await page.locator('#new-audience').fill('Technical learners');
  await page.getByRole('checkbox',{name:'Learner guide',exact:true}).check();
  await page.getByRole('button',{name:'No deck',exact:true}).click();
  await page.getByLabel('Upload source files',{exact:true}).setInputFiles({name:'reference.txt',mimeType:'text/plain',buffer:Buffer.from('A rolling restart replaces instances one batch at a time. Keep more than one instance to maintain capacity. Health checks decide when the next batch starts.\n')});
  await page.getByRole('button',{name:'Preview text',exact:true}).waitFor();
  await page.getByRole('button',{name:'Start',exact:true}).click();
  await page.getByRole('heading',{name:'Here’s what this training will cover',exact:true}).waitFor({timeout:45000});
  assert.equal(await page.getByText('That is all of them',{exact:true}).count(),0);
  assert.equal(writes.filter(r=>r.url==='/api/trainings').length,1);
  assert.equal(writes.filter(r=>r.url==='/api/documents').length,0,'Start must not upload or confirm captured documents again');
  assert.equal(writes.filter(r=>r.url==='/api/research-sources'&&r.body.action==='capture').length,1);
  const sourceRun=await page.evaluate(()=>({path:view.path,run:view.run}));
  assert.equal(sourceRun.run.documents.waiting,false);assert.equal(sourceRun.run.documents.added[0].name,'reference.txt');
  let phase='investigate',elapsed=60;
  const streams=[
   {id:'area1',status:'working',questions:['How does a rolling restart keep serving requests during an upgrade?','Which readiness checks control the next batch?','When should a failed batch pause the rollout?']},
   {id:'area2',status:'kept',questions:['Which capacity constraints must learners check before a restart?','What assumptions limit the availability claim?']},
   {id:'area3',status:'working',questions:['What worked example helps learners choose a safe rollout strategy?','How can learners diagnose an unhealthy replacement?']}
  ];
  await page.route('**/api/run?*',async route=>{const response=await route.fetch(),body=await response.json();Object.assign(body,{state:'working',training_plan:null,training_plan_pending:true,research_progress:{phase,streams},timing:{elapsed_seconds:elapsed,active_seconds:60,assistant_seconds:140}});await route.fulfill({response,json:body});});
  await page.route('**/api/drafts?*',async route=>{const response=await route.fetch(),body=await response.json();body.progress={running:true,line:'',doing:''};await route.fulfill({response,json:body});});
  async function refresh(){await page.evaluate(async()=>{await refresh();});await page.getByRole('region',{name:'Research progress',exact:true}).waitFor();}
  async function fit(){assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Progress must not overflow');}
  async function capture(name){if(process.env.TRAINING_PROGRESS_RESULTS){fs.mkdirSync(process.env.TRAINING_PROGRESS_RESULTS,{recursive:true});await page.evaluate(()=>{document.activeElement?.blur();scrollTo(0,0);});await page.screenshot({path:path.join(process.env.TRAINING_PROGRESS_RESULTS,name+'.png'),fullPage:true});}}
  await refresh();
  const panel=page.getByRole('region',{name:'Research progress',exact:true});
  assert.equal(await panel.getByRole('button',{name:'Stop training',exact:true}).count(),1);
  assert.equal(await page.getByRole('button',{name:'Stop training',exact:true}).count(),1);
  assert.equal(await page.locator('.research-evidence-meter').getAttribute('value'),'1');
  await panel.getByText('1 minute elapsed · 1 minute actively working',{exact:true}).waitFor();
  const questions=panel.locator('.research-area-details').first();await questions.locator('summary').focus();await questions.locator('summary').press('Space');
  await questions.getByText('When should a failed batch pause the rollout?',{exact:true}).waitFor();
  elapsed=120;await refresh();await panel.getByText('2 minutes elapsed · 1 minute actively working',{exact:true}).waitFor();assert.equal(await panel.locator('.research-area-details').first().evaluate(n=>n.open),true);
  assert.equal(await page.evaluate(()=>document.activeElement.dataset.key),'research-area-area1-toggle');
  await panel.locator('.research-area-details').first().locator('summary').press('Space');
  await page.locator('.toast').last().waitFor({state:'hidden',timeout:10000});
  for(const [width,theme] of [[1280,'light'],[1280,'dark'],[390,'light'],[390,'dark'],[320,'light']]){
   await page.setViewportSize({width,height:950});await page.emulateMedia({colorScheme:theme,reducedMotion:'reduce'});await fit();
   assert.equal(await panel.locator('.research-area').count(),3);
   assert.deepEqual(await panel.locator('summary,button').evaluateAll(nodes=>nodes.filter(n=>n.getBoundingClientRect().height<43.5).map(n=>n.textContent)),[]);
   if(width<400){await panel.getByText('Timing details',{exact:true}).scrollIntoViewIfNeeded();const timing=await panel.getByText('Timing details',{exact:true}).boundingBox(),navigation=await page.locator('#sidebar').boundingBox();assert.ok(timing.y+timing.height<=navigation.y,'Timing controls must scroll above phone navigation');}
   if(width>320)await capture(`training-research-${width}-${theme}`);
  }
  await page.setViewportSize({width:1280,height:950});phase='synthesize';await refresh();
  await panel.getByRole('heading',{name:'Combining findings',exact:true}).waitFor();assert.equal(await panel.locator('progress').count(),0);
  phase='review';await refresh();await panel.getByRole('heading',{name:'Independent check',exact:true}).waitFor();
  assert.deepEqual(errors,[]);
  console.log('PASS actual source upload → Start → topics review without second intake; one progress panel, expandable questions/focus retained on refresh, phases, timing, 320–1280px light/dark, no provider jobs.');
 }catch(error){console.error(diagnostics);throw error;}
 finally{if(browser)await browser.close();child.kill('SIGTERM');await new Promise(resolve=>{if(child.exitCode!==null)resolve();else{child.once('exit',resolve);setTimeout(()=>{child.kill('SIGKILL');resolve();},10000).unref();}});}
})().catch(error=>{console.error(error);process.exitCode=1;});
