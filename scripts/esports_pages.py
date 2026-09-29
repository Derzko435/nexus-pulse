"""Static esports schedule pages (used by build_static_pages.py): esports/ + esports/<game>/.

Built only from data/matches.json (scripts/update_matches.py, source bo3.gg: top-tier S/A matches).
Times are shown in MSK. SportsEvent JSON-LD is emitted only for matches that really have two named
teams and a start time and are live or still ahead at build time — finished matches are shown as
results without event markup. Nothing is invented: an empty feed gives an honest "no matches" block.
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timedelta, timezone

MSK = timezone(timedelta(hours=3), name="MSK")
GAMES = [  # slug, gameKey in matches.json, display name, long name
    ("cs2", "cs2", "CS2", "Counter-Strike 2"),
    ("dota2", "dota2", "Dota 2", "Dota 2"),
    ("valorant", "valorant", "Valorant", "Valorant"),
]
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]
CHAN_RE = re.compile(r"^[A-Za-z0-9_]{2,40}$")
UPCOMING_MAX, RESULTS_MAX = 30, 20


def _e(s) -> str:
    return html.escape(str(s if s is not None else ""), quote=True)


def _dt(v):
    try:
        d = datetime.fromisoformat(str(v))
    except (TypeError, ValueError):
        return None
    return (d if d.tzinfo else d.replace(tzinfo=MSK)).astimezone(MSK)


def _when(d) -> str:
    return f"{d.day} {MONTHS[d.month - 1]}, {d:%H:%M} МСК" if d else "—"


def _day(v) -> str:
    try:
        d = datetime.strptime(str(v)[:10], "%Y-%m-%d")
    except ValueError:
        return ""
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def _https(u) -> str:
    u = str(u or "")
    return u if u.startswith("https://") else ""


def stream_links(m) -> list:
    out, seen = [], set()
    for s in m.get("streams") or []:
        ch = str(s.get("channel") or "")
        if not CHAN_RE.match(ch):
            continue
        url = {"twitch": f"https://www.twitch.tv/{ch}", "kick": f"https://kick.com/{ch}"}.get(s.get("type"))
        if url and url not in seen:
            seen.add(url)
            out.append((url, f"{s.get('type').capitalize()}: {ch}" + (f" ({s['lang']})" if s.get("lang") else "")))
    return out


def _teams_ok(m) -> bool:
    a, b = str(m.get("teamA") or "").strip(), str(m.get("teamB") or "").strip()
    return bool(a and b and "tbd" not in (a + b).lower())


def split(matches: list, key: str, now: datetime):
    ms = [m for m in matches if m.get("gameKey") == key and _teams_ok(m) and _dt(m.get("startsAt"))]
    # «live» older than 6 h = stale data (a BO5 rarely runs longer) — not shown as live
    live = sorted([m for m in ms if m.get("status") == "live" and _dt(m["startsAt"]) >= now - timedelta(hours=6)], key=lambda m: _dt(m["startsAt"]))
    # «upcoming» whose start is > 2 h in the past means the data is older than the match — don't show it as ahead
    up = sorted([m for m in ms if m.get("status") == "upcoming" and _dt(m["startsAt"]) >= now - timedelta(hours=2)],
                key=lambda m: _dt(m["startsAt"]))[:UPCOMING_MAX]
    done = sorted([m for m in ms if m.get("status") == "finished"], key=lambda m: _dt(m["startsAt"]), reverse=True)[:RESULTS_MAX]
    return live, up, done


def sports_event(m, game_name: str, now: datetime) -> dict | None:
    st = _dt(m.get("startsAt"))
    if not st or not _teams_ok(m):
        return None
    if m.get("status") == "upcoming" and st < now:
        return None
    if m.get("status") not in ("upcoming", "live"):
        return None
    if m.get("status") == "live" and st < now - timedelta(hours=6):
        return None
    links = stream_links(m)
    where = links[0][0] if links else _https(m.get("url"))
    ev = {"@type": "SportsEvent", "name": f"{m['teamA']} vs {m['teamB']}" + (f" — {m['event']}" if m.get("event") else ""),
          "sport": game_name, "startDate": st.isoformat(), "eventStatus": "https://schema.org/EventScheduled",
          "eventAttendanceMode": "https://schema.org/OnlineEventAttendanceMode",
          "competitor": [{"@type": "SportsTeam", "name": m["teamA"]}, {"@type": "SportsTeam", "name": m["teamB"]}]}
    if where:
        ev["location"] = {"@type": "VirtualLocation", "url": where}
    if _https(m.get("url")):
        ev["url"] = _https(m["url"])
    if m.get("event"):
        ev["superEvent"] = {"@type": "SportsEvent", "name": m["event"]}
    return ev


def _match_rows(ms, kind: str) -> str:
    rows = []
    for m in ms:
        st = _dt(m.get("startsAt"))
        teams = f"<strong>{_e(m['teamA'])}</strong> — <strong>{_e(m['teamB'])}</strong>"
        if kind != "upcoming" and m.get("scoreA") is not None and m.get("scoreB") is not None:
            teams = f"<strong>{_e(m['teamA'])}</strong> {_e(m['scoreA'])} : {_e(m['scoreB'])} <strong>{_e(m['teamB'])}</strong>"
        meta = " · ".join(x for x in [f"BO{m['bo']}" if m.get("bo") else "", f"Tier {m['tier']}" if m.get("tier") else ""] if x)
        streams = " ".join(f'<a href="{_e(u)}" target="_blank" rel="noopener nofollow">{_e(t)}</a>' for u, t in stream_links(m)[:3])
        src = f' <a class="sp-note" href="{_e(_https(m.get("url")))}" target="_blank" rel="noopener nofollow">bo3.gg ↗</a>' if _https(m.get("url")) else ""
        rows.append(f'<tr><td><time datetime="{_e(st.isoformat() if st else "")}">{_e(_when(st))}</time></td>'
                    f'<td>{teams}<br><span class="sp-note">{_e(m.get("event") or "")}{" · " + _e(meta) if meta else ""}</span></td>'
                    f'<td>{streams or "—"}{src}</td></tr>')
    return "".join(rows)


def _table(ms, kind: str, head_last: str) -> str:
    return (f'<div class="sp-table-wrap"><table class="sp-table"><thead><tr><th>Время (МСК)</th><th>Матч</th><th>{_e(head_last)}</th></tr></thead>'
            f'<tbody>{_match_rows(ms, kind)}</tbody></table></div>')


def _tournaments(tours: list, key: str) -> str:
    ts = [t for t in tours if t.get("gameKey") == key and t.get("name") and t.get("status") in ("current", "upcoming")]
    ts.sort(key=lambda t: (t.get("status") != "current", str(t.get("start") or "")))
    if not ts:
        return ""
    rows = "".join(
        f'<tr><td>{_e(t["name"])}{" <span class=\"sp-note\">· Tier " + _e(t["tier"]) + "</span>" if t.get("tier") else ""}</td>'
        f'<td>{_e(_day(t.get("start")))} — {_e(_day(t.get("end")))}</td><td>{"идёт" if t["status"] == "current" else "скоро"}</td>'
        f'<td>{f"<a href=\"{_e(_https(t.get("url")))}\" target=\"_blank\" rel=\"noopener nofollow\">bo3.gg ↗</a>" if _https(t.get("url")) else ""}</td></tr>'
        for t in ts)
    return ('<section class="guide-sec"><h2>Турниры</h2><div class="sp-table-wrap"><table class="sp-table"><thead><tr><th>Турнир</th><th>Даты</th><th>Статус</th><th>Источник</th></tr></thead>'
            f"<tbody>{rows}</tbody></table></div></section>")


def build_pages(data: dict, site: str, publisher: dict, now: datetime | None = None) -> list:
    """Page tuples for build_static_pages: (path, title, desc, body, crumbs, og_type, image, jsonld)."""
    now = (now or datetime.now(MSK)).astimezone(MSK)
    matches = [m for m in (data.get("matches") or []) if isinstance(m, dict)]
    tours = [t for t in (data.get("tournaments") or []) if isinstance(t, dict)]
    upd = _dt(data.get("updatedAt"))
    upd_txt = f"Данные: bo3.gg, обновлено {_when(upd)}." if upd else "Данные: bo3.gg."
    pages, hub_blocks, hub_events = [], [], []
    for slug, key, name, long_name in GAMES:
        live, up, done = split(matches, key, now)
        path = f"esports/{slug}/"
        events = [x for x in (sports_event(m, long_name, now) for m in live + up) if x]
        hub_events += events[:5]
        title = f"Расписание матчей {name} — турниры и трансляции по МСК | NEXUS PULSE"
        nxt = up[0] if up else None
        desc = (f"Ближайшие матчи {name} по московскому времени: "
                + (f"{nxt['teamA']} — {nxt['teamB']} ({_when(_dt(nxt['startsAt']))}). " if nxt else "")
                + "Результаты, турниры топ-уровня и официальные трансляции.")
        body = f"""<article class="sp-article glass">
<p class="eyebrow">Киберспорт · {_e(long_name)}</p>
<h1 class="sp-h1">Расписание матчей {_e(name)}</h1>
<div class="npv-body">
<p class="guide-lead">Матчи {_e(long_name)} турниров уровня S и A по московскому времени, результаты и ссылки на официальные трансляции. {_e(upd_txt)}</p>
{('<section class="guide-sec"><h2>Идут сейчас</h2><p class="sp-note">Статус на момент обновления данных.</p>' + _table(live, "live", "Трансляции") + "</section>") if live else ""}
<section class="guide-sec"><h2>Ближайшие матчи</h2>{_table(up, "upcoming", "Трансляции") if up else "<p>Сейчас в расписании нет ближайших матчей топ-уровня — загляни позже.</p>"}</section>
{('<section class="guide-sec"><h2>Результаты</h2>' + _table(done, "finished", "Ссылки") + "</section>") if done else ""}
{_tournaments(tours, key)}
<p class="sp-note">Время начала может сдвигаться организатором; точное время и состав — на странице матча в источнике.</p>
</div>
<div class="npv-actions sp-actions">
<a class="btn btn-primary btn-sm" href="../../#esports">Матчи и трансляции в портале</a>
<a class="btn btn-ghost btn-sm" href="../">Все дисциплины</a>
</div>
</article>
<aside class="sp-aside glass">
<h2 class="sp-h2">Другие дисциплины</h2>
<ul class="sp-links">{"".join(f'<li><a href="../{s}/">Расписание {_e(n)}</a></li>' for s, _, n, _ in GAMES if s != slug)}</ul>
</aside>"""
        jl = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": f"Расписание матчей {name}", "url": site + path,
               "inLanguage": "ru", "publisher": publisher}]
        if events:
            jl.append({"@context": "https://schema.org", "@type": "ItemList", "name": f"Ближайшие матчи {name}",
                       "itemListElement": [{"@type": "ListItem", "position": i + 1, "item": ev} for i, ev in enumerate(events)]})
        pages.append((path, title, desc, body, [("Главная", ""), ("Киберспорт", "esports/"), (name, path)], "website", "", jl))
        hub_blocks.append(f'<section class="guide-sec"><h2><a href="{slug}/">{_e(long_name)}</a></h2>'
                          + (_table(up[:5], "upcoming", "Трансляции") if up else "<p>Ближайших матчей топ-уровня в расписании нет.</p>")
                          + f'<p><a href="{slug}/">Всё расписание {_e(name)} →</a></p></section>')
    path = "esports/"
    desc = "Расписание матчей CS2, Dota 2 и Valorant по московскому времени: ближайшие игры топ-турниров, результаты и официальные трансляции."
    body = f"""<article class="sp-article glass">
<p class="eyebrow">Киберспорт</p>
<h1 class="sp-h1">Расписание киберспортивных матчей</h1>
<div class="npv-body">
<p class="guide-lead">{_e(desc)} {_e(upd_txt)}</p>
{"".join(hub_blocks)}
</div>
</article>
<aside class="sp-aside glass">
<h2 class="sp-h2">Дисциплины</h2>
<ul class="sp-links">{"".join(f'<li><a href="{s}/">Расписание {_e(n)}</a></li>' for s, _, n, _ in GAMES)}</ul>
</aside>"""
    jl = [{"@context": "https://schema.org", "@type": "CollectionPage", "name": "Расписание киберспортивных матчей", "url": site + path,
           "inLanguage": "ru", "publisher": publisher,
           "hasPart": [{"@type": "WebPage", "url": site + f"esports/{s}/", "name": f"Расписание матчей {n}"} for s, _, n, _ in GAMES]}]
    pages.insert(0, (path, "Расписание матчей CS2, Dota 2 и Valorant — киберспорт | NEXUS PULSE", desc, body,
                     [("Главная", ""), ("Киберспорт", path)], "website", "", jl))
    return pages
