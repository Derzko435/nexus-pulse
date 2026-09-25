#!/usr/bin/env python3
"""Esports matches & tournaments → data/matches.json

Source: bo3.gg public match feed (CS2, Dota 2, Valorant, League of Legends),
top tiers only (S / A). For every match we keep teams, tournament, start time,
score and the broadcast channels listed for it; when a match has no listed
broadcast we attach the organiser's official channel (ESL, BLAST, PGL, Riot…).
If the source is unavailable the previous file is kept — nothing is invented.
"""
from __future__ import annotations

import re
import time
import urllib.parse
from datetime import datetime, timedelta, timezone

from np_common import DATA, MSK, clean_text, fetch_json, log, now_msk_iso, safe_url, write_json_if_good

OUT = DATA / "matches.json"
API = "https://api.bo3.gg/api/v1"
GAMES = {
    1: {"key": "cs2", "name": "CS2", "path": ""},
    4: {"key": "dota2", "name": "Dota 2", "path": "dota2/"},
    2: {"key": "valorant", "name": "Valorant", "path": "valorant/"},
    3: {"key": "lol", "name": "LoL", "path": "lol/"},
}
PER_GAME_UPCOMING = 10
PER_GAME_FINISHED = 5

# Official organiser channels (Twitch) used when a match lists no broadcast.
OFFICIAL = [
    (r"\bPGL\b", {"cs2": "pgl", "dota2": "pgl_dota2"}),
    (r"\b(ESL|IEM|Intel Extreme)\b", {"cs2": "eslcs", "dota2": "esl_dota2"}),
    (r"\bBLAST\b", {"cs2": "blastpremier", "dota2": "blastpremier"}),
    (r"StarLadder|StarSeries", {"cs2": "starladder_cs_en"}),
    (r"The International", {"dota2": "dota2ti"}),
    (r"VALORANT|VCT|Champions Tour", {"valorant": "valorant"}),
    (r"\bLCK\b", {"lol": "lck"}),
    (r"\bLEC\b|EMEA Masters", {"lol": "lec"}),
    (r"Worlds|World Championship|\bMSI\b|\bLCS\b|\bLTA\b", {"lol": "riotgames"}),
]
YT_ID_RE = re.compile(r"(?:embed/|v=|youtu\.be/|live/)([A-Za-z0-9_-]{11})")
SAFE_CHANNEL = re.compile(r"^[A-Za-z0-9_]{2,40}$")


def q(url: str, params: dict) -> str:
    return url + "?" + urllib.parse.urlencode(params, safe="[],")


def parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None


def stream_entry(s: dict) -> dict | None:
    if s.get("blocked"):
        return None
    platform = s.get("platform")
    lang = (s.get("language") or "").lower()[:2]
    official = bool(s.get("official"))
    raw = s.get("raw_url") or ""
    emb = s.get("embed_url") or ""
    if platform == 1 or "twitch.tv" in raw:
        ch = (s.get("name") or "").strip()
        m = re.search(r"twitch\.tv/([A-Za-z0-9_]+)", raw)
        if m:
            ch = m.group(1)
        if SAFE_CHANNEL.match(ch or ""):
            return {"type": "twitch", "channel": ch.lower(), "lang": lang, "official": official, "label": ch}
    if platform == 2 or "youtu" in raw + emb:
        m = YT_ID_RE.search(emb) or YT_ID_RE.search(raw)
        if m:
            return {"type": "youtube", "id": m.group(1), "lang": lang, "official": official, "label": clean_text(s.get("name"))[:80] or "YouTube"}
    if platform == 3 or "kick.com" in raw:
        m = re.search(r"kick\.com/([A-Za-z0-9_]+)", raw or emb)
        if m and SAFE_CHANNEL.match(m.group(1)):
            return {"type": "kick", "channel": m.group(1).lower(), "lang": lang, "official": official, "label": m.group(1)}
    return None


def rank_stream(st: dict) -> tuple:
    lang_score = {"ru": 0, "en": 1}.get(st.get("lang"), 2)
    type_score = {"twitch": 0, "youtube": 1, "kick": 2}.get(st["type"], 3)
    return (0 if st.get("official") else 1, lang_score, type_score)


def official_for(game_key: str, tournament: str) -> dict | None:
    for rx, mp in OFFICIAL:
        if re.search(rx, tournament, re.I) and game_key in mp:
            ch = mp[game_key]
            return {"type": "twitch", "channel": ch, "lang": "en", "official": True, "label": ch, "fallback": True}
    return None


def fetch_matches(discipline: int, statuses: str, sort: str, limit: int) -> list[dict]:
    url = q(f"{API}/matches", {
        "page[offset]": 0, "page[limit]": limit, "sort": sort,
        "filter[matches.status][in]": statuses,
        "filter[matches.discipline_id][eq]": discipline,
        "filter[matches.tier][in]": "s,a",
        "with": "teams,tournament,streams",
    })
    data = fetch_json(url, timeout=40, headers={"Accept": "application/json"})
    return data.get("results") or []


def team(t: dict | None) -> dict | None:
    if not t or not t.get("name"):
        return None
    return {"name": clean_text(t["name"])[:40], "logo": safe_url(t.get("image_url"))}


def convert(m: dict, g: dict) -> dict | None:
    t1, t2 = team(m.get("team1")), team(m.get("team2"))
    if not t1 or not t2:
        return None
    tour = m.get("tournament") or {}
    tname = clean_text(tour.get("name"))
    start = parse_iso(m.get("start_date"))
    if not start:
        return None
    streams = [x for x in (stream_entry(s) for s in m.get("streams") or []) if x]
    uniq, seen = [], set()
    for s in sorted(streams, key=rank_stream):
        k = (s["type"], s.get("channel") or s.get("id"))
        if k not in seen:
            seen.add(k)
            uniq.append(s)
    uniq = uniq[:4]
    if not any(s["type"] in ("twitch", "youtube") for s in uniq):
        off = official_for(g["key"], tname)
        if off:
            uniq.insert(0, off)
    status = {"current": "live", "upcoming": "upcoming", "finished": "finished"}.get(m.get("status"), "upcoming")
    return {
        "id": f"bo3-{m.get('id')}",
        "game": g["name"],
        "gameKey": g["key"],
        "teamA": t1["name"], "teamB": t2["name"],
        "logoA": t1["logo"], "logoB": t2["logo"],
        "scoreA": m.get("team1_score") if m.get("team1_score") is not None else None,
        "scoreB": m.get("team2_score") if m.get("team2_score") is not None else None,
        "bo": m.get("bo_type"),
        "status": status,
        "event": tname,
        "tier": (m.get("tier") or "").upper(),
        "startsAt": start.astimezone(MSK).replace(microsecond=0).isoformat(),
        "streams": uniq,
        "url": f"https://bo3.gg/{g['path']}matches/{m.get('slug')}" if m.get("slug") else "",
    }


def main() -> int:
    now = datetime.now(timezone.utc)
    matches: list[dict] = []
    tournaments: dict = {}
    ok_sources = 0
    for disc, g in GAMES.items():
        try:
            up = fetch_matches(disc, "current,upcoming", "start_date", 100)
            time.sleep(1.0)
            fin = fetch_matches(disc, "finished", "-start_date", 30)
            time.sleep(1.0)
            ok_sources += 1
        except Exception as e:  # noqa: BLE001
            log(f"[bo3-fail] {g['name']}: {e}")
            continue
        n_up = 0
        for m in up:
            c = convert(m, g)
            if not c:
                continue
            st = parse_iso(c["startsAt"])
            if c["status"] == "upcoming" and st and st > now + timedelta(days=5):
                continue
            matches.append(c)
            n_up += 1
            tour = m.get("tournament") or {}
            if tour.get("id") and tour["id"] not in tournaments:
                tournaments[tour["id"]] = {
                    "name": clean_text(tour.get("name")), "game": g["name"], "gameKey": g["key"],
                    "tier": (tour.get("tier") or "").upper(),
                    "prize": tour.get("prize"),
                    "start": (parse_iso(tour.get("start_date")) or st).astimezone(MSK).date().isoformat(),
                    "end": (parse_iso(tour.get("end_date")) or st).astimezone(MSK).date().isoformat(),
                    "status": tour.get("status"),
                    "url": f"https://bo3.gg/{g['path']}tournaments/{tour.get('slug')}" if tour.get("slug") else "",
                }
            if n_up >= PER_GAME_UPCOMING:
                break
        n_fin = 0
        for m in fin:
            c = convert(m, g)
            if not c:
                continue
            st = parse_iso(c["startsAt"])
            if st and st < now - timedelta(days=4):
                continue
            matches.append(c)
            n_fin += 1
            if n_fin >= PER_GAME_FINISHED:
                break
    if ok_sources == 0:
        log("[keep] matches.json: source unavailable")
        return 0
    order = {"live": 0, "upcoming": 1, "finished": 2}
    matches.sort(key=lambda x: (order.get(x["status"], 3), x["startsAt"] if x["status"] != "finished" else "", ))
    fin = sorted([m for m in matches if m["status"] == "finished"], key=lambda x: x["startsAt"], reverse=True)
    matches = [m for m in matches if m["status"] != "finished"] + fin
    # Big (S-tier) tournaments: current and the next ~3 months
    try:
        url = q(f"{API}/tournaments", {
            "page[offset]": 0, "page[limit]": 40, "sort": "start_date",
            "filter[tournaments.status][in]": "current,upcoming",
            "filter[tournaments.tier][in]": "s",
            "filter[tournaments.discipline_id][in]": "1,2,3,4",
        })
        horizon = now + timedelta(days=95)
        disc_map = {d: g for d, g in GAMES.items()}
        for tour in fetch_json(url, timeout=40).get("results") or []:
            g = disc_map.get(tour.get("discipline_id"))
            st = parse_iso(tour.get("start_date"))
            if not g or not st or st > horizon or tour.get("id") in tournaments:
                continue
            en = parse_iso(tour.get("end_date")) or st
            tournaments[tour["id"]] = {
                "name": clean_text(tour.get("name")), "game": g["name"], "gameKey": g["key"],
                "tier": (tour.get("tier") or "").upper(), "prize": tour.get("prize"),
                "start": st.astimezone(MSK).date().isoformat(), "end": en.astimezone(MSK).date().isoformat(),
                "status": tour.get("status"),
                "url": f"https://bo3.gg/{g['path']}tournaments/{tour.get('slug')}" if tour.get("slug") else "",
            }
    except Exception as e:  # noqa: BLE001
        log(f"[bo3-tournaments-fail] {e}")
    tlist = sorted(tournaments.values(), key=lambda t: (0 if t["status"] == "current" else 1, t["start"], t["name"]))
    payload = {
        "updatedAt": now_msk_iso(),
        "source": "bo3.gg",
        "matches": matches,
        "tournaments": tlist[:16],
    }
    write_json_if_good(OUT, payload, "matches", 4)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
