# GitHub Pages, login and sync architecture

## What is already live

The public application entry is:

`https://mlliu6.github.io/26-27-path-to-offer/`

The repository is configured in GitHub Pages as:

`Deploy from a branch → main → / (root)`

The old Actions-based Pages workflow has been removed so there is only one deployment path. Access to the public site does not require an account.

## Why a real GitHub login is not implemented with a secret in `config.js`

A static GitHub Pages application is public client-side code. Putting a GitHub OAuth client secret or a reusable access token in it would disclose that credential to every visitor.

The correct boundary is:

```text
Browser at github.io
      |
      | redirect
      v
GitHub authorization
      |
      | authorization code
      v
OAuth proxy / backend
      |
      | secure token exchange
      v
session + encrypted user store
```

`config.js` already exposes `githubClientId` and `githubOAuthProxy` integration points. When a backend is provisioned, the existing `GitHub 登录` button can redirect into that flow.

## Recommended production identity design

Prefer a GitHub App over a broad OAuth App when the product begins serving multiple users. Grant only identity permissions for login by default. Repository permissions should be requested only for users who explicitly choose a GitHub-backed sync mode.

## Sync tiers

The product should support three tiers rather than force everyone into a server:

1. **Local-first** — current default. Resume and job decisions stay in browser storage.
2. **Encrypted cloud sync** — login-based, cross-device encrypted records.
3. **User-owned GitHub sync** — advanced mode writing an encrypted data blob to a private user-controlled repository or similar storage, with explicit permission.

Resume source files should not be committed to the public application repository.

## Current product truth

The public GitHub.io URL is live and usable today. The `GitHub 登录` button represents the intended identity boundary, but **cross-device account sync is not yet implemented**. Until a server-side OAuth/token-exchange and encrypted persistence layer is provisioned, the application must continue to describe itself as Local-first rather than implying that signing into GitHub already restores personal data on another device.
