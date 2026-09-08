/* v1.5 workspace: additive UI, no account migration or automatic remote writes. */
(function(){
  'use strict';
  if(typeof state==='undefined'||!window.PTO_WORKSPACE_CORE)return;
  const C=window.PTO_WORKSPACE_CORE,$=s=>document.querySelector(s),$$=s=>[...document.querySelectorAll(s)];
  const PREF='pto.workspace.preferences.v15',BACKUP='pto.secure.snapshots.v15.';
  let prefs={evidence:'all',kind:'all',hideEmpty:true,scope:'all',view:'discover'};
  try{prefs={...prefs,...JSON.parse(localStorage.getItem(PREF)||'{}')};}catch(_){}
  const storePrefs=()=>{try{localStorage.setItem(PREF,JSON.stringify(prefs));}catch(_){toast('本机设置未能保存');}};
  const clone=v=>JSON.parse(JSON.stringify(v));
  const account=()=>window.PTO_ACCOUNT_SESSION?.id||'guest';
  let supplemental={jobs:[]},supplementalStatus={sources:[]},flight=null,drawerBefore='',allowClose=false;
  let undo=null,undoTimer=null,lastFocus=null;
  today=C.localDate;
  const oldNormalize=normalizeMarketJob;
  normalizeMarketJob=function(j){return {...oldNormalize(j),source:j.s??j.source??'public',positionId:C.positionId(j),verification:j.verification||'',observedAt:j.observed_at||j.observedAt||'',observedVia:j.observed_via||j.observedVia||'',sourceLabel:j.x||j.source_label||j.sourceLabel||oldNormalize(j).sourceLabel};};
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
        helper.fetchJson('./data/supplemental_source_status.json',{kind:'status',retries:0})
      ]);
      await baseLoad();
      const [feed,status]=await more;
      if(feed.ok&&Array.isArray(feed.value?.jobs))supplemental=feed.value;
      if(status.ok&&Array.isArray(status.value?.sources))supplementalStatus=status.value;
      if(!feed.ok)window.PTO_FEED_RUNTIME.failures.push('supplemental:'+feed.error);
      marketJobs=C.mergeJobs(marketJobs,supplemental.jobs.map(normalizeMarketJob));
      window.PTO_FEED_RUNTIME.jobsLoaded=marketJobs.length;
      window.PTO_RANKING_V14?.clearCache?.();renderDiscovery();return marketJobs;
    })().finally(()=>{flight=null;renderFeedHealth();if(button){button.disabled=false;button.textContent='刷新职位';}});
    return flight;
  };
  const baseVisible=visibleMarketJobs;
  function leadRows(){
    // A verification queue is not a recommendation. Do not hide uncertain leads
    // behind the resume-fit threshold, but preserve explicit metadata/search filters.
    const q=$('#jobSearch')?.value||'',loc=$('#jobLocationFilter')?.value||'all',typ=$('#jobTypeFilter')?.value||'all',batch=$('#jobBatchFilter')?.value||'all';
    return marketJobs.filter(j=>C.isLead(j)&&state.decisions[j.id]!=='hidden'&&(loc==='all'||j.location.includes(loc))&&(typ==='all'||j.companyType===typ)&&(batch==='all'||j.batch===batch)&&window.PTO_MATCHING.searchMatch(j,q).matched).map(j=>({...j,match:{score:null,reasons:[],hits:[],components:{}}}));
  }
  visibleMarketJobs=function(){return (prefs.evidence==='leads'?leadRows():baseVisible()).filter(j=>{
    if(prefs.evidence==='official'&&!C.official(j))return false;
    if(prefs.evidence==='leads'&&!C.isLead(j))return false;
    const label=String(j.batch||'')+' '+String(j.role||'');
    if(prefs.kind==='campus'&&!/校招|校园|应届|届|graduate/i.test(label))return false;
    if(prefs.kind==='intern'&&!/实习|intern/i.test(label))return false;
    if(prefs.kind==='social'&&!/社招|社会招聘/.test(label))return false;
    return true;
  });};
  const baseFilters=renderMarketFilters;
  renderMarketFilters=function(){
    const selected=$('#jobLocationFilter')?.value||'all';baseFilters();const sel=$('#jobLocationFilter');if(!sel)return;
    const cities=['北京','上海','深圳','广州','杭州','南京','成都','武汉','西安','苏州','天津','合肥','长沙','重庆'];
    const observed=[...new Set(marketJobs.flatMap(j=>String(j.location||'').split(/[ ,，、/]+/).filter(x=>x.length>=2&&x.length<=24)))].sort((a,b)=>a.localeCompare(b,'zh-CN'));
    const popular=cities.filter(c=>observed.some(x=>x.includes(c)));
    const rest=observed.filter(x=>!popular.includes(x));if(selected!=='all'&&!popular.includes(selected)&&!rest.includes(selected))rest.push(selected);
    const options=xs=>xs.map(c=>`<option value="${esc(c)}">${esc(c)}</option>`).join('');
    sel.innerHTML='<option value="all">全部地点</option><optgroup label="常用城市">'+options(popular)+'</optgroup><optgroup label="其他已观测地点">'+options(rest)+'</optgroup>';sel.value=selected;
  };
  function knownJob(j){return state.jobs.find(x=>x.sourceJobId===j.id||(C.company(x)===C.company(j)&&C.positionId(x)&&C.positionId(x)===C.positionId(j))||(C.company(x)===C.company(j)&&x.role===j.role&&x.url&&C.canonicalUrl(x.url)===C.canonicalUrl(j.applyUrl)));}
  const basePromote=promoteMarketJob;
  promoteMarketJob=function(id,close=true){const j=marketJobs.find(x=>x.id===id);const known=j&&knownJob(j);if(known){toast('该岗位已在你的流程中');openJob(known.id);return;}basePromote(id,close);};
  function decorateMarket(){
    const leads=marketJobs.filter(C.isLead).length;
    if(!currentProfile()&&Number(($('#marketCount')?.textContent||'0').replace(/,/g,''))>0)$('#jobMarketEmpty')?.classList.add('hidden');
    let meta=$('#v15EvidenceCount');if(!meta){meta=document.createElement('p');meta.id='v15EvidenceCount';meta.className='v15-search-count';$('.market-head')?.insertAdjacentElement('afterend',meta);}
    meta.textContent=`目录 ${marketJobs.length.toLocaleString()} 条 · 其中 ${leads} 条为待复核线索；页面可访问不等于岗位仍在招聘。`;
    for(const card of $$('#jobMarketCards [data-market-id]')){
      const j=marketJobs.find(x=>String(x.id)===card.dataset.marketId);if(!j)continue;
      const badge=document.createElement('span');badge.className='v15-badge'+(C.isLead(j)?' lead':'');
      badge.textContent=C.isLead(j)?'待复核线索 · 地点/届别待确认':C.official(j)?'官网采集 · 投递前确认':'公开索引 · 投递前确认';
      card.querySelector('.job-facts')?.appendChild(badge);
      if(C.isLead(j))card.querySelectorAll('a').forEach(a=>{if(/官网投递/.test(a.textContent))a.textContent='核验官方入口 ↗';});
      const existing=knownJob(j),button=card.querySelector('[data-save-job]');if(existing&&button){button.textContent='已在流程';button.onclick=e=>{e.stopPropagation();openJob(existing.id);};}
    }
    if($('#jobMarketEmpty')&&!$('#jobMarketEmpty').classList.contains('hidden')&&marketJobs.length&&($('#jobSearch')?.value||prefs.evidence!=='all'||prefs.kind!=='all')){
      const p=$('#jobMarketEmpty p');if(p&&$('#marketCount')?.textContent==='0')p.textContent='当前搜索与筛选组合没有结果。清除筛选后重试；这不代表该公司没有招聘。';
    }
  }
  const baseMarket=renderMarket;renderMarket=function(){const out=baseMarket.apply(this,arguments);decorateMarket();return out;};
  renderFeedHealth=function(){const el=$('#feedHealth');if(!el)return;const s=sourceStatus?.sources||[],bad=s.filter(x=>!x.ok).length,r=window.PTO_FEED_RUNTIME||{};const degraded=bad>0||r.failures?.length;el.dataset.health=degraded?'degraded':'healthy';const t=sourceStatus?.priority_generated_at||sourceStatus?.generated_at;el.innerHTML=`<span class="pulse-dot"></span><span>${flight?'正在刷新':degraded?'部分信源降级':'岗位目录已载入'} · ${marketJobs.length.toLocaleString()} 岗位 · ${bad}/${s.length} 个采集组异常<br>${t?'目录时间 '+esc(new Date(t).toLocaleString('zh-CN',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'})):'目录时间未知'}${r.usedPrevious?' · 已保留上一版数据':''}</span>`;};
  function setUndo(label,fn){undo={fn,owner:account()};$('#v15Undo')?.remove();const el=document.createElement('div');el.id='v15Undo';el.className='v15-undo';el.setAttribute('role','status');el.innerHTML=`<span>${esc(label)}</span><button class="text-btn">撤销</button>`;el.querySelector('button').onclick=()=>{if(undo?.owner===account()){undo.fn();saveState();}else toast('账户已切换，未执行撤销');undo=null;el.remove();};document.body.appendChild(el);clearTimeout(undoTimer);undoTimer=setTimeout(()=>{undo=null;el.remove();},18000);}
  function quickUpdate(id){const job=state.jobs.find(j=>j.id===id);if(!job)return;const owner=account();openModal(`${job.company} · 更新进度`,`<form id="v15Update" class="v15-form"><p class="v15-note">${esc(job.role)} · 更新仅保存到你的求职账户，不会向招聘方提交申请。</p><label>当前阶段<select name="status">${stages.map(([k,v])=>`<option value="${k}" ${k===job.status?'selected':''}>${v}</option>`).join('')}</select></label><label>状态日期<input type="date" name="date" value="${today()}" required></label><label>下次跟进日期（可留空）<input type="date" name="followUpAt" value="${esc(job.followUpAt||'')}"></label><label>本次记录 / 下一步<textarea name="note" placeholder="例如：已完成测评，等待一面通知"></textarea></label><div class="v15-actions"><button type="button" id="v15Full" class="btn ghost">编辑完整记录</button><button class="btn primary">保存进度</button></div></form>`);
    $('#v15Full').onclick=()=>{closeModal();openJob(id);};
    $('#v15Update').onsubmit=e=>{e.preventDefault();if(account()!==owner){toast('账户已切换，请重新打开记录');closeModal();return;}const current=state.jobs.find(j=>j.id===id);if(!current)return;const before=clone(current),f=e.currentTarget.elements;try{const next=C.updateStatus(current,f.status.value,f.date.value,f.note.value.trim(),f.followUpAt.value);Object.assign(current,next);saveState();closeModal();setUndo('进度已保存',()=>{const live=state.jobs.find(j=>j.id===id);if(live&&JSON.stringify(live)===JSON.stringify(next)){for(const key of Object.keys(live))delete live[key];Object.assign(live,before);}else toast('记录已有后续修改，未回退');});}catch(err){toast(err.message);}};
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
  const baseOpenModal=openModal,baseCloseModal=closeModal;
  openModal=function(title,html){if(!$('#quickModal').classList.contains('show'))lastFocus=document.activeElement;baseOpenModal(title,html);$('.app-shell').inert=true;setTimeout(()=>$('#modalBody input, #modalBody select, #modalBody button, #closeModal')?.focus(),0);};
  closeModal=function(){baseCloseModal();$('.app-shell').inert=false;if(lastFocus?.isConnected)lastFocus.focus();lastFocus=null;};
  $('#closeModal').onclick=()=>closeModal();$('#modalBackdrop').onclick=()=>closeModal();
  document.addEventListener('keydown',e=>{if(e.isComposing)return;const modal=$('#quickModal');if(e.key==='Tab'&&modal.classList.contains('show')){const focusable=[...modal.querySelectorAll('button,input,select,textarea,a[href],[tabindex="0"]')].filter(x=>!x.disabled&&x.getClientRects().length);const first=focusable[0],last=focusable.at(-1);if(e.shiftKey&&(document.activeElement===first||!modal.contains(document.activeElement))){e.preventDefault();last?.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}}if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='k'){e.preventDefault();switchView('discover');$('#jobSearch')?.focus();}},true);
  const nativeSet=Storage.prototype.setItem;
  Storage.prototype.setItem=function(key,value){if(this===localStorage&&String(key).startsWith('pto.secure.local.v2.')){const previous=this.getItem(key);if(previous&&previous!==value){try{const vault=JSON.parse(previous);if(vault.schema==='pto-encrypted-vault'){const bk=BACKUP+String(key).slice('pto.secure.local.v2.'.length);const history=JSON.parse(this.getItem(bk)||'[]');nativeSet.call(this,bk,JSON.stringify([{savedAt:new Date().toISOString(),vault},...history].slice(0,3)));}}catch(_){/* Backup quota must never block the primary encrypted write. */}}}return nativeSet.call(this,key,value);};
  function backup(){const entries={};for(let i=0;i<localStorage.length;i++){const k=localStorage.key(i);if(k.startsWith('pto.secure.local.v2.')||k.startsWith(BACKUP)||k==='pto.secure.device-account.v1')entries[k]=localStorage.getItem(k);}if(!Object.keys(entries).some(k=>k.startsWith('pto.secure.local.v2.'))){toast('当前浏览器尚无加密账户；可在洞察页导出个人数据');return;}const a=document.createElement('a'),url=URL.createObjectURL(new Blob([JSON.stringify({format:'pto-encrypted-device-backup-v15',createdAt:new Date().toISOString(),entries},null,2)],{type:'application/json'}));a.href=url;a.download=`path-to-offer-encrypted-${today()}.json`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);toast('已导出密文；请同时保留原密码');}
  async function restoreBackup(file){if(!file)return;try{if(file.size>30000000)throw Error('备份过大');const doc=JSON.parse(await file.text());if(doc.format!=='pto-encrypted-device-backup-v15'||!doc.entries)throw Error('请选择加密设备备份文件');const items=Object.entries(doc.entries).filter(([k])=>/^pto\.secure\.local\.v2\.[a-f0-9]{64}$/.test(k));if(!items.length)throw Error('备份中没有加密账户');for(const [,v] of items){const b=JSON.parse(v);if(b.schema!=='pto-encrypted-vault')throw Error('备份格式错误');}if(!confirm(`恢复 ${items.length} 个加密账户副本？本机已有账户不覆盖，只保存为可恢复快照。`))return;for(const [k,v] of items){if(localStorage.getItem(k)){const bk=BACKUP+k.slice('pto.secure.local.v2.'.length),old=JSON.parse(localStorage.getItem(bk)||'[]');nativeSet.call(localStorage,bk,JSON.stringify([{savedAt:new Date().toISOString(),vault:JSON.parse(v)},...old].slice(0,3)));}else nativeSet.call(localStorage,k,v);}if(!window.PTO_DEVICE_ACCOUNT_HINT?.read()){const hint=doc.entries['pto.secure.device-account.v1'];if(hint)window.PTO_DEVICE_ACCOUNT_HINT?.remember(JSON.parse(hint));}window.PTO_DEVICE_ACCOUNT_HINT?.sync();toast('密文已恢复；在账户中使用原密码解锁');}catch(err){toast('未恢复：'+err.message);}}
  function sourcesPanel(){const groups=[...(sourceStatus?.sources||[])];const rows=supplementalStatus.sources||[];openModal('信源覆盖与数据质量',`<p class="v15-note">这里仅展示公开招聘数据，不读取或切换你的账户。来源登记、抓到岗位、完整分页是不同状态；本次未抓到岗位不等于企业停止招聘。</p><div class="v15-summary"><div><strong>${marketJobs.filter(C.official).length.toLocaleString()}</strong><span>官网来源记录</span></div><div><strong>${marketJobs.filter(C.isLead).length}</strong><span>待复核线索</span></div></div><h3>新增来源的逐家结果</h3>${rows.length?rows.map(s=>`<div class="v15-source-row"><div><strong>${esc(s.company)}</strong><small>${esc(s.checked_at||'尚未检查')}${s.last_success_at?' · 上次成功 '+esc(s.last_success_at):''}</small></div><span class="v15-badge">${s.ok?'本轮采集 '+s.count+' 条':s.preserved_previous?'暂不可用 · 保留 '+s.count+' 条':s.checked_at?'未取得有效职位':'待巡检'}</span></div>`).join(''):'<p class="v15-note">新增信源刷新结果暂未载入，现有岗位目录仍可使用。</p>'}<h3>现有采集组</h3>${groups.map(s=>`<div class="v15-source-row"><strong>${esc(s.label||s.name)}</strong><span>${s.ok?'正常':'异常'} · ${Number(s.count||0)} 条</span></div>`).join('')}`);}
  function setup(){
    const skip=document.createElement('a');skip.className='v15-skip';skip.href='#jobSearch';skip.textContent='跳到岗位搜索';document.body.prepend(skip);
    $('.brand small').textContent='求职工作台';$('.brand strong').insertAdjacentHTML('beforeend','<span class="v15-app-version">1.5</span>');
    $('#discoverView h1').textContent='找到机会，推进下一步。';$('#discoverView .page-head p:not(.eyebrow)').textContent='搜索真实岗位，区分待核验线索；简历留在本机，投递进度由你掌握。';
    const toolbar=document.createElement('div');toolbar.className='v15-toolbar';toolbar.innerHTML='<label>证据<select id="v15Evidence"><option value="all">全部记录</option><option value="official">仅官网采集</option><option value="leads">仅待复核线索</option></select></label><label>招聘类型<select id="v15Kind"><option value="all">全部类型</option><option value="campus">校园 / 应届</option><option value="intern">实习</option><option value="social">明确社招</option></select></label><button id="v15ResetFilters" class="btn ghost">清除筛选</button><button id="v15SourceButton" class="text-btn">信源覆盖</button>';
    $('.discovery-toolbar').insertAdjacentElement('afterend',toolbar);
    for(const [id,key] of [['v15Evidence','evidence'],['v15Kind','kind']]){$('#'+id).value=prefs[key];$('#'+id).onchange=e=>{prefs[key]=e.target.value;storePrefs();renderMarket();};}
    $('#v15ResetFilters').onclick=()=>{prefs.kind=prefs.evidence='all';$('#jobSearch').value='';$('#v15Evidence').value=$('#v15Kind').value='all';for(const s of ['#jobLocationFilter','#jobTypeFilter','#jobBatchFilter'])$(s).value='all';storePrefs();window.PTO_RANKING_V14?.clearCache?.();renderMarket();};$('#v15SourceButton').onclick=sourcesPanel;
    const actions=document.createElement('div');actions.className='v15-toolbar';actions.innerHTML='<label>范围<select id="v15Scope"><option value="all">全部记录</option><option value="active">正在推进</option><option value="interview">面试阶段</option><option value="due">到期跟进</option></select></label><label><input type="checkbox" id="v15HideEmpty">隐藏空阶段</label><button class="btn ghost" id="v15Backup">导出加密备份</button><label class="btn ghost">导入加密备份<input hidden type="file" id="v15Restore" accept=".json"></label><span class="v15-backup-status">加密账户另保留最近 3 个本机密文快照</span>';
    $('#pipelineView .filter-row').insertAdjacentElement('afterend',actions);$('#v15Scope').onchange=e=>{prefs.scope=e.target.value;storePrefs();renderPipeline();};$('#v15HideEmpty').checked=prefs.hideEmpty;$('#v15HideEmpty').onchange=e=>{prefs.hideEmpty=e.target.checked;storePrefs();renderPipeline();};$('#v15Backup').onclick=backup;$('#v15Restore').onchange=e=>restoreBackup(e.target.files[0]);
    $('#toast').setAttribute('role','status');$('#toast').setAttribute('aria-live','polite');$('#jobSearch').setAttribute('aria-label','搜索公司、岗位、技能或城市');$('#closeModal').setAttribute('aria-label','关闭对话框');
    const stylesheet=document.createElement('link');stylesheet.rel='stylesheet';stylesheet.href='workspace-v15.css?v=1.5.0';document.head.appendChild(stylesheet);
    const fixMeta=()=>{$('meta[name="theme-color"]')?.setAttribute('content',document.documentElement.dataset.appearance==='dark'?'#111113':'#f5f5f7');};fixMeta();new MutationObserver(fixMeta).observe(document.documentElement,{attributes:true,attributeFilter:['data-appearance']});
    renderAll();
  }
  window.PTO_WORKSPACE_V15={quickUpdate,backup,restoreBackup,sourcesPanel,version:'1.5.0'};
  setup();
})();
