#!/usr/bin/env python3
"""Refresh data/deals.json more aggressively than daily content.

Intended for a frequent cron (e.g. every 4–6 hours):
  python3 scripts/update_deals.py

Deals rotate with steeper discounts and varied stores
(Steam, Epic, PlayStation, Xbox, Nintendo). Daily pulse/calendar
content stays in data/daily.json and is updated separately.
"""
from __future__ import annotations

import argparse
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "deals.json"
MSK = timezone(timedelta(hours=3), name="MSK")

DEALS_POOL = [
    {"id": "d1", "title": "Cyberpunk 2077 + Phantom Liberty", "store": "Steam", "old": 3499, "pct_opts": [50, 60, 70]},
    {"id": "d2", "title": "Baldur's Gate 3", "store": "Steam", "old": 2999, "pct_opts": [30, 40, 50]},
    {"id": "d3", "title": "Elden Ring + Shadow of the Erdtree", "store": "Steam", "old": 5499, "pct_opts": [40, 50, 60]},
    {"id": "d4", "title": "Hades II", "store": "Epic", "old": 1299, "pct_opts": [25, 35, 40]},
    {"id": "d5", "title": "Total War: Warhammer III", "store": "Steam", "old": 2499, "pct_opts": [70, 75, 80]},
    {"id": "d6", "title": "DOOM Eternal Deluxe", "store": "Steam", "old": 1999, "pct_opts": [70, 75, 80]},
    {"id": "d7", "title": "Red Dead Redemption 2", "store": "Steam", "old": 2999, "pct_opts": [60, 67, 75]},
    {"id": "d8", "title": "God of War Ragnarök", "store": "PlayStation", "old": 6990, "pct_opts": [40, 50, 55]},
    {"id": "d9", "title": "Forza Horizon 5 Premium", "store": "Xbox", "old": 4999, "pct_opts": [50, 60, 70]},
    {"id": "d10", "title": "Zelda: Tears of the Kingdom", "store": "Nintendo", "old": 5999, "pct_opts": [20, 25, 30]},
    {"id": "d11", "title": "Resident Evil 4 Remake", "store": "Steam", "old": 3499, "pct_opts": [50, 60, 67]},
    {"id": "d12", "title": "Starfield + Shattered Space", "store": "Xbox", "old": 4499, "pct_opts": [40, 50, 55]},
    {"id": "d13", "title": "Hollow Knight", "store": "Steam", "old": 599, "pct_opts": [40, 50, 60]},
    {"id": "d14", "title": "Celeste", "store": "Epic", "old": 799, "pct_opts": [50, 60, 75]},
    {"id": "d15", "title": "Monster Hunter Wilds", "store": "Steam", "old": 4999, "pct_opts": [20, 25, 30]},
    {"id": "d16", "title": "Spider-Man 2", "store": "PlayStation", "old": 6990, "pct_opts": [30, 40, 50]},
    {"id": "d17", "title": "Sea of Thieves", "store": "Xbox", "old": 2499, "pct_opts": [50, 60, 70]},
    {"id": "d18", "title": "Animal Crossing: New Horizons", "store": "Nintendo", "old": 4499, "pct_opts": [20, 25, 33]},
    {"id": "d19", "title": "Black Myth: Wukong", "store": "Steam", "old": 3999, "pct_opts": [20, 25, 35]},
    {"id": "d20", "title": "Alan Wake 2", "store": "Epic", "old": 3499, "pct_opts": [40, 50, 60]},
    {"id": "d21", "title": "Horizon Forbidden West", "store": "PlayStation", "old": 4990, "pct_opts": [50, 60, 70]},
    {"id": "d22", "title": "Halo Infinite Campaign", "store": "Xbox", "old": 2999, "pct_opts": [50, 60, 75]},
    {"id": "d23", "title": "Metroid Dread", "store": "Nintendo", "old": 3999, "pct_opts": [25, 33, 40]},
    {"id": "d24", "title": "Dead Space Remake", "store": "Steam", "old": 3499, "pct_opts": [50, 60, 70]},
]


def build_deals(count: int = 12) -> dict:
    now = datetime.now(MSK).replace(microsecond=0)
    # Seed on hour bucket so re-runs within same hour are stable, but
    # a 4–6h cron still rotates aggressively across the day.
    hour_bucket = now.replace(minute=0, second=0)
    rng = random.Random(int(hour_bucket.timestamp()) // 14400)  # 4h buckets

    chosen = rng.sample(DEALS_POOL, k=min(count, len(DEALS_POOL)))
    deals = []
    for item in chosen:
        pct = rng.choice(item["pct_opts"])
        neu = max(99, int(round(item["old"] * (100 - pct) / 100)))
        deals.append(
            {
                "id": item["id"],
                "title": item["title"],
                "store": item["store"],
                "old": item["old"],
                "neu": neu,
                "pct": pct,
            }
        )
    deals.sort(key=lambda d: d["pct"], reverse=True)
    return {"updatedAt": now.isoformat(), "deals": deals}


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh NEXUS PULSE deals.json")
    parser.add_argument("--count", type=int, default=12, help="How many deals to publish")
    args = parser.parse_args()

    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = build_deals(count=args.count)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[NEXUS PULSE] deals.json обновлён → {OUT}")
    print(f"  updatedAt={payload['updatedAt']}  deals={len(payload['deals'])}")
    top = payload["deals"][0]
    print(f"  top: {top['title']} −{top['pct']}% ({top['store']})")


if __name__ == "__main__":
    main()
