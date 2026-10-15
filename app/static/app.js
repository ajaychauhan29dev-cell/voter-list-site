const $=s=>document.querySelector(s);let cid='',inst='',page=1,insts=[],total=0;const SIZE=50;
const api=async(u,o={})=>{const r=await fetch(u,{credentials:'same-origin',...o});if(r.status==401&&u!='/api/login'){show(false);throw 0}return r};
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
$('#add-const').onclick=async()=>{const n=prompt('New constituency name');if(!n)return;const r=await api('/api/constituencies',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({name:n})});
 if(!r.ok)alert((await r.json()).error);loadConsts()};
function setInst(v){inst=v;page=1;$('#inst-btn').textContent=(v||'All institutions')+' ▾';$('#inst-pop').classList.add('hidden');load()}
function renderInsts(){const f=$('#inst-q').value.toLowerCase();const l=insts.filter(i=>i.institution.toLowerCase().includes(f)).slice(0,300);
 $('#inst-list').innerHTML='<li data-v="">All institutions</li>'+l.map(i=>`<li data-v="${esc(i.institution)}">${esc(i.institution)} (${i.n})</li>`).join('')}
$('#inst-btn').onclick=()=>{$('#inst-pop').classList.toggle('hidden');$('#inst-q').value='';renderInsts();$('#inst-q').focus()};
$('#inst-q').oninput=renderInsts;$('#inst-list').onclick=e=>{if(e.target.dataset.v!==undefined)setInst(e.target.dataset.v)};
document.addEventListener('click',e=>{if(!e.target.closest('.combo'))$('#inst-pop').classList.add('hidden')});
let t;$('#q').oninput=()=>{clearTimeout(t);t=setTimeout(()=>{page=1;load()},300)};
$('#prev').onclick=()=>{if(page>1){page--;load()}};$('#next').onclick=()=>{if(page*SIZE<total){page++;load()}};
async function load(){const p=new URLSearchParams({q:$('#q').value,page,size:SIZE});if(inst)p.set('institution',inst);
 const d=await (await api(`/api/constituencies/${cid}/voters?${p}`)).json();total=d.total;
 $('#summary').textContent=`${d.total} voters found`;$('#pg').textContent=`Page ${page} of ${Math.max(1,Math.ceil(total/SIZE))}`;
 $('#rows').innerHTML=d.rows.map(r=>`<tr><td>${esc(r.serial)}</td><td>${esc(r.name)}</td><td>${esc(r.relative_name)}</td><td>${esc(r.relation)}</td><td class="addr">${esc(r.address)}</td><td>${esc(r.gender)}</td><td>${esc(r.dob)}</td><td>${esc(r.institution)}</td><td>${esc(r.state)}</td><td>${esc(r.pincode)}</td></tr>`).join('')}
$('#upload-btn').onclick=()=>{$('#up-name').textContent=$('#const').selectedOptions[0].text;$('#up-status').textContent='';$('#up-dlg').showModal()};
$('#up-go').onclick=async e=>{e.preventDefault();const f=$('#up-file').files[0];if(!f)return;const fd=new FormData();fd.append('file',f);if($('#up-replace').checked)fd.append('replace','1');
 $('#up-status').textContent='Uploading…';const r=await api(`/api/constituencies/${cid}/upload`,{method:'POST',body:fd});const j=await r.json();if(!r.ok){$('#up-status').textContent=j.error;return}
 const poll=async()=>{const s=await (await api('/api/jobs/'+j.job)).json();$('#up-status').textContent=`${s.status}: page ${s.done}/${s.pages}, ${s.added} entries added`;
  if(s.status=='running')setTimeout(poll,3000);else{loadConsts(cid);$('#const').dispatchEvent(new Event('change'))}};poll()};
api('/api/me').then(r=>show(r.ok)).catch(()=>{});
