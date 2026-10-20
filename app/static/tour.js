// Lightweight first-visit coachmark tour (vanilla JS). Asks the language first, then shows steps in that language only.
(function(){
const $=s=>document.querySelector(s);const T=(...a)=>{try{window.track(...a)}catch(e){}};
const STEPS=[
 {sel:'#const',en:['Choose a district','Start here: pick the district whose voter list you want to see.'],hi:['ज़िला चुनें','यहाँ से शुरू करें: वह ज़िला चुनें जिसकी मतदाता सूची देखनी है।']},
 {sel:'#q',need:1,en:['Search','Type a name, institution, address or pincode. Spelling mistakes are forgiven (e.g. "ip collage"), and you can search in Hindi too.'],hi:['खोजें','नाम, संस्थान, पता या पिनकोड लिखें। वर्तनी की गलती चल जाती है (जैसे "ip collage"), और आप हिंदी में भी खोज सकते हैं।']},
 {sel:'#inst-btn',need:1,en:['Filter by institution','Show voters of one school or college only. You can type inside the list to find it.'],hi:['संस्थान से छाँटें','केवल एक स्कूल या कॉलेज के मतदाता देखें। सूची में लिखकर संस्थान ढूँढ सकते हैं।']},
 {sel:'.table-wrap',need:1,en:['Voter list','Matching voters appear here, 50 per page.'],hi:['मतदाता सूची','मिलते हुए मतदाता यहाँ दिखते हैं, हर पेज पर 50।']},
 {sel:'.pager',need:1,en:['Pages','Use Next and Prev to move between pages. They open instantly.'],hi:['पेज','अगले और पिछले पेज पर जाने के लिए Next और Prev दबाएँ। पेज तुरंत खुलते हैं।']},
 {sel:'#logout',en:['Log out','Log out here when you are done. Tap "?" anytime to see this guide again.'],hi:['लॉग आउट','काम पूरा होने पर यहाँ से लॉग आउट करें। यह गाइड दोबारा देखने के लिए कभी भी "?" दबाएँ।']}];
const UI={en:{next:'Next',back:'Back',skip:'Skip',done:'Done',of:'of',lang:'हिंदी में देखें'},hi:{next:'आगे',back:'पीछे',skip:'छोड़ें',done:'पूरा',of:'/',lang:'View in English'}};
let i=0,L='en',box,card,running=false;
const get=k=>{try{return localStorage.getItem(k)}catch(e){return null}},set=(k,v)=>{try{localStorage.setItem(k,v)}catch(e){}};
const visible=el=>el&&el.offsetParent!==null&&el.getBoundingClientRect().width>0;
function els(){if(box)return;box=document.createElement('div');box.className='tour-spot';card=document.createElement('div');card.className='tour-card';card.setAttribute('role','dialog');document.body.append(box,card);addEventListener('resize',place);addEventListener('scroll',place,true)}
function close(){running=false;box&&box.remove();card&&card.remove();box=card=null;removeEventListener('resize',place);removeEventListener('scroll',place,true)}
function askLang(){els();box.style.display='none';card.className='tour-card center';
 card.innerHTML='<p class="tour-q">Which language are you comfortable in?<br>आप किस भाषा में सहज हैं?</p><div class="tour-btns"><button data-l="en">English</button><button data-l="hi">हिंदी</button></div><button class="tour-x ghost" data-x>✕</button>';
 card.onclick=e=>{const l=e.target.dataset.l;if(l){L=l;set('tour_lang',l);T('tourLang',l);i=0;T('tour','start',1);show()}else if(e.target.dataset.x!==undefined){T('tour','skip',0);set('tour_done','1');close()}}}
async function ensureList(){if(visible($('#q')))return;const s=$('#const');if(!s.value&&s.options.length>1){s.value=s.options[1].value;s.dispatchEvent(new Event('change'))}
 for(let k=0;k<40&&!visible($('.table-wrap'));k++)await new Promise(r=>setTimeout(r,150))}
async function show(){const st=STEPS[i];if(st.need)await ensureList();if(!running)return;let el=$(st.sel);if(!visible(el)){if(i<STEPS.length-1){i++;return show()}}
 el&&el.scrollIntoView({block:'center',behavior:'instant'});const u=UI[L],[h,b]=st[L];card.className='tour-card';box.style.display='';
 card.innerHTML=`<div class="tour-step">${L==='hi'?`${i+1} ${u.of} ${STEPS.length}`:`${i+1} ${u.of} ${STEPS.length}`}</div><h4>${h}</h4><p>${b}</p><div class="tour-btns"><button class="ghost" data-a="skip">${u.skip}</button><span style="flex:1"></span>${i?`<button class="ghost" data-a="back">${u.back}</button>`:''}<button data-a="next">${i===STEPS.length-1?u.done:u.next}</button></div><button class="tour-lang ghost" data-a="lang">${u.lang}</button>`;
 card.onclick=e=>{const a=e.target.dataset.a;if(!a)return;if(a==='next'){if(i===STEPS.length-1){T('tour','complete',i+1);set('tour_done','1');close()}else{i++;show()}}
  else if(a==='back'){i=Math.max(0,i-1);show()}else if(a==='skip'){T('tour','skip',i+1);set('tour_done','1');close()}else if(a==='lang'){L=L==='hi'?'en':'hi';set('tour_lang',L);T('tourLang',L);show()}};
 place();card.querySelector('[data-a=next]').focus({preventScroll:true})}
function place(){if(!running||!box||!card||card.classList.contains('center'))return;const el=$(STEPS[i].sel);if(!visible(el))return;const r=el.getBoundingClientRect(),p=6;
 Object.assign(box.style,{top:r.top-p+'px',left:r.left-p+'px',width:r.width+2*p+'px',height:r.height+2*p+'px'});
 const mob=innerWidth<640,cw=Math.min(340,innerWidth-24),ch=card.offsetHeight;card.style.width=cw+'px';
 if(mob){card.style.left='12px';card.style.width=innerWidth-24+'px';card.style.top=(r.bottom+ch+16<innerHeight?r.bottom+12:Math.max(12,r.top-ch-12))+'px';return}
 let top=r.bottom+12;if(top+ch>innerHeight-8)top=r.top-ch-12;if(top<8)top=Math.max(8,innerHeight-ch-8);
 card.style.top=top+'px';card.style.left=Math.min(Math.max(12,r.left),innerWidth-cw-12)+'px'}
function start(force){if(running)return;running=true;const l=get('tour_lang');
 if(force||!l)askLang();else{L=l;i=0;els();T('tour','start',1);show()}}
// Wait until the location / analytics prompts are gone so nothing overlaps.
function whenClear(fn){const ok=()=>!$('#app-view').classList.contains('hidden')&&$('#geo-notice').classList.contains('hidden')&&$('#const').options.length>1&&!$('#const').disabled;
 const t=setInterval(()=>{if(ok()){clearInterval(t);fn()}},400)}
window.Tour={start,auto(){if(!get('tour_done'))whenClear(()=>{if(!get('tour_done'))start(false)})}};
$('#tour-btn').onclick=()=>{close();start(true)};
document.addEventListener('keydown',e=>{if(running&&e.key==='Escape'){T('tour','skip',i+1);set('tour_done','1');close()}});
})();
