(function(){
  'use strict';
  if(!window.PTO_MATCHING||typeof marketJobs==='undefined'||typeof state==='undefined')return;
  const CORE=window.PTO_MATCHING;
  const TIER1=['北京','上海','深圳','广州','杭州'];
  const DEFAULT_LOCATIONS=['北京','上海','深圳','杭州','广州'];
  const PORTALS={
    '京东':'https://zhaopin.jd.com/','腾讯':'https://join.qq.com/','字节跳动':'https://jobs.bytedance.com/campus',
    '阿里':'https://campus-talent.alibaba.com/','阿里巴巴':'https://campus-talent.alibaba.com/','美团':'https://zhaopin.meituan.com/',
    '百度':'https://talent.baidu.com/','华为':'https://career.huawei.com/','小米':'https://hr.xiaomi.com/',
    '快手':'https://zhaopin.kuaishou.cn/','拼多多':'https://careers.pinduoduo.com/','大疆':'https://we.dji.com/'
  };

  let jobById=new Map();
  let catalogRevision=0;
  let recommendationCache={key:'',rows:[]};
  let renderQueued=false;

  function safeUrl(value){
    const u=String(value||'').trim();
    return /^https?:\/\//i.test(u)?u:'';
  }
  function officialPortal(company){
    const name=String(company||'');
    const row=Object.entries(PORTALS).find(([k])=>name.includes(k));
    return row?row[1]:'';
  }
  function effectiveUrl(job){return safeUrl(job?.applyUrl||job?.noticeUrl)||officialPortal(job?.company);}
  function isOfficial(job){return !!CORE.sourceSignal?.(job)?.official||/(?:公司官网|官方招聘)/.test(String(job?.sourceLabel||''));}
  function norm(v){return CORE.norm?CORE.norm(v):String(v||'').toLowerCase();}
  function splitTerms(query){return norm(query).split(/[\s,，、/]+/).filter(Boolean);}
  function aliases(term){
    const out=[term];
    for(const [name,list] of Object.entries(CORE.COMPANY_ALIASES||{})){
      const xs=[name,...list].map(norm);
      if(xs.some(x=>x===term||x.includes(term)||term.includes(x)))out.push(...xs);
    }
    return [...new Set(out)];
  }

  function prepareJob(job){
    const family=CORE.classifyJob?CORE.classifyJob(job):{primary:'unknown',families:[]};
    const geo=CORE.geoSignal?CORE.geoSignal(job,{targetLocations:DEFAULT_LOCATIONS}):{};
    const company=norm(job.company),role=norm(job.role),location=norm(job.location),department=norm(job.department),industry=norm(job.industry);
    // A bounded search body is enough for retrieval. Avoid re-normalizing every
    // JD for every keystroke; that was the main v0.6 search latency source.
    const body=norm(String(job.jd||'').slice(0,420));
    job.__v7={company,role,location,department,industry,body,search:`${company}\n${role}\n${department}\n${location}\n${industry}\n${body}`,family,geo,official:isOfficial(job),url:effectiveUrl(job)};
    return job;
  }
  function rebuildIndex(){
    jobById=new Map();
    for(const job of marketJobs){prepareJob(job);jobById.set(job.id,job);}
    catalogRevision++;
    recommendationCache={key:'',rows:[]};
  }
  function jobFor(id){return jobById.get(id)||marketJobs.find(j=>j.id===id)||null;}

  function preferenceMode(){return state.preferences.geoMode||'tier1';}
  function setDefaultPreferences(force=false){
    state.preferences=state.preferences||{};
    let changed=false;
    if(force||!(state.preferences.targetLocations||[]).length){state.preferences.targetLocations=[...DEFAULT_LOCATIONS];changed=true;}
    if(!state.preferences.geoMode){state.preferences.geoMode='tier1';changed=true;}
    if(changed)saveState(false);
  }
  function geoPass(job,mode=preferenceMode()){
    const loc=String(job.location||'');
    if(job.__v7?.geo?.foreign)return false;
    if(mode==='beijing')return loc.includes('北京');
    if(mode==='tier1')return TIER1.some(c=>loc.includes(c));
    return true;
  }

  function cheapPriority(job,profile){
    const pf=CORE.profileFamilies?CORE.profileFamilies(profile).weights:new Map();
    const fams=job.__v7?.family?.families?.length?job.__v7.family.families:[job.__v7?.family?.primary];
    const family=Math.max(0,...fams.map(f=>pf.get(f)||0));
    const loc=String(job.location||'');
    const geo=loc.includes('北京')?14:TIER1.some(c=>loc.includes(c))?8:2;
    const career=CORE.careerSignal?CORE.careerSignal(job):{level:'unknown'};
    const early=career.level==='early'?10:career.level==='senior'?-30:0;
    const official=job.__v7?.official?6:0;
    return family*10+geo+early+official;
  }

  function scoreKey(profile){
    const s=profile?.signals||{};
    return [catalogRevision,profile?.id||profile?.name||'',profile?.profileVersion||'',s.primaryDirection||'',(state.preferences.targetDirections||[]).join('|'),(state.preferences.targetLocations||[]).join('|')].join('::');
  }
  function scoreCached(job,profile){
    if(!profile)return {score:null,reasons:[],hits:[],family:job.__v7?.family||{}};
    const key=scoreKey(profile);
    job.__v7Scores=job.__v7Scores||new Map();
    if(job.__v7Scores.has(key))return job.__v7Scores.get(key);
    const value=CORE.scoreJob(job,profile,{targetLocations:state.preferences.targetLocations||[],targetDirections:state.preferences.targetDirections||[],ageDays:daysAgo(job.updatedAt)});
    if(job.__v7Scores.size>3)job.__v7Scores.clear();
    job.__v7Scores.set(key,value);
    return value;
  }

  function queryBoost(job,query){
    const q=norm(query);const terms=splitTerms(q);const idx=job.__v7||prepareJob(job);
    let matched=true;
    for(const term of terms){if(!aliases(term).some(a=>idx.search.includes(a))){matched=false;break;}}
    if(!matched)return -1;
    const qAliases=aliases(q);
    if(qAliases.some(a=>idx.company===a||idx.company.startsWith(a)))return 120;
    if(qAliases.some(a=>idx.company.includes(a)))return 100;
    if(idx.role.includes(q))return 80;
    if(idx.department.includes(q))return 60;
    if(idx.location.includes(q))return 45;
    return 20;
  }

  function recommendationBase(profile){
    const key=scoreKey(profile);
    if(recommendationCache.key===key)return recommendationCache.rows;
    const pf=CORE.profileFamilies?CORE.profileFamilies(profile).weights:new Map();
    let candidates=marketJobs.filter(j=>!j.__v7?.geo?.foreign);
    if(profile&&pf.size){
      // Remove clear role-family contradictions before expensive semantic scoring.
      // Unknown titles remain eligible because some company sites use generic
      // “研发工程师” titles whose department/JD contains the real specialization.
      candidates=candidates.filter(j=>{
        const fam=j.__v7?.family?.primary||'unknown';
        return fam==='unknown'||(j.__v7?.family?.families||[]).some(f=>pf.has(f));
      });
    }
    candidates.sort((a,b)=>cheapPriority(b,profile)-cheapPriority(a,profile));
    // A role-family prefilter gives better precision while bounding full scoring.
    // 6k is intentionally above a normal user's useful retrieval horizon.
    candidates=candidates.slice(0,6000);
    const rows=candidates.map(job=>({...job,match:scoreCached(job,profile),_age:daysAgo(job.updatedAt)}));
    rows.sort((a,b)=>(b.match.score??-1)-(a.match.score??-1)||cheapPriority(b,profile)-cheapPriority(a,profile)||String(b.updatedAt||'').localeCompare(String(a.updatedAt||'')));
    recommendationCache={key,rows};
    return rows;
  }

  visibleMarketJobs=function(){
    const q=(document.querySelector('#jobSearch')?.value||'').trim();
    const loc=document.querySelector('#jobLocationFilter')?.value||'all';
    const typ=document.querySelector('#jobTypeFilter')?.value||'all';
    const batch=document.querySelector('#jobBatchFilter')?.value||'all';
    const threshold=Number(document.querySelector('#scoreThreshold')?.value||0);
    const freshOnly=!!document.querySelector('#freshOnly')?.checked;
    const profile=currentProfile();
    const hidden=state.decisions||{};

    if(q){
      // Retrieval first: no resume scoring until the compact precomputed index
      // has reduced the catalogue. Exact company/title search therefore stays fast.
      let rows=[];
      for(const job of marketJobs){
        if(hidden[job.id]==='hidden')continue;
        if(loc!=='all'&&!String(job.location||'').includes(loc))continue;
        if(typ!=='all'&&job.companyType!==typ)continue;
        if(batch!=='all'&&job.batch!==batch)continue;
        const boost=queryBoost(job,q);if(boost<0)continue;
        rows.push({...job,_searchBoost:boost,match:{score:null,reasons:[],hits:[]}});
      }
      rows.sort((a,b)=>b._searchBoost-a._searchBoost||String(b.updatedAt||'').localeCompare(String(a.updatedAt||'')));
      // Score only a bounded top slice for explanatory match badges. Retrieval
      // correctness and result count do not depend on the resume score.
      if(profile)for(let i=0;i<Math.min(rows.length,500);i++)rows[i].match=scoreCached(rows[i],profile);
      return rows;
    }

    let rows=recommendationBase(profile).filter(j=>hidden[j.id]!=='hidden');
    const mode=preferenceMode();
    rows=rows.filter(j=>geoPass(j,mode));
    rows=rows.filter(j=>(loc==='all'||String(j.location||'').includes(loc))&&(typ==='all'||j.companyType===typ)&&(batch==='all'||j.batch===batch));
    if(profile)rows=rows.filter(j=>(j.match.score??0)>=threshold);
    if(freshOnly&&rows.some(j=>j.updatedAt))rows=rows.filter(j=>!j.updatedAt||j._age<=30);
    if(marketSort==='fresh')rows=[...rows].sort((a,b)=>String(b.updatedAt||'').localeCompare(String(a.updatedAt||'')));
    else if(marketSort==='company')rows=[...rows].sort((a,b)=>String(a.company||'').localeCompare(String(b.company||''),'zh-CN'));
    return rows;
  };

  const baseCard=marketJobCard;
  marketJobCard=function(j){
    const m=j.match||{score:null,reasons:[]};const score=m.score;const url=effectiveUrl(j);const official=isOfficial(j);
    return `<article class="market-card v7-card" data-market-id="${esc(j.id)}" tabindex="0" role="button" aria-label="查看 ${esc(j.company)} ${esc(j.role)} 详情"><div class="market-card-top"><div class="company-logo">${esc((j.company||'?').slice(0,1))}</div><div class="market-card-title"><h3>${esc(j.role||'未命名岗位')}</h3><p>${esc(j.company||'未知公司')}</p></div>${score==null?'':`<div class="match-score ${score>=75?'high':score>=55?'mid':'low'}"><strong>${score}</strong><small>match</small></div>`}</div><div class="job-facts">${[j.location,j.batch,j.companyType,j.education,j.graduation].filter(Boolean).slice(0,5).map(x=>`<span>${esc(x)}</span>`).join('')}${official?'<span class="official-chip">企业官网</span>':''}</div>${(m.reasons||[]).length?`<div class="match-reasons">${m.reasons.slice(0,4).map(x=>`<span>${esc(x)}</span>`).join('')}</div>`:''}<div class="market-card-foot"><span class="source-tag">${esc(j.sourceLabel||'公开招聘来源')}</span><span class="muted">${j.updatedAt?`${fmt(j.updatedAt)} 更新`:'更新时间未知'}</span><div class="card-spacer"></div><button class="text-btn quiet" data-action="hide" data-hide-job="${esc(j.id)}">不合适</button><button class="btn tiny ghost" data-action="open" data-open-job="${esc(j.id)}">查看详情</button>${url?`<a class="btn tiny ghost official-apply" data-action="apply" href="${esc(url)}" target="_blank" rel="noopener noreferrer">官网投递 ↗</a>`:''}<button class="btn tiny primary" data-action="save" data-save-job="${esc(j.id)}">加入流程</button></div></article>`;
  };
  marketJobTable=function(rows){
    return `<table class="job-table market-table"><thead><tr><th>匹配</th><th>企业</th><th>岗位</th><th>地点</th><th>批次</th><th>来源</th><th>更新</th><th>操作</th></tr></thead><tbody>${rows.map(j=>{const url=effectiveUrl(j);return `<tr data-market-id="${esc(j.id)}"><td><strong>${j.match?.score??'—'}</strong></td><td>${esc(j.company)}</td><td>${esc(j.role)}</td><td>${esc(j.location)}</td><td>${esc(j.batch)}</td><td>${isOfficial(j)?'企业官网':esc(j.sourceLabel||'公开来源')}</td><td>${fmt(j.updatedAt)}</td><td class="row-actions"><button class="text-btn" data-action="open" data-open-job="${esc(j.id)}">详情</button>${url?`<a class="text-btn" data-action="apply" href="${esc(url)}" target="_blank" rel="noopener noreferrer">投递 ↗</a>`:''}<button class="text-btn" data-action="save" data-save-job="${esc(j.id)}">加入流程</button></td></tr>`;}).join('')}</tbody></table>`;
  };

  openMarketJob=function(id){
    const j=jobFor(id);if(!j)return;
    const m=scoreCached(j,currentProfile());const url=effectiveUrl(j);const sourceOfficial=isOfficial(j);
    document.querySelector('#drawerEyebrow').textContent='JOB DETAIL';
    document.querySelector('#drawerTitle').textContent=j.company||'岗位详情';
    document.querySelector('#jobForm').classList.add('hidden');
    const detail=document.querySelector('#marketJobDetail');detail.classList.remove('hidden');
    detail.innerHTML=`<div class="detail-hero"><div><p class="eyebrow">${sourceOfficial?'企业官网直采':'公开招聘来源'} · ${j.updatedAt?esc(fmt(j.updatedAt)):'更新时间未知'}</p><h2>${esc(j.role)}</h2><p>${esc(j.company)}${j.department?` · ${esc(j.department)}`:''}</p></div>${m.score==null?'':`<div class="detail-score"><strong>${m.score}</strong><span>简历匹配</span></div>`}</div><div class="detail-facts">${[['地点',j.location],['薪资',j.salary],['批次',j.batch],['性质',j.companyType],['行业',j.industry],['届别',j.graduation],['学历',j.education]].filter(x=>x[1]).map(([a,b])=>`<div><small>${a}</small><strong>${esc(b)}</strong></div>`).join('')}</div>${(m.reasons||[]).length?`<section class="detail-section"><p class="eyebrow">WHY THIS MATCH</p><div class="reason-grid">${m.reasons.map(x=>`<span>${esc(x)}</span>`).join('')}</div></section>`:''}<section class="detail-section"><p class="eyebrow">JOB DESCRIPTION · 预览</p><div class="jd-text">${esc(j.jd||'职位源暂未提供 JD 预览，请打开企业官网查看完整职位。')}</div>${url?'<p class="detail-note">完整 JD 与最新状态以企业招聘官网为准。</p>':''}</section><div class="detail-actions">${url?`<a class="btn primary" id="detailApply" target="_blank" rel="noopener noreferrer" href="${esc(url)}">打开企业官网投递 ↗</a><button class="btn ghost" data-copy-job-url="${esc(j.id)}">复制投递链接</button>`:''}<button class="btn ghost" id="detailPromote">加入我的流程</button></div>`;
    document.querySelector('#detailPromote').onclick=()=>promoteMarketJob(j.id,true);
    openDrawer();
  };

  const basePromote=promoteMarketJob;
  promoteMarketJob=function(id,close=false){
    const j=jobFor(id);if(!j)return;
    if(state.jobs.some(x=>x.sourceJobId===j.id)){toast('这个岗位已经在流程里');return;}
    const match=scoreCached(j,currentProfile());const p=currentProfile();const url=effectiveUrl(j);
    state.jobs.unshift({id:uid('job'),sourceJobId:j.id,source:j.source,company:j.company,department:j.department,role:j.role,location:j.location,salary:j.salary,direction:match.direction||match.family?.primary||'',priority:match.score!=null&&match.score>=72?'A':'B',status:'discovered',statusDate:today(),url,jd:j.jd,resumeVersion:p?.name||'',prepUrl:'',notes:'',matchAtSave:match.score,timeline:[{status:'discovered',date:today()}]});
    state.decisions[id]='saved';saveState(false);renderAll();if(close)closeDrawer();toast('已加入投递流程，可继续官网投递');
  };

  const baseOpenJob=openJob;
  openJob=function(id=null){
    baseOpenJob(id);
    if(!id)return;
    const job=state.jobs.find(j=>j.id===id);const url=safeUrl(job?.url);
    const form=document.querySelector('#jobForm');
    if(!form||!job)return;
    let actions=form.querySelector('.pipeline-quick-actions');
    if(!actions){actions=document.createElement('div');actions.className='pipeline-quick-actions';form.prepend(actions);}
    actions.innerHTML=`<div><strong>${esc(job.company)} · ${esc(job.role)}</strong><small>${esc(job.location||'地点待确认')} · ${esc(job.resumeVersion||'未绑定简历')}</small></div><div class="pipeline-action-buttons">${url?`<a class="btn primary" target="_blank" rel="noopener noreferrer" href="${esc(url)}">打开投递页 ↗</a><button type="button" class="btn ghost" data-copy-pipeline-url="${esc(job.id)}">复制链接</button>`:''}${job.status!=='applied'?`<button type="button" class="btn ghost" data-mark-applied="${esc(job.id)}">标记已投递</button>`:''}</div>`;
  };

  function markApplied(id){
    const job=state.jobs.find(j=>j.id===id);if(!job)return;
    job.status='applied';job.statusDate=today();job.timeline=job.timeline||[];
    if(!job.timeline.some(x=>x.status==='applied'&&x.date===job.statusDate))job.timeline.push({status:'applied',date:job.statusDate});
    saveState(false);renderAll();closeDrawer();toast('已标记为已投递');
  }
  async function copyText(value){
    if(!value)return;
    try{await navigator.clipboard.writeText(value);toast('投递链接已复制');return;}catch(_){ }
    const ta=document.createElement('textarea');ta.value=value;ta.style.position='fixed';ta.style.opacity='0';document.body.appendChild(ta);ta.select();
    try{document.execCommand('copy');toast('投递链接已复制');}finally{ta.remove();}
  }

  function ensureGeoControls(){
    const toolbar=document.querySelector('.discovery-toolbar');if(!toolbar||document.querySelector('#geoQuickFilters'))return;
    const wrap=document.createElement('div');wrap.id='geoQuickFilters';wrap.className='geo-quick-filters';
    wrap.innerHTML=`<span>岗位范围</span><button type="button" data-geo-mode="beijing">北京</button><button type="button" data-geo-mode="tier1">一线城市</button><button type="button" data-geo-mode="china">全国</button><small>默认只推荐国内岗位；北京优先排序。</small>`;
    toolbar.insertAdjacentElement('afterend',wrap);updateGeoControls();
  }
  function updateGeoControls(){document.querySelectorAll('[data-geo-mode]').forEach(b=>b.classList.toggle('active',b.dataset.geoMode===preferenceMode()));}
  function updateCoverageSummary(){
    const focus=sourceStatus.china_focus||{};const health=document.querySelector('#feedHealth');if(!health||!sourceStatus.generated_at)return;
    const when=new Date(sourceStatus.generated_at);const label=Number.isNaN(when.getTime())?sourceStatus.generated_at:when.toLocaleString('zh-CN',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'});
    const official=Number(focus.company_official_count||0).toLocaleString();const bj=Number(focus.beijing_count||0).toLocaleString();const tier1=Number(focus.tier1_count||0).toLocaleString();const ratio=Math.round(Number(focus.direct_link_ratio||0)*100);
    health.innerHTML=`<span class="pulse-dot"></span><span>${esc(label)} · 国内官网 ${official} · 北京 ${bj} · 一线 ${tier1} · 直链 ${ratio||0}%</span>`;
  }

  showSources=function(){
    const sources=sourceStatus.sources||[];const focus=sourceStatus.china_focus||{};
    const rows=sources.length?sources.map(s=>`<div class="source-status-row"><div><strong>${esc(s.label||s.name||s.source)}</strong><small>${esc(s.url||'')}</small></div><span class="source-health ${s.ok?'ok':'bad'}">${s.ok?`${Number(s.count||0).toLocaleString()} 条`:`异常 · ${esc(s.error||'unknown')}`}</span></div>`).join(''):'<div class="empty-state"><strong>尚无刷新记录</strong></div>';
    openModal('岗位源与刷新状态',`<div class="source-modal"><p><strong>v0.7 中国校招优先：</strong>主数据来自企业自己的公开招聘系统（自建招聘 API / 飞书招聘 / 北森 / Moka 企业招聘门户）；公开校招表只作补充，不再用海外 ATS 大盘填充推荐数量。</p><div class="source-focus-grid"><span>岗位池 <b>${Number(sourceStatus.catalog_count||marketJobs.length).toLocaleString()}</b></span><span>北京 <b>${Number(focus.beijing_count||0).toLocaleString()}</b></span><span>一线 <b>${Number(focus.tier1_count||0).toLocaleString()}</b></span><span>官网直链 <b>${Math.round(Number(focus.direct_link_ratio||0)*100)}%</b></span></div>${rows}<div class="source-foot"><span>完整 JD、职位是否仍开放及最终投递结果以企业招聘官网为准。</span></div></div>`);
  };

  const baseHandleResume=handleResumeFile;
  handleResumeFile=async function(file){
    const before=state.activeResumeId;await baseHandleResume(file);
    if(state.activeResumeId&&state.activeResumeId!==before){
      setDefaultPreferences(true);
      const search=document.querySelector('#jobSearch');if(search)search.value='';
      const threshold=document.querySelector('#scoreThreshold');if(threshold){threshold.value='28';document.querySelector('#scoreThresholdLabel').textContent='28';}
      marketSort='match';recommendationCache={key:'',rows:[]};renderAll();
      setTimeout(()=>{document.querySelector('.market-head')?.scrollIntoView({behavior:'smooth',block:'start'});const n=visibleMarketJobs().length;toast(`简历解析完成 · 已生成 ${n.toLocaleString()} 个国内匹配岗位`);},30);
    }
  };

  const basePasteResume=pasteResume;
  pasteResume=function(){
    basePasteResume();const btn=document.querySelector('#parsePastedResume');if(!btn)return;
    const old=btn.onclick;btn.onclick=()=>{old?.();setTimeout(()=>{if(currentProfile()){setDefaultPreferences(true);recommendationCache={key:'',rows:[]};renderAll();}},0);};
  };

  const oldLoadFeeds=loadFeeds;
  loadFeeds=async function(){await oldLoadFeeds();rebuildIndex();setDefaultPreferences(false);ensureGeoControls();updateCoverageSummary();requestMarketRender();};

  // market-v06 and v0.4 both receive the same input event. Coalesce duplicate
  // render requests into one animation frame instead of ranking twice per key.
  const immediateRender=renderMarket;
  function requestMarketRender(){
    if(renderQueued)return;renderQueued=true;
    const run=()=>{renderQueued=false;immediateRender();updateGeoControls();updateCoverageSummary();};
    if(typeof requestAnimationFrame==='function')requestAnimationFrame(run);else setTimeout(run,0);
  }
  renderMarket=requestMarketRender;

  function injectStyles(){
    if(document.querySelector('#ptoV07Style'))return;
    const style=document.createElement('style');style.id='ptoV07Style';style.textContent=`
      .geo-quick-filters{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin:-8px 0 14px 216px;font-size:10px;color:var(--muted)}.geo-quick-filters>span{font-weight:650;color:var(--text);margin-right:2px}.geo-quick-filters button{border:1px solid var(--line);background:var(--surface);color:var(--muted);border-radius:999px;padding:5px 9px;cursor:pointer}.geo-quick-filters button.active{background:var(--accent-soft);border-color:var(--accent);color:var(--accent-strong);font-weight:650}.geo-quick-filters small{margin-left:4px}
      .official-chip{background:var(--accent-soft)!important;color:var(--accent-strong)!important;border-color:var(--accent)!important}.v7-card{cursor:pointer}.v7-card:focus-visible{outline:2px solid var(--accent-strong);outline-offset:2px}.official-apply{white-space:nowrap}.row-actions{white-space:nowrap}.row-actions>*{margin-right:7px}.detail-note{font-size:10px;color:var(--muted);margin-top:8px}.pipeline-quick-actions{display:flex;align-items:center;justify-content:space-between;gap:12px;border:1px solid var(--line);border-radius:13px;padding:10px 12px;background:var(--surface-2);margin-bottom:14px}.pipeline-quick-actions strong,.pipeline-quick-actions small{display:block}.pipeline-quick-actions small{font-size:10px;color:var(--muted);margin-top:3px}.pipeline-action-buttons{display:flex;gap:6px;flex-wrap:wrap;justify-content:flex-end}.source-focus-grid{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin:12px 0}.source-focus-grid span{border:1px solid var(--line);border-radius:10px;padding:8px;font-size:10px;color:var(--muted)}.source-focus-grid b{display:block;color:var(--text);font-size:14px;margin-top:2px}
      @media(max-width:900px){.geo-quick-filters{margin:-4px 0 12px}.market-card-foot{align-items:flex-start;flex-wrap:wrap}.card-spacer{display:none}.pipeline-quick-actions{align-items:flex-start;flex-direction:column}.pipeline-action-buttons{justify-content:flex-start}.source-focus-grid{grid-template-columns:1fr 1fr}}
    `;document.head.appendChild(style);
  }

  document.addEventListener('click',e=>{
    const open=e.target.closest('[data-open-job]');if(open){e.preventDefault();e.stopPropagation();openMarketJob(open.dataset.openJob);return;}
    const geo=e.target.closest('[data-geo-mode]');if(geo){state.preferences.geoMode=geo.dataset.geoMode;saveState(false);recommendationCache={key:'',rows:[]};updateGeoControls();renderMarket();return;}
    const copy=e.target.closest('[data-copy-job-url]');if(copy){copyText(effectiveUrl(jobFor(copy.dataset.copyJobUrl)));return;}
    const copyPipe=e.target.closest('[data-copy-pipeline-url]');if(copyPipe){copyText(state.jobs.find(j=>j.id===copyPipe.dataset.copyPipelineUrl)?.url);return;}
    const applied=e.target.closest('[data-mark-applied]');if(applied){markApplied(applied.dataset.markApplied);return;}
  },true);
  document.addEventListener('keydown',e=>{
    if(!['Enter',' '].includes(e.key))return;const card=e.target.closest?.('.market-card[data-market-id]');if(!card||e.target.closest('[data-action]'))return;e.preventDefault();openMarketJob(card.dataset.marketId);
  });

  injectStyles();rebuildIndex();setDefaultPreferences(false);ensureGeoControls();
  const pasteBtn=document.querySelector('#pasteResumeBtn');if(pasteBtn)pasteBtn.onclick=pasteResume;
  const sourceBtn=document.querySelector('#openSourcePanel');if(sourceBtn)sourceBtn.onclick=showSources;
  updateCoverageSummary();
})();
