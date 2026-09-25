#!/usr/bin/env python3
"""NEXUS PULSE → Telegram channel autopost (mirrors the Discord feeds).

Posts NEW items from the site's data/*.json: news, discounts −50%+, giveaways, big matches
(daily S-tier schedule + results), game of the day and the Sunday «Итоги недели».
Dedupe state: data/telegram_posted.json. First run per feed = seed (only the freshest item).
Per run: ≤ 6 messages total, ≤ 2 news.

  env TELEGRAM_BOT_TOKEN   bot token from @BotFather (never printed)
  env TELEGRAM_CHANNEL     @channel (or data/site_config.json → telegram.channel)
  python scripts/telegram_post.py [--runner box|actions] [--dry-run] [--only news,deals]

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
MAX_TOTAL = 6
PER_FEED = {"news": 2, "deals": 1, "freebies": 3, "esports": 2, "gotd": 1, "digest": 1}
KEEP = 400
FEEDS = ["freebies", "deals", "esports", "gotd", "news", "digest"]


def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=False)


def clip(s, n: int) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1].rstrip(" ,.;:—-") + "…"


def safe_url(u) -> str | None:
    u = str(u or "").strip()
    return u if re.match(r"^https://[^\s<>\"']+$", u) else None


def link(url: str, text: str) -> str:
    return f'<a href="{html.escape(url, quote=True)}">{esc(text)}</a>'


# ------------------------------------------------------------------ builders → {"key", "text", "photo"?, "button"?}
def b_news() -> list[dict]:
    cutoff = datetime.now(MSK) - timedelta(hours=24)
    out = []
    for n in dg.read_json("news.json").get("items") or []:
        d = dg.parse_dt(n.get("date"))
        if not n.get("id") or not n.get("title") or (d and d < cutoff):
            continue
        text = (f"📰 <b>{esc(clip(n['title'], 200))}</b>\n\n{esc(clip(n.get('summary'), 500))}\n\n"
                f"{link(f'{SITE}#news={n['id']}', 'Читать на NEXUS PULSE →')}" + (f" · <i>{esc(n.get('source'))}</i>" if n.get("source") else ""))
        out.append({"key": str(n["id"]), "sort": d.isoformat() if d else "", "text": text, "photo": safe_url(n.get("image")),
                    "button": ("Читать полностью", f"{SITE}#news={n['id']}")})
    return sorted(out, key=lambda x: x["sort"])


def b_deals() -> list[dict]:
    deals = dg.top_deals(n=50)
    if not deals:
        return []
    key = "set:" + ",".join(sorted(f"{d.get('id') or d.get('title')}:{d['pct']}" for d in deals[:5]))
    lines = [f"🔥 <b>−{d['pct']}%</b> {link(safe_url(d.get('url')) or SITE + '#deals', clip(d['title'], 60))} — "
             f"<s>{esc(d.get('old'))}</s> <b>{esc(d.get('neu'))} ₽</b>" for d in deals[:5]]
    photo = next((f"https://cdn.cloudflare.steamstatic.com/steam/apps/{d['steamAppId']}/header.jpg"
                  for d in deals[:5] if str(d.get("steamAppId") or "").isdigit()), None)
    return [{"key": key, "items": [f"{d.get('id') or d.get('title')}:{d['pct']}" for d in deals[:5]],
             "text": "💸 <b>Скидки дня в Steam</b>\n\n" + "\n".join(lines), "photo": photo,
             "button": ("Все скидки", SITE + "#deals")}]


def b_freebies() -> list[dict]:
    out = []
    for it in dg.current_freebies(n=10):
        state = "soon" if it["soon"] else "now"
        until = dg.parse_dt(it.get("until"))
        head = "⏳ <b>Скоро бесплатно</b>" if it["soon"] else "🎁 <b>Бесплатно</b>"
        text = (f"{head}: {esc(clip(it['title'], 150))}\n{esc(it.get('store'))}"
                + (f" · до {until:%d.%m}" if until else "")
                + ("\n\nЗабирай — игра останется в библиотеке навсегда." if not it["soon"] else "\n\nДобавь в библиотеку, как только стартует."))
        url = safe_url(it.get("claimUrl")) or SITE + "#freebies"
        out.append({"key": f"{it['id']}:{state}", "text": text, "button": ("Забрать" if not it["soon"] else "Открыть", url)})
    return list(reversed(out))  # current giveaways last = preferred by the "newest N" cut


def b_esports() -> list[dict]:
    out = []
    now = datetime.now(MSK)
    up = [m for m in dg.upcoming_matches(hours=24, n=8)]
    if up:
        lines = [f"<code>{m['start']:%H:%M}</code> {esc(m['gameName'])} · <b>{esc(m['teamA'])}</b> vs <b>{esc(m['teamB'])}</b> · {esc(clip(m.get('event'), 40))}" for m in up]
        out.append({"key": f"digest:{now:%Y-%m-%d}", "text": f"🏆 <b>Большие матчи сегодня</b> (МСК)\n\n" + "\n".join(lines),
                    "button": ("Трансляции", SITE + "#esports")})
    res = dg.match_results(days=1, n=6)
    if res:
        lines = [f"{esc(m['gameName'])} · <b>{esc(m['teamA'])}</b> {esc(m.get('scoreA'))}:{esc(m.get('scoreB'))} <b>{esc(m['teamB'])}</b>" for m in res]
        out.append({"key": "results:" + ",".join(sorted(m["id"] for m in res)), "items": ["r:" + m["id"] for m in res],
                    "text": "✅ <b>Результаты топ-матчей</b>\n\n" + "\n".join(lines), "button": ("Все матчи", SITE + "#esports")})
    return out


def b_gotd() -> list[dict]:
    daily = dg.read_json("daily.json")
    g = daily.get("gameOfTheDay") or {}
    d = dg.parse_dt(daily.get("date"))
    if not g.get("title") or not d or d.date() < datetime.now(MSK).date() - timedelta(days=1):
        return []
    img = None
    t = g["title"].lower()
    for game in (dg.read_json("catalog.json").get("games") or {}).values():
        name = str(game.get("name") or "").lower()
        if name and (name == t or name.startswith(t) or t.startswith(name)):
            img = safe_url(game.get("img"))
            break
    text = f"🎮 <b>Игра дня: {esc(g['title'])}</b>" + (f"\n{esc(g.get('genre'))}" if g.get("genre") else "")
    if g.get("reason"):
        text += f"\n\n{esc(clip(g['reason'], 500))}"
    if g.get("tip"):
        text += f"\n\n💡 {esc(clip(g['tip'], 300))}"
    return [{"key": f"gotd:{daily.get('date')}", "text": text, "photo": img, "button": ("Пульс дня", SITE + "#pulse")}]


def b_digest() -> list[dict]:
    now = datetime.now(MSK)
    if not (now.weekday() == 6 and now.hour >= 19):
        return []
    y, w, _ = now.isocalendar()
    d = dg.weekly()
    parts = ["📊 <b>Итоги недели на NEXUS PULSE</b>"]
    if d["deals"]:
        parts.append("💸 <b>Скидки</b>\n" + "\n".join(f"−{x['pct']}% {link(safe_url(x.get('url')) or SITE + '#deals', clip(x['title'], 50))} — {esc(x.get('neu'))} ₽" for x in d["deals"]))
    if d["freebies"]:
        parts.append("🎁 <b>Бесплатно</b>\n" + "\n".join(f"{'⏳ ' if x['soon'] else ''}{link(safe_url(x.get('claimUrl')) or SITE + '#freebies', clip(x['title'], 50))} · {esc(x.get('store'))}" for x in d["freebies"]))
    if d["results"]:
        parts.append("🏆 <b>Большие матчи</b>\n" + "\n".join(f"{esc(m['gameName'])} · {esc(m['teamA'])} {esc(m.get('scoreA'))}:{esc(m.get('scoreB'))} {esc(m['teamB'])}" for m in d["results"][:5]))
    if d["news"]:
        parts.append("📰 <b>Новости</b>\n" + "\n".join(f"• {link(f'{SITE}#news={n['id']}', clip(n['title'], 80))}" for n in d["news"]))
    return [{"key": f"week:{y}-W{w:02d}", "text": "\n\n".join(parts)[:4000], "button": ("Открыть NEXUS PULSE", SITE)}]


BUILDERS = {"news": b_news, "deals": b_deals, "freebies": b_freebies, "esports": b_esports, "gotd": b_gotd, "digest": b_digest}


# ------------------------------------------------------------------ Telegram API
class TG:
    def __init__(self, token: str, chat: str, dry: bool):
        self._token = token
        self.chat = chat
        self.dry = dry

    def call(self, method: str, body: dict) -> dict:
        if self.dry:
            print(f"[dry] {method}: {json.dumps(body, ensure_ascii=False)[:400]}")
            return {"ok": True}
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
            except urllib.error.URLError as e:
                last = e
                time.sleep(3)
        raise RuntimeError(f"Telegram {method} failed")

    def post(self, item: dict) -> None:
        markup = None
        if item.get("button"):
            markup = {"inline_keyboard": [[{"text": item["button"][0], "url": item["button"][1]}]]}
        text = item["text"]
        if item.get("photo") and len(text) <= 1024:
            body = {"chat_id": self.chat, "photo": item["photo"], "caption": text, "parse_mode": "HTML"}
            if markup:
                body["reply_markup"] = markup
            try:
                self.call("sendPhoto", body)
                return
            except RuntimeError as e:
                print(f"  photo failed, sending text: {e}")
        body = {"chat_id": self.chat, "text": text[:4096], "parse_mode": "HTML",
                "link_preview_options": {"is_disabled": not bool(item.get("photo")), **({"url": item["photo"]} if item.get("photo") else {})}}
        if markup:
            body["reply_markup"] = markup
        self.call("sendMessage", body)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runner", choices=["box", "actions", "any"], default="any")
    ap.add_argument("--only", default="")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    cfg = (dg.read_json("site_config.json").get("telegram") or {}) if CONFIG_FILE.is_file() else {}
    token = (os.environ.get("TELEGRAM_BOT_TOKEN") or "").strip()
    chat = (os.environ.get("TELEGRAM_CHANNEL") or cfg.get("channel") or "").strip()
    if not a.dry_run and (not token or not chat):
        print("telegram: no token / channel configured — skip")
        return 0
    if a.runner != "any" and (cfg.get("runner") or "box") != a.runner:
        print(f"telegram: runner is '{cfg.get('runner') or 'box'}', not '{a.runner}' — skip")
        return 0
    if chat and not chat.startswith("@") and not re.fullmatch(r"-?\d+", chat):
        chat = "@" + chat
    tg = TG(token, chat or "@dry", a.dry_run)
    state = dg.read_json("telegram_posted.json") or {}
    posted: dict[str, list[str]] = state.get("posted") or {}
    only = [f for f in (a.only.split(",") if a.only else FEEDS) if f in BUILDERS]
    total = errors = 0
    for feed in only:
        if total >= MAX_TOTAL:
            break
        try:
            cands = BUILDERS[feed]()
        except Exception as e:  # noqa: BLE001
            print(f"{feed}: build failed: {e}")
            continue
        seen = set(posted.get(feed) or [])
        seeding = feed not in posted
        # grouped posts (deals / results) are new only if they contain an unseen item
        new = [c for c in cands if c["key"] not in seen and (not c.get("items") or any(i not in seen for i in c["items"]))]
        limit = 1 if seeding else PER_FEED.get(feed, 2)
        chosen = new[-limit:]
        print(f"{feed}: {len(cands)} items, {len(new)} new, posting {len(chosen)}{' (seed)' if seeding else ''}")
        for c in chosen:
            if total >= MAX_TOTAL:
                break
            try:
                tg.post(c)
                total += 1
            except RuntimeError as e:
                print(f"{feed}: send failed: {e}")
                errors += 1
                break
            posted.setdefault(feed, []).extend([c["key"], *(c.get("items") or [])])
        for c in new:  # overflow is dropped, never queued
            if c not in chosen:
                posted.setdefault(feed, []).extend([c["key"], *(c.get("items") or [])])
        posted.setdefault(feed, [])
        posted[feed] = list(dict.fromkeys(posted[feed]))[-KEEP:]
    if a.dry_run:
        print(f"dry-run: {total} messages")
        return 0
    new_state = {"about": "Telegram autopost dedupe state (ids only). Written by scripts/telegram_post.py.",
                 "updatedAt": datetime.now(MSK).isoformat(timespec="seconds") if total else state.get("updatedAt", ""),
                 "posted": posted}
    if {k: v for k, v in new_state.items() if k != "updatedAt"} != {k: v for k, v in state.items() if k != "updatedAt"}:
        STATE_FILE.write_text(json.dumps(new_state, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"telegram: sent {total}, errors {errors}")
    return 1 if errors and not total else 0


if __name__ == "__main__":
    raise SystemExit(main())
