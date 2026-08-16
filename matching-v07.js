(function(){
  'use strict';
  if(!window.PTO_MATCHING)return;
  const CORE=window.PTO_MATCHING;
  const baseScore=CORE.scoreJob;

  // Title-first role taxonomy. JD vocabulary is deliberately secondary: a
  // marketing/product role that happens to mention AI must not rank as AI Infra.
  const FAMILIES=[
    ['ai_infra',/(?:ai\s*infra|llm\s*(?:serving|inference)|大模型(?:推理|服务|部署)|推理(?:系统|引擎|平台|框架)|模型服务|serving\s*(?:system|engine)|推理加速)/i],
    ['cuda',/(?:cuda|gpu\s*(?:kernel|performance)|算子(?:开发|优化|工程)|高性能算子|kernel\s*engineer|triton|cutlass)/i],
    ['quant',/(?:模型量化|推理量化|ptq|qat|低比特|模型压缩|量化算法|quantization)/i],
    ['multimodal',/(?:vlm|vla|多模态|视觉语言|具身智能|机器人(?:大模型|学习)|vision[- ]language)/i],
    ['chip_software',/(?:ai\s*芯片.*(?:软件|编译)|npu.*(?:软件|编译|runtime)|编译器(?:开发|工程)|compiler\s*engineer|mlir|算子库|runtime\s*开发|芯片软件)/i],
    ['hpc',/(?:高性能计算|hpc|并行计算|通信优化|rdma|mpi|nccl.*(?:通信|优化)|分布式计算)/i],
    ['llm_algo',/(?:大模型算法|llm\s*(?:algorithm|research)|nlp\s*算法|自然语言处理|预训练|对齐算法|强化学习算法|agent\s*算法)/i],
    ['cv',/(?:计算机视觉|视觉算法|图像算法|视频算法|目标检测|3d\s*视觉|slam|cv\s*算法)/i],
    ['backend',/(?:后端|服务端|后台开发|java\s*开发|go\s*开发|golang|分布式系统|云原生|基础架构|平台研发|server[- ]side)/i],
    ['frontend',/(?:前端|客户端|android|ios|web\s*开发|react|vue)/i],
    ['embedded',/(?:嵌入式|机器人软件|控制算法|端侧部署|ros2?|stm32|rtos|jetson)/i],
    ['hardware',/(?:数字ic|芯片设计|芯片验证|fpga|eda|rtl|verilog|硬件研发|soc\s*设计)/i],
    ['data',/(?:推荐算法|搜索算法|广告算法|数据工程|数据科学|数据分析|数据挖掘)/i],
    ['test_sre',/(?:测试开发|自动化测试|\bsre\b|运维研发|devops|安全研发|信息安全)/i],
    ['product',/(?:产品经理|产品运营|用户运营|商业分析|市场营销|品牌|销售|商务|采购|人力资源|hrbp|财务|法务)/i],
    ['finance_quant',/(?:量化研究|量化开发|金融工程|投研|交易系统|quant\s*(?:research|developer))/i],
  ];

  const DIR_FAMILIES={
    'AI Infra / 大模型推理系统':['ai_infra','cuda','hpc','backend','chip_software'],
    'CUDA / GPU 算子优化':['cuda','hpc','ai_infra','chip_software'],
    'LLM / VLM 量化压缩':['quant','ai_infra','cuda','llm_algo','multimodal'],
    'VLM / VLA / 多模态':['multimodal','llm_algo','quant','embedded'],
    'AI 芯片软件 / 编译器':['chip_software','cuda','hpc','hardware'],
    'HPC / 分布式计算':['hpc','cuda','backend','ai_infra'],
    '大模型 / NLP 算法':['llm_algo','multimodal','quant','ai_infra'],
    '计算机视觉 / 多媒体算法':['cv','multimodal','embedded'],
    '后端 / 分布式系统':['backend','hpc','ai_infra'],
    '前端 / 客户端':['frontend'],
    '嵌入式 / 机器人':['embedded','multimodal','cuda'],
    '芯片 / EDA / 硬件':['hardware','chip_software','cuda'],
    '数据 / 推荐 / 搜索':['data','backend'],
    '测试 / SRE / 安全':['test_sre','backend'],
    '产品 / 运营 / 商业':['product'],
    '金融 / 量化':['finance_quant','data','backend'],
  };

  const CHINA_CITIES=['北京','上海','深圳','广州','杭州','南京','苏州','成都','武汉','西安','天津','重庆','长沙','合肥','无锡','厦门','青岛','济南','宁波','东莞','珠海','佛山','大连','沈阳','郑州','福州'];
  const TIER1=['北京','上海','深圳','广州','杭州'];
  const FOREIGN=/(?:United States|USA|\bUS\b|Canada|United Kingdom|\bUK\b|Germany|France|Netherlands|Poland|Spain|Italy|Sweden|Norway|Finland|Denmark|Switzerland|Australia|New Zealand|Japan|Korea|Singapore|India|Brazil|Mexico|Israel|Ireland|Portugal)/i;

  function text(v){return CORE.cleanText(v||'');}
  function classifyJob(job){
    const title=text(job.role||job.title);
    const dept=text(job.department);
    const titleFamilies=[];
    for(const [family,re] of FAMILIES)if(re.test(title))titleFamilies.push(family);
    if(titleFamilies.length)return {primary:titleFamilies[0],families:titleFamilies,confidence:'title'};
    // Department may disambiguate generic titles such as “软件研发工程师”.
    const deptFamilies=[];
    for(const [family,re] of FAMILIES)if(re.test(dept))deptFamilies.push(family);
    if(deptFamilies.length)return {primary:deptFamilies[0],families:deptFamilies,confidence:'department'};
    // JD is a weak fallback only. Require a direction-specific term and never
    // classify generic corporate/product families from body boilerplate.
    const body=text(job.jd||job.description).slice(0,900);
    const bodyFamilies=[];
    for(const [family,re] of FAMILIES){
      if(family==='product')continue;
      if(re.test(body))bodyFamilies.push(family);
    }
    return {primary:bodyFamilies[0]||'unknown',families:bodyFamilies.slice(0,3),confidence:bodyFamilies.length?'body':'unknown'};
  }

  function geoSignal(job,opts={}){
    const loc=text(job.location);
    const targets=(opts.targetLocations||[]).filter(Boolean);
    const foreign=FOREIGN.test(loc)&&!CHINA_CITIES.some(c=>loc.includes(c));
    const beijing=loc.includes('北京');
    const tier1=TIER1.some(c=>loc.includes(c));
    const china=CHINA_CITIES.some(c=>loc.includes(c))||/[\u4e00-\u9fa5]/.test(loc);
    const targetHit=targets.some(c=>loc.includes(c));
    let delta=0,label='';
    if(foreign){delta=-35;label='海外地点';}
    else if(targetHit){delta+=beijing?12:8;label=beijing?'北京优先':'目标城市';}
    else if(beijing){delta+=10;label='北京';}
    else if(tier1){delta+=5;label='一线城市';}
    else if(china){delta+=1;label='国内';}
    return {foreign,beijing,tier1,china,targetHit,delta,label};
  }

  function sourceSignal(job){
    const label=text(job.sourceLabel||job.source_label||job.source);
    const url=text(job.applyUrl||job.apply_url||job.noticeUrl||job.notice_url);
    const official=/(?:公司官网|官方招聘|企业官网|官方\s*ATS)/i.test(label)||/(?:jobs\.feishu\.cn|zhiye\.com|mokahr\.com|join\.qq\.com|zhaopin\.jd\.com|jobs\.bytedance\.com|talent\.baidu\.com)/i.test(url);
    return {official,delta:official?8:0,label:official?'企业官网':''};
  }

  function profileFamilies(profile){
    const s=profile?.signals||profile||{};
    const dirs=(s.directionScores?.length?s.directionScores.map(x=>x.name):s.directions||[]).slice(0,4);
    const weights=new Map();
    dirs.forEach((d,i)=>(DIR_FAMILIES[d]||[]).forEach((f,j)=>weights.set(f,Math.max(weights.get(f)||0,Math.max(1,9-i*2-j)))));
    return {dirs,weights};
  }

  function familyFit(jobFamily,profile){
    const pf=profileFamilies(profile);
    if(!profile||!pf.weights.size)return {kind:'unknown',delta:0,label:''};
    const families=jobFamily.families.length?jobFamily.families:[jobFamily.primary];
    const best=Math.max(0,...families.map(f=>pf.weights.get(f)||0));
    if(best>=7)return {kind:'direct',delta:14,label:'岗位方向高度吻合'};
    if(best>=3)return {kind:'adjacent',delta:6,label:'岗位方向相邻'};
    if(jobFamily.primary==='unknown')return {kind:'unknown',delta:-5,label:'岗位方向证据较弱'};
    return {kind:'mismatch',delta:-32,label:'岗位方向不匹配'};
  }

  function scoreJobV7(job,profile,opts={}){
    const base=baseScore(job,profile,opts);
    if(base.score===null)return {...base,family:classifyJob(job),geo:geoSignal(job,opts),sourceTrust:sourceSignal(job)};
    const family=classifyJob(job);
    const fit=familyFit(family,profile);
    const geo=geoSignal(job,opts);
    const sourceTrust=sourceSignal(job);
    const career=CORE.careerSignal?CORE.careerSignal(job):{level:'unknown',delta:0,label:''};

    // Generic body keyword overlap is deliberately compressed. Precision comes
    // first from title/department role family, then skills/evidence, then locale.
    let raw=Math.round((base.score||0)*0.72 + fit.delta + geo.delta + sourceTrust.delta);
    if(career.level==='early')raw+=8;
    if(career.level==='senior')raw-=30;
    if(geo.foreign)raw=Math.min(raw,28);
    if(fit.kind==='mismatch')raw=Math.min(raw,36);
    if(fit.kind==='mismatch'&&family.primary==='product')raw=Math.min(raw,18);
    if(career.level==='senior')raw=Math.min(raw,32);
    const score=Math.max(0,Math.min(99,raw));

    const reasons=[];
    if(fit.label)reasons.push(fit.label);
    if(geo.label&&!geo.foreign)reasons.push(geo.label);
    if(sourceTrust.official)reasons.push(sourceTrust.label);
    if(career.level==='early')reasons.push('校招 / 初阶');
    for(const r of base.reasons||[])if(!reasons.includes(r))reasons.push(r);
    return {
      ...base,score,reasons:reasons.slice(0,6),family,geo,sourceTrust,career,roleFit:fit,
      components:{...(base.components||{}),roleFamily:fit.delta,geo:geo.delta,officialSource:sourceTrust.delta,careerV7:career.level==='early'?8:career.level==='senior'?-30:0}
    };
  }

  CORE.classifyJob=classifyJob;
  CORE.geoSignal=geoSignal;
  CORE.sourceSignal=sourceSignal;
  CORE.profileFamilies=profileFamilies;
  CORE.scoreJob=scoreJobV7;
  CORE.version='7.0.0';
})();
