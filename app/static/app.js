const T=(...a)=>{try{window.track(...a)}catch(e){}};
const $=s=>document.querySelector(s);let cid='',inst='',page=1,insts=[],total=0;const SIZE=50;
let busy=0;const setBusy=d=>{busy=Math.max(0,busy+d);document.body.classList.toggle('loading',busy>0)};
const api=async(u,o={})=>{setBusy(1);try{const r=await fetch(u,{credentials:'same-origin',...o});if(r.status==401&&u!='/api/login'){show(false);throw 0}
 const t=await r.text();return{ok:r.ok,status:r.status,json:async()=>JSON.parse(t)}}finally{setBusy(-1)}};
const esc=s=>(s??'').toString().replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let LANG=localStorage.getItem('instLang')||'en',HI={};const dn=n=>LANG==='hi'&&HI[n]?HI[n]:n;
const nrm=t=>(t||'').toLowerCase().replace(/([\u0900-\u097f])0/g,'$1 ').replace(/[^a-z0-9\u0900-\u097f]+/g,' ').trim().replace(/\s+/g,' ');
const mrg=t=>t.replace(/\b(\w)\b ?(?=\w\b)/g,'$1');
function lev(a,b){const m=a.length,n=b.length;let p=Array.from({length:n+1},(_,j)=>j);for(let i=1;i<=m;i++){const c=[i];for(let j=1;j<=n;j++)c[j]=Math.min(p[j]+1,c[j-1]+1,p[j-1]+(a[i-1]===b[j-1]?0:1));p=c}return 1-p[n]/Math.max(m,n,1)}
function iscore(nq,v){const ne=nrm(v),ce=ne.replace(/ /g,''),cq=nq.replace(/ /g,'');if(!ce||!cq)return 0;if(ce===cq)return 100;if(ce.startsWith(cq)||ne.startsWith(nq))return 90;
 if(cq.length>=3&&ne.split(' ').some(w=>w.startsWith(cq)))return 85;if(ce.includes(cq))return 80;if(cq.length<4)return 0;
 const qw=mrg(nq).split(' '),ws=mrg(ne).split(' '),k=qw.length;let best=0;
 for(let i=0;i+k<=ws.length;i++){let s=0,ok=true;for(let j=0;j<k;j++){const a=qw[j],b=ws[i+j];let x=a===b?1:a.length<=2?0:b.startsWith(a)?.95:a.length<4?0:lev(a,b);if(x<.75){ok=false;break}s+=x}if(ok)best=Math.max(best,s/k)}
 return best?50+best*20:0}
function setLang(l){LANG=l;localStorage.setItem('instLang',l);$('#lang-btn').textContent=l==='hi'?'संस्थान: हिंदी · EN':'Institutions: EN · हिंदी';
 if(cid){$('#inst-btn').textContent=(inst?dn(inst):'All institutions')+' ▾';if(lastD)renderRows(lastD.rows);if(!$('#inst-pop').classList.contains('hidden'))renderInsts()}}
const dname=id=>{const o=[...$('#const').options].find(o=>o.value==id);return o?o.text.replace(/ \(\d+\)$/,''):''};
let ROLE='';function setRole(r){ROLE=r||'';document.body.classList.toggle('guest',ROLE!=='admin');$('#role-tag').textContent=ROLE==='admin'?'एडमिन · Admin':'अतिथि · Guest'}
function show(a){T('view',a?'app':'login');$('#login-view').classList.toggle('hidden',a);$('#app-view').classList.toggle('hidden',!a);if(a)loadConsts()}
$('#login-form').onsubmit=async e=>{e.preventDefault();$('#login-err').textContent='';
 const r=await api('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:$('#lid').value,password:$('#lpw').value})});
 T('login','admin',r.ok);if(r.ok){setRole('admin');show(true)}else $('#login-err').textContent='Invalid ID or password'};
$('#guest-btn').onclick=async()=>{const r=await api('/api/guest',{method:'POST'});T('login','guest',r.ok);if(r.ok){setRole('guest');show(true)}};
$('#logout').onclick=async()=>{await api('/api/logout',{method:'POST'});location.reload()};
async function loadConsts(keep){const s=$('#const');const first=!s.dataset.loaded;$('#const-err').classList.add('hidden');
 if(first){s.disabled=true;s.innerHTML='<option value="">Loading districts… (ज़िले लोड हो रहे हैं…)</option>';$('#const-spin').classList.remove('hidden')}
 let cs;try{const r=await api('/api/constituencies');if(!r.ok)throw 0;cs=await r.json()}catch(e){T('error','api_districts','load failed');$('#const-spin').classList.add('hidden');
  if(first){s.innerHTML='<option value="">Could not load districts</option>';$('#const-err').classList.remove('hidden')}return}
 $('#const-spin').classList.add('hidden');s.dataset.loaded=1;s.disabled=false;
 s.innerHTML=(cs.length?'<option value="">Please choose District (ज़िला)</option>':'<option value="">No districts yet (कोई ज़िला नहीं)</option>')+cs.map(c=>`<option value="${c.id}">${esc(c.name)} (${c.n})</option>`).join('');s.value=keep||cid}
$('#const-retry').onclick=()=>loadConsts();
$('#const').onchange=async e=>{PC.clear();if(e.target.value&&e.target.value!==cid)T('district',dname(e.target.value),e.target.value);cid=e.target.value;inst='';page=1;$('#q').value='';$('#del-const').disabled=!cid;$('#list-area').classList.toggle('hidden',!cid);
 if(!cid)return;insts=[];HI={};setInst('');const my=cid;const r=await (await api(`/api/constituencies/${cid}/institutions`)).json();if(my===cid){insts=r;r.forEach(i=>{if(i.hi)HI[i.institution]=i.hi});setLang(LANG)}};
let newCid='';
$('#add-const').onclick=()=>{newCid='';$('#add-name').value='';$('#add-err').textContent='';$('#add-status').textContent='';$('#add-file').value='';
 $('#add-step1').classList.remove('hidden');$('#add-step2').classList.add('hidden');$('#add-go').disabled=false;$('#add-dlg').showModal();$('#add-name').focus()};
$('#add-cancel').onclick=()=>$('#add-dlg').close();
$('#add-form').onsubmit=async e=>{e.preventDefault();const n=$('#add-name').value.trim();if(!n)return;
 const r=await api('/api/constituencies',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:n})});const j=await r.json();
 if(!r.ok){$('#add-err').textContent=j.error;return}newCid=String(j.id);$('#add-cname').textContent=n;
 $('#add-step1').classList.add('hidden');$('#add-step2').classList.remove('hidden');await loadConsts()};
async function openConst(id){await loadConsts(id);$('#const').value=id;$('#const').dispatchEvent(new Event('change'))}
$('#add-skip').onclick=()=>{$('#add-dlg').close();openConst(newCid)};
$('#add-go').onclick=()=>startUpload(newCid,$('#add-file').files[0],false,$('#add-status'),$('#add-go'),()=>openConst(newCid));
async function startUpload(id,f,replace,statusEl,btn,done){if(!f){statusEl.textContent='Please choose a PDF file.';return}
 const fd=new FormData();fd.append('file',f);if(replace)fd.append('replace','1');btn.disabled=true;statusEl.innerHTML='<span class="spinner inline"></span> Uploading…';
 const r=await api(`/api/constituencies/${id}/upload`,{method:'POST',body:fd});const j=await r.json();if(!r.ok){T('upload','fail',f.size,dname(id));statusEl.textContent=j.error;btn.disabled=false;return}T('upload','started',f.size,dname(id));
 const poll=async()=>{const s=await (await fetch('/api/jobs/'+j.job,{credentials:'same-origin'})).json();
  const pct=s.pages?Math.round(100*s.done/s.pages):0;
  statusEl.innerHTML=s.status=='running'?`<span class="spinner inline"></span> Reading PDF: page ${s.done}/${s.pages||'?'} (${pct}%), ${s.added} entries added<progress max="100" value="${pct}"></progress>`
   :s.status=='finished'?`Done: ${s.added} entries added.`:`Error: ${s.error||s.status}`;
  if(s.status=='running')setTimeout(poll,3000);else{T('upload',s.status=='finished'?'finished':'error',f.size,dname(id));btn.disabled=false;done&&done()}};poll()}
let instEv=false;function setInst(v){if(v||inst)instEv=true;inst=v;page=1;$('#inst-btn').textContent=(v?dn(v):'All institutions')+' ▾';$('#inst-pop').classList.add('hidden');load()}
let instF=[],instN=0;const CHUNK=200;
function moreInsts(){const l=instF.slice(instN,instN+CHUNK);instN+=l.length;$('#inst-list').insertAdjacentHTML('beforeend',l.map(i=>`<li data-v="${esc(i.institution)}">${esc(dn(i.institution))} (${i.n})</li>`).join(''))}
function renderInsts(){const f=nrm($('#inst-q').value);instF=!f?insts:insts.map(i=>[i,Math.max(iscore(f,i.institution),iscore(f,i.hi||''))]).filter(x=>x[1]>0).sort((a,b)=>b[1]-a[1]).map(x=>x[0]);instN=0;
 $('#inst-list').innerHTML='<li data-v="">All institutions</li>';$('#inst-list').scrollTop=0;moreInsts()}
$('#inst-list').addEventListener('scroll',e=>{const u=e.target;if(instN<instF.length&&u.scrollTop+u.clientHeight>u.scrollHeight-150)moreInsts()});
$('#inst-btn').onclick=()=>{$('#inst-pop').classList.toggle('hidden');$('#inst-q').value='';renderInsts();$('#inst-q').focus()};
$('#inst-q').oninput=renderInsts;$('#inst-list').onclick=e=>{if(e.target.dataset.v!==undefined)setInst(e.target.dataset.v)};
document.addEventListener('click',e=>{if(!e.target.closest('.combo'))$('#inst-pop').classList.add('hidden')});
let t;$('#q').oninput=()=>{clearTimeout(t);t=setTimeout(()=>{page=1;load()},300)};
$('#prev').onclick=()=>{if(page>1){page--;T('page',page,'prev',dname(cid));load()}};$('#next').onclick=()=>{if(page*SIZE<total){page++;T('page',page,'next',dname(cid));load()}};
// Page cache + background prefetch so Next/Prev are instant. Cleared whenever the district changes (incl. after upload/delete).
let PC=new Map();const pkey=(pg,q)=>`${cid}|${inst}|${q}|${pg}`;
function getPage(pg,q,bg){const k=pkey(pg,q);if(PC.has(k))return PC.get(k);const p=new URLSearchParams({q,page:pg,size:SIZE});if(inst)p.set('institution',inst);
 const u=`/api/constituencies/${cid}/voters?${p}`;
 const pr=(bg?fetch(u,{credentials:'same-origin'}).then(r=>{if(!r.ok)throw 0;return r.json()}):api(u).then(r=>{if(!r.ok)throw 0;return r.json()}));
 PC.set(k,pr);pr.catch(()=>PC.delete(k));if(PC.size>200)PC.delete(PC.keys().next().value);return pr}
let seq=0;async function load(){const my=++seq;const q=$('#q').value;
 let d;try{d=await getPage(page,q)}catch(e){if(e!==0)T('error','api_voters',String(e&&e.message||e));return}if(my!==seq)return;
 if(instEv){instEv=false;T('filter',inst,dname(cid),d.total)}
 if(q.trim()&&page===1){const nq=nrm(q);let best=0;for(const i of insts){best=Math.max(best,iscore(nq,i.institution),iscore(nq,i.hi||''));if(best===100)break}
  clearTimeout(window._st);window._st=setTimeout(()=>{if(my===seq)T('search',{q,total:d.total,district:dname(cid),instMatch:best>=80,acronym:best===100})},1200)}
 if(page*SIZE<d.total)getPage(page+1,q,1).catch(()=>{});if(page>1)getPage(page-1,q,1).catch(()=>{});total=d.total;const empty=!total&&!inst&&!$('#q').value.trim();$('#empty').classList.toggle('hidden',!empty);const kw=$('#q').value.trim();const nores=!total&&!empty;
 $('#noresult').textContent=nores?('No entries found'+(kw?` for "${kw}"`:'')+(inst?(kw?' in':' for')+` "${dn(inst)}"`:'')):'';
 $('#noresult').classList.toggle('hidden',!nores);
 document.querySelector('.table-wrap').classList.toggle('hidden',empty||nores);document.querySelector('.pager').classList.toggle('hidden',empty||nores);
 $('#summary').textContent=`${d.total} voters found`;$('#pg').textContent=`Page ${page} of ${Math.max(1,Math.ceil(total/SIZE))}`;
lastD=d;renderRows(d.rows)}
let lastD=null;function renderRows(rows){
 $('#rows').innerHTML=rows.map(r=>`<tr><td>${esc(r.serial)}</td><td>${esc(r.name)}</td><td>${esc(r.relative_name)}</td><td>${esc(r.relation)}</td><td class="addr">${esc(r.address)}</td><td>${esc(r.gender)}</td><td>${esc(r.dob)}</td><td>${esc(dn(r.institution))}</td><td>${esc(r.state)}</td><td>${esc(r.pincode)}</td></tr>`).join('')}
$('#empty-upload').onclick=()=>{$('#up-name').textContent=$('#const').selectedOptions[0].text.replace(/ \(\d+\)$/,'');$('#up-status').textContent='';$('#up-file').value='';$('#up-go').disabled=false;$('#up-dlg').showModal()};
$('#del-const').onclick=()=>{if(!cid)return;$('#del-name').textContent=$('#const').selectedOptions[0].text.replace(/ \(\d+\)$/,'');$('#del-err').textContent='';$('#del-go').disabled=false;$('#del-dlg').showModal()};
$('#del-go').onclick=async()=>{$('#del-go').disabled=true;const r=await api(`/api/constituencies/${cid}`,{method:'DELETE'});
 if(!r.ok){$('#del-err').textContent=(await r.json()).error||'Delete failed';$('#del-go').disabled=false;return}
 $('#del-dlg').close();cid='';$('#list-area').classList.add('hidden');$('#del-const').disabled=true;await loadConsts('')};
$('#up-go').onclick=e=>{e.preventDefault();startUpload(cid,$('#up-file').files[0],$('#up-replace').checked,$('#up-status'),$('#up-go'),()=>openConst(cid))};
api('/api/me').then(async r=>{if(r.ok)setRole((await r.json()).role);show(r.ok)}).catch(()=>{});
$('#lang-btn').onclick=()=>{setLang(LANG==='hi'?'en':'hi');T('lang',LANG)};setLang(LANG);
$('#contact-btn').onclick=e=>{e.preventDefault();const f=$('#contact');f.scrollIntoView({behavior:'smooth',block:'end'});setTimeout(()=>{if(Math.abs(f.getBoundingClientRect().bottom-innerHeight)>4)f.scrollIntoView({block:'end'})},700)};

(()=>{const b=$('#ga-notice');if(!b)return;let v='';try{v=localStorage.getItem('ga_consent')||''}catch(e){}if(!v)b.classList.remove('hidden');
 $('#ga-ok').onclick=()=>{T('consent','granted');b.classList.add('hidden')};$('#ga-no').onclick=()=>{T('consent','denied');try{localStorage.setItem('ga_consent','denied')}catch(e){}b.classList.add('hidden')}})();
