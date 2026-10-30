/* Real Training Studio page, native API and engine; all authors/settings are fixtures. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 let browser;
 try{
  browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});
  for(const width of [390,1280]){
   const child=spawn(process.env.PYTHON||'python3',[path.join(__dirname,'training_plan_fixture.py'),'--two-levels'],{stdio:['ignore','pipe','pipe']});
   let diagnostics=''; child.stderr.on('data',b=>diagnostics+=b);
   try{
    const fixture=await new Promise((resolve,reject)=>{let output='';const timer=setTimeout(()=>reject(Error('Fixture timed out '+diagnostics)),30000);child.stdout.on('data',b=>{output+=b;if(output.includes('\n')){clearTimeout(timer);try{resolve(JSON.parse(output.split('\n')[0]));}catch(e){reject(e);}}});child.on('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code+' '+diagnostics));});});
    const page=await browser.newPage({viewport:{width,height:900}}),errors=[],sent=[];
    page.on('request',r=>{if(r.method()==='POST'&&new URL(r.url()).pathname==='/api/training-plan')sent.push(r.postDataJSON());});
    page.on('pageerror',e=>{errors.push(e.message);console.error('Page error at '+width+': '+e.message);});
    await page.addInitScript(({root})=>history.replaceState({screen:'run',path:root},''),{root:fixture.path});
    await page.goto(fixture.url);
    try{await page.getByRole('heading',{name:'Here’s what this training will cover',exact:true}).waitFor({timeout:30000});}
    catch(error){console.error('Initial page at '+width+': '+await page.locator('body').innerText());console.error('Fixture run: '+await page.evaluate(root=>ask('run',{path:root}).then(run=>JSON.stringify({state:run.state,problem:run.problem,plan:Boolean(run.training_plan)})),fixture.path));throw error;}
    assert.equal(await page.getByRole('button',{name:'Finishing',exact:true}).count(),0);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Phone view must not overflow');
    const before=await page.evaluate(root=>ask('run',{path:root}),fixture.path);
    assert.equal(before.state,'waiting');
    assert.ok(!before.steps.some(s=>s.id?.includes('sample')),'No sample-lesson step');
    await page.getByRole('button',{name:'Ask for changes',exact:true}).click();
    await page.getByText('Say which topics, depth or examples should change.',{exact:true}).waitFor();
    await page.getByLabel('Anything to change?',{exact:true}).fill('Explain the mechanism more deeply and include a practical exercise.');
    await page.getByLabel('Apply changes to',{exact:true}).selectOption('101');
    await page.getByText('Revise only level 101. Other levels and the research are kept.',{exact:true}).waitFor();
    await page.getByRole('button',{name:'Ask for changes',exact:true}).click();
    await page.waitForFunction(({root,previous})=>ask('run',{path:root}).then(run=>run.training_plan?.expected && run.training_plan.expected!==previous),{root:fixture.path,previous:before.training_plan.expected});
    await page.waitForFunction(()=>!view.busy && document.querySelector('#training-plan-note')?.value==='');
    await page.getByRole('heading',{name:'Here’s what this training will cover',exact:true}).waitFor();
    assert.deepEqual(sent.at(-1).levels,['101']);
    const revised=await page.evaluate(root=>ask('run',{path:root}),fixture.path);
    assert.deepEqual(revised.steps.find(s=>s.id==='blueprint@201').attempts,before.steps.find(s=>s.id==='blueprint@201').attempts,'Level 201 must not acquire another revision attempt');
    await page.evaluate(()=>{document.activeElement?.blur();window.scrollTo(0,0);});
    if(process.env.TRAINING_PLAN_UI_RESULTS){fs.mkdirSync(process.env.TRAINING_PLAN_UI_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.TRAINING_PLAN_UI_RESULTS,'training-topics-'+width+'.png'),fullPage:true});}
    await page.getByRole('button',{name:'Build the training',exact:true}).click();
    await page.waitForFunction(root=>ask('run',{path:root}).then(run=>!run.training_plan_pending && !run.problem && run.state==='done'),fixture.path,{timeout:45000});
    try { await page.getByRole('button',{name:'Finishing',exact:true}).waitFor(); }
    catch(error){console.error('Final page at '+width+': '+await page.locator('body').innerText());console.error('View state: '+await page.evaluate(()=>JSON.stringify({busy:view.busy,state:view.run?.state,plan:view.run?.training_plan,pending:view.run?.training_plan_pending})) );throw error;}
    assert.equal(await page.getByRole('heading',{name:'Here’s what this training will cover',exact:true}).count(),0);
    assert.deepEqual(errors,[]);await page.close();
   }finally{child.kill('SIGTERM');await new Promise(resolve=>{if(child.exitCode!==null)resolve();else{child.once('exit',resolve);setTimeout(resolve,10000);}});}
  }
  console.log('PASS real Training Studio phone/desktop: one topics review, scoped changes, automatic materials, no sample lesson or premature delivery');
 }finally{if(browser)await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
