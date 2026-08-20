import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {performance} from 'node:perf_hooks';

globalThis.window=globalThis;
globalThis.performance=performance;
globalThis.PTO_CONFIG={fullScoreLimit:5600};
for(const file of ['matching-core.js','career-taxonomy-v13.js','profile-core-v05.js','ranking-v09.js','ranking-v13.js','ranking-v14.js']){
  vm.runInThisContext(fs.readFileSync(file,'utf8'),{filename:file});
}
const CORE=globalThis.PTO_MATCHING;
const PROFILE=globalThis.PTO_PROFILE_V05;

function makeProfile(text,name='resume.txt'){
  const base=CORE.buildProfile(text,name);
  return PROFILE.enrichProfile(base,text,name,CORE);
}
function job(company,role,jd,{id,location='北京',batch='2027届校园招聘',graduation='2027届',education='本科及以上',sourceTier=7,updatedAt='2026-08-15'}={}){
  return {id:id||`${company}-${role}-${sourceTier}`,company,role,jd,location,batch,graduation,education,industry:'',sourceTier,sourceLabel:sourceTier>=6?'企业招聘官网 · 自主直连':'公开聚合来源',applyUrl:'https://example.com/job',updatedAt};
}
function score(j,p,locations=[]){return CORE.scoreJob(j,p,{ageDays:6,targetLocations:locations,targetDirections:[]});}

const materials=makeProfile(`材料科学与工程 硕士 2027届\n金属材料 材料表征 XRD SEM EBSD 热处理 相变 高熵合金 电化学 失效分析\n研究镍基合金微观组织与力学性能，完成热处理、XRD物相分析和SEM断口分析。\n材料研发实习，参与新能源材料配方、烧结工艺和可靠性验证。`,'materials.txt');
const materialsJob=job('宁德时代','材料研发工程师','负责新能源材料研发、材料表征、XRD SEM分析、烧结工艺优化、热处理与失效分析。');
const wrongVlm=job('某AI公司','VLM量化算法工程师','负责VLM多模态模型PTQ AWQ GPTQ低比特量化、vLLM推理和CUDA性能优化。');
const materialFit=score(materialsJob,materials);
const materialWrong=score(wrongVlm,materials);
assert.ok(materialFit.score>=90,{materialFit,materialWrong});
assert.ok(materialWrong.score<=45,{materialFit,materialWrong});
assert.ok(materialFit.score-materialWrong.score>=45,{materialFit,materialWrong});
assert.equal(materialWrong.components.domainMismatch,true);

const infra=makeProfile(`计算机科学 硕士 2027届\nC++ Python Linux CUDA NCCL RDMA vLLM SGLang Kubernetes\n负责大模型训练与推理基础设施，优化GPU集群调度、分布式训练、KV Cache、模型服务和高并发推理系统。\n机器学习平台研发，参与算力调度、训练框架和推理框架优化。`,'infra.txt');
const shopee=job('Shopee','（27届秋招）AI 基础设施研发工程师-北京','负责分布式训练与推理基础设施、GPU集群、算力调度、模型服务、CUDA、NCCL和高性能通信。');
const shopeeFit=score(shopee,infra);
assert.ok(shopeeFit.score>=90,shopeeFit);
assert.match(shopeeFit.band,/强烈推荐|高度匹配/);
assert.ok(shopeeFit.evidenceConfidence>=70,shopeeFit);

const accounting=makeProfile(`会计学 硕士 2027届\n财务会计 成本核算 财务报表分析 审计 税务 预算管理 CPA\n银行财务部实习，参与月度结账、预算执行分析、会计凭证复核和财务报表编制。`,'accounting.txt');
const accountingJob=job('中国建设银行','财务会计岗','负责财务核算、预算管理、财务报表分析、会计准则执行及税务管理。');
const accountingFit=score(accountingJob,accounting);
assert.ok(accountingFit.score>=88,accountingFit);

// Source quality changes Evidence Confidence, not candidate-job fit.
const official={...shopee,id:'same-role-official',sourceTier:7,sourceLabel:'企业招聘官网 · 自主直连'};
const aggregate={...shopee,id:'same-role-aggregate',sourceTier:1,sourceLabel:'公开聚合来源'};
const officialScore=score(official,infra),aggregateScore=score(aggregate,infra);
assert.ok(Math.abs(officialScore.score-aggregateScore.score)<=2,{officialScore,aggregateScore});
assert.ok(officialScore.evidenceConfidence-aggregateScore.evidenceConfidence>=20,{officialScore,aggregateScore});

// An explicit city preference is meaningful but cannot turn a wrong-city role
// into an apparently perfect recommendation.
const shanghai={...shopee,id:'shopee-shanghai',location:'上海',role:'（27届秋招）AI 基础设施研发工程师-上海'};
const wrongCity=score(shanghai,infra,['北京']);
assert.ok(wrongCity.score<=78,wrongCity);
const rightCity=score(shopee,infra,['北京']);
assert.ok(rightCity.score>=90,rightCity);

// Direct search is retrieval-first: all exact text matches survive even when
// a profile exists, while expensive detailed scoring is bounded.
const many=[];
for(let i=0;i<1800;i++)many.push(job(`企业${i}`,'平台研发工程师',`平台研发 Python C++ ${i}`,{id:`search-${i}`,location:i%2?'北京':'上海'}));
const searched=CORE.filterAndRank(many,{query:'平台研发工程师',profile:infra,threshold:95,freshOnly:true,ageOf:()=>5,location:'all',companyType:'all',batch:'all',sort:'match',preferences:{targetLocations:[],targetDirections:[]}});
assert.equal(searched.length,1800,'explicit search must not be cut by recommendation threshold');
assert.ok(searched.slice(0,1200).some(x=>x.match.score!==null),'top search results should retain explainable match scores');
assert.ok(searched.slice(1200).every(x=>x.match.score===null),'deep search tail must avoid expensive full scoring');

console.log(JSON.stringify({
  materials:[materialFit.score,materialWrong.score],
  shopee:[shopeeFit.score,shopeeFit.evidenceConfidence],
  accounting:accountingFit.score,
  sourceConfidence:[officialScore.evidenceConfidence,aggregateScore.evidenceConfidence],
  cities:[rightCity.score,wrongCity.score],
  searchCount:searched.length,
  searchMs:globalThis.PTO_RANKING_V14.lastMs
},null,2));
console.log('Path to Offer v1.4 score calibration: PASS');