import fs from 'node:fs';
import vm from 'node:vm';

globalThis.window=globalThis;
globalThis.state={preferences:{targetLocations:['北京'],targetDirections:['AI Infra / 大模型推理系统']},decisions:{}};
globalThis.document={querySelector:()=>null};
for(const file of ['matching-core.js','ranking-v06.js','ranking-v07.js','ranking-v09.js']){
  vm.runInThisContext(fs.readFileSync(file,'utf8'),{filename:file});
}
const M=globalThis.PTO_MATCHING;
const profile={signals:{
  primaryDirection:'AI Infra / 大模型推理系统',
  directions:['AI Infra / 大模型推理系统','CUDA / GPU 算子优化','HPC / 分布式计算','VLM / VLA / 多模态'],
  directionScores:[{name:'AI Infra / 大模型推理系统'},{name:'CUDA / GPU 算子优化'},{name:'HPC / 分布式计算'}],
  recommendedRoles:['AI Infra','大模型推理','推理系统','推理引擎','CUDA开发','算子开发'],
  skills:['vllm','pagedattention','kv cache','prefill','decode','continuous batching','nccl','cuda','triton','cutlass','gemm','tensor core','pytorch','python','linux'],
  degree:'硕士',graduationYear:'2027'
}};
const base={location:'北京',batch:'2027校园招聘',graduation:'2027届',education:'硕士',updatedAt:'2026-08-10',source:'direct-official:test',sourceLabel:'企业招聘官网',applyUrl:'https://example.com/apply'};
const jobs=[
  {...base,id:'a',company:'A',role:'大模型推理系统 / AI Infra 工程师',jd:'负责 vLLM PagedAttention KV Cache prefill decode continuous batching CUDA NCCL 推理引擎与显存管理优化。'},
  {...base,id:'b',company:'B',role:'CUDA 高性能算子工程师',jd:'负责 CUDA Triton CUTLASS GEMM Tensor Core kernel 性能优化，服务大模型推理。'},
  {...base,id:'c',company:'C',role:'大模型推理平台研发工程师',location:'上海',jd:'推理服务平台，vLLM KV Cache CUDA Python。'},
  {...base,id:'d',company:'D',role:'多模态大模型算法工程师',jd:'VLM 多模态视觉语言模型，包含推理部署与 CUDA 性能分析。'},
  {...base,id:'e',company:'E',role:'分布式系统研发工程师',location:'杭州',jd:'分布式系统 NCCL RDMA 高性能计算，Python C++。'},
  {...base,id:'f',company:'F',role:'后端开发工程师',location:'北京',jd:'Java Redis MySQL 微服务，也会使用 Python。'},
  {...base,id:'g',company:'G',role:'AI 产品经理',jd:'负责大模型产品规划、用户研究和商业化，不承担推理系统研发。'},
  {...base,id:'h',company:'H',role:'高级大模型平台专家',batch:'社会招聘',graduation:'',jd:'要求5年以上经验，负责大模型平台团队管理，了解 vLLM CUDA。'},
  {...base,id:'i',company:'I',role:'软件研发工程师',jd:'C++ Linux 软件开发。'},
  {...base,id:'j',company:'J',role:'市场运营',jd:'品牌营销、活动运营、用户增长。'},
  {...base,id:'k',company:'K',role:'推理工程师',source:'aggregator',sourceLabel:'公开聚合来源',applyUrl:'',jd:'vLLM。'},
  {...base,id:'l',company:'L',role:'大模型推理系统工程师',location:'南京',batch:'',graduation:'',source:'aggregator',sourceLabel:'公开聚合来源',applyUrl:'',jd:'vLLM CUDA KV Cache。'}
];
const scores=jobs.map(j=>({id:j.id,score:M.scoreJob(j,profile,{targetLocations:['北京'],targetDirections:['AI Infra / 大模型推理系统'],ageDays:7}).score}));
const by=Object.fromEntries(scores.map(x=>[x.id,x.score]));
console.log(JSON.stringify(scores,null,2));
if(!(by.a>by.b&&by.b>by.f&&by.f>by.j))throw new Error(`ordering regression ${JSON.stringify(by)}`);
if(!(by.a>by.c&&by.a>by.l))throw new Error('exact Beijing official campus role must outrank weaker variants');
if(!(by.h<by.c))throw new Error('senior/social conflict must be penalized');
if(new Set(scores.map(x=>x.score)).size<8)throw new Error('score distribution collapsed into too few distinct values');
if(scores.filter(x=>x.score>=95).length>2)throw new Error('95+ score inflation detected');
if(scores.filter(x=>x.score>=98).length>1)throw new Error('near-perfect score inflation detected');
for(const j of jobs){const m=M.scoreJob(j,profile,{targetLocations:['北京'],targetDirections:['AI Infra / 大模型推理系统'],ageDays:7});if(!m.components||m.calibration!=='v9-eight-dimension')throw new Error('missing v9 score explanation');}
console.log('Path to Offer v0.9 ranking calibration: PASS');
