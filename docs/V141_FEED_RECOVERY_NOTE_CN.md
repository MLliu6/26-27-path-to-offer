# Path to Offer v1.4.1 岗位目录恢复热修

## 现象

v1.4.0 在部分真实浏览器/网络环境下出现矛盾状态：页面的 source status 已显示“岗位池 60,000 · federated / 官网快线 2,649”，但 JOB MARKET 为 0，并显示“岗位聚合源目前是空的”。

## 根因

`enhancements-v14.js` 的 JSON loader 对所有 JSON 共用约 7 秒 AbortController，并且计时器覆盖 `fetch()` 与 `response.json()` 整个过程。小型 source-status JSON 可以在窗口内完成，而 60,000 行 compact catalogue 在较慢连接、冷缓存或浏览器 JSON 解析阶段可能超过该时间，于是大目录被主动 abort；首次访问又没有 last-good catalogue 可保留，因此 `marketJobs=[]`。状态文件成功而岗位文件失败，最终形成“状态显示 60,000、实际 0”的错误产品语义。

## v1.4.1 修复

仅做 feed-recovery 热修：

- catalog 与 status 使用独立超时策略；catalog response header 预算 12 秒，body 下载/JSON 解析预算 45 秒，status 继续采用短预算。
- header 返回后立即清除 header timer，不再让同一个 7 秒 timer 覆盖大型 JSON body。
- 当 status 宣称存在岗位而两个主 catalogue 都失败/为空时，将其判定为 `catalogInconsistent`，自动读取兼容 `jobs.json` 恢复岗位，而不是把网络超时显示成“岗位池为空”。
- 若用户已经拥有一版可用岗位，后续全源失败继续保留 last-good catalogue。
- 新增 `PTO_V141_FEED_READY`、`expectedCatalogCount`、`catalogRecovered`、`fallbackUsed` 等运行时诊断。
- 更新入口 cache key 到 1.4.1，避免旧 `config.js` 留在浏览器缓存。

## 回归门

`tests/v141_feed_recovery_smoke.py` 固定复现：source status=60,000/2,649，`jobs_cn.json` 与 `jobs_priority.json` 失败，`jobs.json` fallback 成功；要求岗位卡恢复、`infra` 可搜索、页面不得出现“岗位聚合源目前是空的”。随后让 fallback 也失败，要求刷新后仍保留上一版岗位。
