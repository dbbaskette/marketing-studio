/* Shared controls on real opaque surfaces, including the liquid pilot. */
const {chromium}=require('playwright'),assert=require('node:assert/strict'),fs=require('node:fs');
function luminance(color){const values=color.match(/[\d.]+/g).slice(0,3).map(Number).map(n=>{n/=255;return n<=.04045?n/12.92:((n+.055)/1.055)**2.4;});return values[0]*.2126+values[1]*.7152+values[2]*.0722;}
function contrast(a,b){const x=luminance(a),y=luminance(b);return (Math.max(x,y)+.05)/(Math.min(x,y)+.05);}
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.INFOGRAPHIC_STUDIO_TEST_RENDERER});try{
 const page=await browser.newPage();
 await page.setContent('<main class="page"><section class="card"><h1>Review material</h1><button class="button button-filled">Mark ready</button> <button class="button button-quiet">Edit slide</button> <button class="button button-quiet" disabled>History</button></section></main>');
 await page.addStyleTag({content:fs.readFileSync('ui-kit/style.css','utf8')});
 for(const width of [390,1280])for(const colorScheme of ['light','dark'])for(const pilot of ['', 'liquid']){
  await page.setViewportSize({width,height:844});await page.emulateMedia({colorScheme,reducedMotion:'reduce'});await page.evaluate(p=>document.body.dataset.pilot=p,pilot);
  const button=page.getByRole('button',{name:'Edit slide',exact:true});await button.focus();
  const colors=await button.evaluate(n=>{const s=getComputedStyle(n),card=getComputedStyle(n.closest('.card'));return {fill:s.backgroundColor,ink:s.color,line:s.borderTopColor,surface:card.backgroundColor,height:n.getBoundingClientRect().height,focus:s.outlineStyle};});
  assert(!colors.fill.startsWith('rgba'),'Secondary action has opaque fill');
  assert.notEqual(colors.fill,colors.surface);
  assert(contrast(colors.ink,colors.fill)>=4.5,'Readable button label');
  assert(contrast(colors.line,colors.fill)>=3,'Visible inner control edge');
  assert(contrast(colors.line,colors.surface)>=3,'Visible boundary on reading surface');
  assert(colors.height>=44);assert.notEqual(colors.focus,'none');
  assert(await page.getByRole('button',{name:'History',exact:true}).isDisabled());
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  if(process.env.VISIBILITY_RESULTS){fs.mkdirSync(process.env.VISIBILITY_RESULTS,{recursive:true});await page.screenshot({path:`${process.env.VISIBILITY_RESULTS}/controls-${width}-${colorScheme}-${pilot||'standard'}.png`});}
 }
 await page.emulateMedia({forcedColors:'active'});
 assert.equal(await page.getByRole('button',{name:'Edit slide',exact:true}).evaluate(n=>getComputedStyle(n).borderTopStyle),'solid');
 console.log('PASS shared controls: opaque secondary fills, 3:1 boundaries, 4.5:1 labels, focus, disabled state, 44px targets, phone/desktop, light/dark, standard/pilot and forced colors');
}finally{await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});
