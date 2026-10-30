/* Real private desk and engine; synthetic sources, authors and renderers only. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
(async()=>{
 let browser;
 try {
  browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});
  for(const width of [390,1280]) {
   const child=spawn(process.env.PYTHON||'python3',[path.join(__dirname,'training_plan_fixture.py'),'--workspace'],{stdio:['ignore','pipe','pipe']});
   let diagnostics='';child.stderr.on('data',b=>diagnostics+=b);
   try {
    const fixture=await new Promise((resolve,reject)=>{let output='';const timer=setTimeout(()=>reject(Error(diagnostics)),30000);child.stdout.on('data',b=>{output+=b;if(output.includes('\n')){clearTimeout(timer);resolve(JSON.parse(output.split('\n')[0]));}});child.on('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code+' '+diagnostics));});});
    const page=await browser.newPage({viewport:{width,height:900}}),errors=[],writes=[];
    page.on('pageerror',e=>errors.push(e.message));
    page.on('request',r=>{if(r.method()==='POST')writes.push(new URL(r.url()).pathname);});
    await page.addInitScript(({root})=>history.replaceState({screen:'run',path:root},''),{root:fixture.path});
    await page.goto(fixture.url);
    await page.getByRole('button',{name:'Build the training',exact:true}).click();
    await page.getByRole('heading',{name:'Review slide text',exact:true}).waitFor({timeout:45000});
    let run=await page.evaluate(root=>ask('run',{path:root}),fixture.path);
    assert.equal(run.state,'waiting');assert(run.outline.waiting);
    assert(!run.steps.some(step=>step.id==='deck-sections' && step.attempts?.length),'No slide drawings before explicit text approval');
    await page.getByRole('button',{name:'Approve text & design deck',exact:true}).click();
    await page.getByRole('tablist',{name:'Training material',exact:true}).waitFor();
    await page.waitForFunction(root=>ask('run',{path:root}).then(run=>run.state==='done'),fixture.path,{timeout:45000});
    await page.getByRole('tab',{name:/^Deck · Needs attention$/}).click();
    await page.getByText('This deck has unresolved review issues. Review the affected slides below before marking it ready.',{exact:true}).waitFor();
    assert.equal(await page.locator('.desk-slide-card').count(),1,'One slide editor, not the whole deck');
    assert.equal(await page.getByRole('button',{name:'Apply fix to this slide',exact:true}).count(),1);
    assert.equal(await page.getByText('Major on what-it-does:',{exact:false}).isVisible(),false,'Raw identifiers stay in collapsed details');
    if(process.env.TRAINING_WORKSPACE_UI_RESULTS){fs.mkdirSync(process.env.TRAINING_WORKSPACE_UI_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.TRAINING_WORKSPACE_UI_RESULTS,'training-slide-review-'+width+'.png'),fullPage:true});}
    await page.getByLabel('Slide to review',{exact:true}).selectOption('check-yourself');
    assert.equal(await page.locator('.desk-slide-card').count(),1);
    assert.equal(await page.getByRole('button',{name:'Apply fix to this slide',exact:true}).count(),0);
    const before=writes.length;
    await page.getByRole('tab',{name:/^Plan · Draft$/}).click();
    await page.getByRole('tab',{name:'Frame',exact:true}).click();
    assert.equal(await page.locator('.desk-part').count(),1,'Only the selected section is mounted');
    const frame=page.getByRole('textbox',{name:'Frame',exact:true});
    const original=await frame.inputValue();
    await frame.fill(original+'\nSynthetic local edit retained across navigation.');
    await page.getByRole('tab',{name:/^Guide · Draft$/}).click();
    await page.getByRole('tab',{name:'Research & sources',exact:true}).click();
    await page.getByRole('tab',{name:/^Plan · Draft$/}).click();
    assert((await page.getByRole('textbox',{name:'Frame',exact:true}).inputValue()).includes('Synthetic local edit retained across navigation.'));
    assert(!writes.slice(before).some(route=>/outline|finding|deck-note|slide-note|ready/.test(route)),'Reading navigation never authorizes work');
    await page.getByRole('tab',{name:'Frame',exact:true}).focus();
    await page.keyboard.press('Home');
    assert.equal(await page.getByRole('tab',{name:'Opening',exact:true}).getAttribute('aria-selected'),'true');
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'No phone overflow');
    if(process.env.TRAINING_WORKSPACE_UI_RESULTS){fs.mkdirSync(process.env.TRAINING_WORKSPACE_UI_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.TRAINING_WORKSPACE_UI_RESULTS,'training-workspace-'+width+'.png'),fullPage:true});}
    assert.deepEqual(errors,[]);await page.close();
   }finally{child.kill('SIGTERM');await new Promise(resolve=>{if(child.exitCode!==null)resolve();else{child.once('exit',resolve);setTimeout(resolve,10000);}});}
  }
  console.log('PASS Training Studio phone/desktop: slide text before design, one material/section/slide, keyboard tabs, retained edits, scoped repair controls, no jobs from reading');
 }finally{if(browser)await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
