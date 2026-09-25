#!/usr/bin/env python3
"""Catalog pictures + short official descriptions → data/catalog.json

Steam games: header image + Russian short description from the Steam store.
Games that are not on Steam: official artwork from the game's Wikipedia page
(lead image) + a short Russian description written by the editors below.
Entries that fail keep their previous value.
"""
from __future__ import annotations

import time
import urllib.parse

from np_common import DATA, clean_text, clip, fetch_json, log, now_msk_iso, read_json, safe_url, write_json_if_good

OUT = DATA / "catalog.json"

STEAM = {
    "cp2077": 1091500, "elden": 1245620, "bg3": 1086940, "witcher3": 292030, "rdr2": 1174180,
    "gtav": 271590, "skyrim": 489830, "ffxiv": 39210, "wukong": 2358720, "persona5": 1687950,
    "diablo4": 2344520, "poe2": 2694490, "cs2": 730, "dota2": 570, "rocket": 252950, "r6": 359550,
    "apex": 1172470, "ow2": 2357570, "doom": 782330, "halo": 1240440, "codmw": 2519060,
    "destiny2": 1085660, "titanfall2": 1237970, "ultrakill": 1229490, "civ6": 289070, "aoe4": 1466860,
    "xcom2": 268500, "totalwar": 1142710, "ck3": 1158310, "stellaris": 281990, "hoi4": 394360,
    "rimworld": 294100, "hollow": 367520, "hades": 1145360, "celeste": 504230, "stardew": 413150,
    "hades2": 1145350, "balatro": 2379780, "vampire": 1794680, "outerwilds": 753640, "re4": 2050650,
    "reVillage": 1196590, "phasmo": 739630, "outlast": 1304930, "deadspace": 1693980, "lethal": 1966720,
    "forza5": 1551360, "f1_24": 2488620, "dirt": 690790, "nfs": 1846380, "assetto": 805550,
    "msfs": 1250410, "ets2": 227300, "farming": 2300320, "cities": 949230, "ibeam": 284160,
    "snowrunner": 1465360, "gow": 2322010, "spiderman2": 2651280, "sekiro": 814380, "mhwilds": 2246340,
    "hogwarts": 990080, "acvalhalla": 2208920, "gw2": 1284210, "eso": 306130, "lostark": 1599340,
    "newworld": 1063730, "throne": 2429640,
}

# Not on Steam → Wikipedia page for the official key art + our own short description.
NON_STEAM = {
    "valorant": ("Valorant", "https://playvalorant.com/ru-ru/",
                 "Тактический шутер 5 на 5 от Riot Games: у каждого агента свои способности, но решают точная стрельба, экономика раундов и командная игра."),
    "lol": ("League of Legends", "https://www.leagueoflegends.com/ru-ru/",
            "Командная MOBA 5 на 5: выбираешь чемпиона, фармишь линию, сносишь башни и вместе с командой рушишь вражеский Нексус."),
    "fortnite": ("Fortnite", "https://www.fortnite.com/?lang=ru",
                 "Бесплатная королевская битва от Epic Games на 100 игроков со строительством, постоянными сезонами, коллаборациями и творческими режимами."),
    "alanwake2": ("Alan_Wake_2", "https://www.alanwake.com/",
                  "Сюжетный хоррор от Remedy: писатель Алан Уэйк и агент ФБР Сага Андерсон распутывают кошмар, где реальность переписывается по рукописи."),
    "gt7": ("Gran_Turismo_7", "https://www.gran-turismo.com/ru/gt7/",
            "Автосимулятор Polyphony Digital для PlayStation: сотни реальных машин, тюнинг, лицензии, карьера и сетевые гонки с честной физикой."),
    "totk": ("The_Legend_of_Zelda:_Tears_of_the_Kingdom", "https://www.nintendo.com/us/store/products/the-legend-of-zelda-tears-of-the-kingdom-switch/",
             "Продолжение Breath of the Wild для Nintendo Switch: небесные острова, подземелья и способности Линка, позволяющие собирать из предметов что угодно."),
    "wow": ("World_of_Warcraft", "https://worldofwarcraft.blizzard.com/",
            "Легендарная MMORPG Blizzard: прокачка, подземелья, рейды, эпохальные ключи и PvP в мире Азерота, который развивается с каждым дополнением."),
}


def _ru_only(text: str) -> str:
    """Keep the store description only when it is in Russian (site text must be Russian)."""
    import re
    return text if len(re.findall(r"[А-Яа-яЁё]", text)) > len(text) * 0.3 else ""


# Official sites of these two only expose tiny icons as preview → use the logo, shown "contained".
LOGO_ONLY = {"valorant", "lol"}
# Logos are stored with the site (no hotlinking of third-party thumbnails).
LOCAL_IMG = {"valorant": "./assets/games/valorant.png", "lol": "./assets/games/lol.png"}
# gran-turismo.com blocks hotlinking → official key art from the PlayStation Store page.
FIXED_IMG = {"gt7": "https://image.api.playstation.com/vulcan/ap/rnd/202109/1321/yQv1bEL3MXZbNW6l4RMYgUd2.png?w=960"}


def steam_details(appid: int) -> dict | None:
    for cc in ("ru", "us", "de"):
        info = _steam_details(appid, cc)
        if info:
            return info
        time.sleep(1.0)
    return None


def _steam_details(appid: int, cc: str) -> dict | None:
    url = f"https://store.steampowered.com/api/appdetails?appids={appid}&cc={cc}&l=russian"
    data = fetch_json(url, timeout=30)
    # Steam sometimes keys the answer by a different (package) id — take the only value
    node = (data or {}).get(str(appid)) or next(iter((data or {}).values()), {}) or {}
    if not node.get("success"):
        return None
    d = node["data"]
    return {
        "name": d.get("name") or "",
        "img": safe_url(d.get("header_image")),
        "capsule": safe_url(d.get("capsule_image")),
        "desc": _ru_only(clip(clean_text(d.get("short_description")), 320)),
        "url": f"https://store.steampowered.com/app/{appid}/",
        "appid": appid,
        "genres": [g.get("description") for g in (d.get("genres") or [])][:4],
        "release": clean_text((d.get("release_date") or {}).get("date")),
    }


def official_og_image(url: str) -> str:
    from bs4 import BeautifulSoup
    from np_common import fetch_text, og_image
    soup = BeautifulSoup(fetch_text(url, timeout=30), "html.parser")
    return og_image(soup)


def wiki_image(title: str) -> str:
    url = "https://en.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(title, safe="")
    data = fetch_json(url, timeout=30, headers={"User-Agent": "NexusPulse/1.0 (https://derzko435.github.io/nexus-pulse/)"})
    img = (data.get("originalimage") or data.get("thumbnail") or {}).get("source")
    return safe_url(img)


def main() -> int:
    old = (read_json(OUT, {}) or {}).get("games", {}) or {}
    games: dict = {}
    for gid, appid in STEAM.items():
        try:
            info = steam_details(appid)
            if info and info["img"]:
                games[gid] = info
            else:
                log(f"[steam-miss] {gid} {appid}")
            if (not info or not info["img"]) and gid in old:
                games[gid] = old[gid]
        except Exception as e:  # noqa: BLE001
            log(f"[steam-fail] {gid}: {e}")
            if gid in old:
                games[gid] = old[gid]
        time.sleep(1.2)
    for gid, (wtitle, site, desc) in NON_STEAM.items():
        entry = {"desc": desc, "url": site, "img": LOCAL_IMG.get(gid) or FIXED_IMG.get(gid, "")}
        if gid in LOGO_ONLY:
            entry["fit"] = "contain"
        elif not entry["img"]:
            try:
                entry["img"] = official_og_image(site)
            except Exception as e:  # noqa: BLE001
                log(f"[og-fail] {gid}: {e}")
        if not entry["img"]:
            try:
                entry["img"] = wiki_image(wtitle)
            except Exception as e:  # noqa: BLE001
                log(f"[wiki-fail] {gid}: {e}")
        if not entry["img"] and gid in old:
            entry["img"] = old[gid].get("img", "")
        games[gid] = entry
        time.sleep(0.5)
    payload = {"updatedAt": now_msk_iso(), "ids": sorted(games.keys()), "games": games}
    write_json_if_good(OUT, payload, "ids", 40)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
