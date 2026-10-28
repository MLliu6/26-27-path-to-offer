# Third-party notices

## Browser document parsers

The frontend bundles Mammoth 1.8.0 (BSD-2-Clause, Michael Williamson) and
PDF.js 3.11.174 (Apache-2.0, Mozilla Foundation) under `vendor/` for local
DOCX/PDF text extraction. The pinned distributions are published at
`https://www.npmjs.com/package/mammoth/v/1.8.0` and
`https://www.npmjs.com/package/pdfjs-dist/v/3.11.174`.
Their license texts are included as `vendor/LICENSE-mammoth` and
`vendor/LICENSE-pdfjs`. PDF.js runs with `isEvalSupported: false`.

## Manrope font

The bundled Manrope variable font is from
`https://github.com/google/fonts/tree/main/ofl/manrope`, licensed under the
SIL Open Font License 1.1. Its license is included at
`assets/fonts/OFL-Manrope.txt`.

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
