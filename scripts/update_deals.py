#!/usr/bin/env python3
"""Refresh data/deals.json from live Steam specials (RU storefront).

Only publishes games that currently have a real discount_percent > 0.
Never invents prices. Cyberpunk etc. appear only when Steam actually discounts them.

Usage:
  python3 scripts/update_deals.py
  python3 scripts/update_deals.py --count 16 --pages 2
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "deals.json"
MSK = timezone(timedelta(hours=3), name="MSK")
UA = "NexusPulse/1.0 (+https://derzko435.github.io/nexus-pulse/; deals fetcher)"

ROW_SPLIT = re.compile(r'<a href="https://store\.steampowered\.com/app/')
TITLE_RE = re.compile(r'class="title">\s*([^<]+?)\s*</span>')
PCT_RE = re.compile(r'class="discount_pct">\s*([^<]+?)\s*</div>')
FINAL_RE = re.compile(r'data-price-final="(\d+)"')
ORIG_RE = re.compile(r'class="discount_original_price">\s*([^<]+?)\s*</div>')
APP_RE = re.compile(r'^(\d+)/')


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "ru-RU,ru;q=0.9"})
    with urllib.request.urlopen(req, timeout=45) as resp:
        return resp.read().decode("utf-8", "replace")


def parse_rub_text(text: str) -> int | None:
    """Parse '1 199 руб' or '1199,00 руб' into integer rubles."""
    if not text:
        return None
    t = text.lower().replace("\xa0", " ").replace("руб.", "руб").strip()
    t = t.replace("руб", "").strip()
    t = t.replace(" ", "").replace(",", ".")
    # keep digits and dot
    m = re.search(r"(\d+(?:\.\d+)?)", t)
    if not m:
        return None
    return int(round(float(m.group(1))))


def minor_to_rub(minor: int) -> int:
    """Steam price units → whole rubles (RU uses 1/100)."""
    return int(round(minor / 100))


def parse_specials_html(html: str) -> list[dict]:
    deals: list[dict] = []
    parts = ROW_SPLIT.split(html)
    for part in parts[1:]:
        m_id = APP_RE.match(part)
        if not m_id:
            continue
        appid = m_id.group(1)
        title_m = TITLE_RE.search(part)
        title = (title_m.group(1).strip() if title_m else "").replace("\u2122", "").replace("®", "").strip()
        if not title:
            continue
        pct_m = PCT_RE.search(part)
        pct_raw = (pct_m.group(1).strip() if pct_m else "")
        pct = 0
        pm = re.search(r"(\d+)", pct_raw.replace("−", "-").replace("–", "-"))
        if pm:
            pct = int(pm.group(1))
        final_m = FINAL_RE.search(part)
        if not final_m or pct <= 0:
            continue
        neu = minor_to_rub(int(final_m.group(1)))
        if neu <= 0:
            continue
        orig_m = ORIG_RE.search(part)
        old = parse_rub_text(orig_m.group(1) if orig_m else "")
        if not old or old <= neu:
            # reconstruct from percent
            old = int(round(neu / max(0.01, (100 - pct) / 100)))
        deals.append(
            {
                "id": f"steam-{appid}",
                "title": title,
                "store": "Steam",
                "old": old,
                "neu": neu,
                "pct": pct,
                "url": f"https://store.steampowered.com/app/{appid}/?curator_clanid=0",
                "steamAppId": appid,
            }
        )
    return deals


def fetch_featuredcategories() -> list[dict]:
    url = "https://store.steampowered.com/api/featuredcategories?cc=ru&l=russian"
    raw = json.loads(fetch(url))
    out: list[dict] = []
    for block in raw.values():
        if not isinstance(block, dict):
            continue
        for it in block.get("items") or []:
            pct = int(it.get("discount_percent") or 0)
            if pct <= 0:
                continue
            appid = str(it.get("id") or "")
            if not appid.isdigit():
                continue
            final = it.get("final_price")
            orig = it.get("original_price")
            if final is None or orig is None:
                continue
            neu = minor_to_rub(int(final))
            old = minor_to_rub(int(orig))
            if neu <= 0 or old <= neu:
                continue
            title = str(it.get("name") or "").replace("\u2122", "").replace("®", "").strip()
            out.append(
                {
                    "id": f"steam-{appid}",
                    "title": title,
                    "store": "Steam",
                    "old": old,
                    "neu": neu,
                    "pct": pct,
                    "url": f"https://store.steampowered.com/app/{appid}/",
                    "steamAppId": appid,
                }
            )
    return out


def fetch_search_pages(pages: int) -> list[dict]:
    deals: list[dict] = []
    for page in range(1, pages + 1):
        url = (
            "https://store.steampowered.com/search/?specials=1&filter=topsellers"
            f"&cc=ru&l=russian&page={page}"
        )
        html = fetch(url)
        deals.extend(parse_specials_html(html))
    return deals


def build_deals(count: int = 14, pages: int = 2) -> dict:
    now = datetime.now(MSK).replace(microsecond=0)
    merged: dict[str, dict] = {}
    for src in (fetch_featuredcategories(), fetch_search_pages(pages)):
        for d in src:
            if d["pct"] <= 0:
                continue
            prev = merged.get(d["id"])
            if not prev or d["pct"] > prev["pct"] or (d["pct"] == prev["pct"] and d["neu"] < prev["neu"]):
                merged[d["id"]] = d
    deals = sorted(merged.values(), key=lambda d: (d["pct"], d["old"] - d["neu"]), reverse=True)
    # drop tiny discounts noise
    deals = [d for d in deals if d["pct"] >= 15]
    deals = deals[:count]
    return {"updatedAt": now.isoformat(), "source": "steam-specials-ru", "deals": deals}


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh NEXUS PULSE deals.json from live Steam specials")
    parser.add_argument("--count", type=int, default=14)
    parser.add_argument("--pages", type=int, default=2)
    args = parser.parse_args()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = build_deals(count=args.count, pages=args.pages)
    if not payload["deals"]:
        raise SystemExit("No live Steam discounts fetched — refusing to write empty/fake deals")
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[NEXUS PULSE] deals.json обновлён → {OUT}")
    print(f"  source=steam-specials-ru  updatedAt={payload['updatedAt']}  deals={len(payload['deals'])}")
    for d in payload["deals"][:5]:
        print(f"  −{d['pct']}%  {d['neu']}₽ (было {d['old']}₽)  {d['title']}")

    # Discord: notable deals are posted by the auto-feed (#💸скидки, deduped via
    # data/discord_posted.json) — scripts/discord_feeds.py / discord_box_sync.sh.
    # The old per-run "post-alert" here re-posted the same top deal every run.

    # sanity: Cyberpunk must not appear unless truly discounted
    for d in payload["deals"]:
        if "cyberpunk" in d["title"].lower() and d["pct"] <= 0:
            raise SystemExit("Cyberpunk with 0% slipped in")


if __name__ == "__main__":
    main()
