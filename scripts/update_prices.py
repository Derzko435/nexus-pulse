#!/usr/bin/env python3
"""Current Steam prices (RU region, rubles) for catalog games → data/prices.json

Used by the «Отслеживаю цены» block on the site: current price, regular price
and discount for every Steam game of the catalog. Games that are not sold in
the RU region simply have no entry. If Steam fails, the previous file is kept.
"""
from __future__ import annotations

import time

from np_common import DATA, fetch_json, log, now_msk_iso, write_json_if_good
from update_catalog import STEAM

OUT = DATA / "prices.json"
CHUNK = 25


def main() -> int:
    items = list(STEAM.items())
    by_appid = {str(appid): gid for gid, appid in items}
    prices: dict = {}
    for i in range(0, len(items), CHUNK):
        ids = ",".join(str(a) for _, a in items[i:i + CHUNK])
        url = f"https://store.steampowered.com/api/appdetails?appids={ids}&cc=ru&filters=price_overview"
        try:
            data = fetch_json(url, timeout=30) or {}
        except Exception as e:  # noqa: BLE001
            log(f"[prices-fail] chunk {i}: {e}")
            data = {}
        for appid, node in data.items():
            gid = by_appid.get(str(appid))
            if not gid or not isinstance(node, dict) or not node.get("success"):
                continue
            d = node.get("data")
            if isinstance(d, list) or not d:  # free or not sold in the region → no price
                continue
            po = d.get("price_overview") or {}
            if po.get("currency") != "RUB" or po.get("final") is None:
                continue
            prices[gid] = {
                "appid": int(appid),
                "final": round(int(po["final"]) / 100),
                "initial": round(int(po.get("initial") or po["final"]) / 100),
                "pct": int(po.get("discount_percent") or 0),
            }
        time.sleep(1.5)
    payload = {"updatedAt": now_msk_iso(), "source": "steam-store", "ids": sorted(prices), "prices": prices}
    write_json_if_good(OUT, payload, "ids", 15)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
