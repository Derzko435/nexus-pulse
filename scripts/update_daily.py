#!/usr/bin/env python3
"""Refresh data/daily.json with today's date and rotated sample content.

Intended for a daily cron / scheduled job:
  python3 scripts/update_daily.py

Deals live in data/deals.json and refresh more often via:
  python3 scripts/update_deals.py

Run from repo root or any cwd — paths resolve relative to this script.
"""
from __future__ import annotations

import json
import random
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "daily.json"

MSK = timezone(timedelta(hours=3), name="MSK")

GAMES_OF_DAY = [
    {
        "title": "Counter-Strike 2",
        "genre": "киберспорт",
        "reason": "Ранкид живой, античит свежий — идеальный вечер для калибровки.",
        "tip": "Лимит FPS = Hz монитора + 1, Xbox Game Bar выкл.",
        "platforms": ["PC"],
    },
    {
        "title": "Valorant",
        "genre": "киберспорт",
        "reason": "Новый патч агентов — фаст-лобби и тренировка aim lab.",
        "tip": "Прогрей Vanguard и закрой оверлеи перед матчем.",
        "platforms": ["PC"],
    },
    {
        "title": "Dota 2",
        "genre": "киберспорт",
        "reason": "Патч меняет драфт — лови окно, пока мета не устоялась.",
        "tip": "Смотри #гайды в Discord перед пабом.",
        "platforms": ["PC"],
    },
    {
        "title": "Elden Ring",
        "genre": "RPG",
        "reason": "Кооп-рейды по DLC снова в тренде — зови тиммейта.",
        "tip": "Пароль сессии + туман в #поиск-тимы.",
        "platforms": ["PC", "PS5", "Xbox"],
    },
    {
        "title": "Baldur's Gate 3",
        "genre": "RPG",
        "reason": "Идеальный день для длинной сессии с друзьями.",
        "tip": "Сохраняйся перед каждым ключевым диалогом.",
        "platforms": ["PC", "PS5"],
    },
    {
        "title": "Apex Legends",
        "genre": "FPS",
        "reason": "Сезонный реранк — лучшее окно поднять MMR.",
        "tip": "Играй трио, не соло, в прайм-тайм.",
        "platforms": ["PC", "PS5", "Xbox"],
    },
    {
        "title": "Hollow Knight",
        "genre": "инди",
        "reason": "Перед сиквелом — самое время пройти оригинал на 100%.",
        "tip": "Карта + шар — не стесняйся assist-темпа.",
        "platforms": ["PC", "Switch", "PS5"],
    },
]

TRENDING_POOL = [
    {"title": "Valorant", "note": "Фаст-лобби забиты под завязку", "heat": 90},
    {"title": "Counter-Strike 2", "note": "Вечерний ранкид на пике", "heat": 94},
    {"title": "Dota 2", "note": "Мета после патча ещё качается", "heat": 86},
    {"title": "Elden Ring", "note": "Кооп-рейды по DLC", "heat": 82},
    {"title": "Baldur's Gate 3", "note": "Хардкорные таймлайн-ранны", "heat": 78},
    {"title": "Apex Legends", "note": "Сезонный реранк", "heat": 80},
    {"title": "League of Legends", "note": "Сплит плейофф — смотрибельно", "heat": 77},
    {"title": "Hades", "note": "Рогалик для коротких сессий", "heat": 72},
    {"title": "DOOM Eternal", "note": "Рип энд тир на ультра", "heat": 70},
    {"title": "Stardew Valley", "note": "Уют после токсичного ранкеда", "heat": 68},
]

TIPS_POOL = [
    "Сегодня вечером пинг к EU ниже обычного — хорошее окно для ranked.",
    "Не забывай обновлять GPU-драйверы перед крупными патчами.",
    "В Discord #поиск-тимы уже собирают 5-ки после 21:00 MSK.",
    "Закрой Chrome с 40 вкладками — это бесплатные +10 FPS.",
    "Сделай бэкап конфигов CS2 / Valorant перед патчем.",
    "Разминка 10 минут в aim-тренере экономит первую карту.",
    "Проверь расписание турниров в секции «Киберспорт».",
    "Скидки дня — смотри тикер на главной, не упусти −70%.",
]

PATCH_POOL = [
    {
        "game": "Counter-Strike 2",
        "platforms": ["PC"],
        "note": "Усилен античит, фикс дыма на Ancient, баланс Desert Eagle.",
    },
    {
        "game": "Dota 2",
        "platforms": ["PC"],
        "note": "Нерф мид-саппортов, бафф Carry-темплейтов.",
    },
    {
        "game": "Valorant",
        "platforms": ["PC"],
        "note": "Хотфикс способностей: убран дабл-триггер ульты.",
    },
    {
        "game": "Apex Legends",
        "platforms": ["PC", "PS5", "Xbox"],
        "note": "Баланс оружия: R-301 ↓, Wingman ↑ в mid-range.",
    },
    {
        "game": "Overwatch 2",
        "platforms": ["PC", "PS5", "Xbox"],
        "note": "Патч поддержки: фикс хитбоксов и аудио-коллизий.",
    },
    {
        "game": "League of Legends",
        "platforms": ["PC"],
        "note": "Мини-патч: точечный нерф топ-лейна и бафф саппортов.",
    },
]

RELEASE_POOL = [
    {
        "title": "Hollow Knight: Silksong",
        "offset_days": 2,
        "platforms": ["PC", "Switch", "PS5", "Xbox"],
        "note": "Долгожданный сиквел — метроидвания нового поколения.",
    },
    {
        "title": "Mafia: The Old Country",
        "offset_days": 9,
        "platforms": ["PC", "PS5", "Xbox"],
        "note": "Истоки мафии, новая катсцена-кампания.",
    },
    {
        "title": "Monster Hunter Wilds — Title Update 2",
        "offset_days": 16,
        "platforms": ["PC", "PS5", "Xbox"],
        "note": "Новый монстр, оружие и сезонный ивент.",
    },
    {
        "title": "GTFO: Descent",
        "offset_days": 23,
        "platforms": ["PC"],
        "note": "Кооп-хоррор: новый рунд и перманентные апгрейды.",
    },
    {
        "title": "Path of Exile 2 — Early Access Wave 3",
        "offset_days": 30,
        "platforms": ["PC", "PS5"],
        "note": "Новые классы и эндгейм-маппинг.",
    },
    {
        "title": "ARC Raiders",
        "offset_days": 37,
        "platforms": ["PC", "PS5", "Xbox"],
        "note": "PvPvE экстракшн от Embark — открытый тест.",
    },
]

# Legacy pool kept for reference — live deals come from scripts/update_deals.py
DEALS_POOL = []

NEWS_POOL = [
    {
        "title": "Valve обновила античит в CS2: что изменилось для ранкеда",
        "text": "Короткий разбор новых детектов и влияния на паб.",
        "c1": "#1a3010",
        "c2": "#304010",
    },
    {
        "title": "RTX 50-й серии: первые независимые бенчи в 1440p",
        "text": "Сравниваем с 40-й линейкой в киберспорте и AAA.",
        "c1": "#101828",
        "c2": "#182848",
    },
    {
        "title": "The International: сетка и фавориты по коэффициентам",
        "text": "Кого ставят букмекеры и почему это ещё ничего не значит.",
        "c1": "#281018",
        "c2": "#401820",
    },
    {
        "title": "Инди-неделя: 5 релизов, которые стоит попробовать",
        "text": "От мрачных метроидваний до уютных симов.",
        "c1": "#181028",
        "c2": "#281840",
    },
    {
        "title": "Как стримерам не сгореть: режим и оборудование",
        "text": "Практический чеклист от комьюнити NEXUS PULSE.",
        "c1": "#102028",
        "c2": "#183040",
    },
    {
        "title": "Steam Deck OLED vs ROG Ally: что брать геймеру",
        "text": "Автономия, Windows-игры и реальный комфорт в поездках.",
        "c1": "#201810",
        "c2": "#382818",
    },
    {
        "title": "Discord NEXUS PULSE: новые каналы #скидки и #голос-лобби",
        "text": "Как устроен сервер и куда писать в поиске тимы.",
        "c1": "#181030",
        "c2": "#2a1848",
    },
    {
        "title": "Патч-день: что ставить в первую очередь",
        "text": "Чеклист обновлений игр и драйверов на неделю.",
        "c1": "#102020",
        "c2": "#183838",
    },
]


NEW_INTERESTING_POOL = [
    {
        "title": "Hollow Knight: Silksong",
        "genre": "инди / метроидвания",
        "platforms": ["PC", "Switch", "PS5", "Xbox"],
        "blurb": "Долгожданный сиквел наконец здесь — быстрее, плотнее и с новым героем.",
        "tag": "новинка",
        "offset_days": 0,
        "c1": "#1a1030",
        "c2": "#3a1858",
    },
    {
        "title": "Clair Obscur: Expedition 33",
        "genre": "RPG",
        "platforms": ["PC", "PS5", "Xbox"],
        "blurb": "Французское JRPG с пейнт-панк эстетикой — свежий взгляд на пошаговые бои.",
        "tag": "инди-находка",
        "offset_days": -14,
        "c1": "#101828",
        "c2": "#283858",
    },
    {
        "title": "Split Fiction",
        "genre": "кооп / экшен",
        "platforms": ["PC", "PS5", "Xbox"],
        "blurb": "Кооп от создателей It Takes Two — идеальный вечер вдвоём на диване.",
        "tag": "новинка",
        "offset_days": -30,
        "c1": "#281018",
        "c2": "#482028",
    },
    {
        "title": "Path of Exile 2",
        "genre": "ARPG",
        "platforms": ["PC", "PS5"],
        "blurb": "Волна раннего доступа: новые классы и эндгейм, ради которого стоит зайти.",
        "tag": "ранний доступ",
        "offset_days": -5,
        "c1": "#201010",
        "c2": "#402018",
    },
    {
        "title": "Doom: The Dark Ages",
        "genre": "FPS",
        "platforms": ["PC", "PS5", "Xbox"],
        "blurb": "Средневековый DOOM с щитом и драконом — рип энд тир в новом сеттинге.",
        "tag": "новинка",
        "offset_days": -60,
        "c1": "#181010",
        "c2": "#381818",
    },
    {
        "title": "Blue Prince",
        "genre": "пазл / рогалик",
        "platforms": ["PC", "PS5", "Xbox"],
        "blurb": "Особняк, который перестраивается каждый день — самая обсуждаемая головоломка года.",
        "tag": "инди-находка",
        "offset_days": -90,
        "c1": "#102028",
        "c2": "#183848",
    },
    {
        "title": "Kingdom Come: Deliverance II",
        "genre": "RPG",
        "platforms": ["PC", "PS5", "Xbox"],
        "blurb": "Средневековье без магии: реалистичный RPG, к которому возвращаются спустя месяцы.",
        "tag": "возвращение",
        "offset_days": -120,
        "c1": "#201810",
        "c2": "#3a2818",
    },
    {
        "title": "Schedule I",
        "genre": "симулятор",
        "platforms": ["PC"],
        "blurb": "Нелегальный бизнес-сим в раннем доступе — неожиданный хит Steam.",
        "tag": "ранний доступ",
        "offset_days": -20,
        "c1": "#102018",
        "c2": "#184028",
    },
    {
        "title": "Monster Hunter Wilds",
        "genre": "экшен",
        "platforms": ["PC", "PS5", "Xbox"],
        "blurb": "После title update охота снова в тренде — зови тиммейтов в #поиск-тимы.",
        "tag": "возвращение",
        "offset_days": -45,
        "c1": "#281810",
        "c2": "#483018",
    },
    {
        "title": "Peak",
        "genre": "кооп / инди",
        "platforms": ["PC"],
        "blurb": "Кооп-скалолазание с физикой хаоса — коротко, смешно, идеально для стрима.",
        "tag": "инди-находка",
        "offset_days": -10,
        "c1": "#102030",
        "c2": "#184060",
    },
    {
        "title": "Death Stranding 2",
        "genre": "экшен",
        "platforms": ["PS5", "PC"],
        "blurb": "Кодзима снова про доставку и связь — атмосферный сиквел для длинных сессий.",
        "tag": "новинка",
        "offset_days": -7,
        "c1": "#101820",
        "c2": "#203040",
    },
    {
        "title": "Hades II",
        "genre": "рогалик",
        "platforms": ["PC"],
        "blurb": "Супергил доводит ранний доступ — Мелиноя и новые регионы уже на высоте.",
        "tag": "ранний доступ",
        "offset_days": -40,
        "c1": "#181028",
        "c2": "#301848",
    },
    {
        "title": "Balatro",
        "genre": "рогалик / карты",
        "platforms": ["PC", "Switch", "PS5", "Xbox"],
        "blurb": "Покерный рогалик, к которому возвращаются «на одну партию» — и пропадают на час.",
        "tag": "возвращение",
        "offset_days": -200,
        "c1": "#281018",
        "c2": "#401820",
    },
    {
        "title": "Animal Well",
        "genre": "метроидвания",
        "platforms": ["PC", "PS5", "Switch"],
        "blurb": "Пиксельная метроидвания с секретами на секретах — идеальная инди-находка.",
        "tag": "инди-находка",
        "offset_days": -150,
        "c1": "#0e2018",
        "c2": "#184030",
    },
]

MONTHS_RU = [
    "", "янв", "фев", "мар", "апр", "май", "июн",
    "июл", "авг", "сен", "окт", "ноя", "дек",
]


def fmt_ru(d: date) -> str:
    return f"{d.day:02d} {MONTHS_RU[d.month]} {d.year}"


def patch_label(patch_date: date, today: date) -> str:
    delta = (today - patch_date).days
    if delta == 0:
        return "сегодня"
    if delta == 1:
        return "вчера"
    return f"{patch_date.day} {MONTHS_RU[patch_date.month]}"


def build_payload(today: date | None = None) -> dict:
    today = today or datetime.now(MSK).date()
    rng = random.Random(today.toordinal())  # stable per day

    gotd = rng.choice(GAMES_OF_DAY)
    trending = rng.sample(TRENDING_POOL, k=5)
    for i, t in enumerate(trending):
        t = dict(t)
        t["heat"] = max(60, min(99, t["heat"] + rng.randint(-4, 4) - i))
        trending[i] = t
    trending.sort(key=lambda x: x["heat"], reverse=True)

    tips = rng.sample(TIPS_POOL, k=3)

    patches = []
    chosen_patches = rng.sample(PATCH_POOL, k=4)
    for i, p in enumerate(chosen_patches):
        pd = today - timedelta(days=i)
        patches.append(
            {
                "game": p["game"],
                "date": pd.isoformat(),
                "label": patch_label(pd, today),
                "platforms": p["platforms"],
                "note": p["note"],
            }
        )

    releases = []
    for r in sorted(RELEASE_POOL, key=lambda x: x["offset_days"])[:5]:
        rd = today + timedelta(days=r["offset_days"])
        releases.append(
            {
                "title": r["title"],
                "date": rd.isoformat(),
                "platforms": r["platforms"],
                "note": r["note"],
            }
        )

    # Deals are maintained separately in data/deals.json (see update_deals.py)
    news_items = rng.sample(NEWS_POOL, k=6)
    news = []
    for i, n in enumerate(news_items):
        nd = today - timedelta(days=i)
        news.append(
            {
                "date": fmt_ru(nd),
                "title": n["title"],
                "text": n["text"],
                "c1": n["c1"],
                "c2": n["c2"],
            }
        )

    # 8 spotlight cards; stable rotation keyed by today's date
    new_interesting = []
    for g in rng.sample(NEW_INTERESTING_POOL, k=8):
        spotlight = today + timedelta(days=g["offset_days"])
        new_interesting.append(
            {
                "title": g["title"],
                "genre": g["genre"],
                "platforms": g["platforms"],
                "blurb": g["blurb"],
                "tag": g["tag"],
                "date": spotlight.isoformat(),
                "c1": g["c1"],
                "c2": g["c2"],
            }
        )

    now = datetime.now(MSK).replace(microsecond=0)
    return {
        "date": today.isoformat(),
        "updatedAt": now.isoformat(),
        "gameOfTheDay": gotd,
        "trending": trending,
        "tips": tips,
        "patches": patches,
        "releases": releases,
        "news": news,
        "newInterestingGames": new_interesting,
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    payload = build_payload()
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[NEXUS PULSE] daily.json обновлён → {OUT}")
    print(f"  date={payload['date']}  gameOfTheDay={payload['gameOfTheDay']['title']}  newGames={len(payload['newInterestingGames'])}")


if __name__ == "__main__":
    main()
