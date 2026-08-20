import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';

globalThis.window=globalThis;
for(const file of ['matching-core.js','career-taxonomy-v13.js','profile-core-v05.js','ranking-v09.js','ranking-v13.js']){
  vm.runInThisContext(fs.readFileSync(file,'utf8'),{filename:file});
}
const CORE=globalThis.PTO_MATCHING;
const PROFILE=globalThis.PTO_PROFILE_V05;

function makeProfile(text,name='resume.txt'){
  const base=CORE.buildProfile(text,name);
  const enriched=PROFILE.enrichProfile(base,text,name,CORE);
  return enriched;
}
function job(company,role,jd,{location='北京',batch='2027届校园招聘',graduation='2027届',education='本科及以上',department='',sourceTier=7}={}){
  return {id:`${company}-${role}`,company,role,jd,location,batch,graduation,education,department,industry:'',sourceTier,sourceLabel:'企业招聘官网 · 自主直连',applyUrl:'https://example.com/job'};
}
function score(j,p,locations=[]){return CORE.scoreJob(j,p,{ageDays:8,targetLocations:locations,targetDirections:[]});}
function assertDomainCase({profile,pattern,matched,wrong=shopee,minGap=15,label}){
  assert.match(profile.signals.primaryDirection,pattern,`${label} resume classified into wrong career domain`);
  const right=score(matched,profile);
  const off=score(wrong,profile);
  assert.ok(right.score-off.score>=minGap,{label,right,off,primary:profile.signals.primaryDirection,directions:profile.signals.directionScores.slice(0,4)});
  assert.equal(right.components.domainMismatch,false,`${label} matched role must not be domain-mismatched`);
  return {right,off};
}

const materials=makeProfile(`
教育背景
材料科学与工程 硕士 2027届
专业技能
熟悉金属材料、材料表征、XRD、SEM、EBSD、热处理、相变与高熵合金；掌握电化学测试与失效分析。
科研经历
研究镍基合金微观组织与力学性能，完成热处理实验、XRD物相分析和SEM断口分析。
实习经历
材料研发实习生，参与新能源材料配方、烧结工艺和可靠性验证。
`,'materials-2027.txt');
assert.match(materials.signals.primaryDirection,/材料/,'materials resume must classify as materials');
assert.ok(materials.signals.directionScores.slice(0,3).every(x=>!/VLM|量化|AI Infra/.test(x.name)),materials.signals.directionScores.slice(0,3));

const materialsJob=job('宁德时代','材料研发工程师','负责新能源材料研发、材料表征、XRD/SEM分析、烧结工艺优化与失效分析。');
const vlmJob=job('某AI公司','VLM量化算法工程师','负责VLM多模态模型PTQ、AWQ、GPTQ、低比特量化、vLLM推理和CUDA性能优化。');
const materialScore=score(materialsJob,materials);
const wrongTechScore=score(vlmJob,materials);
assert.ok(materialScore.score>=60,{materialScore,wrongTechScore});
assert.ok(materialScore.score-wrongTechScore.score>=25,{materialScore,wrongTechScore});
assert.equal(wrongTechScore.components.domainMismatch,true,'clear materials-vs-VLM mismatch must be explicit');
assert.ok(wrongTechScore.components.cap<=48,wrongTechScore.components);

const infra=makeProfile(`
教育背景
计算机科学 硕士 2027届
专业技能
C++ Python Linux CUDA NCCL RDMA vLLM SGLang Kubernetes
项目经历
负责大模型训练与推理基础设施，优化GPU集群调度、分布式训练、KV Cache、模型服务和高并发推理系统。
实习经历
机器学习平台研发，参与算力调度、训练框架和推理框架优化。
`,'infra-2027.txt');
assert.match(infra.signals.primaryDirection,/AI Infra|训练推理系统/);
const shopee=job('Shopee（深圳虾皮信息科技有限公司）','（27届秋招）AI 基础设施研发工程师-北京','Shopee AI平台团队负责分布式训练与推理基础设施、GPU集群、算力调度、模型服务、CUDA与高性能通信。',{department:'Shopee CNDC'});
const shopeeScore=score(shopee,infra);
const infraToMaterial=score(materialsJob,infra);
assert.ok(shopeeScore.score-infraToMaterial.score>=20,{shopeeScore,infraToMaterial});
assert.equal(shopeeScore.components.domainMismatch,false);

const product=makeProfile(`
教育背景
工商管理 硕士 2027届
实习经历
互联网产品经理实习，负责用户研究、需求分析、产品规划、竞品分析和版本迭代，协同研发与设计完成上线。
项目经历
完成跨境电商用户增长产品设计与A/B测试，输出PRD和数据复盘。
`,'product-2027.txt');
assert.match(product.signals.primaryDirection,/产品/);
const productJob=job('Shopee','（27届秋招）产品经理-深圳','负责跨境电商产品规划、用户研究、需求分析、竞品分析、产品设计与版本迭代。',{location:'深圳'});
const productScore=score(productJob,product);
const productToAi=score(shopee,product);
assert.ok(productScore.score-productToAi.score>=20,{productScore,productToAi});

// Universal-platform gates: these profiles deliberately contain no AI terms.
// A future change must not regress them toward the site's original tech-user
// bias merely because the catalogue contains many software/AI positions.
const accounting=makeProfile(`
教育背景
会计学 硕士 2027届
专业技能
财务会计、成本核算、财务报表分析、审计、税务、预算管理，已通过CPA部分科目。
实习经历
银行财务部实习，参与月度结账、预算执行分析、会计凭证复核和财务报表编制。
`,'accounting-2027.txt');
const accountingJob=job('中国建设银行','财务会计岗','负责财务核算、预算管理、财务报表分析、会计准则执行及税务管理。');
const accountingCase=assertDomainCase({profile:accounting,pattern:/财务|会计|审计/,matched:accountingJob,minGap:18,label:'accounting'});

const civil=makeProfile(`
教育背景
土木工程 硕士 2027届
专业技能
结构工程、有限元、BIM、施工组织、工程管理、道路桥梁与岩土工程基础。
项目经历
完成钢筋混凝土结构设计与有限元分析，参与桥梁施工方案和工程量计算。
`,'civil-2027.txt');
const civilJob=job('中国交通建设集团','土木工程师','负责道路桥梁结构工程设计、BIM建模、施工技术与工程管理。');
const civilCase=assertDomainCase({profile:civil,pattern:/土木|建筑工程|工程管理/,matched:civilJob,minGap:18,label:'civil'});

const biotech=makeProfile(`
教育背景
生物工程 硕士 2027届
专业技能
分子生物学、细胞培养、蛋白表达纯化、发酵工程、合成生物学和药物研发实验。
科研经历
开展重组蛋白表达、细胞实验和发酵条件优化，完成实验设计与数据分析。
`,'biotech-2027.txt');
const biotechJob=job('中国医药集团','生物研发工程师','负责分子生物学、细胞培养、蛋白表达、发酵和生物药研发实验。');
const biotechCase=assertDomainCase({profile:biotech,pattern:/生物|制药/,matched:biotechJob,minGap:18,label:'biotech'});

const legal=makeProfile(`
教育背景
法学 硕士 2027届
专业技能
公司法、劳动法、合同审查、知识产权、合规管理、法律检索与诉讼实务。
实习经历
企业法务实习，参与合同审核、合规制度梳理、知识产权事务和法律风险分析。
`,'legal-2027.txt');
const legalJob=job('中国银行','法务合规岗','负责合同审查、公司法务、监管合规、法律风险管理和知识产权事务。');
const legalCase=assertDomainCase({profile:legal,pattern:/法务|合规|知识产权/,matched:legalJob,minGap:18,label:'legal'});

const noLocation=score(shopee,infra,[]);
assert.equal(noLocation.components.location,0,'leaving location unconstrained must not silently boost Beijing');
const beijing=score(shopee,infra,['北京']);
assert.equal(beijing.components.location,10,'explicit user location preference should still count');
assert.ok(beijing.score>=noLocation.score);

console.log(JSON.stringify({
  materialsPrimary:materials.signals.primaryDirection,
  materialsJob:materialScore.score,
  materialsVsVlm:wrongTechScore.score,
  infraPrimary:infra.signals.primaryDirection,
  shopee:shopeeScore.score,
  productPrimary:product.signals.primaryDirection,
  product:productScore.score,
  productVsAi:productToAi.score,
  accounting:[accounting.signals.primaryDirection,accountingCase.right.score,accountingCase.off.score],
  civil:[civil.signals.primaryDirection,civilCase.right.score,civilCase.off.score],
  biotech:[biotech.signals.primaryDirection,biotechCase.right.score,biotechCase.off.score],
  legal:[legal.signals.primaryDirection,legalCase.right.score,legalCase.off.score],
},null,2));
console.log('Path to Offer v1.3 general resume matching: PASS');
