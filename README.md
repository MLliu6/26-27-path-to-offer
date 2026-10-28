# Path to Offer

A browser workspace for 2027 graduate recruiting: discover opportunities, understand resume fit, track applications and prepare for interviews.

**[Open Path to Offer](https://mlliu6.github.io/26-27-path-to-offer/)**

## Version 1.6

- Responsive desktop/mobile navigation, a path-shaped SVG identity, locally served Manrope, Chinese system typography and light/dark appearances.
- Encrypted local accounts, duplicate-account protection, cross-tab write protection, encrypted export and restoration on another device.
- PDF/DOCX/TXT parsing with editable confirmation, persistent degree/cohort overrides and locally bundled parsing libraries.
- Explainable matching using role function, required skills, career stage, degree and cohort evidence. Explicit title cohorts take precedence over conflicting index labels.
- An industry directory of official recruiting sites, observed positions and daily source integrity checks.
- Application timelines, follow-ups, quick status changes, undo, resume versions and interview reviews.

## Personal data

Account data stays in the current browser under the existing `pto.secure.local.v2.*` keys. Passwords derive an AES-GCM key using PBKDF2. Login reads the existing encrypted snapshot. Local saving retains resume text.

Use **Account → Export encrypted backup**, import that file on another device, and log in with the original password. New users create their own device account. Optional repository synchronization requires a user-owned **private** GitHub repository and a token scoped to that repository.

Public deployments contain application source, public recruiting information, fonts and parsing libraries. Tests use synthetic accounts and documents.

## Sources

- [Official industry directory](sources/sector_sources_v16.json)
- [Latest integrity audit](data/source_integrity_audit.json)
- [Observed official positions](data/jobs_verified_v16.json)
- [Daily source workflow](.github/workflows/source-integrity-v16.yml)

The audit records response status, final URLs, access restrictions, observed positions, unknown cohorts, expired records, announcement pages and share links. Job observation dates and catalog-generation dates are tracked separately. Source adapters preserve source IDs, job IDs and extended descriptions.

Coverage is measured in the audit report. Some sites require a normal browser visit; the directory provides direct official entry points.

## Run and verify

The application is buildless:

```sh
python -m http.server 8765 --bind 127.0.0.1
```

```sh
node tests/matching_resume_v16.mjs
node tests/matching_adversarial_v16.mjs
node tests/account_vault_security.mjs
node tests/workspace_v15.mjs
python -m unittest tests.test_source_integrity_v16
```

Browser tests require Playwright and Chromium:

```sh
npm install --no-save playwright
npx playwright install chromium
node tests/workspace_v16.mjs
node tests/matching_resume_browser_v16.mjs
node tests/frontend_accessibility_v16.mjs
```

`PTO_TEST_URL` selects another preview URL. `PTO_BROWSER_EXECUTABLE` selects an installed Chromium browser. The [CI workflow](.github/workflows/ci.yml) runs source, matching, account, parsing, accessibility and mobile checks.

See [the v1.6 review record](docs/REVIEW_V16.md) and [third-party notices](THIRD_PARTY_NOTICES.md). Application code is MIT licensed.
