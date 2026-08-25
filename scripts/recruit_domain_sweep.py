#!/usr/bin/env python3
"""Run one bounded shard of the expanded public recruitment-domain catalogue."""
from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CATALOG = DATA / "recruit_domain_catalog.json"
STATUS = DATA / "source_status.json"


def clean(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def stable_order(entry: dict[str, Any]) -> tuple[str, str]:
    raw = f"{clean(entry.get('company')).lower()}|{clean(entry.get('start_url')).lower()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest(), raw


def parse_force() -> set[str]:
    raw = os.getenv("PTO_RECRUIT_SWEEP_FORCE_COMPANIES", "")
    return {clean(x) for x in raw.replace("，", ",").split(",") if clean(x)}


def select(entries: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    sweepable = [x for x in entries if isinstance(x, dict) and x.get("sweep_enabled", True) and clean(x.get("start_url"))]
    ordered = sorted(sweepable, key=stable_order)
    force = parse_force()
    forced = [x for x in ordered if clean(x.get("company")) in force]
    non_forced = [x for x in ordered if clean(x.get("company")) not in force]

    max_targets = max(1, min(40, int(os.getenv("PTO_RECRUIT_SWEEP_MAX_TARGETS", "16"))))
    shard_count = max(1, math.ceil(len(non_forced) / max_targets)) if non_forced else 1
    raw_index = os.getenv("PTO_RECRUIT_SWEEP_SHARD_INDEX", "").strip()
    if raw_index:
        shard_index = int(raw_index) % shard_count
        shard_mode = "explicit"
    else:
        # Default cadence is one run per two-hour bucket. A separate hourly/odd-
        # hour workflow still advances this deterministically without state.
        shard_index = int(time.time() // 3600) % shard_count
        shard_mode = "clock-hour"
    start = shard_index * max_targets
    normal = non_forced[start : start + max_targets]

    selected: list[dict[str, Any]] = []
    seen = set()
    for entry in [*forced, *normal]:
        key = clean(entry.get("id")) or clean(entry.get("start_url"))
        if key and key not in seen:
            selected.append(entry)
            seen.add(key)

    return selected, {
        "catalog_sweepable": len(sweepable),
        "max_targets": max_targets,
        "shard_count": shard_count,
        "shard_index": shard_index,
        "shard_mode": shard_mode,
        "forced_companies": sorted(force),
        "forced_targets": len(forced),
        "selected_targets": len(selected),
    }


def main() -> int:
    catalog = load(CATALOG)
    entries = [x for x in (catalog.get("sources") or []) if isinstance(x, dict)]
    if not entries:
        raise RuntimeError("recruit domain catalogue is empty; run recruit_domain_expander.py first")
    selected, meta = select(entries)
    if not selected:
        print(json.dumps({**meta, "message": "empty shard"}, ensure_ascii=False))
        return 0

    # Import after catalogue selection so normal syntax/unit users do not need a
    # browser. The proven browser harvester is reused instead of maintaining a
    # second JSON/DOM job parser.
    from scripts import priority_browser_harvester as h

    previous_status = load(STATUS)
    previous_priority = next(
        (x for x in previous_status.get("sources", []) if isinstance(x, dict) and x.get("name") == "priority-browser-official"),
        None,
    )

    runtime = Path(tempfile.gettempdir()) / "pto-recruit-domain-sweep.json"
    runtime.write_text(json.dumps({
        "version": 1,
        "policy": "Auto-expanded reviewed employer recruiting surfaces; public browser UI/XHR/DOM only.",
        "sources": selected,
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    h.REGISTRY = runtime
    h.NAV_TIMEOUT = max(7_000, min(20_000, int(os.getenv("PTO_RECRUIT_SWEEP_TIMEOUT_MS", "14000"))))
    rc = h.main()

    # The shared harvester intentionally writes its established status group.
    # Rename this run to a separate group and restore the real priority-browser
    # status so the bounded sweep never erases production diagnostics.
    status = load(STATUS)
    groups = [x for x in status.get("sources", []) if isinstance(x, dict)]
    generated = next((x for x in groups if x.get("name") == "priority-browser-official"), None)
    groups = [x for x in groups if x.get("name") != "priority-browser-official" and x.get("name") != "recruit-domain-sweep"]
    if generated:
        generated = dict(generated)
        generated["name"] = "recruit-domain-sweep"
        generated["label"] = "招聘域名图谱 · 轮转真实浏览器巡检"
        diag = dict(generated.get("diagnostics") or {})
        diag.update(meta)
        diag["selected"] = [
            {"id": x.get("id"), "company": x.get("company"), "start_url": x.get("start_url"), "origin": x.get("origin")}
            for x in selected
        ]
        diag["catalog_total"] = int(catalog.get("source_count") or len(entries))
        generated["diagnostics"] = diag
        groups.insert(0, generated)
    if previous_priority:
        groups.insert(0, previous_priority)
    status["sources"] = groups
    STATUS.write_text(json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(json.dumps({
        **meta,
        "selected_companies": [x.get("company") for x in selected],
        "shared_harvester_rc": rc,
        "fresh_jobs": (generated or {}).get("fresh_count", 0),
        "retained_jobs": (generated or {}).get("count", 0),
    }, ensure_ascii=False))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
