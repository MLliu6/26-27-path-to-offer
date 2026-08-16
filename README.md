# Path to Offer

**Resume-first job discovery + application pipeline + interview memory.**

Path to Offer is an open-source candidate operating system for the complete recruiting journey:

`resume → profile → discover → shortlist → prepare → apply → assessment → interview → review → offer → sign`

Live site: **https://mlliu6.github.io/26-27-path-to-offer/**

The product starts empty. It does not ship fake companies, fake applications, fake match scores, or demo interview records.

## v0.4 — search and candidate-profile reliability

The product center of gravity is intentionally before application. v0.4 fixes two important failure modes discovered through real use: an exact company search could previously be hidden by the resume-match threshold/freshness filter, and resume direction inference was too dependent on a small list of literal keywords.

The new flow is:

1. Upload a PDF / DOCX / TXT resume.
2. Parse the document locally in the browser.
3. Build an explainable candidate profile with weighted direction evidence, confidence, core skills, graduation/degree signals and recommended role-search terms.
4. Read the normalized public job catalog refreshed by GitHub Actions every two hours.
5. With an empty search box, rank jobs by resume fit and user preferences.
6. With an explicit query such as `京东`, perform retrieval first: exact company/role searches are **not** suppressed by the match threshold or the “30 days” switch.
7. Inspect why a job matched, then explicitly move it into the application pipeline.
8. Keep the resume version, initial match score, dated pipeline events and interview review connected.

`matching-core.js` contains the deterministic profile/search/matching engine so it can be regression-tested independently of the UI. `enhancements-v04.js` layers the richer profile/search experience over the stable application shell.

## Candidate profile

The browser currently infers weighted evidence across broad candidate directions including:

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

For well-known companies, a direct search can also expose the official recruiting portal as a fallback when the public catalog currently lacks a usable apply URL. A portal fallback is clearly treated as a portal, not fabricated as a job record.

## Public job aggregation

`.github/workflows/refresh-jobs.yml` runs every two hours.

The current architecture combines:

- **OfferJack public surface** — public rendered/API records only. Its anonymous interface currently limits deeper pagination, so Path to Offer stops at that boundary rather than bypassing login.
- **Gank Interview public recruiting tables** — several auditable slices for latest campus jobs, 2027 internship/technology roles, public-sector/energy and finance/consumer coverage.
- **CodeCV public page adapter** — retained as an independent source; source-health makes parser failures visible rather than silently inventing data.
- **Custom JSON feeds** — optional normalized public feeds in `sources/custom_urls.json`.

The final catalog performs source-independent canonical deduplication by company + role + location and preserves multi-source provenance. A failing source does not erase the previous catalog.

Crawler rules remain strict: public unauthenticated surfaces only, robots checks where available, no login/CAPTCHA/anti-bot bypass, no privileged credentials and no copying non-public source code.

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

`tests/persona_trials.mjs` runs ten deliberately different candidate profiles, from marketing and backend candidates to AI Infra, VLM/PTQ, chip/compiler, HPC, robotics, frontend, quant and EDA users.

The suite also locks the concrete regression that motivated v0.4:

- searching `京东` must return a cached 京东 record even when its match score is below a hypothetical 95-point threshold and the record is older than 30 days;
- `JD` is recognized as a 京东 alias;
- search works before a resume is uploaded;
- empty-query recommendation still uses resume fit and remains explainable.

See `docs/UX_AUDIT_V0.4_DRAFT.md` for the adversarial product walkthrough and remediation matrix.

## GitHub Pages

The repository is currently configured in GitHub as:

`Settings → Pages → Deploy from a branch → main → / (root)`

Therefore every published change/data refresh on `main` is served from:

**https://mlliu6.github.io/26-27-path-to-offer/**

The old GitHub-Actions Pages deployment workflow is intentionally removed to avoid a second, conflicting deployment path.

## GitHub login and cross-device sync

The UI exposes the intended GitHub-login entry, but a real multi-user OAuth flow still needs a server-side authorization-code/token exchange. A reusable token or OAuth client secret is never embedded in public GitHub Pages JavaScript.

The production boundary remains:

`github.io frontend → GitHub OAuth/GitHub App → server-side token exchange → encrypted user storage`

Until that backend exists, the application remains Local-first and usable without an account. See `docs/AUTH_AND_SYNC.md`.

## Run locally

```bash
python -m http.server 8000
```

Open `http://localhost:8000`.

For crawler development:

```bash
python -m pip install requests==2.32.5 beautifulsoup4==4.13.4 playwright
python scripts/aggregate_jobs.py
PYTHONPATH=. python scripts/merge_public_tables.py
```

For matching/profile tests:

```bash
node tests/persona_trials.mjs
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
