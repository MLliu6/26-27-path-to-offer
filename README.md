# Path to Offer

**Resume-first job discovery + application pipeline + interview memory.**

Path to Offer is an open-source candidate operating system for the complete recruiting journey:

`resume → discover → shortlist → prepare → apply → assessment → interview → review → offer → sign`

The product starts empty. It does not ship fake companies, fake applications, fake match scores, or demo interview records.

## v0.2: discovery before application

The major change in v0.2 is moving the product center of gravity earlier in the recruiting funnel.

1. Upload a PDF / DOCX / TXT resume.
2. The browser parses it locally and extracts explainable signals: skills, likely directions, degree/year signals and keywords.
3. `data/jobs.json` is refreshed by GitHub Actions from public, unauthenticated job sources every two hours.
4. Each real job is scored against the active resume with an explainable local matcher.
5. The user decides whether to hide it or move it into the application pipeline.
6. Only then does the normal status timeline begin.

## Job discovery UI

The embedded job market is independently implemented after black-box review of public recruiting aggregators. It supports:

- company / role / skill / city search;
- location, company type and recruiting batch filters;
- resume-match threshold;
- freshness, degree and graduation-year controls;
- match / freshness / company sorting;
- card and dense table views;
- source attribution and refresh health;
- job-detail drawer with announcement/apply links;
- one-click promotion into the user's pipeline;
- explicit “not suitable” feedback stored locally.

## Resume parsing

Resume files are parsed in the browser:

- PDF: PDF.js
- DOCX: Mammoth
- TXT: native File API

The original file is not uploaded to this public repository. Parsed text and signals are stored in browser `localStorage` unless the user deletes them. The user can delete raw parsed text while retaining derived signals.

The v0.2 matcher is deliberately **explainable**, not branded as semantic AI: skill overlap, direction fit, optional target city, degree/year compatibility, and recency. A later version can add local embeddings or a user-configured inference endpoint without changing the data model.

## Public job aggregation

`.github/workflows/refresh-jobs.yml` runs every two hours and executes `scripts/aggregate_jobs.py`.

Current source architecture:

- `OfferJackAdapter`: compatibility parser for OfferJack's publicly rendered/indexable job table, with a generic embedded-JSON fallback.
- `CustomJsonFeedAdapter`: plug-in JSON feeds configured in `sources/custom_urls.json`.
- deterministic normalization and deduplication;
- source-health output in `data/source_status.json`;
- previous-feed retention when a temporary source outage occurs.

Crawler rules are intentionally strict: public unauthenticated pages only, robots check when available, no login/CAPTCHA/anti-bot bypass, no hidden credentials, no attempt to copy non-public application source code.

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
- Analytics intentionally stay blank until enough real samples exist.

## GitHub Pages

The repository contains `.github/workflows/pages.yml` for GitHub Pages deployment. The intended public URL is:

`https://mlliu6.github.io/26-27-path-to-offer/`

GitHub requires Pages to be enabled once for the repository with **Settings → Pages → Source: GitHub Actions**. After that, pushes to `main` deploy automatically.

## GitHub login and cross-device sync

The UI now includes a GitHub login entry and a production auth interface in `config.js`, but the repository does **not** put an OAuth client secret or user access token into public JavaScript.

A secure production flow is:

`github.io frontend → GitHub OAuth → small server-side token-exchange proxy → encrypted user storage`

Configure `githubClientId` and `githubOAuthProxy` in `config.js` after provisioning the OAuth/GitHub App backend. Until then, the site remains fully usable in Local-first mode without login.

See `docs/AUTH_AND_SYNC.md`.

## Run locally

```bash
python -m http.server 8000
```

Open `http://localhost:8000`.

For crawler development:

```bash
python -m pip install requests==2.32.5 beautifulsoup4==4.13.4
python scripts/aggregate_jobs.py
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
