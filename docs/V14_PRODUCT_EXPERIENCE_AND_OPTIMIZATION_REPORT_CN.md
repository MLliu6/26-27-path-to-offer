# Path to Offer v1.4 产品体验审计与优化报告

日期：2026-08-21

## 一、对标对象与结论

本轮不是按“功能数量”比较，而是按候选人完成一次求职决策所需要的链路比较：发现岗位 → 判断是否值得投 → 验证来源 → 打开投递 → 进入跟踪 → 用结果反哺下一轮推荐。

重点参考：

- Simplify：以一个候选人 Profile 贯穿 Job Matches、Resume Tailoring、Copilot Autofill 与 Job Tracker；推荐结果支持 Why This Job is a Match、保存、隐藏、Already Applied 等反馈，且明确把 ATS 兼容和应用跟踪做成一个闭环。参考：https://help.simplify.jobs/articles/2166608-using-your-job-matches 、https://help.simplify.jobs/en/articles/2415391-using-copilot-to-autofill-applications
- Jobright：产品层强调对每个职位给出 0–100 类的 Fit Score，并将“找职位、匹配、定制简历、内推、投递”串成单一流程。其公开对比页可作为用户心智参考，而不是算法真值。参考：https://jobright.ai/compare/simplify
- CareerPulse：自托管、多源抓取、0–100 AI 匹配、match reasons / concerns / skill gaps，抓取层包含指数退避、域名限流和直接申请链接提取。参考：https://github.com/tcpsyn/CareerPulse
- JobSync：把 Application Tracker、Resume Management、AI Job Match、Task/Activity 与 Analytics 放在同一工作台，强调本地/自托管隐私。参考：https://github.com/Gsync/jobsync
- JobOps：强调批量搜索、Watchlists、保存 JD、防止岗位消失、可选 AI、人工决定是否投递；社区反馈表明“可靠发现 + 不替用户做最终决定”是一条有吸引力的产品路线。参考：https://github.com/DaKheera47/job-ops
- 近期 vibe-coded / local-first 项目：普遍在补多职业 lane、本地隐私、可解释评分、ATS 直链、自动跟踪和来源鲁棒性，而不再满足于“一个爬虫 + 一个卡片列表”。参考：https://github.com/humancto/mr-jobs 、https://github.com/maddykws/AI-Powered-Job-Search-Tool

核心结论：Path to Offer 的差异化方向是正确的——国内 2027 秋招、官网/ATS/央国企信源、本地简历画像、真实投递流程——但 v1.3 的体验仍更像“功能叠加后的工程控制台”，而不是一个稳定、可信、能连续使用数月的候选人操作系统。

## 二、v1.3 体验审计

### P0-1：Match 分数语义错误，导致用户不信任

v1.3 将职业方向、技能、届别、城市、学历、来源可信度、新鲜度、JD 完整度直接相加。这个做法把两类不同问题混在一起：

1. “我和岗位是否适合”（candidate-job fit）；
2. “这条岗位信息是否值得相信”（evidence confidence）。

因此，一个实际上很适合的岗位会因为城市未设置、JD 较短、发布时间未知或来源层级不同被压到 40–60 分。用户看到的是“我明明很适合却只有 47 分”，系统失去可解释性。

v1.4 必须把两者拆开：

- Match Score：只描述候选人与岗位的适配程度，0–100；
- Evidence Confidence：描述信源、时效、JD 完整度、岗位领域识别置信度，0–100；
- 明确领域冲突、资历冲突、学历/届别冲突继续作为硬上限，而不是被其它小项“加分冲掉”。

目标分布：强匹配 90–99，高匹配 85–89，值得优先 78–84，可投有缺口 68–77，低匹配快速跌到 55 以下；材料简历匹配材料研发、AI Infra 简历匹配 AI Infra 等正常案例应自然进入 80–95+。

### P0-2：检索路径过重，输入一次就可能触发完整重排

当前页面输入事件直接 renderMarket；完整推荐又包含职业域分析、技能命中、排序。数据量达到数万条以后，即使最终只渲染 60 张卡，也会频繁重复计算。

v1.4 需要：

- 搜索输入 120ms debounce；
- 每条岗位建立轻量搜索索引，明确搜索先走 title/company/location/JD 的廉价命中；
- 明确搜索只对前一小段高相关结果做完整 Match 计算，避免“搜一个公司名却给全部命中做语义评分”；
- 推荐结果建立 LRU 缓存，同一个简历/偏好/筛选组合不重复算；
- UI 显示本次排序耗时，让性能退化可观测。

### P0-3：信源失败时的用户体验仍然是“要么有，要么空”

成熟招聘产品不会让一个次要数据源超时拖死整个岗位池。v1.3 的 feed 读取存在串行路径，并且刷新失败时缺少“保留上一次可用数据”的产品语义。

v1.4 需要：

- 国内主池、priority 官方源、两类 source status 并行加载；
- 每个请求有超时和一次轻量重试；
- 某一源失败时继续展示其它成功源；
- 用户手动刷新失败时保留当前已经可用的岗位，不把页面清空；
- Feed Health 区分 healthy / degraded / stale，并显示岗位数、正常源数量和本次加载耗时。

### P0-4：从“看到合适”到“去投递”多了一次不必要的点击

v1.3 卡片已经有“加入流程”，但打开官方链接仍经常需要先进入详情。对秋招高频使用场景，这会不断增加摩擦。

v1.4：卡片直接提供“官网投递 ↗”；详情页继续保留完整 JD、匹配原因、Match Score、Evidence Confidence 与评分维度。

### P0-5：推荐反馈是单向的

“隐藏岗位”之后用户缺少明显的恢复入口。成熟推荐产品通常把 save/hide/already applied 当作学习信号，并允许用户反悔。

v1.4 先补最小闭环：显示已隐藏数量，并提供一键恢复；保留“加入流程”作为强正反馈。后续再把面邀/拒绝/Offer 作为 ranking learning signal。

## 三、本轮实现范围

### v1.4 本 PR 必须交付

1. 新的 0–100 Match Score 校准：适合岗位进入 80–95+，明显跨领域岗位被硬压低。
2. Evidence Confidence 与 Match Score 分离。
3. 轻量搜索索引 + debounce + ranking LRU cache。
4. 并行、超时、重试、部分成功、失败保留旧数据的 feed loader。
5. Feed Health 明确显示健康/降级/陈旧状态。
6. 卡片一键打开官方/当前可验证申请链接。
7. 90+ / 80+ 推荐概览、排序耗时、官方源占比。
8. 隐藏岗位恢复入口。
9. Node 评分校准回归、浏览器信源韧性回归、现有 60k / privacy / security / priority official / IGuopin 回归全部通过。

### 后续 P1（不阻塞 v1.4）

- Saved Searches / Watchlists 与条件提醒；
- 每个岗位的定制简历版本与差异预览；
- Chrome/Edge Copilot：从官网 ATS 一键读取岗位并自动记录投递；
- 投递结果学习：面邀、拒绝、Offer 对未来排序形成个人化反馈；
- JD 快照与岗位下线检测；
- 多职业 lane（例如“AI Infra”“央国企技术”“芯片软件”可以分别有偏好权重）。

## 四、验收标准

- 强相关简历-岗位样例：Match ≥ 88；典型同领域岗位多数 ≥ 80。
- 明显跨领域：Match ≤ 45；资深/经验严重冲突不能被其它证据抬到高分。
- Source Tier 改变主要影响 Evidence Confidence，而不能让同一个人的岗位适配度大幅改变。
- 60,000 岗位目录仍可通过浏览器压力测试；连续输入搜索不会每个字符都做完整重排。
- priority 官方源失败而国内池成功，页面仍可用；反之亦然；刷新全失败时已有岗位不清空。
- 卡片存在可点击的直接投递入口时，一次点击即可打开。
- 所有新增逻辑必须在旧浏览器状态/无简历/无目标城市/空源情况下可降级运行。
