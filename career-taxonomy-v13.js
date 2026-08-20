(function(root,factory){
  const api=factory(root.PTO_MATCHING);
  if(typeof module==='object'&&module.exports)module.exports=api;
  root.PTO_CAREER_V13=api;
})(typeof globalThis!=='undefined'?globalThis:this,function(BASE){
  'use strict';

  // Capture the pre-v1.3 implementation before installing our wrapper. Calling
  // BASE.buildProfile dynamically after the assignment below would recurse
  // forever and prevented every downstream resume regression from running.
  const BASE_BUILD_PROFILE=typeof BASE?.buildProfile==='function'?BASE.buildProfile.bind(BASE):null;
  const BASE_EXTRACT_SIGNALS=typeof BASE?.extractSignals==='function'?BASE.extractSignals.bind(BASE):null;

  const DOMAINS=[
    {id:'ai-infra',name:'AI Infra / 训练推理系统',roles:['AI基础设施研发工程师','AI基础架构工程师','训练/推理框架工程师','机器学习平台研发工程师','大模型系统研发工程师'],major:['计算机科学','软件工程','电子信息','人工智能'],terms:{'ai infra':9,'ai基础设施':10,'ai基础架构':10,'大模型推理':9,'训练框架':8,'推理框架':9,'vllm':9,'sglang':9,'megatron':7,'deepspeed':7,'cuda':5,'gpu集群':8,'gpu调度':8,'kubernetes':6,'kubeflow':7,'volcano':7,'ray':6,'rdma':7,'nccl':7,'分布式训练':8,'分布式推理':9,'高性能计算':6,'算力调度':8,'模型服务':7,'serving':7}},
    {id:'ai-algorithm',name:'AI / 机器学习 / 算法',roles:['算法工程师','机器学习工程师','大模型算法工程师','推荐算法工程师','计算机视觉算法工程师'],major:['人工智能','机器学习','计算机视觉','模式识别','数据科学','计算机科学'],terms:{'机器学习':8,'深度学习':8,'算法工程师':8,'大模型算法':9,'transformer':6,'pytorch':5,'tensorflow':4,'多模态':7,'计算机视觉':7,'自然语言处理':7,'推荐算法':7,'搜索算法':7,'aigc':6,'强化学习':7,'目标检测':6,'yolo':5,'llm':5,'nlp':5}},
    {id:'software-backend',name:'软件工程 / 后端 / 分布式系统',roles:['后端研发工程师','软件开发工程师','服务端研发工程师','基础架构工程师','云平台研发工程师'],major:['软件工程','计算机科学','计算机技术','网络工程','信息工程'],terms:{'后端':9,'服务端':9,'软件开发':7,'研发工程师':3,'java':5,'golang':6,'spring':5,'mysql':5,'redis':5,'kafka':5,'微服务':6,'分布式系统':7,'云原生':6,'高并发':6,'grpc':5,'数据库':4,'操作系统':4,'计算机网络':4}},
    {id:'frontend-client',name:'前端 / 客户端 / 移动开发',roles:['前端开发工程师','客户端开发工程师','Android开发工程师','iOS开发工程师','Web前端工程师'],major:['软件工程','计算机科学','数字媒体技术'],terms:{'前端':10,'javascript':7,'typescript':7,'react':7,'vue':7,'web开发':6,'android':8,'ios':8,'swift':7,'kotlin':7,'flutter':6,'客户端':8,'html':5,'css':5}},
    {id:'data',name:'数据 / 数据科学 / 搜索推荐',roles:['数据分析师','数据工程师','数据科学家','搜索算法工程师','推荐算法工程师'],major:['数据科学','统计学','大数据','信息管理','计算机科学'],terms:{'数据分析':9,'数据科学':9,'数据工程':8,'大数据':7,'sql':6,'spark':6,'flink':6,'hadoop':5,'数据仓库':6,'商业分析':6,'推荐':6,'搜索':5,'数据挖掘':7,'bi':5,'tableau':4}},
    {id:'sre-security',name:'测试 / SRE / 运维 / 网络安全',roles:['测试开发工程师','SRE工程师','运维研发工程师','安全研发工程师','网络安全工程师'],major:['网络空间安全','信息安全','计算机科学','软件工程'],terms:{'测试开发':9,'软件测试':7,'自动化测试':7,'sre':9,'devops':7,'运维':7,'可观测性':6,'网络安全':9,'信息安全':8,'渗透测试':7,'漏洞':6,'攻防':7,'prometheus':5,'grafana':5,'ci/cd':5}},
    {id:'chip-software',name:'AI芯片软件 / 编译器 / Runtime',roles:['AI芯片软件工程师','编译器开发工程师','Runtime研发工程师','算子开发工程师','NPU软件工程师'],major:['计算机科学','电子信息','微电子','集成电路','软件工程'],terms:{'ai芯片软件':10,'芯片软件':9,'编译器':9,'compiler':8,'runtime':8,'npu':8,'算子库':8,'算子开发':8,'mlir':8,'tvm':7,'图编译':7,'异构计算':7,'kernel':5,'cuda':5,'triton':6}},
    {id:'semiconductor',name:'半导体 / 集成电路 / EDA',roles:['数字IC设计工程师','模拟IC设计工程师','芯片验证工程师','工艺工程师','EDA研发工程师'],major:['微电子','集成电路','电子科学与技术','半导体','物理电子学'],terms:{'半导体':9,'集成电路':9,'数字ic':9,'模拟ic':9,'芯片设计':8,'芯片验证':8,'verilog':7,'systemverilog':7,'rtl':7,'asic':7,'eda':8,'版图':6,'流片':6,'晶圆':6,'工艺整合':7,'器件':5,'soc':5}},
    {id:'embedded-electronics',name:'嵌入式 / 电子 / 通信硬件',roles:['嵌入式软件工程师','硬件工程师','电子工程师','通信工程师','驱动开发工程师'],major:['电子信息','通信工程','自动化','测控技术','电子科学','电气工程'],terms:{'嵌入式':9,'stm32':7,'rtos':7,'单片机':7,'驱动开发':7,'pcb':6,'硬件设计':7,'电路设计':7,'模拟电路':6,'数字电路':6,'通信工程':7,'信号处理':6,'fpga':6,'arm':5,'传感器':5}},
    {id:'mechanical-automation',name:'机械 / 自动化 / 机器人 / 制造',roles:['机械工程师','结构工程师','自动化工程师','机器人工程师','制造工程师'],major:['机械工程','机械设计制造','自动化','机器人工程','机电一体化','工业工程'],terms:{'机械':8,'结构设计':8,'机械设计':8,'solidworks':7,'cad':6,'cae':5,'自动化':7,'机器人':7,'运动控制':6,'plc':6,'机电':6,'制造工程':7,'工艺工程':5,'产线':5,'可靠性':5,'有限元':6}},
    {id:'materials',name:'材料 / 新能源材料 / 工艺研发',roles:['材料研发工程师','材料工程师','工艺研发工程师','失效分析工程师','电池材料研发工程师'],major:['材料科学与工程','材料工程','金属材料','高分子材料','无机非金属材料','新能源材料','复合材料'],terms:{'材料科学':10,'材料工程':9,'金属材料':9,'高分子':8,'无机非金属':8,'复合材料':8,'新能源材料':8,'材料研发':9,'材料表征':8,'xrd':7,'sem':5,'tem':6,'ebsd':6,'热处理':7,'相变':6,'晶体':5,'合金':7,'陶瓷':6,'薄膜':6,'涂层':6,'失效分析':7,'锂电材料':8,'正极材料':8,'负极材料':8,'电化学':6,'粉体':5,'烧结':6}},
    {id:'chemistry',name:'化学 / 化工 / 分析检测',roles:['化学研发工程师','化工工程师','分析工程师','配方研发工程师','工艺研发工程师'],major:['化学','应用化学','化学工程','化学工程与工艺','分析化学','有机化学'],terms:{'化学':7,'化工':9,'有机合成':8,'无机化学':7,'分析化学':8,'催化':7,'反应工程':7,'化工原理':7,'色谱':6,'质谱':6,'hplc':7,'gc-ms':7,'配方':6,'精细化工':7,'聚合反应':6,'实验室':3}},
    {id:'energy-power',name:'能源 / 电气 / 电力 / 新能源',roles:['电气工程师','电力系统工程师','新能源工程师','储能工程师','热能工程师'],major:['电气工程','电力系统','能源与动力工程','新能源科学与工程','热能工程'],terms:{'电气工程':9,'电力系统':9,'电网':7,'继电保护':7,'高电压':7,'电力电子':7,'能源动力':8,'热力学':6,'热能':7,'新能源':6,'储能':7,'光伏':7,'风电':7,'电池系统':6,'bms':6}},
    {id:'civil',name:'土木 / 建筑工程 / 工程管理',roles:['土木工程师','结构工程师','施工工程师','工程管理岗','造价工程师'],major:['土木工程','工程管理','工程造价','道路桥梁','岩土工程','水利工程'],terms:{'土木工程':9,'结构工程':8,'岩土':8,'施工':6,'工程管理':7,'工程造价':8,'bim':7,'道路桥梁':8,'桥梁':6,'建筑工程':7,'水利工程':7,'测绘':5,'工程监理':6}},
    {id:'architecture',name:'建筑 / 城市规划 / 景观',roles:['建筑设计师','城市规划师','景观设计师','室内设计师'],major:['建筑学','城乡规划','城市规划','风景园林','景观设计'],terms:{'建筑学':9,'建筑设计':9,'城乡规划':9,'城市规划':8,'风景园林':8,'景观设计':8,'revit':6,'sketchup':6,'建筑方案':6,'室内设计':6}},
    {id:'environment',name:'环境 / 安全 / 可持续发展',roles:['环境工程师','环保工程师','EHS工程师','可持续发展专员','碳管理工程师'],major:['环境工程','环境科学','安全工程','资源与环境'],terms:{'环境工程':9,'环境科学':8,'环保':7,'水处理':7,'废水':6,'大气污染':6,'固废':6,'ehs':7,'安全工程':7,'碳排放':7,'碳中和':6,'可持续发展':6}},
    {id:'biotech-pharma',name:'生物 / 生物医药 / 制药',roles:['生物研发工程师','药物研发员','生物信息工程师','制剂研发工程师','临床前研究员'],major:['生物工程','生物技术','生物科学','药学','制药工程','生物医学工程'],terms:{'生物工程':9,'生物技术':8,'分子生物学':8,'细胞培养':7,'基因':6,'蛋白':6,'生物信息':7,'药学':8,'制药':8,'药物研发':8,'制剂':7,'药代':6,'药理':6,'发酵':6,'合成生物':7}},
    {id:'healthcare',name:'医学 / 临床 / 公共卫生',roles:['临床研究员','医学专员','公共卫生专员','医学事务','临床数据管理'],major:['临床医学','基础医学','公共卫生','预防医学','护理学','医学检验'],terms:{'临床医学':9,'临床研究':8,'医学':6,'公共卫生':8,'预防医学':8,'流行病学':7,'医学事务':7,'临床试验':8,'gcp':6,'护理':6,'医学检验':7}},
    {id:'math-physics',name:'数学 / 统计 / 物理 / 光学',roles:['数学建模工程师','统计分析师','物理研发工程师','光学工程师','仿真工程师'],major:['数学','应用数学','统计学','物理学','光学工程','光电信息'],terms:{'应用数学':9,'数学建模':7,'统计学':8,'概率论':6,'数值分析':6,'物理学':8,'光学':8,'光电':8,'激光':7,'光学设计':7,'zemax':7,'comsol':6,'仿真':5}},
    {id:'finance-accounting',name:'财务 / 会计 / 审计 / 税务',roles:['财务专员','会计','审计员','税务专员','财务分析师'],major:['会计学','财务管理','审计学','税务','财政学'],terms:{'会计':9,'财务管理':8,'财务分析':8,'审计':9,'税务':8,'成本核算':7,'财务报表':7,'会计准则':6,'cpa':7,'acca':6,'预算管理':6}},
    {id:'finance-investment',name:'金融 / 投资 / 证券 / 量化',roles:['投资分析师','行业研究员','量化研究员','金融科技岗','风险管理岗'],major:['金融学','金融工程','经济学','投资学','保险学'],terms:{'金融学':9,'金融工程':9,'投资':6,'证券':7,'投研':8,'行业研究':7,'量化研究':8,'因子':6,'回测':6,'资产管理':7,'风险管理':7,'估值':6,'宏观经济':6}},
    {id:'product-project',name:'产品 / 项目 / 用户研究',roles:['产品经理','策略产品经理','项目经理','技术产品经理','用户研究员'],major:['工业设计','信息管理','工商管理','心理学','计算机'],terms:{'产品经理':10,'策略产品':8,'技术产品':8,'产品设计':7,'产品规划':7,'用户研究':8,'需求分析':7,'竞品分析':6,'项目经理':8,'项目管理':7,'pjm':8,'tpm':8,'产品运营':5}},
    {id:'operations-supply',name:'运营 / 供应链 / 采购 / 物流',roles:['运营专员','供应链管理','采购工程师','物流规划','计划管理'],major:['供应链管理','物流管理','工业工程','工商管理','国际贸易'],terms:{'供应链':9,'采购':8,'物流':8,'仓储':7,'计划管理':7,'生产计划':7,'s&op':7,'运营':6,'商家运营':7,'内容运营':6,'用户运营':6,'跨境电商':5,'国际贸易':6}},
    {id:'marketing-sales',name:'市场 / 品牌 / 销售 / 商务',roles:['市场专员','品牌专员','销售工程师','商务拓展','客户经理'],major:['市场营销','广告学','国际商务','工商管理'],terms:{'市场营销':9,'品牌':7,'市场':5,'销售':7,'商务拓展':8,'bd':5,'客户经理':7,'渠道':6,'广告投放':6,'公关':6,'整合营销':6,'增长营销':6}},
    {id:'hr-admin',name:'人力资源 / 行政 / 组织发展',roles:['人力资源专员','招聘专员','HRBP','行政专员','组织发展专员'],major:['人力资源管理','劳动与社会保障','行政管理','工商管理'],terms:{'人力资源':9,'招聘':7,'hrbp':8,'人才发展':7,'组织发展':7,'绩效':6,'薪酬':6,'员工关系':6,'行政管理':7,'校园招聘':4}},
    {id:'legal',name:'法务 / 合规 / 知识产权',roles:['法务专员','合规专员','知识产权专员','律师助理','风控合规'],major:['法学','法律','知识产权'],terms:{'法学':9,'法律':7,'法务':9,'合规':8,'合同审查':7,'知识产权':8,'专利':6,'诉讼':6,'律师':7,'公司法':6,'劳动法':6,'监管':5}},
    {id:'consulting-strategy',name:'咨询 / 战略 / 商业研究',roles:['咨询顾问','战略分析师','商业分析师','行业研究员','管理培训生'],major:['工商管理','经济学','管理科学','公共管理'],terms:{'咨询':8,'战略':8,'商业分析':8,'行业研究':7,'管理咨询':9,'商业研究':7,'尽职调查':7,'市场研究':6,'战略规划':7,'管理培训生':6,'管培生':5}},
    {id:'design-creative',name:'设计 / 交互 / 视觉创意',roles:['UI设计师','UX设计师','视觉设计师','工业设计师','交互设计师'],major:['工业设计','视觉传达','艺术设计','交互设计','数字媒体艺术'],terms:{'视觉设计':9,'交互设计':9,'ui':6,'ux':7,'工业设计':8,'视觉传达':8,'平面设计':7,'figma':7,'photoshop':6,'illustrator':5,'用户体验':7,'动效':5}},
    {id:'media-content',name:'传媒 / 内容 / 新闻 / 公关',roles:['内容运营','编辑','记者','新媒体运营','公关传播'],major:['新闻学','传播学','广告学','广播电视','汉语言文学'],terms:{'新闻学':8,'传播学':8,'内容策划':7,'内容运营':7,'编辑':6,'记者':7,'新媒体':7,'公关传播':7,'短视频':6,'文案':6,'社交媒体':5}},
    {id:'education',name:'教育 / 教研 / 培训',roles:['教师','教研员','课程研发','培训专员','教育产品'],major:['教育学','学科教学','教育技术','心理学'],terms:{'教育学':9,'教师':8,'教学':7,'教研':8,'课程设计':7,'课程研发':7,'教育技术':7,'培训':5,'学习科学':6}},
    {id:'geo-petroleum',name:'地质 / 石油 / 矿业 / 测绘',roles:['地质工程师','油气工程师','采矿工程师','测绘工程师','勘探工程师'],major:['地质工程','地球物理','石油工程','矿业工程','采矿工程','测绘工程'],terms:{'地质':8,'地球物理':8,'石油工程':9,'油气':8,'钻井':7,'采油':7,'勘探':8,'采矿':8,'矿业':8,'测绘':8,'遥感':5,'gis':5}},
    {id:'agri-food',name:'农业 / 食品 / 生物育种',roles:['食品研发工程师','农业技术岗','育种研发','质量工程师','食品安全'],major:['食品科学','食品工程','农学','植物保护','动物科学','生物育种'],terms:{'食品科学':9,'食品工程':8,'食品研发':8,'食品安全':7,'农学':8,'农业':6,'育种':8,'种质':6,'植物保护':7,'动物科学':7,'发酵食品':6}},
    {id:'language-intl',name:'语言 / 翻译 / 国际业务',roles:['翻译','本地化专员','国际业务专员','海外运营','语言专家'],major:['英语','日语','德语','法语','翻译','外国语言文学'],terms:{'翻译':9,'英语专业':8,'日语':7,'德语':7,'法语':7,'本地化':8,'国际业务':7,'海外运营':6,'语言学':6,'口译':7,'笔译':7}},
    {id:'policy-social',name:'公共管理 / 社会科学 / 政策研究',roles:['政策研究员','公共事务','政府事务','社会研究员','公共管理岗'],major:['公共管理','行政管理','社会学','政治学','国际关系','公共政策'],terms:{'公共管理':9,'公共政策':8,'政策研究':8,'政府事务':8,'公共事务':7,'社会学':8,'政治学':7,'国际关系':7,'社会调查':6,'公共服务':6}},
  ];

  const DOMAIN_MAP=Object.fromEntries(DOMAINS.map(d=>[d.name,d]));
  const TECH_IDS=new Set(['ai-infra','ai-algorithm','software-backend','frontend-client','data','sre-security','chip-software','semiconductor','embedded-electronics']);
  const GENERIC=new Set(['python','matlab','c++','java','linux','office','excel','项目','研究','工程','研发','分析','设计','管理','技术','系统','模型','算法','实验']);
  const norm=v=>String(v||'').toLowerCase().replace(/[‐‑‒–—]/g,'-').replace(/\s+/g,' ').trim();
  const uniq=a=>[...new Set((a||[]).filter(Boolean))];
  function occurrences(text,term){let n=0,p=0,t=norm(term);if(!t)return 0;while((p=text.indexOf(t,p))>=0&&n<3){n++;p+=Math.max(1,t.length);}return n;}
  function majorWindow(text){
    const lines=String(text||'').split(/\n/).map(x=>x.trim()).filter(Boolean);
    return lines.filter(line=>/(专业|major|主修|学位|学院|系[:：]|硕士|本科|博士)/i.test(line)).slice(0,20).join(' ');
  }
  function scoreDomain(domain,text,{title='',majorText='',resume=false}={}){
    const body=norm(text),ttl=norm(title),major=norm(majorText);let score=0;const evidence=[];let anchors=0;
    for(const term of domain.major||[]){
      if(major.includes(norm(term))||body.includes(norm(term))){score+=resume?14:5;anchors++;evidence.push(term);}
    }
    for(const [term,w] of Object.entries(domain.terms||{})){
      const n=occurrences(body,term);if(!n)continue;
      let value=Number(w||1)*Math.min(2,n);
      if(ttl&&ttl.includes(norm(term)))value*=1.85;
      if(major&&major.includes(norm(term)))value*=1.55;
      score+=value;evidence.push(term);
      if(Number(w)>=7)anchors++;
    }
    return {id:domain.id,name:domain.name,score:Math.round(score*10)/10,evidence:uniq(evidence).slice(0,12),anchors,roles:domain.roles};
  }
  function classifyText(text,options={}){
    const major=options.majorText??(options.resume?majorWindow(text):'');
    const rows=DOMAINS.map(d=>scoreDomain(d,text,{...options,majorText:major})).filter(x=>x.score>0).sort((a,b)=>b.score-a.score);
    const top=rows[0],second=rows[1];
    const raw=top?.score||0,margin=Math.max(0,raw-(second?.score||0));
    let confidence=0;
    if(top){
      confidence=Math.round(Math.min(98,24+Math.min(42,raw*1.7)+Math.min(24,margin*1.7)+(top.anchors>=2?8:0)));
      if(raw<7)confidence=Math.min(confidence,42);
      if(margin<2)confidence=Math.min(confidence,58);
    }
    const scores=rows.slice(0,7).map((row,index)=>({
      name:row.name,rawScore:row.score,
      confidence:index===0?confidence:Math.max(18,Math.min(94,Math.round(confidence*(row.score/Math.max(1,raw))*0.94))),
      evidence:row.evidence,roles:row.roles,id:row.id,anchors:row.anchors,
    }));
    return {scores,primary:scores[0]||null,confidence,majorText:major};
  }
  function extractDomainSkills(text,result){
    const lower=norm(text),out=[];
    for(const row of result.scores.slice(0,4)){
      const d=DOMAIN_MAP[row.name];if(!d)continue;
      for(const [term,w] of Object.entries(d.terms||{}))if(Number(w)>=5&&lower.includes(norm(term))&&!GENERIC.has(norm(term)))out.push(term);
    }
    return uniq(out).sort((a,b)=>b.length-a.length).slice(0,64);
  }
  function buildSignals(rawText){
    const text=String(rawText||'');
    const result=classifyText(text,{resume:true});
    const old=BASE_EXTRACT_SIGNALS?BASE_EXTRACT_SIGNALS(text):{};
    const directions=result.scores.slice(0,5).map(x=>x.name);
    const roles=uniq(result.scores.slice(0,4).flatMap(x=>x.roles||[])).slice(0,18);
    const skills=uniq([...extractDomainSkills(text,result),...(old.skills||[])]).slice(0,72);
    const signals={...old,
      careerDomainScores:result.scores,
      careerDomains:directions,
      primaryCareerDomain:result.primary?.name||'',
      careerDomainConfidence:result.confidence,
      majorEvidence:result.majorText,
      directionScores:result.scores,
      directions,
      primaryDirection:result.primary?.name||'',
      recommendedRoles:roles,
      skills,
    };
    if(result.primary&&!TECH_IDS.has(result.primary.id))signals.technicalSubDirections=[];
    else signals.technicalSubDirections=(old.directionScores||[]).slice(0,4);
    return signals;
  }
  function buildProfile(rawText,fileName='resume'){
    const base=BASE_BUILD_PROFILE?BASE_BUILD_PROFILE(rawText,fileName):{name:String(fileName).replace(/\.[^.]+$/,''),fileName,rawText:String(rawText||''),signals:{}};
    return {...base,profileVersion:13,signals:buildSignals(rawText)};
  }
  function jobDomains(job){
    if(job&&job._ptoV13Domains)return job._ptoV13Domains;
    const title=String(job?.role||job?.title||'');
    const text=[title,job?.department,job?.industry,job?.jd,job?.description,(job?.tags||[]).join(' ')].join(' ');
    const result=classifyText(text,{title,resume:false});
    try{Object.defineProperty(job,'_ptoV13Domains',{value:result,writable:true,configurable:true});}catch(_){/* immutable test rows */}
    return result;
  }
  function profileDomains(profile){
    const rows=profile?.signals?.careerDomainScores||profile?.signals?.directionScores||[];
    return {scores:rows,primary:rows[0]||null,confidence:Number(profile?.signals?.careerDomainConfidence||rows[0]?.confidence||0)};
  }
  function termsFor(name){
    const d=DOMAIN_MAP[name];if(!d)return [];
    return uniq([...(d.major||[]),...Object.entries(d.terms||{}).filter(([,w])=>Number(w)>=5).map(([t])=>t)]);
  }
  function cheapAffinity(job,profile){
    const p=profileDomains(profile);if(!p.primary)return 0;
    const hay=norm([job.role,job.department,String(job.jd||'').slice(0,360)].join(' '));let score=0;
    p.scores.slice(0,3).forEach((row,index)=>{for(const term of termsFor(row.name).slice(0,22))if(hay.includes(norm(term)))score+=index===0?4:2;});
    const keywords=(profile?.signals?.skills||[]).slice(0,14);for(const k of keywords)if(norm(k).length>=3&&hay.includes(norm(k)))score+=1;
    if(/2027|27届|校招|校园招聘|应届|实习/i.test([job.role,job.batch,job.graduation].join(' ')))score+=2;
    return score;
  }

  if(BASE){
    BASE.extractSignals=buildSignals;
    BASE.buildProfile=buildProfile;
    BASE.CAREER_DOMAINS=DOMAINS;
  }
  return {version:'13.0.1',DOMAINS,DOMAIN_MAP,TECH_IDS,classifyText,buildSignals,buildProfile,jobDomains,profileDomains,termsFor,cheapAffinity,norm,uniq};
});
