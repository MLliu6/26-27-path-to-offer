import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
globalThis.window=globalThis;
for(const file of ['matching-core.js','career-taxonomy-v13.js','profile-core-v05.js','ranking-v13.js','ranking-v14.js'])vm.runInThisContext(fs.readFileSync(file,'utf8'),{filename:file});
const M=PTO_MATCHING;
const profile=text=>{
  const p=PTO_PROFILE_V05.enrichProfile(M.buildProfile(text,'synthetic.txt'),text,'synthetic.txt',M);
  p.signals.careerDomainScores=p.signals.directionScores;return p;
};
const infra=profile('教育经历\n计算机科学 硕士 2027届\n专业技能\nPython PyTorch CUDA vLLM NCCL\n项目经历\n大模型推理框架开发、机器学习、深度学习、多模态算法和分布式训练。担任推理优化工程师。');
const backend=profile('教育经历\n软件工程 本科 2027届\n专业技能\nJava Spring MySQL Redis Kafka Docker\n项目经历\n完成后端开发、微服务、分布式系统、高并发系统和数据库设计。');
const mechanical=profile('教育经历\n机械工程 硕士 2027届\n专业技能\nSolidWorks CAD CAE 有限元 结构设计\n科研经历\n完成机器人结构设计、机械仿真、可靠性研究与制造工艺优化。');
const biology=profile('教育经历\n生物工程 硕士 2027届\n专业技能\n细胞培养 PCR 蛋白纯化 药物研发 GMP\n科研经历\n生物医药研发、细胞实验、蛋白表达、发酵工程和药物筛选实验。');
// Public-record snapshots from jobs_cn / jobs_supplemental on 2026-10-28.
const base={batch:'2027校园招聘',graduation:'2027届',education:'本科',sourceTier:7,location:'上海',applyUrl:'https://example.com/job',updatedAt:'2026-10-28'};
const minimax={...base,id:'d10da6a06ff1b63bcb',role:'大模型算法工程师-2028届实习',company:'MiniMax',jd:'LLM / MLLM 预训练、后训练、对齐和多模态；计算机、人工智能、数学、电子信息等相关专业在读，学历不限；熟悉机器学习 / 深度学习基础，熟练使用 Python、PyTorch。'};
assert.deepEqual(M.jobCohort(minimax),{years:['2028'],source:'title',conflict:true});
assert.deepEqual(M.jobCohort({r:'27届实习生',g:'2027届'}).years,['2027']);
assert.deepEqual(M.jobCohort({role:'研发工程师',jd:'面向2026-2027届毕业生'}).years,['2026','2027']);
const miniScore=M.scoreJob(minimax,infra,{ageDays:1});assert.ok(miniScore.score<=35,miniScore);
assert.ok(!miniScore.reasons.some(x=>x==='2027届符合'));
assert.ok(!infra.signals.skills.includes('化工'),'优化工程师 must not emit 化工');
assert.equal(PTO_CAREER_V13.occurrences('推理优化工程师','化工'),0);
assert.equal(PTO_CAREER_V13.occurrences('化工工程师与化学工程','化工'),1);
assert.equal(PTO_CAREER_V13.occurrences('javascript systems business','java'),0);
const packaging={...base,id:'03949f9627ab2f043b46',company:'思朗科技',role:'2027校招-封装工程师（先进封装设计开发方向）-上海',jd:'负责公司芯片产品的封装方案选型、封装结构设计、先进封装设计开发；与前后端协作完成网表、bump location 等封装设计输入件；与前后端、SIPI、系统团队完成封装结构和封装设计的优化。硕士及以上学历，微电子、电子封装、材料等相关专业；熟悉 APD、innovus、virtuoso、3DICC、UCIe/HBM/DDR/SERDES/PCIe。'};
const packageScore=M.scoreJob(packaging,backend,{ageDays:1});
assert.ok(packageScore.score<=50,packageScore);assert.match(packageScore.components.jobDomain,/半导体/);assert.equal(packageScore.components.domainExact,false);
const operation={...base,id:'23b1efd7b6d23dae2b',company:'中创新航科技（武汉）有限公司',role:'自动换设备操作员+27届实习生',education:'专科及以上',jd:'专业：计算机 机械 电气 工业机器人 新能源；学历：专科及以上；招聘人数：200；企业规模：5000以上'};
const operationScore=M.scoreJob(operation,mechanical,{ageDays:1});assert.ok(operationScore.score<=68,operationScore);assert.match(operationScore.components.roleGap,/生产操作/);
const computation={...base,id:'b99fe3d95e933f0e6147',company:'思朗科技',role:'2027校招-计算生物学研究员（北京/上海）',education:'',jd:'设计、执行并分析生物大分子分子动力学模拟；使用 GROMACS、AMBER、NAMD、CADD 分子模拟方法。学历：计算化学、计算生物学、生物物理学、结构生物学、药物化学或相关专业博士学历。熟悉Linux操作系统，具备良好的编程能力（Python/Shell等）。参与药物研发、药物筛选与优化，参与生物医药项目。'};
const computationScore=M.scoreJob(computation,biology,{ageDays:1});assert.ok(computationScore.score<=62,computationScore);assert.ok(computationScore.reasons.some(x=>/学历可能不满足/.test(x)));assert.match(computationScore.components.roleGap,/计算/);
const manufacturing={...base,id:'4fa2255c49efc9b918',company:'南通康源电路科技有限公司',role:'智能制造工程师',jd:'协助智能制造项目规划、智能生产线搭建、工业互联网平台对接；PLC编程、MES系统运维；负责项目数据的收集、整理与分析；优化生产流程。2027届本科及以上学历，智能制造工程、自动化、软件开发等相关专业。'};
const manufacturingScore=M.scoreJob(manufacturing,biology,{ageDays:1});assert.ok(manufacturingScore.score<=50,manufacturingScore);assert.equal(manufacturingScore.components.domainExact,false);
for(const role of ['校园招聘首页','招聘首页','2027届秋季校园招聘活动邀请函','校园宣讲会','职位列表']){
  const item={...base,id:role,role,jd:'面向计算机、生物、化学、机械、Java、Python方向人才'};
  assert.equal(M.isPosition(item),false);
  const score=M.scoreJob(item,infra);assert.equal(score.score,null);assert.equal(score.evidenceConfidence,0);
}
assert.equal(M.isPosition({...base,role:'校园招聘-Java后端开发工程师'}),true);
const bioStrong=M.scoreJob({...base,id:'bio-match',role:'生物医药研发工程师',jd:'负责细胞培养、蛋白表达纯化、药物筛选、发酵工程、GMP及生物医药研发实验。'},biology,{ageDays:1});
assert.ok(bioStrong.score>=85,bioStrong);
// Second independent review: role function must survive company-sector and
// neighbouring-listing contamination, rather than patching company names.
const morimatsu={...base,id:'b26f25162314eec1c5',company:'上海森松制药设备工程有限公司',role:'上海森松制药设备工程有限公司2027校园招聘 学生活动中心420',jd:'校园宣讲与各学院专业介绍。生物医药研发人才招聘。'};
assert.equal(M.isPosition(morimatsu),false);assert.equal(M.scoreJob(morimatsu,biology).score,null);
const salesCases=['BBU县域-医药推广实习生-阜阳','医药信息沟通实习生-肿瘤-上海','BBU影像自免—销售实习生-扬州（可留用）','BBU影像自免-销售管培生-长沙 27届'];
for(const role of salesCases){
  const item={...base,id:role,company:'恒瑞医药',role,industry:'生物医药研发',jd:'向客户提供药品信息，反馈临床使用情况，拜访客户与推广品牌。2027届医药、药学、市场营销专业。生物医药研发、药物研发、蛋白、细胞。'};
  const score=M.scoreJob(item,biology,{ageDays:1});assert.ok(score.score<=50,{role,score});assert.match(score.components.jobDomain,/营销|销售/);
}
const directory='（2027秋招）SoC验证工程师 校招类 上海市 （2027秋招）Web后端工程师 校招类 北京市 软件开发 Java Spring MySQL 其他职位 查看更多职位';
for(const role of ['（2027秋招）SoC验证工程师','（2027秋招）IC数字设计工程师','（2027秋招）IP采购工程师']){
  const item={...base,id:role,company:'进迭时空',role,applyUrl:'https://app.mokahr.com/campus-recruitment/space-t1/67916#/jobs/',jd:directory};
  assert.equal(M.isPosition(item),false);assert.equal(M.scoreJob(item,backend).score,null);
  const detail={...item,id:role+'-detail',applyUrl:'https://example.com/job/123',jd:('Java 后端 软件开发 MySQL 数据库 生物医药研发 '.repeat(15))+'真实岗位职责'};
  const score=M.scoreJob(detail,backend,{ageDays:1});assert.ok(score.score<=50,{role,score});
  assert.equal(score.components.domainExact,false);
  assert.match(score.components.jobDomain,role.includes('采购')?/供应链|采购/:/半导体/);
}
const hydraulic=M.scoreJob({...base,id:'hydraulic',company:'博世',role:'液压研发（减速器）',jd:'负责液压、机械、减速器结构设计。公司有软件开发、后端开发业务。'},backend,{ageDays:1});assert.ok(hydraulic.score<=50,hydraulic);
const senior=M.scoreJob({...base,id:'senior',role:'算力平台研发工程师',jd:'要求5年以上开发经验，负责大模型推理框架、CUDA vLLM NCCL 分布式训练和机器学习平台。'},infra,{ageDays:1});assert.ok(senior.score<=62,senior);assert.equal(senior.components.experienceConflict,true);
assert.equal(PTO_CAREER_V13.occurrences('public','ic'),0);assert.equal(PTO_CAREER_V13.occurrences('linux','ux'),0);
assert.notEqual(PTO_CAREER_V13.titleFunction('Public设计专员'),'semiconductor');
assert.equal(PTO_CAREER_V13.titleFunction('SoC验证工程师'),'semiconductor');
assert.equal(PTO_CAREER_V13.titleFunction('CPU软件设计工程师'),'chip-software');
assert.equal(PTO_CAREER_V13.titleFunction('半导体销售工程师'),'marketing-sales');
assert.equal(PTO_CAREER_V13.titleFunction('医药采购工程师'),'operations-supply');
const backendStrong=M.scoreJob({...base,id:'backend-match',role:'Java后端开发工程师',jd:'Java Spring MySQL Redis Kafka Docker 后端开发、微服务、分布式系统、高并发系统和数据库设计。'},backend,{ageDays:1});assert.ok(backendStrong.score>=85,backendStrong);
console.log(JSON.stringify({wrongCohort:miniScore.score,backendToPackaging:packageScore.score,mechanicalToOperator:operationScore.score,biologyToComputational:computationScore.score,biologyToManufacturing:manufacturingScore.score,biologyToResearch:bioStrong.score}));
console.log(JSON.stringify({biomedicalSales:'<=50',directoryRecords:'unscored',hardwareAndProcurement:'<=50',backendToHydraulic:hydraulic.score,seniorForGraduate:senior.score,backendPositive:backendStrong.score}));
console.log('Adversarial job matching v1.6: PASS');

const genericResearch=M.scoreJob({...base,id:'generic-research',role:'研发工程师2',jd:'2027届本科，化学、材料、电子、机械等专业。负责产品研发和实验，材料性能分析与设计。'},backend,{ageDays:1});
assert.ok(genericResearch.score<=62,genericResearch);
assert.equal(genericResearch.components.domainExact,false);
