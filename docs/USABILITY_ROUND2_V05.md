# Path to Offer v0.5 — Round-2 Usability & Reliability Review

This review starts from actual production failures observed on the GitHub Pages build rather than from presentation polish.

## Ground truth before v0.5

At the start of this round, `data/source_status.json` reported a normalized catalog of only **70** records: 20 anonymous OfferJack records + 50 Gank Interview records. CodeCV returned no compatible table. The experimental Gank public-search collector produced zero additional records because the visible search input was not stable enough for automation. This means the main reason a query such as `京东` returned no actual job row was catalog coverage, not only ranking.

The v0.4 search fix already separated explicit retrieval from resume recommendation, so a direct company query no longer disappears because of match threshold or freshness. v0.5 focuses on the next two weak points: **profile quality** and **catalog breadth**.

## Ten usage-depth trials

The ten trials intentionally vary by how deeply a user engages with the product, not only by academic/technical background.

| Level | User behaviour | Failure sought | v0.5 response |
|---|---|---|---|
| 1 | Opens site and searches a known company without uploading a resume | Search incorrectly depends on profile | Explicit retrieval remains independent of resume matching; official-company fallback remains available |
| 2 | Uploads a plain one-page resume | Text extracts but direction is blank | Section-aware profile engine falls back to full-document evidence and shows parsing quality |
| 3 | Uploads a structured resume with Education / Skills / Internship / Projects | Education/course keywords dominate direction | Skills, internship and project evidence receive higher weights; education receives weak weight |
| 4 | Mixed AI Infra + CUDA candidate | One direction hides the other | Multiple ranked direction hypotheses remain visible with evidence and confidence |
| 5 | VLM + PTQ research candidate | Generic Transformer/CV terms drown quantization | Section-weighted PTQ/research evidence is aggregated across skills/research/projects |
| 6 | Backend candidate searching 京东/美团 | Recommendation filters hide explicit search | Query mode bypasses threshold/freshness; company aliases are preserved |
| 7 | User edits target direction manually | Automatic classifier overwrites explicit intent | Existing user preferences remain authoritative; reparse updates evidence, not the saved preference contract |
| 8 | User clicks suggested role hypothesis | Suggestions are decorative only | v0.5 role chips become direct search actions |
| 9 | Power user inspects source health | UI implies web-wide coverage | Catalog count/source failures remain exposed; another public recruiting table source is added but not pre-counted until the refresh observes it |
| 10 | Full journey: resume → search → save → pipeline → review → insights/export | Enhancement breaks downstream tracker | Existing browser smoke journey remains in CI alongside new section-profile tests |

## Profile-engine change

Before v0.5, even the improved v0.4 engine ultimately treated the resume as a single text bag. That is still vulnerable to false evidence: a course named “computer vision” in Education should not outweigh an internship building a CUDA inference runtime.

v0.5 first detects common resume sections:

- Professional / technical skills
- Internship / work experience
- Projects
- Research / publications
- Education
- Awards
- Summary / objective

It then applies deliberately simple and explainable weights:

`skills 1.45 > experience 1.35 > projects 1.25 > research 1.20 > summary 1.00 > awards 0.70 > education 0.55`

The full resume still contributes context at a lower weight. The output remains deterministic and inspectable; it is not presented as an opaque AI probability.

The UI now shows a **Resume Structure** card: extracted character count, detected section count, evidence count, and section sizes. Users can therefore tell whether “direction not recognized” is caused by a weak taxonomy or a broken PDF/DOCX extraction.

## Catalog change

The catalog remains source-limited, so v0.5 adds another independently accessible public recruiting table source (`job.playoffer.cn`) to the existing normalized source layer. It goes through the same public-only constraints and canonical deduplication as other sources. The product does not claim that this source contributes records until GitHub Actions actually observes and publishes its count.

This matters because a job-search product should distinguish three conditions:

1. **No matching recommendation** — job exists but does not fit the current profile/filter.
2. **No catalog record** — current cached sources do not contain the company/job.
3. **No recruiting entry** — no known official portal or current public record.

Only condition 1 should be described as a matching outcome.

## Automated gates

v0.5 adds deterministic tests for structured resumes:

- AI Infra resume with CV/data-mining courses must still infer AI Infra as primary.
- VLM + PTQ resume must infer quantization as primary and retain multimodal as a secondary direction.
- FPGA/RTL resume with an AI-related award must remain chip/EDA/hardware, not generic AI.
- Section splitting itself is regression-tested.

The existing ten-persona matching suite and the Playwright/Chrome end-to-end browser smoke test remain active.

## Remaining limitations

- A static GitHub Pages client cannot create a genuinely comprehensive Chinese job index by itself; the two-hour GitHub Actions data pipeline is the current server-side substitute.
- Some recruiting aggregators expose only the first anonymous page or use unstable rendered search controls. Those sources must fail visibly rather than be bypassed.
- Resume section detection is heuristic. Complex two-column PDF extraction can still scramble reading order; the new structure card is intended to make that failure visible.
- GitHub login is still not cross-device account sync until a secure OAuth/GitHub App token-exchange backend is provisioned.

## Next acceptance target

Before calling discovery “good”, the live feed should satisfy all of the following:

- hundreds rather than tens of normalized current records;
- direct company retrieval for common targets (京东、腾讯、字节、阿里、美团、百度、华为) from either a current job record or a clearly labelled official-company directory entry;
- resume upload produces a visible primary direction for the existing ten persona regressions;
- recommendation mode can explain at least two positive fit signals for high-ranked roles;
- source-health UI reports actual observed counts and failures rather than aspirational coverage.
