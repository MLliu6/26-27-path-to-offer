# v0.1 Adversarial Review

This review was conducted before delivery from four deliberately different perspectives. The purpose was not to praise the prototype but to identify reasons a real candidate would stop using it.

## 1. Engineering / product architecture

### Initial objections

- A public GitHub repository is a dangerous place for real application data, interview notes and resumes.
- “Scrape the whole network every two hours” is not a reliable product contract: sources differ in terms, authentication, anti-bot controls and schemas.
- A tracker that only stores the current status loses the history needed for cycle-time analysis.
- A static GitHub Pages app cannot honestly promise automatic cross-device data sync without a backend or user-owned storage.

### Changes applied

- Personal data is local-first and not committed to the repository.
- Every status transition appends `{status, date}` to the job timeline.
- JSON export is available for backups.
- Discovery is explicitly designed as a source-adapter architecture with compliance boundaries.
- Cross-device encrypted sync is presented as v0.2, not falsely advertised as finished.

## 2. Senior frontend / UX

### Initial objections

- A classic left-side enterprise dashboard would create unnecessary hierarchy for a personal tool.
- Too many animations would conflict with the “calm, useful, everyday” nature of a recruiting tracker.
- Twelve process stages can make a Kanban board horizontally dense.
- Editing a job should not force navigation to a separate page.

### Changes applied

- Five top-level destinations only; no nested sidebar tree.
- Job editing uses a right-side Drawer, preserving context.
- Kanban is horizontally scrollable with snap behavior; table mode provides a dense alternative.
- Motion is restrained to page fade-up, hover lift, button press, drawer/modal transitions and feedback Toasts.
- Mobile navigation becomes a compact floating bottom control.
- `prefers-reduced-motion` is honored.
- Ten muted theme accents are available without changing structural contrast.

## 3. Candidate review — undergraduate / master / PhD

### Undergraduate concern
“我最需要的是别漏掉测评和面试时间，复杂分析以后再说。”

Response: dashboard exposes near-term actions; status carries a date; the pipeline is the primary interaction.

### Master’s concern
“同一个项目针对不同岗位怎么讲、用了哪一版简历，我很容易混。”

Response: job record contains resume version and preparation asset URL, allowing role-specific evidence binding.

### PhD concern
“我的面经和研究项目追问很多，单纯 Kanban 没有长期价值。”

Response: TXT/DOCX reviews are preserved as a corpus; structured question clustering and evidence graph are on the next roadmap.

## 4. Investor / distribution review

### Initial objections

- “Another job tracker” has little defensibility; Huntr, Teal and Simplify already have strong tracking primitives.
- Job aggregation alone is hard to defend and can become a data-access/maintenance business.
- GitHub-only distribution can be powerful for early adopters but is too technical for a mass-market product.

### Product thesis after review

The wedge should be **candidate memory + evidence + timeline**, not “we also have Kanban”. The open-source/local-first implementation is a distribution and trust advantage for technical candidates. If usage validates the workflow, later hosted versions can add encrypted sync, job-source adapters and AI assistance without changing the core data model.

## Remaining launch blockers

1. **Cross-device sync:** v0.1 only syncs application code; user data remains device-local.
2. **Resume file storage:** current release records resume versions/links; binary attachments should move to IndexedDB or optional encrypted object storage.
3. **Automated job refresh:** source adapters need concrete approved sources before a two-hour scheduled collector is enabled.
4. **Structured review extraction:** DOCX/TXT import works, but automatic decomposition into questions, answers, mistakes and action items is not yet implemented.
5. **Public deployment:** GitHub Pages must be enabled once in repository settings after merge.

These blockers are explicitly documented to avoid presenting roadmap items as finished functionality.
