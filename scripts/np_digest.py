#!/usr/bin/env python3
"""Shared «Итоги недели» data for Discord + Telegram (reads the site's data/*.json only)."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MSK = timezone(timedelta(hours=3), name="MSK")
SITE = "https://derzko435.github.io/nexus-pulse/"
CURATED_FREEBIE = re.compile(r"(-always$|^gog-giveaway|^prime-)")
GAME_NAMES = {"cs2": "CS2", "dota2": "Dota 2", "valorant": "Valorant", "lol": "LoL"}


def read_json(name: str, default=None):
    try:
        return json.loads((DATA / name).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default if default is not None else {}


def parse_dt(s) -> datetime | None:
    if not s:
        return None
    s = str(s).strip()
    try:
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            return datetime.fromisoformat(s).replace(tzinfo=MSK)
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=MSK)
    except ValueError:
        return None


def top_deals(n: int = 5, min_pct: int = 50) -> list[dict]:
    out = []
    for d in (read_json("deals.json").get("deals") or []):
        try:
            pct = int(float(d.get("pct") or 0))
        except ValueError:
            continue
        if pct >= min_pct and d.get("title"):
            out.append(dict(d, pct=pct))
    out.sort(key=lambda d: (-d["pct"], str(d.get("title"))))
    return out[:n]


def current_freebies(n: int = 5, include_soon: bool = True) -> list[dict]:
    today = datetime.now(MSK).date()
    out = []
    for it in read_json("freebies.json").get("items") or []:
        fid = str(it.get("id") or "")
        if not fid or not it.get("title") or CURATED_FREEBIE.search(fid):
            continue
        until = parse_dt(it.get("until"))
        if until and until.date() < today:
            continue
        soon = "скоро" in str(it.get("note") or "").lower()
        if soon and not include_soon:
            continue
        out.append(dict(it, soon=soon))
    out.sort(key=lambda x: x["soon"])
    return out[:n]


def match_results(days: int = 7, n: int = 6) -> list[dict]:
    now = datetime.now(MSK)
    out = []
    for m in read_json("matches.json").get("matches") or []:
        st = parse_dt(m.get("startsAt"))
        if (m.get("status") == "finished" and m.get("tier") == "S" and st and st >= now - timedelta(days=days)
                and m.get("scoreA") not in (None, "") and m.get("scoreB") not in (None, "")):
            out.append(dict(m, gameName=GAME_NAMES.get(m.get("gameKey"), m.get("game") or ""), start=st))
    out.sort(key=lambda m: m["start"], reverse=True)
    return out[:n]


def upcoming_matches(hours: int = 72, n: int = 5) -> list[dict]:
    now = datetime.now(MSK)
    out = []
    for m in read_json("matches.json").get("matches") or []:
        st = parse_dt(m.get("startsAt"))
        if m.get("status") == "upcoming" and m.get("tier") == "S" and st and now <= st <= now + timedelta(hours=hours):
            out.append(dict(m, gameName=GAME_NAMES.get(m.get("gameKey"), m.get("game") or ""), start=st))
    out.sort(key=lambda m: m["start"])
    return out[:n]


def top_news(n: int = 5) -> list[dict]:
    items = [it for it in read_json("news.json").get("items") or [] if it.get("title") and it.get("id")]
    items.sort(key=lambda it: str(it.get("date") or ""), reverse=True)
    return items[:n]


def weekly() -> dict:
    return {"deals": top_deals(), "freebies": current_freebies(), "results": match_results(),
            "upcoming": upcoming_matches(), "news": top_news()}
