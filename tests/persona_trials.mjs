import { createRequire } from 'node:module';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const M=require('../matching-core.js');

const personas=[
  {id:'P01',label:'市场营销本科生',expect:'产品 / 运营 / 商业',resume:'2027届本科，市场营销。负责用户研究、产品运营、增长实验、竞品分析、品牌营销和数据分析，熟悉 Excel、SQL。'},
  {id:'P02',label:'后端开发本科生',expect:'后端 / 分布式系统',resume:'2027届本科计算机。Java、Go、Spring、Redis、MySQL、Kafka、gRPC、Docker、Kubernetes。做过高并发微服务与分布式系统。'},
  {id:'P03',label:'AI Infra硕士',expect:'AI Infra / 大模型推理系统',resume:'2027届硕士。LLM serving / 大模型推理系统；vLLM、PagedAttention、KV Cache、prefill/decode、continuous batching、NCCL、CUDA，做过显存管理与调度优化。'},
  {id:'P04',label:'VLM/PTQ硕士',expect:'LLM / VLM 量化压缩',resume:'硕士预计2027年毕业。VLM PTQ，AWQ、GPTQ、RTN、Hessian、W4A16、INT4、calibration；Qwen-VL视觉语言模型与visual token pruning。'},
  {id:'P05',label:'AI芯片编译器硕士',expect:'AI 芯片软件 / 编译器',resume:'2027届研究生。NPU/RPU芯片软件栈，MLIR、TVM、compiler、runtime、算子库、图编译、hxcc，负责后端编译和kernel适配。'},
  {id:'P06',label:'HPC博士',expect:'HPC / 分布式计算',resume:'博士。高性能计算、MPI、OpenMP、RDMA、NCCL、AllReduce、多机多卡、通信优化、并行计算、GPU cluster。'},
  {id:'P07',label:'机器人嵌入式候选人',expect:'嵌入式 / 机器人',resume:'2027届本科。ROS2、Jetson Orin、嵌入式Linux、STM32、RTOS、机器人、控制算法、雷达传感器和端侧部署。'},
  {id:'P08',label:'前端与产品混合型',expect:'前端 / 客户端',resume:'2027本科。TypeScript、React、Vue、Web前端工程；也做产品设计、用户研究和需求分析，负责前端性能和交互。'},
  {id:'P09',label:'金融量化候选人',expect:'金融 / 量化',resume:'金融工程硕士2027届。量化研究、因子挖掘、回测、交易系统、Python、C++、风险模型、期货和证券投研。'},
  {id:'P10',label:'芯片/EDA硬件候选人',expect:'芯片 / EDA / 硬件',resume:'2027届硕士。FPGA、Verilog、SystemVerilog、RTL、ASIC、EDA、Vivado、数字电路、芯片验证与SoC设计。'},
];

const report=[];
for(const p of personas){
  const profile=M.buildProfile(p.resume,`${p.id}.txt`);
  assert.ok(profile.signals.directions.length>0,`${p.id} should infer at least one direction`);
  assert.equal(profile.signals.primaryDirection,p.expect,`${p.id} primary direction`);
  assert.ok(profile.signals.recommendedRoles.length>0,`${p.id} recommended search roles`);
  report.push({id:p.id,label:p.label,primary:profile.signals.primaryDirection,confidence:profile.signals.directionScores[0]?.confidence||0,skills:profile.signals.skills.slice(0,4)});
}

// Regression for the user's concrete failure: a direct company query is a retrieval
// operation, not a recommendation operation. It must survive an impossible 95-point
// threshold and an old timestamp.
const infra=M.buildProfile(personas[2].resume,'infra.txt');
const jobs=[
  {id:'jd',company:'京东',role:'技术方向, AI Infra, 软件研发, 大模型',location:'北京 全国',industry:'互联网',graduation:'2027届',updatedAt:'2026-03-10',jd:'AI infra 大模型推理 CUDA 软件研发'},
  {id:'tx',company:'腾讯',role:'AI infra / 多模态 / 软件开发',location:'深圳',industry:'互联网',graduation:'2027届',updatedAt:'2026-08-15',jd:'AI infra 多模态 vLLM CUDA'},
  {id:'sales',company:'零售企业',role:'门店运营',location:'广州',industry:'零售',updatedAt:'2026-08-15',jd:'门店运营销售'},
];
const direct=M.filterAndRank(jobs,{query:'京东',profile:infra,threshold:95,freshOnly:true,ageOf:(d)=>d==='2026-03-10'?159:1,preferences:{}});
assert.equal(direct.length,1,'京东 direct search must return the cached 京东 row');
assert.equal(direct[0].company,'京东');
const alias=M.filterAndRank(jobs,{query:'JD',profile:infra,threshold:95,freshOnly:true,ageOf:()=>200,preferences:{}});
assert.equal(alias[0]?.company,'京东','JD alias should match 京东');

const recommendation=M.filterAndRank(jobs,{query:'',profile:infra,threshold:25,freshOnly:false,ageOf:()=>1,preferences:{targetDirections:['AI Infra / 大模型推理系统']}});
assert.ok(recommendation.length>=1,'resume-first recommendation should return relevant jobs');
assert.notEqual(recommendation[0].company,'零售企业','AI Infra evidence should rank above an unrelated operations role');
assert.ok(recommendation[0].match.reasons.length>0,'match must remain explainable');
const salesScore=M.scoreJob(jobs[2],infra,{ageDays:1}).score;
assert.ok(M.scoreJob(jobs[0],infra,{ageDays:1}).score>salesScore,'京东 AI Infra row should outscore unrelated retail operations');
assert.ok(M.scoreJob(jobs[1],infra,{ageDays:1}).score>salesScore,'腾讯 AI Infra row should outscore unrelated retail operations');

const noProfile=M.filterAndRank(jobs,{query:'京东',profile:null,threshold:95,freshOnly:true,ageOf:()=>999,preferences:{}});
assert.equal(noProfile.length,1,'search should work before resume upload');

console.log(JSON.stringify({pass:true,personas:report,regressions:{directCompanySearch:'PASS',companyAlias:'PASS',resumeRecommendation:'PASS',preResumeSearch:'PASS'}},null,2));
