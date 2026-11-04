/* Native outline gate; all sources, authors, workspaces and settings are synthetic. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
async function fixture(args=[]){
 const child=spawn(process.env.PYTHON||'python3',[path.join(__dirname,'story_fixture.py'),...args],{stdio:['ignore','pipe','pipe']});
 let diagnostic='';child.stderr.on('data',b=>diagnostic+=b);
 const result=await new Promise((resolve,reject)=>{let output='';const timer=setTimeout(()=>reject(Error(diagnostic||'Fixture timeout')),30000);child.stdout.on('data',b=>{output+=b;if(output.includes('\n')){clearTimeout(timer);try{resolve(JSON.parse(output.split('\n')[0]));}catch(e){reject(e);}}});child.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code+': '+diagnostic));});});
 return {...result,stop:async()=>{child.kill('SIGTERM');await new Promise(resolve=>child.exitCode!==null?resolve():child.once('exit',resolve));}};
}
(async()=>{
 let browser;
 try{
  browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});
  for(const width of [390,1280]){
   const test=await fixture();
   try{
    const page=await browser.newPage({viewport:{width,height:844}}),errors=[];
    page.on('pageerror',e=>errors.push(e.stack||e.message));
    await page.addInitScript(root=>history.replaceState({screen:'deck',path:root},''),test.path);
    await page.goto(test.url);await page.getByRole('heading',{name:'Review the slide story',exact:true}).waitFor();
    await page.getByText('From an idea · Slide story',{exact:true}).waitFor();
    const before=await page.evaluate(root=>ask('run',{path:root}),test.path);
    assert.equal(before.state,'waiting');assert.equal(before.timeline.find(s=>s.name==='scan').attempts,1);
    assert(!before.timeline.some(s=>s.name==='research'&&s.state==='done'),'no research before outline approval');
    await page.getByLabel('Section 1 title',{exact:true}).fill('Approved context');
    const objectives=page.getByLabel('Section 1 messages',{exact:true});
    const raw='Explain capacity conditions.\n\nApply them safely.';await objectives.fill(raw);
    await objectives.press('ArrowLeft');await objectives.press('ArrowLeft');
    const caret=await objectives.evaluate(n=>[n.selectionStart,n.selectionEnd]);
    await page.evaluate(()=>refresh());
    assert.equal(await objectives.inputValue(),raw,'polling preserves blank lines and typing');
    assert.deepEqual(await objectives.evaluate(n=>[n.selectionStart,n.selectionEnd]),caret,'polling preserves the caret');
    await page.getByLabel('Section 1 research questions',{exact:true}).fill('Which capacity conditions hold?');
    await page.getByRole('button',{name:'Remove section 2',exact:true}).click();
    await page.getByRole('button',{name:'Add section',exact:true}).click();
    await page.getByLabel('Section 2 title',{exact:true}).fill('Local added section');
    await page.getByRole('button',{name:'Remove section 2',exact:true}).click();
    assert.equal(await page.getByLabel('Your additional research questions',{exact:true}).inputValue(),'Which failure modes remain?');
    await page.getByRole('button',{name:'Save story',exact:true}).click();
    await page.getByText('Story saved. No assistant work started.',{exact:true}).waitFor();
    const saved=await page.evaluate(root=>ask('run',{path:root}),test.path);
    assert.equal(saved.spent.dollars,before.spent.dollars);assert.equal(saved.timeline.find(s=>s.name==='scan').attempts,1);
    assert(!saved.timeline.some(s=>s.name==='research'&&s.state==='done'));
    await page.reload();await page.getByRole('heading',{name:'Review the slide story',exact:true}).waitFor();
    assert.equal(await page.getByLabel('Section 1 title',{exact:true}).inputValue(),'Approved context');
    for(const colorScheme of ['light','dark']){
     await page.emulateMedia({colorScheme,reducedMotion:'reduce'});
     assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
     const short=await page.locator('main input,main textarea,main button').evaluateAll(nodes=>nodes.filter(n=>n.offsetParent!==null&&n.getBoundingClientRect().height<43.5).map(n=>n.textContent));assert.deepEqual(short,[]);
     if(process.env.PRESENTATION_STORY_RESULTS){fs.mkdirSync(process.env.PRESENTATION_STORY_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.PRESENTATION_STORY_RESULTS,`outline-${width}-${colorScheme}.png`)});}
    }
    await page.getByLabel('Section 1 title',{exact:true}).focus();await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(()=>document.activeElement?.getAttribute('id')),'story-section-context-messages');
    await page.getByRole('button',{name:'Approve story & research',exact:true}).click();
    let after;
    for(let poll=0;poll<900;poll++){
     after=await page.evaluate(root=>ask('run',{path:root}),test.path);
     if(after.gate?.name==='gate:outline'||after.problem)break;
     await new Promise(resolve=>setTimeout(resolve,50));
    }
    assert.equal(after.problem,null,JSON.stringify(after.problem));assert.equal(after.gate.name,'gate:outline');
    assert.equal(after.timeline.find(s=>s.name==='scan').attempts,1);
    assert.deepEqual(errors,[]);console.log('PASS editable outline '+width);await page.close();
   }finally{await test.stop();}
  }
  console.log('PASS Presentation Studio story: local edit/remove/save/reload, zero deep work before approval, retained slide-text approval, keyboard and 390/1280 light/dark');
 }finally{if(browser)await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
