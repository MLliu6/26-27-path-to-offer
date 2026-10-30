/* v1.5 workspace: additive UI, no account migration or automatic remote writes. */
(function(){
  'use strict';
  if(typeof state==='undefined'||!window.PTO_WORKSPACE_CORE)return;
  const C=window.PTO_WORKSPACE_CORE,$=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
  const PREF='pto.workspace.preferences.v15',BACKUP='pto.secure.snapshots.v15.';
  let prefs={evidence:'all',kind:'all',cohort:'2027',hideEmpty:true,scope:'all',view:'discover'};
  try{prefs={...prefs,...JSON.parse(localStorage.getItem(PREF)||'{}')};}catch(_){}
  const storePrefs=()=>{try{localStorage.setItem(PREF,JSON.stringify(prefs));}catch(_){toast('本机设置未能保存');}};
  const clone=v=>JSON.parse(JSON.stringify(v));
  const account=()=>window.PTO_ACCOUNT_SESSION?.id||'guest';
  let supplemental={jobs:[]},verified={jobs:[]},supplementalStatus={sources:[]},sourceAudit=null,sourceDirectory=[],flight=null,drawerBefore='',allowClose=false;
  let undo=null,undoTimer=null;
  today=C.localDate;
  const oldNormalize=normalizeMarketJob;
  normalizeMarketJob=function(j){const base=oldNormalize(j),cohort=window.PTO_MATCHING.jobCohort?.(base),share=/service\.weibo\.com\/share|(?:facebook|twitter|linkedin)\.com\/(?:share|intent)/i.test(base.applyUrl||'');return {...base,applyUrl:share?'':base.applyUrl,cohortConflict:!!cohort?.conflict,batch:cohort?.conflict?(cohort.years.join(' / ')+' 届 · '+(/实习|intern/i.test(base.role)?'实习':'校园招聘')):base.batch,jd:j.jd_full||base.jd,updatedAt:C.dateValue(base.updatedAt),location:C.cityNames(base.location).join(' / ')||base.location,source:j.s??j.source??'public',positionId:C.positionId(j),verification:j.verification||'',observedAt:C.dateValue(j.observed_at||j.observedAt||''),observedVia:j.observed_via||j.observedVia||'',sourceLabel:j.x||j.source_label||j.sourceLabel||base.sourceLabel,sourceUrl:j.source_url||base.sourceUrl,deadline:j.deadline||'',listingStatus:j.status||'',graduation:cohort?.years?.length?cohort.years.map(y=>y+'届').join(' / '):(j.g||j.graduation||base.graduation)};};
  window.PTO_PRODUCT_V14.mergeBestJobs=C.mergeJobs;
  ptoMergeJobs=C.mergeJobs;
  ptoCanonicalUrl=C.canonicalUrl;
  const baseLoad=loadFeeds;
  loadFeeds=function(){
    if(flight)return flight;
    const button=$('#refreshFeedBtn');if(button){button.disabled=true;button.textContent='正在刷新…';}
    flight=(async()=>{
      const helper=window.PTO_FEED_V141;
      const more=Promise.all([
        helper.fetchJson('./data/jobs_supplemental.json',{kind:'catalog',retries:0}),
        helper.fetchJson('./data/supplemental_source_status.json',{kind:'status',retries:0}),
        helper.fetchJson('./data/jobs_verified_v16.json',{kind:'catalog',retries:0})
      ]);
      await baseLoad();
      const [feed,status,fresh]=await more;
      if(feed.ok&&Array.isArray(feed.value?.jobs))supplemental=feed.value;
      if(status.ok&&Array.isArray(status.value?.sources))supplementalStatus=status.value;
      if(fresh.ok&&Array.isArray(fresh.value?.jobs))verified=fresh.value;
      if(!feed.ok)window.PTO_FEED_RUNTIME.failures.push('supplemental:'+feed.error);
      marketJobs=C.mergeJobs(marketJobs,supplemental.jobs.map(normalizeMarketJob),verified.jobs.map(normalizeMarketJob));
      window.PTO_FEED_RUNTIME.jobsLoaded=marketJobs.length;
      window.PTO_RANKING_V14?.clearCache?.();renderDiscovery();return marketJobs;
    })().finally(()=>{flight=null;renderFeedHealth();if(button){button.disabled=false;button.textContent='刷新职位';}});
    return flight;
  };
  const baseVisible=visibleMarketJobs;
  const isPosition=j=>window.PTO_MATCHING.isPosition?window.PTO_MATCHING.isPosition(j):true;
  function leadRows(){
    // A verification queue is not a recommendation. Do not hide uncertain leads
    // behind the resume-fit threshold, but preserve explicit metadata/search filters.
    const q=$('#jobSearch')?.value||'',loc=$('#jobLocationFilter')?.value||'all',typ=$('#jobTypeFilter')?.value||'all',batch=$('#jobBatchFilter')?.value||'all';
    return marketJobs.filter(j=>(C.isLead(j)||!isPosition(j))&&state.decisions[j.id]!=='hidden'&&(loc==='all'||j.location.includes(loc))&&(typ==='all'||j.companyType===typ)&&(batch==='all'||j.batch===batch)&&window.PTO_MATCHING.searchMatch(j,q).matched).map(j=>({...j,match:{score:null,reasons:[],hits:[],components:{}}}));
  }
  let cohortAlternatives=0;
  visibleMarketJobs=function(){const rows=(prefs.evidence==='leads'?leadRows():baseVisible()).filter(j=>{
    if(prefs.evidence!=='leads'&&(!isPosition(j)||C.isLead(j)))return false;
    if(prefs.evidence==='official'&&!C.official(j))return false;
    if(prefs.evidence==='leads'&&!C.isLead(j)&&isPosition(j))return false;
    if(/^(closed|expired|inactive|已截止|已下线)$/i.test(j.listingStatus)||(/^\d{4}-\d{2}-\d{2}/.test(j.deadline)&&j.deadline.slice(0,10)<C.localDate()))return false;
    const label=String(j.batch||'')+' '+String(j.role||'');
    if(prefs.kind==='campus'&&!/校招|校园|应届|届|graduate/i.test(label))return false;
    if(prefs.kind==='intern'&&!/实习|intern/i.test(label))return false;
    if(prefs.kind==='social'&&!/社招|社会招聘/.test(label))return false;
    return true;
  });cohortAlternatives=prefs.cohort==='2027'?rows.filter(j=>!window.PTO_MATCHING.jobCohort(j).years.length).length:0;
    return rows.filter(j=>{const years=window.PTO_MATCHING.jobCohort(j).years;return prefs.cohort==='2027'?years.includes('2027'):prefs.cohort==='unknown'?!years.length:true;});
  };
  const baseFilters=renderMarketFilters;
  renderMarketFilters=function(){
    const selected=$('#jobLocationFilter')?.value||'all';baseFilters();const sel=$('#jobLocationFilter');if(!sel)return;
    const cities=['北京','上海','深圳','广州','杭州','南京','成都','武汉','西安','苏州','天津','合肥','长沙','重庆'];
    const observed=[...new Set(marketJobs.flatMap(j=>C.cityNames(j.location)))].sort((a,b)=>a.localeCompare(b,'zh-CN'));
    const popular=cities.filter(c=>observed.some(x=>x.includes(c)));
    const rest=observed.filter(x=>!popular.includes(x));if(selected!=='all'&&C.cityNames(selected).length&&!popular.includes(selected)&&!rest.includes(selected))rest.push(selected);
    const options=xs=>xs.map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join('');
    sel.innerHTML='<option value="all">全部地点</option><optgroup label="常用城市">'+options(popular)+'</optgroup><optgroup label="其他已观测地点">'+options(rest)+'</optgroup>';sel.value=selected;
  };
  function knownJob(j){return state.jobs.find(x=>x.sourceJobId===j.id||(C.company(x)===C.company(j)&&C.positionId(x)&&C.positionId(x)===C.positionId(j))||(C.company(x)===C.company(j)&&x.role===j.role&&x.url&&C.canonicalUrl(x.url)===C.canonicalUrl(j.applyUrl)));}
  const basePromote=promoteMarketJob;
  promoteMarketJob=function(id,close=true){const j=marketJobs.find(x=>x.id===id);const known=j&&knownJob(j);if(known){toast('该岗位已在你的流程中');openJob(known.id);return;}basePromote(id,close);};
  function decorateMarket(){
    const leads=marketJobs.filter(C.isLead).length;
    let alternatives=$('#v16CohortAlternatives');if(!alternatives){alternatives=document.createElement('div');alternatives.id='v16CohortAlternatives';alternatives.className='v16-cohort-alternatives';$('.market-head')?.insertAdjacentElement('afterend',alternatives);}
    alternatives.hidden=!cohortAlternatives;
    alternatives.innerHTML=cohortAlternatives?`<span>另有 ${cohortAlternatives.toLocaleString()} 个相关岗位尚未注明毕业届别</span><button class="text-btn">查看这些岗位 →</button>`:'';
    alternatives.querySelector('button')?.addEventListener('click',()=>{prefs.cohort='unknown';$('#v16Cohort').value='unknown';storePrefs();renderMarket();});
    if(!currentProfile()&&Number(($('#marketCount')?.textContent||'0').replace(/,/g,''))>0)$('#jobMarketEmpty')?.classList.add('hidden');
    let meta=$('#v15EvidenceCount');if(!meta){meta=document.createElement('p');meta.id='v15EvidenceCount';meta.className='v15-search-count';$('.market-head')?.insertAdjacentElement('afterend',meta);}
    meta.textContent=`${marketJobs.length.toLocaleString()} 条招聘记录 · ${marketJobs.filter(j=>/2027/.test([j.graduation,j.batch,j.role].join(' '))).length.toLocaleString()} 条明确 2027 届 · ${leads} 条待核验`;
    for(const card of $$('#jobMarketCards [data-market-id]')){
      const j=marketJobs.find(x=>String(x.id)===card.dataset.marketId);if(!j)continue;
      const badge=document.createElement('span');badge.className='v15-badge'+(C.isLead(j)?' lead':'');
      badge.textContent=(C.isLead(j)||!isPosition(j))?'招聘线索 · 查看原文':C.official(j)?'官网来源':'公开招聘索引';
      card.querySelector('.job-facts')?.appendChild(badge);if(j.observedAt){const time=document.createElement('span');time.className='v15-badge';time.textContent='采集 '+j.observedAt.slice(0,10);badge.after(time);}
      if(C.isLead(j))card.querySelectorAll('a').forEach(a=>{if(/官网投递/.test(a.textContent))a.textContent='核验官方入口 ↗';});
      const apply=card.querySelector('[data-open-apply]');if(apply)apply.textContent=C.official(j)?'官网投递 ↗':'查看招聘原文 ↗';const existing=knownJob(j),button=card.querySelector('[data-save-job]');if(existing&&button){button.textContent='已在流程';button.onclick=e=>{e.stopPropagation();openJob(existing.id);};}
    }
    if($('#jobMarketEmpty')&&!$('#jobMarketEmpty').classList.contains('hidden')&&marketJobs.length&&($('#jobSearch')?.value||prefs.evidence!=='all'||prefs.kind!=='all')){
      const p=$('#jobMarketEmpty p');if(p&&$('#marketCount')?.textContent==='0')p.textContent='当前搜索与筛选组合没有结果。清除筛选后重试；这不代表该公司没有招聘。';
    }
  }
  const baseMarket=renderMarket;renderMarket=function(){const out=baseMarket.apply(this,arguments);decorateMarket();return out;};
  renderFeedHealth=function(){const el=$('#feedHealth');if(!el)return;const s=sourceStatus?.sources||[],bad=s.filter(x=>!x.ok).length,r=window.PTO_FEED_RUNTIME||{};const degraded=bad>0||r.failures?.length;el.dataset.health=degraded?'degraded':'healthy';const t=sourceStatus?.priority_generated_at||sourceStatus?.generated_at;el.innerHTML=`<span class="pulse-dot"></span><span>${flight?'正在刷新':degraded?'部分信源降级':'岗位目录已载入'} · ${marketJobs.length.toLocaleString()} 岗位 · ${bad}/${s.length} 个采集组异常<br>${t?'目录时间 '+esc(new Date(t).toLocaleString('zh-CN',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'})):'目录时间未知'}${r.usedPrevious?' · 已保留上一版数据':''}</span>`;};
  function setUndo(label,fn){undo={fn,owner:account()};$('#v15Undo')?.remove();const el=document.createElement('div');el.id='v15Undo';el.className='v15-undo';el.setAttribute('role','status');el.innerHTML=`<span>${esc(label)}</span><button class="text-btn">撤销</button>`;el.querySelector('button').onclick=()=>{if(undo?.owner===account()){undo.fn();saveState();}else toast('账户已切换，未执行撤销');undo=null;el.remove();};document.body.appendChild(el);clearTimeout(undoTimer);undoTimer=setTimeout(()=>{undo=null;el.remove();},18000);}
  function quickUpdate(id){const job=state.jobs.find(j=>j.id===id);if(!job)return;const owner=account();openModal(`${job.company} · 更新进度`,`<form id="v15Update" class="v15-form"><p class="v15-note">${esc(job.role)} · 更新仅保存到你的求职账户，不会向招聘方提交申请。</p><label>当前阶段<select name="status">${stages.map(([k,v])=>`<option value="${k}" ${k===pipelineStage(job.status)?'selected':''}>${v}</option>`).join('')}</select></label><label>状态日期<input type="date" name="date" value="${today()}" required></label><label>下次跟进日期（可留空）<input type="date" name="followUpAt" value="${esc(job.followUpAt||'')}"></label><label>本次记录 / 下一步<textarea name="note" placeholder="例如：已完成测评，等待一面通知"></textarea></label><div class="v15-actions"><button type="button" id="v15Full" class="btn ghost">编辑完整记录</button><button class="btn primary">保存进度</button></div></form>`);
    $('#v15Full').onclick=()=>{closeModal();openJob(id);};
    $('#v15Update').onsubmit=e=>{e.preventDefault();if(account()!==owner){toast('账户已切换，请重新打开记录');closeModal();return;}const current=state.jobs.find(j=>j.id===id);if(!current)return;const before=clone(current),f=e.currentTarget.elements;try{const next=C.updateStatus(current,f.status.value===pipelineStage(current.status)?current.status:f.status.value,f.date.value,f.note.value.trim(),f.followUpAt.value);Object.assign(current,next);saveState();closeModal();setUndo('进度已保存',()=>{const live=state.jobs.find(j=>j.id===id);if(live&&JSON.stringify(live)===JSON.stringify(next)){for(const key of Object.keys(live))delete live[key];Object.assign(live,before);}else toast('记录已有后续修改，未回退');});}catch(err){toast(err.message);}};
  }
  const baseFiltered=filteredPipelineJobs;
  filteredPipelineJobs=function(){return baseFiltered().filter(j=>prefs.scope==='all'||(prefs.scope==='active'&&!['rejected','signed'].includes(j.status))||(prefs.scope==='due'&&j.followUpAt&&j.followUpAt<=today()&&!['rejected','signed'].includes(j.status))||(prefs.scope==='interview'&&/^interview|^hr$/.test(j.status)));};
  const basePipeline=renderPipeline;
  renderPipeline=function(){basePipeline();const s=C.summary(state.jobs);let summary=$('#v15PipelineSummary');if(!summary){summary=document.createElement('div');summary.id='v15PipelineSummary';summary.className='v15-summary';$('#pipelineView .filter-row').insertAdjacentElement('beforebegin',summary);}summary.innerHTML=[['all',s.total,'全部记录'],['active',s.active,'正在推进'],['interview',s.interview,'面试阶段'],['due',s.due,'到期跟进']].map(([k,n,t])=>`<button data-scope="${k}"><strong>${n}</strong><span>${t}</span></button>`).join('');summary.querySelectorAll('button').forEach(b=>b.onclick=()=>{prefs.scope=b.dataset.scope;storePrefs();renderPipeline();});$('#pipelineView').classList.toggle('v15-hide-empty',prefs.hideEmpty);
    for(const card of $$('#kanban [data-job-id]')){const j=state.jobs.find(x=>x.id===card.dataset.jobId);if(!j)continue;const line=document.createElement('div');line.className='v15-status-line';line.innerHTML=`<small>${j.followUpAt?'跟进 '+esc(j.followUpAt):'未设置跟进日'}</small><button class="btn ghost" data-quick-update="${esc(j.id)}">更新进度</button>`;card.appendChild(line);card.tabIndex=0;card.setAttribute('role','button');card.setAttribute('aria-label',`${j.company} ${j.role}，${stageName(j.status)}`);card.onkeydown=e=>{if(e.target===card&&(e.key==='Enter'||e.key===' ')){e.preventDefault();quickUpdate(j.id);}};}
    const table=$('#jobTableWrap table');if(table){table.querySelector('thead tr')?.insertAdjacentHTML('beforeend','<th>快捷操作</th>');table.querySelectorAll('tbody tr').forEach(row=>row.insertAdjacentHTML('beforeend',`<td><button class="btn ghost" data-quick-update="${esc(row.dataset.jobId)}">更新进度</button></td>`));}
    $('#v15Scope')&&( $('#v15Scope').value=prefs.scope );
  };
  document.addEventListener('click',e=>{const b=e.target.closest('[data-quick-update]');if(!b)return;e.preventDefault();e.stopImmediatePropagation();quickUpdate(b.dataset.quickUpdate);},true);
  document.addEventListener('click',e=>{
    const b=e.target.closest('#deleteJobBtn,[data-delete-resume],[data-delete-asset],#deleteReview');if(!b)return;
    e.preventDefault();e.stopImmediatePropagation();if(!confirm('删除这条记录？可在 18 秒内撤销。'))return;
    let field,id,index,before,oldResume=state.activeResumeId;
    if(b.id==='deleteJobBtn'){field='jobs';id=$('#jobForm').elements.id.value;index=state.jobs.findIndex(j=>j.id===id);}
    else if(b.hasAttribute('data-delete-resume')){field='resumes';index=state.resumes.findIndex(j=>j.id===b.dataset.deleteResume);}
    else if(b.hasAttribute('data-delete-asset')){field='assets';index=Number(b.dataset.deleteAsset);}
    else{field='reviews';index=state.reviews.findIndex(j=>j.id===selectedReviewId);}
    if(index<0||!state[field][index])return;before=clone(state[field][index]);state[field].splice(index,1);
    if(field==='resumes'&&state.activeResumeId===before.id)state.activeResumeId=state.resumes[0]?.id||null;
    allowClose=true;closeDrawer();allowClose=false;saveState();setUndo('记录已删除',()=>{if(!before.id||!state[field].some(x=>x.id===before.id))state[field].splice(Math.min(index,state[field].length),0,before);if(field==='resumes')state.activeResumeId=oldResume;});
  },true);
  function formValue(){return JSON.stringify([...new FormData($('#jobForm')).entries()]);}
  const baseOpenJob=openJob;openJob=function(id){if($('#jobDrawer').classList.contains('open')&&formValue()!==drawerBefore&&!$('#jobForm').classList.contains('hidden')&&!confirm('放弃尚未保存的编辑？'))return;baseOpenJob(id);drawerBefore=formValue();};
  const baseCloseDrawer=closeDrawer;closeDrawer=function(){if(!allowClose&&!$('#jobForm').classList.contains('hidden')&&$('#jobDrawer').classList.contains('open')&&drawerBefore&&formValue()!==drawerBefore&&!confirm('放弃尚未保存的编辑？'))return;baseCloseDrawer();drawerBefore='';};
  $('#jobForm').addEventListener('submit',()=>{drawerBefore=formValue();},true);
  for(const id of ['closeDrawer','cancelJobBtn','drawerBackdrop'])$('#'+id).onclick=()=>closeDrawer();
  window.addEventListener('beforeunload',e=>{if((drawerBefore&&$('#jobDrawer').classList.contains('open')&&!$('#jobForm').classList.contains('hidden')&&formValue()!==drawerBefore)||window.PTO_SECURE_ACCOUNT_V2?.pending?.()){e.preventDefault();e.returnValue='';}});
  $('#closeModal').onclick=()=>closeModal();$('#modalBackdrop').onclick=()=>closeModal();
  document.addEventListener('keydown',e=>{if(e.isComposing||$('#quickModal').classList.contains('show')||$('#jobDrawer').classList.contains('open'))return;if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();switchView('discover');$('#jobSearch')?.focus();}},true);
  const nativeSet=Storage.prototype.setItem;
  Storage.prototype.setItem=function(key,value){if(this===localStorage&&String(key).startsWith('pto.secure.local.v2.')){const previous=this.getItem(key);if(previous&&previous!==value){try{const vault=JSON.parse(previous);if(vault.schema==='pto-encrypted-vault'){const bk=BACKUP+String(key).slice('pto.secure.local.v2.'.length);const history=JSON.parse(this.getItem(bk)||'[]');nativeSet.call(this,bk,JSON.stringify([{savedAt:new Date().toISOString(),vault},...history].slice(0,3)));}}catch(_){/* Backup quota must never block the primary encrypted write. */}}}return nativeSet.call(this,key,value);};
  async function backup(){try{await window.PTO_SECURE_ACCOUNT_V2?.flushLocal();}catch(err){toast('备份前保存失败：'+err.message);return;}const entries={};for(let i=0;i<localStorage.length;i++){const k=localStorage.key(i);if(k.startsWith('pto.secure.local.v2.')||k.startsWith(BACKUP)||k==='pto.secure.device-account.v1')entries[k]=localStorage.getItem(k);}if(!Object.keys(entries).some(k=>k.startsWith('pto.secure.local.v2.'))){toast('当前浏览器尚无加密账户；可在洞察页导出个人数据');return;}const a=document.createElement('a'),url=URL.createObjectURL(new Blob([JSON.stringify({format:'pto-encrypted-device-backup-v15',createdAt:new Date().toISOString(),entries},null,2)],{type:'application/json'}));a.href=url;a.download=`path-to-offer-encrypted-${today()}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('已导出密文；请同时保留原密码');}
  async function restoreBackup(file){if(!file)return;try{if(file.size>30000000)throw Error('备份过大');const doc=JSON.parse(await file.text());if(doc.format!=='pto-encrypted-device-backup-v15'||!doc.entries)throw Error('请选择加密设备备份文件');const items=Object.entries(doc.entries).filter(([k])=>/^pto\.secure\.local\.v2\.[a-f0-9]{64}$/.test(k));if(!items.length)throw Error('备份中没有加密账户');for(const [,v] of items){const b=JSON.parse(v);if(b.schema!=='pto-encrypted-vault')throw Error('备份格式错误');}if(!confirm(`恢复 ${items.length} 个加密账户副本？本机已有账户不覆盖，只保存为可恢复快照。`))return;for(const [k,v] of items){if(localStorage.getItem(k)){const bk=BACKUP+k.slice('pto.secure.local.v2.'.length),old=JSON.parse(localStorage.getItem(bk)||'[]');nativeSet.call(localStorage,bk,JSON.stringify([{savedAt:new Date().toISOString(),vault:JSON.parse(v)},...old].slice(0,3)));}else nativeSet.call(localStorage,k,v);}if(!window.PTO_DEVICE_ACCOUNT_HINT?.read()){const hint=doc.entries['pto.secure.device-account.v1'];if(hint)window.PTO_DEVICE_ACCOUNT_HINT?.remember(JSON.parse(hint));}window.PTO_DEVICE_ACCOUNT_HINT?.sync();toast('密文已恢复；在账户中使用原密码解锁');}catch(err){toast('未恢复：'+err.message);}}
  async function sourcesPanel(){
    openModal('官方招聘入口', '<p role="status">正在读取行业目录…</p>');
    const [directory,audit]=await Promise.all([
      window.PTO_FEED_V141.fetchJson('./sources/sector_sources_v16.json',{kind:'status',retries:0}),
      window.PTO_FEED_V141.fetchJson('./data/source_integrity_audit.json',{kind:'status',retries:0})
    ]);
    if(directory.ok)sourceDirectory=directory.value.sources||[];
    if(audit.ok)sourceAudit=audit.value;
    if(!$('#quickModal').classList.contains('show')||$('#modalTitle').textContent!=='官方招聘入口')return;
    const industries=[...new Set(sourceDirectory.map(s=>s.industry).filter(Boolean))];
    const types=[...new Set(sourceDirectory.map(s=>s.company_type).filter(Boolean))];
    const cohort=marketJobs.filter(j=>/2027/.test([j.graduation,j.batch,j.role].join(' '))).length;
    openModal('官方招聘入口',`<p class="v15-note">按行业找到企业官网，直接查看最新岗位与报名要求。</p><div class="v15-summary"><div><strong>${sourceDirectory.length}</strong><span>官方入口</span></div><div><strong>${industries.length}</strong><span>行业方向</span></div><div><strong>${cohort.toLocaleString()}</strong><span>目录中明确 2027 届</span></div></div><div class="v16-source-filters"><input class="search" id="v16SourceSearch" aria-label="搜索公司、专业或行业" placeholder="公司、专业或行业"><select id="v16SourceIndustry" aria-label="选择行业"><option value="all">全部行业</option>${industries.map(v=>`<option>${esc(v)}</option>`).join('')}</select><select id="v16SourceType" aria-label="选择企业性质"><option value="all">全部企业性质</option>${types.map(v=>`<option>${esc(v)}</option>`).join('')}</select></div><div id="v16SourceDirectory"></div><details class="v16-source-health"><summary>采集状态与覆盖详情</summary><p class="v15-note">最近审查：${esc((sourceAudit?.generated_at||'').slice(0,19).replace('T',' ')||'尚未完成')}。各来源按公开招聘页面持续更新。</p>${[...(supplementalStatus.sources||[]),...(sourceStatus?.sources||[])].map(s=>`<div class="v15-source-row"><strong>${esc(s.company||s.label||s.name)}</strong><span>${s.ok?'已更新':s.preserved_previous?'待重试 · 保留上次记录':'待重试'} · ${Number(s.count||0).toLocaleString()} 条</span></div>`).join('')}</details>`);
    function renderDirectory(){
      const query=$('#v16SourceSearch').value.trim().toLowerCase(),industry=$('#v16SourceIndustry').value,type=$('#v16SourceType').value;
      const rows=sourceDirectory.filter(s=>(industry==='all'||s.industry===industry)&&(type==='all'||s.company_type===type)&&[s.company,s.industry,...(s.disciplines||[])].join(' ').toLowerCase().includes(query));
      const checks=sourceAudit?.portal_checks||[];
      $('#v16SourceDirectory').innerHTML=rows.map(s=>{const check=Array.isArray(checks)?checks.find(c=>c.id===s.id||c.url===s.url):checks[s.id];const href=/^https?:\/\//i.test(s.url)?s.url:'#';return `<article class="v15-source-row"><div><strong>${esc(s.company)}</strong><small>${esc(s.company_type)} · ${esc(s.industry)}<br>${esc((s.disciplines||[]).join(' / '))}</small></div><div><span class="v15-badge">${check?.status==='browser_required'?'需浏览器打开':check?.reachable?'入口可访问':check?'访问待复核':'官方招聘入口'}</span><a class="text-btn" href="${esc(href)}" target="_blank" rel="noopener noreferrer">查看官网 ↗</a></div></article>`;}).join('')||'<p class="empty-state">没有符合筛选的入口，试试其他行业或关键词。</p>';
    }
    $('#v16SourceSearch').oninput=renderDirectory;$('#v16SourceIndustry').onchange=renderDirectory;$('#v16SourceType').onchange=renderDirectory;renderDirectory();
  }
  function setup(){
    const skip=document.createElement('a');skip.className='v15-skip';skip.href='#jobSearch';skip.textContent='跳到岗位搜索';document.body.prepend(skip);
    $('.brand small').textContent='每一步，更接近 Offer';
    $('#discoverView h1').textContent='发现你的下一站';$('#discoverView .page-head p:not(.eyebrow)').textContent='从匹配岗位到每一次面试，让求职有序向前。';if(matchMedia('(max-width: 760px)').matches)$('.match-rail')?.removeAttribute('open');
    const toolbar=document.createElement('div');toolbar.className='v15-toolbar';toolbar.innerHTML='<label>来源<select id="v15Evidence"><option value="all">全部记录</option><option value="official">仅官网采集</option><option value="leads">仅待复核线索</option></select></label><label>招聘类型<select id="v15Kind"><option value="all">全部类型</option><option value="campus">校园 / 应届</option><option value="intern">实习</option><option value="social">明确社招</option></select></label><label>毕业届别<select id="v16Cohort"><option value="all">全部届别</option><option value="2027">明确 2027 届</option><option value="unknown">届别待确认</option></select></label><button id="v15ResetFilters" class="btn ghost">清除筛选</button><button id="v15SourceButton" class="text-btn">信源覆盖</button>';
    $('.discovery-toolbar').insertAdjacentElement('afterend',toolbar);
    const extraFilters=document.createElement('details');extraFilters.className='v16-extra-filters';extraFilters.open=!matchMedia('(max-width: 760px)').matches;extraFilters.innerHTML='<summary>更多筛选</summary>';toolbar.before(extraFilters);extraFilters.appendChild(toolbar);const sourceShortcut=document.createElement('button');sourceShortcut.className='text-btn v16-source-shortcut';sourceShortcut.textContent='官方招聘入口 ↗';sourceShortcut.onclick=sourcesPanel;$('.search-policy')?.before(sourceShortcut);
    for(const [id,key] of [['v15Evidence','evidence'],['v15Kind','kind'],['v16Cohort','cohort']]){$('#'+id).value=prefs[key];$('#'+id).onchange=e=>{prefs[key]=e.target.value;storePrefs();renderMarket();};}
    $('#v15ResetFilters').onclick=()=>{prefs.kind=prefs.evidence=prefs.cohort='all';$('#scoreThreshold').value='0';$('#scoreThresholdLabel').textContent='0 · 全部浏览';$('#freshOnly').checked=false;$('#jobSearch').value='';$('#v15Evidence').value=$('#v15Kind').value=$('#v16Cohort').value='all';for(const s of ['#jobLocationFilter','#jobTypeFilter','#jobBatchFilter'])$(s).value='all';storePrefs();window.PTO_RANKING_V14?.clearCache?.();renderMarket();};$('#v15SourceButton').onclick=sourcesPanel;if($('#openSourcePanel'))$('#openSourcePanel').onclick=sourcesPanel;showSources=sourcesPanel;
    const actions=document.createElement('div');actions.className='v15-toolbar';actions.innerHTML='<label>范围<select id="v15Scope"><option value="all">全部记录</option><option value="active">正在推进</option><option value="interview">面试阶段</option><option value="due">到期跟进</option></select></label><label><input type="checkbox" id="v15HideEmpty">隐藏空阶段</label><button class="btn ghost" id="v15Backup">导出加密备份</button><label class="btn ghost" tabindex="0" role="button">导入加密备份<input hidden type="file" id="v15Restore" accept=".json"></label><span class="v15-backup-status">加密账户另保留最近 3 个本机密文快照</span>';
    $('#pipelineView .filter-row').insertAdjacentElement('afterend',actions);$('#v15Scope').onchange=e=>{prefs.scope=e.target.value;storePrefs();renderPipeline();};$('#v15HideEmpty').checked=prefs.hideEmpty;$('#v15HideEmpty').onchange=e=>{prefs.hideEmpty=e.target.checked;storePrefs();renderPipeline();};$('#v15Backup').onclick=backup;$('#v15Restore').onchange=e=>restoreBackup(e.target.files[0]);
    $('#toast').setAttribute('role','status');$('#toast').setAttribute('aria-live','polite');$('#jobSearch').setAttribute('aria-label','搜索公司、岗位、技能或城市');$('#closeModal').setAttribute('aria-label','关闭对话框');

    const fixMeta=()=>{$('meta[name="theme-color"]')?.setAttribute('content',document.documentElement.dataset.appearance==='dark'?'#111113':'#f7f8f5');};fixMeta();new MutationObserver(fixMeta).observe(document.documentElement,{attributes:true,attributeFilter:['data-appearance']});
    renderAll();
  }
  window.PTO_WORKSPACE_V15={quickUpdate,backup,restoreBackup,sourcesPanel,version:'1.5.0'};
  setup();
  // One viewport control mirrors the board; long columns never hide navigation.
  const board=$('#kanban'),dock=document.createElement('div');
  dock.className='pipeline-scroll-dock';dock.hidden=true;
  dock.innerHTML='<button type="button" aria-label="向左浏览阶段">←</button><label>横向浏览<input type="range" min="0" max="0" value="0" step="1" aria-label="投递看板横向位置" aria-controls="kanban"></label><button type="button" aria-label="向右浏览阶段">→</button>';
  document.body.appendChild(dock);const slider=dock.querySelector('input'),buttons=dock.querySelectorAll('button');
  function syncScroll(){slider.value=board.scrollLeft;buttons[0].disabled=board.scrollLeft<=1;buttons[1].disabled=board.scrollLeft>=Number(slider.max)-1;}
  let scrollFrame;
  function layoutScroll(){cancelAnimationFrame(scrollFrame);scrollFrame=requestAnimationFrame(()=>{
    const rect=board.getBoundingClientRect(),max=Math.max(0,board.scrollWidth-board.clientWidth);
    dock.hidden=!$('#pipelineView').classList.contains('active')||board.classList.contains('hidden')||max<2;
    dock.style.left=Math.max(12,rect.left)+'px';dock.style.width=Math.max(0,Math.min(rect.width,innerWidth-rect.left-16)-(innerWidth<=760?56:0))+'px';
    slider.max=max;syncScroll();
  });}
  slider.oninput=()=>{board.scrollLeft=Number(slider.value);syncScroll();};
  buttons.forEach((button,i)=>button.onclick=()=>board.scrollBy({left:(i?1:-1)*Math.max(240,board.clientWidth*.7),behavior:matchMedia('(prefers-reduced-motion: reduce)').matches?'instant':'smooth'}));
  board.addEventListener('scroll',syncScroll,{passive:true});window.addEventListener('resize',layoutScroll);
  new ResizeObserver(layoutScroll).observe(board);
  new MutationObserver(layoutScroll).observe($('#pipelineView'),{attributes:true,attributeFilter:['class'],childList:true,subtree:true});layoutScroll();
})();


/* v1.5.1 working theme controls */
(function(){
  const KEY='pto.ui.theme.v151';
  const palettes={
    blue:{name:'蓝',accent:'#6f82e8',strong:'#5268d9',soft:'#edf0ff'},
    violet:{name:'紫',accent:'#9478d8',strong:'#7457bf',soft:'#f2edff'},
    slate:{name:'石墨',accent:'#7e8794',strong:'#5e6875',soft:'#eef0f3'},
    rose:{name:'玫瑰',accent:'#d47b92',strong:'#b85c76',soft:'#fbeef2'},
    amber:{name:'琥珀',accent:'#c59a55',strong:'#9c7535',soft:'#fbf3e5'},
    sage:{name:'松绿',accent:'#3d8b76',strong:'#176454',soft:'#e8f2ed'}
  };
  let saved={palette:'sage',appearance:'system'};try{saved={...saved,...JSON.parse(localStorage.getItem(KEY)||'{}')}}catch(_){}
  const root=document.documentElement;
  function effectiveAppearance(v){return v==='system'?(matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light'):v}
  function apply(){
    const p=palettes[saved.palette]||palettes.sage;
    root.style.setProperty('--accent',p.accent);root.style.setProperty('--accent-strong',p.strong);root.style.setProperty('--accent-soft',p.soft);
    root.dataset.appearance=effectiveAppearance(saved.appearance);
    const logo=document.querySelector('.brand-mark svg'),icon=document.querySelector('link[rel="icon"]');
    if(logo&&icon){
      const dark=root.dataset.appearance==='dark';
      logo.querySelector('rect').setAttribute('fill',dark?p.accent:p.strong);
      logo.querySelector('path').setAttribute('stroke',dark?'#111113':'#ffffff');
      const svg=logo.cloneNode(true);
      svg.setAttribute('color',getComputedStyle(logo).color);
      svg.querySelector('path').setAttribute('stroke',getComputedStyle(logo.querySelector('path')).stroke);
      icon.href='data:image/svg+xml,'+encodeURIComponent(new XMLSerializer().serializeToString(svg));
    }
    try{localStorage.setItem(KEY,JSON.stringify(saved))}catch(_){}
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content',root.dataset.appearance==='dark'?'#111113':'#f7f8f5');
  }
  function render(){
    const pop=document.querySelector('#themePopover');if(!pop)return;
    pop.innerHTML='<p><strong>外观与强调色</strong></p><div class="v151-appearance">'+[['light','浅色'],['dark','深色'],['system','跟随系统']].map(([k,n])=>`<button data-v151-appearance="${k}" class="${saved.appearance===k?'active':''}">${n}</button>`).join('')+'</div><div class="v151-theme-grid">'+Object.entries(palettes).map(([k,p])=>`<button class="v151-swatch ${saved.palette===k?'active':''}" data-v151-palette="${k}" style="--swatch:${p.strong}"><i></i><span>${p.name}</span></button>`).join('')+'</div><small>选择喜欢的外观，设置自动保存在本机。</small>';
    pop.querySelectorAll('[data-v151-palette]').forEach(b=>b.onclick=e=>{e.stopPropagation();saved.palette=b.dataset.v151Palette;apply();render();});
    pop.querySelectorAll('[data-v151-appearance]').forEach(b=>b.onclick=e=>{e.stopPropagation();saved.appearance=b.dataset.v151Appearance;apply();render();});
  }
  function openTheme(e){e?.preventDefault();e?.stopImmediatePropagation();const pop=document.querySelector('#themePopover');if(!pop)return;render();const opening=!pop.classList.contains('open');pop.classList.toggle('open',opening);pop.style.display=opening?'block':'none';}
  apply();const btn=document.querySelector('#themeBtn');if(btn){btn.title='外观与强调色';btn.addEventListener('click',openTheme,true);}render();
  matchMedia('(prefers-color-scheme: dark)').addEventListener?.('change',()=>{if(saved.appearance==='system')apply();});
  document.addEventListener('click',e=>{const pop=document.querySelector('#themePopover');if(pop?.classList.contains('open')&&!e.target.closest('#themePopover')&&!e.target.closest('#themeBtn')){pop.classList.remove('open');pop.style.display='none';}},true);
})();
