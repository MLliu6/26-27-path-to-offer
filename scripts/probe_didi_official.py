#!/usr/bin/env python3
"""Observe anonymous network calls used by DiDi's employer-owned recruiting UI.

Diagnostic only. It does not log in, submit an application, solve a CAPTCHA,
replay credentials, or bypass access controls.
"""
from __future__ import annotations

import re
import shutil
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

PAGES = [
    "https://talent.didiglobal.com/",
    "https://talent.didiglobal.com/campus",
    "https://talent.didiglobal.com/social",
    "https://talent.didiglobal.com/social/p/58333",
]


def browser_path() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("Chrome/Chromium unavailable")


def compact(value: str, limit: int = 3200) -> str:
    return re.sub(r"\s+", " ", value or "").strip()[:limit]


def main() -> int:
    seen: set[str] = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=browser_path(), args=["--no-sandbox", "--disable-dev-shm-usage"])
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="zh-CN")
        page = context.new_page()

        def on_request(req):
            host = (urlparse(req.url).hostname or "").lower()
            if "didiglobal.com" not in host or req.resource_type not in {"xhr", "fetch", "document"}:
                return
            print("DIDI_REQ", req.method, req.resource_type, req.url, "POST", compact(req.post_data or "", 1600), flush=True)

        def on_response(resp):
            host = (urlparse(resp.url).hostname or "").lower()
            if "didiglobal.com" not in host:
                return
            ctype = (resp.headers.get("content-type") or "").lower()
            interesting = "json" in ctype or re.search(r"/(api|job|position|recruit|campus|search|list|detail|front)", resp.url, re.I)
            if not interesting:
                return
            key = f"{resp.status}:{resp.url}"
            if key in seen:
                return
            seen.add(key)
            body = ""
            try:
                body = compact(resp.text())
            except Exception as exc:
                body = f"<{type(exc).__name__}>"
            print("DIDI_RESP", resp.status, ctype, resp.url, "SNIP", body, flush=True)

        page.on("request", on_request)
        page.on("response", on_response)
        for url in PAGES:
            print("DIDI_GOTO", url, flush=True)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                page.wait_for_timeout(10_000)
                print("DIDI_TITLE", page.title(), flush=True)
                print("DIDI_VISIBLE", compact(page.locator("body").inner_text(), 8000), flush=True)
                print("DIDI_URL", page.url, flush=True)
            except Exception as exc:
                print("DIDI_PAGE_ERROR", url, type(exc).__name__, compact(str(exc), 500), flush=True)
        context.close()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
