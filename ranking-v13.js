(function(){
  'use strict';
  if(!window.PTO_MATCHING||!window.PTO_CAREER_V13)return;
  const CORE=window.PTO_MATCHING;
  const TAX=window.PTO_CAREER_V13;

  const CAMPUS=/(2027|2028|27届|28届|校招|校园招聘|应届|毕业生|秋招|春招|new\s*grad|graduate|campus)/i;
  const INTERN=/(实习|intern)/i;
  const SENIOR=/(senior|staff|principal|资深|专家|负责人|总监|主管|3\s*[-~至]\s*5年|5年以上|[3-9]\s*年(?:工作)?经验)/i;
  const SOCIAL=/(社招|社会招聘|experienced|off-campus)/i;
  const GENERIC=new Set(['python','matlab','c++','java','linux','office','excel','git','项目','研究','工程','研发','分析','设计','管理','技术','系统','模型','算法','实验','开发']);
  const DEGREE_RANK={'大专':1,'专科':1,'本科':2,'学士':2,'硕士':3,'研究生':3,'博士':4,'phd':4,'master':3,'bachelor':2};
  const RELATED={
    'ai-infra':new Set(['ai-algorithm','software-backend','sre-security','chip-software','data']),
    'ai-algorithm':new Set(['ai-infra','data','software-backend']),
    'software-backend':new Set(['ai-infra','data','sre-security']),
    'frontend-client':new Set(['software-backend','product-project','design-creative']),
    'data':new Set(['ai-algorithm','software-backend','finance-investment','consulting-strategy']),
    'sre-security':new Set(['software-backend','ai-infra']),
    'chip-software':new Set(['ai-infra','semiconductor','embedded-electronics']),
    'semiconductor':new Set(['chip-software','embedded-electronics','materials','math-physics']),
    'embedded-electronics':new Set(['semiconductor','mechanical-automation','energy-power','chip-software']),
    'mechanical-automation':new Set(['embedded-electronics','materials','energy-power']),
    'materials':new Set(['chemistry','semiconductor','mechanical-automation','energy-power','environment','math-physics']),
    'chemistry':new Set(['materials','biotech-pharma','environment','agri-food']),
    'energy-power':new Set(['embedded-electronics','materials','mechanical-automation','environment']),
    'civil':new Set(['architecture','environment','geo-petroleum']),
    'architecture':new Set(['civil','design-creative']),
    'environment':new Set(['chemistry','civil','materials','energy-power']),
    'biotech-pharma':new Set(['healthcare','chemistry','agri-food']),
    'healthcare':new Set(['biotech-pharma']),
    'math-physics':new Set(['semiconductor','materials','ai-algorithm','data']),
    'finance-accounting':new Set(['finance-investment','consulting-strategy']),
    'finance-investment':new Set(['finance-accounting','data','consulting-strategy']),
    'product-project':new Set(['operations-supply','marketing-sales','consulting-strategy','design-creative','software-backend']),
    'operations-supply':new Set(['product-project','marketing-sales','consulting-strategy']),
    'marketing-sales':new Set(['operations-supply','product-project','media-content']),
    'hr-admin':new Set(['consulting-strategy','policy-social']),
    'legal':new Set(['policy-social','finance-investment','hr-admin']),
    'consulting-strategy':new Set(['product-project','finance-investment','operations-supply','policy-social']),
    'design-creative':new Set(['product-project','media-content','architecture']),
    'media-content':new Set(['marketing-sales','design-creative','language-intl']),
    'education':new Set(['policy-social','media-content']),
    'geo-petroleum':new Set(['civil','energy-power','environment']),
    'agri-food':new Set(['biotech-pharma','chemistry','materials']),
    'language-intl':new Set(['media-content','marketing-sales','operations-supply']),
    'policy-social':new Set(['legal','consulting-strategy','hr-admin','education']),
  };

  const norm=v=>TAX.norm?TAX.norm(v):String(v||'').toLowerCase().replace(/\s+/g,' ').trim();
  const uniq=a=>[...new Set((a||[]).filter(Boolean))];
  const round=n=>Math.round(Number(n||0)*10)/10;
  function degreeRank(v){const s=norm(v);let r=0;for(const [k,n] of Object.entries(DEGREE_RANK))if(s.includes(k))r=Math.max(r,n);return r;}
  function related(a,b){return !!(a&&b&&(a===b||RELATED[a]?.has(b)||RELATED[b]?.has(a)));}
  function sourceScore(job){
    const tier=Number(job.sourceTier||0);
    if(tier>=7)return {score:7,label:'企业官网直连'};
    if(tier===6)return {score:6,label:'企业官方招聘源'};
    if(tier===5)return {score:5,label:'权威/已验证招聘来源'};
    if(tier===4)return {score:4,label:'国家就业平台'};
    if(tier===3)return {score:3,label:'高校就业网发现'};
    const s=norm([job.sourceLabel,job.source,job.sourceUrl,job.applyUrl,job.noticeUrl].join(' '));
    if(/direct-official|自主直连|招聘官网|mokahr/.test(s))return {score:7,label:'企业官网直连'};
    if(/企业官方|官方招聘|feishu|beisen|zhiye\.com/.test(s))return {score:6,label:'企业官方招聘源'};
    if(/国资委|sasac|政府|官方公告/.test(s))return {score:5,label:'权威招聘公告'};
    if(/国家大学生就业|ncss/.test(s))return {score:4,label:'国家就业平台'};
    if(/高校就业/.test(s))return {score:3,label:'高校就业网发现'};
    return {score:1,label:'公开聚合来源'};
  }
  function freshnessScore(age){const n=Number(age);if(!Number.isFinite(n)||n>=999)return 0;if(n<=14)return 5;if(n<=30)return 4;if(n<=60)return 2.5;if(n<=120)return 1;return 0;}
  function completenessScore(job){const jd=String(job.jd||'').trim();const direct=!!job.applyUrl;let score=0;if(jd.length>=220)score+=2;else if(jd.length>=80)score+=1;if(direct)score+=1;return {score:Math.min(3,score),sparse:jd.length<70,direct};}

  function domainScore(job,profile,preferences={}){
    const p=TAX.profileDomains(profile),j=TAX.jobDomains(job);const pp=p.primary,jp=j.primary;
    if(!pp||!jp)return {score:0,label:'职业方向证据不足',profile:p,job:j,exact:false,related:false,mismatch:false};
    const pTop=p.scores.slice(0,4),jTop=j.scores.slice(0,4);
    let best=0,bestPair=null;
    for(let pi=0;pi<pTop.length;pi++)for(let ji=0;ji<jTop.length;ji++){
      const a=pTop[pi],b=jTop[ji];let value=0;
      if(a.id&&b.id&&a.id===b.id)value=30-(pi*4.5+ji*4);
      else if(related(a.id,b.id))value=14-(pi*2.2+ji*2);
      if(value>best){best=value;bestPair=[a,b];}
    }
    const targets=preferences.targetDirections||[];
    if(targets.length&&targets.some(t=>jTop.some(row=>norm(row.name).includes(norm(t))||norm(t).includes(norm(row.name)))))best=Math.min(30,best+2);
    const exact=!!bestPair&&bestPair[0]?.id===bestPair[1]?.id;
    const rel=!!bestPair&&related(bestPair[0]?.id,bestPair[1]?.id);
    const mismatch=!!(pp.id&&jp.id&&!rel&&Number(p.confidence||0)>=65&&Number(j.confidence||0)>=55);
    return {score:Math.max(0,Math.min(30,best)),label:exact?`${pp.name} · 岗位领域直接匹配`:rel?`${pp.name} · 相邻职业领域`:mismatch?`${pp.name} ↔ ${jp.name} 领域冲突`:'职业领域证据较弱',profile:p,job:j,exact,related:rel,mismatch};
  }

  function skillScore(job,profile){
    const title=norm(job.role),body=norm([job.jd,job.department,job.industry].join(' '));
    const skills=uniq(profile?.signals?.skills||[]).filter(x=>norm(x).length>=2).slice(0,64);
    const primary=profile?.signals?.primaryCareerDomain||profile?.signals?.primaryDirection||'';
    const primaryTerms=new Set((TAX.termsFor(primary)||[]).map(norm));
    let total=0,hit=0;const titleHits=[],bodyHits=[];
    for(const skill of skills){
      const key=norm(skill);if(!key)continue;let w=GENERIC.has(key)?.35:(primaryTerms.has(key)?1.7:(key.length>=7?1.25:1));
      total+=w;
      if(title.includes(key)){hit+=w*1.65;titleHits.push(skill);}else if(body.includes(key)){hit+=w;bodyHits.push(skill);}
    }
    // Resume keywords are useful for unmodelled majors, but intentionally have
    // low weight so generic prose cannot overpower a clear career-domain clash.
    const keywordHits=[];
    for(const raw of (profile?.signals?.keywords||[]).slice(0,40)){
      const key=norm(raw);if(key.length<3||GENERIC.has(key))continue;
      if(title.includes(key)||body.includes(key)){hit+=0.28;keywordHits.push(raw);}
    }
    const denom=Math.max(5,Math.min(18,total));const coverage=Math.min(1,hit/denom);const score=Math.min(24,24*Math.pow(coverage,.88));
    return {score,titleHits:titleHits.slice(0,5),bodyHits:bodyHits.slice(0,7),keywordHits:keywordHits.slice(0,5),hitCount:titleHits.length+bodyHits.length+keywordHits.length,label:titleHits.length?`标题技能 ${titleHits.slice(0,2).join(' · ')}`:bodyHits.length?`简历/JD ${bodyHits.slice(0,3).join(' · ')}`:''};
  }
  function careerScore(job,profile){
    const blob=norm([job.role,job.batch,job.graduation,job.jd].join(' '));const grad=String(profile?.signals?.graduationYear||'');let score=0,penalty=0,label='';
    if(CAMPUS.test(blob)){score+=8;label='校招 / 应届';}else if(INTERN.test(blob)){score+=5;label='实习';}else if(grad){score+=1;}
    if(grad&&blob.includes(grad)){score+=5;label=`${grad}届符合`;}
    if(SENIOR.test(blob)){penalty+=20;label='资深/经验要求冲突';}else if(SOCIAL.test(blob)&&!CAMPUS.test(blob)){penalty+=8;label='社会招聘';}
    return {score:Math.min(13,score),penalty,label,campus:CAMPUS.test(blob)||INTERN.test(blob)};
  }
  function locationScore(job,preferences={}){
    const targets=(preferences.targetLocations||[]).filter(Boolean);if(!targets.length)return {score:0,label:'未设置目标城市'};
    const loc=String(job.location||'');if(targets.some(t=>loc.includes(t)))return {score:10,label:'目标城市'};
    return {score:0,label:'非目标城市'};
  }
  function eligibilityScore(job,profile,domain){
    const wanted=degreeRank(job.education),have=degreeRank(profile?.signals?.degree||'');let score=0,label='';
    if(wanted&&have){if(have>=wanted){score+=4;label='学历满足';}else label='学历可能不满足';}else if(!wanted)score+=1.5;
    const grad=String(profile?.signals?.graduationYear||''),jobGrad=String(job.graduation||'');
    if(grad&&jobGrad)score+=jobGrad.includes(grad)?3:0;else if(!jobGrad)score+=1;
    if(domain.exact)score+=2;
    return {score:Math.min(8,score),label};
  }

  function scoreJobV13(job,profile,opts={}){
    if(!profile)return {score:null,reasons:[],hits:[],components:{},calibration:'no-profile'};
    const domain=domainScore(job,profile,opts),skills=skillScore(job,profile),career=careerScore(job,profile),location=locationScore(job,opts),eligibility=eligibilityScore(job,profile,domain),source=sourceScore(job),fresh=freshnessScore(opts.ageDays),complete=completenessScore(job);
    let penalty=career.penalty;
    let cap=99;
    const pConf=Number(domain.profile?.confidence||0),jConf=Number(domain.job?.confidence||0);
    if(domain.mismatch){penalty+=pConf>=75&&jConf>=65?26:18;cap=Math.min(cap,pConf>=75&&jConf>=65?38:48);}
    if(domain.score<5&&skills.score<7&&pConf>=55)cap=Math.min(cap,48);
    if(domain.score<10&&skills.score<10&&pConf>=60)cap=Math.min(cap,62);
    if(complete.sparse)penalty+=2;
    if((profile?.signals?.graduationYear||'')&&!career.campus&&career.penalty)cap=Math.min(cap,70);
    let raw=domain.score+skills.score+career.score+location.score+eligibility.score+source.score+fresh+complete.score-penalty;
    // 95+ is reserved for unusually strong, explicit evidence. Location is not
    // part of the gate when the user deliberately left location unconstrained.
    const locationRequired=(opts.targetLocations||[]).length>0;
    const elite=domain.exact&&domain.score>=26&&skills.score>=15&&career.score>=8&&source.score>=6&&(!locationRequired||location.score===10);
    if(!elite)cap=Math.min(cap,94);
    const perfect=elite&&skills.score>=20&&eligibility.score>=5&&fresh>=4&&complete.score>=2;
    if(!perfect)cap=Math.min(cap,98);
    const score=Math.max(0,Math.min(cap,round(raw)));
    const reasons=[];
    for(const item of [domain.label,skills.label,career.label,location.score?location.label:'',eligibility.label,source.label])if(item)reasons.push(item);
    const hits=uniq([...skills.titleHits,...skills.bodyHits,...skills.keywordHits]).slice(0,9);
    return {score,reasons:uniq(reasons).slice(0,7),hits,direction:domain.job?.primary?.name||'',components:{
      direction:round(domain.score),skills:round(skills.score),career:round(career.score),location:round(location.score),eligibility:round(eligibility.score),source:round(source.score),freshness:round(fresh),completeness:round(complete.score),penalty:round(penalty),raw:round(raw),cap,
      profileDomain:domain.profile?.primary?.name||'',jobDomain:domain.job?.primary?.name||'',profileDomainConfidence:pConf,jobDomainConfidence:jConf,domainMismatch:domain.mismatch,domainExact:domain.exact,skillHits:skills.hitCount,sourceTier:Number(job.sourceTier||0)
    },calibration:'v13-resume-domain-general'};
  }

  function metadataPass(job,options){
    const location=options.location||'all',companyType=options.companyType||'all',batch=options.batch||'all';
    return (location==='all'||String(job.location||'').includes(location))&&
      (companyType==='all'||job.companyType===companyType||job.company_type===companyType)&&
      (batch==='all'||job.batch===batch);
  }
  function ageOf(job,options){return options.ageOf?options.ageOf(job.updatedAt||job.updated_at):999;}
  function searchRank(job,q){const result=CORE.searchMatch?CORE.searchMatch(job,q):{matched:true,boost:0};return result;}
  function preRankValue(job,profile,options){
    const affinity=TAX.cheapAffinity(job,profile);const source=sourceScore(job).score;const age=ageOf(job,options);const freshness=freshnessScore(age);
    return affinity*10+source*1.5+freshness;
  }

  function filterAndRankV13(jobs,options={}){
    const q=String(options.query||'').trim(),profile=options.profile||null;
    let base=(jobs||[]).filter(job=>metadataPass(job,options));
    if(q){
      base=base.map(job=>{const s=searchRank(job,q);return {job,s};}).filter(row=>row.s.matched).sort((a,b)=>(b.s.boost||0)-(a.s.boost||0)).map(row=>row.job);
      return base.map(job=>({...job,_age:ageOf(job,options),_search:searchRank(job,q),match:scoreJobV13(job,profile,{...(options.preferences||{}),ageDays:ageOf(job,options),targetLocations:options.preferences?.targetLocations||[],targetDirections:options.preferences?.targetDirections||[]})})).sort((a,b)=>(b._search?.boost||0)-(a._search?.boost||0)||(b.match.score??-1)-(a.match.score??-1)||String(b.updatedAt||'').localeCompare(String(a.updatedAt||'')));
    }
    if(!profile){
      if(options.freshOnly&&base.some(j=>ageOf(j,options)<999))base=base.filter(j=>ageOf(j,options)<=30||ageOf(j,options)===999);
      if(options.sort==='company')base.sort((a,b)=>String(a.company||'').localeCompare(String(b.company||''),'zh-CN'));
      else base.sort((a,b)=>String(b.updatedAt||'').localeCompare(String(a.updatedAt||'')));
      return base.map(job=>({...job,_age:ageOf(job,options),match:{score:null,reasons:[],hits:[],components:{},calibration:'no-profile'}}));
    }

    // Full semantic/domain scoring is intentionally bounded. Every row gets a
    // cheap resume-specific pre-rank; only the strongest slice is expanded into
    // detailed evidence. This keeps 60k-row GitHub Pages catalogues responsive.
    const FULL_LIMIT=Math.max(2500,Math.min(8000,Number(window.PTO_CONFIG?.fullScoreLimit||5600)));
    base=base.map(job=>({job,pre:preRankValue(job,profile,options),age:ageOf(job,options)})).sort((a,b)=>b.pre-a.pre||String(b.job.updatedAt||'').localeCompare(String(a.job.updatedAt||''))).slice(0,FULL_LIMIT).map(row=>({...row.job,_age:row.age,match:scoreJobV13(row.job,profile,{...(options.preferences||{}),ageDays:row.age,targetLocations:options.preferences?.targetLocations||[],targetDirections:options.preferences?.targetDirections||[]})}));
    const threshold=Number(options.threshold??25);base=base.filter(job=>(job.match.score??0)>=threshold);
    if(options.freshOnly&&base.some(j=>Number.isFinite(j._age)&&j._age<999))base=base.filter(j=>j._age<=30||j._age===999);
    if(options.sort==='fresh')base.sort((a,b)=>String(b.updatedAt||'').localeCompare(String(a.updatedAt||''))||(b.match.score??0)-(a.match.score??0));
    else if(options.sort==='company')base.sort((a,b)=>String(a.company||'').localeCompare(String(b.company||''),'zh-CN')||(b.match.score??0)-(a.match.score??0));
    else base.sort((a,b)=>(b.match.score??-1)-(a.match.score??-1)||(b.match.components?.direction??0)-(a.match.components?.direction??0)||(b.match.components?.skills??0)-(a.match.components?.skills??0));
    return base;
  }

  CORE.scoreJob=scoreJobV13;
  CORE.filterAndRank=filterAndRankV13;
  CORE.version='13.0.0';
  window.PTO_MATCHING_V13={scoreJob:scoreJobV13,filterAndRank:filterAndRankV13};
})();
