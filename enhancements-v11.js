(function(){
  'use strict';
  if(typeof normalizeMarketJob!=='function'||typeof renderDiscovery!=='function')return;

  const nativeFetch=window.PTO_NATIVE_FETCH||window.fetch.bind(window);
  const previousNormalize=normalizeMarketJob;
  normalizeMarketJob=function(row){
    const job=previousNormalize(row);
    if(job&&row&&row.s)job.source=row.s;
    if(job&&row&&row.z)job.positionId=row.z;
    return job;
  };

  function parseTime(value){
    const n=Date.parse(value||'');return Number.isFinite(n)?n:0;
  }
  async function fetchJson(url){
    if(!url)return null;
    const join=url.includes('?')?'&':'?';
    const r=await nativeFetch(`${url}${join}v=${Date.now()}`,{cache:'no-store'});
    if(!r.ok)throw new Error(`${url}: HTTP ${r.status}`);
    return r.json();
  }
  function positionId(job){
    if(job?.positionId)return String(job.positionId).toLowerCase();
    const url=job?.applyUrl||job?.noticeUrl||'';
    try{return new URL(url,location.href).searchParams.get('positionId')?.toLowerCase()||'';}catch(_){return '';}
  }
  function canonical(job){
    const pid=positionId(job);if(pid)return `position:${pid}`;
    const url=String(job.applyUrl||job.noticeUrl||'').trim().replace(/\/$/,'').toLowerCase();
    if(url)return `url:${url}`;
    return [job.company,job.role,job.location].map(x=>String(x||'').trim().toLowerCase()).join('|');
  }
  function mergeJobs(priorityRows,domesticRows){
    const out=[];const seen=new Set();
    for(const raw of [...priorityRows,...domesticRows]){
      const job=normalizeMarketJob(raw);const key=canonical(job);
      if(!job.company||!job.role||!key||seen.has(key))continue;
      seen.add(key);out.push(job);
    }
    return out;
  }
  function mergeStatus(priority,domestic){
    const rows=[];const names=new Set();
    for(const s of [...(priority?.sources||[]),...(domestic?.sources||[])]){
      if(!s||typeof s!=='object')continue;
      const name=String(s.name||s.label||'');
      if(name&&names.has(name))continue;
      if(name)names.add(name);rows.push(s);
    }
    const generated=parseTime(priority?.generated_at)>=parseTime(domestic?.generated_at)?priority?.generated_at:domestic?.generated_at;
    return {...(domestic||{}),generated_at:generated||null,sources:rows,priority_catalog_count:priority?.catalog_count||0,priority_interval_minutes:priority?.nominal_interval_minutes||10,exact_pdd_position_ok:priority?.exact_pdd_position_ok};
  }

  loadFeeds=async function(){
    const priorityUrl=window.PTO_CONFIG?.priorityJobsFeed||'./data/jobs_priority.json';
    const domesticUrl=window.PTO_CONFIG?.domesticJobsFeed||'./data/jobs_cn.json';
    const globalUrl=window.PTO_CONFIG?.globalJobsFeed||'./data/jobs.json';
    const priorityStatusUrl=window.PTO_CONFIG?.prioritySourceStatusFeed||'./data/priority_source_status.json';
    const domesticStatusUrl=window.PTO_CONFIG?.sourceStatusFeed||'./data/source_status.json';
    let priority={jobs:[]},domestic={jobs:[]},pStatus=null,dStatus=null;
    const results=await Promise.allSettled([
      fetchJson(priorityUrl),fetchJson(domesticUrl),fetchJson(priorityStatusUrl),fetchJson(domesticStatusUrl)
    ]);
    if(results[0].status==='fulfilled'&&results[0].value)priority=results[0].value;
    if(results[1].status==='fulfilled'&&results[1].value)domestic=results[1].value;
    else{
      try{domestic=await fetchJson(globalUrl)||{jobs:[]};}catch(err){console.warn('Path to Offer catalogue unavailable',err);}
    }
    if(results[2].status==='fulfilled')pStatus=results[2].value;
    if(results[3].status==='fulfilled')dStatus=results[3].value;
    marketJobs=mergeJobs(Array.isArray(priority.jobs)?priority.jobs:[],Array.isArray(domestic.jobs)?domestic.jobs:[]);
    sourceStatus=mergeStatus(pStatus,dStatus);
    window.PTO_PRIORITY_FEED_READY=true;
    renderDiscovery();
  };

  function sourceRows(){
    const sources=sourceStatus?.sources||[];
    return sources.length?sources.map(s=>{
      const preserved=s.preserved_previous?' · 保留上次有效数据':'';
      const state=s.ok?`${Number(s.count||0).toLocaleString()} 条${preserved}`:`异常 · ${esc(s.error||'unknown')}`;
      return `<div class="source-status-row"><div><strong>${esc(s.label||s.name||'招聘源')}</strong><small>${esc(s.url||'')}</small></div><span class="source-health ${s.ok?'ok':'bad'}">${state}</span></div>`;
    }).join(''):'<div class="empty-state"><strong>尚无刷新记录</strong><p>定时任务完成后会显示官网源数量与错误。</p></div>';
  }
  showSources=function(){
    openModal('岗位源与刷新状态',`<div class="source-modal"><p><strong>重点企业官网：</strong>名义上每 10 分钟检查一次，优先发布拼多多、美团、腾讯等已验证的企业公开接口；<strong>全国深度联邦：</strong>每 2 小时刷新一次。外部站点临时失败时保留上一版有效数据，不用空结果覆盖。</p>${sourceRows()}<div class="source-foot"><span>只访问公开、无需登录的招聘页面或接口；不会绕过验证码、登录墙或访问控制。</span></div></div>`);
  };
  const sourceButton=document.querySelector('#openSourcePanel');if(sourceButton)sourceButton.onclick=showSources;

  function patchCopy(){
    const fallback=document.querySelector('#ptoSourceFallback');
    if(fallback)fallback.innerHTML=fallback.innerHTML.replace(/两小时刷新/g,'10 分钟重点官网刷新').replace(/每 2 小时刷新/g,'每 10 分钟刷新重点官网');
    let chip=document.querySelector('#priorityFeedChip');
    const head=document.querySelector('.market-head h2');
    if(head&&!chip){chip=document.createElement('span');chip.id='priorityFeedChip';chip.className='coverage-chip';head.appendChild(chip);}
    if(chip)chip.textContent=`官网快线 ${Number(sourceStatus?.priority_catalog_count||0).toLocaleString()} 条 · 10 min`;
  }
  const previousRender=renderMarket;
  renderMarket=function(){const out=previousRender.apply(this,arguments);patchCopy();return out;};
  patchCopy();
})();
