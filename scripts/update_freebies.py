#!/usr/bin/env python3
"""Refresh data/freebies.json from Epic freeGamesPromotions API + curated stores."""
from __future__ import annotations

import json
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "freebies.json"
CHANNELS = ROOT / "data" / "discord_channels.json"
MSK = timezone(timedelta(hours=3), name="MSK")
EPIC_URL = (
    "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
    "?locale=ru&country=RU&allowCountries=RU"
)
UA = "NexusPulseFreebiesBot/1.1 (+static portal updater)"


def fetch_json(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def claim_url_for(element: dict) -> str:
    mappings = (element.get("catalogNs") or {}).get("mappings") or []
    for m in mappings:
        slug = m.get("pageSlug")
        if slug:
            return f"https://store.epicgames.com/ru/p/{slug}"
    slug = element.get("productSlug") or element.get("urlSlug")
    if slug and slug not in {"[]", "null"}:
        slug = str(slug).split("/")[0]
        return f"https://store.epicgames.com/ru/p/{slug}"
    return "https://store.epicgames.com/ru/free-games"


def parse_epic_free() -> list[dict]:
    """Current + upcoming 100% off promotions from public Epic API."""
    data = fetch_json(EPIC_URL)
    elements = (
        ((data.get("data") or {}).get("Catalog") or {}).get("searchStore") or {}
    ).get("elements") or []
    items: list[dict] = []
    seen: set[str] = set()

    def add(el: dict, end_iso: str, kind: str) -> None:
        title = (el.get("title") or "").strip()
        if not title or title.lower() in {"epic games store", "free games"}:
            return
        key = title.lower()
        if key in seen:
            return
        seen.add(key)
        until = end_iso[:10] if end_iso else (datetime.now(MSK) + timedelta(days=7)).date().isoformat()
        eid = el.get("id") or el.get("offerId") or f"epic-{len(items)}"
        items.append(
            {
                "id": f"epic-{eid}",
                "store": "Epic Games",
                "title": title,
                "until": until,
                "claimUrl": claim_url_for(el),
                "note": "Текущая раздача Epic" if kind == "current" else "Скоро бесплатно на Epic",
                "status": kind,
            }
        )

    for el in elements:
        promos = el.get("promotions") or {}
        for bucket, kind in (
            ("promotionalOffers", "current"),
            ("upcomingPromotionalOffers", "upcoming"),
        ):
            for block in promos.get(bucket) or []:
                for offer in block.get("promotionalOffers") or []:
                    disc = offer.get("discountSetting") or {}
                    pct = disc.get("discountPercentage")
                    # Epic marks free as PERCENTAGE 0
                    if disc.get("discountType") == "PERCENTAGE" and pct == 0:
                        add(el, offer.get("endDate") or "", kind)

    # Prefer current first
    items.sort(key=lambda x: (0 if x.get("status") == "current" else 1, x.get("until") or ""))
    return items


def curated_extras() -> list[dict]:
    now = datetime.now(MSK)
    month_end = (now.replace(day=28) + timedelta(days=8)).replace(day=1) - timedelta(days=1)
    until = month_end.date().isoformat()
    return [
        {
            "id": "steam-f2p-always",
            "store": "Steam",
            "title": "Counter-Strike 2 / Dota 2 / Warframe",
            "until": "2099-12-31",
            "claimUrl": "https://store.steampowered.com/genre/Free%20to%20Play/",
            "note": "Постоянно бесплатные хиты",
        },
        {
            "id": f"gog-giveaway-{now.strftime('%Y-%m')}",
            "store": "GOG",
            "title": "GOG Giveaway / free spotlight",
            "until": until,
            "claimUrl": "https://www.gog.com/en/games?priceRange=0,0&discounted=true",
            "note": "Проверяй актуальный giveaway на GOG",
        },
        {
            "id": f"prime-{now.strftime('%Y-%m')}",
            "store": "Prime Gaming",
            "title": "Prime Gaming monthly drop",
            "until": until,
            "claimUrl": "https://gaming.amazon.com/",
            "note": "Требуется подписка Amazon Prime",
        },
    ]


def maybe_discord_post() -> None:
    """Discord posting moved to the auto-feed (#🎁раздачи, deduped): scripts/discord_feeds.py."""
    return


def main() -> int:
    now = datetime.now(MSK).isoformat(timespec="seconds")
    epic: list[dict] = []
    err = None
    try:
        epic = parse_epic_free()
    except Exception as exc:  # noqa: BLE001
        err = str(exc)
        print(f"[update_freebies] Epic API failed: {exc}", file=sys.stderr)

    items = epic + curated_extras()
    # Drop status field from public JSON (optional keep)
    for it in items:
        it.pop("status", None)

    source = "epic-promotions-api+curated" if epic else "curated-fallback"
    note = "Epic Free Games API (RU) + кураторский Steam/GOG/Prime."
    if err:
        note += f" Epic error: {err}"

    payload = {
        "updatedAt": now,
        "source": source,
        "note": note,
        "items": items,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT} ({len(items)} items, source={source})")
    maybe_discord_post()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
