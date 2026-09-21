/* Parametric isometric mission illustration. No external textures or rendering dependencies. */
const conopsView={mode:'overview',links:true,labels:true,motion:false};
const conopsClamp=(v,a,b)=>Math.max(a,Math.min(b,v));
function conopsTag(x,y,title,detail,color='#89d9ef',anchor='start'){
 return `<g class="conops-label" text-anchor="${anchor}"><text x="${x}" y="${y}" fill="${color}" font-size="12" font-weight="700" letter-spacing="1.4">${escapeMarkup(title)}</text><text x="${x}" y="${y+21}" fill="#d4e3ee" font-size="14">${escapeMarkup(detail)}</text></g>`;
}
function conopsBuilding(x,y,w,h,color='#47738d'){
 let windows='';for(let i=7;i<w-3;i+=12)for(let j=8;j<h-4;j+=12)windows+=`<rect x="${i}" y="${-h+j}" width="5" height="4" fill="#9ee2e8" opacity=".65"/>`;
 return `<g transform="translate(${x} ${y})"><path d="M0 0 L${w} 0 L${w+18} -12 L18 -12Z" fill="#010c18" opacity=".5"/><path d="M0 0 V${-h} L${w} ${-h} V0Z" fill="${color}"/><path d="M0 ${-h} L18 ${-h-12} L${w+18} ${-h-12} L${w} ${-h}Z" fill="#81a6b8"/><path d="M${w} 0 V${-h} L${w+18} ${-h-12} V-12Z" fill="#24465f"/>${windows}</g>`;
}
function conopsDish(x,y,scale=1){
 return `<g transform="translate(${x} ${y}) scale(${scale})"><ellipse cy="6" rx="31" ry="9" fill="#000b15" opacity=".6"/><path d="M-12 0 L0 -39 L12 0Z" fill="#8bafbf" stroke="#d3e4ec"/><path d="M-5 -30 L16 -52" stroke="#bacfd9" stroke-width="6"/><g transform="translate(7 -48) rotate(-32)"><path d="M-29 0 Q0 45 29 0" fill="url(#conopsMetal)" stroke="#c5e5ef"/><ellipse rx="29" ry="10" fill="#254d67" stroke="#d6edf4" stroke-width="2"/><path d="M-26 0 L0 -25 L25 0 M0 -25 V7" fill="none" stroke="#a9cbd9" stroke-width="2"/><circle cy="-25" r="4" fill="#edc575"/></g></g>`;
}
// Local +Y is nadir: apertures and feeds face the ground below the bus.
function conopsAntennaGeometry(m){
 const b=m.bodySize*2.1,dish=conopsClamp(m.dish*24,10,30);
 return {b,dish,array:{x:12,y:b*.6+16},reflector:{x:-b-8,y:b*.6+14}};
}
function conopsSpacecraft(m,mini=false){
 const b=m.bodySize*2.1,w=m.wing*1.55,r=m.radiatorSize*1.4;
 const cells=conopsClamp(Math.ceil(Math.sqrt(m.elements)),4,24);
 const {dish,array,reflector}=conopsAntennaGeometry(m),rows=Math.ceil(cells/6);
 const id=name=>mini?'':`id="${name}"`;
 let antennas='';
 for(let n=0;n<cells;n++)antennas+=`<circle cx="${-b*.5+(n%6)*b*.2}" cy="${-12+(Math.floor(n/6)+.5)*24/rows}" r="1.6" fill="#f5d287"/>`;
 // Each wing has its own yoke off #conopsBody's own vertical midline (f),
 // canted up and outward like a real deployed array instead of lying level:
 // b tilts the span upward as it extends away from the bus, c,d keep it
 // mostly upright (a standing panel, not a plank lying flat) along its
 // depth. The left wing's transform mirrors the right's (b,c negated) so
 // both cant upward symmetrically instead of one rising and one dipping.
 const bodyCenterY=-b*.75+b*1.35/2;
 const wingR=`matrix(1 -.4 .1 .95 0 ${bodyCenterY})`,wingL=`matrix(1 .4 -.1 .95 0 ${bodyCenterY})`;
 return `<g ${id('conopsSatellite')}>
  <g transform="${wingL}" stroke="#3c5568" stroke-width="1">
   <path d="M${-b-w-16} -24 h${w} v48 h${-w}Z" fill="#050b12" transform="translate(0 5)"/>
   <rect ${id('conopsSolar')} x="${-b-w-16}" y="-24" width="${w}" height="48" fill="url(#conopsCells)"/>
   <path d="M${-b-16} 0 H${-b}" stroke="#43607a" stroke-width="5"/>
  </g>
  <g transform="${wingR}" stroke="#3c5568" stroke-width="1">
   <path d="M${b+16} -24 h${w} v48 h${-w}Z" fill="#050b12" transform="translate(0 5)"/>
   <rect x="${b+16}" y="-24" width="${w}" height="48" fill="url(#conopsCells)"/>
   <path d="M${b} 0 H${b+16}" stroke="#43607a" stroke-width="5"/>
  </g>
  <rect ${id('conopsBody')} x="${-b}" y="${-b*.75}" width="${b*2}" height="${b*1.35}" rx="2" fill="url(#conopsGold)" stroke="#d3b976"/>
  <path d="M${b} ${-b*.75} L${b+24} ${-b*.75+20} V${b*.6+20} L${b} ${b*.6}Z" fill="#775b33" stroke="#d3b976"/>
  <path d="M${-b} ${b*.6} H${b} L${b+24} ${b*.6+20} H${-b+24}Z" fill="#52616a" stroke="#b7cbd1"/>
  <path d="M${-b+4} ${-b*.75+4} L${b-4} ${b*.6-4} M${b-4} ${-b*.75+4} L${-b+4} ${b*.6-4}" stroke="#fff0bf" stroke-opacity=".24"/>
  <g transform="translate(${b+18} ${b*.6-10}) skewY(-34)"><rect ${id('conopsRadiator')} width="${r}" height="26" fill="#c8dce5" stroke="#fff"/>${Array.from({length:5},(_,i)=>`<path d="M2 ${4+i*4} H${r-2}" stroke="#799fb5"/>`).join('')}</g>
  <path d="M-8 ${-b*.75+3} V${-b*.75-24}" stroke="#d7e9f1" stroke-width="2"/><circle cx="-8" cy="${-b*.75-24}" r="3" fill="#d7e9f1"/>
  <circle cx="${b*.4}" cy="${-b*.75+10}" r="5" fill="#0c2845" stroke="#acccdb"/>
  <path d="M${-b*.6} ${b*.5} L${reflector.x} ${reflector.y-10}" stroke="#b5cbd4" stroke-width="4"/>
  <g ${id('conopsReflector')} transform="translate(${reflector.x} ${reflector.y}) rotate(32)"><path d="M${-dish} 0 Q0 ${-dish*1.45} ${dish} 0" fill="url(#conopsMetal)" stroke="#b5d9e6"/><ellipse rx="${dish}" ry="${dish*.34}" fill="#274d62" stroke="#cae6f0"/><path d="M${-dish} 0 L0 ${dish*.8} L${dish} 0 M0 0 V${dish*.8}" stroke="#e7d3a0" fill="none"/><circle cy="${dish*.8}" r="2.5" fill="#f5d287"/></g>
  <!-- Underside view: the array plane shares the bus floor depth vector (24, 20).
       Its radiating face is below the mounting plate, with a projected normal along +Y. -->
  <g ${id('conopsAntennaArray')} transform="translate(${array.x} ${array.y})">
   <path d="M${-b*.75-9} -7.5 v-4 H${b*.75-9} l18 15 v4" fill="#637c8c" stroke="#abc6d3"/>
   <g transform="matrix(1 0 .6 .5 0 0)"><rect x="${-b*.75}" y="-15" width="${b*1.5}" height="30" rx="1" fill="#0a2941" stroke="#e2ca86"/>${antennas}</g>
  </g>
 </g>`;
}
function conopsScene(m){
 const payload=conopsView.mode==='payload',coverage=conopsView.mode==='coverage';
 const sx=600,sy=235-conopsClamp((m.alt-300)/1700,0,1)*65;
 const scale=coverage?.7:1,{array,reflector}=conopsAntennaGeometry(m);
 const ax=sx+array.x*scale,ay=sy+array.y*scale;
 const fx=sx+reflector.x*scale,fy=sy+reflector.y*scale;
 const spread=100+conopsClamp(m.footprint/2300,0,1)*215;
 const ground=492,shown=Math.min(m.beams,12),planes=Math.min(m.orbit.planes,5);
 let stars='',grid='',fleet='',beams='',terminals='';
 for(let n=0;n<85;n++)stars+=`<circle cx="${(n*137.51)%1200}" cy="${(n*n*23.73)%530}" r="${n%7===0?1.3:.65}" fill="#b9ddeb" opacity="${.15+(n%5)*.1}"/>`;
 for(let n=0;n<9;n++)grid+=`<path d="M${-160+n*190} 650 Q${360+n*42} 410 ${250+n*90} 402"/>`;
 for(let n=0;n<6;n++)grid+=`<path d="M-50 ${445+n*40} Q600 ${345+n*30} 1250 ${445+n*40}"/>`;
 for(let p=0;p<planes;p++){
  const slope=Math.sin(m.orbit.inclination_deg*Math.PI/180)*(.35+p*.1);
  fleet+=`<g transform="rotate(${-12+p*8} 600 235)"><ellipse cx="600" cy="235" rx="${385+p*28}" ry="${60+slope*95}" fill="none" stroke="#42677f" stroke-dasharray="${p===0?'7 5':'2 9'}" opacity="${p===0?.65:.25}"/>`;
  for(let n=0;m.total>1&&n<Math.min(m.orbit.sats_per_plane,4);n++){
   const a=(n/Math.min(m.orbit.sats_per_plane,4)*Math.PI*2)+p*.55+m.orbit.walker_f*.18;
   const x=600+Math.cos(a)*(385+p*28),y=235+Math.sin(a)*(60+slope*95);
   fleet+=`<g class="conops-fleet-sat" transform="translate(${x} ${y}) rotate(${12-p*8}) scale(.17)">${conopsSpacecraft(m,true)}</g>`;
  }
  fleet+='</g>';
 }
 for(let n=0;n<shown;n++){
  const a=n*2.39996,rad=shown===1?0:Math.sqrt((n+.5)/shown);
  const x=640+Math.cos(a)*spread*.78*rad,y=ground+Math.sin(a)*52*rad;
  const rx=conopsClamp(spread/Math.sqrt(shown)*.7,24,85),ry=rx*.34;
  beams+=`<g class="conops-beam" data-beam="${n+1}"><path class="conops-cone" d="M${ax} ${ay} L${x-rx} ${y} Q${x} ${y+ry*2} ${x+rx} ${y}Z" fill="url(#conopsBeam)"/><ellipse cx="${x}" cy="${y}" rx="${rx}" ry="${ry}" fill="#fb6757" fill-opacity=".10" stroke="#ef8c77" stroke-opacity=".55"/><path class="conops-flow" d="M${ax} ${ay} L${x} ${y}" stroke="#f8a591" stroke-opacity=".48" stroke-dasharray="3 14" fill="none"/></g>`;
  terminals+=`<g transform="translate(${x} ${y})"><path d="M-4 0 H4 V-9 H-4Z M0 -9 V-17 M-6 -17 Q0 -22 6 -17" fill="#2d6478" stroke="#bde5ea" stroke-width="1.3"/></g>`;
 }
 const defs=`<defs>
  <radialGradient id="conopsSpace" cx="52%" cy="35%" r="75%"><stop stop-color="#173047"/><stop offset=".65" stop-color="#081525"/><stop offset="1" stop-color="#040b15"/></radialGradient>
  <linearGradient id="conopsEarth" x2="0" y2="1"><stop stop-color="#295b72"/><stop offset=".22" stop-color="#173f55"/><stop offset="1" stop-color="#091d30"/></linearGradient>
  <linearGradient id="conopsGold"><stop stop-color="#856339"/><stop offset=".35" stop-color="#ddc18b"/><stop offset=".65" stop-color="#ab8549"/><stop offset="1" stop-color="#e0ca98"/></linearGradient>
  <linearGradient id="conopsMetal" x2=".7" y2="1"><stop stop-color="#f4fafc"/><stop offset=".4" stop-color="#96b6c9"/><stop offset="1" stop-color="#375c76"/></linearGradient>
  <linearGradient id="conopsBeam" x2="0" y2="1"><stop stop-color="#ffb291" stop-opacity=".025"/><stop offset="1" stop-color="#f97859" stop-opacity=".14"/></linearGradient>
  <pattern id="conopsCells" width="12" height="12" patternUnits="userSpaceOnUse"><rect width="12" height="12" fill="#0a1119"/><rect x="1" y="1" width="10" height="10" fill="#141f2b" stroke="#3c5568" stroke-width=".45"/><path d="M2 4 H10 M2 8 H10" stroke="#5a7690" stroke-opacity=".3" stroke-width=".5"/></pattern>
  <filter id="conopsGlow" x="-50%" y="-300%" width="200%" height="700%"><feGaussianBlur stdDeviation="4"/></filter>
  <clipPath id="conopsTerrainClip"><path d="M-60 497 Q600 286 1260 497 V670 H-60Z"/></clipPath>
 </defs>`;
 const groundScene=`<g clip-path="url(#conopsTerrainClip)"><path d="M-60 497 Q600 286 1260 497 V670 H-60Z" fill="url(#conopsEarth)"/><path d="M80 459 L210 421 298 427 356 407 457 443 509 429 561 451 542 477 589 498 548 531 456 514 375 554 287 540 260 510 156 518Z M820 421 L899 448 990 442 1081 491 1049 539 975 525 952 567 871 581 789 545 745 494 784 475Z" fill="#4b716c" opacity=".32"/><g fill="none" stroke="#72b4c4" stroke-opacity=".13">${grid}</g><path d="M60 560 Q260 481 386 555 T900 587 L1120 537" fill="none" stroke="#a7c7cc" stroke-opacity=".14" stroke-width="5"/></g><path d="M-60 497 Q600 286 1260 497" fill="none" stroke="#79d6ed" stroke-width="9" opacity=".28" filter="url(#conopsGlow)"/><path d="M-60 497 Q600 286 1260 497" fill="none" stroke="#8ed7e8" stroke-width="1.4" opacity=".55"/>`;
 const label=(...a)=>conopsTag(...a);
 const overview=`<g opacity="${coverage?.35:1}">${fleet}</g>${groundScene}
  ${coverage?`<g id="conopsEnvelope"><ellipse cx="640" cy="${ground}" rx="${spread+20}" ry="87" fill="#80d9df" fill-opacity=".04" stroke="#8adce4" stroke-width="1.5" stroke-dasharray="6 5"/><path d="M640 ${ground+91} h${spread+20} m0 -5 v10 M640 ${ground+86} v10" fill="none" stroke="#8adce4"/><text class="conops-label" x="${640+(spread+20)/2}" y="${ground+80}" text-anchor="middle" fill="#a8e4ec" font-size="12" paint-order="stroke" stroke="#050f18" stroke-width="4" stroke-linejoin="round">가시 반경 약 ${Math.round(m.footprint).toLocaleString()} km</text></g>`:''}
  <g class="conops-links">${beams}
   <path class="conops-flow" d="M210 469 Q346 284 ${fx} ${fy}" fill="none" stroke="#edcc85" stroke-width="2.5" stroke-dasharray="9 8"/>
   <path class="conops-flow conops-return" d="M${fx} ${fy} Q330 319 225 480" fill="none" stroke="#edcc85" stroke-opacity=".4" stroke-dasharray="4 9"/>
   <path class="conops-flow" d="M198 497 L125 556 H315 L351 537" fill="none" stroke="#78d4d7" stroke-width="2" stroke-dasharray="5 7"/>
   <path class="conops-flow" d="M350 504 Q358 355 ${ax} ${ay}" fill="none" stroke="#79d4d7" stroke-dasharray="3 9"/>
  </g>
  ${m.isl>0?`<g id="conopsISL" class="conops-links"><path class="conops-flow" d="M${sx+95} ${sy-9} L965 183" stroke="#bda5ff" stroke-width="2" stroke-dasharray="7 7"/><g transform="translate(985 180) scale(.36)">${conopsSpacecraft(m,true)}</g>${label(940,250,'INTER-SATELLITE LINK',`Offload ${Math.round(m.isl*100)}%`,'#c7b8f8')}</g>`:''}
  <g opacity="${coverage?.32:1}">${conopsBuilding(151,500,65,24)}${conopsDish(201,479,.9)}${conopsDish(140,502,.48)}${conopsBuilding(295,553,85,40)}${conopsBuilding(351,531,34,24)}${conopsBuilding(970,553,28,60)}${conopsBuilding(1009,564,37,91)}${conopsBuilding(1060,564,26,43)}${conopsBuilding(1094,552,19,29)}
   <path d="M813 575 l57 0 -12 14 h-36Z" fill="#7ea6b7"/><path d="M837 575 v-24 l18 24Z" fill="#d4e6eb"/><path d="M838 551 v-7" stroke="#aacee0"/>
  </g>${terminals}
  <g transform="translate(${sx} ${sy}) scale(${scale})">${conopsSpacecraft(m)}</g>
  <g class="conops-label" fill="#091726" opacity=".9"><rect x="18" y="15" width="350" height="110" rx="8"/><rect x="842" y="15" width="340" height="110" rx="8"/></g>
  ${label(32,37,'MISSION / SPACE SEGMENT',`${m.alt.toLocaleString()} km · ${m.orbit.inclination_deg}° inclination`)}
  ${label(32,91,'WALKER CONSTELLATION',`${m.orbit.planes} × ${m.orbit.sats_per_plane} / ${m.total} satellites · F ${m.orbit.walker_f}`,'#92aabf')}
  ${label(1168,37,'PAYLOAD CONFIGURATION',m.archLabel,'#edc980','end')}
  ${label(1168,91,'BEAMFORMING',`${m.beamArch} · ${m.elements} elements`,'#92aabf','end')}
  <g class="conops-label"><path d="M${sx} ${sy-64} V${sy-88} H${sx+120}" fill="none" stroke="#8ba9bc"/><text x="${sx+128}" y="${sy-84}" fill="#e0edf4" font-size="13">통신 위성 / ${m.arch==='Bent-Pipe'?'RF relay':'On-board processing'}</text></g>
  ${label(80,330,'FEEDER LINK',`${m.freq} GHz / ${m.bw} MHz`,'#edcc85')}
  ${label(878,371,'MULTI-BEAM SERVICE',`${m.beams} beams · ${shown}개 대표 표시`,'#ffab96')}
  ${label(878,421,'COVERAGE ENVELOPE',`반경 약 ${Math.round(m.footprint).toLocaleString()} km · 최소 ${m.minEl}°`,'#a1d8e4')}
  ${label(152,590,'01 / GATEWAY','지상 게이트웨이','#edcc85')}
  ${label(335,606,'02 / MISSION CONTROL','관제 · 명령 / 상태 수신','#83d5d8')}
  ${label(687,607,'03 / USER SEGMENT','육상 · 해상 · 이동 단말','#ffab96')}
  <g class="conops-label"><text x="32" y="642" fill="#7896ac" font-size="11">${m.total===1?0:Math.min(m.total,planes*Math.min(m.orbit.sats_per_plane,4))}개 군집 위성 대표 표시 · 궤도 위치 / 지형 / 빔 배치는 설명용</text></g>`;
 const payloadScene=`<g stroke="#33546c" stroke-opacity=".25" fill="none">${Array.from({length:12},(_,i)=>`<path d="M${i*110-100} 650 L${i*110+400} 100 M0 ${160+i*40} H1200"/>`).join('')}</g>
  <ellipse cx="600" cy="454" rx="350" ry="35" fill="#010813" opacity=".5"/>
  <g transform="translate(590 307) scale(1.75)">${conopsSpacecraft(m)}</g>
  ${label(32,38,'SPACECRAFT / PAYLOAD DETAIL',m.archLabel)}
  ${label(1168,38,'PARAMETRIC ASSEMBLY',m.current?'현재 계산 결과의 상대 크기':'입력 미리보기 · RUN / SYNC 후 크기 갱신','#edc980','end')}
  <g class="conops-label" fill="none" stroke="#718fa4"><path d="M310 143 H386 L420 264"/><path d="M857 146 H774 L${590+array.x*1.75} ${307+array.y*1.75}"/><path d="M301 418 H423 L${590+reflector.x*1.75} ${307+reflector.y*1.75}"/><path d="M862 407 H803 L688 326"/></g>
  ${label(45,132,'01 / SOLAR ARRAY',m.current?`탑재체 전력 ${m.power} W 기반 상대 면적`:'탑재체 전력 계산 대기','#89d9ef')}
  ${label(863,132,'02 / NADIR ANTENNA ARRAY',`${m.beamArch} · ${m.elements} elements`,'#edc980')}
  ${label(45,410,'03 / EARTH-FACING REFLECTOR',`안테나 직경 ${m.dish} m · ${m.freq} GHz`,'#edc980')}
  ${label(863,400,'04 / THERMAL RADIATOR',m.current?`${m.radiator} m² · 열 부하 ${m.heat} W`:'방열 면적 계산 대기','#b9dce9')}
  <g class="conops-label"><path d="M${590+array.x*1.75} ${307+array.y*1.75+24} v45 m-5 -7 l5 7 5 -7" fill="none" stroke="#89d9ef"/><text x="${605+array.x*1.75}" y="${307+array.y*1.75+56}" fill="#89d9ef" font-size="12">NADIR / 지구 방향</text></g>
  <g class="conops-label"><rect x="55" y="509" width="1090" height="101" rx="12" fill="#0a2033" stroke="#36526a"/><text x="78" y="535" fill="#8eb1c9" font-size="11" letter-spacing="2">ON-BOARD SIGNAL PATH</text></g>
  ${conopsSignalPath(m)}
  <text class="conops-label" x="55" y="641" fill="#91a9bb" font-size="12">본체: 질량 · 태양전지판: 탑재체 전력 · 방열판: 방열 면적에 연동 / 제작 치수와 배치가 아닌 상대적 표현</text>`;
 return `<svg viewBox="0 0 1200 660" xmlns="http://www.w3.org/2000/svg" role="img" aria-labelledby="conopsTitle conopsDesc" data-view="${conopsView.mode}" class="${conopsView.links?'':'conops-hide-links'} ${conopsView.labels?'':'conops-hide-labels'} ${conopsView.motion?'conops-playing':''}">
 <title id="conopsTitle">${escapeMarkup(m.archLabel)}, ${m.alt} km, ${m.beams} beams, ${m.total} satellites</title><desc id="conopsDesc">입체 운용개념도. 위성, 빔, 게이트웨이, 관제센터와 사용자 단말의 연결. 실제 축척이 아닙니다. ${m.current?'현재 계산 결과 반영.':'입력 미리보기, 크기는 계산 후 갱신.'}</desc>${defs}<rect width="1200" height="660" fill="url(#conopsSpace)"/>${stars}${payload?payloadScene:overview}</svg>`;
}
function conopsSignalPath(m){
 const stages=m.arch==='Bent-Pipe'?['RX / LNA','Filter / Mixer','RF relay','HPA','TX / Antenna']:['RX / LNA','ADC / Channelizer',m.arch==='Flexible Digital'?'Digital routing':m.stack,'DAC / HPA','TX / Beamforming'];
 return stages.map((s,i)=>`<g class="conops-label"><rect x="${78+i*213}" y="550" width="185" height="38" rx="5" fill="${i===2?'#243e50':'#102c41'}" stroke="${i===2?'#d9bd7b':'#375a72'}"/><text x="${170+i*213}" y="574" text-anchor="middle" fill="#deebf3" font-size="13">${escapeMarkup(s)}</text>${i<4?`<path class="conops-links conops-flow" d="M${265+i*213} 569 h23 l-5 -4 m5 4 l-5 4" stroke="#edcc85" fill="none"/>`:''}</g>`).join('');
}
document.querySelector('.conops-toolbar').addEventListener('click',event=>{
 const button=event.target.closest('button');if(!button)return;
 if(button.dataset.conopsView){conopsView.mode=button.dataset.conopsView;document.querySelectorAll('[data-conops-view]').forEach(el=>el.setAttribute('aria-pressed',String(el.dataset.conopsView===conopsView.mode)));}
 if(button.dataset.conopsToggle){const key=button.dataset.conopsToggle;conopsView[key]=!conopsView[key];button.setAttribute('aria-pressed',String(conopsView[key]));if(key==='motion')button.textContent=conopsView.motion?'흐름 정지':'흐름 재생';}
 renderConops();
});
