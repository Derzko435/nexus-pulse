#!/usr/bin/env python3
"""NEXUS PULSE → Discord auto-feed.

Reads the site's real data files (data/*.json) and posts NEW items into the
read-only feed channels of the Discord server. Nothing is invented.

Delivery modes
  webhook : env DISCORD_WEBHOOKS_JSON = {"news": "<url>", "deals": "<url>", ...}
            (GitHub Actions secret; no bot token needed)
  bot     : bot token (box only) + channel ids from data/discord_channels.json
  auto    : webhook if DISCORD_WEBHOOKS_JSON is set, else bot

Dedupe state: data/discord_posted.json (ids only, committed to the repo).
First run for a feed (no state) = seed: everything is marked as seen and only the
freshest few items (default 3) are posted. Later runs post at most 5 new items per
feed (news/videos: 3); older overflow is marked seen instead of queuing up.

  python scripts/discord_feeds.py --mode auto [--only news,deals] [--dry-run]
  python scripts/discord_feeds.py --require-mode webhook   # skip unless feedMode == webhook

Never prints tokens or webhook URLs.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from discord_api import Bot, DiscordError, webhook_execute  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STATE_FILE = DATA / "discord_posted.json"
CHANNELS_FILE = DATA / "discord_channels.json"
MSK = timezone(timedelta(hours=3), name="MSK")
SITE = "https://derzko435.github.io/nexus-pulse/"
LOGO = SITE + "assets/nexus-pulse-icon.png"
BRAND_NAME = "NEXUS PULSE"
MAX_PER_RUN = 5
PER_FEED_MAX = {"news": 3, "videos": 3}  # busy feeds: fewer posts per run
SEED_COUNT = 3
KEEP_IDS = 500
MATCH_PINGS_PER_DAY = 3
FEEDS = ["news", "deals", "freebies", "esports", "patches", "videos", "releases", "gotd"]
COLORS = {
    "news": 0x00F5FF, "deals": 0x00D1FF, "freebies": 0x3DFF9A, "esports": 0xFFB020,
    "patches": 0x8B5CFF, "videos": 0xFF3D5A, "releases": 0xFF8A3D, "gotd": 0xFF5EA8,
}
GAME_NAMES = {"cs2": "CS2", "dota2": "Dota 2", "valorant": "Valorant", "lol": "LoL"}
CURATED_FREEBIE = re.compile(r"(-always$|^gog-giveaway|^prime-)")
MONTHS = ["янв", "фев", "мар", "апр", "мая", "июн", "июл", "авг", "сен", "окт", "ноя", "дек"]


# ------------------------------------------------------------------ helpers
def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def now_msk() -> datetime:
    return datetime.now(MSK)


def parse_dt(s: str | None) -> datetime | None:
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


def utc_iso(d: datetime | None) -> str | None:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z") if d else None


def clip(s: str | None, n: int) -> str:
    s = re.sub(r"\s+", " ", str(s or "")).strip()
    if len(s) <= n:
        return s
    cut = s[:n]
    sp = cut.rfind(" ")
    if sp > n * 0.6:
        cut = cut[:sp]
    return cut.rstrip(" ,.;:—-") + "…"


def md(s: str | None) -> str:
    """escape Discord markdown in external text"""
    s = "" if s is None else str(s)
    return re.sub(r"([\\*_~`|>\[\]()])", r"\\\1", s).replace("@", "@\u200b")


def safe_url(u: str | None) -> str | None:
    u = str(u or "").strip()
    return u if re.match(r"^https://[^\s<>\"']+$", u) else None


def day_ru(d: datetime) -> str:
    return f"{d.day} {MONTHS[d.month - 1]}"


def footer(label: str) -> dict:
    return {"text": f"{BRAND_NAME} · {label}", "icon_url": LOGO}


def site_link(anchor: str, label: str = "Открыть на NEXUS PULSE") -> str:
    return f"[{label} →]({SITE}{anchor})"


# ------------------------------------------------------------------ builders
# each builder returns a list of candidates (oldest → newest):
#   {"key": str, "sort": datetime, "body": {...message...}, "ping": bool}

def build_news() -> list[dict]:
    items = (read_json(DATA / "news.json", {}) or {}).get("items") or []
    cutoff = now_msk() - timedelta(hours=48)
    out = []
    for n in items:
        nid, title = n.get("id"), n.get("title")
        d = parse_dt(n.get("date"))
        if not nid or not title or (d and d < cutoff):
            continue
        link = f"{SITE}#news={nid}"
        src = safe_url(n.get("url"))
        desc = md(clip(n.get("summary"), 320))
        desc += "\n\n" + site_link(f"#news={nid}", "Читать полностью на NEXUS PULSE")
        if src:
            desc += f" · [Источник]({src})"
        emb = {"title": clip(title, 240), "url": link, "description": desc, "color": COLORS["news"],
               "author": {"name": f"📰 {clip(n.get('source'), 60)}"}, "footer": footer("Новости"),
               "timestamp": utc_iso(d)}
        img = safe_url(n.get("image"))
        if img:
            emb["image"] = {"url": img}
        out.append({"key": str(nid), "sort": d or now_msk(), "body": {"embeds": [emb]}})
    return sorted(out, key=lambda x: x["sort"])


def build_deals() -> list[dict]:
    payload = read_json(DATA / "deals.json", {}) or {}
    upd = parse_dt(payload.get("updatedAt")) or now_msk()
    out = []
    for i, d in enumerate(payload.get("deals") or []):
        try:
            pct = int(float(d.get("pct") or 0))
        except ValueError:
            continue
        if pct < 50 or not d.get("title"):
            continue
        url = safe_url(d.get("url"))
        old, neu = d.get("old"), d.get("neu")
        price = f"~~{md(old)} ₽~~ → **{md(neu)} ₽**" if old and neu else ""
        emb = {"title": f"−{pct}% · {clip(d.get('title'), 200)}", "url": url, "color": COLORS["deals"],
               "description": f"{price} · {md(d.get('store') or 'Steam')}\n{site_link('#deals', 'Все скидки на NEXUS PULSE')}",
               "footer": footer("Скидки"), "timestamp": utc_iso(upd)}
        if d.get("steamAppId") and str(d["steamAppId"]).isdigit():
            emb["thumbnail"] = {"url": f"https://cdn.cloudflare.steamstatic.com/steam/apps/{d['steamAppId']}/header.jpg"}
        if not url:
            emb.pop("url")
        # list order = best first → give earlier items a later sort so they are kept by the "newest N" cut
        out.append({"key": f"{d.get('id') or d.get('title')}:{pct}", "sort": upd - timedelta(seconds=i),
                    "embed": emb, "group": True})
    return sorted(out, key=lambda x: x["sort"])


def build_freebies() -> list[dict]:
    payload = read_json(DATA / "freebies.json", {}) or {}
    upd = parse_dt(payload.get("updatedAt")) or now_msk()
    today = now_msk().date()
    out = []
    for i, it in enumerate(payload.get("items") or []):
        fid, title = str(it.get("id") or ""), it.get("title")
        if not fid or not title or CURATED_FREEBIE.search(fid):
            continue  # skip evergreen / generic curated hints — only concrete giveaways
        until = parse_dt(it.get("until"))
        if until and until.date() < today:
            continue
        soon = "скоро" in str(it.get("note") or "").lower()
        state = "soon" if soon else "now"
        url = safe_url(it.get("claimUrl"))
        head = "⏳ Скоро бесплатно" if soon else "🎁 Бесплатно"
        when = f"до {day_ru(until)}" if until else ""
        if soon and until:
            when = f"раздача до {day_ru(until)}"
        desc = f"**{md(it.get('store'))}** · {when}\n"
        desc += ("Добавь в библиотеку, как только стартует — игра останется навсегда.\n" if soon
                 else "Забирай, пока бесплатно — игра останется в библиотеке навсегда.\n")
        desc += site_link("#freebies", "Все раздачи на NEXUS PULSE")
        emb = {"title": f"{head}: {clip(title, 200)}", "url": url, "description": desc,
               "color": COLORS["freebies"], "footer": footer("Раздачи"), "timestamp": utc_iso(upd)}
        if not url:
            emb.pop("url")
        out.append({"key": f"{fid}:{state}", "sort": upd - timedelta(seconds=i), "embed": emb,
                    "group": True, "ping": not soon})
    return sorted(out, key=lambda x: x["sort"])


def build_esports() -> list[dict]:
    payload = read_json(DATA / "matches.json", {}) or {}
    matches = [m for m in payload.get("matches") or [] if m.get("teamA") and m.get("startsAt")]
    upd = parse_dt(payload.get("updatedAt")) or now_msk()
    now = now_msk()
    out = []
    watch = f"{SITE}#esports"

    def label(m):
        return f"**{md(m['teamA'])}** vs **{md(m['teamB'])}**"

    # 1) live top-tier matches — only while the data is fresh (no stale "LIVE" posts)
    fresh = now - upd <= timedelta(minutes=100)
    for m in matches:
        if not fresh or m.get("status") != "live" or m.get("tier") not in ("S", "A"):
            continue
        st = parse_dt(m.get("startsAt"))
        if st and now - st > timedelta(hours=5):
            continue
        game = GAME_NAMES.get(m.get("gameKey"), m.get("game") or "")
        emb = {"title": f"🔴 LIVE · {clip(m['teamA'], 60)} vs {clip(m['teamB'], 60)}", "url": watch,
               "description": f"{md(game)} · {md(m.get('event'))} · BO{md(m.get('bo') or '?')}\n"
                              f"Счёт: **{md(m.get('scoreA', 0))} : {md(m.get('scoreB', 0))}**\n"
                              f"▶ [Смотреть трансляцию на NEXUS PULSE]({watch})",
               "color": 0xFF3D3D, "footer": footer("Киберспорт · лайв"), "timestamp": utc_iso(st)}
        logo = safe_url(m.get("logoA"))
        if logo:
            emb["thumbnail"] = {"url": logo}
        out.append({"key": f"live:{m['id']}", "sort": st or upd, "body": {"embeds": [emb]},
                    "ping": m.get("tier") == "S", "kind": "live"})

    # 2) daily digest of upcoming top matches (next 24h), once per Moscow day
    upcoming = sorted(
        [m for m in matches if m.get("status") == "upcoming" and m.get("tier") in ("S", "A")
         and (parse_dt(m["startsAt"]) or now) >= now - timedelta(minutes=30)
         and (parse_dt(m["startsAt"]) or now) <= now + timedelta(hours=24)],
        key=lambda m: m["startsAt"])[:12]
    if upcoming:
        lines = []
        for m in upcoming:
            st = parse_dt(m["startsAt"]).astimezone(MSK)
            game = GAME_NAMES.get(m.get("gameKey"), m.get("game") or "")
            lines.append(f"`{st:%H:%M}` {label(m)} — {md(game)} · {md(clip(m.get('event'), 40))}{' ⭐' if m.get('tier') == 'S' else ''}")
        emb = {"title": f"🏆 Топ-матчи на {day_ru(now)} (время МСК)", "url": watch,
               "description": "\n".join(lines) + f"\n\n⭐ — турниры S-тира\n▶ [Трансляции и расписание на NEXUS PULSE]({watch})",
               "color": COLORS["esports"], "footer": footer("Киберспорт"), "timestamp": utc_iso(upd)}
        out.append({"key": f"digest:{now:%Y-%m-%d}", "sort": upd, "body": {"embeds": [emb]}, "kind": "digest"})

    # 3) results of S-tier matches (grouped)
    for m in matches:
        if m.get("status") != "finished" or m.get("tier") != "S":
            continue
        st = parse_dt(m.get("startsAt"))
        if st and st < now - timedelta(hours=36):
            continue
        game = GAME_NAMES.get(m.get("gameKey"), m.get("game") or "")
        out.append({"key": f"result:{m['id']}", "sort": st or upd, "group": True, "kind": "result",
                    "line": f"{md(game)} · {label(m)} **{md(m.get('scoreA'))}:{md(m.get('scoreB'))}** · {md(clip(m.get('event'), 40))}"})
    return sorted(out, key=lambda x: x["sort"])


def build_patches() -> list[dict]:
    items = (read_json(DATA / "patches.json", {}) or {}).get("items") or []
    cutoff = now_msk() - timedelta(days=10)
    out = []
    for p in items:
        d = parse_dt(p.get("date"))
        if not p.get("id") or not d or d < cutoff:
            continue
        src = safe_url(p.get("url"))
        desc = md(clip(p.get("summary"), 350)) + "\n\n" + site_link(f"#patch={p['id']}", "Подробности на NEXUS PULSE")
        if src:
            desc += f" · [Источник]({src})"
        emb = {"title": f"🛠 {clip(p.get('game'), 80)}: {clip(p.get('title'), 150)}", "url": f"{SITE}#patch={p['id']}",
               "description": desc, "color": COLORS["patches"], "footer": footer("Патчи"), "timestamp": utc_iso(d)}
        img = safe_url(p.get("image"))
        if img:
            emb["thumbnail"] = {"url": img}
        out.append({"key": f"{p['id']}:{d:%Y-%m-%d}", "sort": d, "body": {"embeds": [emb]}})
    return sorted(out, key=lambda x: x["sort"])


def build_videos() -> list[dict]:
    items = (read_json(DATA / "videos.json", {}) or {}).get("items") or []
    cutoff = now_msk() - timedelta(hours=36)
    out = []
    for v in items:
        vid = str(v.get("id") or "")
        d = parse_dt(v.get("date"))
        if not re.fullmatch(r"[\w-]{6,20}", vid) or v.get("category") not in ("games", "esports") or (d and d < cutoff):
            continue
        content = (f"🎬 **{md(clip(v.get('title'), 180))}** · {md(v.get('channel'))}\n"
                   f"https://www.youtube.com/watch?v={vid}\n"
                   f"Больше видео: <{SITE}#video={vid}>")
        out.append({"key": vid, "sort": d or now_msk(), "body": {"content": content}})
    return sorted(out, key=lambda x: x["sort"])


def build_releases() -> list[dict]:
    items = (read_json(DATA / "releases.json", {}) or {}).get("items") or []
    now = now_msk()
    today = now.date()
    iso = today.isocalendar()
    out = []
    week = []
    for r in items:
        d = parse_dt(r.get("date"))
        if d and today <= d.date() <= today + timedelta(days=7):
            week.append((d, r))
    week.sort(key=lambda x: x[0])
    if week:
        lines = [f"`{d:%d.%m}` **[{md(clip(r.get('title'), 70))}]({safe_url(r.get('url')) or SITE + '#calendar'})**"
                 f" — {md(' · '.join((r.get('genres') or [])[:2]))}" for d, r in week[:15]]
        emb = {"title": f"📅 Релизы недели · {day_ru(now)} — {day_ru(now + timedelta(days=7))}", "url": f"{SITE}#calendar",
               "description": "\n".join(lines) + "\n\n" + site_link("#calendar", "Весь календарь релизов на NEXUS PULSE"),
               "color": COLORS["releases"], "footer": footer("Релизы"), "timestamp": utc_iso(now)}
        img = next((safe_url(r.get("image")) for _d, r in week if safe_url(r.get("image"))), None)
        if img:
            emb["image"] = {"url": img}
        out.append({"key": f"week:{iso[0]}-W{iso[1]:02d}", "sort": now, "body": {"embeds": [emb]}})
    # releases coming out today (daily post)
    todays = [r for d, r in week if d.date() == today]
    for r in todays:
        appid = str(r.get("appid") or r.get("title"))
        emb = {"title": f"🚀 Сегодня выходит: {clip(r.get('title'), 200)}", "url": safe_url(r.get("url")) or f"{SITE}#calendar",
               "description": md(clip(r.get("desc"), 300)) + f"\n{md(' · '.join(r.get('genres') or []))}"
                              + (f" · {md(r.get('price'))}" if r.get("price") else "")
                              + "\n\n" + site_link(f"#release={appid}", "Подробнее на NEXUS PULSE"),
               "color": COLORS["releases"], "footer": footer("Релизы"), "timestamp": utc_iso(now)}
        img = safe_url(r.get("image"))
        if img:
            emb["image"] = {"url": img}
        out.append({"key": f"day:{today}:{appid}", "sort": now + timedelta(seconds=1), "body": {"embeds": [emb]}})
    return out


def build_gotd() -> list[dict]:
    daily = read_json(DATA / "daily.json", {}) or {}
    g = daily.get("gameOfTheDay") or {}
    ds = daily.get("date")
    d = parse_dt(ds)
    if not g.get("title") or not d or d.date() < now_msk().date() - timedelta(days=1):
        return []
    cat = read_json(DATA / "catalog.json", {}) or {}
    img = None
    t = g["title"].lower()
    for game in (cat.get("games") or {}).values():
        name = str(game.get("name") or "").lower()
        if name and (name == t or name.startswith(t) or t.startswith(name)):
            img = safe_url(game.get("img") or game.get("capsule"))
            break
    fields = []
    if g.get("genre"):
        fields.append({"name": "Жанр", "value": md(g["genre"]), "inline": True})
    if g.get("platforms"):
        fields.append({"name": "Платформы", "value": md(", ".join(g["platforms"])), "inline": True})
    desc = md(g.get("reason") or "")
    if g.get("tip"):
        desc += f"\n\n💡 **Совет:** {md(g['tip'])}"
    desc += "\n\n" + site_link("#pulse", "Пульс дня на NEXUS PULSE")
    emb = {"title": f"🎮 Игра дня: {clip(g['title'], 200)}", "url": f"{SITE}#pulse", "description": desc,
           "fields": fields, "color": COLORS["gotd"], "footer": footer("Игра дня"), "timestamp": utc_iso(now_msk())}
    if img:
        emb["image"] = {"url": img}
    return [{"key": f"gotd:{ds}", "sort": d, "body": {"embeds": [emb]}}]


BUILDERS = {
    "news": build_news, "deals": build_deals, "freebies": build_freebies, "esports": build_esports,
    "patches": build_patches, "videos": build_videos, "releases": build_releases, "gotd": build_gotd,
}


# ------------------------------------------------------------------ delivery
class Sender:
    def __init__(self, mode: str, dry: bool):
        self.dry = dry
        self.mode = mode
        self.channels = read_json(CHANNELS_FILE, {}) or {}
        if mode == "webhook":
            raw = os.environ.get("DISCORD_WEBHOOKS_JSON") or ""
            try:
                self.hooks = json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError:
                raise SystemExit("DISCORD_WEBHOOKS_JSON is not valid JSON") from None
            self.bot = None
        else:
            self.hooks = {}
            self.bot = None if dry else Bot()

    def available(self, feed: str) -> bool:
        if self.mode == "webhook":
            return bool(self.hooks.get(feed))
        return bool((self.channels.get("feeds") or {}).get(feed))

    def send(self, feed: str, body: dict) -> None:
        body = dict(body)
        body.setdefault("allowed_mentions", {"parse": []})
        if self.dry:
            print(f"  [dry] {feed}: {json.dumps(body, ensure_ascii=False)[:220]}")
            return
        if self.mode == "webhook":
            body["username"] = BRAND_NAME
            body["avatar_url"] = LOGO
            webhook_execute(self.hooks[feed], body)
        else:
            self.bot.api("POST", f"/channels/{self.channels['feeds'][feed]}/messages", body)


def role_mention(channels: dict, key: str) -> str | None:
    rid = channels.get(key)
    return str(rid) if rid else None


def run(args) -> int:
    channels = read_json(CHANNELS_FILE, {}) or {}
    mode = args.mode
    if mode == "auto":
        mode = "webhook" if (os.environ.get("DISCORD_WEBHOOKS_JSON") or "").strip() else "bot"
    if args.require_mode and channels.get("feedMode", "bot") != args.require_mode:
        print(f"feedMode is '{channels.get('feedMode', 'bot')}', not '{args.require_mode}' — skip")
        return 0
    if mode == "webhook" and not (os.environ.get("DISCORD_WEBHOOKS_JSON") or "").strip():
        print("No DISCORD_WEBHOOKS_JSON — skip")
        return 0

    state = read_json(STATE_FILE, {}) or {}
    posted: dict[str, list[str]] = state.get("posted") or {}
    pings: list[str] = state.get("matchPings") or []
    today = now_msk().strftime("%Y-%m-%d")
    pings = [p for p in pings if p >= (now_msk() - timedelta(days=2)).strftime("%Y-%m-%d")]
    sender = Sender(mode, args.dry_run)
    only = [f.strip() for f in (args.only or "").split(",") if f.strip()] or FEEDS
    total = 0
    errors = 0
    for feed in only:
        if feed not in BUILDERS:
            continue
        if not sender.available(feed):
            print(f"{feed}: no channel/webhook configured — skip")
            continue
        try:
            cands = BUILDERS[feed]()
        except Exception as exc:  # noqa: BLE001
            print(f"{feed}: build failed: {exc}")
            errors += 1
            continue
        seen = set(posted.get(feed) or [])
        seeding = feed not in posted or args.seed
        new = [c for c in cands if c["key"] not in seen]
        limit = SEED_COUNT if seeding else PER_FEED_MAX.get(feed, MAX_PER_RUN)
        chosen = new[-limit:]
        skipped = [c for c in new if c not in chosen]
        print(f"{feed}: {len(cands)} items, {len(new)} new, posting {len(chosen)}{' (seed)' if seeding else ''}")

        # messages: grouped candidates → one message (max 5 embeds / lines), others one each
        messages: list[tuple[list[dict], dict]] = []
        grouped = [c for c in chosen if c.get("group")]
        singles = [c for c in chosen if not c.get("group")]
        if grouped:
            embeds = [c["embed"] for c in grouped if c.get("embed")]
            lines = [c["line"] for c in grouped if c.get("line")]
            body: dict = {}
            if embeds:
                body["embeds"] = list(reversed(embeds))[:10]  # best / newest first
            if lines:
                body.setdefault("embeds", []).append({
                    "title": "✅ Результаты топ-матчей", "url": f"{SITE}#esports",
                    "description": "\n".join(lines) + f"\n\n{site_link('#esports', 'Все матчи на NEXUS PULSE')}",
                    "color": COLORS["esports"], "footer": footer("Киберспорт"),
                    "timestamp": utc_iso(now_msk())})
            messages.append((grouped, body))
        for c in singles:
            messages.append(([c], dict(c["body"])))

        for group, body in messages:
            # role pings: freebies (new current giveaways) and big live matches — never during seed
            if not seeding and any(c.get("ping") for c in group):
                role_key = {"freebies": "role_n_freebies", "esports": "role_n_matches"}.get(feed)
                rid = role_mention(channels, role_key) if role_key else None
                allow = True
                if feed == "esports":
                    allow = sum(1 for p in pings if p.startswith(today)) < MATCH_PINGS_PER_DAY
                if rid and allow:
                    text = "новая бесплатная игра!" if feed == "freebies" else "большой матч в эфире!"
                    body["content"] = f"<@&{rid}> {text}" + (("\n" + body["content"]) if body.get("content") else "")
                    body["allowed_mentions"] = {"parse": [], "roles": [rid]}
                    if feed == "esports":
                        pings.append(now_msk().isoformat(timespec="minutes"))
            try:
                sender.send(feed, body)
                for c in group:
                    seen.add(c["key"])
                    posted.setdefault(feed, []).append(c["key"])
                total += 1
            except (DiscordError, RuntimeError) as exc:
                print(f"{feed}: send failed: {str(exc)[:200]}")
                errors += 1
                break
        # older overflow is dropped (marked seen) so the channel never gets a backlog flood
        for c in skipped:
            posted.setdefault(feed, []).append(c["key"])
        posted.setdefault(feed, [])
        posted[feed] = list(dict.fromkeys(posted[feed]))[-KEEP_IDS:]

    if args.dry_run:
        print(f"dry-run: {total} messages would be sent")
        return 0
    new_state = dict(state)  # keep other keys (e.g. "weekly" from discord_weekly.py)
    new_state.update({
        "about": "Discord auto-feed dedupe state (ids only). Written by scripts/discord_feeds.py.",
        "updatedAt": now_msk().isoformat(timespec="seconds") if total else state.get("updatedAt", now_msk().isoformat(timespec="seconds")),
        "posted": posted,
        "matchPings": pings,
    })
    old_cmp = {k: v for k, v in state.items() if k != "updatedAt"}
    new_cmp = {k: v for k, v in new_state.items() if k != "updatedAt"}
    if old_cmp != new_cmp:
        STATE_FILE.write_text(json.dumps(new_state, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"sent {total} messages, errors {errors}")
    return 1 if errors and not total else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--mode", choices=["auto", "webhook", "bot"], default="auto")
    ap.add_argument("--only", default="", help="comma list of feeds: " + ",".join(FEEDS))
    ap.add_argument("--require-mode", choices=["webhook", "bot"], default=None)
    ap.add_argument("--seed", action="store_true", help="force seed behaviour (post only freshest few)")
    ap.add_argument("--dry-run", action="store_true")
    return run(ap.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
