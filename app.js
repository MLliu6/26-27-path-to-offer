'use strict';

const CONFIG = window.PTO_CONFIG || {};
const STORAGE_KEY = 'pathToOffer.v0.2';
const LEGACY_KEY = 'pathToOffer.v0.1';
const THEME_KEY = 'pathToOffer.theme';
const stages = [
  ['discovered','发现'],['wishlist','待投递'],['preparing','准备中'],['applied','已投递'],
  ['assessment','测评'],['interview1','一面'],['interview2','二面'],['interview3','三面/终面'],
  ['hr','HR 面'],['offer','Offer'],['signed','已签约'],['rejected','结束']
];
const palettes = [
  ['Sage','#97b4a7','#668d7b','#e8f0ec'],['Mist Blue','#9db4c5','#66879d','#e9f0f5'],
  ['Dusty Rose','#c7a5a7','#9e7478','#f4eaea'],['Lavender','#b4aac9','#867aa3','#efebf5'],
  ['Oat','#c4b49a','#9b8768','#f3eee5'],['Seafoam','#9ec3bb','#6d9b91','#e8f4f1'],
  ['Clay','#c5a28c','#9f7560','#f5ece6'],['Periwinkle','#a8b1d0','#7883ad','#eceef7'],
  ['Olive Mist','#b1b99a','#858f69','#eff1e8'],['Peach Mist','#d1ad9d','#aa7f6d','#f7ede8']
];

const SKILL_GROUPS = {
  'LLM 推理':['vllm','sglang','tensorrt-llm','pagedattention','kv cache','prefill','decode','continuous batching','speculative decoding','大模型推理','推理系统'],
  'CUDA / GPU':['cuda','triton','cutlass','gemm','tensor core','cublas','nccl','nsight','gpu','算子优化','显存'],
  '量化 / 压缩':['ptq','qat','awq','gptq','smoothquant','int8','int4','fp8','mxfp8','量化','剪枝','蒸馏'],
  'VLM / VLA':['vlm','vla','multimodal','vision-language','qwen-vl','llava','视觉语言','多模态','具身智能'],
  'AI 芯片软件':['npu','compiler','编译器','算子库','runtime','ai chip','芯片软件','hxcc','tvm','mlir'],
  'HPC / 分布式':['hpc','mpi','openmp','rdma','distributed','tensor parallel','pipeline parallel','data parallel','分布式','高性能计算'],
  '深度学习工程':['pytorch','tensorflow','onnx','transformers','huggingface','python','c++','linux','docker','深度学习'],
  'CV':['yolo','opencv','detection','segmentation','目标检测','计算机视觉','图像处理'],
};
const DIRECTION_RULES = [
  ['AI Infra / 推理系统',['LLM 推理','CUDA / GPU','HPC / 分布式']],
  ['CUDA / 算子优化',['CUDA / GPU']],
  ['大模型量化 / 压缩',['量化 / 压缩','LLM 推理']],
  ['VLM / VLA',['VLM / VLA','量化 / 压缩']],
  ['AI 芯片软件',['AI 芯片软件','CUDA / GPU']],
  ['HPC / 异构计算',['HPC / 分布式','CUDA / GPU']],
  ['计算机视觉',['CV','深度学习工程']],
];
const DEGREE_RANK = {'大专':1,'本科':2,'学士':2,'硕士':3,'研究生':3,'博士':4};
const STOPWORDS = new Set(['负责','相关','项目','工作','使用','进行','基于','以及','通过','实现','技术','能力','熟悉','掌握','经验','优化','系统','模型','算法','开发','设计','支持','研究','本科','硕士','北京','上海','深圳','公司']);

const emptyState = () => ({
  schemaVersion: 2,
  jobs: [],
  reviews: [],
  resumes: [],
  activeResumeId: null,
  assets: [],
  decisions: {},
  preferences: {targetLocations:[], targetDirections:[]}
});

let state = loadState();
let marketJobs = [];
let sourceStatus = {generated_at:null,sources:[]};
let selectedReviewId = state.reviews[0]?.id || null;
let pipelineMode = 'board';
let marketMode = 'cards';
let marketSort = 'match';

function loadState(){
  try{
    const current = localStorage.getItem(STORAGE_KEY);
    if(current) return normalizeState(JSON.parse(current));
    const legacyRaw = localStorage.getItem(LEGACY_KEY);
    if(!legacyRaw) return emptyState();
    const legacy = JSON.parse(legacyRaw);
    const clean = emptyState();
    clean.jobs = (legacy.jobs || []).filter(j=>!String(j.company||'').startsWith('示例 ·'));
    clean.reviews = (legacy.reviews || []).filter(r=>!String(r.title||'').startsWith('示例 ·'));
    clean.resumes = (legacy.resumes || []).filter(r=>!['私企版 v7.1','央国企版 v7.1'].includes(r.name));
    clean.assets = (legacy.assets || []).filter(a=>!String(a.name||'').includes('26-27-interview · 面试知识库'));
    localStorage.setItem(STORAGE_KEY, JSON.stringify(clean));
    return clean;
  }catch(err){ console.warn('State load failed',err); return emptyState(); }
}
function normalizeState(s){
  return {...emptyState(), ...s, preferences:{...emptyState().preferences,...(s.preferences||{})}, decisions:s.decisions||{}};
}
function saveState(render=true){ localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); if(render) renderAll(); }
function uid(prefix='id'){ return `${prefix}_${Date.now().toString(36)}_${Math.random().toString(36).slice(2,8)}`; }
function today(){ return new Date().toISOString().slice(0,10); }
function stageName(id){ return stages.find(s=>s[0]===id)?.[1] || id; }
function esc(s=''){ return String(s).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
function fmt(date){ if(!date) return '未记录'; const d=new Date(`${String(date).slice(0,10)}T00:00:00`); return Number.isNaN(d.getTime())?date:d.toLocaleDateString('zh-CN',{month:'numeric',day:'numeric'}); }
function daysAgo(date){ if(!date) return 999; const d=new Date(String(date).slice(0,10)); if(Number.isNaN(d.getTime())) return 999; return Math.max(0,Math.floor((Date.now()-d.getTime())/86400000)); }
function toast(msg){ const el=document.querySelector('#toast'); el.textContent=msg; el.classList.add('show'); clearTimeout(toast.t); toast.t=setTimeout(()=>el.classList.remove('show'),1900); }
function openModal(title,html){ document.querySelector('#modalTitle').textContent=title; document.querySelector('#modalBody').innerHTML=html; document.querySelector('#modalBackdrop').classList.add('show'); document.querySelector('#quickModal').classList.add('show'); document.querySelector('#quickModal').setAttribute('aria-hidden','false'); }
function closeModal(){ document.querySelector('#modalBackdrop').classList.remove('show'); document.querySelector('#quickModal').classList.remove('show'); document.querySelector('#quickModal').setAttribute('aria-hidden','true'); }
function currentProfile(){ return state.resumes.find(r=>r.id===state.activeResumeId) || state.resumes[0] || null; }

function switchView(view){
  document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.id===`${view}View`));
  document.querySelectorAll('.nav-item').forEach(n=>n.classList.toggle('active',n.dataset.view===view));
  window.scrollTo({top:0,behavior:window.matchMedia('(prefers-reduced-motion: reduce)').matches?'auto':'smooth'});
}

async function loadFeeds(){
  const cacheBust = `v=${Date.now()}`;
  try{
    const r=await fetch(`${CONFIG.jobsFeed||'./data/jobs.json'}?${cacheBust}`,{cache:'no-store'});
    if(!r.ok) throw new Error(`HTTP ${r.status}`);
    const payload=await r.json(); marketJobs=(payload.jobs||[]).map(normalizeMarketJob);
  }catch(err){ console.warn('Job feed unavailable',err); marketJobs=[]; }
  try{
    const r=await fetch(`${CONFIG.sourceStatusFeed||'./data/source_status.json'}?${cacheBust}`,{cache:'no-store'});
    if(r.ok) sourceStatus=await r.json();
  }catch(err){ console.warn('Source status unavailable',err); }
  renderDiscovery();
}
function normalizeMarketJob(j){
  return {
    id:j.id||uid('feed'), source:j.source||'public', sourceLabel:j.source_label||j.source||'公开来源',
    sourceUrl:j.source_url||'', company:j.company||'', department:j.department||'', role:j.role||j.position||'',
    location:j.location||'', salary:j.salary||'', batch:j.batch||'', companyType:j.company_type||'', industry:j.industry||'',
    graduation:j.graduation||'', education:j.education||'', updatedAt:j.updated_at||j.date||'', noticeUrl:j.notice_url||'',
    applyUrl:j.apply_url||j.url||'', jd:j.jd||j.description||'', tags:Array.isArray(j.tags)?j.tags:[]
  };
}

async function handleResumeFile(file){
  if(!file) return;
  const ext=(file.name.split('.').pop()||'').toLowerCase();
  if(!['pdf','docx','txt'].includes(ext)){ toast('仅支持 PDF / DOCX / TXT'); return; }
  toast('正在本地解析简历…');
  try{
    const text=await extractResumeText(file,ext);
    if(!text || text.trim().length<30) throw new Error('未提取到足够文本');
    const profile=buildResumeProfile(text,file.name);
    state.resumes.unshift(profile);
    state.activeResumeId=profile.id;
    saveState(false);
    renderAll();
    toast(`已解析 ${profile.signals.skills.length} 个技能信号`);
  }catch(err){ console.error(err); toast(`解析失败：${err.message||'文件格式异常'}`); }
}
async function extractResumeText(file,ext){
  if(ext==='txt') return await file.text();
  const buf=await file.arrayBuffer();
  if(ext==='docx'){
    if(!window.mammoth) throw new Error('DOCX 解析器尚未加载');
    const result=await mammoth.extractRawText({arrayBuffer:buf}); return result.value;
  }
  if(ext==='pdf'){
    if(!window.pdfjsLib) throw new Error('PDF 解析器尚未加载');
    pdfjsLib.GlobalWorkerOptions.workerSrc='https://cdn.jsdelivr.net/npm/pdfjs-dist@3.11.174/build/pdf.worker.min.js';
    const pdf=await pdfjsLib.getDocument({data:new Uint8Array(buf)}).promise;
    const pages=[];
    for(let i=1;i<=pdf.numPages;i++){
      const page=await pdf.getPage(i); const content=await page.getTextContent();
      pages.push(content.items.map(x=>x.str).join(' '));
    }
    return pages.join('\n');
  }
  return '';
}
function buildResumeProfile(rawText,fileName){
  const text=rawText.replace(/\u0000/g,' ').replace(/[ \t]+/g,' ').replace(/\n{3,}/g,'\n\n').trim().slice(0,140000);
  const lower=text.toLowerCase();
  const groupScores={}; const skills=[];
  for(const [group,terms] of Object.entries(SKILL_GROUPS)){
    const hits=terms.filter(t=>lower.includes(t.toLowerCase()));
    if(hits.length){ groupScores[group]=hits.length; skills.push(...hits.map(x=>x.length<=6?x:x)); }
  }
  const directions=DIRECTION_RULES.map(([name,groups])=>({name,score:groups.reduce((s,g)=>s+(groupScores[g]||0),0)})).filter(x=>x.score>0).sort((a,b)=>b.score-a.score).slice(0,4).map(x=>x.name);
  const degree=Object.keys(DEGREE_RANK).filter(d=>text.includes(d)).sort((a,b)=>DEGREE_RANK[b]-DEGREE_RANK[a])[0]||'';
  const years=[...new Set((text.match(/20(?:2[4-9]|3\d)/g)||[]))].sort();
  const cities=['北京','上海','深圳','广州','杭州','南京','成都','武汉','西安','苏州','天津','重庆','长沙','合肥','无锡','厦门','青岛','济南','宁波','东莞'].filter(c=>text.includes(c));
  const tokens=extractKeywords(text);
  const lines=text.split(/\n/).map(x=>x.trim()).filter(Boolean);
  let displayName=fileName.replace(/\.(pdf|docx|txt)$/i,'');
  const probable=lines.slice(0,5).find(x=>/^[\u4e00-\u9fa5·]{2,5}$/.test(x)); if(probable) displayName=probable;
  return {id:uid('resume'), name:fileName.replace(/\.(pdf|docx|txt)$/i,''), fileName, displayName, uploadedAt:new Date().toISOString(), rawText:text,
    signals:{skills:[...new Set(skills)].slice(0,32), groups:groupScores, directions, degree, years, mentionedCities:cities.slice(0,12), keywords:tokens.slice(0,40)}};
}
function extractKeywords(text){
  const latin=(text.toLowerCase().match(/[a-z][a-z0-9+.#-]{1,24}/g)||[]).filter(x=>!['and','the','with','from','using','for','of','to','in','on'].includes(x));
  const chinese=(text.match(/[\u4e00-\u9fa5]{2,8}/g)||[]).filter(x=>!STOPWORDS.has(x));
  const freq=new Map(); [...latin,...chinese].forEach(w=>freq.set(w,(freq.get(w)||0)+1));
  return [...freq.entries()].sort((a,b)=>b[1]-a[1]).map(x=>x[0]);
}

function scoreJob(job,profile){
  if(!profile) return {score:null,reasons:[],hits:[]};
  const text=[job.role,job.jd,job.industry,job.tags.join(' '),job.company].join(' ').toLowerCase();
  const signals=profile.signals||{};
  const skillHits=(signals.skills||[]).filter(s=>text.includes(String(s).toLowerCase()));
  const keywordHits=(signals.keywords||[]).filter(s=>String(s).length>2 && text.includes(String(s).toLowerCase())).slice(0,8);
  const directionHits=(signals.directions||[]).filter(d=>directionMatchesJob(d,text));
  let score=0; const reasons=[];
  const skillScore=Math.min(48,skillHits.length*7 + Math.min(10,keywordHits.length*2)); score+=skillScore;
  if(skillHits.length) reasons.push(`技能 ${skillHits.slice(0,3).join(' · ')}`);
  if(directionHits.length){ score+=20; reasons.push(directionHits[0]); }
  const prefDirs=state.preferences.targetDirections||[];
  if(prefDirs.some(d=>directionMatchesJob(d,text))){score+=8;reasons.push('目标方向');}
  const prefLocs=state.preferences.targetLocations||[];
  if(prefLocs.length && prefLocs.some(c=>job.location.includes(c))){score+=8;reasons.push('目标城市');}
  if(document.querySelector('#matchDegree')?.checked && signals.degree && job.education){
    const need=Object.keys(DEGREE_RANK).find(d=>job.education.includes(d));
    if(need){ if((DEGREE_RANK[signals.degree]||0)>=(DEGREE_RANK[need]||0)){score+=7;reasons.push('学历符合');} else score-=8; }
  }
  if(document.querySelector('#matchGrad')?.checked && job.graduation && (signals.years||[]).some(y=>job.graduation.includes(y))){score+=5;reasons.push('届别符合');}
  const age=daysAgo(job.updatedAt); if(age<=7) score+=8; else if(age<=30) score+=5; else if(age<=60) score+=2;
  if(state.decisions[job.id]==='saved') score+=2;
  return {score:Math.max(0,Math.min(99,Math.round(score))),reasons:[...new Set(reasons)].slice(0,4),hits:[...new Set([...skillHits,...keywordHits])].slice(0,8)};
}
function directionMatchesJob(direction,text){
  const rule=DIRECTION_RULES.find(x=>x[0]===direction); if(!rule) return text.includes(direction.toLowerCase());
  const terms=rule[1].flatMap(g=>SKILL_GROUPS[g]||[]); return terms.some(t=>text.includes(t.toLowerCase()));
}
function visibleMarketJobs(){
  const q=(document.querySelector('#jobSearch')?.value||'').trim().toLowerCase();
  const loc=document.querySelector('#jobLocationFilter')?.value||'all';
  const typ=document.querySelector('#jobTypeFilter')?.value||'all';
  const batch=document.querySelector('#jobBatchFilter')?.value||'all';
  const threshold=Number(document.querySelector('#scoreThreshold')?.value||0);
  const freshOnly=!!document.querySelector('#freshOnly')?.checked;
  const profile=currentProfile();
  let rows=marketJobs.map(job=>({...job,match:scoreJob(job,profile)})).filter(j=>state.decisions[j.id]!=='hidden');
  rows=rows.filter(j=>(loc==='all'||j.location.includes(loc))&&(typ==='all'||j.companyType===typ)&&(batch==='all'||j.batch===batch));
  if(q) rows=rows.filter(j=>[j.company,j.role,j.location,j.industry,j.jd,j.tags.join(' ')].join(' ').toLowerCase().includes(q));
  if(profile) rows=rows.filter(j=>(j.match.score??0)>=threshold);
  if(freshOnly && rows.some(j=>j.updatedAt)) rows=rows.filter(j=>!j.updatedAt||daysAgo(j.updatedAt)<=30);
  if(marketSort==='match') rows.sort((a,b)=>(b.match.score??-1)-(a.match.score??-1)||String(b.updatedAt).localeCompare(String(a.updatedAt)));
  if(marketSort==='fresh') rows.sort((a,b)=>String(b.updatedAt).localeCompare(String(a.updatedAt)));
  if(marketSort==='company') rows.sort((a,b)=>a.company.localeCompare(b.company,'zh-CN'));
  return rows;
}

function renderDiscovery(){
  renderProfile(); renderFeedHealth(); renderMarketFilters(); renderMarket();
}
function renderProfile(){
  const p=currentProfile();
  document.querySelector('#resumeOnboarding').classList.toggle('hidden',!!p);
  document.querySelector('#profileStrip').classList.toggle('hidden',!p);
  if(!p) return;
  document.querySelector('#profileName').textContent=p.displayName||p.name;
  const s=p.signals||{};
  document.querySelector('#profileMeta').textContent=[s.degree, (s.years||[]).length?`${s.years.join('/')} 届别信号`:'', `${p.rawText?.length||0} 字符已解析`].filter(Boolean).join(' · ');
  const chips=[...(s.directions||[]).slice(0,3),...(s.skills||[]).slice(0,5)];
  document.querySelector('#profileSignals').innerHTML=chips.length?chips.map(x=>`<span class="signal-chip">${esc(x)}</span>`).join(''):'<span class="muted">暂未识别到明确技术信号，可在画像中补充偏好。</span>';
}
function renderFeedHealth(){
  const el=document.querySelector('#feedHealth'); const sources=sourceStatus.sources||[]; const ok=sources.filter(s=>s.ok).length;
  if(!sourceStatus.generated_at){ el.innerHTML='<span class="pulse-dot warn"></span><span>岗位源尚未产生首轮数据</span>'; return; }
  const when=new Date(sourceStatus.generated_at); const label=Number.isNaN(when.getTime())?sourceStatus.generated_at:when.toLocaleString('zh-CN',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'});
  el.innerHTML=`<span class="pulse-dot ${ok?'':'warn'}"></span><span>${esc(label)} 刷新 · ${ok}/${sources.length} 个源正常</span>`;
}
function uniqValues(key){ return [...new Set(marketJobs.map(j=>j[key]).filter(Boolean))].sort((a,b)=>a.localeCompare(b,'zh-CN')); }
function fillSelect(id,values,label){ const el=document.querySelector(id); if(!el) return; const old=el.value; el.innerHTML=`<option value="all">${label}</option>`+values.slice(0,120).map(v=>`<option value="${esc(v)}">${esc(v)}</option>`).join(''); if([...el.options].some(o=>o.value===old))el.value=old; }
function renderMarketFilters(){
  const locations=[...new Set(marketJobs.flatMap(j=>String(j.location).split(/[ ,，、/]+/).filter(x=>x.length>=2&&x.length<=6)))].sort((a,b)=>a.localeCompare(b,'zh-CN'));
  fillSelect('#jobLocationFilter',locations,'全部地点'); fillSelect('#jobTypeFilter',uniqValues('companyType'),'全部企业性质'); fillSelect('#jobBatchFilter',uniqValues('batch'),'全部批次');
}
function renderMarket(){
  const rows=visibleMarketJobs(); const p=currentProfile();
  document.querySelector('#marketCount').textContent=rows.length;
  const empty=document.querySelector('#jobMarketEmpty');
  if(!marketJobs.length){
    empty.classList.remove('hidden');
    empty.innerHTML=`<div class="empty-orbit">⌁</div><h3>岗位聚合源目前是空的</h3><p>仓库已配置每 2 小时刷新器。首轮 Actions 成功后，公开岗位会出现在这里；不会用虚构职位填充页面。</p><button class="text-btn" id="emptySourcesBtn">查看岗位源状态 →</button>`;
    document.querySelector('#jobMarketCards').innerHTML=''; document.querySelector('#jobMarketTable').innerHTML=''; document.querySelector('#emptySourcesBtn').onclick=showSources; return;
  }
  if(!p){
    empty.classList.remove('hidden'); empty.innerHTML='<div class="empty-orbit">CV</div><h3>职位源已就绪，先上传简历再排序</h3><p>未建立候选人画像时只提供普通搜索，不生成伪装成 AI 的匹配分数。</p>';
  }else if(!rows.length){
    empty.classList.remove('hidden'); empty.innerHTML='<div class="empty-orbit">0</div><h3>当前筛选没有命中</h3><p>降低最低匹配度、关闭“30 天内”，或调整目标方向与城市。</p>';
  }else empty.classList.add('hidden');
  const cards=document.querySelector('#jobMarketCards');
  cards.innerHTML=rows.map(marketJobCard).join('');
  cards.classList.toggle('hidden',marketMode!=='cards');
  const table=document.querySelector('#jobMarketTable'); table.classList.toggle('hidden',marketMode!=='table');
  table.innerHTML=marketJobTable(rows);
  document.querySelectorAll('[data-market-id]').forEach(el=>el.addEventListener('click',e=>{ if(e.target.closest('[data-action]'))return; openMarketJob(el.dataset.marketId); }));
  document.querySelectorAll('[data-save-job]').forEach(b=>b.onclick=e=>{e.stopPropagation(); promoteMarketJob(b.dataset.saveJob);});
  document.querySelectorAll('[data-hide-job]').forEach(b=>b.onclick=e=>{e.stopPropagation(); state.decisions[b.dataset.hideJob]='hidden';saveState(false);renderMarket();toast('已隐藏该岗位');});
}
function marketJobCard(j){
  const m=j.match; const score=m.score;
  return `<article class="market-card" data-market-id="${esc(j.id)}"><div class="market-card-top"><div class="company-logo">${esc((j.company||'?').slice(0,1))}</div><div class="market-card-title"><h3>${esc(j.role||'未命名岗位')}</h3><p>${esc(j.company||'未知公司')}</p></div>${score===null?'':`<div class="match-score ${score>=75?'high':score>=55?'mid':'low'}"><strong>${score}</strong><small>match</small></div>`}</div><div class="job-facts">${[j.location,j.batch,j.companyType,j.education,j.graduation].filter(Boolean).slice(0,5).map(x=>`<span>${esc(x)}</span>`).join('')}</div>${m.reasons.length?`<div class="match-reasons">${m.reasons.map(x=>`<span>${esc(x)}</span>`).join('')}</div>`:''}<div class="market-card-foot"><span class="source-tag">${esc(j.sourceLabel)}</span><span class="muted">${j.updatedAt?`${fmt(j.updatedAt)} 更新`:'更新时间未知'}</span><div class="card-spacer"></div><button class="text-btn quiet" data-action="hide" data-hide-job="${esc(j.id)}">不合适</button><button class="btn tiny primary" data-action="save" data-save-job="${esc(j.id)}">加入流程</button></div></article>`;
}
function marketJobTable(rows){
  return `<table class="job-table market-table"><thead><tr><th>匹配</th><th>企业</th><th>岗位</th><th>地点</th><th>批次</th><th>企业性质</th><th>届别</th><th>更新</th><th></th></tr></thead><tbody>${rows.map(j=>`<tr data-market-id="${esc(j.id)}"><td><strong>${j.match.score??'—'}</strong></td><td>${esc(j.company)}</td><td>${esc(j.role)}</td><td>${esc(j.location)}</td><td>${esc(j.batch)}</td><td>${esc(j.companyType)}</td><td>${esc(j.graduation)}</td><td>${fmt(j.updatedAt)}</td><td><button class="text-btn" data-action="save" data-save-job="${esc(j.id)}">加入流程</button></td></tr>`).join('')}</tbody></table>`;
}
function openMarketJob(id){
  const j=marketJobs.find(x=>x.id===id); if(!j)return; const m=scoreJob(j,currentProfile());
  document.querySelector('#drawerEyebrow').textContent='DISCOVERED JOB'; document.querySelector('#drawerTitle').textContent=j.company||'岗位详情';
  document.querySelector('#jobForm').classList.add('hidden'); const detail=document.querySelector('#marketJobDetail'); detail.classList.remove('hidden');
  detail.innerHTML=`<div class="detail-hero"><div><p class="eyebrow">${esc(j.sourceLabel)} · ${j.updatedAt?esc(fmt(j.updatedAt)):'更新时间未知'}</p><h2>${esc(j.role)}</h2><p>${esc(j.company)}${j.department?` · ${esc(j.department)}`:''}</p></div>${m.score===null?'':`<div class="detail-score"><strong>${m.score}</strong><span>简历匹配</span></div>`}</div><div class="detail-facts">${[['地点',j.location],['薪资',j.salary],['批次',j.batch],['性质',j.companyType],['行业',j.industry],['届别',j.graduation],['学历',j.education]].filter(x=>x[1]).map(([a,b])=>`<div><small>${a}</small><strong>${esc(b)}</strong></div>`).join('')}</div>${m.reasons.length?`<section class="detail-section"><p class="eyebrow">WHY THIS MATCH</p><div class="reason-grid">${m.reasons.map(x=>`<span>${esc(x)}</span>`).join('')}</div></section>`:''}<section class="detail-section"><p class="eyebrow">JOB DESCRIPTION</p><div class="jd-text">${esc(j.jd||'职位源暂未提供完整 JD。')}</div></section><div class="detail-actions">${j.noticeUrl?`<a class="btn ghost" target="_blank" rel="noopener" href="${esc(j.noticeUrl)}">招聘公告 ↗</a>`:''}${j.applyUrl?`<a class="btn ghost" target="_blank" rel="noopener" href="${esc(j.applyUrl)}">投递地址 ↗</a>`:''}<button class="btn primary" id="detailPromote">加入我的流程</button></div>`;
  document.querySelector('#detailPromote').onclick=()=>promoteMarketJob(j.id,true); openDrawer();
}
function promoteMarketJob(id,close=false){
  const j=marketJobs.find(x=>x.id===id); if(!j)return;
  if(state.jobs.some(x=>x.sourceJobId===j.id)){toast('这个岗位已经在流程里');return;}
  const match=scoreJob(j,currentProfile()); const p=currentProfile();
  state.jobs.unshift({id:uid('job'),sourceJobId:j.id,source:j.source,company:j.company,department:j.department,role:j.role,location:j.location,salary:j.salary,direction:match.reasons.find(x=>DIRECTION_RULES.some(r=>r[0]===x))||'',priority:match.score!==null&&match.score>=78?'A':'B',status:'discovered',statusDate:today(),url:j.applyUrl||j.noticeUrl,jd:j.jd,resumeVersion:p?.name||'',prepUrl:'',notes:'',matchAtSave:match.score,timeline:[{status:'discovered',date:today()}]});
  state.decisions[id]='saved'; saveState(false); renderAll(); if(close)closeDrawer(); toast('已加入投递流程');
}

function filteredPipelineJobs(){
  const q=(document.querySelector('#pipelineSearch')?.value||'').trim().toLowerCase(); const p=document.querySelector('#priorityFilter')?.value||'all'; const d=document.querySelector('#directionFilter')?.value||'all';
  return state.jobs.filter(j=>(p==='all'||j.priority===p)&&(d==='all'||j.direction===d)&&(!q||[j.company,j.role,j.location,j.direction].join(' ').toLowerCase().includes(q)));
}
function renderDirectionFilter(){ const el=document.querySelector('#directionFilter'); const old=el.value; const values=[...new Set(state.jobs.map(j=>j.direction).filter(Boolean))]; el.innerHTML='<option value="all">全部方向</option>'+values.map(x=>`<option>${esc(x)}</option>`).join(''); if(values.includes(old))el.value=old; }
function pipelineCard(j){ return `<article class="job-card" draggable="true" data-job-id="${j.id}"><div class="job-meta"><span class="priority">${esc(j.priority)}</span><span class="date">${fmt(j.statusDate)}</span></div><h3>${esc(j.company)}</h3><p>${esc(j.role)}</p><div class="job-meta"><span class="date">${esc(j.location||'地点待定')}</span>${j.matchAtSave!=null?`<span class="date">match ${j.matchAtSave}</span>`:''}</div></article>`; }
function renderPipeline(){
  renderDirectionFilter(); const jobs=filteredPipelineJobs(); const empty=document.querySelector('#pipelineEmpty');
  empty.classList.toggle('hidden',state.jobs.length>0); if(!state.jobs.length) empty.innerHTML='<div class="empty-orbit">→</div><h3>还没有岗位进入流程</h3><p>去“发现”页上传简历并选择岗位，或点击右上角“记录岗位”手工添加。</p><button class="btn primary" data-empty-go="discover">开始发现岗位</button>';
  empty.querySelector('[data-empty-go]')?.addEventListener('click',()=>switchView('discover'));
  const kanban=document.querySelector('#kanban'); kanban.classList.toggle('hidden',pipelineMode!=='board'||!state.jobs.length);
  kanban.innerHTML=stages.map(([id,name])=>{const list=jobs.filter(j=>j.status===id);return `<section class="kanban-col" data-stage="${id}"><div class="kanban-head"><strong>${name}</strong><span class="count">${list.length}</span></div><div class="job-stack">${list.map(pipelineCard).join('')}</div></section>`}).join('');
  const table=document.querySelector('#jobTableWrap'); table.classList.toggle('hidden',pipelineMode!=='table'||!state.jobs.length); table.innerHTML=`<table class="job-table"><thead><tr><th>公司</th><th>岗位</th><th>方向</th><th>状态</th><th>日期</th><th>优先级</th><th>初始匹配</th></tr></thead><tbody>${jobs.map(j=>`<tr data-job-id="${j.id}"><td>${esc(j.company)}</td><td>${esc(j.role)}</td><td>${esc(j.direction)}</td><td>${stageName(j.status)}</td><td>${fmt(j.statusDate)}</td><td>${esc(j.priority)}</td><td>${j.matchAtSave??'—'}</td></tr>`).join('')}</tbody></table>`;
  bindDnD(); document.querySelectorAll('[data-job-id]').forEach(el=>el.addEventListener('click',e=>{if(!e.defaultPrevented)openJob(el.dataset.jobId)}));
}
function bindDnD(){ let dragging=null; document.querySelectorAll('.job-card').forEach(card=>{card.addEventListener('dragstart',e=>{dragging=card.dataset.jobId;card.classList.add('dragging');e.dataTransfer.effectAllowed='move'});card.addEventListener('dragend',()=>card.classList.remove('dragging'))}); document.querySelectorAll('.kanban-col').forEach(col=>{col.addEventListener('dragover',e=>e.preventDefault());col.addEventListener('drop',e=>{e.preventDefault();const job=state.jobs.find(j=>j.id===dragging);const next=col.dataset.stage;if(job&&job.status!==next){job.status=next;job.statusDate=today();job.timeline=job.timeline||[];job.timeline.push({status:next,date:today()});saveState();toast(`已更新为「${stageName(next)}」`)}})}); }

function openDrawer(){ document.querySelector('#drawerBackdrop').classList.add('show');document.querySelector('#jobDrawer').classList.add('open');document.querySelector('#jobDrawer').setAttribute('aria-hidden','false'); }
function closeDrawer(){ document.querySelector('#drawerBackdrop').classList.remove('show');document.querySelector('#jobDrawer').classList.remove('open');document.querySelector('#jobDrawer').setAttribute('aria-hidden','true'); }
function openJob(id=null){
  const form=document.querySelector('#jobForm'); document.querySelector('#marketJobDetail').classList.add('hidden'); form.classList.remove('hidden');
  document.querySelector('#drawerEyebrow').textContent='JOB RECORD'; document.querySelector('#drawerTitle').textContent=id?'岗位详情':'记录岗位'; form.reset(); form.id.value=id||'';
  document.querySelector('#statusSelect').innerHTML=stages.map(([v,n])=>`<option value="${v}">${n}</option>`).join('');
  const resumeSelect=document.querySelector('#jobResumeSelect'); resumeSelect.innerHTML='<option value="">未绑定</option>'+state.resumes.map(r=>`<option value="${esc(r.name)}">${esc(r.name)}</option>`).join('');
  const job=state.jobs.find(j=>j.id===id); if(job){ Object.entries(job).forEach(([k,v])=>{if(form.elements[k]&&typeof v!=='object')form.elements[k].value=v??'';}); }
  else {form.status.value='discovered';form.statusDate.value=today();form.priority.value='B';if(currentProfile())form.resumeVersion.value=currentProfile().name;}
  renderTimeline(job); document.querySelector('#deleteJobBtn').classList.toggle('hidden',!job); openDrawer();
}
function renderTimeline(job){ const el=document.querySelector('#statusTimeline'); const tl=job?.timeline||[]; el.innerHTML=tl.length?tl.slice().reverse().map(x=>`<div class="timeline-row"><span></span><strong>${stageName(x.status)}</strong><small>${fmt(x.date)}</small></div>`).join(''):'<div class="empty-state compact-empty"><p>保存后开始记录状态时间线。</p></div>'; }
function submitJob(e){ e.preventDefault(); const fd=new FormData(e.currentTarget); const data=Object.fromEntries(fd.entries()); let job=state.jobs.find(j=>j.id===data.id); if(job){const prev=job.status;Object.assign(job,data);if(prev!==data.status){job.timeline=job.timeline||[];job.timeline.push({status:data.status,date:data.statusDate||today()});}}else{job={...data,id:uid('job'),timeline:[{status:data.status,date:data.statusDate||today()}]};state.jobs.unshift(job);}saveState();closeDrawer();toast('岗位已保存'); }

function renderLibrary(){
  const p=currentProfile(); const list=document.querySelector('#resumeList');
  list.innerHTML=state.resumes.length?state.resumes.map(r=>`<div class="asset-item resume-item ${r.id===p?.id?'active':''}"><div><div class="asset-title"><strong>${esc(r.name)}</strong>${r.id===p?.id?'<span class="mini-badge">当前</span>':''}</div><small>${esc((r.signals?.directions||[]).slice(0,2).join(' · ')||'未识别方向')} · ${new Date(r.uploadedAt).toLocaleDateString('zh-CN')}</small></div><div class="asset-actions"><button class="text-btn" data-use-resume="${r.id}">设为当前</button><button class="text-btn quiet" data-delete-resume="${r.id}">删除</button></div></div>`).join(''):'<div class="empty-state"><strong>还没有简历版本</strong><p>上传 PDF / DOCX / TXT 后会自动建立解析画像。</p></div>';
  document.querySelectorAll('[data-use-resume]').forEach(b=>b.onclick=()=>{state.activeResumeId=b.dataset.useResume;saveState();toast('已切换当前简历')});
  document.querySelectorAll('[data-delete-resume]').forEach(b=>b.onclick=()=>{const id=b.dataset.deleteResume;state.resumes=state.resumes.filter(r=>r.id!==id);if(state.activeResumeId===id)state.activeResumeId=state.resumes[0]?.id||null;saveState();});
  const assets=document.querySelector('#assetList'); assets.innerHTML=state.assets.length?state.assets.map((a,i)=>`<div class="asset-item"><div><strong>${esc(a.name)}</strong><small>${esc(a.note||a.url||'')}</small></div><div class="asset-actions"><a class="text-btn" href="${esc(a.url)}" target="_blank" rel="noopener">打开 ↗</a><button class="text-btn quiet" data-delete-asset="${i}">删除</button></div></div>`).join(''):`<div class="empty-state"><strong>资料区目前为空</strong><p>可添加 GitHub、Notion、语雀或其他准备材料。你的 26-27-interview 仓库入口保留在标题栏。</p></div>`;
  document.querySelectorAll('[data-delete-asset]').forEach(b=>b.onclick=()=>{state.assets.splice(Number(b.dataset.deleteAsset),1);saveState();});
}

function renderReviews(){
  const list=document.querySelector('#reviewList'); list.innerHTML=state.reviews.length?state.reviews.slice().sort((a,b)=>String(b.date).localeCompare(String(a.date))).map(r=>`<article class="review-card ${r.id===selectedReviewId?'active':''}" data-review-id="${r.id}"><p class="eyebrow">${fmt(r.date)}</p><h3>${esc(r.title)}</h3><small>${r.content.length} 字符</small></article>`).join(''):'<div class="empty-state"><strong>还没有面经</strong><p>导入 TXT / DOCX 后会保存在当前浏览器。</p></div>';
  document.querySelectorAll('[data-review-id]').forEach(c=>c.onclick=()=>{selectedReviewId=c.dataset.reviewId;renderReviews();}); const r=state.reviews.find(x=>x.id===selectedReviewId); const empty=document.querySelector('#reviewEmpty'); const content=document.querySelector('#reviewContent'); empty.classList.toggle('hidden',!!r); content.classList.toggle('hidden',!r);
  if(r){const job=state.jobs.find(j=>j.id===r.jobId);content.innerHTML=`<div class="panel-head"><div><p class="eyebrow">${job?esc(job.company):'INTERVIEW REVIEW'}</p><h2>${esc(r.title)}</h2></div><button class="text-btn quiet" id="deleteReview">删除</button></div><p class="muted">${fmt(r.date)}</p><pre>${esc(r.content)}</pre>`;document.querySelector('#deleteReview').onclick=()=>{state.reviews=state.reviews.filter(x=>x.id!==r.id);selectedReviewId=state.reviews[0]?.id||null;saveState();};}
}
async function importReview(file){ if(!file)return; const ext=(file.name.split('.').pop()||'').toLowerCase(); try{let text='';if(ext==='txt')text=await file.text();else if(ext==='docx'&&window.mammoth){const result=await mammoth.extractRawText({arrayBuffer:await file.arrayBuffer()});text=result.value;}else throw new Error('仅支持 TXT / DOCX');const review={id:uid('review'),jobId:'',title:file.name.replace(/\.(txt|docx)$/i,''),date:today(),content:text};state.reviews.unshift(review);selectedReviewId=review.id;saveState();toast('面经已导入');}catch(err){toast(err.message||'导入失败');} }

function renderInsights(){
  const applied=state.jobs.filter(j=>!['discovered','wishlist','preparing'].includes(j.status)).length; const interviews=state.jobs.filter(j=>['interview1','interview2','interview3','hr','offer','signed'].includes(j.status)).length; const offers=state.jobs.filter(j=>['offer','signed'].includes(j.status)).length;
  const metrics=[['已选择',state.jobs.length,'加入个人流程'],['已投递',applied,'进入正式申请'],['面试',interviews,'至少进入一面'],['Offer',offers,'收到 / 已签']]; document.querySelector('#metricGrid').innerHTML=metrics.map(([k,v,s])=>`<article class="metric"><p class="eyebrow">${k}</p><div class="value">${v}</div><small>${s}</small></article>`).join('');
  const rows=[['已选择',state.jobs.length],['已投递',applied],['进入面试',interviews],['Offer',offers]]; const max=Math.max(1,...rows.map(r=>r[1])); document.querySelector('#funnel').innerHTML=rows.map(([n,v])=>`<div class="funnel-row"><span>${n}</span><div class="funnel-track"><div class="funnel-fill" style="width:${v/max*100}%"></div></div><strong>${v}</strong></div>`).join('');
  const cycles=state.jobs.map(j=>{const a=j.timeline?.find(x=>x.status==='applied');const i=j.timeline?.find(x=>['interview1','interview2','interview3','hr'].includes(x.status));if(!a||!i)return null;return Math.max(0,Math.round((new Date(i.date)-new Date(a.date))/86400000));}).filter(x=>x!=null); const avg=cycles.length?Math.round(cycles.reduce((a,b)=>a+b,0)/cycles.length):null; document.querySelector('#cycleMetric').innerHTML=avg===null?'<div class="big">—</div><p>还没有足够的“投递 → 面试”时间线样本。</p>':`<div class="big">${avg}<small> 天</small></div><p>平均从投递到首次进入面试。</p>`;
  const withMatch=state.jobs.filter(j=>j.matchAtSave!=null); const interviewed=withMatch.filter(j=>['interview1','interview2','interview3','hr','offer','signed'].includes(j.status)); document.querySelector('#matchFeedback').innerHTML=withMatch.length<3?'<div class="empty-state"><strong>样本不足</strong><p>至少积累 3 个带初始匹配分的岗位后，再分析匹配分与实际面邀之间的关系，避免用小样本制造结论。</p></div>':`<div class="feedback-sentence">已记录 <strong>${withMatch.length}</strong> 个匹配岗位，其中 <strong>${interviewed.length}</strong> 个进入面试。随着样本增加，这里会比较不同匹配区间的转化率。</div>`;
}

function inspectProfile(){
  const p=currentProfile(); if(!p)return; const s=p.signals||{};
  openModal('候选人画像',`<div class="profile-inspector"><div class="profile-summary"><strong>${esc(p.name)}</strong><small>${esc(s.degree||'学历未识别')} · ${(s.years||[]).join('/')||'届别未识别'}</small></div><label><span>目标方向（逗号分隔）</span><input id="prefDirections" value="${esc((state.preferences.targetDirections||s.directions||[]).join(', '))}"></label><label><span>目标城市（逗号分隔）</span><input id="prefLocations" value="${esc((state.preferences.targetLocations||[]).join(', '))}" placeholder="北京, 上海, 深圳"></label><div><p class="eyebrow">SKILL SIGNALS</p><div class="signal-cloud">${(s.skills||[]).map(x=>`<span>${esc(x)}</span>`).join('')||'<span>暂无</span>'}</div></div><div><p class="eyebrow">DIRECTION INFERENCE</p><div class="signal-cloud">${(s.directions||[]).map(x=>`<span>${esc(x)}</span>`).join('')||'<span>暂无</span>'}</div></div><div class="modal-actions"><button class="btn ghost" id="clearResumeText">删除原始解析文本</button><button class="btn primary" id="saveProfilePrefs">保存偏好</button></div></div>`);
  document.querySelector('#saveProfilePrefs').onclick=()=>{state.preferences.targetDirections=document.querySelector('#prefDirections').value.split(/[,，]/).map(x=>x.trim()).filter(Boolean);state.preferences.targetLocations=document.querySelector('#prefLocations').value.split(/[,，]/).map(x=>x.trim()).filter(Boolean);saveState();closeModal();toast('匹配偏好已更新');};
  document.querySelector('#clearResumeText').onclick=()=>{p.rawText='';saveState();closeModal();toast('已删除简历原始解析文本，画像信号仍保留');};
}
function pasteResume(){ openModal('粘贴简历文本',`<div class="stack-form"><p class="muted">文本只在浏览器本地解析。</p><textarea id="resumePasteText" rows="14" placeholder="粘贴简历正文…"></textarea><input id="resumePasteName" placeholder="简历版本名称，例如 AI Infra 版"><div class="modal-actions"><button class="btn primary" id="parsePastedResume">解析并匹配</button></div></div>`);document.querySelector('#parsePastedResume').onclick=()=>{const text=document.querySelector('#resumePasteText').value.trim();if(text.length<30){toast('文本过短');return;}const name=document.querySelector('#resumePasteName').value.trim()||`粘贴简历 ${today()}`;const p=buildResumeProfile(text,`${name}.txt`);p.name=name;state.resumes.unshift(p);state.activeResumeId=p.id;saveState();closeModal();toast('候选人画像已建立');}; }
function addAsset(){ openModal('添加准备资料',`<div class="stack-form"><label><span>名称</span><input id="assetName" placeholder="例如 CUDA GEMM 项目讲稿"></label><label><span>链接</span><input id="assetUrl" type="url" placeholder="https://..."></label><label><span>备注</span><input id="assetNote" placeholder="用途 / 对应岗位"></label><div class="modal-actions"><button class="btn primary" id="saveAsset">添加</button></div></div>`);document.querySelector('#saveAsset').onclick=()=>{const name=document.querySelector('#assetName').value.trim(),url=document.querySelector('#assetUrl').value.trim();if(!name||!url){toast('名称和链接不能为空');return;}state.assets.unshift({name,url,note:document.querySelector('#assetNote').value.trim()});saveState();closeModal();}; }
function showSources(){
  const sources=sourceStatus.sources||[]; const rows=sources.length?sources.map(s=>`<div class="source-status-row"><div><strong>${esc(s.label||s.name||s.source)}</strong><small>${esc(s.url||'')}</small></div><span class="source-health ${s.ok?'ok':'bad'}">${s.ok?`${s.count||0} 条`:`异常 · ${esc(s.error||'unknown')}`}</span></div>`).join(''):'<div class="empty-state"><strong>尚无刷新记录</strong><p>定时聚合工作流运行后，这里会展示每个数据源的成功状态、数量和错误。</p></div>';
  openModal('岗位源与刷新状态',`<div class="source-modal"><p>聚合器每 2 小时运行一次。当前适配器只访问公开、无需登录的页面/Feed；遇到验证码、登录墙或明确禁止自动访问时停止，不做绕过。</p>${rows}<div class="source-foot"><span>OfferJack 被作为公开聚合产品的黑盒参考与公开页面适配源；本站代码为独立实现，不复制其非公开源码。</span></div></div>`);
}
function githubLogin(){
  if(CONFIG.githubOAuthProxy && CONFIG.githubClientId){
    const returnTo=location.href.split('?')[0]; location.href=`${CONFIG.githubOAuthProxy.replace(/\/$/,'')}/login/github?return_to=${encodeURIComponent(returnTo)}`; return;
  }
  openModal('GitHub 登录',`<div class="auth-explain"><div class="auth-mark">⌘</div><h3>GitHub Pages 已作为前端入口</h3><p>真正的“Sign in with GitHub”不能把 OAuth client secret 或用户 token 写进公开的 GitHub Pages JavaScript。当前已经预留 OAuth Proxy 接口；配置服务端 token exchange 后即可启用账号登录和跨设备同步。</p><div class="auth-path"><span>github.io</span><b>→</b><span>GitHub OAuth</span><b>→</b><span>secure proxy</span><b>→</b><span>encrypted sync</span></div><p class="muted">在此之前，应用保持 Local-first；访问网站不需要登录。</p></div>`);
}
function exportData(){ const blob=new Blob([JSON.stringify(state,null,2)],{type:'application/json'});const a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`path-to-offer-${today()}.json`;a.click();URL.revokeObjectURL(a.href);toast('个人数据已导出'); }

function renderAll(){ renderDiscovery(); renderPipeline(); renderLibrary(); renderReviews(); renderInsights(); }
function bindEvents(){
  document.querySelectorAll('.nav-item').forEach(b=>b.onclick=()=>switchView(b.dataset.view)); document.querySelectorAll('[data-view-go]').forEach(b=>b.onclick=()=>switchView(b.dataset.viewGo));
  document.querySelector('#addJobBtn').onclick=()=>openJob(); document.querySelector('#closeDrawer').onclick=closeDrawer;document.querySelector('#drawerBackdrop').onclick=closeDrawer;document.querySelector('#cancelJobBtn').onclick=closeDrawer;document.querySelector('#jobForm').addEventListener('submit',submitJob);
  document.querySelector('#deleteJobBtn').onclick=()=>{const id=document.querySelector('#jobForm').id.value;if(!id)return;state.jobs=state.jobs.filter(j=>j.id!==id);saveState();closeDrawer();toast('岗位已删除');};
  document.querySelector('#closeModal').onclick=closeModal;document.querySelector('#modalBackdrop').onclick=closeModal;
  document.querySelector('#resumeImport').onchange=e=>handleResumeFile(e.target.files[0]); document.querySelector('#libraryResumeImport').onchange=e=>handleResumeFile(e.target.files[0]);document.querySelector('#replaceResumeInput').onchange=e=>handleResumeFile(e.target.files[0]);
  document.querySelector('#replaceResumeBtn').onclick=()=>document.querySelector('#replaceResumeInput').click();document.querySelector('#pasteResumeBtn').onclick=pasteResume;document.querySelector('#inspectProfileBtn').onclick=inspectProfile;
  ['#jobSearch','#jobLocationFilter','#jobTypeFilter','#jobBatchFilter','#scoreThreshold','#freshOnly','#matchDegree','#matchGrad'].forEach(sel=>{const el=document.querySelector(sel);el?.addEventListener(el?.tagName==='INPUT'&&el.type==='text'?'input':'change',()=>{if(sel==='#scoreThreshold')document.querySelector('#scoreThresholdLabel').textContent=el.value;renderMarket();});});
  document.querySelector('#refreshFeedBtn').onclick=async()=>{toast('正在读取最新聚合结果…');await loadFeeds();toast('岗位列表已刷新');};document.querySelector('#openSourcePanel').onclick=showSources;
  document.querySelectorAll('[data-sort]').forEach(b=>b.onclick=()=>{marketSort=b.dataset.sort;document.querySelectorAll('[data-sort]').forEach(x=>x.classList.toggle('active',x===b));renderMarket();});
  document.querySelectorAll('[data-job-view]').forEach(b=>b.onclick=()=>{marketMode=b.dataset.jobView;document.querySelectorAll('[data-job-view]').forEach(x=>x.classList.toggle('active',x===b));renderMarket();});
  ['#pipelineSearch','#priorityFilter','#directionFilter'].forEach(sel=>document.querySelector(sel).addEventListener(sel==='#pipelineSearch'?'input':'change',renderPipeline));document.querySelectorAll('[data-pipeline-mode]').forEach(b=>b.onclick=()=>{pipelineMode=b.dataset.pipelineMode;document.querySelectorAll('[data-pipeline-mode]').forEach(x=>x.classList.toggle('active',x===b));renderPipeline();});
  document.querySelector('#reviewImport').onchange=e=>importReview(e.target.files[0]);document.querySelector('#addAssetBtn').onclick=addAsset;document.querySelector('#exportBtn').onclick=exportData;document.querySelector('#githubLoginBtn').onclick=githubLogin;
  document.addEventListener('keydown',e=>{if(e.key==='Escape'){closeModal();closeDrawer();}});
  setupTheme();
}
function setupTheme(){
  const wrap=document.querySelector('#swatches'); wrap.innerHTML=palettes.map((p,i)=>`<button class="swatch" data-theme="${i}" title="${p[0]}" style="--sw:${p[0]}"></button>`).join('');
  const saved=Number(localStorage.getItem(THEME_KEY)||0);applyTheme(Number.isFinite(saved)?saved:0);
  document.querySelector('#themeBtn').onclick=e=>{e.stopPropagation();document.querySelector('#themePopover').classList.toggle('show');};
  document.querySelectorAll('[data-theme]').forEach(b=>b.onclick=()=>{applyTheme(Number(b.dataset.theme));localStorage.setItem(THEME_KEY,b.dataset.theme);document.querySelector('#themePopover').classList.remove('show');});document.addEventListener('click',e=>{if(!e.target.closest('#themePopover')&&!e.target.closest('#themeBtn'))document.querySelector('#themePopover').classList.remove('show');});
}
function applyTheme(i){const p=palettes[i]||palettes[0];const root=document.documentElement;root.style.setProperty('--accent',p[1]);root.style.setProperty('--accent-strong',p[2]);root.style.setProperty('--accent-soft',p[3]);}

bindEvents(); renderAll(); loadFeeds();
