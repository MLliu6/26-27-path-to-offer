(function(){
  'use strict';
  if(typeof state==='undefined'||typeof normalizeMarketJob!=='function'||typeof renderDiscovery!=='function')return;

  const nativeFetch=(typeof PTO_NATIVE_FETCH==='function')?PTO_NATIVE_FETCH:window.fetch.bind(window);
  const runtime=window.PTO_FEED_RUNTIME||(window.PTO_FEED_RUNTIME={state:'booting',failures:[],loadMs:0,usedPrevious:false,jobsLoaded:0,lastSuccessAt:null});
  const baseRenderMarket=typeof renderMarket==='function'?renderMarket:null;
  const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));

  // v1.4 used one 7s AbortController for both response headers and JSON body.
  // That is fine for tiny status files but can abort the 60k compact catalogue
  // while the browser is still downloading/parsing it. v1.4.1 deliberately
  // separates time-to-first-response from body time and gives catalogues a
  // substantially larger body budget.
  async function fetchJson(url,{kind='catalog',retries=1}={}){
    const isCatalog=kind==='catalog';
    const headerTimeout=isCatalog?12000:6500;
    const bodyTimeout=isCatalog?45000:8000;
    let last=null;
    for(let attempt=0;attempt<=retries;attempt++){
      const controller=new AbortController();
      let headerTimer=null,bodyTimer=null;
      try{
        headerTimer=setTimeout(()=>controller.abort(),headerTimeout);
        const join=String(url).includes('?')?'&':'?';
        const response=await nativeFetch(`${url}${join}v=${Date.now()}`,{cache:'no-store',signal:controller.signal});
        clearTimeout(headerTimer);headerTimer=null;
        if(!response.ok)throw new Error(`HTTP ${response.status}`);
        bodyTimer=setTimeout(()=>controller.abort(),bodyTimeout);
        const value=await response.json();
        clearTimeout(bodyTimer);bodyTimer=null;
        return {ok:true,value,url,attempt:attempt+1,kind};
      }catch(err){
        last=err;
        if(attempt<retries)await wait(220*(attempt+1));
      }finally{
        if(headerTimer)clearTimeout(headerTimer);
        if(bodyTimer)clearTimeout(bodyTimer);
      }
    }
    const reason=last?.name==='AbortError'?'timeout':String(last?.message||last||'unknown');
    return {ok:false,error:reason,url,kind};
  }

  function rows(payload){return Array.isArray(payload?.jobs)?payload.jobs:[];}
  function numberOf(value){const n=Number(value);return Number.isFinite(n)&&n>0?n:0;}
  function advertisedCount(domesticStatus,priorityStatus){
    const candidates=[
      domesticStatus?.catalog_count,domesticStatus?.cn_catalog_count,domesticStatus?.total_count,
      priorityStatus?.catalog_count,priorityStatus?.priority_catalog_count
    ].map(numberOf);
    return Math.max(0,...candidates);
  }
  function mergeJobs(priorityRows,domesticRows){
    const fn=window.PTO_PRODUCT_V14?.mergeBestJobs;
    if(typeof fn==='function')return fn(priorityRows||[],domesticRows||[]);
    if(typeof ptoMergeJobs==='function')return ptoMergeJobs(priorityRows||[],domesticRows||[]);
    return [...(priorityRows||[]),...(domesticRows||[])];
  }
  function mergeStatus(priority,domestic){
    if(typeof ptoMergeSources==='function'){
      return {
        ...(domestic||{}),
        sources:ptoMergeSources(priority||{},domestic||{}),
        priority_generated_at:priority?.generated_at||null,
        priority_catalog_count:priority?.catalog_count||priority?.priority_catalog_count||0
      };
    }
    return domestic||priority||{generated_at:null,sources:[]};
  }

  function patchInconsistentEmpty(){
    if(!runtime.catalogInconsistent||marketJobs.length)return;
    const empty=document.querySelector('#jobMarketEmpty');if(!empty)return;
    const expected=Number(runtime.expectedCatalogCount||0);
    empty.classList.remove('hidden');
    empty.innerHTML=`<div class="empty-orbit">↻</div><h3>岗位目录本轮加载失败</h3><p>岗位源状态显示约 <strong>${expected.toLocaleString()}</strong> 条岗位，系统没有把网络超时误判成“岗位池为空”。可重新加载；若此前已有可用目录会自动保留上一版。</p><button class="btn primary" id="ptoV141Retry">重新加载岗位</button><button class="text-btn" id="ptoV141Sources">查看岗位源状态 →</button>`;
    document.querySelector('#ptoV141Retry')?.addEventListener('click',()=>loadFeeds(),{once:true});
    document.querySelector('#ptoV141Sources')?.addEventListener('click',()=>typeof showSources==='function'&&showSources(),{once:true});
  }

  loadFeeds=async function(){
    const started=performance.now();
    const previousJobs=Array.isArray(marketJobs)?marketJobs.slice():[];
    const previousStatus=sourceStatus&&typeof sourceStatus==='object'?sourceStatus:null;
    const cfg=window.PTO_CONFIG||{};
    runtime.failures=[];
    runtime.usedPrevious=false;
    runtime.catalogRecovered=false;
    runtime.fallbackUsed=false;
    runtime.catalogInconsistent=false;
    runtime.expectedCatalogCount=0;
    runtime.state='loading';

    const [domestic,priority,status,priorityStatus]=await Promise.all([
      fetchJson(cfg.domesticJobsFeed||'./data/jobs_cn.json',{kind:'catalog',retries:1}),
      fetchJson(cfg.priorityJobsFeed||'./data/jobs_priority.json',{kind:'catalog',retries:1}),
      fetchJson(cfg.sourceStatusFeed||'./data/source_status.json',{kind:'status',retries:0}),
      fetchJson(cfg.prioritySourceStatusFeed||'./data/priority_source_status.json',{kind:'status',retries:0})
    ]);

    if(!domestic.ok)runtime.failures.push(`domestic:${domestic.error}`);
    if(!priority.ok)runtime.failures.push(`priority:${priority.error}`);
    if(!status.ok)runtime.failures.push(`status:${status.error}`);
    if(!priorityStatus.ok)runtime.failures.push(`priority-status:${priorityStatus.error}`);

    const dStatus=status.ok?status.value:null;
    const pStatus=priorityStatus.ok?priorityStatus.value:null;
    runtime.expectedCatalogCount=advertisedCount(dStatus,pStatus);

    let rawJobs=mergeJobs(priority.ok?rows(priority.value):[],domestic.ok?rows(domestic.value):[]);
    const advertisedNonEmpty=runtime.expectedCatalogCount>0;
    const catalogResponsesEmpty=(domestic.ok||priority.ok)&&rawJobs.length===0;
    const catalogResponsesFailed=!domestic.ok&&!priority.ok;

    // A source-status payload declaring tens of thousands of jobs while both
    // catalogue payloads are empty/failed is a consistency error, not a valid
    // empty market. Recover through the compatibility/global feed before the UI
    // is allowed to show an empty-source state.
    if((catalogResponsesFailed||catalogResponsesEmpty)&&advertisedNonEmpty){
      runtime.catalogInconsistent=true;
      const fallbackUrl=cfg.globalJobsFeed||cfg.jobsFeed||'./data/jobs.json';
      const fallback=await fetchJson(fallbackUrl,{kind:'catalog',retries:1});
      if(fallback.ok&&rows(fallback.value).length){
        rawJobs=mergeJobs(priority.ok?rows(priority.value):[],rows(fallback.value));
        runtime.catalogRecovered=true;
        runtime.fallbackUsed=true;
        runtime.failures.push('catalog-recovered:global-fallback');
      }else{
        runtime.failures.push(`global:${fallback.ok?'empty':fallback.error}`);
      }
    }else if(catalogResponsesFailed){
      // Status itself may also be unavailable. Still try the global feed so a
      // first visit has one more recovery path instead of rendering an empty UI.
      const fallbackUrl=cfg.globalJobsFeed||cfg.jobsFeed||'./data/jobs.json';
      const fallback=await fetchJson(fallbackUrl,{kind:'catalog',retries:1});
      if(fallback.ok&&rows(fallback.value).length){
        rawJobs=rows(fallback.value);
        runtime.catalogRecovered=true;
        runtime.fallbackUsed=true;
        runtime.failures.push('catalog-recovered:global-fallback');
      }else runtime.failures.push(`global:${fallback.ok?'empty':fallback.error}`);
    }

    if(rawJobs.length){
      marketJobs=rawJobs.map(normalizeMarketJob);
      runtime.lastSuccessAt=Date.now();
      // Once recovery succeeds the catalogue is usable; keep degraded state so
      // the source-health UI still exposes that a fallback was necessary.
      runtime.catalogInconsistent=false;
    }else if(previousJobs.length){
      marketJobs=previousJobs;
      runtime.usedPrevious=true;
    }else{
      marketJobs=[];
    }

    if(status.ok||priorityStatus.ok){
      sourceStatus=mergeStatus(pStatus||{sources:[]},dStatus||{sources:[]});
    }else if(previousStatus){
      sourceStatus=previousStatus;
    }else{
      sourceStatus={generated_at:null,sources:[]};
    }

    runtime.jobsLoaded=marketJobs.length;
    runtime.loadMs=Math.round((performance.now()-started)*10)/10;
    runtime.state=marketJobs.length
      ?(runtime.failures.length||runtime.fallbackUsed||runtime.usedPrevious?'degraded':'healthy')
      :(runtime.catalogInconsistent?'failed':'failed');
    window.PTO_PRIORITY_FEED_READY=true;
    window.PTO_V141_FEED_READY=true;
    window.PTO_RANKING_V14?.clearCache?.();
    renderDiscovery();
    patchInconsistentEmpty();
    return marketJobs;
  };

  if(baseRenderMarket){
    renderMarket=function(){const out=baseRenderMarket.apply(this,arguments);patchInconsistentEmpty();return out;};
  }

  window.PTO_FEED_V141={
    version:'1.4.1',
    fetchJson,
    advertisedCount,
    headerTimeoutMs:{catalog:12000,status:6500},
    bodyTimeoutMs:{catalog:45000,status:8000}
  };
})();