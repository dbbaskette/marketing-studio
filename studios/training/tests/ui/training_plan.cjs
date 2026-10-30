/* Real Training Studio page, native API and engine; all authors/settings are fixtures. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 let browser;
 try{
  browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});
  for(const width of [390,1280]){
   const child=spawn(process.env.PYTHON||'python3',[path.join(__dirname,'training_plan_fixture.py')],{stdio:['ignore','pipe','pipe']});
   let diagnostics=''; child.stderr.on('data',b=>diagnostics+=b);
   try{
    const fixture=await new Promise((resolve,reject)=>{let output='';const timer=setTimeout(()=>reject(Error('Fixture timed out '+diagnostics)),30000);child.stdout.on('data',b=>{output+=b;if(output.includes('\n')){clearTimeout(timer);try{resolve(JSON.parse(output.split('\n')[0]));}catch(e){reject(e);}}});child.on('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code+' '+diagnostics));});});
    const page=await browser.newPage({viewport:{width,height:900}}),errors=[];
    page.on('pageerror',e=>errors.push(e.message));
    await page.addInitScript(({root})=>history.replaceState({screen:'run',path:root},''),{root:fixture.path});
    await page.goto(fixture.url);
    await page.getByRole('heading',{name:'Here’s what this training will cover',exact:true}).waitFor({timeout:30000});
    assert.equal(await page.getByRole('button',{name:'Finishing',exact:true}).count(),0);
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Phone view must not overflow');
    const before=await page.evaluate(root=>ask('run',{path:root}),fixture.path);
    assert.equal(before.state,'waiting');
    assert.ok(!before.steps.some(s=>s.id?.includes('sample')),'No sample-lesson step');
    await page.getByRole('button',{name:'Ask for changes',exact:true}).click();
    await page.getByText('Say which topics, depth or examples should change.',{exact:true}).waitFor();
    await page.getByLabel('Anything to change?',{exact:true}).fill('Explain the mechanism more deeply and include a practical exercise.');
    await page.getByRole('button',{name:'Ask for changes',exact:true}).click();
    await page.waitForFunction(({root,previous})=>ask('run',{path:root}).then(run=>run.training_plan?.expected && run.training_plan.expected!==previous),{root:fixture.path,previous:before.training_plan.expected});
    await page.getByRole('heading',{name:'Here’s what this training will cover',exact:true}).waitFor();
    if(process.env.TRAINING_PLAN_UI_RESULTS){fs.mkdirSync(process.env.TRAINING_PLAN_UI_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.TRAINING_PLAN_UI_RESULTS,'training-topics-'+width+'.png'),fullPage:true});}
    await page.getByRole('button',{name:'Build the training',exact:true}).click();
    await page.waitForFunction(root=>ask('run',{path:root}).then(run=>!run.training_plan_pending && !run.problem && run.state==='done'),fixture.path,{timeout:45000});
    await page.getByRole('button',{name:'Finishing',exact:true}).waitFor();
    assert.equal(await page.getByRole('heading',{name:'Here’s what this training will cover',exact:true}).count(),0);
    assert.deepEqual(errors,[]);await page.close();
   }finally{child.kill('SIGTERM');await new Promise(resolve=>{if(child.exitCode!==null)resolve();else{child.once('exit',resolve);setTimeout(resolve,10000);}});}
  }
  console.log('PASS real Training Studio phone/desktop: one topics review, scoped changes, automatic materials, no sample lesson or premature delivery');
 }finally{if(browser)await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
