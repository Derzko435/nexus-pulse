#!/usr/bin/env python3
"""Daily Steam price history (RU region, rubles) → data/price_history.json

Sources: data/prices.json (catalog games, refreshed by update_prices.py) and data/deals.json
(current Steam discounts). Games that were tracked before but are in neither file right now
(e.g. a discount has ended) are re-checked directly in the Steam store — no guessing.

Format (compact): {"updatedAt", "days": 180, "items": {"<appid>": [["YYYY-MM-DD", price], ...]}}
Only price *changes* are stored: a new point is appended when the price differs from the last one.
Points older than ~180 days are dropped (the last old point is moved to the window start so the
line stays continuous). If Steam fails, the known history is kept as it is.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timedelta

from np_common import DATA, MSK, fetch_json, log, now_msk_iso, read_json

OUT = DATA / "price_history.json"
DAYS = 180
RECHECK_DAYS = 60   # stop re-checking games that left every list more than 60 days ago
MAX_RECHECK = 300
CHUNK = 25


def current_prices() -> dict[str, int]:
    cur: dict[str, int] = {}
    prices = (read_json(DATA / "prices.json", {}) or {}).get("prices") or {}
    for p in prices.values():
        try:
            cur[str(int(p["appid"]))] = int(round(float(p["final"])))
        except (KeyError, TypeError, ValueError):
            continue
    for d in (read_json(DATA / "deals.json", {}) or {}).get("deals") or []:
        aid = str(d.get("steamAppId") or "")
        price = d.get("neu", d.get("price"))
        if aid.isdigit() and price is not None and (d.get("store") or "Steam") == "Steam":
            try:
                cur.setdefault(aid, int(round(float(price))))
            except (TypeError, ValueError):
                pass
    return cur


def steam_prices(appids: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for i in range(0, len(appids), CHUNK):
        ids = ",".join(appids[i:i + CHUNK])
        try:
            data = fetch_json(f"https://store.steampowered.com/api/appdetails?appids={ids}&cc=ru&filters=price_overview", timeout=30) or {}
        except Exception as e:  # noqa: BLE001
            log(f"[history] steam chunk failed: {e}")
            continue
        for appid, node in data.items():
            d = node.get("data") if isinstance(node, dict) and node.get("success") else None
            po = d.get("price_overview") if isinstance(d, dict) else None
            if po and po.get("currency") == "RUB" and po.get("final") is not None:
                out[str(appid)] = round(int(po["final"]) / 100)
        time.sleep(1.5)
    return out


def main() -> int:
    today = datetime.now(MSK).date()
    t = today.isoformat()
    old = read_json(OUT, {}) or {}
    items: dict[str, list] = old.get("items") or {}
    seen: dict[str, str] = old.get("seen") or {}  # appid → last day it was in prices/deals
    cur = current_prices()
    for aid in cur:
        seen[aid] = t
    # re-check games that dropped out of both lists (discount ended etc.)
    recheck_cut = (today - timedelta(days=RECHECK_DAYS)).isoformat()
    stale = [a for a in items if a not in cur and seen.get(a, "") >= recheck_cut][:MAX_RECHECK]
    if stale:
        got = steam_prices(stale)
        log(f"[history] re-checked {len(stale)} games, got {len(got)} prices")
        cur.update(got)
    changes = 0
    for aid, price in cur.items():
        pts = items.setdefault(aid, [])
        if not pts or pts[-1][1] != price:
            if pts and pts[-1][0] == t:
                pts[-1][1] = price  # several runs a day → keep the latest price of the day
            else:
                pts.append([t, price])
            changes += 1
    # trim to the window
    cut = (today - timedelta(days=DAYS)).isoformat()
    for aid in list(items):
        pts = items[aid]
        older = [p for p in pts if p[0] < cut]
        pts = [p for p in pts if p[0] >= cut]
        if older and (not pts or pts[0][0] > cut):
            pts.insert(0, [cut, older[-1][1]])
        if not pts or (seen.get(aid, "") < cut and len(pts) <= 1):
            items.pop(aid, None)
            seen.pop(aid, None)
        else:
            items[aid] = pts
    payload = {"updatedAt": now_msk_iso(), "days": DAYS, "items": dict(sorted(items.items(), key=lambda kv: int(kv[0]))),
               "seen": {k: v for k, v in sorted(seen.items(), key=lambda kv: int(kv[0])) if k in items}}
    if old.get("items") == payload["items"] and old.get("seen") == payload["seen"]:
        log(f"[history] no changes ({len(items)} games)")
        return 0
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    log(f"[history] {len(items)} games, {changes} new price points")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
