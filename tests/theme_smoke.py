#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil

from playwright.sync_api import sync_playwright

BASE="http://127.0.0.1:8000"
EMPTY={"schema_version":3,"generated_at":"2026-08-16T10:00:00Z","jobs":[]}
STATUS={"generated_at":"2026-08-16T10:00:00Z","catalog_count":0,"catalog_target":10000,"sources":[]}


def browser_path():
    for name in ("google-chrome","google-chrome-stable","chromium","chromium-browser"):
        p=shutil.which(name)
        if p:return p
    raise RuntimeError("Chrome/Chromium unavailable")


def main():
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=browser_path(),args=["--no-sandbox","--disable-dev-shm-usage"])
        context=browser.new_context(viewport={"width":1280,"height":900})
        page=context.new_page()
        def route(route):
            u=route.request.url
            if "/data/jobs.json" in u: route.fulfill(status=200,content_type="application/json",body=json.dumps(EMPTY))
            elif "/data/source_status.json" in u: route.fulfill(status=200,content_type="application/json",body=json.dumps(STATUS))
            elif u.startswith("https://cdn.jsdelivr.net/"): route.abort()
            else: route.continue_()
        page.route("**/*",route)
        page.goto(BASE,wait_until="domcontentloaded")
        page.wait_for_selector(".appearance-control",timeout=12000)
        page.locator("#themeBtn").click()
        page.wait_for_selector("#themePopover.show")
        swatches=page.locator(".swatch")
        assert swatches.count()==10
        colors=[swatches.nth(i).evaluate("el => getComputedStyle(el).backgroundColor") for i in range(swatches.count())]
        assert len(set(colors))>=8, colors
        assert all(c not in {"rgba(0, 0, 0, 0)","transparent"} for c in colors)

        # Accent previews intentionally keep the palette open so the user can
        # compare several colors without repeatedly reopening the popover.
        page.locator('[data-theme="3"]').click()
        assert "Lavender" in page.locator("#activeThemeName").inner_text()
        assert page.locator("#themePopover").evaluate("el => el.classList.contains('show')")
        page.locator('[data-appearance-choice="dark"]').click()
        assert page.locator("html").get_attribute("data-appearance")=="dark"
        bg=page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--bg').trim()")
        surface=page.evaluate("getComputedStyle(document.documentElement).getPropertyValue('--surface').trim()")
        assert bg.lower()=="#101512"
        assert surface.lower()=="#171d1a"
        assert page.locator(".panel").count()>0 or page.locator(".market-empty").count()>0

        page.reload(wait_until="domcontentloaded")
        page.wait_for_selector(".appearance-control",timeout=12000)
        assert page.locator("html").get_attribute("data-appearance")=="dark"
        page.locator("#themeBtn").click()
        assert page.locator('[data-appearance-choice="dark"]').evaluate("el => el.classList.contains('active')")
        context.close();browser.close()
    print("Path to Offer theme smoke: PASS")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
