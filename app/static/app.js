const $=s=>document.querySelector(s);let cid='',inst='',page=1,insts=[],total=0;const SIZE=50;
let busy=0;const setBusy=d=>{busy=Math.max(0,busy+d);document.body.classList.toggle('loading',busy>0)};
const api=async(u,o={})=>{setBusy(1);try{const r=await fetch(u,{credentials:'same-origin',...o});if(r.status==401&&u!='/api/login'){show(false);throw 0}
 const t=await r.text();return{ok:r.ok,status:r.status,json:async()=>JSON.parse(t)}}finally{setBusy(-1)}};
const esc=s=>(s??'').toString().replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
function show(a){$('#login-view').classList.toggle('hidden',a);$('#app-view').classList.toggle('hidden',!a);if(a)loadConsts()}
$('#login-form').onsubmit=async e=>{e.preventDefault();$('#login-err').textContent='';
 const r=await api('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:$('#lid').value,password:$('#lpw').value})});
 if(r.ok)show(true);else $('#login-err').textContent='Invalid ID or password'};
$('#logout').onclick=async()=>{await api('/api/logout',{method:'POST'});location.reload()};
async function loadConsts(keep){const cs=await (await api('/api/constituencies')).json();const s=$('#const');
 s.innerHTML='<option value="">Please choose constituency</option>'+cs.map(c=>`<option value="${c.id}">${esc(c.name)} (${c.n})</option>`).join('');s.value=keep||cid}
$('#const').onchange=async e=>{cid=e.target.value;inst='';page=1;$('#q').value='';$('#upload-btn').disabled=!cid;$('#list-area').classList.toggle('hidden',!cid);
 if(!cid)return;insts=await (await api(`/api/constituencies/${cid}/institutions`)).json();setInst('');};
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
 const r=await api(`/api/constituencies/${id}/upload`,{method:'POST',body:fd});const j=await r.json();if(!r.ok){statusEl.textContent=j.error;btn.disabled=false;return}
 const poll=async()=>{const s=await (await fetch('/api/jobs/'+j.job,{credentials:'same-origin'})).json();
  const pct=s.pages?Math.round(100*s.done/s.pages):0;
  statusEl.innerHTML=s.status=='running'?`<span class="spinner inline"></span> Reading PDF: page ${s.done}/${s.pages||'?'} (${pct}%), ${s.added} entries added<progress max="100" value="${pct}"></progress>`
   :s.status=='finished'?`Done: ${s.added} entries added.`:`Error: ${s.error||s.status}`;
  if(s.status=='running')setTimeout(poll,3000);else{btn.disabled=false;done&&done()}};poll()}
function setInst(v){inst=v;page=1;$('#inst-btn').textContent=(v||'All institutions')+' ▾';$('#inst-pop').classList.add('hidden');load()}
function renderInsts(){const f=$('#inst-q').value.toLowerCase();const l=insts.filter(i=>i.institution.toLowerCase().includes(f)).slice(0,300);
 $('#inst-list').innerHTML='<li data-v="">All institutions</li>'+l.map(i=>`<li data-v="${esc(i.institution)}">${esc(i.institution)} (${i.n})</li>`).join('')}
$('#inst-btn').onclick=()=>{$('#inst-pop').classList.toggle('hidden');$('#inst-q').value='';renderInsts();$('#inst-q').focus()};
$('#inst-q').oninput=renderInsts;$('#inst-list').onclick=e=>{if(e.target.dataset.v!==undefined)setInst(e.target.dataset.v)};
document.addEventListener('click',e=>{if(!e.target.closest('.combo'))$('#inst-pop').classList.add('hidden')});
let t;$('#q').oninput=()=>{clearTimeout(t);t=setTimeout(()=>{page=1;load()},300)};
$('#prev').onclick=()=>{if(page>1){page--;load()}};$('#next').onclick=()=>{if(page*SIZE<total){page++;load()}};
let seq=0;async function load(){const my=++seq;const p=new URLSearchParams({q:$('#q').value,page,size:SIZE});if(inst)p.set('institution',inst);
 const d=await (await api(`/api/constituencies/${cid}/voters?${p}`)).json();if(my!==seq)return;total=d.total;
 $('#summary').textContent=`${d.total} voters found`;$('#pg').textContent=`Page ${page} of ${Math.max(1,Math.ceil(total/SIZE))}`;
 $('#rows').innerHTML=d.rows.map(r=>`<tr><td>${esc(r.serial)}</td><td>${esc(r.name)}</td><td>${esc(r.relative_name)}</td><td>${esc(r.relation)}</td><td class="addr">${esc(r.address)}</td><td>${esc(r.gender)}</td><td>${esc(r.dob)}</td><td>${esc(r.institution)}</td><td>${esc(r.state)}</td><td>${esc(r.pincode)}</td></tr>`).join('')}
$('#upload-btn').onclick=()=>{$('#up-name').textContent=$('#const').selectedOptions[0].text;$('#up-status').textContent='';$('#up-dlg').showModal()};
$('#up-go').onclick=e=>{e.preventDefault();startUpload(cid,$('#up-file').files[0],$('#up-replace').checked,$('#up-status'),$('#up-go'),()=>openConst(cid))};
api('/api/me').then(r=>show(r.ok)).catch(()=>{});
