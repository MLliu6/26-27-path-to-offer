# Privacy, local accounts and encrypted sync

## Default behavior

Path to Offer is local-first. Resume files are parsed in the browser and are not committed to the public repository. Guest-mode records use browser storage. When a local account is unlocked, the application stores that account state as an AES-GCM encrypted vault instead of keeping the ordinary application-state key.

The application must not use a public Git commit as temporary resume storage. Deleting a file in a later commit does not guarantee removal from Git history, forks, caches, mirrors, workflow logs or audit records. The same restriction applies to interview notes, salary information, phone numbers and e-mail addresses.

## Custom username and password

A local account derives an encryption key from:

- normalized username;
- password;
- a random 128-bit salt;
- PBKDF2-HMAC-SHA-256 with 310,000 iterations.

The state is encrypted with AES-256-GCM. The password is never written to `localStorage` or included in an export file.

Without a configured sync endpoint, the same username and password separate and unlock accounts on the same device. Cross-device movement is available through an encrypted vault export/import. The product must not claim automatic cross-device recovery while `syncApiBase` is empty.

## Optional cross-device sync

`backend/cloudflare-worker.js` implements the server contract expected by the browser:

```text
GET /v1/vault/{accountId}
PUT /v1/vault/{accountId}
X-PTO-Auth: <password-derived bearer>
```

The server stores an opaque encrypted envelope. By default, remote state excludes raw resume text while retaining parsed directions, skills, resume metadata, applications, timelines and interview records. Set `syncRawResumeText: true` only after an explicit product/privacy decision.

Deployment requires a Cloudflare account and a KV namespace. Copy `backend/wrangler.toml.example`, create the namespace, deploy the Worker, and set `syncApiBase` in `config.js`. Until then the UI labels sync as unconfigured rather than simulating success.

## Resume parser diagnostics

The profile inspector offers **导出匿名解析诊断**. It exports:

- detected resume sections and their weights;
- extracted directions, skills, degree, graduation year and role hypotheses;
- short redacted section previews;
- parser quality counters.

The exporter masks common e-mail, phone, Chinese ID, URL and contact-handle patterns, as well as the detected display name. It is still the user's responsibility to review the JSON before sharing it.

## Source-panel password gate

The source-health panel is protected by a UI access gate because its operational details are not useful to ordinary candidates. This is not a security boundary: the source registry and generated data are public in the repository. The passphrase must be rotated before broader public promotion, and secrets must never be placed in public JavaScript.
