# Federated discovery v0.6

Path to Offer's discovery layer is no longer designed around one aggregator. The crawler runs in GitHub Actions, because GitHub Pages itself is a static frontend and browsers cannot reliably crawl arbitrary recruiting sites because of CORS, credentials and execution limits.

## Runtime pipeline

Every two hours:

1. The existing public OfferJack/Gank adapters refresh what their anonymous surfaces expose.
2. A pinned MIT `Hiring-Radar` checkout is loaded as an adapter library.
3. China company collectors run concurrently across direct official APIs plus public Feishu Hire and Beisen portals. Moka encrypted-payload adapters are deliberately excluded.
4. Eight current 2027 SWE/AI public job-list documents are scanned only for outgoing official ATS links.
5. The discovered Greenhouse/Ashby/Lever/SmartRecruiters/Recruitee/Breezy/BambooHR/Personio boards are queried directly for current official jobs.
6. Public remote boards are collected.
7. Records are normalized, source-independently deduplicated, compacted and written to `data/jobs.json`.
8. `data/source_status.json` records the measured catalogue size and diagnostics.

The first product threshold is **10,000 real normalized live records**. This is a measured acceptance gate, not a number inserted into the UI. The catalogue can grow up to a 60,000-row cap before the frontend data architecture should be sharded.

## Why this is more robust than copying an aggregator

An aggregator can expose 15,000+ records internally while restricting anonymous users to its first page. Repeatedly attacking that restriction does not create a reliable product. Federation instead moves toward the original sources: official employer APIs and standardized ATS job boards. If one aggregator or employer changes its public interface, other source families continue to refresh.

## Current source families

- Direct official China company APIs: JD, ByteDance, Tencent, Baidu, NetEase, Unitree where the pinned upstream adapter remains operational.
- Feishu Hire: data-driven employer seed list, one generic public adapter.
- Beisen / zhiye.com: data-driven employer seed list, one generic public adapter.
- Greenhouse.
- Ashby.
- Lever.
- SmartRecruiters.
- Recruitee.
- Breezy.
- BambooHR.
- Personio.
- Existing public aggregator surfaces.
- RemoteOK / Remotive / WeWorkRemotely / WorkingNomads.

## Retrieval vs recommendation

These remain separate:

- **Explicit search** (`京东`, `腾讯`, `CUDA`) retrieves matching catalogue rows and ignores recommendation thresholds/freshness toggles.
- **Empty search** ranks the catalogue using the active resume profile and candidate preferences.

A zero-result explicit query therefore means “the current catalogue did not contain this query,” not “your resume was judged unfit.”

## Access policy

The crawler does not use user cookies or accounts, solve CAPTCHAs, rotate proxies, impersonate logged-in sessions, bypass rate limits or replay requests after an anonymous-access denial. It broadens coverage by adding independent public sources instead.
