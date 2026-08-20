(function(){
  'use strict';
  if(typeof state==='undefined'||!window.PTO_MATCHING)return;
  const $=s=>document.querySelector(s);
  const $$=s=>[...document.querySelectorAll(s)];
  const nativeFetch=(typeof PTO_NATIVE_FETCH==='function')?PTO_NATIVE_FETCH:window.fetch.bind(window);
  const oldLoadFeeds=typeof loadFeeds==='function'?loadFeeds:null;
  const oldRenderFeedHealth=typeof renderFeedHealth==='function'?renderFeedHealth:null;
  const oldRenderMarket=typeof renderMarket==='function'?renderMarket:null;
  const oldOpenMarketJob=typeof openMarketJob==='function'?openMarketJob:null;
  const oldHandleResumeFile=typeof handleResumeFile==='function'?handleResumeFile:null;
  const CITIES=['北京','上海','深圳','广州','杭州','南京','成都','武汉','西安','苏州','天津','重庆','长沙','合肥','无锡','厦门','青岛','济南','宁波','东莞'];
  const RUNTIME=window.PTO_FEED_RUNTIME={state:'booting',failures:[],loadMs:0,usedPrevious:false,jobsLoaded:0,lastSuccessAt:null};
  let searchTimer=null;

  function ensureStyles(){
    if($('#ptoV14Style'))return;
    const style=document.createElement('style');style.id='ptoV14Style';style.textContent=`
      .match-score:after{content:'FIT'!important;letter-spacing:.04em}.match-score small{max-width:72px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      .pto-market-summary{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:0 0 14px}.pto-summary-cell{border:1px solid var(--line);background:var(--surface);border-radius:12px;padding:10px 12px;min-width:0}.pto-summary-cell small{display:block;color:var(--muted);font-size:9px;text-transform:uppercase;letter-spacing:.08em}.pto-summary-cell strong{display:block;margin-top:3px;font-family:var(--serif);font-size:18px}.pto-summary-cell span{display:block;margin-top:2px;color:var(--muted);font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
      .pto-evidence-badge{display:inline-flex;align-items:center;gap:4px;padding:3px 7px;border:1px solid var(--line);border-radius:999px;color:var(--muted);font-size:9px;background:var(--surface-2)}.pto-evidence-badge.high{color:var(--accent-strong);background:var(--accent-soft)}
      .pto-hidden-control{margin-top:11px;padding:9px 10px;border:1px dashed var(--line);border-radius:10px;color:var(--muted);font-size:10px;display:flex;align-items:center;justify-content:space-between;gap:8px}.pto-hidden-control button{font-size:10px}
      .pto-v14-audit{margin-top:14px;padding:15px;border:1px solid var(--line);border-radius:14px;background:var(--surface)}.pto-v14-audit-head{display:flex;align-items:flex-start;justify-content:space-between;gap:14px}.pto-v14-audit h4{margin:0;font-family:var(--serif);font-size:16px}.pto-v14-audit p{margin:3px 0 0;color:var(--muted);font-size:10px;line-height:1.5}.pto-v14-scores{display:flex;gap:8px;align-items:stretch}.pto-v14-score{min-width:92px;border:1px solid var(--line);border-radius:11px;padding:8px 10px}.pto-v14-score small{display:block;color:var(--muted);font-size:8px;text-transform:uppercase}.pto-v14-score strong{display:block;font-family:var(--serif);font-size:23px;margin-top:1px}.pto-v14-score span{display:block;font-size:9px;color:var(--muted)}.pto-v14-dims{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:6px;margin-top:11px}.pto-v14-dim{border:1px solid var(--line);border-radius:9px;padding:7px 8px}.pto-v14-dim span{display:block;color:var(--muted);font-size:8px}.pto-v14-dim strong{display:block;margin-top:2px;font-size:12px}
      .feed-health[data-health="degraded"] .pulse-dot,.feed-health[data-health="stale"] .pulse-dot{background:#c5974f;box-shadow:0 0 0 4px rgba(197,151,79,.12)}.feed-health[data-health="healthy"] .pulse-dot{background:var(--accent-strong)}
      .pto-source-open{white-space:nowrap}.pto-score-band{font-size:9px;color:var(--muted);font-weight:600}.match-score.high .pto-score-band{color:var(--accent-strong)}
      @media(max-width:900px){.pto-market-summary{grid-template-columns:1fr 1fr}.pto-v14-dims{grid-template-columns:1fr 1fr}.pto-v14-audit-head{display:block}.pto-v14-scores{margin-top:10px}}
    `;document.head.appendChild(style);
  }

  function canonicalText(value){return String(value||'').trim().replace(/\s+/g,' ').toLowerCase();}
  function inferredCity(job){
    const loc=String(job?.l??job?.location??'').trim();if(loc)return loc;
    const title=String(job?.r??job?.role??job?.position??'');
    return CITIES.find(c=>title.includes(c))||'';
  }
  function canonicalRole(job){
    let role=String(job?.r??job?.role??job?.position??'').trim();
    for(const city of CITIES)role=role.replace(new RegExp(`[\\s\\-—–·（）()]*${city}[\\s）)]*$`),'').trim();
    return canonicalText(role);
  }
  function opportunityKey(job){
    const company=canonicalText(job?.c??job?.company);
    const role=canonicalRole(job);
    const city=canonicalText(inferredCity(job));
    return company&&role?`${company}|${role}|${city}`:'';
  }
  function sourceQuality(job){
    const tier=Number(job?.q??job?.sourceTier??0);
    const apply=String(job?.u??job?.apply_url??job?.applyUrl??job?.url??'');
    const notice=String(job?.n??job?.notice_url??job?.noticeUrl??'');
    const source=canonicalText(job?.s??job?.source??job?.x??job?.sourceLabel);
    let q=tier*10+(apply?8:0)+(notice?2:0);
    if(/direct-official|官网|官方|moka|beisen|feishu|iguopin/.test(source))q+=6;
    return q;
  }
  function mergeBestJobs(priorityJobs,domesticJobs){
    const map=new Map(),orphans=[];
    for(const job of [...(Array.isArray(priorityJobs)?priorityJobs:[]),...(Array.isArray(domesticJobs)?domesticJobs:[])]){
      if(!job||typeof job!=='object')continue;
      const key=opportunityKey(job);
      if(!key){orphans.push(job);continue;}
      const current=map.get(key);
      if(!current||sourceQuality(job)>sourceQuality(current))map.set(key,job);
    }
    return [...map.values(),...orphans];
  }
  function mergeStatuses(priority,domestic){
    if(typeof ptoMergeSources==='function')return {...(domestic||{}),sources:ptoMergeSources(priority||{},domestic||{}),priority_generated_at:priority?.generated_at||null,priority_catalog_count:priority?.catalog_count||0};
    const rows=[],seen=new Set();
    for(const s of [...(priority?.sources||[]),...(domestic?.sources||[])]){const key=canonicalText(s?.name||s?.label||s?.url);if(!key||seen.has(key))continue;seen.add(key);rows.push(s);}
    return {...(domestic||{}),sources:rows,priority_generated_at:priority?.generated_at||null,priority_catalog_count:priority?.catalog_count||0};
  }
  function wait(ms){return new Promise(resolve=>setTimeout(resolve,ms));}
  async function fetchJson(url,{timeout=7000,retries=1}={}){
    let last;
    for(let attempt=0;attempt<=retries;attempt++){
      const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),timeout);
      try{
        const r=await nativeFetch(`${url}${String(url).includes('?')?'&':'?'}v=${Date.now()}`,{cache:'no-store',signal:controller.signal});
        if(!r.ok)throw new Error(`HTTP ${r.status}`);
        return {ok:true,value:await r.json(),url};
      }catch(err){last=err;if(attempt<retries)await wait(160*(attempt+1));}
      finally{clearTimeout(timer);}
    }
    return {ok:false,error:String(last?.name==='AbortError'?'timeout':last?.message||last||'unknown'),url};
  }

  loadFeeds=async function(){
    const started=performance.now();const previous=Array.isArray(marketJobs)?marketJobs.slice():[];
    RUNTIME.failures=[];RUNTIME.usedPrevious=false;RUNTIME.state='loading';
    const cfg=window.PTO_CONFIG||{};
    const [domestic,priority,status,priorityStatus]=await Promise.all([
      fetchJson(cfg.domesticJobsFeed||'./data/jobs_cn.json'),
      fetchJson(cfg.priorityJobsFeed||'./data/jobs_priority.json'),
      fetchJson(cfg.sourceStatusFeed||'./data/source_status.json',{timeout:5500,retries:0}),
      fetchJson(cfg.prioritySourceStatusFeed||'./data/priority_source_status.json',{timeout:5500,retries:0})
    ]);
    const jobSuccess=[];
    if(domestic.ok)jobSuccess.push({kind:'domestic',jobs:domestic.value?.jobs||[]});else RUNTIME.failures.push(`domestic:${domestic.error}`);
    if(priority.ok)jobSuccess.push({kind:'priority',jobs:priority.value?.jobs||[]});else RUNTIME.failures.push(`priority:${priority.error}`);
    if(!status.ok)RUNTIME.failures.push(`status:${status.error}`);
    if(!priorityStatus.ok)RUNTIME.failures.push(`priority-status:${priorityStatus.error}`);

    let rawJobs=[];
    if(jobSuccess.length){
      rawJobs=mergeBestJobs(priority.ok?priority.value?.jobs:[],domestic.ok?domestic.value?.jobs:[]);
    }else{
      // Last-resort compatibility feed. A total transient failure must never
      // erase a catalogue that the candidate was already browsing.
      const fallback=await fetchJson(cfg.jobsFeed||'./data/jobs.json',{timeout:5000,retries:0});
      if(fallback.ok){rawJobs=fallback.value?.jobs||[];RUNTIME.failures.push('using-global-fallback');}
      else RUNTIME.failures.push(`global:${fallback.error}`);
    }

    if(rawJobs.length){
      marketJobs=rawJobs.map(normalizeMarketJob);
      RUNTIME.lastSuccessAt=Date.now();
    }else if(previous.length){
      marketJobs=previous;RUNTIME.usedPrevious=true;
    }else marketJobs=[];

    if(status.ok||priorityStatus.ok)sourceStatus=mergeStatuses(priorityStatus.ok?priorityStatus.value:{sources:[]},status.ok?status.value:{sources:[]});
    if(!sourceStatus||typeof sourceStatus!=='object')sourceStatus={generated_at:null,sources:[]};
    RUNTIME.jobsLoaded=marketJobs.length;
    RUNTIME.loadMs=Math.round((performance.now()-started)*10)/10;
    RUNTIME.state=RUNTIME.failures.length?(marketJobs.length?'degraded':'failed'):'healthy';
    window.PTO_RANKING_V14?.clearCache?.();
    renderDiscovery();
    return marketJobs;
  };

  renderFeedHealth=function(){
    const el=$('#feedHealth');if(!el)return;
    const sources=sourceStatus?.sources||[];const ok=sources.filter(s=>s?.ok).length;
    const generated=sourceStatus?.priority_generated_at||sourceStatus?.generated_at||null;
    const when=generated?new Date(generated):null;
    const ageMs=when&&!Number.isNaN(when.getTime())?Date.now()-when.getTime():Infinity;
    const stale=ageMs>6*3600*1000;
    let health=RUNTIME.state==='failed'?'degraded':RUNTIME.failures.length?'degraded':stale?'stale':'healthy';
    const label=when&&!Number.isNaN(when.getTime())?when.toLocaleString('zh-CN',{month:'numeric',day:'numeric',hour:'2-digit',minute:'2-digit'}):'刷新时间未知';
    const stateText=health==='healthy'?'岗位源健康':health==='stale'?'岗位数据偏旧':'部分信源降级';
    el.dataset.health=health;
    el.innerHTML=`<span class="pulse-dot"></span><span><b>${stateText}</b> · ${marketJobs.length.toLocaleString()} 岗位 · ${ok}/${sources.length||0} 源正常 · ${esc(label)}${RUNTIME.loadMs?` · ${Math.round(RUNTIME.loadMs)} ms`:''}${RUNTIME.usedPrevious?' · 已保留上一版数据':''}</span>`;
    el.title=RUNTIME.failures.length?`本轮异常：${RUNTIME.failures.join('；')}`:'岗位池与来源状态均正常';
  };

  function scoreBand(score){return window.PTO_RANKING_V14?.bandFor?.(score)||((score||0)>=85?'高度匹配':(score||0)>=70?'可投':'低匹配');}
  function currentRows(){try{return visibleMarketJobs();}catch(_){return [];}}
  function ensureSummary(rows){
    const market=$('.job-market');if(!market)return;
    let el=$('#ptoMarketSummary');if(!el){el=document.createElement('div');el.id='ptoMarketSummary';el.className='pto-market-summary';const flow=$('#ptoFlow');(flow||market.firstElementChild)?.insertAdjacentElement(flow?'afterend':'beforebegin',el);if(!flow)market.prepend(el);}
    const scored=rows.filter(j=>Number.isFinite(Number(j.match?.score)));
    const over90=scored.filter(j=>Number(j.match.score)>=90).length;
    const over80=scored.filter(j=>Number(j.match.score)>=80).length;
    const official=(marketJobs||[]).filter(j=>Number(j.sourceTier||0)>=6||/官方|官网|direct-official/i.test(String(j.sourceLabel||j.source||''))).length;
    const officialPct=marketJobs.length?Math.round(official/marketJobs.length*100):0;
    const ranking=window.PTO_RANKING_V14;
    const ms=Number(ranking?.lastMs||0);
    el.innerHTML=`
      <div class="pto-summary-cell"><small>Strong Fit</small><strong>${over90.toLocaleString()}</strong><span>90+ · 强烈推荐</span></div>
      <div class="pto-summary-cell"><small>Priority Fit</small><strong>${over80.toLocaleString()}</strong><span>80+ · 建议优先查看</span></div>
      <div class="pto-summary-cell"><small>Search / Rank</small><strong>${ranking?.cacheHit?'cache':`${Math.round(ms)} ms`}</strong><span>${scored.length.toLocaleString()} 条已校准</span></div>
      <div class="pto-summary-cell"><small>Trusted Sources</small><strong>${officialPct}%</strong><span>官方/高可信岗位占比</span></div>`;
  }
  function ensureHiddenControl(){
    const rail=$('.match-rail');if(!rail)return;
    const count=Object.values(state.decisions||{}).filter(v=>v==='hidden').length;
    let el=$('#ptoHiddenControl');
    if(!count){el?.remove();return;}
    if(!el){el=document.createElement('div');el.id='ptoHiddenControl';el.className='pto-hidden-control';rail.appendChild(el);}
    el.innerHTML=`<span>已隐藏 <strong>${count}</strong> 个岗位</span><button class="text-btn" id="ptoRestoreHidden">恢复全部</button>`;
    $('#ptoRestoreHidden').onclick=()=>{for(const [id,v] of Object.entries(state.decisions||{}))if(v==='hidden')delete state.decisions[id];saveState(false);window.PTO_RANKING_V14?.clearCache?.();renderMarket();toast('已恢复隐藏岗位');};
  }
  function upgradeCards(){
    $$('[data-market-id]').forEach(card=>{
      const id=card.dataset.marketId;const job=(marketJobs||[]).find(j=>String(j.id)===String(id));if(!job)return;
      const scoreEl=card.querySelector('.match-score');
      const match=scoreEl?scoreJob(job,currentProfile()):null;
      if(scoreEl&&match?.score!=null){
        const small=scoreEl.querySelector('small');if(small){small.textContent=scoreBand(match.score);small.className='pto-score-band';}
        if(!scoreEl.parentElement?.querySelector('.pto-evidence-badge')&&Number.isFinite(Number(match.evidenceConfidence))){
          const badge=document.createElement('span');badge.className=`pto-evidence-badge ${match.evidenceConfidence>=80?'high':''}`;badge.textContent=`证据 ${match.evidenceConfidence}`;badge.title=`${match.evidenceLabel||'Evidence Confidence'}：来源可信度、岗位新鲜度、JD 完整度与岗位领域识别置信度`;scoreEl.insertAdjacentElement('afterend',badge);
        }
      }
      if(card.matches('.market-card')){
        const actions=card.querySelector('.pto-card-actions');
        if(actions&&!actions.querySelector('.pto-source-open')&&!job.applyUrl&&job.noticeUrl){
          actions.insertAdjacentHTML('beforeend',`<a class="btn tiny ghost pto-source-open" data-action="source" href="${esc(job.noticeUrl)}" target="_blank" rel="noopener noreferrer">打开招聘源 ↗</a>`);
        }
      }
    });
  }

  renderMarket=function(){
    const out=oldRenderMarket?oldRenderMarket.apply(this,arguments):undefined;
    const rows=currentRows();ensureSummary(rows);ensureHiddenControl();upgradeCards();renderFeedHealth();
    const threshold=$('#scoreThreshold'),label=$('#scoreThresholdLabel');
    if(threshold&&label)label.textContent=`${threshold.value} · ${Number(threshold.value)>=85?'高度匹配':Number(threshold.value)>=78?'优先岗位':Number(threshold.value)>=68?'可投以上':'宽松探索'}`;
    return out;
  };

  function renderV14Audit(job){
    const match=scoreJob(job,currentProfile());if(!match||match.score==null)return '';
    const c=match.components||{};const dims=[['职业方向',c.direction,30],['技能证据',c.skills,24],['届别/资历',c.career,13],['城市',c.location,10],['学历/届别资格',c.eligibility,8]];
    return `<section class="pto-v14-audit"><div class="pto-v14-audit-head"><div><h4>为什么这个岗位是 ${match.score} 分</h4><p>Match Score 只回答“你和岗位是否适合”；来源、时效与 JD 完整度单独进入 Evidence Confidence，不再把适合岗位压成四五十分。</p></div><div class="pto-v14-scores"><div class="pto-v14-score"><small>Match Score</small><strong>${match.score}</strong><span>${esc(match.band||scoreBand(match.score))}</span></div><div class="pto-v14-score"><small>Evidence</small><strong>${match.evidenceConfidence??'—'}</strong><span>${esc(match.evidenceLabel||'证据可信度')}</span></div></div></div><div class="pto-v14-dims">${dims.map(([n,v,max])=>`<div class="pto-v14-dim"><span>${n} / ${max}</span><strong>${Number(v||0).toFixed(1).replace(/\.0$/,'')}</strong></div>`).join('')}</div><p>适配核心 ${Number(c.fitCore||0).toFixed(1).replace(/\.0$/,'')} / 100${c.calibrationCap<99?` · 当前存在硬性约束，上限 ${c.calibrationCap}`:''}。清晰的领域冲突、资历冲突或学历/届别不满足仍会触发硬上限。</p></section>`;
  }
  openMarketJob=function(id){
    if(oldOpenMarketJob)oldOpenMarketJob(id);
    const job=(marketJobs||[]).find(j=>String(j.id)===String(id)),detail=$('#marketJobDetail');if(!job||!detail)return;
    detail.querySelectorAll('.pto-score-audit,.pto-v14-audit').forEach(x=>x.remove());
    const html=renderV14Audit(job);if(html)detail.insertAdjacentHTML('beforeend',html);
  };

  function setProductThreshold(force=false){
    const threshold=$('#scoreThreshold');if(!threshold)return;
    if(force||Number(threshold.value)<=35)threshold.value='70';
    const label=$('#scoreThresholdLabel');if(label)label.textContent=`${threshold.value} · 可投以上`;
  }
  if(oldHandleResumeFile){
    handleResumeFile=async function(file){const before=currentProfile()?.id||'';await oldHandleResumeFile(file);if(currentProfile()?.id!==before){setProductThreshold(true);window.PTO_RANKING_V14?.clearCache?.();renderMarket();}};
  }

  function bindFastSearch(){
    const search=$('#jobSearch');if(!search||search.dataset.v14Bound)return;search.dataset.v14Bound='1';
    search.addEventListener('input',e=>{
      e.stopImmediatePropagation();clearTimeout(searchTimer);searchTimer=setTimeout(()=>{window.PTO_RANKING_V14?.clearCache?.();renderMarket();},120);
    },true);
  }
  document.addEventListener('keydown',e=>{
    if(e.key==='/'&&!/input|textarea|select/i.test(document.activeElement?.tagName||'')){e.preventDefault();$('#jobSearch')?.focus();}
  });
  document.addEventListener('click',e=>{
    if(e.target.closest('#parsePastedResume'))setTimeout(()=>{setProductThreshold(true);window.PTO_RANKING_V14?.clearCache?.();renderMarket();},260);
  },true);

  ensureStyles();bindFastSearch();setProductThreshold(false);ensureHiddenControl();
  // Do not call the previous loader here. config.js invokes loadFeeds once all
  // enhancements are loaded, so the first real catalogue load already uses the
  // resilient v1.4 path rather than downloading the same feeds twice.
  window.PTO_PRODUCT_V14={mergeBestJobs,opportunityKey,sourceQuality,fetchJson};
})();