# Path to Offer

**Resume-first job discovery + application pipeline + interview memory.**

Path to Offer is an open-source candidate operating system for the complete recruiting journey:

`resume → profile → discover → shortlist → prepare → apply → assessment → interview → review → offer → sign`

Live site: **https://mlliu6.github.io/26-27-path-to-offer/**

The product starts empty. It does not ship fake companies, fake applications, fake match scores, or demo interview records.

## v0.4.1 — search, profile and browser reliability

The product center of gravity is intentionally before application. v0.4 fixed two important failures discovered through real use: an exact company search could be hidden by recommendation filters, and resume direction inference was too dependent on a small literal-keyword taxonomy. v0.4.1 adds a real headless-browser user-journey gate and a finite public-search collector for priority campus companies/roles.

The current flow is:

1. Upload a PDF / DOCX / TXT resume, or paste resume text.
2. Parse it locally in the browser.
3. Build an explainable candidate profile with weighted direction evidence, confidence, core skills, graduation/degree signals and recommended role-search terms.
4. Read the normalized public job catalog refreshed by GitHub Actions every two hours.
5. With an empty search box, rank jobs by resume fit and user preferences.
6. With an explicit query such as `京东`, perform retrieval first: exact company/role searches are **not** suppressed by the match threshold or the “30 days” switch.
7. Inspect why a job matched, then explicitly move it into the application pipeline.
8. Keep the resume version, initial match score, dated pipeline events and interview review connected.

`matching-core.js` contains the deterministic profile/search/matching engine. `enhancements-v04.js` layers the richer profile/search experience over the stable application shell.

## Candidate profile

The browser infers weighted evidence across broad candidate directions including:

- AI Infra / large-model inference systems
- CUDA / GPU kernel optimization
- LLM / VLM quantization and compression
- VLM / VLA / multimodal
- AI-chip software / compiler
- HPC / distributed computing
- LLM / NLP algorithms
- computer vision / multimedia
- backend / distributed systems
- frontend / client
- embedded / robotics
- chip / EDA / hardware
- data / recommendation / search
- testing / SRE / security
- product / operations / business
- finance / quantitative research

The profile UI exposes direction confidence, supporting evidence, core skills and recommended role-search terms. Users can override target directions and cities; the inferred profile is evidence, not an irreversible label.

PDF parsing uses PDF.js, DOCX uses Mammoth, and TXT uses the native File API. The original resume file is not committed to this public repository. Parsed text and derived signals remain in browser storage unless the user deletes them.

## Embedded job market

The job market is an independent UI, not an iframe wrapper. Public source records are normalized into Path to Offer's data model and rendered with:

- company / role / skill / city search;
- location, company type and recruiting-batch filters;
- resume-match threshold and freshness control;
- match / freshness / company sorting;
- card and dense-table views;
- source attribution and source-health diagnostics;
- match reasons and candidate-profile evidence;
- one-click promotion into the personal pipeline;
- local “not suitable” feedback.

The UI explicitly separates two modes:

- **Explicit search** — retrieval-first; a direct company/role query bypasses recommendation threshold and freshness filtering.
- **Empty search** — resume-first recommendation; threshold, freshness, profile evidence and user preferences apply.

For well-known companies, a direct search can also expose the official recruiting portal as a fallback when the public catalog currently lacks an actionable job URL. A portal fallback is clearly treated as a portal, not fabricated as a job record.

## Public job aggregation

`.github/workflows/refresh-jobs.yml` runs every two hours.

Current collection paths:

- **OfferJack public surface** — public rendered/API records only. Anonymous access currently limits deeper pagination; Path to Offer stops at that boundary rather than bypassing login.
- **Gank Interview base public campus table** — auditable HTML-table collection.
- **Gank public search UI collector** — `scripts/gank_browser_search.py` loads the normal public campus page in a headless browser, enters a finite configured set of company/role queries through the page's visible search box, and parses only the public table rendered to that browser. Priority queries include companies such as 京东/腾讯/字节/阿里/美团 and role terms such as AI Infra/CUDA/大模型/量化/芯片/后端.
- **CodeCV public page adapter** — kept as an independent adapter; parser failure is surfaced in source health rather than silently counted as coverage.
- **Custom JSON feeds** — optional normalized public feeds in `sources/custom_urls.json`.

The catalog performs source-independent canonical deduplication by company + role + location and preserves multi-source provenance. A failing source does not erase the previous catalog.

Crawler rules remain strict: public unauthenticated surfaces only, robots checks where applicable, no login/CAPTCHA/anti-bot bypass, no privileged credentials and no copying non-public source code. The public-search collector deliberately uses the visible search UI rather than guessing or calling private endpoints.

## Application tracking

The pipeline supports:

`发现 → 待投递 → 准备中 → 已投递 → 测评 → 一面 → 二面 → 三面/终面 → HR 面 → Offer → 已签约 → 结束`

Dragging between stages records dated timeline events. A selected job retains the resume version and initial match score/direction so later analytics can compare “recommended” with actual interview conversion.

## Interview preparation and memory

- Multiple resume versions and active-profile switching.
- User-added GitHub / Notion / document assets.
- Direct link to `MLliu6/26-27-interview` for interview preparation material.
- TXT / DOCX interview-review import.
- Reviews linked to job history.
- Analytics remain explicit about insufficient sample size.

## Reliability tests

`tests/persona_trials.mjs` runs ten deliberately different candidate profiles, from marketing/backend candidates to AI Infra, VLM/PTQ, chip/compiler, HPC, robotics, frontend, quant and EDA users. It also locks the concrete `京东`/`JD` regression: direct search must work even at a hypothetical 95-point recommendation threshold and with an old timestamp.

`tests/browser_smoke.py` drives the actual static application in headless Chrome through the critical journey: pre-resume search → resume/profile creation → v4 profile inspection → direct `京东` search → shortlist → pipeline status update → resume library → TXT interview-review import → insights → export → theme switch → source health, plus a mobile search/action sanity check. The job records used there are CI-only fixtures and are never shipped in the product.

See [`docs/UX_AUDIT_V0.4.md`](docs/UX_AUDIT_V0.4.md) for the 10-persona adversarial walkthrough and remediation matrix.

## GitHub Pages

The repository is configured as:

`Settings → Pages → Deploy from a branch → main → / (root)`

Published changes and refreshed public data on `main` are served from:

**https://mlliu6.github.io/26-27-path-to-offer/**

The obsolete Actions-based Pages workflow was removed to avoid a second deployment path.

## GitHub login and cross-device sync

The UI exposes the intended GitHub-login entry, but a real multi-user OAuth flow still needs a server-side authorization-code/token exchange. A reusable token or OAuth client secret is never embedded in public GitHub Pages JavaScript.

The intended production boundary remains:

`github.io frontend → GitHub OAuth/GitHub App → server-side token exchange → encrypted user storage`

Until that backend exists, the application is Local-first and usable without an account. See `docs/AUTH_AND_SYNC.md`.

## Run locally

```bash
python -m http.server 8000
```

For crawler development:

```bash
python -m pip install requests==2.32.5 beautifulsoup4==4.13.4 playwright
python scripts/aggregate_jobs.py
PYTHONPATH=. python scripts/merge_public_tables.py
PYTHONPATH=. python scripts/gank_browser_search.py
```

For reliability tests:

```bash
node tests/persona_trials.mjs
python tests/browser_smoke.py  # while a local HTTP server is running
```

## Design

- Georgia for English/numerals with Chinese serif fallbacks.
- Light, low-contrast Morandi palette; ten accent themes.
- Five flat product views rather than deep admin navigation.
- Restrained Hover Lift, Active State, Drawer, Modal, Toast, Kanban Drag and Theme Accent Switch interactions.
- `prefers-reduced-motion` support.
- Mobile bottom navigation and single-column job cards.

## License

MIT
