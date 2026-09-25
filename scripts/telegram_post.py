#!/usr/bin/env python3
"""NEXUS PULSE → Telegram channel autopost (mirrors the Discord feeds).

Posts NEW items from the site's data/*.json: news, discounts −50%+, giveaways, big matches
(daily S-tier schedule + results), game of the day, the Friday poll «Во что играешь на выходных?»
and the Sunday «Итоги недели». Every post: emoji header, short text, hashtag line
(#новости #раздача #скидки #киберспорт #иградня #опрос #итогинедели), buttons «Подробнее» + «🌐 Сайт».

Anti-spam: quiet hours 00:00–08:00 MSK (nothing is sent); ≤ 4 posts per run — the remainder stays
unseen and goes out on the next run, oldest first (news backlog is trimmed to the freshest few).
Dedupe state: data/telegram_posted.json. First run per feed = seed (only the freshest item).

Channel setup (idempotent, runs automatically on every real run): description + a pinned welcome
post with buttons «🌐 Сайт» «💬 Discord» «🎮 Найти тиммейтов». Versions are kept in the state
file → "channel"; bump DESC_VERSION / WELCOME_VERSION to re-apply.

  env TELEGRAM_BOT_TOKEN   bot token from @BotFather (never printed);
                           box fallback: /home/box/.config/telegram-bot-token
  env TELEGRAM_CHANNEL     @channel (or data/site_config.json → telegram.channel)
  python scripts/telegram_post.py [--runner box|actions] [--dry-run] [--only news,deals]
                                  [--now 2026-09-25T18:30] [--force] [--no-setup]

No token or channel → silent skip (exit 0). --runner: runs only if site_config telegram.runner
matches (default "box"), so the box routine and the GitHub workflow never both post.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import np_digest as dg  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STATE_FILE = DATA / "telegram_posted.json"
CONFIG_FILE = DATA / "site_config.json"
SITE = dg.SITE
MSK = dg.MSK
NOW = datetime.now(MSK)  # overridable with --now (tests)
MAX_TOTAL = 4                      # posts per run (hourly) — the rest waits for the next run
QUIET = (0, 8)                     # MSK hours [from, to): no posts at night
NEWS_MAX_AGE_H = 12
NEWS_BACKLOG = 4                   # pending news beyond this are skipped (keeps the feed fresh)
PER_FEED = {"news": 2, "deals": 1, "freebies": 2, "esports": 2, "gotd": 1, "digest": 1, "poll": 1}
KEEP = 400
FEEDS = ["poll", "digest", "freebies", "deals", "esports", "gotd", "news"]  # priority order
TAGS = {"news": "#новости", "freebies": "#раздача", "deals": "#скидки", "esports": "#киберспорт",
        "gotd": "#иградня", "digest": "#итогинедели", "poll": "#опрос"}
DISCORD_FALLBACK = "https://discord.gg/7JvfzNrt4x"
POLL_Q = "Во что играешь на выходных? 🎮"
POLL_FALLBACK = ["CS2", "Dota 2", "Valorant", "Minecraft", "Fortnite", "Apex Legends", "GTA Online", "Rust"]

DESC_VERSION = 1
WELCOME_VERSION = 1


def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=False)


def clip(s, n: int) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1].rstrip(" ,.;:—-") + "…"


def tidy(s) -> str:
    """Repair words glued together by the source's HTML (e.g. «Teamоказалась сильнееRostik»)."""
    s = " ".join(str(s or "").split())
    s = re.sub(r"(?<=[A-Za-z])(?=[а-яё])|(?<=[а-яё])(?=[A-Z])|(?<=\d)(?=[а-яё]{2,}\b)", " ", s)
    return re.sub(r"(?<=\w)—", " —", s)


def short(s, n: int) -> str:
    """Clean, short text that ends on a whole sentence when possible."""
    s = tidy(s)
    cut = bool(re.search(r"(\.\.\.|…)$", s))
    s = re.sub(r"\s*(\.\.\.|…)+$", "", s)
    if not cut and len(s) <= n:
        return s
    head = s[:n]
    ends = [m.end() for m in re.finditer(r"[.!?](?=\s|$)", head)]
    if ends and ends[-1] >= 60:
        return head[: ends[-1]]
    if len(s) > n:
        return clip(s, n)
    if re.search(r"[.!?]$", s):
        return s
    return (s.rsplit(" ", 1)[0] if " " in s else s).rstrip(" ,.;:—-") + "…"  # drop the half-cut word


def safe_url(u) -> str | None:
    u = str(u or "").strip()
    return u if re.match(r"^https://[^\s<>\"']+$", u) else None


def link(url: str, text: str) -> str:
    return f'<a href="{html.escape(url, quote=True)}">{esc(text)}</a>'


def discord_url() -> str:
    return safe_url(dg.read_json("discord_channels.json").get("invite_url")) or DISCORD_FALLBACK


def footer(feed: str) -> str:
    """One quiet line: hashtag · NEXUS PULSE · Discord."""
    return f"\n\n{TAGS[feed]}  ·  {link(SITE, 'NEXUS PULSE')}  ·  {link(discord_url(), 'Discord')}"


def buttons(more: str | None, site: str = SITE, more_text: str = "Подробнее") -> list[tuple[str, str]]:
    out = []
    if more:
        out.append((more_text, more))
    if site and site != more:
        out.append(("🌐 Сайт", site))
    return out


def fits_caption(text: str) -> bool:
    return len(re.sub(r"<[^>]+>", "", text)) <= 1000


# ------------------------------------------------------------------ builders → {"key", "text", "photo"?, "buttons"?, "poll"?}
def b_news() -> list[dict]:
    cutoff = NOW - timedelta(hours=NEWS_MAX_AGE_H)
    out = []
    for n in dg.read_json("news.json").get("items") or []:
        d = dg.parse_dt(n.get("date"))
        if not n.get("id") or not n.get("title") or (d and d < cutoff):
            continue
        summary = short(n.get("summary"), 320)
        text = f"📰 <b>{esc(clip(tidy(n['title']), 180))}</b>"
        if summary:
            text += f"\n\n{esc(summary)}"
        if n.get("source"):
            text += f"\n\n<i>Источник: {esc(clip(n['source'], 40))}</i>"
        text += footer("news")
        more = f"{SITE}#news={n['id']}"
        out.append({"key": str(n["id"]), "sort": d.isoformat() if d else "", "text": text,
                    "photo": safe_url(n.get("image")), "buttons": buttons(more, SITE)})
    return sorted(out, key=lambda x: x["sort"])  # oldest → newest


def b_deals() -> list[dict]:
    deals = dg.top_deals(n=50)
    if not deals:
        return []
    top = deals[:5]
    key = "set:" + ",".join(sorted(f"{d.get('id') or d.get('title')}:{d['pct']}" for d in top))
    lines = [f"🔥 <b>−{d['pct']}%</b>  {link(safe_url(d.get('url')) or SITE + '#deals', clip(d['title'], 48))} — "
             f"<s>{esc(d.get('old'))}</s> <b>{esc(d.get('neu'))} ₽</b>" for d in top]
    photo = next((f"https://cdn.cloudflare.steamstatic.com/steam/apps/{d['steamAppId']}/header.jpg"
                  for d in top if str(d.get("steamAppId") or "").isdigit()), None)
    text = "💸 <b>Скидки дня в Steam</b>\n\n" + "\n".join(lines) + footer("deals")
    return [{"key": key, "items": [f"{d.get('id') or d.get('title')}:{d['pct']}" for d in top],
             "text": text, "photo": photo, "buttons": buttons(SITE + "#deals", SITE, "Все скидки")}]


def b_freebies() -> list[dict]:
    out = []
    for it in dg.current_freebies(n=10):
        state = "soon" if it["soon"] else "now"
        until = dg.parse_dt(it.get("until"))
        store = esc(it.get("store")) if it.get("store") else ""
        meta = " · ".join(x for x in [store, f"до {until:%d.%m}" if until else ""] if x)
        if it["soon"]:
            text = f"⏳ <b>Скоро бесплатно: {esc(clip(it['title'], 120))}</b>"
            tail = "Раздача вот-вот начнётся — загляни сюда чуть позже."
        else:
            text = f"🎁 <b>Бесплатно: {esc(clip(it['title'], 120))}</b>"
            tail = "Забирай — игра останется в библиотеке навсегда."
        text += (f"\n{meta}" if meta else "") + f"\n\n{tail}" + footer("freebies")
        claim = safe_url(it.get("claimUrl"))
        out.append({"key": f"{it['id']}:{state}", "text": text,
                    "buttons": buttons(claim or SITE + "#freebies", SITE + "#freebies",
                                       "🎁 Забрать" if claim and not it["soon"] else "Подробнее")})
    return list(reversed(out))  # current giveaways last


def b_esports() -> list[dict]:
    out = []
    up = dg.upcoming_matches(hours=24, n=8)
    if up:
        lines = [f"<code>{m['start']:%H:%M}</code>  {esc(m['gameName'])} · <b>{esc(m['teamA'])}</b> vs <b>{esc(m['teamB'])}</b>"
                 for m in up]
        out.append({"key": f"digest:{NOW:%Y-%m-%d}",
                    "text": "🏆 <b>Большие матчи сегодня</b> · время МСК\n\n" + "\n".join(lines) + footer("esports"),
                    "buttons": buttons(SITE + "#esports", SITE)})
    res = dg.match_results(days=1, n=6)
    if res:
        lines = [f"{esc(m['gameName'])} · <b>{esc(m['teamA'])}</b> {esc(m.get('scoreA'))}:{esc(m.get('scoreB'))} <b>{esc(m['teamB'])}</b>"
                 for m in res]
        out.append({"key": "results:" + ",".join(sorted(m["id"] for m in res)), "items": ["r:" + m["id"] for m in res],
                    "text": "✅ <b>Результаты больших матчей</b>\n\n" + "\n".join(lines) + footer("esports"),
                    "buttons": buttons(SITE + "#esports", SITE)})
    return out


def b_gotd() -> list[dict]:
    daily = dg.read_json("daily.json")
    g = daily.get("gameOfTheDay") or {}
    d = dg.parse_dt(daily.get("date"))
    if not g.get("title") or not d or d.date() < NOW.date() - timedelta(days=1):
        return []
    img = None
    t = g["title"].lower()
    for game in (dg.read_json("catalog.json").get("games") or {}).values():
        name = str(game.get("name") or "").lower()
        if name and (name == t or name.startswith(t) or t.startswith(name)):
            img = safe_url(game.get("img"))
            break
    text = f"🎮 <b>Игра дня: {esc(g['title'])}</b>" + (f" · {esc(g.get('genre'))}" if g.get("genre") else "")
    if g.get("reason"):
        text += f"\n\n{esc(clip(g['reason'], 300))}"
    if g.get("tip"):
        text += f"\n\n💡 {esc(clip(g['tip'], 200))}"
    text += footer("gotd")
    return [{"key": f"gotd:{daily.get('date')}", "text": text, "photo": img, "buttons": buttons(SITE + "#pulse", SITE)}]


def b_digest() -> list[dict]:
    if not (NOW.weekday() == 6 and NOW.hour >= 19):
        return []
    y, w, _ = NOW.isocalendar()
    d = dg.weekly()
    parts = ["📊 <b>Итоги недели на NEXUS PULSE</b>"]
    if d["freebies"]:
        parts.append("🎁 <b>Раздачи</b>\n" + "\n".join(
            f"{'⏳ ' if x['soon'] else '• '}{link(safe_url(x.get('claimUrl')) or SITE + '#freebies', clip(x['title'], 45))} · {esc(x.get('store'))}"
            for x in d["freebies"]))
    if d["deals"]:
        parts.append("💸 <b>Скидки</b>\n" + "\n".join(
            f"• −{x['pct']}% {link(safe_url(x.get('url')) or SITE + '#deals', clip(x['title'], 45))} — {esc(x.get('neu'))} ₽"
            for x in d["deals"]))
    if d["results"]:
        parts.append("🏆 <b>Большие матчи</b>\n" + "\n".join(
            f"• {esc(m['gameName'])} · {esc(m['teamA'])} {esc(m.get('scoreA'))}:{esc(m.get('scoreB'))} {esc(m['teamB'])}"
            for m in d["results"][:5]))
    if d["news"]:
        parts.append("📰 <b>Главные новости</b>\n" + "\n".join(
            f"• {link(f'{SITE}#news={n['id']}', clip(n['title'], 70))}" for n in d["news"]))
    if len(parts) == 1:
        return []
    text = "\n\n".join(parts)[:3800] + footer("digest")
    return [{"key": f"week:{y}-W{w:02d}", "text": text, "buttons": [("Подробнее", SITE), ("💬 Discord", discord_url())]}]


def poll_options() -> list[str]:
    daily = dg.read_json("daily.json")
    names = [str(t.get("title") or "").strip() for t in daily.get("trending") or []]
    names += POLL_FALLBACK
    out: list[str] = []
    for n in names:
        if n and len(n) <= 90 and n.lower() not in {x.lower() for x in out}:
            out.append(n)
        if len(out) >= 8:
            break
    return out + ["Другое / пока не решил 🤔"]


def b_poll() -> list[dict]:
    wd, h = NOW.weekday(), NOW.hour
    if not ((wd == 4 and h >= 12) or (wd == 5 and h < 14)):
        return []
    y, w, _ = NOW.isocalendar()
    return [{"key": f"poll:{y}-W{w:02d}", "text": POLL_Q, "poll": poll_options(),
             "buttons": [("🎮 Найти тиммейтов", SITE + "#lfg")]}]


BUILDERS = {"news": b_news, "deals": b_deals, "freebies": b_freebies, "esports": b_esports, "gotd": b_gotd,
            "digest": b_digest, "poll": b_poll}


# ------------------------------------------------------------------ channel setup (description + pinned welcome)
def description() -> str:
    site = SITE.replace("https://", "").rstrip("/")
    disc = discord_url().replace("https://", "")
    return ("🎮 Игровой пульс каждый день: новости, раздачи бесплатных игр, скидки от −50%, "
            "большие матчи и игра дня. По пятницам — опрос, по воскресеньям — итоги недели.\n"
            f"🌐 {site}\n💬 {disc}")


def welcome() -> dict:
    text = (
        "👋 <b>Добро пожаловать в NEXUS PULSE!</b>\n\n"
        "Каждый день здесь — всё главное из мира игр, коротко и по делу:\n\n"
        "📰 Свежие новости — #новости\n"
        "🎁 Раздачи бесплатных игр — #раздача\n"
        "💸 Скидки от −50% в Steam — #скидки\n"
        "🏆 Большие матчи и результаты — #киберспорт\n"
        "🎮 Игра дня: во что поиграть сегодня — #иградня\n"
        "🗳 Опрос по пятницам — #опрос\n"
        "📊 Итоги недели по воскресеньям — #итогинедели\n\n"
        "🔎 Нажми на хэштег — и увидишь все посты по теме.\n"
        "🌙 С 00:00 до 08:00 по Москве канал молчит — никаких ночных уведомлений.\n\n"
        "Ищешь, с кем поиграть? Заходи в наш Discord или жми «Найти тиммейтов» 👇"
    )
    kb = [[{"text": "🌐 Сайт", "url": SITE}, {"text": "💬 Discord", "url": discord_url()}],
          [{"text": "🎮 Найти тиммейтов", "url": SITE + "#lfg"}]]
    return {"text": text, "reply_markup": {"inline_keyboard": kb}}


def setup_channel(tg: "TG", chan: dict, force: bool = False) -> list[str]:
    log = []
    if force or chan.get("descVersion") != DESC_VERSION:
        desc = description()
        try:
            tg.call("setChatDescription", {"chat_id": tg.chat, "description": desc[:255]})
            chan["descVersion"] = DESC_VERSION
            log.append("description set")
        except RuntimeError as e:
            if "not modified" in str(e):
                chan["descVersion"] = DESC_VERSION
            else:
                log.append(f"[warn] description: {e}")
    if force or chan.get("welcomeVersion") != WELCOME_VERSION:
        w = welcome()
        try:
            r = tg.call("sendMessage", {"chat_id": tg.chat, "text": w["text"], "parse_mode": "HTML",
                                        "link_preview_options": {"is_disabled": True}, "reply_markup": w["reply_markup"]})
            mid = (r.get("result") or {}).get("message_id")
            old = chan.get("welcomeId")
            if mid:
                if old and old != mid:
                    try:
                        tg.call("unpinChatMessage", {"chat_id": tg.chat, "message_id": old})
                    except RuntimeError:
                        pass
                tg.call("pinChatMessage", {"chat_id": tg.chat, "message_id": mid, "disable_notification": True})
                try:  # the «… закрепил сообщение» service line right after the post
                    tg.call("deleteMessage", {"chat_id": tg.chat, "message_id": mid + 1})
                except RuntimeError:
                    pass
                chan.update(welcomeId=mid, welcomeVersion=WELCOME_VERSION)
            elif tg.dry:
                chan.update(welcomeVersion=WELCOME_VERSION)
            log.append(f"welcome posted + pinned ({mid})")
        except RuntimeError as e:
            log.append(f"[warn] welcome: {e}")
    return log


# ------------------------------------------------------------------ Telegram API
class TG:
    def __init__(self, token: str, chat: str, dry: bool):
        self._token = token
        self.chat = chat
        self.dry = dry

    def call(self, method: str, body: dict) -> dict:
        if self.dry:
            print(f"[dry] {method}: {json.dumps(body, ensure_ascii=False)[:1500]}")
            return {"ok": True, "result": {}}
        data = json.dumps(body).encode("utf-8")
        for _ in range(4):
            req = urllib.request.Request(f"https://api.telegram.org/bot{self._token}/{method}", data=data,
                                         headers={"Content-Type": "application/json"}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return json.loads(r.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                txt = e.read().decode("utf-8", "replace")
                try:
                    j = json.loads(txt)
                except Exception:  # noqa: BLE001
                    j = {"description": txt[:200]}
                if e.code == 429:
                    time.sleep(min(int((j.get("parameters") or {}).get("retry_after", 5)), 60) + 1)
                    continue
                raise RuntimeError(f"Telegram {method} → {e.code}: {j.get('description', '')[:200]}") from None
            except urllib.error.URLError:
                time.sleep(3)
        raise RuntimeError(f"Telegram {method} failed")

    def post(self, item: dict) -> dict:
        markup = None
        if item.get("buttons"):
            markup = {"inline_keyboard": [[{"text": t, "url": u} for t, u in item["buttons"]]]}
        if item.get("poll"):
            body = {"chat_id": self.chat, "question": item["text"][:300],
                    "options": [{"text": o[:100]} for o in item["poll"][:10]],
                    "is_anonymous": True, "allows_multiple_answers": True}
            if markup:
                body["reply_markup"] = markup
            return self.call("sendPoll", body)
        text = item["text"]
        if item.get("photo") and fits_caption(text) and len(text) <= 4000:
            body = {"chat_id": self.chat, "photo": item["photo"], "caption": text, "parse_mode": "HTML"}
            if markup:
                body["reply_markup"] = markup
            try:
                return self.call("sendPhoto", body)
            except RuntimeError as e:
                print(f"  photo failed, sending text: {e}")
        body = {"chat_id": self.chat, "text": text[:4096], "parse_mode": "HTML",
                "link_preview_options": {"is_disabled": not bool(item.get("photo")), **({"url": item["photo"], "show_above_text": True} if item.get("photo") else {})}}
        if markup:
            body["reply_markup"] = markup
        return self.call("sendMessage", body)


def main() -> int:
    global NOW
    ap = argparse.ArgumentParser()
    ap.add_argument("--runner", choices=["box", "actions", "any"], default="any")
    ap.add_argument("--only", default="")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--now", default="", help="pretend time (MSK), e.g. 2026-09-27T19:30 — for tests")
    ap.add_argument("--force", action="store_true", help="ignore quiet hours")
    ap.add_argument("--no-setup", action="store_true", help="skip channel description / pinned welcome")
    ap.add_argument("--setup-only", action="store_true", help="only (re)apply description + pinned welcome")
    ap.add_argument("--repin", action="store_true", help="re-post and re-pin the welcome message")
    a = ap.parse_args()
    if a.now:
        NOW = datetime.fromisoformat(a.now).replace(tzinfo=MSK)
    cfg = (dg.read_json("site_config.json").get("telegram") or {}) if CONFIG_FILE.is_file() else {}
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        token_file = Path("/home/box/.config/telegram-bot-token")
        if token_file.is_file():
            token = token_file.read_text(encoding="utf-8").strip()
    chat = (os.environ.get("TELEGRAM_CHANNEL") or cfg.get("channel") or "").strip()
    if not a.dry_run and (not token or not chat):
        return 0
    if a.runner != "any" and (cfg.get("runner") or "box") != a.runner:
        print(f"telegram: runner is '{cfg.get('runner') or 'box'}', not '{a.runner}' — skip")
        return 0
    if chat and not chat.startswith("@") and not re.fullmatch(r"-?\d+", chat):
        chat = "@" + chat
    quiet = QUIET[0] <= NOW.hour < QUIET[1]
    if quiet and not a.force and not a.setup_only:
        print(f"telegram: quiet hours ({QUIET[0]:02d}:00–{QUIET[1]:02d}:00 MSK) — nothing sent")
        return 0
    tg = TG(token, chat or "@dry", a.dry_run)
    state = dg.read_json("telegram_posted.json") or {}
    posted: dict[str, list[str]] = {k: list(v) for k, v in (state.get("posted") or {}).items()}
    chan: dict = dict(state.get("channel") or {})
    for line in ([] if a.no_setup else setup_channel(tg, chan, force=a.repin)):
        print(f"channel: {line}")
    only = [] if a.setup_only else [f for f in (a.only.split(",") if a.only else FEEDS) if f in BUILDERS]
    total = errors = 0
    for feed in only:
        try:
            cands = BUILDERS[feed]()
        except Exception as e:  # noqa: BLE001
            print(f"{feed}: build failed: {e}")
            continue
        seen = set(posted.get(feed) or [])
        seeding = feed not in posted and feed not in ("poll", "digest")
        # grouped posts (deals / results) are new only if they contain an unseen item
        new = [c for c in cands if c["key"] not in seen and (not c.get("items") or any(i not in seen for i in c["items"]))]
        skip: list[dict] = []
        if seeding:
            skip, new = new[:-1], new[-1:]
        elif feed == "news" and len(new) > NEWS_BACKLOG:
            skip, new = new[:-NEWS_BACKLOG], new[-NEWS_BACKLOG:]
        room = max(0, MAX_TOTAL - total)
        chosen = new[: min(PER_FEED.get(feed, 2), room)]  # oldest first; the rest waits for the next run
        print(f"{feed}: {len(cands)} items, {len(new)} new, posting {len(chosen)}"
              f"{' (seed)' if seeding else ''}{f', {len(new) - len(chosen)} wait' if len(new) > len(chosen) else ''}"
              f"{f', {len(skip)} skipped' if skip else ''}")
        for c in chosen:
            try:
                r = tg.post(c)
                mid = (r.get("result") or {}).get("message_id")
                if mid:
                    print(f"  → message {mid}")
                total += 1
            except RuntimeError as e:
                print(f"{feed}: send failed: {e}")
                errors += 1
                break
            posted.setdefault(feed, []).extend([c["key"], *(c.get("items") or [])])
        for c in skip:
            posted.setdefault(feed, []).extend([c["key"], *(c.get("items") or [])])
        posted.setdefault(feed, [])
        posted[feed] = list(dict.fromkeys(posted[feed]))[-KEEP:]
    if a.dry_run:
        print(f"dry-run: {total} messages")
        return 0
    new_state = {"about": "Telegram autopost dedupe state (ids only). Written by scripts/telegram_post.py.",
                 "updatedAt": NOW.isoformat(timespec="seconds") if total else state.get("updatedAt", ""),
                 "channel": chan, "posted": posted}
    if {k: v for k, v in new_state.items() if k != "updatedAt"} != {k: v for k, v in state.items() if k != "updatedAt"}:
        STATE_FILE.write_text(json.dumps(new_state, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"telegram: sent {total}, errors {errors}")
    return 1 if errors and not total else 0


if __name__ == "__main__":
    raise SystemExit(main())
