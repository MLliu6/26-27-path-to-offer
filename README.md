# Path to Offer

**Resume-first job discovery + application pipeline + interview memory.**

Path to Offer is an open-source candidate operating system for the complete recruiting journey:

`resume → discover → shortlist → prepare → apply → assessment → interview → review → offer → sign`

The product starts empty. It does not ship fake companies, fake applications, fake match scores, or demo interview records.

## Discovery before application

The product center of gravity is intentionally placed before the application itself.

1. Upload a PDF / DOCX / TXT resume.
2. The browser parses it locally and extracts explainable signals: skills, likely directions, degree/year signals and keywords.
3. `data/jobs.json` is refreshed by GitHub Actions from public, unauthenticated job sources every two hours.
4. Each real job is scored against the active resume with an explainable local matcher.
5. The user decides whether to hide it or move it into the application pipeline.
6. Only then does the normal status timeline begin.

## Embedded job market

The job market is independently implemented after black-box review of public recruiting aggregators. It supports company / role / skill / city search, location/company-type/batch filtering, resume-match thresholds, freshness and education controls, match/freshness/company sorting, card and table views, source attribution, job-detail drawers, one-click promotion into the pipeline, and explicit “not suitable” feedback stored locally.

The UI is not an iframe wrapper around another service. It normalizes public source records into Path to Offer's own data model and renders them inside the application.

## Resume parsing and matching

Resume files are parsed in the browser:

- PDF: PDF.js
- DOCX: Mammoth
- TXT: native File API

The original file is not uploaded to this public repository. Parsed text and signals are stored in browser `localStorage` unless the user deletes them. The matcher is deliberately explainable rather than pretending to be a black-box AI score: skill overlap, direction fit, optional target city, degree/year compatibility, and recency are exposed as match reasons.

## Public job aggregation

`.github/workflows/refresh-jobs.yml` runs every two hours.

Current source architecture:

- `OfferJack` public-surface compatibility adapters: rendered table, embedded JSON, headless-browser observation of the same unauthenticated XHR/fetch request used by the page, and same-origin replay of only pagination parameters already observed in that public request.
- `Public HTML table adapters`: auditable sources listed in `sources/public_pages.json`. The current list includes Gank Interview's public campus page and CodeCV's public jobs page. Each source is fetched only if robots/public access allows it; incompatible or gated pages fail closed and are surfaced in `data/source_status.json`.
- `CustomJsonFeedAdapter`: plug-in JSON feeds configured in `sources/custom_urls.json`.
- deterministic normalization and deduplication across sources;
- source-health output in `data/source_status.json`;
- previous-feed retention when a temporary source outage occurs.

Crawler rules are strict: public unauthenticated surfaces only, robots check when available, no login/CAPTCHA/anti-bot bypass, no hidden credentials, and no copying of non-public source code. When a service restricts unauthenticated users, the crawler stops at that boundary and broadens coverage through other public sources instead.

## Application tracking

The application pipeline supports:

`发现 → 待投递 → 准备中 → 已投递 → 测评 → 一面 → 二面 → 三面/终面 → HR 面 → Offer → 已签约 → 结束`

Dragging a card between columns records a dated timeline event. A job can retain the resume version and initial match score used when it entered the pipeline, enabling later match-to-interview analytics.

## Interview preparation and memory

- Multiple resume versions.
- User-added GitHub / Notion / document assets.
- Direct link to the `MLliu6/26-27-interview` knowledge base.
- TXT / DOCX interview-review import.
- Review records linked to job history.
- Analytics stay blank until enough real samples exist.

## GitHub Pages

The repository contains `.github/workflows/pages.yml` for GitHub Pages deployment. The intended public URL is:

`https://mlliu6.github.io/26-27-path-to-offer/`

GitHub requires Pages to be enabled once for the repository with **Settings → Pages → Source: GitHub Actions**. After that, pushes to `main` deploy automatically. The repository workflow already contains the official `configure-pages`, `upload-pages-artifact`, and `deploy-pages` steps.

## GitHub login and cross-device sync

The UI includes a GitHub login entry and a production auth interface in `config.js`, but the repository does **not** put an OAuth client secret or reusable user token into public JavaScript.

A secure production flow is:

`github.io frontend → GitHub OAuth/GitHub App → small server-side token exchange → encrypted user storage`

Configure `githubClientId` and `githubOAuthProxy` in `config.js` after provisioning the identity backend. Until then, the site remains fully usable in Local-first mode without an account. GitHub's own documentation recommends a GitHub App for fine-grained permissions and short-lived tokens when the product serves multiple users.

See `docs/AUTH_AND_SYNC.md`.

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

## Design

- Georgia for English/numerals with Chinese serif fallbacks.
- Light, low-contrast Morandi palette; ten accent themes.
- Five flat product views rather than deep admin navigation.
- Hover Lift, Active State, Drawer, Modal, Toast, Kanban Drag, Theme Accent Switch and restrained page transitions.
- `prefers-reduced-motion` support.
- Mobile bottom navigation and single-column job cards.

## License

MIT
