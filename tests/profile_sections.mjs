import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
const require=createRequire(import.meta.url);
const CORE=require('../matching-core.js');
const PROFILE=require('../profile-core-v05.js');

function profile(text,name='resume.txt'){
  const base=CORE.buildProfile(text,name);
  return PROFILE.enrichProfile(base,text,name,CORE);
}

const aiInfra=profile(`张三\n教育经历\n某大学 计算机科学 硕士 2027届\n课程：计算机视觉 数据挖掘 深度学习\n专业技能\nCUDA Triton vLLM NCCL PagedAttention KV Cache\n实习经历\n负责大模型推理服务，优化 prefill/decode、continuous batching 和显存管理\n项目经历\n实现 GEMM kernel 与 Tensor Core 算子优化`);
assert.equal(aiInfra.profileVersion,5);
assert.equal(aiInfra.signals.primaryDirection,'AI Infra / 大模型推理系统');
assert.ok(aiInfra.signals.sectionSummary.some(x=>x.name==='skills'));
assert.ok(aiInfra.signals.directionScores[0].evidence.some(x=>x.includes('专业技能')||x.includes('实习/工作')));

const quant=profile(`李四\n教育背景\n电子信息 硕士 2027届\n专业技能\nPTQ AWQ GPTQ INT4 W4A16 Hessian calibration\n科研经历\nVLM post-training quantization，视觉 token pruning，多模态模型压缩\n项目经历\n实现低比特量化算法并进行消融实验`);
assert.equal(quant.signals.primaryDirection,'LLM / VLM 量化压缩');
assert.ok(quant.signals.directions.includes('VLM / VLA / 多模态'));

const chip=profile(`王五\n教育经历\n微电子 本科\n专业技能\nSystemVerilog Verilog RTL FPGA Vivado\n项目经历\n完成 FPGA 流水线设计与时序优化\n获奖经历\n人工智能创新竞赛二等奖`);
assert.equal(chip.signals.primaryDirection,'芯片 / EDA / 硬件');

const split=PROFILE.splitSections(`教育经历\nA大学\n专业技能\nCUDA C++\n项目经历\nGEMM`);
assert.deepEqual(split.map(x=>x.name),['education','skills','projects']);

console.log('v0.5 section-aware profile tests passed');
