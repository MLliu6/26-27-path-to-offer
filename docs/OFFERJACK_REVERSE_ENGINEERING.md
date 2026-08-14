# OfferJack black-box product study

This document records observable product behavior, not copied proprietary source code.

## Observable information architecture

Public search/index results expose a large tabular campus-recruiting dataset with fields such as:

- 更新时间
- 企业名称
- 招聘批次
- 企业性质
- 行业
- 工作地点
- 职位
- 毕业年份
- 公告链接
- 投递地址
- 求职进展

The public page also exposes category/filter affordances such as internship/campus listings, state-owned-enterprise and foreign-enterprise views, saved filters and refresh.

## What Path to Offer copies conceptually

Only generic product patterns that are not unique implementation code:

- a dense normalized job table;
- multi-dimensional filters;
- announcement + application links;
- freshness visibility;
- a unified job-source layer.

## What Path to Offer adds

1. Resume-first ranking rather than a generic table first.
2. Explainable match reasons per job.
3. Candidate preferences layered on top of resume evidence.
4. “not suitable” feedback to progressively clean the discovery inbox.
5. Direct transition from discovery into a dated application pipeline.
6. Binding of the selected resume version and initial match score to the job.
7. Interview preparation and interview-memory feedback after application.
8. Source health and stale-feed reporting instead of silently showing old data.
9. Local-first privacy for candidate files and personal decisions.
10. Open adapter architecture instead of coupling the UI to one source.

## Technical compatibility adapter

`scripts/aggregate_jobs.py` tries, in order:

1. semantic table-header matching against a publicly rendered HTML table;
2. a conservative scan of explicit JSON script blocks (`application/json`, `__NEXT_DATA__`, `__NUXT_DATA__`) for job-like records.

It does not attempt to de-minify or copy proprietary bundles, bypass login, solve CAPTCHA, spoof sessions, evade rate limits, or access non-public endpoints.

If the public surface changes, the adapter records failure in `data/source_status.json` rather than escalating to bypass techniques.
