/* Real Change settings flow; disposable state and scripted workers only. */
const {chromium}=require('playwright'),{spawn}=require('node:child_process');
const assert=require('node:assert/strict'),path=require('node:path'),fs=require('node:fs');
async function fixture(){
 const child=spawn(process.env.PYTHON||'python3',['studios/training/tests/ui/training_plan_fixture.py','--desk','--settings','--practice'],{stdio:['ignore','pipe','pipe']});
 let errors='';child.stderr.on('data',b=>errors+=b);
 try {
  const result=await new Promise((resolve,reject)=>{let raw='';const timer=setTimeout(()=>reject(Error('Fixture timed out '+errors)),30000);child.stdout.on('data',b=>{raw+=b;if(raw.includes('\n')){clearTimeout(timer);resolve(JSON.parse(raw.split('\n')[0]));}});child.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code+' '+errors));});});
  return {...result,stop:async()=>{child.kill('SIGTERM');await new Promise(resolve=>child.exitCode!==null?resolve():child.once('exit',resolve));assert.equal(child.exitCode,0,errors);}};
 }catch(error){child.kill('SIGTERM');throw error;}
}
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});
 try{
  for(const width of [390,1280]){
   const test=await fixture();let page;
   try{
    page=await browser.newPage({viewport:{width,height:900}});const failures=[];page.on('pageerror',e=>failures.push(e.message));
    await page.goto(test.url+'&resume='+encodeURIComponent(path.basename(test.path)));
    const before=await page.evaluate(root=>ask('run',{path:root}),test.path);
    await page.getByRole('button',{name:'Change settings',exact:true}).first().click();
    const sheet=page.getByRole('dialog',{name:'Change settings',exact:true});await sheet.waitFor();
    await sheet.getByRole('button',{name:'Materials',exact:true}).click();
    await sheet.getByRole('button',{name:'Define scenarios',exact:true}).click();
    await sheet.getByRole('button',{name:'Teaching',exact:true}).click();
    await sheet.getByRole('button',{name:'Review the change',exact:true}).click();
    assert.equal(await sheet.getByRole('button',{name:'Materials',exact:true}).getAttribute('aria-pressed'),'true');
    await sheet.getByText('Add a short description for each scenario (up to 300 characters), or let AI choose.',{exact:true}).waitFor();
    await sheet.getByLabel('Scenario 1',{exact:true}).fill('Explain restart trade-offs to a skeptical platform lead.');
    for(const colorScheme of ['light','dark']){
     await page.emulateMedia({colorScheme,reducedMotion:'reduce'});
     await sheet.getByLabel('Scenario 1',{exact:true}).scrollIntoViewIfNeeded();
     assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
     assert.equal(await sheet.getByLabel('Scenario 1',{exact:true}).getAttribute('maxlength'),'300');
     if(process.env.TRAINING_SCENARIO_RESULTS){fs.mkdirSync(process.env.TRAINING_SCENARIO_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.TRAINING_SCENARIO_RESULTS,`scenario-settings-${width}-${colorScheme}.png`)});}
    }
    await sheet.getByRole('button',{name:'Review the change',exact:true}).click();
    await sheet.getByText('What this change does',{exact:true}).waitFor();
    await sheet.getByRole('button',{name:'Save the change',exact:true}).click();await sheet.waitFor({state:'hidden'});
    const after=await page.evaluate(root=>ask('run',{path:root}),test.path);
    assert.deepEqual(after.spent,before.spent);
    assert.deepEqual(after.steps.map(s=>[s.id,s.attempts]),before.steps.map(s=>[s.id,s.attempts]));
    await page.reload();await page.getByRole('button',{name:'Change settings',exact:true}).first().click();await sheet.waitFor();
    await sheet.getByRole('button',{name:'Materials',exact:true}).click();
    assert.equal(await sheet.getByLabel('Scenario 1',{exact:true}).inputValue(),'Explain restart trade-offs to a skeptical platform lead.');
    await sheet.getByRole('button',{name:'Let AI choose',exact:true}).click();
    await sheet.getByRole('button',{name:'Review the change',exact:true}).click();
    await sheet.getByRole('button',{name:'Save the change',exact:true}).click();await sheet.waitFor({state:'hidden'});
    const settings=await page.evaluate(root=>ask('training-settings',{path:root}),test.path);
    assert.deepEqual(settings.values.scenario_plan,{mode:'ai',scenarios:[]});
    assert.deepEqual(failures,[]);
    console.log('PASS Training Studio scenario settings '+width+': validation, saved descriptions, reload, AI reset, no dispatch.');
   }finally{if(page)await page.close();await test.stop();}
  }
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
