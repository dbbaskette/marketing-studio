/* Actual page + API; scripted workers and disposable workspace only. */
const {chromium}=require('playwright'),{spawn}=require('node:child_process'),assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
(async()=>{
 const child=spawn(process.env.PYTHON||'python3',['tests/research_decision_fixture.py'],{stdio:['ignore','pipe','pipe']});let errors='';child.stderr.on('data',b=>errors+=b);
 let browser;
 try {
  const test=await new Promise((resolve,reject)=>{let out='';const timer=setTimeout(()=>reject(Error('Fixture timeout '+errors)),30000);child.stdout.on('data',b=>{out+=b;if(out.includes('\n')){clearTimeout(timer);resolve(JSON.parse(out.split('\n')[0]));}});child.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exit '+code+' '+errors));});});
  browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});
  const page=await browser.newPage({viewport:{width:390,height:950}}),failures=[];page.on('pageerror',e=>failures.push(e.message));
  await page.goto(test.url+'&resume='+encodeURIComponent(path.basename(test.path)));
  const before=await page.evaluate(()=>ask('fixture-decision-state'));
  const opener=page.getByRole('button',{name:'View flagged items',exact:true});
  await opener.click();
  await page.getByRole('heading',{name:'Flagged research items',exact:true}).waitFor();
  assert.equal(await page.evaluate(()=>document.activeElement.textContent),'Flagged research items');
  assert.equal(await opener.getAttribute('aria-expanded'),'true');
  assert.equal(await page.getByText('Flagged content:',{exact:true}).count(),2);
  assert.equal(await page.getByText('Why it was flagged:',{exact:true}).count(),2);
  assert(await page.getByRole('link',{name:'Open source',exact:true}).first().isVisible());
  await page.getByText('Read the complete draft',{exact:true}).click();
  assert(await page.getByText('Read the complete draft',{exact:true}).evaluate(n=>n.parentElement.open));
  await page.getByRole('button',{name:'Close review',exact:true}).click();
  assert.equal(await opener.getAttribute('aria-expanded'),'false');
  assert(await opener.evaluate(n=>n===document.activeElement),'Closing inspection returns focus');
  const inspected=await page.evaluate(()=>ask('fixture-decision-state'));
  assert.deepEqual(inspected,before,'Inspecting/closing makes no decisions, report changes, or jobs');
  await opener.click();
  await page.getByRole('heading',{name:'Flagged research items',exact:true}).waitFor();
  await page.getByRole('button',{name:'Save choices',exact:true}).click();
  await page.getByText('Choose Include, Include with warning, or Exclude for every flag.',{exact:true}).waitFor();
  assert.equal(await page.locator('input[type=radio]:checked').count(),0);
  await page.getByRole('radio',{name:'Include',exact:true}).first().check();
  await page.getByRole('group',{name:'Report passage',exact:true}).getByRole('radio',{name:'Exclude',exact:true}).check();
  for(const width of [390,1280])for(const colorScheme of ['light','dark']){
   await page.setViewportSize({width,height:950});await page.emulateMedia({colorScheme,reducedMotion:'reduce'});
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'horizontal overflow');
   if(process.env.RESEARCH_DECISION_RESULTS){fs.mkdirSync(process.env.RESEARCH_DECISION_RESULTS,{recursive:true});await page.getByRole('heading',{name:'Flagged research items',exact:true}).scrollIntoViewIfNeeded();await page.screenshot({path:path.join(process.env.RESEARCH_DECISION_RESULTS,`creator-review-${width}-${colorScheme}.png`)});}
  }
  await page.getByRole('button',{name:'Save choices',exact:true}).click();
  await page.getByText(/What happened: Your research choices are saved/).waitFor().catch(async error=>{throw Error(error.message+'\nPAGE: '+(await page.locator('body').innerText()).slice(-9000)+'\nJS: '+JSON.stringify(failures));});
  const after=await page.evaluate(()=>ask('fixture-decision-state'));
  assert.equal(after.jobs,before.jobs);assert.equal(after.creator,true);assert.match(after.report,/Omitted by the creator/);assert.doesNotMatch(after.report,/Creator included with warning|Preserve.*warnings|independent-check notes/);assert.deepEqual(failures,[]);
  console.log('PASS Training Studio: no default inclusion; include/exclude save; phone/desktop light/dark; heading focus; zero provider dispatch.');
 } finally {
  if(browser)await browser.close();child.kill('SIGTERM');await new Promise(resolve=>child.exitCode!==null?resolve():child.once('exit',resolve));assert.equal(child.exitCode,0,errors);
 }
})().catch(error=>{console.error(error);process.exitCode=1;});
