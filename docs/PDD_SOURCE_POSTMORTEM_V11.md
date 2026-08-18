# PDD source omission postmortem — v1.1

## User-reported missing position

- Company: 拼多多
- Position: AI Infra研发工程师
- Stable employer position ID: `5e4eb6f3-294f-491b-9d39-42895eed98c3`
- Employer URL: `https://careers.pddglobalhr.com/campus/grad/detail?positionId=5e4eb6f3-294f-491b-9d39-42895eed98c3`

## Why production missed it

1. The production direct-source layer had concrete adapters for Meituan and Tencent, but not PDD. PDD appeared only as a coarse campaign record such as “研发类 / 产品类 / 数据算法类”; this cannot substitute for concrete employer positions.
2. An earlier browser probe discovered PDD's public list/detail endpoints, but the diagnostic branch was never turned into a production adapter or merged.
3. During the production fix, the PDD endpoint exposed a second trap: it reported 22 graduate positions but returned only ten rows even when `pageSize=100`. The first adapter stopped on `len(rows) < requested_page_size`, so it retained only the first page. Pagination now terminates on accumulated rows versus the employer-reported total and detects repeated page signatures.

## Production correction

- Enumerate every public graduate and internship page from PDD's employer-owned API.
- Fetch public position details to preserve responsibilities and requirements.
- Preserve all role categories, not only technical jobs.
- Resolve user-reported official URLs by stable UUID through `sources/official_position_seeds.json`.
- Publish a separate employer-direct priority feed every ten minutes; merge it ahead of the two-hour China federation in the browser.
- Preserve the previous valid priority rows when an upstream source temporarily fails.
- Also merge PDD rows into the deeper China catalogue.

## Live acceptance on 2026-08-18

The strict GitHub-hosted run observed:

- PDD: 24 public campus positions — 22 graduate and 2 internship rows;
- categories: 技术 9, 职能 5, 运营 5, 产品 1, 市场营销 1, 视觉类 1, 设计 1, 语言 1;
- exact position UUID/title/link: PASS;
- priority employer-direct feed: 2,586 rows — PDD 24, Meituan 562, Tencent 2,000;
- unit tests: PASS;
- exact-position/category live gate: PASS;
- browser search → detail → employer URL: PASS;
- existing static/product/browser suite: PASS.

## Non-claim

This correction guarantees that the currently public PDD rows and the exact seeded employer URL are independently observed. It does not claim that every employer on the internet exposes a complete anonymous API. Unavailable/login-gated sources remain visible as monitored sources rather than being fabricated as concrete openings.
