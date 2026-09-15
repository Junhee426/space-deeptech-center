// Run against a local uvicorn server. See tests/README.md.
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
(async()=>{
 const browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{})});
 try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('console',message=>{if(message.type()==='warning'&&message.text().startsWith('Chart could not be drawn:'))errors.push(message.text());});
 const out=process.env.REVIEW_OUTPUT;
 if(out)fs.mkdirSync(out,{recursive:true});
 await page.goto(process.env.APP_URL||'http://127.0.0.1:8765/');
 await page.waitForFunction(()=>!document.getElementById('syncBtn').disabled&&document.getElementById('c_capacity').textContent!=='—');
 const views=await page.locator('.nav-item').evaluateAll(es=>es.map(e=>e.dataset.view));
 const sizes=[];
 for(const width of [1440,1024,390]){
  await page.setViewportSize({width,height:1000});
  for(const view of views){
   await page.evaluate(v=>show(v),view);await page.waitForTimeout(220);
   await page.waitForFunction(()=>[...chartStates].filter(([id])=>document.getElementById(id).closest('.view.active')).every(([id,state])=>!state.running&&!state.dirty&&document.getElementById(id).classList.contains('js-plotly-plot')));
   const actual=await page.evaluate(()=>document.documentElement.scrollWidth);
   sizes.push({width,view,actual});assert(actual<=width+1,`${view}: ${actual}px overflows ${width}px viewport`);
   if(view!=='center'&&view!=='theory'){
    const box=await page.locator(`#${view} .run-lab`).boundingBox();
    assert(box.x>=0&&box.x+box.width<=width+1,`${view}: run button outside viewport`);
   }
   if(out&&['center','payload','constellation'].includes(view))await page.screenshot({path:path.join(out,`${width}-${view}.png`),fullPage:true});
  }
 }
 async function edit(id,value){await page.evaluate(({id,value})=>{const el=document.getElementById(id);if(el.type==='checkbox')el.checked=value;else el.value=value;el.dispatchEvent(new Event('input',{bubbles:true}));el.dispatchEvent(new Event('change',{bubbles:true}));},{id,value});}
 await page.evaluate(()=>show('center'));
 await edit('cv_alt','888');await edit('cv_planes','4');await edit('cv_spp','6');await edit('cv_inc','55');await edit('cv_f','2');await edit('p_geo_el','15');
 const geometry=await page.evaluate(()=>({coverage:coverageObj(),payload:payloadObj(),timeline:timelineObj(),sat:satObj()}));
 for(const obj of [geometry.coverage,geometry.timeline,geometry.sat])assert.equal(obj.altitude_km,888);
 for(const obj of [geometry.coverage,geometry.timeline]){assert.equal(obj.planes,4);assert.equal(obj.sats_per_plane,6);assert.equal(obj.inclination_deg,55);assert.equal(obj.walker_f,2);assert.equal(obj.min_elevation_deg,15);}
 assert.equal(geometry.payload.geometry_altitude_km,888);assert.equal(geometry.payload.geometry_planes,4);assert.equal(geometry.payload.geometry_sats_per_plane,6);assert.equal(geometry.payload.geometry_inclination_deg,55);assert.equal(geometry.payload.geometry_walker_f,2);assert.equal(geometry.payload.geometry_min_elevation_deg,15);
 assert.match(await page.locator('#conopsCaption').textContent(),/24 sats/);
 await edit('p_stack','PHY');assert.match(await page.locator('#conopsTitle').textContent(),/Regenerative · PHY/);
 await edit('b_arch','Hybrid');assert.match(await page.locator('#conopsDiagram').textContent(),/Hybrid/);
 await edit('p_isl','.25');assert.equal(await page.locator('#conopsISL').count(),1);
 await edit('p_isl','0');assert.equal(await page.locator('#conopsISL').count(),0);
 await edit('g_alt','');assert.equal(await page.locator('#conopsDiagram svg').count(),0);await edit('g_alt','888');
 assert.equal(await page.locator('#missionStatus').getAttribute('data-state'),'stale');
 await page.evaluate(()=>runIntegrated());assert.equal(await page.locator('#missionStatus').getAttribute('data-state'),'ready');
 const originalSizes=await page.locator('#conopsSolar').getAttribute('width');
 await edit('s_rf','80');await page.evaluate(()=>runIntegrated());
 assert.notEqual(await page.locator('#conopsSolar').getAttribute('width'),originalSizes);
 assert.match(await page.locator('#conopsDetails').textContent(),/방열판 면적/);
 const warningsBefore=await page.locator('#s_warn').textContent();
 for(let n=0;n<4;n++)await page.evaluate(()=>{show('satcom');show('center')});
 assert.equal(await page.locator('#s_warn').textContent(),warningsBefore);
 // A response for inputs changed while the request was pending must never replace current results.
 let release;const gate=new Promise(resolve=>release=resolve);let received;const started=new Promise(resolve=>received=resolve);
 await page.route('**/api/integrated',async route=>{const response=await route.fetch();received();await gate;await route.fulfill({response});});
 const pending=page.evaluate(()=>runIntegrated());await started;await edit('g_alt','500');release();await pending;
 assert.equal(await page.locator('#missionStatus').getAttribute('data-state'),'stale');
 await page.unroute('**/api/integrated');
 // Show validation failures and retain last good KPI values.
 const capacity=await page.locator('#c_capacity').textContent();
 await page.route('**/api/integrated',route=>route.fulfill({status:422,contentType:'application/json',body:JSON.stringify({detail:'검증용 입력 오류'})}));
 await page.evaluate(()=>show('payload'));await page.click('#p_run');await page.waitForFunction(()=>!document.getElementById('p_run').disabled);
 assert.equal(await page.locator('#missionStatus').getAttribute('data-state'),'error');
 assert.match(await page.locator('#missionStatus').textContent(),/검증용 입력 오류/);assert.match(await page.locator('#payload .action-error').textContent(),/검증용 입력 오류/);assert.equal(await page.locator('#c_capacity').textContent(),capacity);
 await page.unroute('**/api/integrated');
 await page.evaluate(()=>saveScenario());await page.reload();await page.waitForFunction(()=>!document.getElementById('syncBtn').disabled);
 assert.equal(await page.locator('#g_alt').inputValue(),'500');assert.equal(await page.locator('#cv_alt').inputValue(),'500');assert.equal(await page.locator('#cv_inc').inputValue(),'55');assert.equal(await page.locator('#p_stack').inputValue(),'PHY');
 await page.setViewportSize({width:1440,height:1000});await page.evaluate(()=>show('optimizer'));await page.click('#o_run');await page.waitForFunction(()=>!document.getElementById('o_run').disabled,{timeout:60000});assert((await page.locator('#o_summary').textContent()).length>10);
 // The optimizer table, objective label and report summary must all reflect the
 // SAME request-time input snapshot, and a response for now-stale inputs must be
 // discarded entirely (matching runIntegrated's established convention above)
 // rather than rendered -- whether with its own request-time value or with a
 // live-DOM value read after the fact.
 await edit('o_obj','Highest Capacity');await page.evaluate(()=>runOptimizer());
 const optBaseline=await page.locator('#o_objlabel').textContent();assert.equal(optBaseline,'Highest Capacity');
 {
  await edit('o_obj','Balanced');
  let release;const gate=new Promise(resolve=>release=resolve);let received;const started=new Promise(resolve=>received=resolve);
  await page.route('**/api/optimize',async route=>{const response=await route.fetch();received();await gate;await route.fulfill({response});});
  const pending=page.evaluate(()=>runOptimizer());await started; // captures objective=Balanced
  await edit('o_obj','Lowest Cost'); // live input changes again while the Balanced run is in flight
  release();await pending;
  assert.equal(await page.locator('#o_objlabel').textContent(),optBaseline,'a response for now-stale inputs must be discarded, leaving the last valid render untouched');
  await page.unroute('**/api/optimize');
 }
 {
  // A stale (slower, earlier) response must not clobber a fresher run's results
  // even if it resolves after the fresher one.
  let releaseFirst;const gateFirst=new Promise(resolve=>releaseFirst=resolve);
  let firstReceived;const firstStarted=new Promise(resolve=>firstReceived=resolve);
  let secondSeen=false;
  await page.route('**/api/optimize',async route=>{
   if(!secondSeen){secondSeen=true;firstReceived();await gateFirst;}
   await route.continue();
  });
  const firstRun=page.evaluate(()=>runOptimizer());await firstStarted; // objective=Lowest Cost (current DOM)
  await edit('o_obj','Highest Capacity');
  const secondRun=page.evaluate(()=>runOptimizer());await secondRun; // second (newer) request resolves first
  assert.equal(await page.locator('#o_objlabel').textContent(),'Highest Capacity');
  releaseFirst();await firstRun; // stale first request resolves after -- must be discarded
  assert.equal(await page.locator('#o_objlabel').textContent(),'Highest Capacity','a late-arriving stale response must not overwrite the newer run\'s rendered result');
  await page.unroute('**/api/optimize');
 }
 assert.deepEqual(errors,[]);
 console.log(JSON.stringify({checks:'30 viewport checks, shared geometry, SVG structure and sizing, stale response, API failure, persistence, optimizer, optimizer stale-response discard',sizes,errors},null,2));
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1});
