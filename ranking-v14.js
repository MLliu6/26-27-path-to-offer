(function(){
  'use strict';
  if(!window.PTO_MATCHING||!window.PTO_CAREER_V13)return;
  const CORE=window.PTO_MATCHING;
  const TAX=window.PTO_CAREER_V13;
  const scoreV13=CORE.scoreJob;
  const scoreCache=new Map();
  const rankCache=new Map();
  const SEARCH_SCORE_LIMIT=1200;
  const MAX_RANK_CACHE=14;

  const clamp=(n,min=0,max=1)=>Math.max(min,Math.min(max,Number(n)||0));
  const round=n=>Math.round((Number(n)||0)*10)/10;
  const norm=v=>TAX.norm?TAX.norm(v):String(v||'').toLowerCase().replace(/\s+/g,' ').trim();

  function profileKey(profile){
    if(!profile)return 'none';
    const s=profile.signals||{};
    return String(profile.id||profile.name||[
      s.primaryCareerDomain||s.primaryDirection||'',s.degree||'',s.graduationYear||'',
      ...(s.skills||[]).slice(0,8)
    ].join('|'));
  }
  function preferenceKey(opts={}){
    return `${(opts.targetLocations||[]).join(',')}|${(opts.targetDirections||[]).join(',')}`;
  }
  function bandFor(score){
    const n=Number(score)||0;
    if(n>=92)return '强烈推荐';
    if(n>=85)return '高度匹配';
    if(n>=78)return '值得优先';
    if(n>=68)return '可投 · 有缺口';
    if(n>=55)return '谨慎评估';
    return '低匹配';
  }
  function confidenceBand(score){
    const n=Number(score)||0;
    if(n>=85)return '高可信';
    if(n>=68)return '中高可信';
    if(n>=48)return '中等可信';
    return '证据偏弱';
  }
  function explicitGraduationConflict(job,profile){
    const wanted=String(profile?.signals?.graduationYear||'').match(/20\d{2}/)?.[0];
    if(!wanted)return false;
    const blob=[job.graduation,job.batch,job.role].filter(Boolean).join(' ');
    const years=[...new Set(blob.match(/20\d{2}/g)||[])];
    return years.length>0&&!years.includes(wanted);
  }

  function calibrate(job,profile,legacy,opts={}){
    if(!profile||legacy?.score===null)return {score:null,reasons:legacy?.reasons||[],hits:legacy?.hits||[],components:legacy?.components||{},calibration:'no-profile'};
    const c=legacy?.components||{};
    const locationRequired=(opts.targetLocations||[]).filter(Boolean).length>0;
    const domain=clamp(Number(c.direction||0)/30);
    const skills=clamp(Number(c.skills||0)/24);
    const career=clamp(Number(c.career||0)/13);
    const eligibility=clamp(Number(c.eligibility||0)/8);
    const location=clamp(Number(c.location||0)/10);

    // Match means candidate-job fit, not source quality. Source/freshness/JD
    // completeness are reported separately as Evidence Confidence below.
    let fit;
    if(locationRequired){
      fit=domain*.42+Math.sqrt(skills)*.26+career*.14+eligibility*.08+location*.10;
    }else{
      fit=domain*.46+Math.sqrt(skills)*.28+career*.16+eligibility*.10;
    }
    fit=clamp(fit);
    let score=15+84*Math.pow(fit,.62);

    let cap=99;
    const legacyCap=Number(c.cap??99);
    const mismatch=!!c.domainMismatch;
    if(mismatch)cap=Math.min(cap,42);
    else if(legacyCap<=48)cap=Math.min(cap,48);
    else if(legacyCap<=62)cap=Math.min(cap,66);
    else if(legacyCap<=70)cap=Math.min(cap,70);
    if(locationRequired&&Number(c.location||0)<=0)cap=Math.min(cap,78);
    if((legacy?.reasons||[]).some(x=>/学历可能不满足/.test(String(x))))cap=Math.min(cap,62);
    if(explicitGraduationConflict(job,profile))cap=Math.min(cap,68);
    const skillHits=Number(c.skillHits||0);
    if(skillHits===0)cap=Math.min(cap,84);
    else if(skillHits===1)cap=Math.min(cap,89);
    if(!c.domainExact&&Number(c.direction||0)<12)cap=Math.min(cap,76);
    score=round(Math.max(0,Math.min(cap,score)));

    const source=clamp(Number(c.source||0)/7);
    const freshness=clamp(Number(c.freshness||0)/5);
    const completeness=clamp(Number(c.completeness||0)/3);
    const domainConfidence=clamp(Number(c.jobDomainConfidence||0)/100);
    const evidenceConfidence=Math.round(100*(source*.35+freshness*.25+completeness*.25+domainConfidence*.15));
    const band=bandFor(score);
    const confidenceLabel=confidenceBand(evidenceConfidence);
    const reasons=[...(legacy?.reasons||[])];

    return {
      ...legacy,
      score,
      band,
      evidenceConfidence,
      evidenceLabel:confidenceLabel,
      reasons:[...new Set(reasons)].slice(0,7),
      components:{
        ...c,
        legacyRaw:round(c.raw??legacy?.score),
        fitCore:round(fit*100),
        evidenceConfidence,
        calibrationCap:cap,
      },
      calibration:'v14-fit-confidence-separated'
    };
  }

  function jobEvidenceKey(job){
    // Employer APIs frequently reuse a position id while changing the JD,
    // source tier or update time. Cache the expensive score, but never let a
    // refresh keep stale explanation/confidence for the same id.
    return [
      job?.id||`${job?.company||''}|${job?.role||''}`,
      job?.role||'',job?.location||'',job?.sourceTier||0,
      job?.updatedAt||job?.updated_at||'',String(job?.jd||'').length
    ].join('~');
  }
  function scoreJobV14(job,profile,opts={}){
    if(!profile)return {score:null,reasons:[],hits:[],components:{},calibration:'no-profile'};
    const age=Number.isFinite(Number(opts.ageDays))?Math.floor(Number(opts.ageDays)):999;
    const key=`${profileKey(profile)}|${jobEvidenceKey(job)}|${preferenceKey(opts)}|${age}`;
    if(scoreCache.has(key))return scoreCache.get(key);
    const legacy=scoreV13(job,profile,opts);
    const result=calibrate(job,profile,legacy,opts);
    if(scoreCache.size>16000)scoreCache.clear();
    scoreCache.set(key,result);
    return result;
  }

  function ageOf(job,options){return options.ageOf?options.ageOf(job.updatedAt||job.updated_at):999;}
  function metadataPass(job,options){
    const location=options.location||'all',companyType=options.companyType||'all',batch=options.batch||'all';
    return (location==='all'||String(job.location||'').includes(location))&&
      (companyType==='all'||job.companyType===companyType||job.company_type===companyType)&&
      (batch==='all'||job.batch===batch);
  }
  function freshnessQuick(age){const n=Number(age);if(!Number.isFinite(n)||n>=999)return 0;if(n<=14)return 5;if(n<=30)return 4;if(n<=60)return 2.5;if(n<=120)return 1;return 0;}
  function preRank(job,profile,options){
    const affinity=TAX.cheapAffinity?TAX.cheapAffinity(job,profile):0;
    const source=Math.min(7,Math.max(1,Number(job.sourceTier||1)));
    return affinity*10+source*1.5+freshnessQuick(ageOf(job,options));
  }
  function searchIndex(job){
    if(job._ptoSearchV14)return job._ptoSearchV14;
    const fields={
      company:norm(job.company),role:norm(job.role),location:norm(job.location),department:norm(job.department),
      industry:norm(job.industry),jd:norm(job.jd),batch:norm(job.batch),graduation:norm(job.graduation)
    };
    const blob=Object.values(fields).join(' ');
    try{Object.defineProperty(job,'_ptoSearchV14',{value:{fields,blob},writable:true,configurable:true});}
    catch(_){job._ptoSearchV14={fields,blob};}
    return job._ptoSearchV14;
  }
  function searchRankFast(job,query){
    const q=norm(query);if(!q)return {matched:true,boost:0};
    const idx=searchIndex(job);
    const tokens=q.split(/\s+/).filter(Boolean);
    if(!tokens.every(t=>idx.blob.includes(t)))return {matched:false,boost:0};
    let boost=0;
    if(idx.fields.role===q)boost+=260;else if(idx.fields.role.includes(q))boost+=150;
    if(idx.fields.company===q)boost+=240;else if(idx.fields.company.includes(q))boost+=135;
    if(idx.fields.location.includes(q))boost+=55;
    if(idx.fields.department.includes(q))boost+=38;
    if(idx.fields.industry.includes(q))boost+=24;
    for(const token of tokens){
      if(idx.fields.role.includes(token))boost+=28;
      if(idx.fields.company.includes(token))boost+=24;
      if(idx.fields.location.includes(token))boost+=8;
      if(idx.fields.jd.includes(token))boost+=3;
    }
    return {matched:true,boost};
  }
  function catalogueKey(jobs){
    const a=jobs?.[0],b=jobs?.[jobs.length-1];
    return `${jobs?.length||0}:${a?.id||a?.company||''}:${b?.id||b?.company||''}`;
  }
  function optionsKey(jobs,options){
    return [catalogueKey(jobs),options.query||'',options.location||'all',options.companyType||'all',options.batch||'all',
      options.threshold??'',options.freshOnly?'1':'0',options.sort||'match',profileKey(options.profile),
      preferenceKey(options.preferences||{})].join('::');
  }
  function putRankCache(key,value){
    if(rankCache.has(key))rankCache.delete(key);
    rankCache.set(key,value);
    while(rankCache.size>MAX_RANK_CACHE)rankCache.delete(rankCache.keys().next().value);
  }

  function filterAndRankV14(jobs,options={}){
    const started=typeof performance!=='undefined'?performance.now():Date.now();
    const key=optionsKey(jobs,options);
    if(rankCache.has(key)){
      const cached=rankCache.get(key);rankCache.delete(key);rankCache.set(key,cached);
      window.PTO_RANKING_V14.lastMs=0;window.PTO_RANKING_V14.cacheHit=true;
      return cached;
    }
    const q=String(options.query||'').trim();
    const profile=options.profile||null;
    let base=(jobs||[]).filter(job=>metadataPass(job,options));
    let rows;

    if(q){
      const matched=[];
      for(const job of base){const s=searchRankFast(job,q);if(s.matched)matched.push({job,s});}
      matched.sort((a,b)=>b.s.boost-a.s.boost||String(b.job.updatedAt||'').localeCompare(String(a.job.updatedAt||'')));
      rows=matched.map((row,index)=>{
        const age=ageOf(row.job,options);
        const match=profile&&index<SEARCH_SCORE_LIMIT
          ?scoreJobV14(row.job,profile,{...(options.preferences||{}),ageDays:age,targetLocations:options.preferences?.targetLocations||[],targetDirections:options.preferences?.targetDirections||[]})
          :{score:null,reasons:[],hits:[],components:{},calibration:profile?'v14-search-lazy':'no-profile'};
        return {...row.job,_age:age,_search:row.s,match};
      });
      rows.sort((a,b)=>(b._search?.boost||0)-(a._search?.boost||0)||(b.match.score??-1)-(a.match.score??-1)||String(b.updatedAt||'').localeCompare(String(a.updatedAt||'')));
    }else if(!profile){
      if(options.freshOnly&&base.some(j=>ageOf(j,options)<999))base=base.filter(j=>ageOf(j,options)<=30||ageOf(j,options)===999);
      if(options.sort==='company')base.sort((a,b)=>String(a.company||'').localeCompare(String(b.company||''),'zh-CN'));
      else base.sort((a,b)=>String(b.updatedAt||'').localeCompare(String(a.updatedAt||'')));
      rows=base.map(job=>({...job,_age:ageOf(job,options),match:{score:null,reasons:[],hits:[],components:{},calibration:'no-profile'}}));
    }else{
      const FULL_LIMIT=Math.max(2500,Math.min(8000,Number(window.PTO_CONFIG?.fullScoreLimit||5600)));
      rows=base.map(job=>({job,pre:preRank(job,profile,options),age:ageOf(job,options)}))
        .sort((a,b)=>b.pre-a.pre||String(b.job.updatedAt||'').localeCompare(String(a.job.updatedAt||'')))
        .slice(0,FULL_LIMIT)
        .map(row=>({...row.job,_age:row.age,match:scoreJobV14(row.job,profile,{...(options.preferences||{}),ageDays:row.age,targetLocations:options.preferences?.targetLocations||[],targetDirections:options.preferences?.targetDirections||[]})}));
      const threshold=Number(options.threshold??70);
      rows=rows.filter(job=>(job.match.score??0)>=threshold);
      if(options.freshOnly&&rows.some(j=>Number.isFinite(j._age)&&j._age<999))rows=rows.filter(j=>j._age<=30||j._age===999);
      if(options.sort==='fresh')rows.sort((a,b)=>String(b.updatedAt||'').localeCompare(String(a.updatedAt||''))||(b.match.score??0)-(a.match.score??0));
      else if(options.sort==='company')rows.sort((a,b)=>String(a.company||'').localeCompare(String(b.company||''),'zh-CN')||(b.match.score??0)-(a.match.score??0));
      else rows.sort((a,b)=>(b.match.score??-1)-(a.match.score??-1)||(b.match.components?.fitCore??0)-(a.match.components?.fitCore??0));
    }

    const ended=typeof performance!=='undefined'?performance.now():Date.now();
    window.PTO_RANKING_V14.lastMs=Math.round((ended-started)*10)/10;
    window.PTO_RANKING_V14.cacheHit=false;
    putRankCache(key,rows);
    return rows;
  }

  window.PTO_RANKING_V14={
    lastMs:0,cacheHit:false,bandFor,confidenceBand,clearCache(){scoreCache.clear();rankCache.clear();}
  };
  CORE.scoreJob=scoreJobV14;
  CORE.filterAndRank=filterAndRankV14;
  CORE.version='14.0.0';
  window.PTO_MATCHING_V14={scoreJob:scoreJobV14,filterAndRank:filterAndRankV14};
})();