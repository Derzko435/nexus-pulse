#!/usr/bin/env python3
"""Refresh data/freebies.json from Epic freeGamesPromotions API + curated stores.

data/freebies.json keeps its original fields (id, store, title, until, claimUrl, note) for the SPA,
Discord and Telegram. Epic items additionally carry (additive, optional for consumers):
  startsAt / endsAt — full ISO datetimes in MSK from the API `promotions` (e.g. 2026-10-01T18:00:00+03:00)
  status            — "now" (free right now) or "upcoming" (announced, not free yet)
  price_rub         — regular price in roubles for region RU, when the API provides it
  image             — cover URL (OfferImageWide, else Thumbnail)
The file is rewritten only when something besides `updatedAt` changes.

data/freebies_archive.json — append-only history of real giveaways (curated placeholder rows are never
archived), deduplicated by store + id + startsAt; each entry records `firstSeen`. Existing entries are
never modified or removed.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "freebies.json"
ARCHIVE = ROOT / "data" / "freebies_archive.json"
CHANNELS = ROOT / "data" / "discord_channels.json"
MSK = timezone(timedelta(hours=3), name="MSK")
EPIC_URL = (
    "https://store-site-backend-static.ak.epicgames.com/freeGamesPromotions"
    "?locale=ru&country=RU&allowCountries=RU"
)
UA = "NexusPulseFreebiesBot/1.1 (+static portal updater)"
# curated placeholder rows (not concrete giveaways) — same filter as np_digest.py / discord_feeds.py
CURATED_RE = re.compile(r"(-always$|^gog-giveaway|^prime-)")


def fetch_json(url: str, timeout: int = 30) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8", "replace"))


def parse_utc(value) -> datetime | None:
    try:
        d = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else None


def msk_iso(value) -> str:
    d = parse_utc(value)
    return d.astimezone(MSK).replace(microsecond=0).isoformat() if d else ""


def price_rub(el: dict) -> int | None:
    """Regular (undiscounted) price in roubles, only when the API answers in RUB."""
    tp = (el.get("price") or {}).get("totalPrice") or {}
    if tp.get("currencyCode") != "RUB":
        return None
    try:
        decimals = int((tp.get("currencyInfo") or {}).get("decimals", 2))
        value = int(tp.get("originalPrice") or 0) / (10 ** decimals)
    except (TypeError, ValueError):
        return None
    return int(round(value)) if value > 0 else None


def image_for(el: dict) -> str:
    imgs = {k.get("type"): k.get("url") for k in el.get("keyImages") or [] if isinstance(k, dict)}
    for t in ("OfferImageWide", "Thumbnail", "OfferImageTall"):
        u = str(imgs.get(t) or "")
        if u.startswith("https://"):
            return u
    return ""


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
    now = datetime.now(MSK)

    def add(el: dict, offer: dict, kind: str) -> None:
        title = (el.get("title") or "").strip()
        if not title or title.lower() in {"epic games store", "free games"}:
            return
        key = title.lower()
        if key in seen:
            return
        seen.add(key)
        end_iso = offer.get("endDate") or ""
        until = end_iso[:10] if end_iso else (datetime.now(MSK) + timedelta(days=7)).date().isoformat()
        eid = el.get("id") or el.get("offerId") or f"epic-{len(items)}"
        starts, ends = msk_iso(offer.get("startDate")), msk_iso(end_iso)
        status = "now" if kind == "current" else "upcoming"
        if starts and datetime.fromisoformat(starts) > now:
            status = "upcoming"
        item = {
            "id": f"epic-{eid}",
            "store": "Epic Games",
            "title": title,
            "until": until,
            "claimUrl": claim_url_for(el),
            "note": "Текущая раздача Epic" if status == "now" else "Скоро бесплатно на Epic",
            # additive fields (see module docstring)
            "status": status,
        }
        if starts:
            item["startsAt"] = starts
        if ends:
            item["endsAt"] = ends
        price = price_rub(el)
        if price:
            item["price_rub"] = price
        img = image_for(el)
        if img:
            item["image"] = img
        desc = re.sub(r"\s+", " ", str(el.get("description") or "")).strip()
        if desc and desc.lower() != key:
            item["_description"] = desc[:400]  # archive only, not written to freebies.json
        items.append(item)

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
                        end = parse_utc(offer.get("endDate"))
                        if end and end <= now:
                            continue  # already over (stale CDN answer)
                        add(el, offer, kind)

    # Prefer current first
    items.sort(key=lambda x: (0 if x.get("status") == "now" else 1, x.get("until") or ""))
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
            # Prime Gaming was folded into Amazon Luna ("Free Games with Prime"); gaming.amazon.com now
            # redirects to luna.amazon.com/claims (checked 28.09.2026, Amazon help: nodeId=GYASXBBWEH247EPQ)
            "store": "Amazon Luna (Prime)",
            "title": "Free Games with Prime — игры месяца",
            "until": until,
            "claimUrl": "https://luna.amazon.com/claims/home",
            "note": "Требуется подписка Amazon Prime, набор игр зависит от страны",
        },
    ]


def maybe_discord_post() -> None:
    """Discord posting moved to the auto-feed (#🎁раздачи, deduped): scripts/discord_feeds.py."""
    return


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_if_changed(path: Path, text: str) -> bool:
    if path.exists() and path.read_text(encoding="utf-8") == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def archive_key(it: dict) -> str:
    return f"{it.get('store')}|{it.get('id')}|{it.get('startsAt') or ''}"


def update_archive(items: list[dict], seen_at: str) -> int:
    """Append real giveaways (never curated rows) that are not in the archive yet. Returns count added."""
    data = load_json(ARCHIVE, {}) or {}
    entries = [x for x in data.get("items") or [] if isinstance(x, dict)]
    known = {archive_key(x) for x in entries}
    added = 0
    for it in items:
        if CURATED_RE.search(str(it.get("id") or "")) or not it.get("startsAt"):
            continue  # only concrete giveaways with a known start
        k = archive_key(it)
        if k in known:
            continue
        known.add(k)
        entry = {"store": it["store"], "id": it["id"], "title": it["title"], "startsAt": it["startsAt"],
                 "endsAt": it.get("endsAt") or "", "claimUrl": it.get("claimUrl") or ""}
        for f in ("price_rub", "image"):
            if it.get(f):
                entry[f] = it[f]
        if it.get("_description"):
            entry["description"] = it["_description"]
        entry["firstSeen"] = seen_at
        entries.append(entry)
        added += 1
    if not added and ARCHIVE.exists():
        return 0
    payload = {
        "about": "Append-only history of real giveaways seen by scripts/update_freebies.py "
                 "(key: store + id + startsAt; curated placeholder rows are not archived). Do not edit by hand.",
        "items": entries,
    }
    write_if_changed(ARCHIVE, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return added


def main() -> int:
    now = datetime.now(MSK).isoformat(timespec="seconds")
    epic: list[dict] = []
    err = None
    try:
        epic = parse_epic_free()
    except Exception as exc:  # noqa: BLE001
        err = str(exc)
        print(f"[update_freebies] Epic API failed: {exc}", file=sys.stderr)

    added = update_archive(epic, now) if epic else 0
    items = epic + curated_extras()
    for it in items:
        it.pop("_description", None)  # archive-only

    source = "epic-promotions-api+curated" if epic else "curated-fallback"
    note = "Epic Free Games API (RU) + кураторский Steam/GOG/Prime (Amazon Luna)."
    if err:
        note += f" Epic error: {err}"

    payload = {
        "updatedAt": now,
        "source": source,
        "note": note,
        "items": items,
    }
    # keep the file (and its updatedAt) untouched when nothing else changed: no commit churn every 2 hours
    old = load_json(OUT, {}) or {}
    if {k: v for k, v in old.items() if k != "updatedAt"} == {k: v for k, v in payload.items() if k != "updatedAt"}:
        print(f"{OUT} unchanged ({len(items)} items, source={source}); archive +{added}")
    else:
        write_if_changed(OUT, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
        print(f"Wrote {OUT} ({len(items)} items, source={source}); archive +{added}")
    maybe_discord_post()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
