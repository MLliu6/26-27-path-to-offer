(function(){
  'use strict';
  if(!window.PTO_MATCHING)return;
  const CORE=window.PTO_MATCHING;
  const baseScore=CORE.scoreJob;
  const baseSearch=CORE.searchMatch;

  const CN_CITIES=['北京','上海','深圳','广州','杭州','南京','苏州','成都','武汉','西安','天津','重庆','长沙','合肥','无锡','厦门','青岛','济南','宁波','东莞','珠海','佛山','大连','沈阳','郑州','福州'];
  const FIRST_TIER=new Set(['北京','上海','深圳','广州','杭州']);
  const OVERSEAS=/(海外|美国|加拿大|英国|德国|法国|欧洲|新加坡|日本|韩国|澳大利亚|印度|poland|germany|france|london|new york|san francisco|singapore|tokyo|india|united states|canada)/i;
  const CAMPUS=/(校招|校园招聘|应届|毕业生|实习|实习生|new\s*grad|graduate|campus|intern)/i;
  const TECH=/(ai|llm|vlm|vla|大模型|多模态|推理|serving|cuda|gpu|kernel|算子|量化|ptq|编译器|compiler|runtime|npu|芯片|hpc|高性能|分布式|后端|算法|机器学习|深度学习|计算机视觉|嵌入式|机器人)/i;
  const MAX_FULL_SCORE=4200;

  function text(v){return String(v||'').toLowerCase();}
  function locationText(job){return String(job.location||'');}
  function isDomestic(job){
    if(job.__ptoDomestic!==undefined)return job.__ptoDomestic;
    const loc=locationText(job);
    const source=String(job.sourceLabel||job.source||'');
    const domestic=source.includes('中国企业官方招聘') || /招聘官网|官方招聘|direct-official/i.test(source) || CN_CITIES.some(c=>loc.includes(c)) || /(中国|china|cn\b)/i.test(loc);
    job.__ptoDomestic=!!domestic&&!OVERSEAS.test(loc);
    return job.__ptoDomestic;
  }
  function cityOf(job){return CN_CITIES.find(c=>locationText(job).includes(c))||'';}
  function sourceSignal(job){
    const s=String(job.sourceLabel||job.source||'');
    if(/招聘官网|direct-official/i.test(s))return {delta:18,label:'企业招聘官网'};
    if(s.includes('中国企业官方招聘'))return {delta:12,label:'企业官方招聘'};
    if(/官方|campus/i.test(s))return {delta:6,label:'官方来源'};
    return {delta:0,label:''};
  }
  function locationSignal(job,preferences={}){
    const loc=locationText(job); const targets=preferences.targetLocations||[];
    if(OVERSEAS.test(loc))return {delta:-45,label:'海外岗位'};
    if(targets.length&&targets.some(c=>loc.includes(c)))return {delta:16,label:'目标城市'};
    const city=cityOf(job);
    if(city==='北京')return {delta:12,label:'北京'};
    if(FIRST_TIER.has(city))return {delta:6,label:'一线 / 新一线'};
    return {delta:0,label:''};
  }
  function roleSignal(job,profile){
    if(!profile)return {delta:0,label:''};
    const role=text(job.role); const jd=text(job.jd);
    const s=profile.signals||{};
    const terms=[...(s.recommendedRoles||[]),...(s.skills||[]).slice(0,24)].map(x=>text(x).trim()).filter(x=>x.length>=3);
    let titleHits=0,bodyHits=0;
    for(const t of terms){if(role.includes(t))titleHits++;else if(jd.includes(t))bodyHits++;}
    if(titleHits)return {delta:Math.min(16,8+titleHits*3),label:'岗位标题高度相关'};
    if(bodyHits>=2)return {delta:Math.min(8,bodyHits*2),label:'JD 技能相关'};
    return {delta:0,label:''};
  }
  function scoreJobV7(job,profile,opts={}){
    const base=baseScore(job,profile,opts);
    if(base.score===null)return base;
    const src=sourceSignal(job),loc=locationSignal(job,opts),role=roleSignal(job,profile);
    const campus=CAMPUS.test([job.role,job.batch,job.graduation,job.jd].join(' '))?6:0;
    const domestic=isDomestic(job)?4:-28;
    const score=Math.max(0,Math.min(99,Math.round(base.score+src.delta+loc.delta+role.delta+campus+domestic)));
    const reasons=[...(base.reasons||[])];
    for(const x of [src.label,loc.label,role.label,campus?'校招 / 实习':''])if(x)reasons.unshift(x);
    return {...base,score,reasons:[...new Set(reasons)].slice(0,6),components:{...(base.components||{}),domestic,official:src.delta,location:loc.delta,titleFit:role.delta,campus}};
  }

  function fastBlob(job){
    if(job.__ptoFastBlob)return job.__ptoFastBlob;
    job.__ptoFastBlob=text([job.company,job.role,job.location,job.department,job.batch,job.graduation,job.jd].join(' '));
    return job.__ptoFastBlob;
  }
  function literalSearch(job,nq){
    const company=text(job.company),role=text(job.role),blob=fastBlob(job);
    if(company===nq||company.startsWith(nq))return {matched:true,exact:true,boost:100};
    if(company.includes(nq))return {matched:true,exact:false,boost:70};
    if(role.includes(nq))return {matched:true,exact:false,boost:50};
    if(blob.includes(nq))return {matched:true,exact:false,boost:20};
    return null;
  }
  function cheapFit(job,profile,preferences={}){
    const s=profile?.signals||{}; const title=text(job.role); const blob=fastBlob(job);
    let score=0;
    if(isDomestic(job))score+=30; else score-=60;
    const city=cityOf(job); if(city==='北京')score+=20; else if(FIRST_TIER.has(city))score+=10;
    if((preferences.targetLocations||[]).some(c=>locationText(job).includes(c)))score+=28;
    if(/招聘官网|direct-official/i.test(String(job.sourceLabel||job.source||'')))score+=28;
    else if(String(job.sourceLabel||'').includes('中国企业官方招聘'))score+=18;
    if(CAMPUS.test(blob))score+=12;
    if(profile){
      const roles=(s.recommendedRoles||[]).map(text).filter(Boolean);
      const skills=(s.skills||[]).map(text).filter(x=>x.length>=3).slice(0,30);
      for(const r of roles){if(title.includes(r))score+=22;else if(blob.includes(r))score+=7;}
      for(const k of skills){if(title.includes(k))score+=7;else if(blob.includes(k))score+=2;}
      if(TECH.test(title))score+=5;
    }
    return score;
  }

  function filterAndRankV7(jobs,options={}){
    const {query='',profile=null,threshold=25,freshOnly=false,ageOf=()=>999,location='all',companyType='all',batch='all',sort='match',preferences={}}=options;
    const q=String(query||'').trim();
    let candidates=(jobs||[]).filter(j=>state?.decisions?.[j.id]!=='hidden');
    candidates=candidates.filter(j=>(location==='all'||locationText(j).includes(location))&&(companyType==='all'||j.companyType===companyType||j.company_type===companyType)&&(batch==='all'||j.batch===batch));

    if(q){
      const nq=text(q); let rows=[];
      for(const job of candidates){
        // Most user searches are literal company/title terms (e.g. 美团/京东/CUDA).
        // Handle those from a cached lowercase blob and only invoke the more
        // expensive alias/token matcher for literal misses. This avoids doing
        // normalization + alias expansion across every row on every keystroke.
        const fast=literalSearch(job,nq);
        const sm=fast||baseSearch(job,q);
        if(!sm.matched)continue;
        const age=ageOf(job.updatedAt||job.updated_at);
        rows.push({...job,_age:age,_search:sm,match:scoreJobV7(job,profile,{...preferences,ageDays:age,targetLocations:preferences.targetLocations||[],targetDirections:preferences.targetDirections||[]})});
      }
      rows.sort((a,b)=>b._search.boost-a._search.boost||(b.match.score??-1)-(a.match.score??-1)||cheapFit(b,profile,preferences)-cheapFit(a,profile,preferences));
      return rows;
    }

    candidates=candidates.filter(isDomestic);
    if(profile&&candidates.length>MAX_FULL_SCORE){
      candidates=candidates.map(j=>({j,q:cheapFit(j,profile,preferences)})).sort((a,b)=>b.q-a.q).slice(0,MAX_FULL_SCORE).map(x=>x.j);
    }
    let rows=candidates.map(job=>{const age=ageOf(job.updatedAt||job.updated_at);return {...job,_age:age,match:scoreJobV7(job,profile,{...preferences,ageDays:age,targetLocations:preferences.targetLocations||[],targetDirections:preferences.targetDirections||[]})};});
    if(profile)rows=rows.filter(j=>(j.match.score??0)>=threshold && j.match.career?.level!=='senior');
    if(freshOnly&&rows.some(j=>Number.isFinite(j._age)&&j._age<999))rows=rows.filter(j=>j._age<=45||j._age===999);
    if(sort==='match')rows.sort((a,b)=>(b.match.score??-1)-(a.match.score??-1)||cheapFit(b,profile,preferences)-cheapFit(a,profile,preferences)||String(b.updatedAt||'').localeCompare(String(a.updatedAt||'')));
    else if(sort==='fresh')rows.sort((a,b)=>String(b.updatedAt||'').localeCompare(String(a.updatedAt||'')));
    else if(sort==='company')rows.sort((a,b)=>String(a.company||'').localeCompare(String(b.company||''),'zh-CN'));
    return rows;
  }

  CORE.scoreJob=scoreJobV7;
  CORE.filterAndRank=filterAndRankV7;
  CORE.isDomesticJob=isDomestic;
  CORE.version='7.1.0';
})();
