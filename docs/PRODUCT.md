# Path to Offer — Product Brief

## North Star

Path to Offer is not another spreadsheet. It is a candidate operating system that keeps the complete causal chain of a recruiting process in one record:

**discover → evaluate → prepare → apply → assess → interview → review → offer → sign**.

The core object is a `Job Record`. Every resume version, preparation asset, status event and interview review should be attributable to that record.

## First-principles product principles

1. **The user should know what to do next in under 10 seconds.** Dashboard and pipeline must expose current state and next action without nested navigation.
2. **History must be reconstructable.** A status is not only a label; every transition carries a date and is appended to a timeline.
3. **Learning compounds.** Interview notes are not dead documents. They become a durable corpus that can later produce weak-point clusters, repeated questions and preparation priorities.
4. **Privacy is the default.** v0.1 stores personal recruiting data in browser localStorage; the public repository contains only application code and fictional demo data. Users explicitly export their own JSON backups.
5. **Job discovery is source-adapter based, not an uncontrolled scraper.** Public feeds/pages can be normalized on a schedule where permitted. Sources requiring authentication, CAPTCHA bypass, anti-bot evasion or prohibited automated access are not scraped.
6. **A flat interface beats a feature maze.** Five primary destinations: Overview, Pipeline, Discover, Preparation, Reviews.

## Competitive baseline and differentiation

Common modern trackers already cover important primitives: Kanban job tracking, saved job details, documents, notes, activities and metrics. Path to Offer therefore does not treat “a Kanban board” as innovation.

The differentiating loop is:

- **event-sourced recruiting timeline** — each state transition has an explicit date;
- **application-to-evidence binding** — exact resume version and interview assets can be attached to each role;
- **interview memory** — TXT/DOCX notes become a searchable personal corpus rather than isolated files;
- **local-first/open-source** — usable without an account or backend, with portable JSON export;
- **China-campus-recruiting aware stages** — assessment, multiple technical rounds, HR, offer and signing are first-class states;
- **future evidence graph** — repeated interview questions can be mapped back to preparation assets and project evidence.

## Information architecture

### Overview
Metrics, current pipeline, near-term actions, funnel, review accumulation.

### Pipeline
Kanban + table modes, search and filters, drag-to-change status, role drawer, dated state timeline.

### Discover
Discovery inbox and source registry. External job aggregators open in a dedicated tab; job records can be promoted into the pipeline.

### Preparation
Resume version registry plus links to project/interview assets. Initial owner integration points to `MLliu6/26-27-interview`.

### Reviews
Import `.txt` and `.docx`; store extracted text locally; associate with a job in a later iteration.

## Interaction language applied from the supplied Vibe Coding handbook

The implementation intentionally uses a small set of interaction patterns instead of decorating every surface:

- Page Transition / Fade Up for view changes;
- Hover Lift for clickable cards;
- Button Press for explicit click feedback;
- Drawer for job editing;
- Modal for small creation flows;
- Active / Selected State for navigation and segmented controls;
- Focus Highlight for form fields;
- Kanban Drag for pipeline movement;
- Toast for save/import/status feedback;
- Theme Accent Switch with ten muted palettes;
- Smooth Scroll and `prefers-reduced-motion` support.

Animations stay in the 0.2–0.4 s range and primarily use transform/opacity to avoid layout-jank.

## v0.2 candidates

- IndexedDB document store for resume/PDF attachments.
- Optional encrypted cross-device sync (GitHub private Gist, user-owned Supabase, or WebDAV adapter).
- Job↔review binding UI and structured question/answer tags.
- Two-hour GitHub Actions discovery pipeline for explicitly allowed sources.
- Browser extension / bookmarklet for “Save to Path to Offer”.
- Resume/JD matching executed locally or via user-selected model provider.
- Calendar export and reminder generation.
- Analytics: response latency, interview conversion, source quality, role-family funnel, time-in-stage.
