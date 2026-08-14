# v0.2 adversarial review

## Developer / security review

Attack: “A public GitHub Pages app with GitHub login will tempt developers to put the OAuth secret in JavaScript.”

Resolution: login remains an integration boundary until a server-side exchange endpoint exists. The UI does not fake an authenticated session.

Attack: “A scheduled crawler will eventually become an anti-bot bypass project.”

Resolution: the crawler has explicit public-URL checks, robots handling, bounded requests, login/CAPTCHA stop conditions and source-level failure reporting. New adapters must preserve the same contract.

## Senior frontend / UX review

Attack: “The old version makes users enter the application tracker before solving the harder problem: what should I apply to?”

Resolution: `发现` becomes the default first view. Resume upload and the embedded job market now dominate the first screen; pipeline is downstream.

Attack: “A giant OfferJack-style table alone is efficient but cognitively expensive.”

Resolution: cards are the default, dense table is optional, matching reasons are visible, and only five top-level navigation items remain.

Attack: “Fake data makes a product screenshot look full while hiding whether empty-state UX works.”

Resolution: all built-in mock jobs, mock reviews and mock resume versions are removed. Empty states are first-class.

## Candidate review (undergraduate / master / PhD)

Undergraduate: needs obvious eligibility filters and a low-friction shortlist. Graduation year, degree and one-click pipeline promotion address this.

Master: often has several technical directions and multiple resume versions. Active profile, inferred directions and per-job resume binding address this.

PhD: may have a narrow research profile where keyword overlap is misleading. v0.2 exposes why a score exists and avoids calling the rule matcher “AI semantic understanding”. Later embeddings must remain explainable.

## Product / investor review

Attack: “Why is this not another job board?”

Answer: the data source is not the product moat. The differentiator is the closed loop from candidate evidence → discovery decision → application timeline → interview outcome → improved candidate memory.

Attack: “Why would users return?”

The recurring loop is every two-hour feed refresh plus personalized triage, followed by application deadlines and interview-review accumulation. A future notification layer should be based on those user-owned decisions rather than generic job spam.

## Remaining blockers before public launch

- Source coverage is still adapter-limited; “all-network crawling” would be an inaccurate claim today.
- Secure GitHub login/cross-device sync needs a small backend or managed auth service.
- Match calibration needs real user outcomes before weights should be optimized.
- Full-text resume parsing for highly graphical PDFs needs regression tests on diverse resumes.
