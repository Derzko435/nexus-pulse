#!/usr/bin/env python3
"""Current patch notes for popular games → data/patches.json

- Steam games: official developer announcements (Steam News) — the latest post
  that is a real update / patch note (not a sale or event).
- Valorant and League of Legends: official Riot patch notes pages (Russian).
Every entry has the date, the notes as safe text blocks and a link to the source.
If everything fails the previous file is kept.
"""
from __future__ import annotations

import json
import re
import time
from datetime import datetime, timedelta

from bs4 import BeautifulSoup

from np_common import (
    DATA, MSK, best_text_container, blocks_from_soup, clean_text, clip, fetch_json, fetch_text,
    iso_from_ts, log, now_msk_iso, og_image, safe_url, write_json_if_good,
)

try:
    from np_translate import Translator
except Exception:  # noqa: BLE001 — translation is optional, never breaks the update
    Translator = None  # type: ignore

OUT = DATA / "patches.json"
MAX_AGE_DAYS = 150

STEAM_GAMES = [
    # id, name, appid, title regex (None = rely on the patchnotes tag), catalog id
    ("cs2", "Counter-Strike 2", 730, None, "cs2"),
    ("dota2", "Dota 2", 570, None, "dota2"),
    ("pubg", "PUBG: Battlegrounds", 578080, r"patch notes|update\s*\d", None),
    ("apex", "Apex Legends", 1172470, r"update|patch", "apex"),
    ("r6", "Rainbow Six Siege", 359550, r"patch notes|y\d+s\d", "r6"),
    ("ow2", "Overwatch 2", 2357570, r"patch notes|patch|hotfix", "ow2"),
    ("rust", "Rust", 252490, r".", None),
    ("destiny2", "Destiny 2", 1085660, r"update|hotfix|patch", "destiny2"),
    ("warframe", "Warframe", 230410, r"hotfix|update", None),
    ("poe2", "Path of Exile 2", 2694490, r"patch|hotfix|\d+\.\d+\.\d+", "poe2"),
    ("helldivers2", "Helldivers 2", 553850, r"patch|\d+\.\d+\.\d+", None),
    ("rivals", "Marvel Rivals", 2767030, r"patch notes|version|update|balance", None),
]
EXCLUDE_RE = re.compile(
    r"(sale|скидк|bundle|available now|is live|live!|drops|devstream|this week in|showcase|registration|"
    r"steam deck verified|coming to|giveaway|contest|trailer|cosmetic|pack|tournament|championship|series|"
    r"weekly bans|ban notice|anniversary|event)", re.I)
STEAM_IMG_RE = re.compile(r"\[img\](.*?)\[/img\]", re.I | re.S)


def bbcode_to_blocks(text: str, max_blocks: int = 60, max_chars: int = 9000) -> list[dict]:
    t = text.replace("\r", "")
    t = re.sub(r"\[img[^\]]*\].*?\[/img\]", "\n", t, flags=re.I | re.S)
    t = re.sub(r"\[previewyoutube[^\]]*\].*?\[/previewyoutube\]", "\n", t, flags=re.I | re.S)
    t = re.sub(r"\{STEAM_CLAN_IMAGE\}\S*", "", t)
    t = re.sub(r"\[url=[^\]]*\](.*?)\[/url\]", r"\1", t, flags=re.I | re.S)
    t = re.sub(r"\[/?(b|i|u|strike|spoiler|noparse|code|quote[^\]]*|table|tr|td|th|hr|carousel|video[^\]]*)\]", "", t, flags=re.I)
    # headings
    t = re.sub(r"\[h[1-6]\](.*?)\[/h[1-6]\]", lambda m: "\n\u0001H" + m.group(1) + "\n", t, flags=re.I | re.S)
    t = re.sub(r"\[\*\]", "\n\u0001L", t)
    t = re.sub(r"\[/?(list|olist)[^\]]*\]", "\n", t, flags=re.I)
    t = re.sub(r"\[/\*\]", "\n", t)
    t = re.sub(r"\[p[^\]]*\]", "\n", t, flags=re.I)
    t = re.sub(r"\[/p\]", "\n", t, flags=re.I)
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"<li[^>]*>", "\n\u0001L", t, flags=re.I)
    t = re.sub(r"<h[1-6][^>]*>", "\n\u0001H", t, flags=re.I)
    t = re.sub(r"</?(p|div|ul|ol|h[1-6]|li)[^>]*>", "\n", t, flags=re.I)
    t = re.sub(r"\[[^\]\n]{1,40}\]", "", t)  # leftover tags
    out: list[dict] = []
    total = 0
    for raw in t.split("\n"):
        kind = "p"
        line = raw
        if line.startswith("\u0001H"):
            kind, line = "h", line[2:]
        elif line.startswith("\u0001L"):
            kind, line = "li", line[2:]
        line = clean_text(line)
        if not line or not re.search(r"[0-9A-Za-zА-Яа-яЁё]", line):
            continue
        if kind == "p" and re.match(r"^[-•–]\s+", line):
            kind, line = "li", re.sub(r"^[-•–]\s+", "", line)
        if kind == "p" and len(line) < 60 and line.endswith(":"):
            kind = "h"
        out.append({"t": kind, "x": clip(line, 900)})
        total += len(line)
        if len(out) >= max_blocks or total >= max_chars:
            out.append({"t": "p", "x": "Полный список изменений — по ссылке на источник."})
            break
    while out and out[-1]["t"] == "h":
        out.pop()
    return out


def steam_image(contents: str, appid: int) -> str:
    m = STEAM_IMG_RE.search(contents or "")
    if m:
        u = m.group(1).strip().replace("{STEAM_CLAN_IMAGE}", "https://clan.akamai.steamstatic.com/images")
        u = safe_url(u)
        if u:
            return u
    return f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg"


def steam_patch(gid: str, name: str, appid: int, title_re: str | None, cat: str | None) -> dict | None:
    url = (f"https://api.steampowered.com/ISteamNews/GetNewsForApp/v2/?appid={appid}&count=40&maxlength=0"
           f"&feeds=steam_community_announcements")
    data = fetch_json(url, timeout=30)
    items = ((data or {}).get("appnews") or {}).get("newsitems") or []
    cutoff = (datetime.now(MSK) - timedelta(days=MAX_AGE_DAYS)).timestamp()
    for it in items:
        if it.get("date", 0) < cutoff:
            continue
        title = clean_text(it.get("title"))
        tags = it.get("tags") or []
        if title_re is None:
            if "patchnotes" not in tags:
                continue
        else:
            if "patchnotes" not in tags and (not re.search(title_re, title, re.I) or EXCLUDE_RE.search(title)):
                continue
        blocks = bbcode_to_blocks(it.get("contents") or "")
        if sum(len(b["x"]) for b in blocks) < 200:
            continue
        summary = next((b["x"] for b in blocks if b["t"] in ("p", "li") and len(b["x"]) > 20), "")
        return {
            "id": gid,
            "game": name,
            "catalogId": cat,
            "title": title,
            "date": iso_from_ts(it["date"]),
            "image": steam_image(it.get("contents") or "", appid),
            "summary": clip(summary, 220),
            "body": blocks,
            "lang": "en" if not re.search(r"[А-Яа-яЁё]", " ".join(b["x"] for b in blocks[:5])) else "ru",
            "url": safe_url(it.get("url")) or f"https://store.steampowered.com/news/app/{appid}",
            "source": "Steam",
            "platforms": ["PC"],
        }
    return None


RIOT = [
    ("valorant", "Valorant", "https://playvalorant.com", "/ru-ru/news/tags/patch-notes/", "valorant"),
    ("lol", "League of Legends", "https://www.leagueoflegends.com", "/ru-ru/news/tags/patch-notes/", "lol"),
]


def riot_patch(gid: str, name: str, base: str, path: str, cat: str) -> dict | None:
    html = fetch_text(base + path, timeout=30)
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        return None
    blob = m.group(1)
    urls = re.findall(r'"url":"(/ru-ru/news/game-updates/[^"]+)"', blob)
    ru_titles = [t for t in re.findall(r'"title":"([^"]{5,140})"', blob) if re.search(r"(обновлени|патч|\d+\.\d+)", t, re.I)]
    if not urls:
        return None
    art_url = base + urls[0].rstrip("/") + "/"
    art = fetch_text(art_url, timeout=30)
    soup = BeautifulSoup(art, "html.parser")
    title = clean_text((soup.find("meta", attrs={"property": "og:title"}) or {}).get("content") or (soup.title.string if soup.title else ""))
    if ru_titles and not re.search(r"[А-Яа-яЁё]", title):
        title = clean_text(ru_titles[0])
    image = og_image(soup)
    date = ""
    tm = soup.find("time")
    if tm and tm.get("datetime"):
        try:
            date = datetime.fromisoformat(tm["datetime"].replace("Z", "+00:00")).astimezone(MSK).replace(microsecond=0).isoformat()
        except ValueError:
            date = ""
    if not date:
        dm = re.search(r'"publishedAt":"([^"]+)"', blob)
        if dm:
            date = datetime.fromisoformat(dm.group(1).replace("Z", "+00:00")).astimezone(MSK).replace(microsecond=0).isoformat()
    rich = sorted(soup.select("[data-testid='rich-text-html']"), key=lambda e: len(e.get_text()), reverse=True)
    cont = (rich[0] if rich and len(rich[0].get_text()) > 300 else None) or best_text_container(soup)
    blocks = blocks_from_soup(cont, max_blocks=70, max_chars=9000) if cont is not None else []
    if not blocks:
        return None
    summary = next((b["x"] for b in blocks if b["t"] == "p" and len(b["x"]) > 40), blocks[0]["x"])
    return {
        "id": gid, "game": name, "catalogId": cat, "title": title or f"Обновление {name}",
        "date": date, "image": image, "summary": clip(summary, 220), "body": blocks, "lang": "ru",
        "url": art_url, "source": "Riot Games", "platforms": ["PC"],
    }


def translate_items(items: list[dict]) -> None:
    """English patch notes → Russian (machine translation, cached). Original link is kept.
    If the translation is incomplete the item stays in English (no half-translated notes)."""
    if Translator is None:
        return
    try:
        tr = Translator()
    except Exception as e:  # noqa: BLE001
        log(f"[translate-fail] init: {e}")
        return
    for it in items:
        if it.get("lang") != "en":
            continue
        src = [it.get("title") or "", it.get("summary") or ""] + [b["x"] for b in it.get("body") or []]
        need = [s for s in src if tr.needs(s)]
        try:
            ru = tr.many(src)
        except Exception as e:  # noqa: BLE001
            log(f"[translate-fail] {it['game']}: {e}")
            continue
        changed = sum(1 for a, b in zip(src, ru) if a != b)
        if need and changed >= len(need) * 0.9:
            it["titleOriginal"] = it.get("title")
            it["title"], it["summary"] = ru[0], ru[1]
            for b, x in zip(it.get("body") or [], ru[2:]):
                b["x"] = x
            it["lang"] = "ru"
            it["translated"] = True
            log(f"[translate] {it['game']}: {changed}/{len(need)} strings")
        else:
            log(f"[translate-keep-en] {it['game']}: only {changed}/{len(need)} strings translated")
    try:
        tr.save()
    except Exception as e:  # noqa: BLE001
        log(f"[translate-fail] save: {e}")


def main() -> int:
    out = []
    for gid, name, base, path, cat in RIOT:
        try:
            p = riot_patch(gid, name, base, path, cat)
            if p:
                out.append(p)
            log(f"[riot] {name}: {'ok' if p else 'none'}")
        except Exception as e:  # noqa: BLE001
            log(f"[riot-fail] {name}: {e}")
    for gid, name, appid, rx, cat in STEAM_GAMES:
        try:
            p = steam_patch(gid, name, appid, rx, cat)
            if p:
                out.append(p)
            log(f"[steam] {name}: {p['title'] if p else 'none'}")
        except Exception as e:  # noqa: BLE001
            log(f"[steam-fail] {name}: {e}")
        time.sleep(0.6)
    out.sort(key=lambda x: x.get("date") or "", reverse=True)
    translate_items(out)
    write_json_if_good(OUT, {"updatedAt": now_msk_iso(), "items": out}, "items", 4)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
