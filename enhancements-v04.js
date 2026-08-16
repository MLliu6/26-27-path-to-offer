(function(){
  'use strict';
  if(!window.PTO_MATCHING || typeof state==='undefined') return;
  const CORE=window.PTO_MATCHING;

  const COMPANY_PORTALS={
    '京东':'https://zhaopin.jd.com/','腾讯':'https://join.qq.com/','字节跳动':'https://jobs.bytedance.com/campus','阿里':'https://talent.alibaba.com/','阿里巴巴':'https://talent.alibaba.com/','美团':'https://zhaopin.meituan.com/','百度':'https://talent.baidu.com/','华为':'https://career.huawei.com/','小米':'https://hr.xiaomi.com/','快手':'https://zhaopin.kuaishou.cn/','拼多多':'https://careers.pinduoduo.com/','大疆':'https://we.dji.com/','地平线':'https://horizon.zhiye.com/','商汤':'https://joinus.sensetime.com/'};

  const oldRenderProfile=renderProfile;
  const oldRenderMarket=renderMarket;

  function injectStyles(){
    if(document.querySelector('#ptoV04Style')) return;
    const style=document.createElement('style'); style.id='ptoV04Style'; style.textContent=`
      .profile-intelligence{display:grid;grid-template-columns:1.15fr 1fr 1fr;gap:10px;margin:-8px 0 20px}
      .intel-card{background:var(--surface);border:1px solid var(--line);border-radius:15px;padding:15px 16px;min-width:0}
      .intel-card h3{font-family:var(--serif);font-size:15px;margin:0 0 7px}.intel-card p{font-size:11px;color:var(--muted);margin:0}
      .direction-row{display:flex;align-items:center;gap:9px;margin:7px 0}.direction-row strong{font-size:12px;min-width:0;flex:1}.confidence{font-family:var(--serif);font-size:12px;color:var(--accent-strong)}
      .evidence-line{font-size:10px;color:var(--muted);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;margin-top:2px}
      .micro-bar{height:4px;border-radius:99px;background:var(--surface-2);overflow:hidden;margin-top:4px}.micro-bar>span{display:block;height:100%;background:var(--accent-strong);border-radius:inherit}
      .role-cloud,.skill-cloud-v4{display:flex;flex-wrap:wrap;gap:5px}.role-cloud span,.skill-cloud-v4 span{font-size:10px;padding:4px 7px;border:1px solid var(--line);border-radius:999px;background:#fafbf8}
      .search-policy{font-size:10px;color:var(--muted);margin:-10px 0 12px 216px}.search-policy b{color:var(--accent-strong)}
      .coverage-chip{display:inline-flex;align-items:center;gap:5px;padding:4px 8px;border-radius:999px;background:var(--accent-soft);color:var(--accent-strong);font-size:10px;margin-left:8px}
      .profile-inspector .direction-evidence{display:grid;grid-template-columns:1fr 1fr;gap:8px}.profile-inspector .direction-evidence>div{border:1px solid var(--line);border-radius:11px;padding:10px}
      .profile-inspector .direction-evidence strong{display:block;font-size:12px}.profile-inspector .direction-evidence small{display:block;color:var(--muted);font-size:10px;margin-top:3px}
      .empty-search-actions{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin-top:10px}
      @media(max-width:900px){.profile-intelligence{grid-template-columns:1fr}.search-policy{margin:-8px 0 12px}.profile-inspector .direction-evidence{grid-template-columns:1fr}}
    `; document.head.appendChild(style);
  }

  function buildV4Profile(rawText,fileName){
    const base=CORE.buildProfile(rawText,fileName); return {...base,id:uid('resume'),uploadedAt:new Date().toISOString()};
  }
  buildResumeProfile=buildV4Profile;

  const oldHandleResumeFile=handleResumeFile;
  handleResumeFile=async function(file){
    await oldHandleResumeFile(file);
    const p=currentProfile();
    if(p && !(state.preferences.targetDirections||[]).length && (p.signals?.directions||[]).length){
      state.preferences.targetDirections=p.signals.directions.slice(0,3); saveState(false); renderAll();
    }
  };

  scoreJob=function(job,profile){
    return CORE.scoreJob(job,profile,{targetLocations:state.preferences.targetLocations||[],targetDirections:state.preferences.targetDirections||[],ageDays:daysAgo(job.updatedAt||job.updated_at)});
  };

  visibleMarketJobs=function(){
    const q=(document.querySelector('#jobSearch')?.value||'').trim();
    const loc=document.querySelector('#jobLocationFilter')?.value||'all';
    const typ=document.querySelector('#jobTypeFilter')?.value||'all';
    const batch=document.querySelector('#jobBatchFilter')?.value||'all';
    const threshold=Number(document.querySelector('#scoreThreshold')?.value||0);
    const freshOnly=!!document.querySelector('#freshOnly')?.checked;
    const base=marketJobs.filter(j=>state.decisions[j.id]!=='hidden');
    return CORE.filterAndRank(base,{query:q,profile:currentProfile(),threshold,freshOnly,ageOf:daysAgo,location:loc,companyType:typ,batch,sort:marketSort,preferences:state.preferences});
  };

  function ensureProfileIntelligence(){
    let el=document.querySelector('#profileIntelligence');
    if(!el){el=document.createElement('div');el.id='profileIntelligence';el.className='profile-intelligence hidden';document.querySelector('#profileStrip')?.insertAdjacentElement('afterend',el);}
    return el;
  }
  renderProfile=function(){
    oldRenderProfile();
    const p=currentProfile(); const el=ensureProfileIntelligence(); el.classList.toggle('hidden',!p); if(!p)return;
    const s=p.signals||{}; const dirs=(s.directionScores||[]).slice(0,3); const roles=(s.recommendedRoles||[]).slice(0,8); const skills=(s.skills||[]).slice(0,12);
    el.innerHTML=`
      <article class="intel-card"><p class="eyebrow">DIRECTION PROFILE</p><h3>${esc(s.primaryDirection||dirs[0]?.name||'方向证据不足')}</h3>${dirs.length?dirs.map(d=>`<div class="direction-row"><div style="flex:1;min-width:0"><strong>${esc(d.name)}</strong><div class="evidence-line">${esc((d.evidence||[]).slice(0,4).join(' · ')||'来自简历语义信号')}</div><div class="micro-bar"><span style="width:${Math.min(100,d.confidence||0)}%"></span></div></div><span class="confidence">${d.confidence||0}%</span></div>`).join(''):'<p>暂未抽取到足够的方向证据，可点击“查看解析结果”手工补充。</p>'}</article>
      <article class="intel-card"><p class="eyebrow">CORE SIGNALS</p><h3>核心技能</h3><div class="skill-cloud-v4">${skills.length?skills.map(x=>`<span>${esc(x)}</span>`).join(''):'<span>待补充</span>'}</div><p style="margin-top:9px">学历 ${esc(s.degree||'未识别')} · 毕业 ${esc(s.graduationYear||'未识别')}</p></article>
      <article class="intel-card"><p class="eyebrow">ROLE HYPOTHESES</p><h3>建议搜索词</h3><div class="role-cloud">${roles.length?roles.map(x=>`<span>${esc(x)}</span>`).join(''):'<span>先补充目标方向</span>'}</div><p style="margin-top:9px">这些只是检索假设，不替代你的岗位选择。</p></article>`;
  };

  inspectProfile=function(){
    const p=currentProfile(); if(!p)return; const s=p.signals||{}; const dirs=(s.directionScores||[]).slice(0,6);
    openModal('候选人画像',`<div class="profile-inspector"><div class="profile-summary"><strong>${esc(p.name)}</strong><small>${esc(s.degree||'学历未识别')} · ${esc(s.graduationYear?`${s.graduationYear} 届`:'届别未识别')} · 画像引擎 v4</small></div><label><span>目标方向（逗号分隔，可手工修正）</span><input id="prefDirections" value="${esc((state.preferences.targetDirections||s.directions||[]).join(', '))}"></label><label><span>目标城市（逗号分隔）</span><input id="prefLocations" value="${esc((state.preferences.targetLocations||[]).join(', '))}" placeholder="北京, 上海, 深圳"></label><div><p class="eyebrow">DIRECTION EVIDENCE</p><div class="direction-evidence">${dirs.map(d=>`<div><strong>${esc(d.name)} · ${d.confidence||0}%</strong><small>${esc((d.evidence||[]).join(' · ')||'无显式证据')}</small></div>`).join('')||'<div><strong>证据不足</strong><small>建议直接填写目标方向。</small></div>'}</div></div><div><p class="eyebrow">SKILL SIGNALS</p><div class="signal-cloud">${(s.skills||[]).slice(0,40).map(x=>`<span>${esc(x)}</span>`).join('')||'<span>暂无</span>'}</div></div><div><p class="eyebrow">RECOMMENDED SEARCH TERMS</p><div class="signal-cloud">${(s.recommendedRoles||[]).map(x=>`<span>${esc(x)}</span>`).join('')||'<span>暂无</span>'}</div></div><div class="modal-actions"><button class="btn ghost" id="reparseResume">重新生成画像</button><button class="btn ghost" id="clearResumeText">删除原始解析文本</button><button class="btn primary" id="saveProfilePrefs">保存偏好</button></div></div>`);
    document.querySelector('#saveProfilePrefs').onclick=()=>{state.preferences.targetDirections=document.querySelector('#prefDirections').value.split(/[,，]/).map(x=>x.trim()).filter(Boolean);state.preferences.targetLocations=document.querySelector('#prefLocations').value.split(/[,，]/).map(x=>x.trim()).filter(Boolean);saveState();closeModal();toast('匹配偏好已更新');};
    document.querySelector('#clearResumeText').onclick=()=>{p.rawText='';saveState();closeModal();toast('已删除简历原始解析文本，画像信号仍保留');};
    document.querySelector('#reparseResume').onclick=()=>{if(!p.rawText){toast('原始解析文本已删除，无法重算');return;}const n=CORE.buildProfile(p.rawText,p.fileName||`${p.name}.txt`);p.signals=n.signals;p.profileVersion=4;p.displayName=n.displayName||p.displayName;saveState();closeModal();toast('画像已按 v4 规则重新生成');};
  };

  promoteMarketJob=function(id,close=false){
    const j=marketJobs.find(x=>x.id===id); if(!j)return; if(state.jobs.some(x=>x.sourceJobId===j.id)){toast('这个岗位已经在流程里');return;}
    const match=scoreJob(j,currentProfile()); const p=currentProfile();
    state.jobs.unshift({id:uid('job'),sourceJobId:j.id,source:j.source,company:j.company,department:j.department,role:j.role,location:j.location,salary:j.salary,direction:match.direction||'',priority:match.score!==null&&match.score>=72?'A':'B',status:'discovered',statusDate:today(),url:j.applyUrl||j.noticeUrl||portalFor(j.company),jd:j.jd,resumeVersion:p?.name||'',prepUrl:'',notes:'',matchAtSave:match.score,timeline:[{status:'discovered',date:today()}]});
    state.decisions[id]='saved';saveState(false);renderAll();if(close)closeDrawer();toast('已加入投递流程');
  };

  function portalFor(company){
    const c=String(company||''); return Object.entries(COMPANY_PORTALS).find(([k])=>c.includes(k))?.[1]||'';
  }
  const oldOpenMarketJob=openMarketJob;
  openMarketJob=function(id){
    const j=marketJobs.find(x=>x.id===id); if(j&&!j.applyUrl&&!j.noticeUrl){const portal=portalFor(j.company);if(portal)j.applyUrl=portal;}
    oldOpenMarketJob(id);
  };

  renderMarket=function(){
    oldRenderMarket();
    const q=(document.querySelector('#jobSearch')?.value||'').trim(); const rows=visibleMarketJobs(); const empty=document.querySelector('#jobMarketEmpty');
    if(q&&!rows.length&&marketJobs.length){
      const portal=portalFor(q); empty.classList.remove('hidden'); empty.innerHTML=`<div class="empty-orbit">⌕</div><h3>缓存岗位暂未命中“${esc(q)}”</h3><p>关键词搜索已自动绕过匹配阈值和“30 天内”限制，因此这里的 0 表示当前静态聚合缓存确实没有这家公司/岗位，而不是被简历分数误过滤。后台正在通过多源与重点公司查询扩充目录。</p><div class="empty-search-actions"><button class="text-btn" id="emptySourcesBtnV4">查看岗位源状态 →</button>${portal?`<a class="btn ghost" href="${esc(portal)}" target="_blank" rel="noopener">打开官方招聘 ↗</a>`:''}</div>`; document.querySelector('#emptySourcesBtnV4').onclick=showSources;
    }
  };

  function migrateProfiles(){
    let changed=false;
    for(const p of state.resumes||[]){if(p.rawText&&p.profileVersion!==4){const n=CORE.buildProfile(p.rawText,p.fileName||`${p.name}.txt`);p.signals=n.signals;p.profileVersion=4;p.displayName=p.displayName||n.displayName;changed=true;}}
    const p=currentProfile(); if(p&&!(state.preferences.targetDirections||[]).length&&(p.signals?.directions||[]).length){state.preferences.targetDirections=p.signals.directions.slice(0,3);changed=true;}
    if(changed)saveState(false);
  }
  function improveControls(){
    const threshold=document.querySelector('#scoreThreshold'); if(threshold&&Number(threshold.value)===55)threshold.value='25'; const label=document.querySelector('#scoreThresholdLabel');if(label)label.textContent=threshold?.value||'25';
    const search=document.querySelector('#jobSearch');if(search)search.placeholder='搜京东 / 公司 / AI Infra / CUDA / 城市…';
    const toolbar=document.querySelector('.discovery-toolbar');if(toolbar&&!document.querySelector('#searchPolicy')){const p=document.createElement('div');p.id='searchPolicy';p.className='search-policy';p.innerHTML='<b>搜索优先：</b>输入明确关键词时不受最低匹配度和“30 天内”限制；空搜索才按简历画像自动推荐。';toolbar.insertAdjacentElement('afterend',p);}
    const head=document.querySelector('.market-head h2'); if(head&&!document.querySelector('#coverageChip')){const chip=document.createElement('span');chip.id='coverageChip';chip.className='coverage-chip';chip.textContent=`缓存 ${marketJobs.length} 条`;head.appendChild(chip);}
  }
  function rebindEnhancedHandlers(){
    // app.js attached some handlers before v0.4 is dynamically loaded. Rebind the
    // handlers whose behavior was intentionally replaced rather than relying on
    // function-name lookup inside an old callback closure.
    const inspect=document.querySelector('#inspectProfileBtn'); if(inspect)inspect.onclick=inspectProfile;
    const search=document.querySelector('#jobSearch');
    if(search&&!search.dataset.v4SearchBound){
      search.dataset.v4SearchBound='1';
      search.addEventListener('input',()=>setTimeout(()=>renderMarket(),0));
    }
  }
  const oldLoadFeeds=loadFeeds;
  loadFeeds=async function(){await oldLoadFeeds();const chip=document.querySelector('#coverageChip');if(chip)chip.textContent=`缓存 ${marketJobs.length} 条`;};

  injectStyles(); migrateProfiles(); improveControls(); rebindEnhancedHandlers(); renderAll();
  setTimeout(()=>{improveControls();rebindEnhancedHandlers();renderAll();},0);
})();
