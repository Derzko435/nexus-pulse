#!/usr/bin/env python3
"""Try to refresh data/freebies.json from public pages; keep curated fallback on failure."""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "freebies.json"
MSK = timezone(timedelta(hours=3))


def fetch(url: str, timeout: int = 12) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "NexusPulseFreebiesBot/1.0 (+static portal updater)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def load_fallback() -> dict:
    if OUT.exists():
        return json.loads(OUT.read_text(encoding="utf-8"))
    return {"items": [], "source": "empty"}


def try_epic() -> list[dict]:
    """Best-effort: Epic free games GraphQL often needs specific payload; skip if blocked."""
    items: list[dict] = []
    try:
        # Public store free-games landing — parse titles loosely if HTML available
        html = fetch("https://store.epicgames.com/en-US/free-games")
        titles = re.findall(r'"title"\s*:\s*"([^"]{2,80})"', html)
        seen = set()
        for t in titles:
            if t in seen or t.lower() in {"epic games store", "free games"}:
                continue
            seen.add(t)
            items.append(
                {
                    "id": f"epic-auto-{len(items)}",
                    "store": "Epic Games",
                    "title": t,
                    "until": (datetime.now(MSK) + timedelta(days=7)).date().isoformat(),
                    "claimUrl": "https://store.epicgames.com/ru/free-games",
                    "note": "Авто-парс (может быть неточным)",
                }
            )
            if len(items) >= 3:
                break
    except Exception as exc:  # noqa: BLE001
        print(f"[update_freebies] Epic fetch skipped: {exc}", file=sys.stderr)
    return items


def main() -> int:
    fallback = load_fallback()
    scraped = try_epic()
    now = datetime.now(MSK).isoformat(timespec="seconds")
    if scraped:
        payload = {
            "updatedAt": now,
            "source": "script-scrape+curated",
            "note": "Часть записей обновлена скриптом; остальное — кураторский фолбэк.",
            "items": scraped + [
                i for i in fallback.get("items", []) if i.get("store") != "Epic Games"
            ][:4],
        }
    else:
        payload = dict(fallback)
        payload["updatedAt"] = now
        payload["source"] = fallback.get("source", "curated") + "+script-fallback"
        payload["note"] = (
            "Скрейп не удался — оставлен кураторский список. "
            + str(fallback.get("note", ""))
        ).strip()
        print("[update_freebies] Using curated fallback", file=sys.stderr)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} ({len(payload.get('items', []))} items)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
