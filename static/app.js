const $=id=>document.getElementById(id), num=id=>parseFloat($(id).value);
function debounce(fn,ms=180){let t;return(...a)=>{clearTimeout(t);t=setTimeout(()=>fn(...a),ms)}}
const KASA={navy:"#012B49",red:"#F94239",silver:"#A7ADB3",gold:"#B39A67"};
const layout={
 paper_bgcolor:"rgba(0,0,0,0)",
 plot_bgcolor:"rgba(0,0,0,0)",
 font:{color:"#dce8ee",size:10},
 margin:{l:48,r:24,t:34,b:44},
 xaxis:{gridcolor:"rgba(130,170,195,.14)",zerolinecolor:"rgba(255,255,255,.10)"},
 yaxis:{gridcolor:"rgba(130,170,195,.14)",zerolinecolor:"rgba(255,255,255,.10)"}
};
const cfg={displayModeBar:false,responsive:true};
let lastIntegrated=null,lastIntegratedInput=null;
// Cache hidden charts and draw them only after their tab has a measurable width.
const chartStates=new Map();
function reactChart(id,traces,layoutObj,cfgObj){
 const state=chartStates.get(id)||{running:false};
 Object.assign(state,{traces:structuredClone(traces),layout:structuredClone(layoutObj),config:cfgObj,dirty:true});
 chartStates.set(id,state);
 drawChart(id);
}
async function drawChart(id){
 const el=$(id),state=chartStates.get(id);
 if(!el||!state||state.running||!state.dirty||!el.closest('.view.active')||el.clientWidth<1)return;
 state.running=true;state.dirty=false;
 try{
  el.classList.remove('chart-empty');
  await Plotly.react(el,structuredClone(state.traces),{...structuredClone(state.layout),autosize:true,width:el.clientWidth},state.config);
 }catch(error){
  console.warn('Chart could not be drawn: '+id,error);
  if(el.closest('.view.active'))el.setAttribute('aria-label','차트를 표시하지 못했습니다. 다시 실행해 주세요.');
  else state.dirty=true;
 }finally{state.running=false;if(state.dirty&&el.closest('.view.active'))requestAnimationFrame(()=>drawChart(id));}
}
function refreshVisibleCharts(){
 for(const [id,state] of chartStates){if($(id).closest('.view.active')){state.dirty=true;drawChart(id);}}
}
window.addEventListener('resize',debounce(refreshVisibleCharts,150));
let lastDesignKey=null,lastCalculatedAt=null,integratedRequest=0;
function designKey(){return JSON.stringify(integratedObj());}
function setMissionStatus(kind,message){
 $('missionStatus').dataset.state=kind;
 $('missionStatus').textContent=message+(lastCalculatedAt?' · 마지막 통합 계산 '+lastCalculatedAt:'');
}
function reportError(error){
 console.warn(error);
 setMissionStatus('error','계산 실패: '+error.message+' 기존 결과를 유지합니다. 입력값을 확인하고 다시 실행해 주세요.');
 trace('계산 실패 — 현재 입력은 결과에 반영되지 않았습니다.');
}
function constellationObj(){
 return {altitude_km:num('g_alt'),min_elevation_deg:num('s_el'),inclination_deg:num('cv_inc'),
  planes:num('cv_planes'),sats_per_plane:num('cv_spp'),walker_f:num('cv_f')};
}
const sharedFields=[['g_alt','cv_alt'],['s_el','cv_el','p_geo_el'],['s_rf','p_geo_tx'],['s_tops','b_tops']];
function syncSharedField(id){
 for(const group of sharedFields){if(group.includes(id))group.forEach(peer=>$(peer).value=$(id).value);}
}

async function post(url,obj){
 const r=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(obj)});
 if(!r.ok){
  let detail='HTTP '+r.status;
  try{const body=await r.json();detail=Array.isArray(body.detail)?body.detail.map(x=>x.loc.join('.')+': '+x.msg).join('; '):(body.detail||detail);}catch{}
  throw Error(detail);
 }
 return r.json();
}
// Wraps a button's click handler so a slow request (Monte Carlo, Optimizer, ...) shows a
// spinner and can't be double-submitted, instead of leaving the user staring at a static button.
function withLoading(btn,fn){
 return async(...args)=>{
  if(btn.classList.contains("is-loading")) return;
  btn.classList.add("is-loading"); btn.disabled=true; btn.setAttribute("aria-busy","true");
  const previousError=btn.parentElement.querySelector('.action-error');
  if(previousError)previousError.remove();
  try{ return await fn(...args) }
  catch(e){
   reportError(e);
   const message=document.createElement('p');message.className='action-error';message.setAttribute('role','alert');
   message.textContent='계산 실패: '+e.message+' 입력을 확인하고 다시 실행해 주세요.';
   btn.insertAdjacentElement('afterend',message);
  }
  finally{ btn.classList.remove("is-loading"); btn.disabled=false; btn.removeAttribute("aria-busy") }
 }
}
function warnings(id,arr){$(id).innerHTML=(arr||[]).map(x=>"• "+x).join("<br>")}
function trace(t){$("traceText").textContent=t}
function show(v){
 document.querySelectorAll(".view").forEach(x=>x.classList.remove("active")); $(v).classList.add("active");
 document.querySelectorAll(".nav-item").forEach(x=>x.classList.toggle("active",x.dataset.view===v));
 window.scrollTo({top:0,behavior:"smooth"});
 requestAnimationFrame(refreshVisibleCharts);
 if(v==='center')renderConops();
}
document.querySelectorAll(".nav-item").forEach(b=>b.onclick=()=>show(b.dataset.view));

function syncGlobalToLabs(){
 trace(`Mission inputs: ${$("g_alt").value} km · ${$("g_freq").value} GHz · ${$("g_bw").value} MHz · ${$("g_elem").value} elements · ${$("g_beams").value} beams`);
}

function satObj(){
 return {
 material:$("s_material").value,part_pa:$("s_pa").value,part_lna:$("s_lna").value,
 altitude_km:num("g_alt"),min_elevation_deg:num("s_el"),frequency_ghz:num("g_freq"),bandwidth_mhz:num("g_bw"),
 rf_output_w:num("s_rf"),tx_gain_dbi:num("s_tx"),rx_gain_dbi:num("s_rx"),losses_db:num("s_loss"),antenna_temp_k:290,
 bus_power_w:num("s_bus"),payload_share:num("s_pshare")/100,antenna_diameter_m:num("s_dia"),antenna_efficiency:.62,
 structure_mass_kg:180,base_payload_mass_kg:75,base_cost_musd:12,radiator_w_m2:350,mission_years:5,
 array_elements:parseInt($("g_elem").value),beams:parseInt($("g_beams").value),processor:"FPGA",processor_tops:num("s_tops"),
 coding_gap_db:num("s_gap"),max_spectral_eff:6,atmospheric_loss_db:num("s_atm"),
 radiator_temp_k:num("s_rtemp"),radiator_emissivity:num("s_eps"),radiator_view_factor:.80
 }}
function beamObj(){
 return {elements:parseInt($("g_elem").value),beams:parseInt($("g_beams").value),bandwidth_mhz:num("g_bw"),
 sample_gsps:num("b_gsps"),bits:parseInt($("b_bits").value),architecture:$("b_arch").value,processor:$("b_proc").value,
 available_tops:num("b_tops"),available_power_w:num("b_power"),phase_bits:parseInt($("b_phase").value),amplitude_bits:6,
 calibration_error_deg:num("b_cal"),element_spacing_lambda:num("b_space"),max_scan_deg:num("b_scan")}
}
function radObj(){
 return {mission_years:num("r_year"),shielding_mm_al:num("r_shield"),tid_env_krad_yr:num("r_tid"),tid_tolerance_krad:num("r_tidt"),
 dd_env_arb_yr:num("r_dd"),dd_tolerance_arb:num("r_ddt"),seu_rate_device_day:num("r_seu"),sel_rate_device_day:num("r_sel"),
 sensitive_devices:parseInt($("r_dev").value),mitigation:$("r_mit").value,scrub_interval_min:num("r_scrub"),spares:parseInt($("r_spares").value),
 reset_recovery_sec:5,service_nodes:parseInt($("r_nodes").value)}
}
function payloadObj(){
 return {architecture:$("p_arch").value,frequency_ghz:num("g_freq"),bandwidth_mhz:num("g_bw"),input_power_dbw:num("p_in"),
 antenna_gain_rx_dbi:35,antenna_gain_tx_dbi:35,lna_gain_db:num("p_lg"),lna_nf_db:num("p_nf"),filter_loss_db:num("p_fl"),
 mixer_loss_db:num("p_ml"),channelizer_loss_db:num("p_cl"),switch_loss_db:num("p_sl"),pa_gain_db:num("p_pg"),pa_output_w:num("s_rf"),
 pa_efficiency:.46,channels:parseInt($("p_ch").value),beams:parseInt($("g_beams").value),processor_power_w:120,converter_power_w:55,
 other_power_w:90,dry_mass_kg:65,thermal_margin_pct:20,radiator_temp_k:num("s_rtemp"),radiator_emissivity:num("s_eps"),radiator_view_factor:.80,
 papr_db:num("p_papr"),output_backoff_db:num("p_obo"),hpa_model:"Rapp",rapp_p:num("p_rapp"),dpd_enabled:$("p_dpd").checked,dpd_gain_db:2,
 frequency_reuse:parseInt($("p_reuse").value),beam_hopping_duty:num("p_bhduty"),traffic_hotspot_factor:num("p_hotspot"),
 precoding_enabled:$("p_prec").checked,precoding_efficiency:.8,channelizer_granularity_mhz:num("p_gran"),
 routing_matrix_inputs:parseInt($("p_mi").value),routing_matrix_outputs:parseInt($("p_mo").value),
 regenerative_stack:$("p_stack").value,isl_offload_fraction:num("p_isl"),
 users:parseInt($("p_users").value),user_noise_dbm:num("p_noise"),desired_signal_dbm:num("p_sig"),
 cochannel_coupling_db:num("p_cpl"),precoding_method:$("p_prec_method").value,rzf_lambda:num("p_lambda"),
 traffic_pattern:$("p_traffic").value,scheduler:$("p_sched").value,timeslots:parseInt($("p_slots").value),
 hpa_samples:parseInt($("p_samples").value),modulation_order:parseInt($("p_qam").value),aclr_guard_fraction:.15,
 geometry_channel_enabled:$("p_geo").checked,geometry_region:$("p_geo_region").value,geometry_time_min:num("p_geo_time"),
 geometry_user_radius_km:num("p_geo_radius"),geometry_satellite_count:1,geometry_inclination_deg:constellationObj().inclination_deg,
 geometry_planes:constellationObj().planes,geometry_sats_per_plane:constellationObj().sats_per_plane,geometry_walker_f:constellationObj().walker_f,geometry_altitude_km:constellationObj().altitude_km,
 geometry_min_elevation_deg:num("p_geo_el"),geometry_terminal_gain_dbi:num("p_geo_gr"),
 geometry_beam_hpbw_deg:num("p_geo_hpbw"),geometry_atmospheric_loss_db:num("p_geo_loss"),
 geometry_total_tx_power_w:num("p_geo_tx"),analysis_mode:"Full"}
}
function renderPayload(d){
 $("p_out").textContent=d.rf.output_dbw+" dBW"; $("p_total").textContent=d.power.total_w+" W"; $("p_heat").textContent=d.power.heat_w+" W";
 $("p_rad").textContent=d.power.radiator_m2+" m²"; $("p_mass").textContent=d.system.mass_kg+" kg"; $("p_service").textContent=d.system.service_index;
 $("p_comp").textContent=d.rf.hpa_effective_compression_db+" dB"; $("p_lin").textContent=d.rf.hpa_linearity_score+" /100";
 $("p_avgrf").textContent=d.rf.average_rf_w+" W"; $("p_bins").textContent=d.digital.channelizer_bins_proxy;
 $("p_bhgain").textContent=d.resource.normalized_resource_gain+"×"; $("p_feeder").textContent=(d.resource.feeder_load_fraction*100).toFixed(0)+" %";
 reactChart("p_chain",[{type:"scatter",mode:"lines+markers",x:d.chain.map(x=>x.stage),y:d.chain.map(x=>x.level_dbw)}],{...layout,title:"RF Signal Level [dBW]"},cfg);
 reactChart("p_archchart",[{type:"bar",x:["Flexibility","Complexity"],y:[d.system.flexibility_score,d.system.complexity_score]}],{...layout,title:lastIntegratedInput?.payload.architecture||payloadObj().architecture,yaxis:{range:[0,100]}},cfg);
 reactChart("p_powerstack",[{type:"bar",x:["PA DC","Regen","Converters","Channelizer","Routing"],y:[d.power.pa_dc_w,d.digital.regenerative_power_w,d.digital.converter_power_w,d.digital.channelizer_power_w,d.digital.routing_power_w]}],{...layout,title:"Payload Power Stack [W]"},cfg);
 reactChart("p_flex",[{type:"bar",x:["Resource gain","Interference eff.","Demand match","Coverage duty"],y:[d.resource.normalized_resource_gain,d.resource.interference_efficiency,d.resource.demand_match_gain,d.resource.coverage_duty_pct/100]}],{...layout,title:"Flexible Payload Indicators"},cfg);

 $("p_sinr").textContent=d.resource.mean_sinr_db+" dB"; $("p_p5sinr").textContent=d.resource.p5_sinr_db+" dB";
 $("p_evm").textContent=d.waveform.evm_pct+" %"; $("p_aclr").textContent=d.waveform.aclr_proxy_db+" dB";
 $("p_schedkpi").textContent=d.traffic.scheduler; $("p_preckpi").textContent=d.resource.precoding_enabled?d.resource.precoding_method:"MRT";
 reactChart("p_sinrchart",[{type:"bar",x:d.interference.sinr.map(x=>"U"+x.user),y:d.interference.sinr.map(x=>x.sinr_db)}],{...layout,title:"Per-user SINR [dB]"},cfg);
 reactChart("p_trafficmap",[{type:"bar",x:d.traffic.user_share.map((_,i)=>"U"+(i+1)),y:d.traffic.user_share}],{...layout,title:"User traffic share"},cfg);
 reactChart("p_precoder",[{type:"heatmap",z:d.interference.precoder_power_matrix}],{...layout,title:"|W|² precoder matrix"},cfg);
 reactChart("p_schedule",[
 {type:"heatmap",z:d.traffic.schedule,name:"Active beams"},
 {type:"scatter",mode:"lines+markers",x:d.traffic.slot_mean_sinr_db.map((_,i)=>i),y:d.traffic.slot_mean_sinr_db,yaxis:"y2",name:"Slot mean SINR"}
],{...layout,title:`Beam hopping · OFDM PAPR ${d.waveform.actual_papr_db} dB`,xaxis:{title:"Time slot"},yaxis:{title:"Beam activity"},yaxis2:{title:"SINR dB",overlaying:"y",side:"right"}},cfg);

 $("p_chsource").textContent=d.geometry.channel_source.includes("Walker")?"Walker":"Synthetic";
 $("p_schedcap").textContent=d.traffic.aggregate_scheduled_gbps+" Gbps";
 $("p_servsat").textContent=d.geometry.satellite_indices.length?d.geometry.satellite_indices[0]:"—";
 const validElev=d.geometry.user_elevation_deg.filter(v=>v>-89);
 $("p_minelev").textContent=validElev.length?Math.min(...validElev).toFixed(1)+"°":"—";
 const validRange=d.geometry.user_range_km.filter(v=>v!==null);
 $("p_maxrange").textContent=validRange.length?Math.max(...validRange).toFixed(0)+" km":"—";
 reactChart("p_userthroughput",[{type:"bar",x:d.traffic.user_throughput_mbps.map((_,i)=>"U"+(i+1)),y:d.traffic.user_throughput_mbps}],{...layout,title:"Scheduled User Throughput [Mbps]"},cfg);
 const ux=d.geometry.users.map(x=>x.lon), uy=d.geometry.users.map(x=>x.lat);
 const bx=d.geometry.beam_centers.map(x=>x.lon), by=d.geometry.beam_centers.map(x=>x.lat);
 reactChart("p_geomap",[
   {type:"scatter",mode:"markers+text",name:"Users",x:ux,y:uy,text:ux.map((_,i)=>"U"+(i+1)),textposition:"top center"},
   {type:"scatter",mode:"markers",name:"Beam centers",x:bx,y:by,marker:{size:13,symbol:"x",color:KASA.red}}
 ],{...layout,title:`Geometry channel · ${d.geometry.region}`,xaxis:{title:"Longitude °"},yaxis:{title:"Latitude °"}},cfg);
 warnings("p_warn",d.warnings);
}
function renderRad(d){
 $("r_mtid").textContent=d.dose.mission_tid_krad+" krad"; $("r_use").textContent=d.dose.tid_usage_pct+" %"; $("r_sday").textContent=d.see.seu_day;
 $("r_msel").textContent=d.see.mission_sel; $("r_av").textContent=d.service.electronics_availability_pct+" %"; $("r_risk").textContent=d.risk.class;
 reactChart("r_dosechart",[{type:"bar",x:["TID use","DD use","Risk"],y:[d.dose.tid_usage_pct,d.dose.dd_usage_pct,d.risk.score_pct]}],{...layout,title:"Radiation Budget [%]"},cfg);
 reactChart("r_service",[{type:"indicator",mode:"gauge+number",value:d.risk.score_pct,title:{text:"System Radiation Risk"},gauge:{axis:{range:[0,100]}}}],{...layout},cfg);
 warnings("r_warn",d.warnings);
}

function renderSat(d){
 $("s_eff").textContent=d.device.pa_eff_pct+" %"; $("s_padc").textContent=d.device.pa_dc_w+" W";
 $("s_heat").textContent=d.payload.heat_w+" W"; $("s_mass").textContent=d.payload.mass_kg+" kg";
 $("s_snr").textContent=d.link.snr_db+" dB"; $("s_agg").textContent=d.link.aggregate_gbps+" Gbps";
 reactChart("s_powerchart",[{type:"bar",x:["PA DC","Other payload","Total payload"],y:[d.device.pa_dc_w,Math.max(0,d.payload.power_w-d.device.pa_dc_w),d.payload.power_w]}],{...layout,title:"Semiconductor → Payload Power [W]"},cfg);
 warnings("s_warn",d.warnings);
}

function renderBeam(d){
 $("b_req").textContent=d.compute.required_tops+" TOPS"; $("b_margin").textContent=d.compute.margin_x+"×";
 $("b_total").textContent=d.power.total_w+" W"; $("b_pmargin").textContent=d.power.margin_w+" W";
 $("b_effbeams").textContent=d.compute.effective_beams; $("b_grating").textContent=d.quality.grating_lobe_risk;
 reactChart("b_powerchart",[{type:"bar",x:["Converters","Processor","Phase control"],y:[d.power.converter_w,d.power.processor_w,d.power.phase_control_w]}],{...layout,title:"Beamforming Power Breakdown [W]"},cfg);
 reactChart("b_gauge",[{type:"indicator",mode:"gauge+number",value:d.compute.effective_beams,title:{text:"Effective Beams"},gauge:{axis:{range:[0,Math.max(1,parseInt($("g_beams").value))]}}}],{...layout},cfg);
 warnings("b_warn",d.warnings);
}

async function renderOrbit(){
 const input=satObj();
 const rows=await post('/api/satcom/orbit-sweep',input);
 if(JSON.stringify(input)!==JSON.stringify(satObj()))return;
 reactChart("s_orbit",[
  {type:"bar",name:"SNR dB",x:rows.map(r=>r.altitude_km+" km"),y:rows.map(r=>r.snr_db)},
  {type:"scatter",mode:"lines+markers",name:"Footprint radius km",x:rows.map(r=>r.altitude_km+" km"),y:rows.map(r=>r.footprint_radius_km),yaxis:"y2"}
 ],{...layout,title:"Orbit altitude sweep (500 / 888 / 1280 km)",xaxis:{title:"Altitude"},yaxis:{title:"SNR dB"},yaxis2:{title:"Footprint km",overlaying:"y",side:"right"}},cfg);
}

function integratedObj(){
 return {satcom:satObj(),beam:beamObj(),radiation:radObj(),payload:payloadObj()}
}

function renderCenter(d){
 const i=d.integrated;
 $("c_capacity").textContent=i.effective_capacity_gbps+" Gbps"; $("c_mass").textContent=i.total_mass_kg+" kg";
 $("c_power").textContent=i.payload_power_w+" W"; $("c_avail").textContent=i.availability_pct+" %";
 $("c_cost").textContent="$"+i.total_cost_proxy_musd+"M"; $("c_service").textContent=i.service_index;

 reactChart("centerRadar",[{
  type:"scatterpolar",
  r:[i.scores.Power,i.scores.Mass,i.scores.Capacity,i.scores.Reliability,i.scores.Thermal,i.scores.Power],
  theta:["Power","Mass","Capacity","Reliability","Thermal","Power"],fill:"toself"
 }],{...layout,polar:{bgcolor:"rgba(0,0,0,0)",radialaxis:{range:[0,100],gridcolor:"#1b3b50"}},showlegend:false},cfg);

 reactChart("centerPower",[{
  type:"bar",x:["Semiconductor","Beamforming","RF Payload"],
  y:[d.satcom.payload.power_w,d.beamforming.power.total_w,d.payload.power.total_w]
 }],{...layout,title:"Power by subsystem [W]"},cfg);

 $("bottleneckBoard").innerHTML=i.bottlenecks.map(b=>`<div class="bottleneck"><strong>${b}</strong></div>`).join("");
 $("systemFlow").innerHTML=i.chain.map((c,n)=>`<div class="flow-stage ${c.status.toLowerCase()}"><span class="n">0${n+1}</span><span class="name">${c.stage}</span><span class="metric">${c.metric}</span><span class="status">${c.status}</span></div>`).join("");

 $("impactSemi").textContent=`${d.satcom.device.pa_eff_pct}% eff`;
 $("impactBeam").textContent=`${d.beamforming.compute.effective_beams} beams`;
 $("impactPayload").textContent=`${d.payload.power.total_w} W / ${d.payload.system.mass_kg} kg`;
 $("impactRad").textContent=`${d.radiation.service.electronics_availability_pct} %`;
 $("impactSvc").textContent=`${i.effective_capacity_gbps} Gbps`;
 renderConops();
}

// The diagram previews the shared mission; physical dimensions are relative proxies.
function escapeMarkup(value){return String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
function renderConops(){
 const orbit=constellationObj(),alt=orbit.altitude_km,minEl=orbit.min_elevation_deg;
 const freq=num('g_freq'),bw=num('g_bw'),elements=num('g_elem'),beams=num('g_beams');
 const valid=[alt,freq,bw,elements,beams,orbit.planes,orbit.sats_per_plane].every(v=>Number.isFinite(v)&&v>0)&&
  [elements,beams,orbit.planes,orbit.sats_per_plane,orbit.walker_f].every(Number.isInteger)&&Number.isFinite(minEl)&&minEl>=0&&minEl<90&&Number.isFinite(orbit.inclination_deg);
 if(!valid){
  $('conopsDiagram').textContent='유효한 고도·주파수·빔 수·군집 설정을 입력하면 그림이 표시됩니다.';
  $('conopsCaption').textContent='입력 확인 필요';$('conopsDetails').textContent='';return;
 }
 const current=lastIntegrated&&lastDesignKey===designKey();
 const result=current?lastIntegrated:null;
 const mass=result?.integrated.total_mass_kg,power=result?.payload.power.total_w,radiator=result?.payload.power.radiator_m2;
 const bodySize=result?Math.min(20,Math.max(10,Math.sqrt(mass)*.8)):12;
 const wing=result?Math.min(90,Math.max(25,Math.sqrt(power)*2.2)):36;
 const radiatorSize=result?Math.min(35,Math.max(6,Math.sqrt(radiator)*16)):10;
 const arch=$('p_arch').value,stack=$('p_stack').value,beamArch=$('b_arch').value;
 const archLabel=arch==='Bent-Pipe'?'Bent-Pipe · RF relay':arch+' · '+stack;
 const isl=Math.max(0,Math.min(1,num('p_isl')||0));
 const W=900,H=390,groundY=285,satX=450,satY=175-Math.max(0,Math.min(90,(alt-300)/1700*90));
 const halfWidth=70+Math.max(.15,Math.min(1,(85-minEl)/75))*230;
 const shown=Math.min(beams,7),total=orbit.planes*orbit.sats_per_plane;
 let beamLines='',terminals='';
 for(let n=0;n<shown;n++){
  const x=satX+halfWidth*.82*(shown===1?0:2*n/(shown-1)-1);
  beamLines+=`<path d="M${satX},${satY+bodySize} L${x},${groundY}" stroke="#F94239" stroke-width="1.5" opacity=".65"/>`;
  terminals+=`<path d="M${x-5},${groundY} h10 v-8 h-10 z M${x},${groundY-8} v-8" fill="#12384f" stroke="#7ec8df"/>`;
 }
 $('conopsDiagram').innerHTML=`<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="conopsTitle conopsDesc">
  <title id="conopsTitle">${escapeMarkup(archLabel)}, ${alt} km, ${beams} beams, ${total} satellites</title>
  <desc id="conopsDesc">설계 입력 운용개념도. 실제 축척이 아닙니다. ${current?'위성 크기와 패널은 현재 계산 결과의 상대적 크기입니다.':'전력·열·질량을 계산하면 상대적 크기가 갱신됩니다.'}</desc>
  <path d="M0,${groundY} Q450,320 900,${groundY} V390 H0 Z" fill="#0a2638"/>
  <path d="M0,${groundY} H900" stroke="#315b75"/>
  <path d="M145,${satY+35} Q450,${satY-45} 755,${satY+35}" fill="none" stroke="#4f9fc7" stroke-dasharray="4 6"/>
  <path d="M450,${satY+bodySize} L${450-halfWidth},${groundY} H${450+halfWidth} Z" fill="#7ec8df" opacity=".08"/>
  ${beamLines}${terminals}
  <path d="M85,${groundY-20} L${satX-bodySize},${satY+bodySize}" stroke="#d6b66d" stroke-width="2" stroke-dasharray="4 5"/>
  <g transform="translate(85,${groundY})" stroke="#d6b66d" fill="#12384f"><rect x="-12" y="-18" width="24" height="18"/><circle cy="-24" r="7"/></g>
  <g id="conopsSatellite" transform="translate(${satX},${satY})">
   <rect id="conopsBody" x="${-bodySize}" y="${-bodySize}" width="${bodySize*2}" height="${bodySize*2}" rx="3" fill="#153d56" stroke="#b8e6f3" stroke-width="2"/>
   <g fill="#174a6b" stroke="#7ec8df"><rect id="conopsSolar" x="${-bodySize-wing-5}" y="-8" width="${wing}" height="16"/><rect x="${bodySize+5}" y="-8" width="${wing}" height="16"/></g>
   <rect id="conopsRadiator" x="${bodySize+4}" y="13" width="${radiatorSize}" height="9" fill="#b1c5d0" stroke="#fff"/>
  </g>
  ${isl>0?`<g id="conopsISL"><path d="M${satX+bodySize+wing+8},${satY} L735,${satY-15}" stroke="#9fbdf7" stroke-width="2" stroke-dasharray="6 4"/><rect x="735" y="${satY-22}" width="14" height="14" fill="#174a6b" stroke="#9fbdf7"/><text x="660" y="${satY-30}" fill="#c9d9ff">ISL ${Math.round(isl*100)}%</text></g>`:''}
  <g fill="#dce8ee" font-size="14" font-family="system-ui,sans-serif">
   <text x="20" y="28">ALTITUDE ${alt} km</text>
   <text x="20" y="51">Walker ${orbit.planes} × ${orbit.sats_per_plane} · ${orbit.inclination_deg}° · F ${orbit.walker_f}</text>
   <text x="450" y="${satY-bodySize-15}" text-anchor="middle" fill="#ffa39d">${escapeMarkup(archLabel)}</text>
   <text x="450" y="${satY+bodySize+38}" text-anchor="middle">${escapeMarkup(beamArch)} · ${elements} elements</text>
   <text x="85" y="${groundY+27}" text-anchor="middle" fill="#e7d6a8">GATEWAY</text>
   <text x="148" y="${groundY-65}" fill="#e7d6a8">Feeder ${freq} GHz</text>
   <text x="700" y="${groundY-40}" text-anchor="middle" fill="#ffa39d">${beams} beams · ${shown} shown</text>
   <text x="450" y="${groundY+27}" text-anchor="middle">${minEl}° min elevation · ${bw} MHz</text>
   <text x="450" y="362" text-anchor="middle" fill="#a9c4d4">${current?'계산 결과 반영 · 상대 크기':'입력 미리보기 · 크기는 계산 후 반영'} / Not to scale</text>
  </g>
 </svg>`;
 $('conopsCaption').textContent=`${archLabel} · ${alt} km · 최소 고도각 ${minEl}° · ${beams} beams (${shown}개 표시) · ${orbit.planes}×${orbit.sats_per_plane} Walker (${total} sats) · ${orbit.inclination_deg}° / F ${orbit.walker_f} · ${freq} GHz / ${bw} MHz`;
 const details=current?[['위성 질량',mass+' kg'],['탑재체 전력',power+' W'],['열 부하',result.payload.power.heat_w+' W'],['방열판 면적',radiator+' m²']]:[['설계 상태','입력 미리보기'],['크기 반영','RUN 또는 SYNC 후 갱신']];
 $('conopsDetails').innerHTML=details.map(([label,value])=>`<div><span>${label}</span><b>${escapeMarkup(value)}</b></div>`).join('');
}

async function runIntegrated(msg){
 const input=integratedObj(),key=JSON.stringify(input),request=++integratedRequest;
 setMissionStatus('loading','통합 설계를 계산하고 있습니다.');
 let d;
 try{d=await post('/api/integrated',input);}catch(error){if(request===integratedRequest)reportError(error);throw error;}
 if(request!==integratedRequest||key!==designKey())return null;
 lastIntegrated=d;lastIntegratedInput=input;lastDesignKey=key;
 lastCalculatedAt=new Date().toLocaleTimeString('ko-KR');
 setMissionStatus('ready','현재 입력의 통합 계산 완료. Coverage / Monte Carlo는 각 결과 상태를 확인하세요.');
 renderSat(d.satcom);
 renderBeam(d.beamforming);
 renderPayload(d.payload);
 renderRad(d.radiation);
 renderCenter(d);
 if(msg) trace(msg);
 return d;
}

async function syncAll(){
 syncGlobalToLabs();
 const tasks=await Promise.allSettled([runIntegrated('공유 설계값의 통합 계산을 완료했습니다.'),renderOrbit(),runCoverage(),runMonteCarlo(),runTimeline()]);
 const failure=tasks.find(task=>task.status==='rejected');
 if(failure)throw failure.reason;
}
$('syncBtn').onclick=withLoading($('syncBtn'),syncAll);
$("s_run").onclick=withLoading($("s_run"),()=>runIntegrated("Semiconductor changes propagated downstream to power, thermal, payload and service metrics."));
$("b_run").onclick=withLoading($("b_run"),()=>runIntegrated("Beamforming changes propagated to effective beams, payload power and service capacity."));
$("p_run").onclick=withLoading($("p_run"),()=>runIntegrated("RF payload architecture changes propagated to heat, radiator, mass and integrated mission metrics."));
$("r_run").onclick=withLoading($("r_run"),()=>runIntegrated("Radiation mitigation changes propagated to availability and effective service capacity."));

function optimizerObj(){
 return {
  base:integratedObj(),
  max_total_mass_kg:num("o_mass"),
  max_payload_power_w:num("o_power"),
  min_effective_capacity_gbps:num("o_cap"),
  min_effective_beams:parseInt($("o_beams").value),
  min_availability_pct:num("o_avail"),
  max_cost_musd:num("o_cost"),
  allowed_risk:$("o_risk").value,
  objective:$("o_obj").value
 }
}
function renderOptTable(rows){
 const t=$("o_table"),th=t.querySelector("thead"),tb=t.querySelector("tbody");
 if(!rows.length){th.innerHTML="";tb.innerHTML="<tr><td>No feasible design</td></tr>";return}
 const keys=["material","processor","altitude_km","beams","elements","bandwidth_mhz","rf_output_w","capacity_gbps","mass_kg","payload_power_w","cost_musd","risk"];
 th.innerHTML="<tr>"+keys.map(k=>`<th>${k}</th>`).join("")+"</tr>";
 tb.innerHTML=rows.map(r=>"<tr>"+keys.map(k=>`<td>${r[k]}</td>`).join("")+"</tr>").join("");
}
let optimizerRequest=0;
function optimizerKey(input){return JSON.stringify(input);}
// The results table, objective label and report summary must all reflect the
// SAME request-time input snapshot, even if the user edits inputs (or triggers
// another run) while this request is in flight. `input` is captured once, up
// front, and used for every render below (never re-read live from the DOM
// after the fact); `request`/`key` identify this call so a late-arriving
// response for now-stale inputs is discarded rather than rendered.
async function runOptimizer(){
 const input=optimizerObj(), key=optimizerKey(input), request=++optimizerRequest;
 const d=await post("/api/optimize",input);
 if(request!==optimizerRequest||key!==optimizerKey(optimizerObj()))return; // a newer run superseded this one
 const rows=d.results;
 $("o_count").textContent=d.count;
 $("o_objlabel").textContent=input.objective;
 if(rows.length){
   $("o_bestcap").textContent=Math.max(...rows.map(r=>r.capacity_gbps)).toFixed(2)+" Gbps";
   $("o_bestmass").textContent=Math.min(...rows.map(r=>r.mass_kg)).toFixed(1)+" kg";
   $("o_bestpower").textContent=Math.min(...rows.map(r=>r.payload_power_w)).toFixed(1)+" W";
   $("o_bestcost").textContent="$"+Math.min(...rows.map(r=>r.cost_musd)).toFixed(2)+"M";
 }else{
   ["o_bestcap","o_bestmass","o_bestpower","o_bestcost"].forEach(id=>$(id).textContent="—");
 }
 renderOptTable(rows);
 reactChart("o_pareto",[{
   type:"scatter",mode:"markers",
   x:rows.map(r=>r.mass_kg),y:rows.map(r=>r.capacity_gbps),
   text:rows.map(r=>`${r.material}/${r.processor}<br>${r.altitude_km} km<br>$${r.cost_musd}M`),
   marker:{size:rows.map(r=>8+Math.min(18,r.cost_musd/4))}
 }],{...layout,title:"Capacity vs Mass",xaxis:{title:"Mass kg"},yaxis:{title:"Effective Gbps"}},cfg);
 // Uses input.base (the same snapshot the table/label above were computed
 // from), not a fresh integratedObj() read, so the summary can never describe
 // a different scenario than the table it accompanies.
 const rep=await post("/api/report-summary",input.base);
 if(request!==optimizerRequest||key!==optimizerKey(optimizerObj()))return; // superseded during the summary request
 $("o_summary").innerHTML=rep.bullets.map(x=>`<div class="summary-item">${x}</div>`).join("");
}
$("o_run").onclick=withLoading($("o_run"),runOptimizer);

async function runSensitivity(){
 const body={base:integratedObj(),parameter:$("sen_param").value,low:num("sen_low"),high:num("sen_high"),steps:9};
 const d=await post("/api/sensitivity",body),rows=d.rows;
 reactChart("o_sensitivity",[
   {type:"scatter",mode:"lines+markers",name:"Capacity Gbps",x:rows.map(r=>r.x),y:rows.map(r=>r.effective_capacity_gbps)},
   {type:"scatter",mode:"lines+markers",name:"Mass kg",x:rows.map(r=>r.x),y:rows.map(r=>r.total_mass_kg),yaxis:"y2"}
 ],{...layout,title:`Sensitivity: ${d.parameter}`,xaxis:{title:d.parameter},yaxis:{title:"Gbps"},yaxis2:{title:"kg",overlaying:"y",side:"right"},legend:{orientation:"h"}},cfg);
}
$("sen_run").onclick=withLoading($("sen_run"),runSensitivity);

// Persistent scenario snapshot
function saveScenario(){
 try{localStorage.setItem('sdtc_v07_fields',JSON.stringify(Object.fromEntries([...document.querySelectorAll('input[id],select[id]')].map(el=>[el.id,el.type==='checkbox'?el.checked:el.value]))));}catch(error){console.warn('Scenario could not be saved',error);}
}
function loadScenario(){
 const fields=localStorage.getItem('sdtc_v07_fields');
 if(fields){for(const [id,value] of Object.entries(JSON.parse(fields))){const el=$(id);if(el&&el.matches('input,select')){if(el.type==='checkbox')el.checked=value===true;else el.value=value;}}return true;}
 const raw=localStorage.getItem("sdtc_v06_scenario"); if(!raw)return false;
 const s=JSON.parse(raw);
 $("g_alt").value=s.global.alt;$("g_freq").value=s.global.freq;$("g_bw").value=s.global.bw;$("g_elem").value=s.global.elem;$("g_beams").value=s.global.beams;
 if(s.sat){$("s_material").value=s.sat.material;$("s_pa").value=s.sat.part_pa;$("s_lna").value=s.sat.part_lna;$("s_rf").value=s.sat.rf_output_w;$("s_tops").value=s.sat.processor_tops}
 if(s.beam){$("b_arch").value=s.beam.architecture;$("b_proc").value=s.beam.processor;$("b_tops").value=s.beam.available_tops;$("b_power").value=s.beam.available_power_w}
 if(s.rad){$("r_mit").value=s.rad.mitigation;$("r_shield").value=s.rad.shielding_mm_al}
 if(s.payload){$("p_arch").value=s.payload.architecture}
 return true;
}
window.addEventListener("beforeunload",saveScenario);

function coverageObj(){
 return {
  ...constellationObj(),target_min_visible:parseInt($("cv_minvis").value),
  duration_hours:num("cv_hours"),time_step_sec:num("cv_step")
 }
}
async function runCoverage(){
 const input=coverageObj();
 const d=await post('/api/coverage',input);
 if(JSON.stringify(input)!==JSON.stringify(coverageObj()))return null;
 $("cv_total").textContent=d.total_sats;
 $("cv_foot").textContent=d.footprint_radius_km+" km";
 $("cv_overlap").textContent=d.mean_global_overlap_proxy+"×";
 const by=Object.fromEntries(d.regions.map(x=>[x.region,x]));
 $("cv_kr").textContent=by["Korea"].availability_pct+" %";
 $("cv_uae").textContent=by["UAE"].availability_pct+" %";
 $("cv_sea").textContent=by["Southeast Asia"].availability_pct+" %";
 const minReg=Math.min(...d.regions.map(x=>x.availability_pct));
 if($("c_regmin")) $("c_regmin").textContent=minReg+" %";
 reactChart("cv_regions",[{
   type:"bar",x:d.regions.map(x=>x.region),y:d.regions.map(x=>x.availability_pct),name:"Availability"
 },{
   type:"bar",x:d.regions.map(x=>x.region),y:d.regions.map(x=>x.continuity_pct),name:"Continuity"
 }],{...layout,barmode:"group",title:"Regional availability proxy [%]",yaxis:{range:[0,100]}},cfg);
 reactChart("cv_visible",[{
   type:"scatter",mode:"markers+text",x:d.regions.map(x=>x.latitude_deg),y:d.regions.map(x=>x.mean_visible_proxy),
   text:d.regions.map(x=>x.region),textposition:"top center",marker:{size:14,color:KASA.red}
 }],{...layout,title:"Latitude vs mean visible proxy",xaxis:{title:"Latitude °"},yaxis:{title:"Mean visible proxy"}},cfg);
 $("cv_note").textContent=d.note;
 return d;
}
$("cv_run").onclick=withLoading($("cv_run"),async()=>{if(await runCoverage())trace("Constellation geometry propagated to regional service visibility proxies.")});

$("cv_sweep").onclick=withLoading($("cv_sweep"),async()=>{
 const rows=await post("/api/coverage-sweep",coverageObj());
 reactChart("cv_sweepchart",[{
  type:"scatter",mode:"markers",
  x:rows.map(r=>r.total_sats),y:rows.map(r=>r.min_region_availability_pct),
  text:rows.map(r=>`${r.planes}×${r.sats_per_plane}`),
  marker:{size:rows.map(r=>8+r.planes/2)}
 }],{...layout,title:"Minimum regional availability vs satellite count",xaxis:{title:"Total satellites"},yaxis:{title:"Min regional availability %"}},cfg);
});

function mcObj(){
 return {
  base:integratedObj(),
  runs:parseInt($("mc_runs").value),seed:parseInt($("mc_seed").value),
  rf_output_sigma_pct:num("mc_rf"),pa_eff_sigma_pct:6,loss_sigma_db:num("mc_loss"),
  bandwidth_sigma_pct:num("mc_bw"),processor_tops_sigma_pct:num("mc_tops"),
  tid_sigma_pct:num("mc_tid"),seu_sigma_pct:num("mc_seu"),
  mass_sigma_pct:num("mc_mass"),cost_sigma_pct:num("mc_cost"),
  capacity_threshold_gbps:num("mc_cap"),max_power_w:num("mc_pmax"),max_mass_kg:num("mc_mmax")
 }
}
async function runMonteCarlo(){
 const input=mcObj();
 const d=await post('/api/montecarlo',input),m=d.metrics;
 if(JSON.stringify(input)!==JSON.stringify(mcObj()))return null;
 $("mc_success").textContent=d.success_probability_pct+" %";
 $("mc_cp50").textContent=m.capacity_gbps.p50+" Gbps";
 $("mc_cp10").textContent=m.capacity_gbps.p10+" Gbps";
 $("mc_pp90").textContent=m.power_w.p90+" W";
 $("mc_mp90").textContent=m.mass_kg.p90+" kg";
 $("mc_costp90").textContent="$"+m.cost_musd.p90+"M";
 if($("c_mc")) $("c_mc").textContent=d.success_probability_pct+" %";

 reactChart("mc_hist",[{
   type:"histogram",x:d.samples.map(x=>x.capacity_gbps),nbinsx:24
 }],{...layout,title:"Effective capacity distribution",xaxis:{title:"Gbps"},yaxis:{title:"Count"}},cfg);

 const names=["Capacity","Power","Mass","Cost"];
 const p10=[m.capacity_gbps.p10,m.power_w.p10,m.mass_kg.p10,m.cost_musd.p10];
 const p50=[m.capacity_gbps.p50,m.power_w.p50,m.mass_kg.p50,m.cost_musd.p50];
 const p90=[m.capacity_gbps.p90,m.power_w.p90,m.mass_kg.p90,m.cost_musd.p90];
 reactChart("mc_band",[
  {type:"bar",name:"P10",x:names,y:p10},
  {type:"bar",name:"P50",x:names,y:p50},
  {type:"bar",name:"P90",x:names,y:p90}
 ],{...layout,barmode:"group",title:"P10 / P50 / P90"},cfg);

 const robust=[
   Math.min(100,d.success_probability_pct),
   Math.min(100,100*num("mc_cap")/Math.max(m.capacity_gbps.p10,0.01)),
   Math.min(100,100*num("mc_pmax")/Math.max(m.power_w.p90,0.01)),
   Math.min(100,100*num("mc_mmax")/Math.max(m.mass_kg.p90,0.01))
 ];
 reactChart("mc_radar",[{
   type:"scatterpolar",r:[...robust,robust[0]],theta:["Success","Capacity margin","Power margin","Mass margin","Success"],fill:"toself"
 }],{...layout,polar:{bgcolor:"rgba(0,0,0,0)",radialaxis:{range:[0,100],gridcolor:"#1b3b50"}},showlegend:false},cfg);
 $("mc_note").textContent=d.note;
 return d;
}
$("mc_run").onclick=withLoading($("mc_run"),async()=>{if(await runMonteCarlo())trace("Monte Carlo uncertainty propagated to mission robustness and success probability.")});

async function loadTheory(){
 const d=await fetch("/api/theory").then(r=>r.json());
 $("theoryGrid").innerHTML=d.physics_core.map(x=>`<div class="theory-card"><span>${x.status.toUpperCase()}</span><b>${x.area}</b><code>${x.equation}</code></div>`).join("");
 $("engineeringModels").innerHTML=d.engineering_models.map(x=>`<div>${x}</div>`).join("");
}

// V0.8 physical-result visibility
const oldRenderSatV08 = renderSat;
renderSat = function(d){
 oldRenderSatV08(d);
 const w = [...(d.warnings || [])];
 if(d.link && d.orbit){
   w.unshift(`Physics: orbital period ${d.orbit.period_min} min · orbital speed ${d.orbit.speed_km_s} km/s · max Doppler bound ${d.link.max_doppler_khz} kHz`);
   w.unshift(`Link: Tx aperture gain ${d.antenna.used_tx_gain_dbi} dBi · noise T ${d.link.noise_temp_k} K · spectral efficiency ${d.link.practical_se} bit/s/Hz`);
 }
 warnings("s_warn",w);
}

async function runPoisson(){
 const body={
  thickness_um:num("po_L"),net_doping_cm3:num("po_N"),relative_permittivity:num("po_eps"),
  left_potential_v:0,right_potential_v:num("po_vr"),grid_points:121,model:$("po_model").value,temperature_k:num("po_temp"),intrinsic_cm3:num("po_ni"),carrier_sign:1,max_iterations:80,tolerance_v:1e-7
 };
 const d=await post("/api/poisson-device",body);
 reactChart("po_chart",[
  {type:"scatter",mode:"lines",name:"Potential [V]",x:d.x_um,y:d.potential_v},
  {type:"scatter",mode:"lines",name:"E field [V/m]",x:d.x_um,y:d.electric_field_v_m,yaxis:"y2"}
 ],{...layout,title:"Poisson solution: potential & electric field",xaxis:{title:"x [μm]"},yaxis:{title:"Potential [V]"},yaxis2:{title:"E [V/m]",overlaying:"y",side:"right"},legend:{orientation:"h"}},cfg);
 $("po_note").textContent=d.max_numeric_error_v!==undefined?`${d.physics} · ${d.assumption} · error ${d.max_numeric_error_v.toExponential(2)} V`:`${d.physics} · ${d.boundary} · converged=${d.converged}, iterations=${d.iterations}`;
}
$("po_run").onclick=withLoading($("po_run"),runPoisson);

function propagationObj(){
 return {frequency_ghz:num("pr_f"),elevation_deg:num("pr_el"),rain_rate_mm_h:num("pr_rain"),
  polarization:$("pr_pol").value,polarization_tilt_deg:45,rain_height_km:num("pr_hr"),
  station_height_km:num("pr_hs"),path_reduction_factor:num("pr_red")}
}
async function runPropagation(){
 const d=await post("/api/propagation",propagationObj());
 $("pr_k").textContent=d.k;$("pr_alpha").textContent=d.alpha;
 $("pr_gamma").textContent=d.specific_attenuation_db_km+" dB/km";
 $("pr_path").textContent=d.effective_rain_path_km+" km";$("pr_loss").textContent=d.rain_attenuation_db+" dB";
 const base=propagationObj(), rates=[1,5,10,20,30,40,50,75,100];
 const vals=[];
 for(const R of rates){const q=await post("/api/propagation",{...base,rain_rate_mm_h:R});vals.push(q.rain_attenuation_db)}
 reactChart("pr_curve",[{type:"scatter",mode:"lines+markers",x:rates,y:vals}],{...layout,title:`Rain attenuation at ${base.frequency_ghz} GHz`,xaxis:{title:"Rain rate [mm/h]"},yaxis:{title:"Attenuation [dB]"}},cfg);
 $("pr_note").textContent=d.physics+" "+d.boundary;
}
$("pr_run").onclick=withLoading($("pr_run"),runPropagation);

function timelineObj(){
 return {...constellationObj(),region:$("tl_region").value,
 duration_hours:num("tl_hours"),time_step_sec:num("tl_step")}
}
async function runTimeline(){
 const input=timelineObj();
 const d=await post('/api/pass-timeline',input),r=d.rows;
 if(JSON.stringify(input)!==JSON.stringify(timelineObj()))return;
 reactChart("tl_chart",[
  {type:"scatter",mode:"lines",name:"Visible sats",x:r.map(x=>x.time_min),y:r.map(x=>x.visible_count),line:{shape:"hv"}},
  {type:"scatter",mode:"lines",name:"Max elevation °",x:r.map(x=>x.time_min),y:r.map(x=>x.max_elevation_deg),yaxis:"y2"},
  {type:"scatter",mode:"lines",name:"Doppler kHz",x:r.map(x=>x.time_min),y:r.map(x=>x.best_doppler_khz),yaxis:"y3"}
 ],{...layout,title:`${d.region} pass timeline`,xaxis:{title:"Time [min]"},
 yaxis:{title:"Visible sats"},yaxis2:{title:"Elevation °",overlaying:"y",side:"right"},
 yaxis3:{title:"Doppler kHz",overlaying:"y",side:"right",anchor:"free",position:.92},legend:{orientation:"h"}},cfg);
}
$("tl_run").onclick=withLoading($("tl_run"),runTimeline);

async function loadPhysicsRegistry(){
 const d=await fetch("/api/physics-registry").then(r=>r.json());
 if($("physicsVersion")) $("physicsVersion").textContent=d.core_version;
 if($("physicsCount")) $("physicsCount").textContent=d.count;
 if($("theoryGrid")) $("theoryGrid").innerHTML=d.registry.map(x=>`<div class="theory-card"><span>${x.domain.toUpperCase()} · ${x.level}</span><b>${x.id}</b><code>${x.equation}</code><small>model v${x.version}</small></div>`).join("");
}

// Restore once before any API calls, so startup cannot overwrite a restored design.
try{loadScenario();}catch(error){console.warn('Saved scenario could not be restored',error);}
sharedFields.forEach(group=>syncSharedField(group[0]));
function designChanged(event){
 const el=event.target;if(!el.matches('input,select'))return;
 syncSharedField(el.id);
 if(lastDesignKey!==designKey()){
  setMissionStatus('stale','입력이 변경되었습니다. 그림은 미리보기이며 기존 계산 결과는 갱신 전입니다. RUN 또는 SYNC를 실행하세요.');
  $('c_mc').textContent='재계산 필요';
 }else if(lastIntegrated){
  setMissionStatus('ready','현재 입력의 통합 계산 결과입니다. Coverage / Monte Carlo는 각 결과 상태를 확인하세요.');
 }
 if(el.id.startsWith('cv_')||['g_alt','s_el','p_geo_el'].includes(el.id))$('c_regmin').textContent='재계산 필요';
 if(el.id.startsWith('mc_'))$('c_mc').textContent='재계산 필요';
 renderConops();
}
document.addEventListener('input',designChanged);
document.addEventListener('change',designChanged);
renderConops();
withLoading($('syncBtn'),syncAll)();
withLoading($('po_run'),runPoisson)();
withLoading($('pr_run'),runPropagation)();
loadTheory().then(loadPhysicsRegistry).catch(reportError);
const missionBarObserver=new ResizeObserver(entries=>{
 document.documentElement.style.setProperty('--mission-height',entries[0].target.offsetHeight+'px');
});
missionBarObserver.observe(document.querySelector('.mission-bar'));
