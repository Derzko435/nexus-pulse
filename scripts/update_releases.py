#!/usr/bin/env python3
"""Release calendar + new games from the Steam store (RU storefront).

data/releases.json  — upcoming PC releases with exact dates (next ~3 months),
                      picked from Steam's most wished-for / pre-ordered games.
data/new_games.json — popular games released in the last ~6 weeks
                      (Steam top sellers filtered by release date).

Only real store data. Adult-only titles are filtered out. If Steam fails, the
previous files are kept.
"""
from __future__ import annotations

import re
import time
from datetime import date, datetime, timedelta

from np_common import (
    DATA, MSK, clean_text, clip, fetch_json, log, now_msk_iso, safe_url, write_json_if_good,
)

RU_MONTHS = {"янв": 1, "фев": 2, "мар": 3, "апр": 4, "мая": 5, "май": 5, "июн": 6, "июл": 7,
             "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12}
ADULT_RE = re.compile(r"(hentai|хентай|erotic|эроти|эроп|waifu|nsfw|sex|milf|tomboy|ntr\b|lewd|nude|18\+|porn|girls vs|succub|harem|гарем)", re.I)
SEARCH = "https://store.steampowered.com/search/results/?query&start={start}&count={count}&{q}&infinite=1&cc=ru&l=russian&ignore_preferences=1&category1=998"
ROW_RE = re.compile(r'<a href="https://store\.steampowered\.com/app/(\d+)/[^"]*"[^>]*class="search_result_row[^"]*"(.*?)</a>', re.S)


def parse_ru_date(s: str) -> date | None:
    s = clean_text(s).lower()
    m = re.search(r"(\d{1,2})\s+([а-я]{3})[а-я]*\.?\s+(\d{4})", s)
    if not m:
        return None
    mon = RU_MONTHS.get(m.group(2))
    if not mon:
        return None
    try:
        return date(int(m.group(3)), mon, int(m.group(1)))
    except ValueError:
        return None


def search_rows(q: str, pages: int, count: int = 100) -> list[dict]:
    rows = []
    for p in range(pages):
        try:
            data = fetch_json(SEARCH.format(start=p * count, count=count, q=q), timeout=40)
        except Exception as e:  # noqa: BLE001
            log(f"[search-fail] {q} p{p}: {e}")
            break
        html = data.get("results_html") or ""
        for appid, body in ROW_RE.findall(html):
            title = clean_text((re.search(r'class="title">([^<]*)<', body) or [None, ""])[1])
            rel = clean_text((re.search(r'search_released[^>]*>\s*([^<]*?)\s*<', body) or [None, ""])[1])
            rows.append({"appid": int(appid), "title": title, "releaseText": rel, "date": parse_ru_date(rel)})
        time.sleep(1.0)
    return rows


def details(appid: int) -> dict | None:
    for cc in ("ru", "us"):
        try:
            data = fetch_json(f"https://store.steampowered.com/api/appdetails?appids={appid}&cc={cc}&l=russian", timeout=30)
        except Exception as e:  # noqa: BLE001
            log(f"[details-fail] {appid}: {e}")
            return None
        node = (data or {}).get(str(appid)) or next(iter((data or {}).values()), {}) or {}
        if node.get("success"):
            return node["data"]
        time.sleep(0.8)
    return None


def is_adult(d: dict, title: str) -> bool:
    ids = set((d.get("content_descriptors") or {}).get("ids") or [])
    if ids & {1, 3, 4}:
        return True
    text = " ".join([title, d.get("short_description") or "", " ".join(g.get("description", "") for g in d.get("genres") or [])])
    if ADULT_RE.search(text):
        return True
    return any((g.get("id") in ("71", "72")) for g in d.get("genres") or [])  # Nudity / Sexual Content genres


CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")


def readable(d: dict) -> bool:
    text = clean_text(d.get("short_description"))
    return bool(text) and len(CJK_RE.findall(text)) < len(text) * 0.2


def price_text(d: dict) -> str:
    if d.get("is_free"):
        return "Бесплатно"
    po = d.get("price_overview") or {}
    if po.get("final_formatted"):
        return clean_text(po["final_formatted"])
    return ""


def make_item(row: dict, d: dict, dt: date) -> dict:
    genres = [clean_text(g.get("description")) for g in d.get("genres") or []][:3]
    plats = [name for key, name in (("windows", "PC"), ("mac", "Mac"), ("linux", "Linux")) if (d.get("platforms") or {}).get(key)]
    return {
        "appid": row["appid"],
        "title": clean_text(d.get("name")) or row["title"],
        "date": dt.isoformat(),
        "image": safe_url(d.get("header_image")),
        "desc": clip(clean_text(d.get("short_description")), 300),
        "genres": genres,
        "platforms": plats or ["PC"],
        "developer": clean_text(", ".join((d.get("developers") or [])[:2])),
        "price": price_text(d),
        "url": f"https://store.steampowered.com/app/{row['appid']}/",
    }


def build_releases(today: date) -> list[dict]:
    horizon = today + timedelta(days=150)
    seen: set = set()

    def pick(q: str, pages: int, count: int = 100, strict: bool = False) -> list[dict]:
        got = []
        for r in search_rows(q, pages=pages, count=count):
            if not r["date"] or (strict and r["date"] <= today):
                continue
            if today <= r["date"] <= horizon and r["appid"] not in seen:
                seen.add(r["appid"]); got.append(r)
        return got

    # 1) pre-orders among top sellers, 2) most wishlisted upcoming games — the releases people wait for
    primary = pick("filter=topsellers&sort_by=Released_DESC", 1, 60, strict=True) + pick("filter=popularwishlist", 3)
    # 3) popular "coming soon" only as a filler when the big list is short
    filler = pick("filter=popularcomingsoon", 2)

    def resolve(rows: list[dict], limit: int, out: list[dict]) -> None:
        for r in rows:
            if len(out) >= limit:
                return
            if ADULT_RE.search(r["title"]):
                continue
            d = details(r["appid"])
            time.sleep(1.1)
            if not d or d.get("type") != "game" or is_adult(d, r["title"]) or not readable(d):
                continue
            rd = d.get("release_date") or {}
            dt = parse_ru_date(rd.get("date") or "") or r["date"]
            if not dt or not (today <= dt <= horizon):
                continue
            item = make_item(r, d, dt)
            if item["image"]:
                out.append(item)

    out: list[dict] = []
    resolve(primary, 24, out)
    if len(out) < 14:
        resolve(filler, 18, out)
    out.sort(key=lambda x: (x["date"], x["title"]))
    return out


def build_new_games(today: date) -> list[dict]:
    since = today - timedelta(days=45)
    rows = [r for r in search_rows("filter=topsellers", pages=3, count=100) if r["date"] and since <= r["date"] <= today]
    out = []
    seen = set()
    for r in rows:
        if r["appid"] in seen or ADULT_RE.search(r["title"]):
            continue
        seen.add(r["appid"])
        d = details(r["appid"])
        time.sleep(1.1)
        if not d or d.get("type") != "game" or is_adult(d, r["title"]) or not readable(d):
            continue
        item = make_item(r, d, r["date"])
        rec = (d.get("recommendations") or {}).get("total")
        if rec:
            item["reviews"] = int(rec)
        if item["image"]:
            out.append(item)
        if len(out) >= 12:
            break
    return out  # keep top-seller order (most popular first)


def main() -> int:
    today = datetime.now(MSK).date()
    rel = build_releases(today)
    write_json_if_good(DATA / "releases.json", {"updatedAt": now_msk_iso(), "items": rel}, "items", 5)
    new = build_new_games(today)
    write_json_if_good(DATA / "new_games.json", {"updatedAt": now_msk_iso(), "items": new}, "items", 4)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
