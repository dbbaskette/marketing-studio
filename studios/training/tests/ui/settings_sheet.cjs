/* A stopped run's real Change settings sheet, with disposable state and fake workers. */
const {chromium}=require('playwright');
const {spawn}=require('node:child_process');
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const python=process.env.PYTHON||'python3';
async function fixture(){
 const child=spawn(python,[path.join(__dirname,'training_plan_fixture.py'),'--desk','--settings'],{stdio:['ignore','pipe','pipe']});
 let diagnostics='';child.stderr.on('data',b=>diagnostics+=b);
 try{
  const found=await new Promise((resolve,reject)=>{let raw='';const timer=setTimeout(()=>reject(Error('Fixture timed out '+diagnostics)),60000);child.stdout.on('data',b=>{raw+=b;if(raw.includes('\n')){clearTimeout(timer);resolve(JSON.parse(raw.split('\n')[0]));}});child.once('exit',code=>{clearTimeout(timer);reject(Error('Fixture exited '+code+' '+diagnostics));});});
  return {child,...found};
 }catch(error){await stop(child);throw error;}
}
async function stop(child){child.kill('SIGTERM');await new Promise(resolve=>{if(child.exitCode!==null)resolve();else{child.once('exit',resolve);setTimeout(()=>{child.kill('SIGKILL');resolve();},10000).unref();}});}
const inside=page=>page.evaluate(()=>document.getElementById('sheet').contains(document.activeElement));
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});
 try{
  for(const [width,height,theme] of [[390,844,'light'],[1280,900,'dark']]){
   const {child,url,path:root}=await fixture();let page;
   try{
    page=await browser.newPage({viewport:{width,height},colorScheme:theme});
    const errors=[],writes=[];page.on('pageerror',e=>errors.push(e.message));
    page.on('request',r=>{if(r.method()==='POST')writes.push(new URL(r.url()).pathname);});
    await page.addInitScript(root=>history.replaceState({screen:'run',path:root},''),root);
    await page.goto(url);
    const opener=page.getByRole('button',{name:'Change settings',exact:true}).last();
    await opener.waitFor();await opener.click();
    const sheet=page.locator('#sheet'),form=sheet.locator('form.create-flow');
    await form.waitFor();assert.ok(await inside(page),'Focus starts inside the sheet');
    assert.ok(await page.locator('.spending-status').evaluateAll(nodes=>nodes.length>0&&nodes.every(node=>node.inert)), 'Spending controls behind the sheet are inert');
    const background=await page.evaluate(()=>scrollY);
    const box=await form.boundingBox();await page.mouse.move(box.x+box.width/2,box.y+box.height/2);
    await page.mouse.wheel(0,450);
    await page.waitForFunction(()=>document.querySelector('#sheet form').scrollTop>0,null,{timeout:3000});
    assert.equal(await page.evaluate(()=>scrollY),background);
    await page.mouse.move(width-2,height/2);await page.mouse.wheel(0,600);
    await page.waitForTimeout(200);
    assert.equal(await page.evaluate(()=>scrollY),background,'Backdrop cannot scroll the page');
    await page.mouse.move(box.x+box.width/2,box.y+box.height/2);await page.mouse.wheel(0,10000);
    await page.waitForFunction(()=>{const f=document.querySelector('#sheet form');return f.scrollTop+f.clientHeight>=f.scrollHeight-2;});
    const cancel=sheet.getByRole('button',{name:'Cancel',exact:true});
    const end=await cancel.boundingBox();assert.ok(end.y>=0&&end.y+end.height<=height,'Cancel is in the viewport');
    const review=await sheet.getByRole('button',{name:'Review the change',exact:true}).boundingBox();
    assert.ok(review.y>=0&&review.y+review.height<=height,'Review is in the viewport');
    await cancel.focus();await page.keyboard.press('Tab');assert.ok(await inside(page));
    await page.keyboard.press('Shift+Tab');assert.ok(await inside(page));
    if(process.env.TRAINING_SETTINGS_UI_RESULTS){fs.mkdirSync(process.env.TRAINING_SETTINGS_UI_RESULTS,{recursive:true});await page.screenshot({path:path.join(process.env.TRAINING_SETTINGS_UI_RESULTS,`settings-${width}.png`)});}
    await page.keyboard.press('Escape');await sheet.waitFor({state:'hidden'});
    assert.equal(await page.evaluate(()=>document.activeElement.textContent.trim()),'Change settings');
    assert.notEqual(await page.evaluate(()=>getComputedStyle(document.body).overflow),'hidden');
    assert.ok(await page.locator('.spending-status').evaluateAll(nodes=>nodes.every(node=>!node.inert)), 'Closing restores spending controls');
    await opener.click();await form.waitFor();assert.ok(await inside(page));
    assert.equal(await form.evaluate(e=>e.scrollTop),0,'Reopening starts at the first setting');
    await sheet.getByRole('button',{name:'Cancel',exact:true}).click();await sheet.waitFor({state:'hidden'});
    assert.ok(writes.every(route=>route==='/api/training-settings/sources'),'No settings save or job: '+writes.join(','));
    assert.deepEqual(errors,[]);
   }finally{if(page)await page.close();await stop(child);}
  }
  console.log('PASS Training Studio Change settings: desktop/phone scrolling, reachable actions, background lock, focus containment/return, reopen and no save/job');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
