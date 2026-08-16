(function(root,factory){
  const api=factory();
  if(typeof module==='object'&&module.exports) module.exports=api;
  root.PTO_MATCHING=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(){
  'use strict';

  const DEGREE_RANK={'大专':1,'专科':1,'本科':2,'学士':2,'硕士':3,'研究生':3,'博士':4,'phd':4,'master':3,'bachelor':2};
  const CITIES=['北京','上海','深圳','广州','杭州','南京','成都','武汉','西安','苏州','天津','重庆','长沙','合肥','无锡','厦门','青岛','济南','宁波','东莞','珠海','佛山','大连','沈阳','郑州','福州','海外','香港'];
  const STOP=new Set(['负责','相关','项目','工作','使用','进行','基于','以及','通过','实现','技术','能力','熟悉','掌握','经验','优化','系统','模型','算法','开发','设计','支持','研究','本科','硕士','博士','北京','上海','深圳','公司','团队','岗位','方向','主要','参与','完成','具有','良好','能够','需求','业务']);

  const DIRECTIONS=[
    {name:'AI Infra / 大模型推理系统',roles:['AI Infra','大模型推理','推理系统','推理引擎','LLM Serving','平台研发'],terms:{'vllm':10,'sglang':10,'tensorrt-llm':9,'pagedattention':10,'kv cache':8,'kv-cache':8,'prefill':7,'decode':6,'continuous batching':8,'speculative decoding':8,'llm serving':9,'推理系统':10,'大模型推理':10,'推理引擎':9,'serving':5,'flashattention':6,'nccl':5,'cuda':4,'分布式推理':8,'显存管理':7,'调度器':6,'scheduler':5}},
    {name:'CUDA / GPU 算子优化',roles:['CUDA开发','GPU性能优化','算子开发','高性能算子','Kernel Engineer'],terms:{'cuda':8,'triton':9,'cutlass':9,'gemm':10,'tensor core':8,'tensorcore':8,'cublas':6,'shared memory':7,'warp':7,'mma':7,'wgmma':8,'nsight':7,'roofline':7,'算子优化':10,'算子开发':9,'gpu性能':8,'kernel':5,'访存':5,'bank conflict':6}},
    {name:'LLM / VLM 量化压缩',roles:['模型量化','推理量化','模型压缩','PTQ算法','低比特量化'],terms:{'ptq':10,'qat':8,'awq':10,'gptq':10,'smoothquant':9,'rtn':8,'hessian':7,'w4a16':9,'w4':5,'int4':8,'int8':6,'fp8':7,'mxfp8':9,'量化':9,'模型压缩':8,'剪枝':7,'蒸馏':6,'低比特':8,'calibration':5}},
    {name:'VLM / VLA / 多模态',roles:['多模态算法','VLM算法','VLA算法','具身智能','视觉语言模型'],terms:{'vlm':10,'vla':10,'multimodal':8,'vision-language':9,'vision language':9,'qwen-vl':8,'llava':8,'视觉语言':10,'多模态':9,'具身智能':9,'视觉token':7,'visual token':7,'token pruning':8,'图文':5}},
    {name:'AI 芯片软件 / 编译器',roles:['AI芯片软件','NPU软件','编译器开发','算子库','Runtime开发'],terms:{'npu':9,'rpu':9,'compiler':7,'编译器':9,'算子库':9,'runtime':8,'mlir':9,'tvm':8,'hxcc':10,'ai chip':8,'芯片软件':10,'图编译':7,'计算图':6,'kernel compiler':8,'后端编译':8}},
    {name:'HPC / 分布式计算',roles:['高性能计算','分布式系统','通信优化','并行计算'],terms:{'hpc':10,'mpi':9,'openmp':8,'rdma':9,'nccl':7,'allreduce':8,'distributed':6,'tensor parallel':7,'pipeline parallel':7,'data parallel':6,'分布式':8,'高性能计算':10,'通信优化':9,'并行计算':9,'多机多卡':8}},
    {name:'大模型 / NLP 算法',roles:['大模型算法','NLP算法','训练算法','强化学习算法','LLM算法'],terms:{'llm':7,'transformer':6,'大语言模型':9,'大模型':7,'nlp':8,'自然语言处理':9,'rag':6,'rlhf':8,'dpo':7,'ppo':7,'强化学习':8,'预训练':8,'微调':6,'sft':7,'alignment':6,'agent':5}},
    {name:'计算机视觉 / 多媒体算法',roles:['计算机视觉','视觉算法','图像算法','视频算法','目标检测'],terms:{'opencv':7,'yolo':9,'detection':7,'segmentation':7,'目标检测':9,'计算机视觉':10,'图像处理':8,'视觉算法':9,'cv':5,'ocr':6,'视频编解码':6,'slam':7,'3d':4}},
    {name:'后端 / 分布式系统',roles:['后端开发','服务端研发','基础架构','分布式系统','云原生'],terms:{'java':6,'golang':7,'go':3,'spring':6,'redis':6,'mysql':6,'kafka':6,'微服务':7,'后端':9,'服务端':9,'分布式系统':8,'云原生':8,'kubernetes':7,'k8s':7,'grpc':6,'数据库':5,'高并发':7}},
    {name:'前端 / 客户端',roles:['前端开发','客户端开发','Web开发','移动端开发'],terms:{'javascript':7,'typescript':8,'react':8,'vue':8,'frontend':8,'前端':10,'ios':8,'android':8,'swift':7,'kotlin':7,'flutter':7,'客户端':8,'web':4}},
    {name:'嵌入式 / 机器人',roles:['嵌入式软件','机器人软件','控制算法','端侧部署'],terms:{'embedded':8,'嵌入式':10,'stm32':8,'rtos':8,'ros':8,'ros2':8,'机器人':8,'robotics':8,'控制算法':7,'jetson':7,'orin':7,'端侧部署':8,'传感器':5,'雷达':6}},
    {name:'芯片 / EDA / 硬件',roles:['数字IC','芯片设计','芯片验证','FPGA','EDA研发','硬件研发'],terms:{'fpga':9,'verilog':9,'systemverilog':9,'rtl':8,'asic':8,'eda':9,'vivado':8,'数字电路':8,'芯片设计':9,'芯片验证':9,'ic':4,'soc':6,'硬件':5,'电路':5,'验证工程师':7}},
    {name:'数据 / 推荐 / 搜索',roles:['数据工程','推荐算法','搜索算法','数据分析','数据科学'],terms:{'spark':7,'flink':7,'hadoop':6,'推荐':8,'搜索':7,'广告':6,'ranking':7,'recall':6,'数据工程':8,'数据分析':8,'数据科学':8,'sql':5,'特征工程':6,'数据挖掘':7}},
    {name:'测试 / SRE / 安全',roles:['测试开发','SRE','运维研发','安全研发'],terms:{'测试开发':9,'自动化测试':8,'sre':9,'devops':7,'运维':7,'可观测':6,'安全':6,'渗透':7,'攻防':7,'漏洞':6,'ci/cd':6,'prometheus':5,'grafana':5}},
    {name:'产品 / 运营 / 商业',roles:['产品经理','AI产品','运营','市场','商业分析'],terms:{'产品经理':10,'产品运营':8,'运营':6,'市场':6,'用户研究':7,'商业分析':8,'增长':6,'营销':6,'品牌':5,'需求分析':7,'竞品':6,'产品设计':7}},
    {name:'金融 / 量化',roles:['量化研究','量化开发','金融科技','投研'],terms:{'quant':8,'量化':9,'因子':7,'回测':7,'金融':6,'证券':6,'期货':6,'投研':8,'风险模型':6,'交易系统':7,'金融工程':8}},
  ];

  const COMPANY_ALIASES={
    '京东':['京东','jd','jd.com','京东集团','京东科技','京东物流','京东零售'],
    '字节跳动':['字节跳动','字节','bytedance','tiktok'],
    '腾讯':['腾讯','tencent'],
    '阿里巴巴':['阿里巴巴','阿里','alibaba','淘天','阿里云'],
    '美团':['美团','meituan'],
    '百度':['百度','baidu'],
    '华为':['华为','huawei'],
    '小米':['小米','xiaomi'],
    '拼多多':['拼多多','pdd','temu'],
    '快手':['快手','kuaishou'],
  };

  function cleanText(v){return String(v||'').replace(/\u0000/g,' ').replace(/[\t\r]+/g,' ').replace(/\s+/g,' ').trim();}
  function norm(v){return cleanText(v).toLowerCase().replace(/[‐‑‒–—]/g,'-');}
  function uniq(xs){return [...new Set(xs.filter(Boolean))];}
  function occurrences(text,term){
    const t=norm(term); if(!t)return 0; let n=0,p=0; while((p=text.indexOf(t,p))>=0&&n<6){n++;p+=Math.max(1,t.length);} return n;
  }
  function termHits(text,terms){
    const hits=[]; let score=0;
    for(const [term,weight] of Object.entries(terms)){
      const n=occurrences(text,term); if(n){hits.push(term);score+=weight*Math.min(2,n);}
    }
    return {score,hits};
  }
  function inferDegree(text){
    const lower=norm(text); let best=''; let rank=0;
    for(const [k,r] of Object.entries(DEGREE_RANK)){if(lower.includes(k.toLowerCase())&&r>rank){best=k;rank=r;}}
    if(best==='phd')return '博士'; if(best==='master')return '硕士'; if(best==='bachelor')return '本科'; return best;
  }
  function inferYears(text){
    const explicit=[...(text.match(/20(?:2[4-9]|3\d)\s*届/g)||[])].map(x=>(x.match(/20\d{2}/)||[])[0]);
    const graduation=[...(text.match(/(?:毕业|graduat(?:e|ion))[^\n]{0,24}(20(?:2[4-9]|3\d))/ig)||[])].map(x=>(x.match(/20\d{2}/)||[])[0]);
    const all=(text.match(/20(?:2[4-9]|3\d)/g)||[]);
    return uniq([...explicit,...graduation,...all]).sort();
  }
  function extractKeywords(text){
    const latin=(norm(text).match(/[a-z][a-z0-9+.#/_-]{1,28}/g)||[]).filter(x=>!['and','the','with','from','using','for','of','to','in','on','or','is','as'].includes(x));
    const chinese=(text.match(/[\u4e00-\u9fa5]{2,9}/g)||[]).filter(x=>!STOP.has(x));
    const freq=new Map(); [...latin,...chinese].forEach(w=>freq.set(w,(freq.get(w)||0)+1));
    return [...freq.entries()].sort((a,b)=>b[1]-a[1]).slice(0,60).map(x=>x[0]);
  }
  function extractSignals(text){
    const raw=String(text||''); const lower=norm(raw);
    const scored=DIRECTIONS.map(d=>{
      const h=termHits(lower,d.terms);
      return {name:d.name,rawScore:h.score,evidence:h.hits.slice(0,8),roles:d.roles};
    }).filter(x=>x.rawScore>0).sort((a,b)=>b.rawScore-a.rawScore);
    const max=scored[0]?.rawScore||1;
    const directionScores=scored.slice(0,6).map((x,i)=>({...x,confidence:Math.max(18,Math.min(96,Math.round(34+62*(x.rawScore/max)*(i?0.92:1))))}));
    const knownSkills=[];
    for(const d of DIRECTIONS){for(const t of Object.keys(d.terms)){if(lower.includes(t))knownSkills.push(t);}}
    const degree=inferDegree(raw); const years=inferYears(raw);
    const mentionedCities=CITIES.filter(c=>raw.includes(c));
    const recommendedRoles=uniq(directionScores.slice(0,4).flatMap(x=>x.roles)).slice(0,12);
    return {
      skills:uniq(knownSkills).sort((a,b)=>b.length-a.length).slice(0,48),
      directions:directionScores.slice(0,4).map(x=>x.name), directionScores,
      primaryDirection:directionScores[0]?.name||'',
      recommendedRoles, degree, years,
      graduationYear:years.find(y=>raw.includes(`${y}届`))||years.at(-1)||'',
      mentionedCities:mentionedCities.slice(0,16), keywords:extractKeywords(raw)
    };
  }
  function buildProfile(rawText,fileName='resume'){
    const text=String(rawText||'').replace(/\u0000/g,' ').replace(/[ \t]+/g,' ').replace(/\n{3,}/g,'\n\n').trim().slice(0,180000);
    const lines=text.split(/\n/).map(x=>x.trim()).filter(Boolean);
    const probable=lines.slice(0,8).find(x=>/^[\u4e00-\u9fa5·]{2,6}$/.test(x));
    const base=String(fileName).replace(/\.(pdf|docx|txt)$/i,'');
    return {name:base,fileName,displayName:probable||base,rawText:text,profileVersion:4,signals:extractSignals(text)};
  }
  function directionEvidence(direction,text){
    const d=DIRECTIONS.find(x=>x.name===direction); if(!d)return {score:0,hits:[]}; return termHits(norm(text),d.terms);
  }
  function degreeCompatible(candidate,required){
    if(!candidate||!required)return null; const c=Object.entries(DEGREE_RANK).find(([k])=>norm(candidate).includes(k)); const r=Object.entries(DEGREE_RANK).find(([k])=>norm(required).includes(k));
    if(!c||!r)return null; return c[1]>=r[1];
  }
  function scoreJob(job,profile,opts={}){
    if(!profile)return {score:null,reasons:[],hits:[],direction:'',components:{}};
    const s=profile.signals||profile; const text=[job.role,job.jd,job.description,job.industry,(job.tags||[]).join(' '),job.company,job.department].join(' '); const lower=norm(text);
    const dirs=(s.directionScores?.length?s.directionScores:(s.directions||[]).map((name,i)=>({name,confidence:80-i*10}))).slice(0,5);
    let bestDir={name:'',fit:0,hits:[]};
    for(const d of dirs){const ev=directionEvidence(d.name,lower); const fit=ev.score*Math.max(.45,(d.confidence||60)/100); if(fit>bestDir.fit)bestDir={name:d.name,fit,hits:ev.hits};}
    const directionScore=Math.min(38,Math.round(bestDir.fit*1.7));
    const skillHits=uniq((s.skills||[]).filter(k=>k.length>1&&lower.includes(norm(k))));
    const skillScore=Math.min(32,skillHits.reduce((sum,k)=>sum+(k.length>=6?6:4),0));
    const keywordHits=uniq((s.keywords||[]).filter(k=>String(k).length>2&&lower.includes(norm(k)))).slice(0,10);
    const keywordScore=Math.min(10,keywordHits.length*2);
    let compatibility=0; const reasons=[];
    if(bestDir.name&&directionScore>=8) reasons.push(`${bestDir.name}${bestDir.hits.length?` · ${bestDir.hits.slice(0,2).join('/')}`:''}`);
    if(skillHits.length) reasons.push(`技能 ${skillHits.slice(0,4).join(' · ')}`);
    const dc=degreeCompatible(s.degree,job.education); if(dc===true){compatibility+=6;reasons.push('学历符合');}else if(dc===false)compatibility-=10;
    const gy=s.graduationYear||s.years?.at?.(-1); if(gy&&job.graduation&&String(job.graduation).includes(gy)){compatibility+=6;reasons.push(`${gy}届符合`);}
    const targetLocations=opts.targetLocations||[]; if(targetLocations.length&&targetLocations.some(c=>String(job.location||'').includes(c))){compatibility+=5;reasons.push('目标城市');}
    const targetDirections=opts.targetDirections||[]; if(targetDirections.some(d=>directionEvidence(d,lower).score>0)){compatibility+=5;reasons.push('目标方向');}
    let freshness=0; const age=Number.isFinite(opts.ageDays)?opts.ageDays:null; if(age!==null){freshness=age<=7?8:age<=30?5:age<=60?2:0;}
    const roleBoost=(s.recommendedRoles||[]).some(r=>lower.includes(norm(r)))?7:0;
    const score=Math.max(0,Math.min(99,Math.round(directionScore+skillScore+keywordScore+compatibility+freshness+roleBoost)));
    return {score,reasons:uniq(reasons).slice(0,5),hits:uniq([...skillHits,...keywordHits]).slice(0,10),direction:bestDir.name,components:{direction:directionScore,skills:skillScore,keywords:keywordScore,compatibility,freshness,roleBoost}};
  }
  function queryTerms(query){return norm(query).split(/[\s,，、/]+/).filter(Boolean);}
  function aliasesFor(query){
    const q=norm(query); const out=[q];
    for(const [name,aliases] of Object.entries(COMPANY_ALIASES)){if(norm(name)===q||aliases.some(a=>norm(a)===q)||norm(name).includes(q)){out.push(...aliases.map(norm));}}
    return uniq(out);
  }
  function searchMatch(job,query){
    const q=norm(query); if(!q)return {matched:true,exact:false,boost:0};
    const fields=[job.company,job.role,job.department,job.location,job.industry,job.jd,job.description,(job.tags||[]).join(' ')].map(norm);
    const hay=fields.join(' '); const terms=queryTerms(q);
    const matched=terms.every(t=>hay.includes(t)||aliasesFor(t).some(a=>hay.includes(a)));
    const company=norm(job.company); const exact=aliasesFor(q).some(a=>company===a||company.startsWith(a)||a.startsWith(company));
    const boost=exact?100:company.includes(q)?70:norm(job.role).includes(q)?50:matched?20:0;
    return {matched,exact,boost};
  }
  function filterAndRank(jobs,options={}){
    const {query='',profile=null,threshold=25,freshOnly=false,ageOf=()=>999,location='all',companyType='all',batch='all',sort='match',preferences={}}=options;
    const hasQuery=!!cleanText(query);
    let rows=(jobs||[]).map(job=>{const age=ageOf(job.updatedAt||job.updated_at);const match=scoreJob(job,profile,{targetLocations:preferences.targetLocations||[],targetDirections:preferences.targetDirections||[],ageDays:age});const search=searchMatch(job,query);return {...job,match,_age:age,_search:search};});
    rows=rows.filter(j=>(location==='all'||String(j.location||'').includes(location))&&(companyType==='all'||j.companyType===companyType||j.company_type===companyType)&&(batch==='all'||j.batch===batch));
    if(hasQuery) rows=rows.filter(j=>j._search.matched);
    else if(profile) rows=rows.filter(j=>(j.match.score??0)>=threshold);
    if(freshOnly&&!hasQuery&&rows.some(j=>Number.isFinite(j._age)&&j._age<999)) rows=rows.filter(j=>j._age<=30||j._age===999);
    if(hasQuery) rows.sort((a,b)=>b._search.boost-a._search.boost-(0)||((b.match.score??-1)-(a.match.score??-1))||String(b.updatedAt||'').localeCompare(String(a.updatedAt||'')));
    else if(sort==='match') rows.sort((a,b)=>(b.match.score??-1)-(a.match.score??-1)||String(b.updatedAt||'').localeCompare(String(a.updatedAt||'')));
    else if(sort==='fresh') rows.sort((a,b)=>String(b.updatedAt||'').localeCompare(String(a.updatedAt||'')));
    else if(sort==='company') rows.sort((a,b)=>String(a.company||'').localeCompare(String(b.company||''),'zh-CN'));
    return rows;
  }

  return {version:'4.0.0',DIRECTIONS,COMPANY_ALIASES,DEGREE_RANK,extractSignals,extractKeywords,buildProfile,scoreJob,searchMatch,filterAndRank,directionEvidence,cleanText,norm};
});
