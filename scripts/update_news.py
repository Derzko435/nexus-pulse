#!/usr/bin/env python3
"""Daily gaming news → data/news.json

Sources: public RSS feeds of Russian gaming media (StopGame, 3DNews, Playground,
Cybersport.ru, Kanobu). For each item we open the original article and keep a
substantial plain-text excerpt (never the whole site HTML), the picture and a
link to the original. Nothing is invented: if every source fails, the previous
file stays untouched.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree as ET

from bs4 import BeautifulSoup

from np_common import (
    DATA, MSK, best_text_container, blocks_from_soup, clean_text, clip, fetch_text,
    log, now_msk_iso, og_image, paragraphs_to_blocks, safe_url, write_json_if_good,
)

OUT = DATA / "news.json"
PER_SOURCE = 8
TOTAL = 32

SOURCES = [
    {"id": "stopgame", "name": "StopGame", "home": "https://stopgame.ru", "rss": "https://rss.stopgame.ru/rss_news.xml", "selector": "#material_content"},
    {"id": "3dnews", "name": "3DNews", "home": "https://3dnews.ru/games", "rss": "https://3dnews.ru/games/rss/", "selector": ".js-mediator-article, .article-entry"},
    {"id": "goha", "name": "GoHa.ru", "home": "https://www.goha.ru", "rss": "https://www.goha.ru/rss/news", "selector": None},
    {"id": "cybersport", "name": "Cybersport.ru", "home": "https://www.cybersport.ru", "rss": "https://www.cybersport.ru/rss/materials", "selector": None, "limit": 6},
    {"id": "kanobu", "name": "Канобу", "home": "https://kanobu.ru", "rss": "https://kanobu.ru/rss/news.xml", "selector": None, "games_only": True, "limit": 3},
]

NON_GAME_RE = re.compile(r"(фильм|сериал|аниме|кино|актёр|актер|актрис|экраниз|мультфильм|книг|манг|режисс|сезон шоу|netflix|hbo|кинопоиск|премьер[аы] (фильма|сериала))", re.I)
GAME_RE = re.compile(r"(игр|gta|steam|playstation|xbox|nintendo|switch|ps5|консол|геймер|dlc|патч|релиз игры|call of duty|cs2|dota|valorant)", re.I)
MEDIA_NS = "{http://search.yahoo.com/mrss/}"


def parse_date(s: str) -> str:
    try:
        d = parsedate_to_datetime(s)
        return d.astimezone(MSK).replace(microsecond=0).isoformat()
    except Exception:  # noqa: BLE001
        return ""


def parse_feed(src: dict) -> list[dict]:
    xml = fetch_text(src["rss"], timeout=30)
    xml = re.sub(r"^[^<]+", "", xml)
    root = ET.fromstring(xml.encode("utf-8"))
    items = []
    for it in root.iter("item"):
        title = clean_text(it.findtext("title"))
        link = safe_url(clean_text(it.findtext("link")))
        if not title or not link:
            continue
        if src.get("games_only") and (NON_GAME_RE.search(title) or not GAME_RE.search(title)):
            continue
        desc = clean_text(it.findtext("description"))
        img = ""
        enc = it.find("enclosure")
        if enc is not None and (enc.get("type") or "image").startswith("image"):
            img = safe_url(enc.get("url"))
        if not img:
            for tag in (MEDIA_NS + "content", MEDIA_NS + "thumbnail"):
                m = it.find(tag)
                if m is not None and m.get("url"):
                    img = safe_url(m.get("url"))
                    break
        items.append({
            "title": title,
            "url": link,
            "summary": desc,
            "image": img,
            "date": parse_date(it.findtext("pubDate") or ""),
        })
        if len(items) >= src.get("limit", PER_SOURCE):
            break
    return items


def extract_article(url: str, selector: str | None) -> tuple[list[dict], str]:
    html_text = fetch_text(url, timeout=30)
    soup = BeautifulSoup(html_text, "html.parser")
    image = og_image(soup)
    # 1) JSON-LD articleBody
    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            data = json.loads(tag.string or "")
        except Exception:  # noqa: BLE001
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            node = stack.pop()
            if isinstance(node, dict):
                if node.get("@graph"):
                    stack.extend(node["@graph"])
                body = node.get("articleBody")
                if isinstance(body, str) and len(body) > 300:
                    blocks = paragraphs_to_blocks(body)
                    if blocks:
                        return blocks, image
    # 2) site selector
    if selector:
        for sel in selector.split(","):
            el = soup.select_one(sel.strip())
            if el is not None:
                for bad in el(["script", "style", "noscript", "iframe", "form", "aside", "figure", "button", "svg"]):
                    bad.decompose()
                blocks = blocks_from_soup(el)
                if sum(len(b["x"]) for b in blocks) > 250:
                    return blocks, image
    # 3) generic
    cont = best_text_container(soup)
    if cont is not None:
        blocks = blocks_from_soup(cont)
        if blocks:
            return blocks, image
    return [], image


def main() -> int:
    collected: list[dict] = []
    for src in SOURCES:
        try:
            items = parse_feed(src)
            log(f"[feed] {src['name']}: {len(items)}")
        except Exception as e:  # noqa: BLE001
            log(f"[feed-fail] {src['name']}: {e}")
            continue
        for it in items:
            it["source"] = src["name"]
            it["sourceHome"] = src["home"]
            it["_sel"] = src.get("selector")
            collected.append(it)

    # newest first, then round-robin fairness is naturally achieved by PER_SOURCE cap
    collected.sort(key=lambda x: x.get("date") or "", reverse=True)
    seen = set()
    final = []
    for it in collected:
        key = re.sub(r"\W+", "", it["title"].lower())[:60]
        if key in seen:
            continue
        seen.add(key)
        try:
            blocks, og = extract_article(it["url"], it.pop("_sel", None))
        except Exception as e:  # noqa: BLE001
            log(f"[article-fail] {it['url']}: {e}")
            blocks, og = [], ""
        it.pop("_sel", None)
        if not blocks and it.get("summary"):
            blocks = paragraphs_to_blocks(it["summary"])
        if not it.get("image") and og:
            it["image"] = og
        if not it.get("image") or not blocks or sum(len(b["x"]) for b in blocks) < 250:
            continue  # the user wants a picture and full text for every item
        summary = it.get("summary") or next((b["x"] for b in blocks if b["t"] == "p"), "")
        it["summary"] = clip(re.sub(r"\s*(…\s*)?\[…\]\s*$", "…", summary), 260)
        it["body"] = blocks
        it["id"] = hashlib.sha1(it["url"].encode()).hexdigest()[:12]
        final.append(it)
        time.sleep(0.4)
        if len(final) >= TOTAL:
            break

    payload = {"updatedAt": now_msk_iso(), "items": final}
    write_json_if_good(OUT, payload, "items", min_items=6)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
