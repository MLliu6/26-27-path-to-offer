# Third-party notices

Path to Offer v0.6 uses the following project **at refresh time** as a pinned adapter library. Its source is not bundled into the GitHub Pages frontend.

## Hiring-Radar

- Project: `simonlin1212/Hiring-Radar`
- Repository: https://github.com/simonlin1212/Hiring-Radar
- Pinned commit: `f49ec607e4cb89091a9447c9f527e43d0afdc6a4`
- License: MIT
- Copyright: respective Hiring-Radar contributors

Path to Offer calls/adapts public ATS and official-career-site collectors exposed by that project. The v0.6 federation deliberately excludes its Moka encrypted-payload path and uses only public unauthenticated ATS / official-site surfaces.

The original MIT license remains available in the upstream repository. Runtime pinning is enforced in `.github/workflows/refresh-jobs.yml`.

## Discovery-only public job lists

The public README documents from `speedyapply/2027-SWE-College-Jobs` and `speedyapply/2027-AI-College-Jobs` are used only to discover outgoing **official ATS board identities** (for example a Greenhouse or Ashby board slug). Path to Offer does not copy their job-table rows into its catalogue. After a board is discovered, current records are fetched independently from the employer's official public ATS endpoint.
