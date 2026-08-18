#!/usr/bin/env python3
"""One-off diagnostic for PDD's public campus recruiting frontend.

The probe opens only anonymous public pages and prints same-origin network
requests/responses so a production adapter can use the site's documented-by-
behaviour public surface. It does not create an account, log in, solve a CAPTCHA,
or replay private credentials.
"""
from __future__ import annotations

import json
import re
import shutil
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright

PAGES = [
    "https://careers.pddglobalhr.com/campus/grad",
    "https://careers.pddglobalhr.com/campus/intern",
    "https://careers.pddglobalhr.com/campus/grad/detail?t=M6S4Z4Bjid",
]


def browser_path() -> str:
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    raise RuntimeError("Chrome/Chromium not available")


def compact(value: str, limit: int = 1800) -> str:
    return re.sub(r"\s+", " ", value or "").strip()[:limit]


def main() -> int:
    seen: set[str] = set()
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            executable_path=browser_path(),
            args=["--no-sandbox", "--disable-dev-shm-usage"],
        )
        context = browser.new_context(viewport={"width": 1440, "height": 1000}, locale="zh-CN")
        page = context.new_page()

        def on_request(req):
            url = req.url
            host = (urlparse(url).hostname or "").lower()
            if "pddglobalhr.com" not in host or url in seen:
                return
            if req.resource_type not in {"xhr", "fetch", "document"}:
                return
            print("PDD_REQ", req.method, req.resource_type, url, "POST", compact(req.post_data or "", 1200), flush=True)

        def on_response(resp):
            url = resp.url
            host = (urlparse(url).hostname or "").lower()
            if "pddglobalhr.com" not in host:
                return
            ctype = (resp.headers.get("content-type") or "").lower()
            interesting = "json" in ctype or re.search(r"/(api|job|position|recruit|campus|search|list|detail)", url, re.I)
            if not interesting:
                return
            key = f"{resp.status}:{url}"
            if key in seen:
                return
            seen.add(key)
            body = ""
            try:
                raw = resp.text()
                if len(raw) <= 3_000_000:
                    body = compact(raw)
            except Exception as exc:  # pragma: no cover - diagnostic only
                body = f"<{type(exc).__name__}>"
            print("PDD_RESP", resp.status, ctype, url, "SNIP", body, flush=True)

        page.on("request", on_request)
        page.on("response", on_response)
        for url in PAGES:
            print("PDD_GOTO", url, flush=True)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60_000)
                page.wait_for_timeout(10_000)
                print("PDD_TITLE", page.title(), flush=True)
                print("PDD_VISIBLE", compact(page.locator("body").inner_text(), 5000), flush=True)
                print("PDD_URL", page.url, flush=True)
                scripts = page.locator("script[src]")
                for idx in range(min(scripts.count(), 40)):
                    src = scripts.nth(idx).get_attribute("src")
                    if src:
                        print("PDD_SCRIPT", src, flush=True)
            except Exception as exc:
                print("PDD_PAGE_ERROR", url, type(exc).__name__, compact(str(exc), 500), flush=True)
        context.close()
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
