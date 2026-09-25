#!/usr/bin/env python3
"""Fresh videos from well-known gaming / esports / AI channels → data/videos.json

Uses the public YouTube channel feeds (no key). Shorts are skipped.
The site shows a thumbnail first and loads the player only on click.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from xml.etree import ElementTree as ET

from np_common import DATA, MSK, clean_text, clip, fetch_text, log, now_msk_iso, write_json_if_good

OUT = DATA / "videos.json"
PER_CHANNEL = 3
MAX_AGE_DAYS = 21

CHANNELS = [
    # (channel_id, display name, category, language)
    ("UCq7JZ8ATgQWeu6sDM1czjhg", "StopGame", "games", "ru"),
    ("UC4e_XPBiiIO4fo4_CucxQeg", "IXBT Games", "games", "ru"),
    ("UCdKuE7a2QZeHPhDntXVZ91w", "Kuplinov ► Play", "games", "ru"),
    ("UCf31Gf5nCU8J6eUlr7QSU0w", "Marmok", "games", "ru"),
    ("UCyJrhZm9KXrzRub3-wD2zWg", "TheBrianMaps", "games", "ru"),
    ("UCKy1dAqELo0zrOtPkf0eTMw", "IGN", "games", "en"),
    ("UCbu2SsF-Or3Rsn3NxqODImw", "GameSpot", "games", "en"),
    ("UC9PBzalIcEQCsiIkq36PyUA", "Digital Foundry", "games", "en"),
    ("UC-2Y8dQb0S6DtpxNgAKoJKA", "PlayStation", "games", "en"),
    ("UCNvzD7Z-g64bPXxGzaQaa4g", "gameranx", "games", "en"),
    ("UCPq2ETz4aAGo2Z-8JisDPIA", "ESL Counter-Strike", "esports", "en"),
    ("UC9k--dE_UE0Faxzgb_DDkYQ", "BLAST Premier", "esports", "en"),
    ("UC5jpxDZx4yoBo324pMQ91Ww", "PGL", "esports", "en"),
    ("UCvqRdlKsE5Q8mf8YXbdIJLw", "LoL Esports", "esports", "en"),
    ("UCTQKT5QqO3h7y32G8VzuySQ", "Dota 2", "esports", "en"),
    ("UCaYLBJfw6d8XqmNlL204lNg", "ESL Dota 2", "esports", "en"),
    ("UCXbsUubmNPK8XJFbkmlMcMg", "HLTV", "esports", "en"),
    ("UC8CX0LD98EDXl4UYX1MDCXg", "VALORANT", "esports", "en"),
    ("UCbfYPyITQ-7l4upoX8nvctg", "Two Minute Papers", "ai", "en"),
    ("UCNJ1Ymd5yFuUPtn21xtRbbw", "AI Explained", "ai", "en"),
    ("UCsBjURrPoezykLs9EqgamOA", "Fireship", "ai", "en"),
    ("UCY03gpyR__MuJtBpoSyIGnw", "Droider", "ai", "ru"),
    ("UCL-g3eGJi1omSDSz48AML-g", "NVIDIA GeForce", "ai", "en"),
]

NS = {
    "a": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}
ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")


def channel_videos(cid: str, name: str, cat: str, lang: str) -> list[dict]:
    xml = fetch_text(f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}", timeout=25)
    root = ET.fromstring(xml.encode("utf-8"))
    cutoff = datetime.now(timezone.utc) - timedelta(days=MAX_AGE_DAYS + (14 if cat == "esports" else 0))
    out = []
    for e in root.findall("a:entry", NS):
        vid = (e.findtext("yt:videoId", default="", namespaces=NS) or "").strip()
        link = e.find("a:link", NS)
        href = link.get("href") if link is not None else ""
        title = clean_text(e.findtext("a:title", default="", namespaces=NS))
        if not ID_RE.match(vid) or "/shorts/" in href or re.search(r"#shorts?\b", title, re.I):
            continue
        pub = e.findtext("a:published", default="", namespaces=NS)
        try:
            dt = datetime.fromisoformat(pub.replace("Z", "+00:00"))
        except ValueError:
            continue
        if dt < cutoff:
            continue
        grp = e.find("media:group", NS)
        desc = clean_text(grp.findtext("media:description", default="", namespaces=NS)) if grp is not None else ""
        views = None
        if grp is not None:
            st = grp.find("media:community/media:statistics", NS)
            if st is not None and (st.get("views") or "").isdigit():
                views = int(st.get("views"))
        out.append({
            "id": vid,
            "title": clip(title, 140),
            "channel": name,
            "category": cat,
            "lang": lang,
            "date": dt.astimezone(MSK).replace(microsecond=0).isoformat(),
            "desc": clip(desc.split("\n")[0] if desc else "", 220),
            "views": views,
        })
        if len(out) >= PER_CHANNEL:
            break
    return out


def main() -> int:
    items: list[dict] = []
    for cid, name, cat, lang in CHANNELS:
        try:
            vids = channel_videos(cid, name, cat, lang)
            log(f"[yt] {name}: {len(vids)}")
            items.extend(vids)
        except Exception as e:  # noqa: BLE001
            log(f"[yt-fail] {name}: {e}")
    items.sort(key=lambda x: x["date"], reverse=True)
    write_json_if_good(OUT, {"updatedAt": now_msk_iso(), "items": items}, "items", 8)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
