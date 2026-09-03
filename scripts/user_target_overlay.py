#!/usr/bin/env python3
"""Audit user-curated target positions against live feeds and overlay missing leads.

The overlay is intentionally not a live-source claim. A target is only marked
"present_live" when an existing non-curated feed row matches its employer and
position id/title. Missing targets are added to the priority feed as searchable
leads with an explicit "待官网实时复核" batch label. A later live employer row
wins naturally because curated rows are removed before each audit and appended
only when the target is still missing.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MANIFEST = ROOT / "sources" / "user_target_positions_20260903.json"
PRIORITY = DATA / "jobs_priority.json"
DOMESTIC = DATA / "jobs_cn.json"
AUDIT = DATA / "target_position_audit.json"
SOURCE = "curated-target:20260903"


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def norm(value: Any) -> str:
    text = clean(value).lower()
    text = text.replace("（", "(").replace("）", ")").replace("—", "-").replace("·", " ")
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", text)


def company_norm(value: Any) -> str:
    text = norm(value)
    aliases = {
        "shopee深圳虾皮信息科技有限公司": "shopee",
        "shopee": "shopee",
        "小鹏汽车": "小鹏集团",
        "小鹏集团": "小鹏集团",
        "kimi": "月之暗面",
        "moonshot": "月之暗面",
        "月之暗面": "月之暗面",
        "智谱ai": "智谱ai",
        "智谱": "智谱ai",
        "千寻智能spiritai": "千寻智能spiritai",
    }
    return norm(aliases.get(text, text))


def load(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def rows(path: Path) -> list[dict[str, Any]]:
    payload = load(path)
    return [x for x in (payload.get("jobs") or []) if isinstance(x, dict)]


def row_company(row: dict[str, Any]) -> str:
    return company_norm(row.get("c") or row.get("company"))


def row_role(row: dict[str, Any]) -> str:
    return clean(row.get("r") or row.get("role"))


def row_pid_blob(row: dict[str, Any]) -> str:
    return " ".join(clean(row.get(k)) for k in ("z", "position_id", "u", "n", "apply_url", "notice_url", "id", "i"))


def role_match(expected: str, actual: str) -> bool:
    a = norm(expected)
    b = norm(actual)
    if not a or not b:
        return False
    if a == b or a in b or b in a:
        return True
    # Slash-separated target descriptions often express alternatives rather
    # than a literal employer title. Require at least two meaningful fragments.
    parts = [norm(x) for x in re.split(r"[/、|]", expected) if len(norm(x)) >= 2]
    if parts:
        hits = sum(1 for part in parts if part in b)
        return hits >= min(2, len(parts))
    return False


def live_match(company: str, role: dict[str, Any], live_rows: list[dict[str, Any]]) -> dict[str, Any] | None:
    cn = company_norm(company)
    expected = clean(role.get("title"))
    pid = clean(role.get("position_id"))
    for row in live_rows:
        if row_company(row) != cn:
            continue
        if pid and pid.lower() in row_pid_blob(row).lower():
            return row
    for row in live_rows:
        if row_company(row) == cn and role_match(expected, row_role(row)):
            return row
    return None


def seed_id(company: str, title: str, url: str) -> str:
    return hashlib.sha1(f"{company}|{title}|{url}".encode("utf-8")).hexdigest()[:18]


def seed_row(target: dict[str, Any], role: dict[str, Any], reported_at: str) -> dict[str, Any] | None:
    company = clean(target.get("company"))
    title = clean(role.get("title"))
    url = clean(role.get("url") or target.get("portal_url"))
    if not company or not title or not url.startswith(("http://", "https://")):
        return None
    tier = clean(role.get("tier"))
    note = "用户目标岗位清单；当前实时职位库未命中。此条用于防漏投与持续巡检，不代表岗位仍开放，提交前必须以官方页面为准。"
    if tier:
        note += f" 用户清单优先级：{tier}。"
    out: dict[str, Any] = {
        "i": seed_id(company, title, url),
        "c": company,
        "r": title,
        "x": "目标岗位清单 · 官方入口待实时复核",
        "q": 6,
        "s": SOURCE,
        "l": clean(target.get("location")),
        "u": url,
        "n": url,
        "t": reported_at,
        "b": "2027目标岗位·待官网实时复核",
        "g": "2027届",
        "d": note,
    }
    pid = clean(role.get("position_id"))
    if pid:
        out["z"] = pid
    return {k: v for k, v in out.items() if v not in (None, "")}


def main() -> int:
    manifest = load(MANIFEST)
    reported_at = clean(manifest.get("reported_at")) or datetime.now(timezone.utc).date().isoformat()
    priority_payload = load(PRIORITY)
    priority_rows = [x for x in (priority_payload.get("jobs") or []) if isinstance(x, dict)]
    # Never let yesterday's curated overlay satisfy today's live audit.
    base_priority = [x for x in priority_rows if clean(x.get("s")) != SOURCE]
    live_rows = [*base_priority, *rows(DOMESTIC)]

    audit_rows: list[dict[str, Any]] = []
    seeds: list[dict[str, Any]] = []
    total = present = missing = unseedable = exact_id_targets = exact_id_present = 0
    companies: set[str] = set()

    for target in manifest.get("targets") or []:
        if not isinstance(target, dict):
            continue
        company = clean(target.get("company"))
        if not company:
            continue
        companies.add(company)
        for role in target.get("roles") or []:
            if not isinstance(role, dict) or not clean(role.get("title")):
                continue
            total += 1
            if clean(role.get("position_id")):
                exact_id_targets += 1
            hit = live_match(company, role, live_rows)
            if hit:
                present += 1
                if clean(role.get("position_id")):
                    exact_id_present += 1
                audit_rows.append({
                    "company": company,
                    "target_role": clean(role.get("title")),
                    "position_id": clean(role.get("position_id")),
                    "status": "present_live",
                    "matched_role": row_role(hit),
                    "matched_source": clean(hit.get("s") or hit.get("source")),
                    "matched_url": clean(hit.get("u") or hit.get("apply_url") or hit.get("n") or hit.get("notice_url")),
                })
                continue
            missing += 1
            seed = seed_row(target, role, reported_at)
            if seed:
                seeds.append(seed)
                status = "seeded_target_lead"
            else:
                unseedable += 1
                status = "missing_no_official_url"
            audit_rows.append({
                "company": company,
                "target_role": clean(role.get("title")),
                "position_id": clean(role.get("position_id")),
                "status": status,
                "official_url": clean(role.get("url") or target.get("portal_url")),
            })

    # Preserve live/source rows first. Curated leads are intentionally last so a
    # later employer-direct row wins in the frontend's priority-first dedup.
    priority_payload["schema_version"] = 4
    priority_payload["jobs"] = [*base_priority, *seeds]
    priority_payload["target_overlay_generated_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    PRIORITY.write_text(json.dumps(priority_payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")

    audit = {
        "version": 1,
        "generated_at": priority_payload["target_overlay_generated_at"],
        "manifest": str(MANIFEST.relative_to(ROOT)),
        "companies": len(companies),
        "targets": total,
        "present_live": present,
        "missing_before_overlay": missing,
        "seeded_target_leads": len(seeds),
        "missing_no_official_url": unseedable,
        "exact_id_targets": exact_id_targets,
        "exact_id_present_live": exact_id_present,
        "rows": audit_rows,
    }
    AUDIT.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: audit[k] for k in ("companies", "targets", "present_live", "missing_before_overlay", "seeded_target_leads", "missing_no_official_url", "exact_id_targets", "exact_id_present_live")}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
