# Path to Offer v0.6 — adversarial review

## Trigger

v0.5 made candidate profiling materially better, but the product still failed the most important product-value test: a useful job operating system cannot recommend from a catalogue of only tens of records. The production source-health snapshot before v0.6 contained only 70 normalized jobs. A visually polished tracker cannot compensate for a discovery layer that misses a known company.

v0.6 therefore treats **catalogue coverage + retrieval correctness + recommendation quality + large-catalogue rendering** as four independent systems. None is allowed to hide failure in another.

## Live acceptance result

The first isolated live federation gate ran on GitHub Actions before merge and passed the product-value threshold with measured data:

- **69,839 raw public official/ATS rows** collected in the run.
- **60,000 normalized rows** retained at the configured browser-catalogue cap.
- **11,685 China official/ATS rows** from 89 attempted company adapters; 84 companies returned jobs.
- **57,890 official global ATS rows** from 417 discovered boards; 416 boards returned jobs.
- **264 public remote-board rows**.
- Direct catalogue presence checks passed for **京东、腾讯、字节**.
- Representative China counts in that run included 腾讯 600、京东 300、京东方 381、智元机器人 386、拓竹 387、智谱AI 222、Momenta 235, plus multiple automotive/AI/software employers.

These are crawler observations from the acceptance workflow, not marketing estimates. The scheduled production refresh uses the same federation architecture and publishes its own measured counts in `data/source_status.json`.

## Ten adversarial users

| Persona / usage depth | Attack | Required behavior | v0.6 response |
|---|---|---|---|
| 1. Visitor, no resume | Search `京东` immediately | Exact retrieval must not depend on match score | Query-first retrieval + live federation proved 京东 is present |
| 2. Undergraduate | Upload a simple resume | A weak profile must not hide search results | Explicit search remains independent; recommendation shows profile evidence |
| 3. AI Infra master's candidate | Upload vLLM/CUDA resume, leave search empty | Recommend systems/CUDA roles from a large catalogue | Section-aware profile + federated official job pool + early-career ranking |
| 4. VLM/PTQ researcher | Mixed research/project resume | Preserve multiple directions and retrieve sparse niche roles | v5 profile retained; global ATS expansion increases niche recall |
| 5. AI-chip compiler candidate | Search compiler/NPU | Needs semiconductor/startup coverage, not only internet majors | China Feishu/Beisen seed federation includes AI/chip/startup employers |
| 6. SOE-oriented candidate | Search company rather than role | Company search must remain trustworthy even when profile mismatch | Retrieval ignores recommendation threshold; coverage gaps remain explicit |
| 7. Foreign-company candidate | Search international employer | Need official ATS records with actionable links | Greenhouse/Ashby/Lever/SmartRecruiters/Recruitee/Breezy/BambooHR/Personio federation |
| 8. Heavy desktop user | Search/filter 60k records | Must not render tens of thousands of DOM cards | Query-first scoring, score cache, 60-row bounded rendering + load more |
| 9. Mobile user | Switch theme and shortlist jobs | No hover dependency; dark theme must remain legible | click-first interactions retained; designed dark tokens cover inputs/cards/drawers/nav |
| 10. Maintainer/investor | Inspect source health | Cannot claim coverage that was not measured | source groups publish attempted boards/companies, success counts, failures and actual catalogue count |

## P0 findings and remediation

### P0 — catalogue size was not product-grade

**Failure:** `data/source_status.json` showed 70 rows. OfferJack anonymous access exposed 20 rows despite a much larger server-side total; Gank supplied 50; other experimental sources returned zero.

**Change:** introduce a federated harvester independent of any single aggregator. It combines China official APIs, public Feishu Hire, Beisen/zhiye.com portals, official global ATS boards, public remote boards and existing public aggregator surfaces.

**Measured result:** the live gate reached the configured **60,000-row cap** and passed direct `京东`/`腾讯`/`字节` presence checks.

### P0 — “crawl the web” cannot mean one brittle scraper

**Failure:** a single reverse-engineered aggregator becomes a single point of failure and inherits its anonymous-access limits.

**Change:** source discovery and source fetching are separated. Public 2027 list documents may reveal that an employer uses a Greenhouse/Ashby/Lever/etc. board, but the actual catalogue rows are then fetched independently from the employer's official public ATS. China employer APIs/Feishu/Beisen are queried directly through pinned public adapters.

### P0 — 60k results would freeze the original frontend

**Failure:** the original `renderMarket()` joined **every** matching row into both the card DOM and the table DOM. A 60k catalogue would turn a data success into a browser failure.

**Change:** v0.6.1 adds large-catalogue controls:

- explicit queries filter text/company aliases before resume scoring;
- resume scores are cached per profile/preferences/day;
- graduate profiles suppress explicitly senior/staff/principal roles in recommendation mode while explicit search can still retrieve them;
- only 60 result rows/cards are rendered initially, with progressive “load more”;
- expensive location/type/batch option extraction is cached until the catalogue changes;
- UI reports ranking time and shown/total result counts;
- a real Chrome test generates a 60,000-row fixture and asserts bounded DOM rendering plus exact `京东` retrieval.

### P0 — theme selector showed blank-looking swatches

**Root cause:** base `setupTheme()` assigned CSS `--sw` to `p[0]` — the palette name such as `Sage` — instead of `p[1]`, the actual color hex.

**Change:** v0.6 repairs every swatch with an explicit `backgroundColor`, marks the selected accent, labels all ten choices, and keeps the palette open while comparing accents.

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
 query-first          profile + early-career fit
        │                │
        └───────┬────────┘
                ▼
         bounded 60-row DOM
                │
                ▼
          shortlist / pipeline
```

## Deliberate boundaries

- No account/cookie reuse from OfferJack or other sites.
- No CAPTCHA solving, stealth browser fingerprinting, proxy rotation or anti-bot evasion.
- No attempt to turn an explicit anonymous-access denial into a successful request.
- Moka encrypted/obfuscated payload adapters are excluded from the v0.6 federation.
- “All jobs on the internet” is not represented as a literal guarantee. The product goal is **broad, current, auditable coverage**, and each scheduled refresh publishes the actual measured count.
- Full job descriptions remain canonical at official application URLs. The static search catalogue intentionally stores bounded JD text for matching so tens of thousands of rows remain publishable/loadable.

## Acceptance gates

- [x] Exact search remains independent of resume threshold/freshness.
- [x] Section-aware resume profile remains inspectable and editable.
- [x] 10 accent swatches render actual distinct colors.
- [x] Light / Dark / System appearance persists locally.
- [x] Dark mode is a designed token set, not CSS inversion.
- [x] Federated harvester supports official China sources and 8 public ATS families.
- [x] Moka/credential/CAPTCHA bypass paths are excluded.
- [x] Source-health diagnostics distinguish discovered boards, successful boards, failed boards and company counts.
- [x] Browser feed is minified and JD-capped for large catalogues.
- [x] ≥10,000 live normalized records — live gate reached **60,000**.
- [x] Direct live catalogue presence: 京东 / 腾讯 / 字节.
- [x] 60k browser catalogue is protected by query-first ranking and bounded rendering.
- [ ] Central/SOE official-site coverage is broad enough to call comprehensive — this remains a measured source-expansion task, not a solved claim.
- [ ] Cross-device account sync — requires the planned real auth/token-exchange backend and is unrelated to crawler coverage.

## Next adversarial loop

The next work should be driven by actual scheduled-refresh diagnostics rather than visual feature count:

1. measure production `data/jobs.json` payload size and Pages load time;
2. broaden central/SOE official-source discovery where source health shows gaps;
3. add Workday discovery if foreign-company coverage needs it;
4. shard/index the static feed if payload transfer, not DOM rendering, becomes the next bottleneck;
5. calibrate recommendation weights from local outcomes (`不合适` / `加入流程` / actual interview) without weakening explicit retrieval.
