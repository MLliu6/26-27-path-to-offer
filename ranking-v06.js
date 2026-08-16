(function(){
  'use strict';
  if(!window.PTO_MATCHING)return;
  const CORE=window.PTO_MATCHING;
  const baseScore=CORE.scoreJob;
  const baseSearch=CORE.searchMatch;
  const DAY=new Date().toISOString().slice(0,10);

  const EARLY=[
    /(?:校招|校园招聘|应届|毕业生|管培|管培生|实习|实习生|初级|助理|培训生|新卒)/i,
    /\b(?:intern(?:ship)?|new\s*grad|graduate|campus|entry[ -]?level|junior|early\s*career|apprentice)\b/i,
    /(?:2026|2027|2028)\s*(?:届|graduate|毕业)/i,
  ];
  const SENIOR=[
    /(?:资深|高级专家|首席|总监|负责人|架构师|技术专家|研究专家)/i,
    /\b(?:senior|staff|principal|lead|director|head of|architect|distinguished)\b/i,
    /(?:[5-9]|1\d)\s*(?:年|years?)\s*(?:以上|\+|of experience)?/i,
  ];

  function careerSignal(job){
    const role=String(job.role||'');
    const text=[job.role,job.jd,job.description,job.batch,job.graduation].join(' ');
    if(EARLY.some(r=>r.test(text)))return {level:'early',delta:10,label:'校招 / 初阶'};
    // Senior words in the title are much more reliable than boilerplate in JD.
    if(SENIOR.slice(0,2).some(r=>r.test(role))||SENIOR[2].test(text))return {level:'senior',delta:-35,label:'资历要求偏高'};
    return {level:'unknown',delta:0,label:''};
  }
  function graduateProfile(profile){
    const s=profile?.signals||profile||{};const year=Number(s.graduationYear||s.years?.at?.(-1)||0);const now=new Date().getFullYear();
    return year>=now-1&&year<=now+3;
  }
  function scoreJobV6(job,profile,opts={}){
    const base=baseScore(job,profile,opts);if(base.score===null)return {...base,career:careerSignal(job)};
    const career=careerSignal(job);const score=Math.max(0,Math.min(99,Math.round(base.score+career.delta)));
    const reasons=[...(base.reasons||[])];
    if(career.level==='early')reasons.unshift(career.label);
    else if(career.level==='senior')reasons.push(career.label);
    return {...base,score,reasons:[...new Set(reasons)].slice(0,5),career,components:{...(base.components||{}),career:career.delta}};
  }

  function cacheKey(profile,preferences,age){
    const s=profile?.signals||{};
    return [DAY,profile?.id||profile?.name||'',profile?.profileVersion||'',s.primaryDirection||'',(preferences.targetDirections||[]).join('|'),(preferences.targetLocations||[]).join('|'),age].join('::');
  }
  function cachedScore(job,profile,preferences,age){
    const key=cacheKey(profile,preferences,age);job.__ptoScoreCache=job.__ptoScoreCache||new Map();
    if(job.__ptoScoreCache.has(key))return job.__ptoScoreCache.get(key);
    const value=scoreJobV6(job,profile,{targetLocations:preferences.targetLocations||[],targetDirections:preferences.targetDirections||[],ageDays:age});
    if(job.__ptoScoreCache.size>4)job.__ptoScoreCache.clear();job.__ptoScoreCache.set(key,value);return value;
  }

  function filterAndRankV6(jobs,options={}){
    const {query='',profile=null,threshold=25,freshOnly=false,ageOf=()=>999,location='all',companyType='all',batch='all',sort='match',preferences={}}=options;
    const hasQuery=!!CORE.cleanText(query);let candidates=jobs||[];
    candidates=candidates.filter(j=>(location==='all'||String(j.location||'').includes(location))&&(companyType==='all'||j.companyType===companyType||j.company_type===companyType)&&(batch==='all'||j.batch===batch));

    // Explicit queries are retrieval, not recommendation. Filter text/company
    // aliases *before* any expensive resume scoring. On a 60k catalogue this is
    // both logically correct and materially faster.
    if(hasQuery){
      let rows=candidates.map(job=>({...job,_search:baseSearch(job,query)})).filter(j=>j._search.matched);
      rows=rows.map(j=>{const age=ageOf(j.updatedAt||j.updated_at);return {...j,_age:age,match:cachedScore(j,profile,preferences,age)};});
      rows.sort((a,b)=>b._search.boost-a._search.boost||((b.match.score??-1)-(a.match.score??-1))||String(b.updatedAt||'').localeCompare(String(a.updatedAt||'')));
      return rows;
    }

    let rows=candidates.map(job=>{const age=ageOf(job.updatedAt||job.updated_at);return {...job,_age:age,match:cachedScore(job,profile,preferences,age)};});
    if(profile){
      // Graduate profiles should not be flooded by Staff/Principal/资深 roles
      // just because the technical vocabulary matches. Explicit search can
      // still retrieve those roles because that is a different user intent.
      if(graduateProfile(profile))rows=rows.filter(j=>j.match.career?.level!=='senior');
      rows=rows.filter(j=>(j.match.score??0)>=threshold);
    }
    if(freshOnly&&rows.some(j=>Number.isFinite(j._age)&&j._age<999))rows=rows.filter(j=>j._age<=30||j._age===999);
    if(sort==='match')rows.sort((a,b)=>(b.match.score??-1)-(a.match.score??-1)||String(b.updatedAt||'').localeCompare(String(a.updatedAt||'')));
    else if(sort==='fresh')rows.sort((a,b)=>String(b.updatedAt||'').localeCompare(String(a.updatedAt||'')));
    else if(sort==='company')rows.sort((a,b)=>String(a.company||'').localeCompare(String(b.company||''),'zh-CN'));
    return rows;
  }

  CORE.scoreJob=scoreJobV6;
  CORE.filterAndRank=filterAndRankV6;
  CORE.careerSignal=careerSignal;
  CORE.version='6.0.0';
})();
