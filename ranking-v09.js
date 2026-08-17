(function(){
  'use strict';
  if(!window.PTO_MATCHING)return;
  const CORE=window.PTO_MATCHING;
  const baseFilter=CORE.filterAndRank;

  const FIRST_TIER=new Set(['北京','上海','深圳','广州','杭州']);
  const CAMPUS=/(2027|27届|校招|校园招聘|应届|毕业生|new\s*grad|graduate|campus)/i;
  const INTERN=/(实习|intern)/i;
  const SENIOR=/(senior|staff|principal|资深|专家|负责人|总监|经理|主管|3-?5年|5年以上|[3-9]\s*年经验)/i;
  const SOCIAL=/(社招|社会招聘|experienced|off-campus)/i;
  const GENERIC_SKILLS=new Set(['python','c++','linux','git','docker','pytorch','transformer','llm','ai','算法','开发','系统','模型','深度学习']);
  const DEGREE_RANK={'大专':1,'专科':1,'本科':2,'学士':2,'硕士':3,'研究生':3,'博士':4,'phd':4,'master':3,'bachelor':2};
  const DIRECTION_TERMS={
    'AI Infra / 大模型推理系统':['ai infra','大模型推理','推理系统','推理引擎','llm serving','serving','vllm','sglang','pagedattention','kv cache','prefill','decode','continuous batching','speculative decoding','显存管理','调度器','分布式推理'],
    'CUDA / GPU 算子优化':['cuda','triton','cutlass','gemm','tensor core','算子优化','算子开发','gpu性能','kernel','warp','mma','wgmma','shared memory','访存优化'],
    'LLM / VLM 量化压缩':['ptq','qat','awq','gptq','smoothquant','量化','模型压缩','低比特','int4','int8','fp8','mxfp8','剪枝','calibration'],
    'VLM / VLA / 多模态':['vlm','vla','多模态','视觉语言','vision-language','具身智能','visual token','token pruning','qwen-vl','llava'],
    'AI 芯片软件 / 编译器':['ai芯片','芯片软件','npu','rpu','compiler','编译器','runtime','算子库','mlir','tvm','hxcc','图编译','后端编译'],
    'HPC / 分布式计算':['hpc','高性能计算','分布式','通信优化','并行计算','nccl','mpi','rdma','allreduce','tensor parallel','pipeline parallel','多机多卡'],
    '大模型 / NLP 算法':['大模型算法','llm算法','nlp','自然语言处理','预训练','sft','rlhf','dpo','强化学习','agent','rag'],
    '计算机视觉 / 多媒体算法':['计算机视觉','视觉算法','目标检测','yolo','opencv','detection','segmentation','ocr','slam','图像算法'],
    '后端 / 分布式系统':['后端','服务端','基础架构','分布式系统','云原生','java','golang','redis','mysql','kafka','kubernetes','高并发'],
    '嵌入式 / 机器人':['嵌入式','机器人','robotics','ros','ros2','jetson','orin','端侧部署','控制算法','rtos'],
    '芯片 / EDA / 硬件':['fpga','verilog','systemverilog','rtl','asic','eda','vivado','芯片设计','芯片验证','数字ic'],
    '金融 / 量化':['量化研究','量化开发','金融科技','quant','因子','回测','交易系统','金融工程'],
    '数据 / 推荐 / 搜索':['推荐算法','搜索算法','数据工程','数据科学','spark','flink','ranking','recall','数据挖掘'],
  };

  const norm=v=>String(v||'').toLowerCase().replace(/[‐‑‒–—]/g,'-').replace(/\s+/g,' ').trim();
  const uniq=a=>[...new Set(a.filter(Boolean))];
  function includesTerm(text,term){const t=norm(term);return t.length>=2&&text.includes(t);}
  function degreeRank(v){const s=norm(v);let r=0;for(const [k,n] of Object.entries(DEGREE_RANK))if(s.includes(k))r=Math.max(r,n);return r;}
  function sourceScore(job){
    const s=norm([job.sourceLabel,job.source,job.sourceUrl,job.applyUrl].join(' '));
    if(/direct-official|自主直连|招聘官网/.test(s))return {score:7,label:'企业官网直连'};
    if(/企业官方|官方招聘|官方 ats|feishu|beisen|zhiye\.com/.test(s))return {score:6,label:'企业官方招聘源'};
    if(/国资委|sasac|政府|官方公告/.test(s))return {score:4,label:'权威招聘公告'};
    if(/校园就业|高校就业|ncss/.test(s))return {score:3,label:'高校/国家就业平台'};
    return {score:1,label:'公开聚合来源'};
  }
  function freshnessScore(age){
    const n=Number(age);
    if(!Number.isFinite(n)||n>=999)return 0;
    if(n<=14)return 5;if(n<=30)return 4;if(n<=60)return 2.5;if(n<=120)return 1;return 0;
  }
  function directionScore(job,profile,preferences={}){
    const title=norm(job.role),body=norm([job.jd,job.department,job.industry].join(' '));
    const dirs=profile?.signals?.directionScores?.map(x=>x.name)||profile?.signals?.directions||[];
    const primary=profile?.signals?.primaryDirection||dirs[0]||'';
    const secondary=dirs.filter(x=>x&&x!==primary).slice(0,3);
    const primaryTerms=DIRECTION_TERMS[primary]||[];
    let titleHits=primaryTerms.filter(t=>includesTerm(title,t)).length;
    let bodyHits=primaryTerms.filter(t=>includesTerm(body,t)).length;
    const rolePhrases=(profile?.signals?.recommendedRoles||[]).filter(r=>norm(r).length>=3);
    const phraseHits=rolePhrases.filter(r=>includesTerm(title,r)).length;
    let secondaryHits=0;
    for(const d of secondary){const ts=DIRECTION_TERMS[d]||[];secondaryHits+=Math.min(2,ts.filter(t=>includesTerm(title,t)).length);}
    const targetDirs=preferences.targetDirections||[];
    const targetHit=targetDirs.some(d=>(DIRECTION_TERMS[d]||[]).some(t=>includesTerm(title+' '+body,t)));
    let score=Math.min(30,titleHits*5.2+Math.min(4,bodyHits)*2.1+Math.min(2,phraseHits)*4+Math.min(3,secondaryHits)*1.5+(targetHit?2:0));
    if(!titleHits&&!phraseHits&&bodyHits)score=Math.min(score,16);
    return {score,titleHits,bodyHits,phraseHits,label:titleHits||phraseHits?'岗位方向直接命中':bodyHits?'JD方向相关':''};
  }
  function skillScore(job,profile){
    const title=norm(job.role),body=norm([job.jd,job.department].join(' '));
    const skills=uniq(profile?.signals?.skills||[]).filter(x=>norm(x).length>=2).slice(0,36);
    let hitWeight=0,totalWeight=0,titleHits=[],bodyHits=[];
    for(const skill of skills){
      const k=norm(skill);const w=GENERIC_SKILLS.has(k)?0.45:(k.length>=8?1.35:k.length>=5?1.15:1);
      totalWeight+=w;
      if(title.includes(k)){hitWeight+=w*1.45;titleHits.push(skill);}
      else if(body.includes(k)){hitWeight+=w;bodyHits.push(skill);}
    }
    const denom=Math.max(6,Math.min(14,totalWeight));
    const coverage=Math.min(1,hitWeight/denom);
    const score=Math.min(24,24*Math.pow(coverage,0.92));
    return {score,coverage,titleHits:titleHits.slice(0,5),bodyHits:bodyHits.slice(0,6),hitCount:titleHits.length+bodyHits.length,label:titleHits.length?`标题技能 ${titleHits.slice(0,2).join(' · ')}`:bodyHits.length?`技能 ${bodyHits.slice(0,3).join(' · ')}`:''};
  }
  function careerScore(job,profile){
    const blob=norm([job.role,job.batch,job.graduation,job.jd].join(' '));
    const grad=profile?.signals?.graduationYear||'';
    let score=0,penalty=0,label='';
    if(CAMPUS.test(blob)){score+=8;label='校招 / 应届';}
    else if(INTERN.test(blob)){score+=5;label='实习';}
    else if(grad){score+=1;}
    if(SENIOR.test(blob)){penalty+=18;label='资深/经验要求冲突';}
    else if(SOCIAL.test(blob)&&!CAMPUS.test(blob)){penalty+=9;label='社会招聘';}
    if(grad&&blob.includes(grad)){score+=5;label=`${grad}届`;}
    return {score:Math.min(13,score),penalty,label,campus:CAMPUS.test(blob)||INTERN.test(blob)};
  }
  function locationScore(job,preferences={}){
    const loc=String(job.location||'');const targets=preferences.targetLocations||[];
    if(targets.length&&targets.some(x=>loc.includes(x)))return {score:10,label:'目标城市'};
    if(loc.includes('北京'))return {score:8,label:'北京'};
    const ft=[...FIRST_TIER].find(x=>loc.includes(x));if(ft)return {score:5,label:'一线/重点城市'};
    return {score:loc?2:0,label:''};
  }
  function eligibilityScore(job,profile){
    const wanted=degreeRank(job.education);const have=degreeRank(profile?.signals?.degree||'');
    let score=0,label='';
    if(wanted&&have){score+=have>=wanted?4:0;label=have>=wanted?'学历满足':'学历可能不满足';}
    else if(!wanted)score+=1.5;
    const grad=profile?.signals?.graduationYear||'';const jobGrad=String(job.graduation||'');
    if(grad&&jobGrad)score+=jobGrad.includes(grad)?4:0;
    else if(!jobGrad)score+=1;
    return {score:Math.min(8,score),label};
  }
  function completenessScore(job){
    const jd=String(job.jd||'').trim();const direct=!!(job.applyUrl||job.noticeUrl);let score=0;
    if(jd.length>=250)score+=2;else if(jd.length>=100)score+=1;
    if(direct)score+=1;
    return {score:Math.min(3,score),sparse:jd.length<90,direct};
  }

  function scoreJobV9(job,profile,opts={}){
    if(!profile)return {score:null,reasons:[],hits:[],components:{},calibration:'no-profile'};
    const direction=directionScore(job,profile,opts),skills=skillScore(job,profile),career=careerScore(job,profile),location=locationScore(job,opts),eligibility=eligibilityScore(job,profile),source=sourceScore(job),fresh=freshnessScore(opts.ageDays),complete=completenessScore(job);
    let penalty=career.penalty;
    if(direction.score<7&&skills.score<7)penalty+=12;
    if(complete.sparse)penalty+=4;
    if(!job.location)penalty+=2;
    let raw=direction.score+skills.score+career.score+location.score+eligibility.score+source.score+fresh+complete.score-penalty;
    let cap=99;
    if(direction.score<5&&skills.score<8)cap=Math.min(cap,50);
    else if(direction.score<10)cap=Math.min(cap,72);
    if((profile?.signals?.graduationYear||'')&&!career.campus)cap=Math.min(cap,84);
    if(source.score<=1)cap=Math.min(cap,88);
    if(complete.sparse)cap=Math.min(cap,86);
    const eliteGate=direction.score>=22&&skills.score>=14&&location.score>=8&&career.score>=8&&source.score>=6&&complete.score>=2;
    if(!eliteGate)cap=Math.min(cap,94);
    const perfectGate=eliteGate&&direction.score>=28&&skills.score>=20&&eligibility.score>=5&&fresh>=4;
    if(!perfectGate)cap=Math.min(cap,98);
    const score=Math.max(0,Math.min(cap,Math.round(raw*10)/10));
    const reasons=[];
    for(const x of [direction.label,skills.label,career.penalty?career.label:'',location.label,source.label])if(x)reasons.push(x);
    if(career.campus&&!career.penalty)reasons.push(career.label||'校招/实习');
    const components={
      direction:Math.round(direction.score*10)/10,skills:Math.round(skills.score*10)/10,career:career.score,
      location:location.score,eligibility:eligibility.score,source:source.score,freshness:fresh,completeness:complete.score,
      penalty,skillHits:skills.hitCount,titleDirectionHits:direction.titleHits,titleSkillHits:skills.titleHits.length,
      eliteGate,perfectGate,raw:Math.round(raw*10)/10,cap
    };
    return {score,reasons:uniq(reasons).slice(0,6),hits:uniq([...skills.titleHits,...skills.bodyHits]).slice(0,8),components,calibration:'v9-eight-dimension'};
  }

  function filterAndRankV9(jobs,options={}){
    const q=String(options.query||'').trim();
    const profile=options.profile||null;
    // Ask v0.7 only for retrieval/coarse preselection. Re-score every retained
    // row with the calibrated model before applying the user's threshold.
    let rows=baseFilter(jobs,{...options,threshold:0}).map(j=>{
      const age=Number.isFinite(j._age)?j._age:(options.ageOf?options.ageOf(j.updatedAt||j.updated_at):999);
      return {...j,match:scoreJobV9(j,profile,{...(options.preferences||{}),ageDays:age,targetLocations:options.preferences?.targetLocations||[],targetDirections:options.preferences?.targetDirections||[]})};
    });
    if(!q&&profile){
      const threshold=Number(options.threshold??25);
      rows=rows.filter(j=>(j.match.score??0)>=threshold);
    }
    if(options.sort==='fresh')rows.sort((a,b)=>String(b.updatedAt||'').localeCompare(String(a.updatedAt||''))||(b.match.score??0)-(a.match.score??0));
    else if(options.sort==='company')rows.sort((a,b)=>String(a.company||'').localeCompare(String(b.company||''),'zh-CN')||(b.match.score??0)-(a.match.score??0));
    else rows.sort((a,b)=>(b.match.score??-1)-(a.match.score??-1)||(b.match.components?.direction??0)-(a.match.components?.direction??0)||(b.match.components?.skills??0)-(a.match.components?.skills??0));
    return rows;
  }

  CORE.scoreJob=scoreJobV9;
  CORE.filterAndRank=filterAndRankV9;
  CORE.version='9.0.0';
})();
