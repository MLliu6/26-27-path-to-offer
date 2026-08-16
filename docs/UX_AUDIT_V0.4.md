# Path to Offer v0.4 — 10 Persona Adversarial Product Audit

## Scope and method

This audit was triggered by real product failures rather than visual polish requests:

1. A user searched for **京东** and got no result although public recruiting aggregators contain a JD/京东 recruiting record.
2. Resume text extraction worked, but candidate-direction inference was weak and the resulting profile was not visible or useful enough.
3. “0 results” did not distinguish between **catalog coverage failure** and **match/filter rejection**, making the product feel broken.

The review uses two complementary methods:

- **Deterministic core simulation**: `tests/persona_trials.mjs` feeds ten deliberately different resume texts through the real v0.4 profile/matching core and locks search regressions with assertions.
- **Persona-based adversarial walkthrough**: each persona is walked through the full product journey — first visit, resume import, profile interpretation, job search/recommendation, job detail, shortlist/pipeline, preparation assets, interview-review import and insights — looking for points where a plausible user would get blocked, misled or lose trust.

This is not represented as ten independent human usability-study participants. It is a deliberately adversarial product simulation using ten user archetypes plus executable regression tests. Human usability testing remains a later validation stage.

## Executive finding

The v0.3 product had a sound information architecture but two architectural errors in discovery:

- **Retrieval and recommendation were accidentally coupled.** A company query was first matched as text, then still forced through resume-score and freshness filters. An exact query such as `京东` could therefore disappear because it scored below 55 or was older than 30 days.
- **The catalog was much smaller than the UI implied.** Source health showed approximately 20 anonymous OfferJack rows + 50 Gank rows, while one configured CodeCV parser returned zero. The user was effectively searching a tiny cache, not “the recruiting web”.

The profile engine had a third weakness: it counted literal keyword hits from a small taxonomy, then showed only a few chips. That was insufficient for mixed resumes and made the result difficult to trust or correct.

v0.4 separates the concerns:

`explicit search = retrieval`  
`empty search = recommendation`

and makes candidate profiling an explainable artifact rather than an invisible filter.

---

## Persona trials

### P01 — First-time undergraduate, marketing / operations

**Context**: non-technical user, low tolerance for jargon, resume contains user research, product operations, growth, brand and data analysis.

**Walkthrough**

- Upload resume: must receive a useful direction even without CUDA/LLM-style technical keywords.
- Profile: should show `产品 / 运营 / 商业` with evidence rather than “未识别方向”.
- Discovery: empty search should rank product/operations/business roles rather than technical roles simply because “SQL” appeared once.
- Search: entering a company name must work independently of profile fit.
- Pipeline/review: normal status flow remains usable without technical-specific assumptions.

**v0.3 problem**: taxonomy was heavily engineering-biased; a non-technical resume could produce weak or empty direction inference.

**v0.4 result**: broader direction taxonomy adds product/operations/business signals and recommended role hypotheses.

### P02 — CS undergraduate, backend engineering

**Context**: Java/Go/Spring/Redis/MySQL/Kafka/Kubernetes resume.

**Expected profile**: `后端 / 分布式系统`.

**Adversarial checks**

- “distributed” evidence should not automatically misclassify the user as HPC.
- Explicit `美团` or `京东` query should not be removed by a 95-point match threshold.
- A backend posting should beat an unrelated operations posting in recommendation mode.

**v0.4 result**: separate backend/distributed-system direction and weighted evidence reduce collision with HPC.

### P03 — AI Infra / large-model inference master’s candidate

**Context**: vLLM, PagedAttention, KV Cache, prefill/decode, continuous batching, NCCL, CUDA, memory management.

**Expected profile**: `AI Infra / 大模型推理系统`.

**Adversarial checks**

- AI Infra should rank above generic “deep learning”.
- Profile panel should expose why: vLLM / PagedAttention / KV Cache etc.
- Suggested search roles should include AI Infra / LLM serving / inference systems.
- Search for `京东` should return JD if the catalog contains it even if the cached row says only “技术方向”.

**v0.3 problem**: the profile strip showed a few chips but did not make direction evidence/confidence legible.

**v0.4 result**: direction confidence, evidence, skills and recommended role terms are presented as separate profile artifacts.

### P04 — VLM + PTQ research master’s candidate

**Context**: PTQ, AWQ, GPTQ, Hessian, W4A16, INT4, VLM, visual-token pruning.

**Expected profile**: primary `LLM / VLM 量化压缩`, with VLM/multimodal as a secondary direction.

**Adversarial checks**

- A mixed research resume must preserve more than one direction.
- Quantization should not disappear because the resume also contains generic PyTorch/Transformer terms.
- User must be able to override inferred target directions.

**v0.4 result**: weighted multi-direction ranking exposes up to several hypotheses and permits manual target-direction correction.

### P05 — AI-chip compiler / NPU software master’s candidate

**Context**: NPU/RPU, MLIR, TVM, compiler, runtime, operator library, graph compilation.

**Expected profile**: `AI 芯片软件 / 编译器`.

**Adversarial checks**

- “runtime” should not be lost as a generic software keyword.
- Compiler/NPU evidence should dominate generic C++/Linux terms.
- Matching should explain chip/compiler fit rather than only show an opaque score.

**v0.4 result**: dedicated weighted direction with MLIR/TVM/NPU/runtime/operator evidence.

### P06 — HPC / distributed-computing PhD

**Context**: MPI, OpenMP, RDMA, AllReduce, multi-node/multi-GPU communication.

**Expected profile**: `HPC / 分布式计算`.

**Adversarial checks**

- PhD-level HPC should not be collapsed into generic backend.
- Degree matching must treat PhD as satisfying lower degree requirements rather than filtering it out.
- Recommendation reasoning should show communication/HPC evidence.

**v0.4 result**: dedicated HPC evidence and degree-rank compatibility remain explicit.

### P07 — Embedded / robotics candidate

**Context**: ROS2, Jetson Orin, STM32, RTOS, robotics, control, radar, edge deployment.

**Expected profile**: `嵌入式 / 机器人`.

**Adversarial checks**

- Jetson/CUDA appearance should not force AI Infra as the primary direction.
- Search/recommendation should support robotics and embedded vocabulary.
- Mobile UI must not require hover to inspect primary actions.

**v0.4 result**: dedicated embedded/robotics direction; existing click/drawer interactions remain mobile-accessible.

### P08 — Frontend + product hybrid candidate

**Context**: TypeScript/React/Vue plus user research/product design.

**Expected profile**: frontend/client primary with product as secondary evidence.

**Adversarial checks**

- Mixed profiles need ranked hypotheses rather than a single hard label.
- User should see and edit target direction rather than being trapped by automatic classification.
- Search must still retrieve a product role if user explicitly asks for it.

**v0.4 result**: multiple direction hypotheses + editable preferences + query-first retrieval.

### P09 — Quant / finance candidate

**Context**: factor research, backtesting, trading systems, financial engineering.

**Expected profile**: `金融 / 量化`.

**Adversarial checks**

- Quant candidates should not be classified only as Python/C++ software engineers.
- Public job-source mix must not be exclusively technology-company oriented.

**v0.4 result**: finance/quant taxonomy plus a dedicated public recruiting slice for finance/consumer/professional-service coverage.

### P10 — Chip / FPGA / EDA candidate

**Context**: FPGA, Verilog, SystemVerilog, RTL, ASIC, Vivado, chip verification.

**Expected profile**: `芯片 / EDA / 硬件`.

**Adversarial checks**

- “芯片” must not automatically mean AI-chip software/compiler.
- Digital-design evidence must distinguish hardware/EDA from compiler/runtime.
- Public catalog should include semiconductor-oriented slices.

**v0.4 result**: separate chip/EDA/hardware direction and technology/semiconductor discovery slice.

---

## Cross-functional findings

| Severity | Finding | Why it matters | v0.4 remediation |
|---|---|---|---|
| P0 | Exact text search was still filtered by match threshold | User searches a known company and sees 0; trust collapses immediately | Explicit query now bypasses match threshold and freshness filter |
| P0 | Catalog coverage was only tens of records | Search behaved like a tiny cache while UI looked like an aggregator | Add multiple public recruiting slices and expose cached catalog size/source health |
| P0 | `京东` regression reproducible | Concrete user-reported failure | Regression test: `京东` and alias `JD` must retrieve cached JD even at threshold 95 and old timestamp |
| P1 | Resume direction inference too literal | Mixed/specialized resumes produce weak or misleading profiles | Weighted direction taxonomy with evidence/confidence and broader domains |
| P1 | Candidate profile was too hidden | User could not understand or trust recommendation basis | Persistent profile-intelligence panel + inspectable evidence modal |
| P1 | Old threshold default 55 too aggressive | Sparse public JD text often cannot score 55 even when role is relevant | Default recommendation threshold reduced to 25; explicit search ignores it entirely |
| P1 | “0 results” had ambiguous cause | User cannot tell if search, matching or crawler failed | Query-specific empty state says catalog did not contain the query and exposes source diagnostics |
| P1 | Overlapping source slices duplicate records | Broader crawling can make the market noisy | Source-independent company+role+location dedupe with multi-source provenance |
| P1 | Saved job direction depended on parsing reason text | Fragile after match explanation evolves | Matcher returns canonical `direction`; pipeline stores it directly |
| P1 | Aggregator links may be absent/gated | A useful result may still be impossible to act on | Well-known-company official-career-portal fallback, clearly separated from job records |
| P2 | CodeCV parser currently yields zero | Source list can look healthier than it is | Keep failure visible in source health; do not count it as coverage |
| P2 | GitHub login button is not yet full account sync | Cross-device expectation can exceed actual behavior | Continue Local-first wording; production OAuth/token-exchange backend remains required |
| P2 | Insights are sparse early in the season | Empty charts can feel unfinished | Continue minimum-sample guardrails instead of inventing statistics |

---

## Search model: before vs. after

### Before

```text
query text match
   ↓
resume score >= 55
   ↓
fresh <= 30 days
   ↓
result
```

This is logically wrong for an explicit search. “Find 京东” is a retrieval instruction, not “recommend only 京东 rows that also satisfy my current recommendation settings”.

### After

```text
                    ┌─ explicit query ──► textual/company-alias retrieval
job catalog ────────┤
                    └─ empty query ─────► resume recommendation + threshold + freshness
```

The two paths meet again at the same result cards, job detail drawer and pipeline action.

---

## Candidate-profile model: before vs. after

### Before

- small hardcoded skill groups;
- exact substring hit counts;
- up to a few inferred direction strings;
- a few chips in the header;
- no confidence/evidence hierarchy.

### After

- weighted direction vocabulary spanning technical and non-technical candidate families;
- direction-specific evidence;
- ranked direction hypotheses and confidence;
- core skills, degree/year/city signals;
- recommended role-search terms;
- user-editable target directions and cities;
- re-run profile inference from retained local resume text;
- matching score components remain explainable rather than branded as opaque AI truth.

---

## Job-catalog review

Current source diagnostics exposed the real root cause of the “search 京东” complaint: the product had a very small normalized catalog. OfferJack's anonymous public surface yielded only its first page, Gank's configured base page contributed only one visible page, and CodeCV's static parser produced no compatible table.

v0.4 therefore broadens coverage by treating a large aggregator as a set of auditable public discovery slices instead of depending on one generic first page. The configured slices now cover latest campus records, technology/AI/semiconductor, technology internships, broader national internships, public-sector/energy and finance/consumer/professional-service categories. All are still public unauthenticated pages; any source that becomes gated fails closed.

The product deliberately does **not** claim “full-web coverage”. The UI instead exposes source health and cached catalog count so users can distinguish recommendation quality from collection coverage.

---

## Functional walkthrough checklist

Each persona review included these product surfaces:

- first landing / discovery empty state;
- resume upload/paste path;
- candidate-profile output and preference editing;
- exact search and empty-query recommendation;
- location/company-type/batch filters;
- match threshold/freshness/sort controls;
- card/table market views;
- source-health diagnostics;
- job-detail drawer;
- add-to-pipeline behavior;
- pipeline board/table mode;
- status date/timeline update path;
- resume-version library and preparation links;
- TXT/DOCX interview-review import path;
- insight sample-size behavior;
- export and local-data expectations;
- mobile/no-hover interaction assumptions;
- GitHub-login messaging boundary.

No live sample applications or fake interview data were added to make these screens appear populated.

---

## Acceptance gates for v0.4

### Automated

- [x] Ten distinct resume archetypes infer a non-empty and expected primary direction.
- [x] `京东` exact search survives a 95-point recommendation threshold.
- [x] `京东` exact search survives a >30-day timestamp when “fresh only” would otherwise apply.
- [x] `JD` alias retrieves 京东.
- [x] Search works before resume upload.
- [x] Empty-query recommendation still uses resume fit.
- [x] Match output has human-readable reasons.
- [x] JavaScript/Python syntax and existing crawler unit tests remain in CI.
- [x] No mock company/job/interview records are reintroduced.

### Product / data

- [x] Search empty state explicitly distinguishes catalog coverage from filtering.
- [x] Candidate direction evidence is visible and editable.
- [x] Catalog count and source health are visible.
- [x] Source overlaps are canonically deduplicated.
- [x] Official recruiting portal fallback exists for common companies when a public aggregator row lacks an actionable URL.
- [ ] Cross-device GitHub account sync — requires a real backend/token-exchange boundary and is intentionally not faked in a static Pages site.
- [ ] Broad enough catalog to call “near-comprehensive” — must be measured after the new source slices run in GitHub Actions; the site should not claim this before observing source counts.

---

## Next product hypotheses

1. **Feedback-trained ranking without server-side tracking**: use local “不合适 / 加入流程 / 实际面邀” outcomes to calibrate personal direction weights over time.
2. **Company directory layer**: separate “company recruiting portal exists” from “specific current job record exists”, so a user can always discover official entry points without fabricating postings.
3. **Query-aware collection queue**: once a secure backend exists, unresolved searches could become anonymous aggregate demand signals for which public sources/companies to refresh more frequently.
4. **Resume section parser**: distinguish education, internships, projects, papers and skills before direction inference, reducing false evidence from unrelated dates or boilerplate.
5. **Cross-device encrypted sync**: identity should unlock continuity, not become a prerequisite for browsing or resume parsing.

## Product principle retained

A candidate should be able to answer four questions at any moment:

1. **What opportunities exist?**
2. **Which of them fit me, and why?**
3. **What have I already done with each one?**
4. **What did I learn from the process?**

v0.4 focuses on making questions 1 and 2 credible enough that the downstream tracking system is worth using.
