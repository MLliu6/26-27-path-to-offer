# Path to Offer v0.6 — adversarial review

## Trigger

v0.5 made candidate profiling materially better, but the product still failed the most important product-value test: a useful job operating system cannot recommend from a catalogue of only tens of records. The production source-health snapshot before v0.6 contained only 70 normalized jobs. A visually polished tracker cannot compensate for a discovery layer that misses a known company.

v0.6 therefore treats **catalogue coverage + retrieval correctness + recommendation quality** as three independent systems. None is allowed to hide failure in another.

## Ten adversarial users

| Persona / usage depth | Attack | Required behavior | v0.6 response |
|---|---|---|---|
| 1. Visitor, no resume | Search `京东` immediately | Exact retrieval must not depend on match score | Existing query-first path retained; official JD API is now part of the China federation |
| 2. Undergraduate | Upload a simple resume | A weak profile must not hide search results | Explicit search remains independent; recommendation shows profile evidence |
| 3. AI Infra master's candidate | Upload vLLM/CUDA resume, leave search empty | Recommend systems/CUDA roles from a large catalogue | Section-aware profile + federated official job pool |
| 4. VLM/PTQ researcher | Mixed research/project resume | Preserve multiple directions and retrieve sparse niche roles | v5 profile retained; global ATS board expansion increases niche recall |
| 5. AI-chip compiler candidate | Search compiler/NPU | Needs semiconductor/startup coverage, not only internet majors | China Feishu/Beisen seed federation includes AI/chip/startup employers |
| 6. SOE-oriented candidate | Search company rather than role | Company search must remain trustworthy even when profile mismatch | retrieval path ignores recommendation threshold; missing company is surfaced as coverage failure |
| 7. Foreign-company candidate | Search international employer | Need official ATS records with actionable links | Greenhouse/Ashby/Lever/SmartRecruiters/Recruitee/Breezy/BambooHR/Personio federation |
| 8. Heavy desktop user | Search/filter thousands of records | Feed must remain browser-loadable | catalogue JD is deliberately truncated and JSON is minified; official link remains canonical detail source |
| 9. Mobile user | Switch theme and shortlist jobs | No hover dependency; dark theme must remain legible | click-first interactions retained; dark-mode overrides inputs/cards/drawers/nav |
| 10. Maintainer/investor | Inspect source health | Cannot claim coverage that was not measured | source groups publish attempted boards/companies, success counts, failures and actual catalog count |

## P0 findings and remediation

### P0 — catalogue size was not product-grade

**Failure:** `data/source_status.json` showed 70 rows. OfferJack anonymous access exposed 20 rows despite a much larger server-side total; Gank supplied 50; other experimental sources returned zero.

**Change:** introduce a federated harvester that is independent of any single aggregator. It combines:

1. China official company APIs;
2. Feishu Hire company portals;
3. Beisen / zhiye.com public company portals;
4. official global ATS boards;
5. public remote job boards;
6. existing OfferJack/Gank records when publicly available.

### P0 — “crawl the web” cannot mean one brittle scraper

**Failure:** a single reverse-engineered aggregator becomes a single point of failure and inherits its anonymous-access limits.

**Change:** use an adapter federation. Source discovery and source fetching are separated. Public job-list documents may reveal that a company uses a Greenhouse/Ashby/Lever board, but the catalogue row is then fetched directly from the official ATS.

### P0 — theme selector showed blank-looking swatches

**Root cause:** base `setupTheme()` assigned CSS `--sw` to `p[0]` — the palette name such as `Sage` — instead of `p[1]`, the actual color hex.

**Change:** v0.6 repairs every swatch with an explicit `backgroundColor`, marks the selected accent, labels all ten choices, and keeps the existing palette values.

### P1 — dark mode should be designed, not inverted

**Change:** add Light / Dark / System. Dark appearance uses charcoal-green neutrals with the selected Morandi accent as a larger structural color: active navigation, primary actions, match/profile evidence and hover boundaries. It is not `filter: invert()` and does not turn all surfaces into the accent color.

## Data architecture

```text
public aggregators (limited) ─┐
China official APIs ──────────┤
Feishu Hire portals ──────────┤
Beisen portals ────────────────┤
public 2027 lists ──discover──► official ATS boards
Greenhouse/Ashby/Lever/... ───┤
remote public boards ─────────┘
                │
                ▼
       normalize + canonical dedupe
                │
                ▼
       compact browser catalogue
                │
        ┌───────┴────────┐
        ▼                ▼
 explicit retrieval   resume recommendation
        │                │
        └───────┬────────┘
                ▼
          shortlist / pipeline
```

## Deliberate boundaries

- No account/cookie reuse from OfferJack or other sites.
- No CAPTCHA solving, stealth browser fingerprinting, proxy rotation or anti-bot evasion.
- No attempt to turn an explicit anonymous-access denial into a successful request.
- Moka encrypted/obfuscated payload adapters are excluded from the v0.6 federation.
- “All jobs on the internet” is not represented as a measurable guarantee. The product goal is **broad, current, auditable coverage**, with ≥10,000 normalized live records as the first acceptance threshold and source health showing the real number.

## Acceptance gates

- [x] Exact search remains independent of resume threshold/freshness.
- [x] Section-aware resume profile remains inspectable and editable.
- [x] 10 accent swatches render actual distinct colors.
- [x] Light / Dark / System appearance persists locally.
- [x] Dark mode is a designed token set, not CSS inversion.
- [x] Federated harvester supports official China sources and 8 public ATS families.
- [x] Moka/credential/CAPTCHA bypass paths are excluded.
- [x] Source-health diagnostics distinguish discovered boards, successful boards, failed boards and company counts.
- [x] Browser feed is minified and JD-capped for larger catalogues.
- [ ] ≥10,000 live normalized records — **must be verified by the post-merge GitHub Actions run; never pre-claim.**
- [ ] Central/SOE official-site coverage is broad enough to call comprehensive — continue adding official adapters/seed discovery based on measured gaps.

## Next adversarial loop after live refresh

If the post-merge catalogue is below 10k, prioritize the measured bottleneck rather than adding UI features:

1. inspect `official-ats-discovery.boards_discovered / boards_with_jobs`;
2. inspect `china-official-federation.adapters_attempted / companies_with_jobs`;
3. add Workday board discovery and additional official SOE adapters;
4. shard the feed only if browser payload size becomes the limiting factor;
5. rerun the same ten-persona browser journey against a real large catalogue sample.
