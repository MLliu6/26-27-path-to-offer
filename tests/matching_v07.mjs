import fs from 'node:fs';
import vm from 'node:vm';

const sandbox={console,Date,Map,Set,Math,JSON,String,Number,Object,Array,RegExp};
sandbox.window=sandbox;sandbox.globalThis=sandbox;
vm.createContext(sandbox);
for(const file of ['matching-core.js','ranking-v06.js','matching-v07.js']){
  vm.runInContext(fs.readFileSync(new URL(`../${file}`,import.meta.url),'utf8'),sandbox,{filename:file});
}
const CORE=sandbox.PTO_MATCHING;
if(!CORE||CORE.version!=='7.0.0')throw new Error('v0.7 matching layer did not load');

const profile=CORE.buildProfile(`
2027届硕士，应聘 AI Infra / 大模型推理系统。
专业技能：C++ Python CUDA Triton vLLM SGLang NCCL。
实习经历：负责 LLM Serving、KV Cache、PagedAttention、prefill/decode、continuous batching、显存管理、通信优化与 GPU kernel profiling。
项目经历：CUDA GEMM、Tensor Core、模型推理性能优化。
`,'ai-infra.txt');
profile.id='p-ai';

function score(job,targets=['北京','上海','深圳','杭州','广州']){
  return CORE.scoreJob({
    company:'测试公司',department:'',location:'北京',batch:'2027校园招聘',education:'硕士',graduation:'2027届',updatedAt:'2026-08-17',
    sourceLabel:'公司官网 · 测试公司',applyUrl:'https://example.com/campus/job/1',jd:'',...job
  },profile,{targetLocations:targets,targetDirections:['AI Infra / 大模型推理系统'],ageDays:0});
}

const ideal=score({role:'大模型推理系统工程师',jd:'负责 vLLM / SGLang serving、KV Cache、CUDA kernel、NCCL 通信与显存优化。'});
const wrong=score({role:'AI 产品经理',jd:'与研发团队沟通 vLLM、CUDA、KV Cache 等大模型基础设施能力，负责产品规划和商业化。'});
const senior=score({role:'资深大模型推理架构师',jd:'8年以上经验，负责 vLLM CUDA 推理平台架构。'});
const foreign=score({role:'大模型推理系统工程师',location:'Singapore',jd:'vLLM CUDA KV Cache serving'});
const official=score({role:'CUDA算子优化工程师',jd:'CUDA Triton GEMM Tensor Core'});
const aggregator=score({role:'CUDA算子优化工程师',sourceLabel:'第三方岗位聚合',applyUrl:'https://example.com/job',jd:'CUDA Triton GEMM Tensor Core'});

if(ideal.score<55)throw new Error(`ideal Beijing AI Infra score too low: ${ideal.score}`);
if(wrong.score>18)throw new Error(`title-level product mismatch leaked through: ${wrong.score}`);
if(senior.score>32)throw new Error(`senior role not capped for graduate profile: ${senior.score}`);
if(foreign.score>28)throw new Error(`foreign-only role not capped: ${foreign.score}`);
// A perfect technical match can saturate at 99. Source trust is still an
// explicit ranking component and a cheap-priority tie breaker in experience-v07.
if(!official.sourceTrust?.official||official.sourceTrust.delta<=aggregator.sourceTrust.delta)throw new Error('company-official source trust did not beat aggregator');
if(CORE.classifyJob({role:'AI 产品经理',jd:'CUDA vLLM'}).primary!=='product')throw new Error('title-first family classifier regressed');
const bj=CORE.geoSignal({location:'北京市海淀区'},{targetLocations:['北京']});
const sg=CORE.geoSignal({location:'Singapore'},{targetLocations:['北京']});
if(!bj.beijing||!sg.foreign||bj.delta<=sg.delta)throw new Error('China/Beijing geo prior regressed');

console.log(JSON.stringify({pass:true,scores:{ideal:ideal.score,wrong:wrong.score,senior:senior.score,foreign:foreign.score,official:official.score,aggregator:aggregator.score},sourceTrust:{official:official.sourceTrust,aggregator:aggregator.sourceTrust},reasons:ideal.reasons},null,2));
