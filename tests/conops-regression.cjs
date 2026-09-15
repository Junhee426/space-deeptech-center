const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const path=require('node:path');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})});
 try{
 const page=await browser.newPage({viewport:{width:1600,height:1100}}),errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 await page.goto(process.env.APP_URL||'http://127.0.0.1:8765/');
 await page.waitForFunction(()=>document.querySelector('#missionStatus').dataset.state==='ready');
 const edit=(id,value)=>page.evaluate(({id,value})=>{const el=document.getElementById(id);el.value=value;el.dispatchEvent(new Event('input',{bubbles:true}));},{id,value});
 const shot=async name=>{if(process.env.REVIEW_OUTPUT){fs.mkdirSync(process.env.REVIEW_OUTPUT,{recursive:true});await page.locator('.conops-panel').screenshot({path:path.join(process.env.REVIEW_OUTPUT,`${name}.png`)});}};
 await shot('overview');
 assert.equal(await page.locator('.conops-beam').count(),8);
 await edit('g_beams','1');assert.equal(await page.locator('.conops-beam').count(),1);
 await edit('g_beams','64');assert.equal(await page.locator('.conops-beam').count(),12);
 assert.match(await page.locator('#conopsTitle').textContent(),/64 beams/);
 await edit('g_beams','8');
 const beamBefore=await page.locator('.conops-beam ellipse').first().getAttribute('rx');
 await edit('s_el','50');assert.notEqual(await page.locator('.conops-beam ellipse').first().getAttribute('rx'),beamBefore);
 const satelliteBefore=await page.locator('#conopsSatellite').evaluate(el=>el.parentElement.getAttribute('transform'));
 await edit('g_alt','500');assert.notEqual(await page.locator('#conopsSatellite').evaluate(el=>el.parentElement.getAttribute('transform')),satelliteBefore);
 await edit('cv_planes','3');await edit('cv_spp','5');assert.equal(await page.locator('.conops-fleet-sat').count(),12);
 await edit('cv_f','0');const fleetBefore=await page.locator('.conops-fleet-sat').first().getAttribute('transform');await edit('cv_f','1');assert.notEqual(await page.locator('.conops-fleet-sat').first().getAttribute('transform'),fleetBefore);
 await edit('p_isl','.4');assert.match(await page.locator('#conopsISL').textContent(),/40%/);
 await page.click('[data-conops-toggle="links"]');assert.equal(await page.locator('#conopsISL').evaluate(el=>getComputedStyle(el).display),'none');
 await page.click('[data-conops-toggle="links"]');
 await page.click('[data-conops-view="payload"]');assert.equal(await page.locator('#conopsDiagram svg').getAttribute('data-view'),'payload');
 await edit('p_arch','Bent-Pipe');assert.match(await page.locator('#conopsDiagram').textContent(),/RF relay/);assert.doesNotMatch(await page.locator('#conopsDiagram').textContent(),/ADC \/ Channelizer/);
 await edit('p_arch','Regenerative');await edit('p_stack','PHY');assert.match(await page.locator('#conopsDiagram').textContent(),/ADC \/ Channelizer/);assert.match(await page.locator('#conopsTitle').textContent(),/PHY/);
 const dishBefore=await page.locator('#conopsSatellite ellipse').getAttribute('rx');await edit('s_dia','1');assert.notEqual(await page.locator('#conopsSatellite ellipse').getAttribute('rx'),dishBefore);
 await page.evaluate(()=>runIntegrated());await shot('payload');
 await page.click('[data-conops-view="coverage"]');assert.equal(await page.locator('#conopsEnvelope').count(),1);await shot('coverage');
 await page.click('[data-conops-toggle="motion"]');assert.equal(await page.locator('.conops-flow').first().evaluate(el=>getComputedStyle(el).animationName),'conops-flow');
 await page.emulateMedia({reducedMotion:'reduce'});assert.equal(await page.locator('.conops-flow').first().evaluate(el=>getComputedStyle(el).animationName),'none');
 await page.click('[data-conops-toggle="labels"]');assert.equal(await page.locator('.conops-label').first().evaluate(el=>getComputedStyle(el).display),'none');
 await page.click('[data-conops-toggle="labels"]');
 for(const id of ['g_alt','s_dia','cv_inc']){const prev=await page.locator('#'+id).inputValue();await edit(id,'');assert.equal(await page.locator('#conopsDiagram svg').count(),0);await edit(id,prev);assert.equal(await page.locator('#conopsDiagram svg').count(),1);}
 for(const width of [1440,1024,390]){
  await page.setViewportSize({width,height:1000});
  for(const mode of ['overview','payload','coverage']){
   await page.click(`[data-conops-view="${mode}"]`);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),`${mode}: overflow at ${width}`);
   assert.equal(await page.locator(`[data-conops-view="${mode}"]`).getAttribute('aria-pressed'),'true');
   const markup=await page.locator('#conopsDiagram svg').innerHTML();assert.doesNotMatch(markup,/NaN|undefined|Infinity/);
  }
 }
 await shot('mobile');assert.deepEqual(errors,[]);
 console.log('CONOPS passed: 3 views x 3 widths, beam limits, altitude, elevation, Walker phasing, ISL, architecture, dish size, layers, animation, reduced motion, invalid input.');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
