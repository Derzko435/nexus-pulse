#!/usr/bin/env python3
"""OPTIONAL Steam Web API helper for library snapshots.

Skips entirely when STEAM_API_KEY is unset. Writes data/steam_profiles_snapshot.json
for configured STEAM_PROFILE_IDS (comma-separated SteamID64).
Browser clients still use manual checklist as primary import path.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "steam_profiles_snapshot.json"
MSK = timezone(timedelta(hours=3), name="MSK")
UA = "NexusPulseSteamProfiles/1.0 (+Actions optional)"


def main() -> int:
    key = (os.environ.get("STEAM_API_KEY") or "").strip()
    if not key:
        print("STEAM_API_KEY not set — skipping update_steam_profiles.py")
        return 0

    ids_raw = (os.environ.get("STEAM_PROFILE_IDS") or "").strip()
    if not ids_raw:
        print("STEAM_PROFILE_IDS empty — nothing to fetch")
        return 0

    steamids = [x.strip() for x in ids_raw.split(",") if x.strip()]
    profiles = []
    for sid in steamids:
        qs = urllib.parse.urlencode(
            {"key": key, "steamid": sid, "include_appinfo": 1, "include_played_free_games": 1}
        )
        url = f"https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/?{qs}"
        req = urllib.request.Request(url, headers={"User-Agent": UA})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8", "replace"))
            games = ((data.get("response") or {}).get("games")) or []
            profiles.append(
                {
                    "steamid": sid,
                    "game_count": len(games),
                    "games": [
                        {
                            "appid": g.get("appid"),
                            "name": g.get("name"),
                            "playtime_forever": g.get("playtime_forever"),
                        }
                        for g in games
                    ],
                }
            )
            print(f"Fetched {len(games)} games for {sid}")
        except Exception as e:  # noqa: BLE001
            print(f"Failed {sid}: {e}", file=sys.stderr)
            profiles.append({"steamid": sid, "error": str(e)})
        time.sleep(0.5)

    payload = {
        "updatedAt": datetime.now(MSK).isoformat(timespec="seconds"),
        "source": "steam-webapi-GetOwnedGames",
        "profiles": profiles,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
