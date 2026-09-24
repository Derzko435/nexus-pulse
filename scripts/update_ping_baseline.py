#!/usr/bin/env python3
"""Write data/ping_targets.json + data/steam_catalog_snapshot.json.

Runner latency is NOT user latency. This job stores:
  - curated CDN endpoints for browser-side img/favicon RTT
  - Steam store appdetails snapshot for catalog metadata
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PING_OUT = DATA / "ping_targets.json"
STEAM_OUT = DATA / "steam_catalog_snapshot.json"
MSK = timezone(timedelta(hours=3), name="MSK")
UA = "NexusPulseDataBot/1.0 (+https://derzko435.github.io/nexus-pulse/; Actions refresh)"

# Curated popular Steam apps used on the site (catalog + deals)
CURATED_STEAM_APPS = [
    ("730", "cs2"),
    ("570", "dota2"),
    ("252950", "rocket"),
    ("1172470", "apex"),
    ("1245620", "elden"),
    ("1086940", "bg3"),
    ("292030", "witcher3"),
    ("1091500", "cp2077"),
    ("1174180", "rdr2"),
    ("271590", "gtav"),
    ("367520", "hollow"),
    ("1145360", "hades"),
    ("413150", "stardew"),
    ("739630", "phasmo"),
    ("1966720", "lethal"),
    ("782330", "doom"),
    ("814380", "sekiro"),
    ("2379780", "balatro"),
    ("2358720", "blackmyth"),  # optional
    ("1888160", "arma"),
    ("678960", None),
    ("1282100", None),
    ("1222140", None),
    ("227300", None),  # ETS2
    ("281990", None),  # Stellaris
]

PING_TARGETS = [
    {
        "id": "cloudflare",
        "name": "Cloudflare",
        "url": "https://www.cloudflare.com/favicon.ico",
        "kind": "img",
        "region_hint": "anycast",
        "note": "CDN anycast — browser img RTT",
    },
    {
        "id": "steam",
        "name": "Steam CDN",
        "url": "https://cdn.cloudflare.steamstatic.com/steam/apps/730/header.jpg",
        "kind": "img",
        "region_hint": "steamstatic",
        "note": "Valve CDN via Cloudflare",
    },
    {
        "id": "steam_store",
        "name": "Steam Store",
        "url": "https://store.steampowered.com/favicon.ico",
        "kind": "img",
        "region_hint": "valve",
        "note": "Store edge",
    },
    {
        "id": "riot",
        "name": "Riot",
        "url": "https://authenticate.riotgames.com/favicon.ico",
        "kind": "img",
        "region_hint": "riot",
        "note": "Approx Valorant/LoL auth edge",
    },
    {
        "id": "epic",
        "name": "Epic",
        "url": "https://static-assets-prod.unrealengine.com/account-portal/static/favicon.ico",
        "kind": "img",
        "region_hint": "epic",
        "note": "Epic / Unreal static",
    },
    {
        "id": "blizzard",
        "name": "Blizzard",
        "url": "https://www.blizzard.com/favicon.ico",
        "kind": "img",
        "region_hint": "blizzard",
        "note": "Battle.net portal",
    },
    {
        "id": "google",
        "name": "Google (ref)",
        "url": "https://www.google.com/favicon.ico",
        "kind": "img",
        "region_hint": "ref",
        "note": "Reference latency only",
    },
]


def now_iso() -> str:
    return datetime.now(MSK).isoformat(timespec="seconds")


def http_get(url: str, timeout: int = 20) -> tuple[int | None, float, str | None]:
    """Return (status, elapsed_ms, error)."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read(64)
            ms = (time.perf_counter() - t0) * 1000
            return resp.status, ms, None
    except urllib.error.HTTPError as e:
        ms = (time.perf_counter() - t0) * 1000
        return e.code, ms, str(e.reason)
    except Exception as e:  # noqa: BLE001
        ms = (time.perf_counter() - t0) * 1000
        return None, ms, str(e)


def write_ping_targets() -> None:
    reachability = []
    for t in PING_TARGETS:
        status, ms, err = http_get(t["url"])
        reachability.append(
            {
                "id": t["id"],
                "status": status,
                "runner_rtt_ms": round(ms, 1),
                "ok": status is not None and 200 <= status < 400,
                "error": err,
            }
        )
        time.sleep(0.15)

    payload = {
        "updatedAt": now_iso(),
        "source": "github-actions-ping-baseline",
        "disclaimer": (
            "Runner RTT is NOT end-user latency. "
            "Client measures live RTT via img/favicon from the browser."
        ),
        "targets": PING_TARGETS,
        "runnerReachability": reachability,
    }
    DATA.mkdir(parents=True, exist_ok=True)
    PING_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {PING_OUT} ({len(PING_TARGETS)} targets)")


def fetch_steam_app(appid: str) -> dict | None:
    url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc=ru&l=russian"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.loads(resp.read().decode("utf-8", "replace"))
    except Exception as e:  # noqa: BLE001
        print(f"  steam {appid}: fetch error {e}", file=sys.stderr)
        return None
    block = data.get(str(appid)) or data.get(appid)
    if not block or not block.get("success") or not isinstance(block.get("data"), dict):
        print(f"  steam {appid}: no data", file=sys.stderr)
        return None
    d = block["data"]
    genres = [g.get("description") for g in (d.get("genres") or []) if isinstance(g, dict)]
    platforms = d.get("platforms") or {}
    metacritic = None
    if isinstance(d.get("metacritic"), dict):
        metacritic = d["metacritic"].get("score")
    return {
        "appid": str(appid),
        "name": d.get("name"),
        "header_image": d.get("header_image"),
        "genres": [g for g in genres if g],
        "is_free": bool(d.get("is_free")),
        "platforms": {
            "windows": bool(platforms.get("windows")),
            "mac": bool(platforms.get("mac")),
            "linux": bool(platforms.get("linux")),
        },
        "metacritic": metacritic,
        "short_description": (d.get("short_description") or "")[:600],
    }


def curated_fallback(appid: str, catalog_id: str | None) -> dict:
    """Minimal stub if Steam blocks the runner."""
    names = {
        "730": "Counter-Strike 2",
        "570": "Dota 2",
        "252950": "Rocket League",
        "1172470": "Apex Legends",
        "1245620": "ELDEN RING",
        "1086940": "Baldur's Gate 3",
        "292030": "The Witcher 3: Wild Hunt",
        "1091500": "Cyberpunk 2077",
        "1174180": "Red Dead Redemption 2",
        "271590": "Grand Theft Auto V",
        "367520": "Hollow Knight",
        "1145360": "Hades",
        "413150": "Stardew Valley",
        "739630": "Phasmophobia",
        "1966720": "Lethal Company",
        "782330": "DOOM Eternal",
        "814380": "Sekiro™: Shadows Die Twice",
        "2379780": "Balatro",
        "678960": "CODE VEIN",
        "1282100": "REMNANT II",
        "1222140": "Detroit: Become Human",
        "227300": "Euro Truck Simulator 2",
        "281990": "Stellaris",
    }
    return {
        "appid": str(appid),
        "name": names.get(str(appid), f"Steam App {appid}"),
        "header_image": f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg",
        "genres": [],
        "is_free": str(appid) in {"730", "570", "1172470"},
        "platforms": {"windows": True, "mac": False, "linux": False},
        "metacritic": None,
        "short_description": "",
        "catalogId": catalog_id,
        "curated": True,
    }


def collect_appids_from_deals() -> list[str]:
    deals_path = DATA / "deals.json"
    ids: list[str] = []
    if deals_path.exists():
        try:
            payload = json.loads(deals_path.read_text(encoding="utf-8"))
            for d in payload.get("deals") or []:
                sid = d.get("steamAppId")
                if sid:
                    ids.append(str(sid))
        except Exception:  # noqa: BLE001
            pass
    return ids


def write_steam_catalog() -> None:
    seen: set[str] = set()
    rows: list[dict] = []
    pairs = list(CURATED_STEAM_APPS)
    for aid in collect_appids_from_deals():
        pairs.append((aid, None))

    for appid, catalog_id in pairs:
        if appid in seen:
            continue
        seen.add(appid)
        print(f"Steam appdetails {appid}…")
        row = fetch_steam_app(appid)
        if not row:
            row = curated_fallback(appid, catalog_id)
        else:
            if catalog_id:
                row["catalogId"] = catalog_id
        rows.append(row)
        time.sleep(1.1)  # be polite to Steam

    payload = {
        "updatedAt": now_iso(),
        "source": "steam-store-appdetails",
        "count": len(rows),
        "apps": rows,
    }
    DATA.mkdir(parents=True, exist_ok=True)
    STEAM_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {STEAM_OUT} ({len(rows)} apps)")


def main() -> int:
    write_ping_targets()
    # Always refresh steam snapshot from this script (also invoked standalone)
    write_steam_catalog()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
