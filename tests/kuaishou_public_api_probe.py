#!/usr/bin/env python3
import json
import sys
from typing import Any

import requests

URL = "https://campus.kuaishou.cn/recruit/campus/e/api/v1/open/positions/simple"
PROJECTS = {
    "fulltime_2027": "20271779425607",
    "retention_intern_2027": "20271772783534",
}
PAGES = (1, 7, 8, 13, 23)


def scalar_meta(value: Any, prefix: str = "root", depth: int = 0) -> dict[str, Any]:
    out = {}
    if depth > 4:
        return out
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}"
            low = str(key).lower()
            if not isinstance(child, (dict, list)) and any(x in low for x in ("total", "count", "page", "size", "num")):
                out[path] = child
            elif isinstance(child, (dict, list)):
                out.update(scalar_meta(child, path, depth + 1))
    return out


def rows_from(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, dict):
        for key in ("list", "rows", "records", "positions", "data"):
            rows = result.get(key)
            if isinstance(rows, list):
                return [x for x in rows if isinstance(x, dict)]
    return []


def fetch(project: str, page: int) -> dict[str, Any]:
    response = requests.post(
        URL,
        json={"recruitSubProjectCodes": [project], "pageSize": 10, "pageNum": page},
        timeout=20,
        headers={"User-Agent": "Mozilla/5.0 Path-to-Offer public recruitment regression"},
    )
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or payload.get("code") not in (0, 200, "0", "200", None):
        raise RuntimeError(f"unexpected response: {payload!r}")
    result = payload.get("result")
    rows = rows_from(result)
    return {
        "page": page,
        "meta": scalar_meta(result),
        "count": len(rows),
        "ids": [str(x.get("id") or x.get("code") or "") for x in rows],
        "names": [str(x.get("name") or "") for x in rows[:3]],
    }


def main() -> int:
    report = {}
    for label, project in PROJECTS.items():
        pages = [fetch(project, page) for page in PAGES]
        report[label] = {"project": project, "pages": pages}
        print(json.dumps({label: report[label]}, ensure_ascii=False))
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
