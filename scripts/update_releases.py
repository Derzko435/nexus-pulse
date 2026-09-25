#!/usr/bin/env python3
"""Release calendar + new games: Steam, PlayStation, Xbox, Nintendo Switch and Epic.

data/releases.json  — upcoming releases with exact dates (next ~5 months):
                      * Steam (RU storefront): most wished-for / pre-ordered games
                      * consoles: Wikipedia «List of video games released in <year>» —
                        only titles that have their own Wikipedia article (notable games)
                        and a worldwide/western release date (no Japan-only dates)
                      * Epic Games Store: public "coming soon" catalog (no key needed) —
                        marks games also sold in Epic and adds the Epic store link
data/new_games.json — popular games released in the last ~6 weeks (Steam top sellers
                      + notable console releases from the same Wikipedia list).

Every item: platforms (PC / PlayStation / Xbox / Switch), stores (Steam / Epic).
Only real store/encyclopedia data. Adult-only titles are filtered out. If a source fails,
the others still work; if everything fails the previous files are kept.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta

from bs4 import BeautifulSoup

from np_common import (
    DATA, MSK, clean_text, clip, fetch_json, log, now_msk_iso, safe_url, write_json_if_good,
)

try:
    from np_translate import Translator
except Exception:  # noqa: BLE001
    Translator = None  # type: ignore

RU_MONTHS = {"янв": 1, "фев": 2, "мар": 3, "апр": 4, "мая": 5, "май": 5, "июн": 6, "июл": 7,
             "авг": 8, "сен": 9, "окт": 10, "ноя": 11, "дек": 12}
ADULT_RE = re.compile(r"(hentai|хентай|erotic|эроти|эроп|waifu|nsfw|sex|milf|tomboy|ntr\b|lewd|nude|18\+|porn|girls vs|succub|harem|гарем)", re.I)
SEARCH = "https://store.steampowered.com/search/results/?query&start={start}&count={count}&{q}&infinite=1&cc=ru&l=russian&ignore_preferences=1&category1=998"
ROW_RE = re.compile(r'<a href="https://store\.steampowered\.com/app/(\d+)/[^"]*"[^>]*class="search_result_row[^"]*"(.*?)</a>', re.S)


def parse_ru_date(s: str) -> date | None:
    s = clean_text(s).lower()
    m = re.search(r"(\d{1,2})\s+([а-я]{3})[а-я]*\.?\s+(\d{4})", s)
    if not m:
        return None
    mon = RU_MONTHS.get(m.group(2))
    if not mon:
        return None
    try:
        return date(int(m.group(3)), mon, int(m.group(1)))
    except ValueError:
        return None


def search_rows(q: str, pages: int, count: int = 100) -> list[dict]:
    rows = []
    for p in range(pages):
        try:
            data = fetch_json(SEARCH.format(start=p * count, count=count, q=q), timeout=40)
        except Exception as e:  # noqa: BLE001
            log(f"[search-fail] {q} p{p}: {e}")
            break
        html = data.get("results_html") or ""
        for appid, body in ROW_RE.findall(html):
            title = clean_text((re.search(r'class="title">([^<]*)<', body) or [None, ""])[1])
            rel = clean_text((re.search(r'search_released[^>]*>\s*([^<]*?)\s*<', body) or [None, ""])[1])
            rows.append({"appid": int(appid), "title": title, "releaseText": rel, "date": parse_ru_date(rel)})
        time.sleep(1.0)
    return rows


def details(appid: int) -> dict | None:
    for cc in ("ru", "us"):
        try:
            data = fetch_json(f"https://store.steampowered.com/api/appdetails?appids={appid}&cc={cc}&l=russian", timeout=30)
        except Exception as e:  # noqa: BLE001
            log(f"[details-fail] {appid}: {e}")
            return None
        node = (data or {}).get(str(appid)) or next(iter((data or {}).values()), {}) or {}
        if node.get("success"):
            return node["data"]
        time.sleep(0.8)
    return None


def is_adult(d: dict, title: str) -> bool:
    ids = set((d.get("content_descriptors") or {}).get("ids") or [])
    if ids & {1, 3, 4}:
        return True
    text = " ".join([title, d.get("short_description") or "", " ".join(g.get("description", "") for g in d.get("genres") or [])])
    if ADULT_RE.search(text):
        return True
    return any((g.get("id") in ("71", "72")) for g in d.get("genres") or [])  # Nudity / Sexual Content genres


CJK_RE = re.compile(r"[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af]")


def readable(d: dict) -> bool:
    text = clean_text(d.get("short_description"))
    return bool(text) and len(CJK_RE.findall(text)) < len(text) * 0.2


def price_text(d: dict) -> str:
    if d.get("is_free"):
        return "Бесплатно"
    po = d.get("price_overview") or {}
    if po.get("final_formatted"):
        return clean_text(po["final_formatted"])
    return ""


def make_item(row: dict, d: dict, dt: date) -> dict:
    genres = [clean_text(g.get("description")) for g in d.get("genres") or []][:3]
    plats = [name for key, name in (("windows", "PC"), ("mac", "Mac"), ("linux", "Linux")) if (d.get("platforms") or {}).get(key)]
    return {
        "appid": row["appid"],
        "title": clean_text(d.get("name")) or row["title"],
        "date": dt.isoformat(),
        "image": safe_url(d.get("header_image")),
        "desc": clip(clean_text(d.get("short_description")), 300),
        "genres": genres,
        "platforms": plats or ["PC"],
        "stores": ["Steam"],
        "developer": clean_text(", ".join((d.get("developers") or [])[:2])),
        "price": price_text(d),
        "url": f"https://store.steampowered.com/app/{row['appid']}/",
        "links": {"steam": f"https://store.steampowered.com/app/{row['appid']}/"},
    }


def build_releases(today: date) -> list[dict]:
    horizon = today + timedelta(days=150)
    seen: set = set()

    def pick(q: str, pages: int, count: int = 100, strict: bool = False) -> list[dict]:
        got = []
        for r in search_rows(q, pages=pages, count=count):
            if not r["date"] or (strict and r["date"] <= today):
                continue
            if today <= r["date"] <= horizon and r["appid"] not in seen:
                seen.add(r["appid"]); got.append(r)
        return got

    # 1) pre-orders among top sellers, 2) most wishlisted upcoming games — the releases people wait for
    primary = pick("filter=topsellers&sort_by=Released_DESC", 1, 60, strict=True) + pick("filter=popularwishlist", 3)
    # 3) popular "coming soon" only as a filler when the big list is short
    filler = pick("filter=popularcomingsoon", 2)

    def resolve(rows: list[dict], limit: int, out: list[dict]) -> None:
        for r in rows:
            if len(out) >= limit:
                return
            if ADULT_RE.search(r["title"]):
                continue
            d = details(r["appid"])
            time.sleep(1.1)
            if not d or d.get("type") != "game" or is_adult(d, r["title"]) or not readable(d):
                continue
            rd = d.get("release_date") or {}
            dt = parse_ru_date(rd.get("date") or "") or r["date"]
            if not dt or not (today <= dt <= horizon):
                continue
            item = make_item(r, d, dt)
            if item["image"]:
                out.append(item)

    out: list[dict] = []
    resolve(primary, 24, out)
    if len(out) < 14:
        resolve(filler, 18, out)
    out.sort(key=lambda x: (x["date"], x["title"]))
    return out


def build_new_games(today: date) -> list[dict]:
    since = today - timedelta(days=45)
    rows = [r for r in search_rows("filter=topsellers", pages=3, count=100) if r["date"] and since <= r["date"] <= today]
    out = []
    seen = set()
    for r in rows:
        if r["appid"] in seen or ADULT_RE.search(r["title"]):
            continue
        seen.add(r["appid"])
        d = details(r["appid"])
        time.sleep(1.1)
        if not d or d.get("type") != "game" or is_adult(d, r["title"]) or not readable(d):
            continue
        item = make_item(r, d, r["date"])
        rec = (d.get("recommendations") or {}).get("total")
        if rec:
            item["reviews"] = int(rec)
        if item["image"]:
            out.append(item)
        if len(out) >= 12:
            break
    return out  # keep top-seller order (most popular first)


# ====================================================================== consoles (Wikipedia)
WIKI_API = "https://{lang}.wikipedia.org/w/api.php"
WIKI_UA = "NexusPulseBot/1.0 (https://derzko435.github.io/nexus-pulse/; GitHub Actions daily refresh)"
MONTHS_EN = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august",
                                          "september", "october", "november", "december"], 1)}
PLATFORM_MAP = {  # Wikipedia abbreviations → site platform groups
    "WIN": "PC", "PS5": "PlayStation", "PS4": "PlayStation", "XBX/S": "Xbox", "XBO": "Xbox", "XSX": "Xbox",
    "NS": "Switch", "NS2": "Switch", "OSX": "Mac", "MAC": "Mac", "LIN": "Linux",
}
CONSOLES = {"PlayStation", "Xbox", "Switch"}
REGION_SKIP = {"JP", "KR", "CN", "TW", "AS", "SEA", "HK"}
PLAT_ORDER = ["PC", "PlayStation", "Xbox", "Switch", "Mac", "Linux"]


def wiki_get(params: dict, lang: str = "en") -> dict:
    q = dict(params, format="json", formatversion="2", maxlag="5")
    return fetch_json(WIKI_API.format(lang=lang) + "?" + urllib.parse.urlencode(q),
                      headers={"User-Agent": WIKI_UA, "Api-User-Agent": WIKI_UA}, timeout=40)


def table_grid(table) -> list[list]:
    """Expand a wikitable into a grid honouring rowspan/colspan (cells are bs4 tags)."""
    grid: list[list] = []
    carry: dict[int, tuple] = {}  # col → (cell, rows_left)
    for tr in table.find_all("tr"):
        cells = tr.find_all(["td", "th"], recursive=False)
        row: list = []
        col = 0
        it = iter(cells)
        pending = next(it, None)
        while pending is not None or any(c >= col for c in carry):
            if col in carry:
                cell, left = carry[col]
                row.append(cell)
                if left <= 1:
                    del carry[col]
                else:
                    carry[col] = (cell, left - 1)
                col += 1
                continue
            if pending is None:
                break
            span = int(re.sub(r"\D", "", pending.get("colspan") or "1") or 1)
            rs = int(re.sub(r"\D", "", pending.get("rowspan") or "1") or 1)
            for _ in range(span):
                row.append(pending)
                if rs > 1:
                    carry[col] = (pending, rs - 1)
                col += 1
            pending = next(it, None)
        grid.append(row)
    return grid


def wiki_year_rows(year: int) -> list[dict]:
    try:
        data = wiki_get({"action": "parse", "page": f"List_of_video_games_released_in_{year}", "prop": "text",
                         "redirects": "1"})
    except Exception as e:  # noqa: BLE001
        log(f"[wiki-fail] {year}: {e}")
        return []
    html = ((data or {}).get("parse") or {}).get("text") or ""
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for table in soup.select("table.wikitable"):
        head = [clean_text(c.get_text(" ")).lower() for c in (table.find("tr") or soup.new_tag("tr")).find_all(["th", "td"])]
        if not head or not head[0].startswith("release date") or "title" not in " ".join(head):
            continue
        idx = {k: next((i for i, h in enumerate(head) if h.startswith(k)), None)
               for k in ("release date", "title", "platform", "genre", "developer", "publisher")}
        for row in table_grid(table)[1:]:
            def cell(k):
                i = idx.get(k)
                return row[i] if i is not None and i < len(row) else None
            dc, tc, pc = cell("release date"), cell("title"), cell("platform")
            if dc is None or tc is None or pc is None:
                continue
            m = re.match(r"([A-Za-z]+)\s+(\d{1,2})\b", clean_text(dc.get_text(" ")))
            if not m or m.group(1).lower() not in MONTHS_EN:
                continue  # month-only / TBA dates are skipped (calendar needs an exact day)
            try:
                dt = date(year, MONTHS_EN[m.group(1).lower()], int(m.group(2)))
            except ValueError:
                continue
            for sup in tc.find_all("sup"):
                sup.decompose()
            raw_title = re.sub(r"\s+([:!?,.])", r"\1", clean_text(tc.get_text("")))
            regions = set(re.findall(r"\(([A-Z]{2,4})\)", raw_title))
            if regions and regions <= REGION_SKIP:
                continue
            title = clean_text(re.sub(r"\s*\([A-Z]{2,4}\)", "", raw_title)).strip(" –-")
            link = None
            for a in tc.find_all("a", href=True):
                href = a["href"]
                if href.startswith("/wiki/") and "#" not in href and "new" not in (a.get("class") or []) and ":" not in href[6:]:
                    cand = urllib.parse.unquote(href[6:]).replace("_", " ")
                    if same_game(title, cand):
                        link = cand
                    break
            plats = []
            for tok in re.split(r"[,\s]+", clean_text(pc.get_text(" ")).upper()):
                g = PLATFORM_MAP.get(tok.strip())
                if g and g not in plats:
                    plats.append(g)
            if not title or not plats:
                continue
            gen = cell("genre")
            dev = cell("developer")
            pub = cell("publisher")
            out.append({
                "title": title, "date": dt, "wiki": link, "platforms": plats,
                "genres": [clean_text(x) for x in re.split(r",", clean_text(gen.get_text(" ")) if gen else "") if clean_text(x) and "n/a" not in x.lower()][:3],
                "developer": clean_text(dev.get_text(" ")) if dev else "",
                "publisher": clean_text(pub.get_text(" ")) if pub else "",
            })
    log(f"[wiki] {year}: {len(out)} dated rows")
    return out


def wiki_enrich(titles: list[str]) -> dict:
    """title → {image, extract, ru_title, ru_extract} via the keyless MediaWiki API."""
    info: dict = {}
    for i in range(0, len(titles), 20):
        chunk = titles[i:i + 20]
        try:
            d = wiki_get({"action": "query", "prop": "pageimages|extracts|langlinks", "titles": "|".join(chunk),
                          "redirects": "1", "piprop": "thumbnail", "pithumbsize": "640", "pilicense": "any",
                          "exintro": "1", "explaintext": "1", "exsentences": "3", "exlimit": "20",
                          "lllang": "ru", "lllimit": "50"})
        except Exception as e:  # noqa: BLE001
            log(f"[wiki-enrich-fail] {e}")
            continue
        q = d.get("query") or {}
        alias = {}
        for key in ("normalized", "redirects"):
            for n in q.get(key) or []:
                alias[n["to"]] = alias.get(n["from"], n["from"])
        for pg in q.get("pages") or []:
            t = pg.get("title")
            src = t
            while src in alias:
                src = alias[src]
            ll = pg.get("langlinks") or []
            info[src] = info[t] = {
                "image": safe_url((pg.get("thumbnail") or {}).get("source")),
                "extract": clean_text(pg.get("extract")),
                "ru_title": ll[0].get("title") if ll else "",
                "page": t,
            }
        time.sleep(0.5)
    # Russian intro for games that have a Russian article
    ru_titles = sorted({v["ru_title"] for v in info.values() if v.get("ru_title")})
    ru_ext: dict = {}
    for i in range(0, len(ru_titles), 20):
        try:
            d = wiki_get({"action": "query", "prop": "extracts", "titles": "|".join(ru_titles[i:i + 20]),
                          "redirects": "1", "exintro": "1", "explaintext": "1", "exsentences": "3", "exlimit": "20"}, lang="ru")
        except Exception as e:  # noqa: BLE001
            log(f"[wiki-ru-fail] {e}")
            continue
        for pg in (d.get("query") or {}).get("pages") or []:
            ru_ext[pg.get("title")] = clean_text(pg.get("extract"))
        time.sleep(0.5)
    for v in info.values():
        v["ru_extract"] = ru_ext.get(v.get("ru_title") or "", "")
    return info


# ====================================================================== Epic Games Store
EPIC_Q = """query($start:Int,$count:Int){Catalog{searchStore(category:"games/edition/base",comingSoon:true,start:$start,
count:$count,country:"RU",locale:"ru",sortBy:"releaseDate",sortDir:"ASC"){elements{title releaseDate description
seller{name} keyImages{type url} catalogNs{mappings(pageType:"productHome"){pageSlug}} offerMappings{pageSlug}
productSlug urlSlug}}}}"""


def epic_coming_soon(today: date, horizon: date) -> dict:
    """normalized title → Epic item (upcoming games in the Epic Games Store)."""
    out: dict = {}
    for start in range(0, 1600, 40):  # the store answers at most 40 items per page
        body = json.dumps({"query": EPIC_Q, "variables": {"start": start, "count": 40}}).encode()
        req = urllib.request.Request("https://store.epicgames.com/graphql", data=body, headers={
            "Content-Type": "application/json", "User-Agent": BROWSER_UA_EPIC, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                d = json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            log(f"[epic-fail] start={start}: {e}")
            break
        els = ((((d or {}).get("data") or {}).get("Catalog") or {}).get("searchStore") or {}).get("elements") or []
        if not els:
            break
        last = None
        for e in els:
            try:
                rd = datetime.fromisoformat(str(e.get("releaseDate")).replace("Z", "+00:00")).astimezone(MSK).date()
            except ValueError:
                continue
            last = rd
            if not (today - timedelta(days=45) <= rd <= horizon):
                continue
            slug = next((m.get("pageSlug") for m in ((e.get("catalogNs") or {}).get("mappings") or []) + (e.get("offerMappings") or []) if m.get("pageSlug")), None) \
                or e.get("productSlug") or e.get("urlSlug")
            if not slug or ADULT_RE.search(e.get("title") or ""):
                continue
            imgs = {k.get("type"): k.get("url") for k in e.get("keyImages") or []}
            out.setdefault(norm_title(e.get("title")), {
                "title": clean_text(e.get("title")).replace("™", "").replace("®", "").strip(),
                "date": rd,
                "url": f"https://store.epicgames.com/ru/p/{slug.split('/')[0]}",
                "image": safe_url(imgs.get("OfferImageWide") or imgs.get("DieselStoreFrontWide") or imgs.get("Thumbnail")),
                "desc": clip(clean_text(e.get("description")), 300),
                "developer": clean_text((e.get("seller") or {}).get("name")),
            })
        if last and last > horizon:
            break
        time.sleep(0.7)
    log(f"[epic] {len(out)} upcoming/recent games")
    return out


BROWSER_UA_EPIC = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


SEQUEL_RE = re.compile(r"^(\d+|[ivx]+)\b", re.I)


def same_game(title: str, article: str) -> bool:
    """The article must be about this game, not the previous part of the series
    («Toem 2» → «Toem» is rejected, «Gothic II Complete Classic» → «Gothic II» is fine)."""
    a = norm_title(re.sub(r"\s*\((?:\d{4} )?video game\)$", "", article, flags=re.I))
    t = norm_title(title)
    if a == t:
        return True
    if t.startswith(a + " "):
        rest = t[len(a):].strip()
        if SEQUEL_RE.match(rest):
            return False
        # only edition words may follow («… Complete Edition», «… Remastered», «… Nintendo Switch 2 Edition»)
        if rest.startswith("nintendo switch 2"):
            return True
        return all(w in EDITION_WORDS for w in rest.split())
    return False


EDITION_WORDS = set("""complete classic remastered remaster remake collection edition deluxe gold definitive goty game
of the year hd director s directors cut encore galactic ultimate enhanced special anniversary retro complete
legendary royal premium bundle trilogy""".split())


def norm_title(s: str | None) -> str:
    s = (s or "").lower().replace("ё", "е")
    s = re.sub(r"[™®©:’'`\-–—!?.,&]+", " ", s)
    s = re.sub(r"\b(the|edition|standard|deluxe|remastered)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def slug_id(title: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", norm_title(title)).strip("-")
    return ("x-" + s)[:60].rstrip("-") or "x-game"


def steam_lookup(title: str) -> dict | None:
    """Exact-title match in the Steam store search (keyless) → appid + header image."""
    try:
        d = fetch_json("https://store.steampowered.com/api/storesearch/?term=" + urllib.parse.quote(title) + "&cc=ru&l=russian", timeout=25)
    except Exception:  # noqa: BLE001
        return None
    for it in (d or {}).get("items") or []:
        if norm_title(it.get("name")) == norm_title(title):
            appid = it.get("id")
            return {"appid": appid, "url": f"https://store.steampowered.com/app/{appid}/",
                    "image": f"https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/header.jpg"}
    return None


def order_plats(pl: list[str]) -> list[str]:
    return sorted(set(pl), key=lambda x: PLAT_ORDER.index(x) if x in PLAT_ORDER else 99)


def build_other(wiki: list[dict], epic: dict, lo: date, hi: date, limit: int, consoles_only: bool,
                steam_titles: dict, tr) -> list[dict]:
    """Wikipedia (notable, has article) + Epic → calendar items. Steam items get extra platforms/stores."""
    picked: list[dict] = []
    seen = set()
    for r in sorted(wiki, key=lambda x: (x["date"], x["title"])):
        if not (lo <= r["date"] <= hi) or not r["wiki"]:
            continue
        if ADULT_RE.search(r["title"]):
            continue
        key = norm_title(r["title"])
        if key in seen:
            continue
        seen.add(key)
        st = steam_titles.get(key)
        ep = epic.get(key)
        if st is not None:  # the Steam item already exists → enrich it with console platforms / Epic
            st["platforms"] = order_plats(st.get("platforms", []) + r["platforms"])
            if ep and "Epic" not in st["stores"]:
                st["stores"].append("Epic"); st.setdefault("links", {})["epic"] = ep["url"]
            continue
        if not (set(r["platforms"]) & CONSOLES) and (consoles_only or not ep):
            continue  # PC-only games come from Steam; here: consoles, or PC games sold in Epic
        picked.append({"r": r, "ep": ep})
    picked = picked[:int(limit * 1.5) + 2]
    info = wiki_enrich(sorted({p["r"]["wiki"] for p in picked})) if picked else {}
    items = []
    for p in picked:
        if len(items) >= limit:
            break
        r, ep = p["r"], p["ep"]
        wi = info.get(r["wiki"]) or {}
        if wi and not same_game(r["title"], wi.get("page") or ""):
            continue  # the link redirects to a series / person / older game — not this game
        desc = wi.get("ru_extract") or ""
        if not desc and ep and re.search(r"[А-Яа-яЁё]", ep.get("desc") or ""):
            desc = ep["desc"]
        if not desc:
            desc = wi.get("extract") or ""
        stores, links = [], {}
        image = ""
        steam = None
        if "PC" in r["platforms"]:
            steam = steam_lookup(r["title"])
            time.sleep(0.8)
        price = ""
        if steam:
            sd = steam_details_ru(steam["appid"])
            time.sleep(1.0)
            if sd.get("adult"):
                continue
            stores.append("Steam"); links["steam"] = steam["url"]; image = sd.get("image") or ""
            price = sd.get("price") or ""
            if not re.search(r"(руб|₽|Бесплатно)", price):
                price = ""  # not sold in the RU region → no foreign currency on the site
            if re.search(r"[А-Яа-яЁё]", sd.get("desc") or "") and not wi.get("ru_extract"):
                desc = sd["desc"]
        if ep:
            stores.append("Epic"); links["epic"] = ep["url"]
            if "PC" not in r["platforms"]:
                r["platforms"].insert(0, "PC")
            image = image or ep["image"]
        wiki_url = ""
        if wi.get("ru_title"):
            wiki_url = "https://ru.wikipedia.org/wiki/" + urllib.parse.quote(wi["ru_title"].replace(" ", "_"))
        elif r["wiki"]:
            wiki_url = "https://en.wikipedia.org/wiki/" + urllib.parse.quote((wi.get("page") or r["wiki"]).replace(" ", "_"))
        if wiki_url:
            links["wiki"] = wiki_url
        image = image or wi.get("image") or ""
        desc = tidy_extract(desc)
        item = {
            "appid": steam["appid"] if steam else slug_id(r["title"]),
            "title": r["title"],
            "date": r["date"].isoformat(),
            "image": image,
            "desc": clip(desc, 300),
            "genres": r["genres"],
            "platforms": order_plats(r["platforms"]),
            "stores": stores,
            "developer": r["developer"] or r["publisher"],
            "price": price,
            "url": links.get("steam") or links.get("epic") or links.get("wiki") or "",
            "links": links,
            "source": "wiki",
        }
        if item["url"]:
            items.append(item)
    # machine-translate English descriptions / genres (cached; originals kept on failure)
    if tr is not None and items:
        try:
            mapped = []
            for it in items:
                it["genres"] = [genre_ru(g) or g for g in it["genres"]]
                mapped.append([g in GENRE_RU.values() for g in it["genres"]])
            src = [it["desc"] for it in items] + [g for it in items for g in it["genres"]]
            ru = tr.many(src)
            # dictionary genres (RPG, Survival horror…) are final — never re-translated
            gi = len(items)
            for it, mk in zip(items, mapped):
                for j, is_mapped in enumerate(mk):
                    if is_mapped:
                        ru[gi + j] = it["genres"][j]
                gi += len(mk)
            n = len(items)
            for k, it in enumerate(items):
                it["desc"] = ru[k]
            gi = n
            for it in items:
                it["genres"] = [ru[gi + j] for j in range(len(it["genres"]))]
                gi += len(it["genres"])
        except Exception as e:  # noqa: BLE001
            log(f"[translate-fail] releases: {e}")
    return items


GENRE_RU = {
    "adventure": "Приключение", "action rpg": "Экшен-RPG", "action-adventure": "Экшен-приключение", "rpg": "RPG",
    "action": "Экшен", "puzzle": "Головоломка", "platformer": "Платформер", "roguelike": "Рогалик", "roguelite": "Рогалик",
    "fps": "Шутер от первого лица", "tps": "Шутер от третьего лица", "survival horror": "Survival-хоррор",
    "visual novel": "Визуальная новелла", "simulation": "Симулятор", "horror": "Хоррор", "survival": "Выживание",
    "metroidvania": "Метроидвания", "racing": "Гонки", "tactical rpg": "Тактическая RPG", "party": "Для компании",
    "sports": "Спорт", "strategy": "Стратегия", "hack and slash": "Слэшер", "life sim": "Симулятор жизни",
    "shoot 'em up": "Shoot 'em up", "fighting": "Файтинг", "deck building": "Карточная игра", "brawler": "Beat 'em up",
    "puzzle-platformer": "Головоломка-платформер", "cms": "Строительство и менеджмент", "rhythm": "Ритм-игра",
    "pca": "Point-and-click квест", "tbs": "Пошаговая стратегия", "sandbox": "Песочница", "business sim": "Бизнес-симулятор",
    "stealth": "Стелс", "monster tamer": "Коллекционирование монстров", "dungeon crawl": "Данжен-кроулер",
    "city builder": "Градостроитель", "farming": "Фермерство", "otome": "Отомэ", "narrative adventure": "Сюжетное приключение",
    "digital tabletop": "Настольная игра", "deck building (roguelike)": "Карточный рогалик", "vehicular combat": "Боевые машины",
    "interactive film": "Интерактивное кино", "bullet hell": "Bullet hell", "raising sim": "Симулятор воспитания",
    "tower defense": "Tower defense", "rts": "Стратегия в реальном времени", "soulslike": "Соулслайк", "mmorpg": "MMORPG",
    "extraction shooter": "Extraction-шутер", "cozy": "Уютная игра", "horror (psych)": "Психологический хоррор",
    "bullet heaven": "Bullet heaven", "social sim": "Социальный симулятор", "hero shooter": "Геройский шутер",
    "tbt": "Пошаговая тактика", "rtt": "Тактика в реальном времени", "vehicle sim": "Симулятор техники", "mmo": "MMO",
    "dccg": "Коллекционная карточная игра", "factory sim": "Симулятор завода", "moba": "MOBA", "casual": "Казуальная игра",
    "hidden object": "Поиск предметов", "run and gun": "Run and gun", "card": "Карточная игра", "deckbuilder": "Карточная игра",
    "sports management": "Спортивный менеджер", "pinball": "Пинбол", "dating sim": "Симулятор свиданий", "god game": "Симулятор бога",
    "social deduction": "Социальная дедукция", "photography": "Фотография", "compilation": "Сборник",
}


def genre_ru(g: str) -> str | None:
    k = g.strip().lower()
    if k in GENRE_RU:
        return GENRE_RU[k]
    base = re.sub(r"\s*\(.*?\)", "", k).strip()
    return GENRE_RU.get(base)


def steam_details_ru(appid) -> dict:
    """Russian description + proper header image from the Steam store (keyless appdetails)."""
    try:
        d = details(int(appid)) or {}
    except Exception:  # noqa: BLE001
        return {}
    return {"desc": clean_text(d.get("short_description")), "image": safe_url(d.get("header_image")),
            "price": price_text(d), "adult": is_adult(d, d.get("name") or "")}


def tidy_extract(s: str) -> str:
    """Drop foreign-script parentheses like «(яп. パタポン)» or «(англ. …)» from encyclopedia intros."""
    s = re.sub(r"\s*\((?:[^()]*[\u3040-\u30ff\u3400-\u9fff\uac00-\ud7af][^()]*|[^()]*(?:яп|англ|кит|кор)\.[^()]*|[^()]*в Японии[^()]*)\)", "", s or "")
    return re.sub(r"\s{2,}", " ", s).strip()


def translate_descs(items: list[dict], tr) -> None:
    """Steam descriptions without Russian localisation → machine translation (cached)."""
    if tr is None:
        return
    todo = [it for it in items if tr.needs(it.get("desc") or "")]
    if not todo:
        return
    try:
        ru = tr.many([it["desc"] for it in todo])
        for it, x in zip(todo, ru):
            it["desc"] = x
    except Exception as e:  # noqa: BLE001
        log(f"[translate-fail] descs: {e}")


def add_epic_to_steam(items: list[dict], epic: dict) -> None:
    for it in items:
        ep = epic.get(norm_title(it["title"]))
        if ep and "Epic" not in it.get("stores", []):
            it.setdefault("stores", ["Steam"]).append("Epic")
            it.setdefault("links", {})["epic"] = ep["url"]


def main() -> int:
    today = datetime.now(MSK).date()
    horizon = today + timedelta(days=150)
    tr = None
    if Translator is not None:
        try:
            tr = Translator()
        except Exception as e:  # noqa: BLE001
            log(f"[translate-fail] init: {e}")
    wiki = wiki_year_rows(today.year)
    if horizon.year != today.year or today.month <= 1:
        wiki += wiki_year_rows(horizon.year if horizon.year != today.year else today.year - 1)
    epic = epic_coming_soon(today, horizon)

    rel = build_releases(today)
    add_epic_to_steam(rel, epic)
    steam_idx = {norm_title(x["title"]): x for x in rel}
    rel += build_other(wiki, epic, today, horizon, 40, False, steam_idx, tr)
    rel.sort(key=lambda x: (x["date"], x["title"]))
    translate_descs(rel, tr)
    write_json_if_good(DATA / "releases.json", {"updatedAt": now_msk_iso(), "items": rel}, "items", 5)

    new = build_new_games(today)
    add_epic_to_steam(new, epic)
    steam_idx = {norm_title(x["title"]): x for x in new}
    other = build_other(wiki, epic, today - timedelta(days=45), today, 8, True, steam_idx, tr)
    other.sort(key=lambda x: x["date"], reverse=True)
    new += other
    translate_descs(new, tr)
    write_json_if_good(DATA / "new_games.json", {"updatedAt": now_msk_iso(), "items": new}, "items", 4)
    if tr is not None:
        try:
            tr.save()
        except Exception as e:  # noqa: BLE001
            log(f"[translate-fail] save: {e}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
