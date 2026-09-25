#!/usr/bin/env python3
"""NEXUS PULSE — recurring server activity (run hourly by scripts/discord_box_sync.sh).

  * Friday ≥18:00 MSK  — native poll «Во что играем в выходные?» in #💬общий (24 h, games from roles)
  * Sunday ≥19:00 MSK  — «Итоги недели» digest in #📢анонсы (deals, giveaways, results, news, poll, members)
  * Tue…Sat            — weekly «Игровой вечер» scheduled event: Saturday 20:00 MSK in 🔊 Игровой вечер
                         (description updated with the poll winner; started/finished automatically)

Idempotent: keyed by ISO week in data/discord_posted.json → "weekly". No @everyone / role pings.
  python scripts/discord_weekly.py [--dry-run] [--now 2026-09-25T18:30]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from discord_api import GUILD_ID, Bot, DiscordError  # noqa: E402
import np_digest as dg  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
STATE_FILE = ROOT / "data" / "discord_posted.json"
CHANNELS_FILE = ROOT / "data" / "discord_channels.json"
MSK = dg.MSK
SITE = dg.SITE
LOGO = SITE + "assets/nexus-pulse-icon.png"
GAMES = [  # emoji, poll label (same order as the role picker)
    ("💣", "CS2"), ("🎯", "Valorant"), ("🐉", "Dota 2"), ("🧙", "League of Legends"), ("🦙", "Fortnite"),
    ("🧱", "Minecraft"), ("🦅", "Apex Legends"), ("🍳", "PUBG"), ("🚗", "GTA Online"), ("🪓", "Rust"),
]
POLL_Q = "Во что играем в выходные?"
NIGHT_NAME = "🎮 Игровой вечер NEXUS PULSE"
MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"]


def read_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def md(s) -> str:
    import re
    return re.sub(r"([\\*_~`|>\[\]()])", r"\\\1", "" if s is None else str(s)).replace("@", "@\u200b")


def clip(s, n: int) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def score(m: dict) -> str:
    a, b = m.get("scoreA"), m.get("scoreB")
    return f"{a}:{b}" if a is not None and b is not None else "vs"


def iso_z(d: datetime) -> str:
    return d.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")


class Weekly:
    def __init__(self, now: datetime, dry: bool):
        self.now = now
        self.dry = dry
        self.bot = Bot()
        self.ch = read_json(CHANNELS_FILE, {})
        self.state = read_json(STATE_FILE, {})
        self.w = self.state.setdefault("weekly", {})
        y, wk, _ = now.isocalendar()
        self.week = f"{y}-W{wk:02d}"
        self.changed = False
        self.log: list[str] = []

    # ---------------------------------------------------------------- helpers
    def mark(self, key: str, value) -> None:
        self.w.setdefault(key, {})[self.week] = value
        # keep the last 8 weeks only
        self.w[key] = dict(sorted(self.w[key].items())[-8:])
        self.changed = True

    def got(self, key: str, week: str | None = None):
        return (self.w.get(key) or {}).get(week or self.week)

    def saturday(self) -> datetime:
        monday = (self.now - timedelta(days=self.now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
        return monday + timedelta(days=5)

    def send(self, channel: str, body: dict) -> dict | None:
        body.setdefault("allowed_mentions", {"parse": []})
        if self.dry:
            print("[dry]", json.dumps(body, ensure_ascii=False)[:1500])
            return {"id": "dry"}
        return self.bot.api("POST", f"/channels/{channel}/messages", body)

    def poll_message(self, week: str | None = None) -> dict | None:
        mid = self.got("poll", week)
        if not mid or mid == "dry" or not self.ch.get("general"):
            return None
        try:
            return self.bot.api("GET", f"/channels/{self.ch['general']}/messages/{mid}")
        except DiscordError:
            return None

    @staticmethod
    def poll_ranking(msg: dict | None) -> list[tuple[str, int]]:
        poll = (msg or {}).get("poll") or {}
        counts = {a["id"]: a.get("count", 0) for a in (poll.get("results") or {}).get("answer_counts") or []}
        rank = [((a.get("poll_media") or {}).get("text") or "?", counts.get(a.get("answer_id"), 0)) for a in poll.get("answers") or []]
        return sorted([r for r in rank if r[1] > 0], key=lambda r: -r[1])

    # ---------------------------------------------------------------- game night event
    def gamenight(self) -> None:
        vc = self.ch.get("voice_gamenight")
        if not vc:
            return
        sat = self.saturday()
        start = sat.replace(hour=20)
        eid = self.got("gamenight")
        if not eid and 1 <= self.now.weekday() <= 5 and self.now < start - timedelta(hours=1):
            body = {
                "name": NIGHT_NAME,
                "description": (f"Суббота, {start.day} {MONTHS[start.month - 1]}, 20:00 МСК — собираемся поиграть всем сервером!\n"
                                "Во что — решаем в пятничном опросе в #💬общий. Заходи в 🔊 Игровой вечер, "
                                "нажми «Интересно», чтобы получить напоминание.\n"
                                f"Тиммейтов можно найти заранее в #🔎поиск-тимы · {SITE}#lfg")[:1000],
                "privacy_level": 2, "entity_type": 2, "channel_id": vc,
                "scheduled_start_time": iso_z(start),
            }
            if self.dry:
                print("[dry] event", json.dumps(body, ensure_ascii=False))
                return
            try:
                ev = self.bot.api("POST", f"/guilds/{GUILD_ID}/scheduled-events", body, reason="NEXUS PULSE game night")
                self.mark("gamenight", ev["id"])
                self.log.append(f"+ game night event {start:%d.%m %H:%M} MSK")
            except DiscordError as e:
                self.log.append(f"[warn] game night event failed ({e.code}): {e.body[:200]}")
            return
        if not eid or self.dry:
            return
        try:
            ev = self.bot.api("GET", f"/guilds/{GUILD_ID}/scheduled-events/{eid}")
        except DiscordError:
            return
        st = ev.get("status")
        ev_start = dg.parse_dt(ev.get("scheduled_start_time"))
        # poll winner → description (once the poll is finalized)
        if st == 1 and not self.got("gamenightGame"):
            rank = self.poll_ranking(self.poll_message())
            finalized = ((self.poll_message() or {}).get("poll") or {}).get("results", {}).get("is_finalized")
            if rank and finalized:
                top = ", ".join(t for t, c in rank[:2] if c == rank[0][1]) or rank[0][0]
                desc = (f"По итогам опроса играем: **{top}** 🎮\n" + (ev.get("description") or ""))[:1000]
                try:
                    self.bot.api("PATCH", f"/guilds/{GUILD_ID}/scheduled-events/{eid}", {"description": desc})
                    self.mark("gamenightGame", top)
                    self.log.append(f"~ game night: {top}")
                except DiscordError as e:
                    self.log.append(f"[warn] event patch failed ({e.code})")
        try:
            if st == 1 and ev_start and self.now >= ev_start:
                self.bot.api("PATCH", f"/guilds/{GUILD_ID}/scheduled-events/{eid}", {"status": 2})
                self.log.append("~ game night started")
            elif st == 2 and ev_start and self.now >= ev_start + timedelta(hours=3, minutes=30):
                self.bot.api("PATCH", f"/guilds/{GUILD_ID}/scheduled-events/{eid}", {"status": 3})
                self.log.append("~ game night finished")
        except DiscordError as e:
            self.log.append(f"[warn] event status failed ({e.code})")

    # ---------------------------------------------------------------- Friday poll
    def poll(self) -> None:
        wd, h = self.now.weekday(), self.now.hour
        due = (wd == 4 and h >= 18) or (wd == 5 and h < 14)
        if not due or self.got("poll") or not self.ch.get("general"):
            return
        ev = self.got("gamenight")
        when = "в субботу в 20:00 МСК" + (f" — [событие сервера](https://discord.com/events/{GUILD_ID}/{ev})" if ev else "")
        body = {
            "content": (f"🗳 **Выходные близко!** Голосуй за игру (можно несколько) — соберёмся {when} "
                        f"в <#{self.ch.get('voice_gamenight', self.ch.get('voice_lobby'))}>.\n"
                        f"Не нашёл свою игру — напиши в чат 👇"),
            "poll": {
                "question": {"text": POLL_Q},
                "answers": [{"poll_media": {"text": t, "emoji": {"name": e}}} for e, t in GAMES],
                "duration": 24, "allow_multiselect": True, "layout_type": 1,
            },
        }
        try:
            msg = self.send(self.ch["general"], body)
            if not self.dry:
                self.mark("poll", msg["id"])
            self.log.append("+ weekend poll")
        except DiscordError as e:
            self.log.append(f"[warn] poll failed ({e.code}): {e.body[:200]}")

    # ---------------------------------------------------------------- Sunday digest
    def digest(self) -> None:
        if not (self.now.weekday() == 6 and self.now.hour >= 19) or self.got("digest") or not self.ch.get("announcements"):
            return
        d = dg.weekly()
        fields = []
        if d["deals"]:
            fields.append({"name": "💸 Лучшие скидки", "inline": False, "value": "\n".join(
                f"**−{x['pct']}%** [{md(clip(x['title'], 60))}]({x.get('url') or SITE + '#deals'}) — {md(x.get('neu'))} ₽"
                for x in d["deals"])[:1024]})
        if d["freebies"]:
            fields.append({"name": "🎁 Бесплатно", "inline": False, "value": "\n".join(
                f"{'⏳ скоро: ' if x['soon'] else ''}[{md(clip(x['title'], 60))}]({x.get('claimUrl') or SITE + '#freebies'}) · {md(x.get('store'))}"
                + (f" · до {dg.parse_dt(x['until']):%d.%m}" if x.get("until") else "") for x in d["freebies"])[:1024]})
        if d["results"]:
            fields.append({"name": "🏆 Большие матчи", "inline": False, "value": "\n".join(
                f"{md(m['gameName'])} · **{md(m['teamA'])}** {score(m)} **{md(m['teamB'])}** · {md(clip(m.get('event'), 40))}"
                for m in d["results"])[:1024]})
        if d["upcoming"]:
            fields.append({"name": "📅 Скоро", "inline": False, "value": "\n".join(
                f"`{m['start']:%d.%m %H:%M}` {md(m['gameName'])} · **{md(m['teamA'])}** vs **{md(m['teamB'])}**" for m in d["upcoming"][:3])[:1024]})
        if d["news"]:
            fields.append({"name": "📰 Свежие новости", "inline": False, "value": "\n".join(
                f"• [{md(clip(n['title'], 90))}]({SITE}#news={n['id']})" for n in d["news"])[:1024]})
        rank = self.poll_ranking(self.poll_message())
        if rank:
            fields.append({"name": "🗳 Опрос выходных", "inline": False, "value": " · ".join(f"{md(t)} — {c}" for t, c in rank[:5])})
        members = None
        try:
            g = self.bot.api("GET", f"/guilds/{GUILD_ID}?with_counts=true")
            members = int(g.get("approximate_member_count") or 0)
        except (DiscordError, ValueError, TypeError):
            pass
        if members:
            prev = None
            for wk, cnt in sorted((self.w.get("members") or {}).items()):
                if wk < self.week:
                    prev = cnt
            grow = f" (+{members - prev} за неделю)" if prev is not None and members > prev else ""
            fields.append({"name": "👥 Сервер", "inline": False, "value": f"Нас уже **{members}**{grow}. Зови друзей: {self.ch.get('invite_url', '')}"})
        body = {"embeds": [{
            "title": "📊 Итоги недели на NEXUS PULSE", "url": SITE, "color": 0x8B5CFF,
            "description": "Всё главное за неделю в одном посте. Больше — на сайте 👇",
            "fields": fields[:10], "thumbnail": {"url": LOGO},
            "footer": {"text": "NEXUS PULSE · итоги недели", "icon_url": LOGO},
            "timestamp": iso_z(self.now),
        }]}
        try:
            msg = self.send(self.ch["announcements"], body)
            if not self.dry:
                self.mark("digest", msg["id"])
                if members:
                    self.mark("members", members)
            self.log.append("+ weekly digest")
        except DiscordError as e:
            self.log.append(f"[warn] digest failed ({e.code}): {e.body[:200]}")

    def run(self) -> int:
        self.gamenight()
        self.poll()
        self.digest()
        if self.changed and not self.dry:
            fresh = read_json(STATE_FILE, {})  # feeds may have written meanwhile
            fresh["weekly"] = self.w
            STATE_FILE.write_text(json.dumps(fresh, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        for line in self.log:
            print(line)
        print(f"weekly: {self.week} · {len(self.log)} actions")
        return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--now", default="", help="override time (MSK), e.g. 2026-09-27T19:30")
    a = ap.parse_args()
    now = datetime.fromisoformat(a.now).replace(tzinfo=MSK) if a.now else datetime.now(MSK)
    return Weekly(now, a.dry_run).run()


if __name__ == "__main__":
    raise SystemExit(main())
