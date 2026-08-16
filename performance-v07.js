(function(){
  'use strict';
  if(typeof visibleMarketJobs!=='function'||typeof marketJobs==='undefined')return;
  const rankedVisible=visibleMarketJobs;
  const TIER1=['北京','上海','深圳','广州','杭州'];

  // Before a resume exists there is no reason to run semantic scoring or sort
  // thousands of rows through role-profile comparators. The China-first crawler
  // already publishes early-career / Beijing / tier-one rows in priority order.
  // Preserve that order and perform only linear filters. Explicit queries still
  // use experience-v07's precomputed index.
  visibleMarketJobs=function(){
    const query=(document.querySelector('#jobSearch')?.value||'').trim();
    const profile=currentProfile();
    if(query||profile)return rankedVisible();
    const loc=document.querySelector('#jobLocationFilter')?.value||'all';
    const typ=document.querySelector('#jobTypeFilter')?.value||'all';
    const batch=document.querySelector('#jobBatchFilter')?.value||'all';
    const mode=state.preferences?.geoMode||'tier1';
    const hidden=state.decisions||{};
    const rows=[];
    for(const job of marketJobs){
      if(hidden[job.id]==='hidden'||job.__v7?.geo?.foreign)continue;
      const place=String(job.location||'');
      if(mode==='beijing'&&!place.includes('北京'))continue;
      if(mode==='tier1'&&!TIER1.some(c=>place.includes(c)))continue;
      if(loc!=='all'&&!place.includes(loc))continue;
      if(typ!=='all'&&job.companyType!==typ)continue;
      if(batch!=='all'&&job.batch!==batch)continue;
      rows.push({...job,match:{score:null,reasons:[],hits:[]}});
    }
    return rows;
  };
})();
