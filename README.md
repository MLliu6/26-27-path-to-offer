# Path to Offer

A local-first, open-source candidate operating system for the complete recruiting journey: **discover → prepare → apply → interview → review → offer → sign**.

当前版本是面向 2026–2027 秋招的可用 MVP，同时按“未来可开放给更多 candidates 使用”的方向设计。

## What works now

- 五个扁平主视图：总览、流程、发现岗位、准备资料、面经。
- 12 个中国校招常见状态：发现、待投递、准备中、已投递、测评、一面、二面、三面/终面、HR 面、Offer、已签约、结束。
- Kanban 拖拽更新状态；每次变化自动记录日期并进入岗位时间线。
- 表格视图、关键词搜索、优先级与岗位方向筛选。
- 岗位详情包含公司、部门、JD、薪资、地点、链接、简历版本、准备资料和下一步。
- 面经导入支持 `.txt` / `.docx`（DOCX 使用 Mammoth 浏览器端解析）。
- 准备资料可绑定 GitHub / 文档链接；默认提供 `MLliu6/26-27-interview` 入口。
- 10 套浅色莫兰迪主题，选择保存在本机。
- JSON 数据导出备份。
- 响应式桌面/移动端界面，支持 reduced-motion。

## Privacy model

个人求职数据默认只保存在浏览器 `localStorage`。仓库和 GitHub Pages 只发布应用代码与虚构示例数据，不会自动把你的真实投递、JD、面经或简历公开到 GitHub。

这意味着 v0.1 在不同设备之间不会自动同步个人数据。可以通过“导出”保存 JSON；跨设备加密同步列在 v0.2 路线中。

## Run locally

这是纯静态站点，无构建步骤：

```bash
python -m http.server 8000
```

然后打开 `http://localhost:8000`。

## Publish with GitHub Pages

合并到 `main` 后，在仓库 `Settings → Pages` 中选择 `Deploy from a branch`，Branch 选择 `main`、目录选择 `/ (root)`。之后站点即可通过 GitHub Pages URL 在任意设备打开。

> GitHub Connector 当前不能替你切换仓库 Pages 设置，因此这是首次发布唯一需要在 GitHub UI 中手动完成的一步。

## Product direction

见 [`docs/PRODUCT.md`](docs/PRODUCT.md) 与 [`docs/REVIEW.md`](docs/REVIEW.md)。核心差异化不是再造一个 Kanban，而是把“岗位状态 + 具体日期 + 投递简历 + 面试准备资产 + 面经复盘”连成可追溯、可统计、可持续学习的一条路径。

## Job discovery boundary

计划中的“每 2 小时岗位刷新”采用可插拔公开数据源适配器。只接入允许自动访问的公开页面、RSS、JSON/API 等来源；不会绕过登录、验证码、反爬机制或网站访问控制。OfferJack 当前作为公开聚合入口外部打开，后续若存在稳定且允许的接口再接入自动归一化。

## Design

视觉基调为 Georgia + 中文 serif fallback、浅背景、低嵌套、低动效密度。交互从用户提供的 Vibe Coding 术语手册中选取 Drawer、Modal、Kanban Drag、Active State、Focus Highlight、Toast、Theme Accent Switch、Hover Lift 与轻量 Page Transition 等模式。

## License

MIT
