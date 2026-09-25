#!/usr/bin/env python3
"""NEXUS PULSE Discord server setup — idempotent, safe to re-run.

  python scripts/discord_setup.py            # apply
  python scripts/discord_setup.py --check    # only report permissions / state

What it does (only what the bot's permissions allow; missing ones are reported):
  * categories + channels (edits existing ones by ID, never deletes)
  * read-only auto-feed channels in «📡 ЛЕНТА»
  * game roles + notification roles, reaction role-picker in #🎭роли
  * rules / welcome (pinned) / intro messages (bot's own messages are edited, not duplicated)
  * permanent invite
  * with MANAGE_GUILD: description, system/rules channels, Community, Onboarding,
    Welcome Screen, widget
Never prints the bot token.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from discord_api import GUILD_ID, PERM, Bot, DiscordError  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CHANNELS_FILE = ROOT / "data" / "discord_channels.json"
MSK = timezone(timedelta(hours=3), name="MSK")
SITE = "https://derzko435.github.io/nexus-pulse/"
LOGO = SITE + "assets/nexus-pulse-icon.png"
BRAND = 0x8B5CFF
MARK = "NEXUS PULSE"  # footer marker for bot-owned messages
CLIENT_ID = "1552769358156140565"

# ---------------------------------------------------------------- spec
CATEGORIES = [
    # key, known id, name
    ("cat_info", "1552771361934540923", "📢 ИНФО"),
    ("cat_feed", "1552778940924563540", "📡 ЛЕНТА"),  # was the stray duplicate «ИГРЫ» category
    ("cat_chat", "1552771365151445122", "💬 ЧАТ"),
    ("cat_games", "1552771369534488577", "🎮 ИГРЫ"),
    ("cat_voice", "1552771372218982555", "🔊 ГОЛОС"),
]

RO = "readonly"   # @everyone can read + react, cannot write
PRIVATE = "private"  # staff only
# key, known id, name, category key, topic, mode, type (0 text / 2 voice)
CHANNELS = [
    ("rules", "1552771375276625960", "📜правила", "cat_info", "Правила сервера NEXUS PULSE — коротко и по-человечески", RO, 0),
    ("announcements", "1552771380532093080", "📢анонсы", "cat_info", "Важные анонсы сервера и сайта NEXUS PULSE", RO, 0),
    ("roles", None, "🎭роли", "cat_info", "Выбери игры и уведомления — нажми на реакцию под сообщением", RO, 0),
    ("giveaways", None, "🎉розыгрыши", "cat_info", "Розыгрыши и ивенты сервера. Включи 🔔 Раздачи в #🎭роли", RO, 0),
    ("guides", "1552736872860749845", "📚гайды", "cat_info", "Гайды и полезные ссылки · больше на derzko435.github.io/nexus-pulse", None, 0),
    ("mod", None, "🛡модерация", "cat_info", "Канал для команды сервера", PRIVATE, 0),
    # bot-visible staff channel: Discord Community updates, safety alerts, AutoMod alerts
    ("staff", None, "🔒служебное", "cat_info", "Служебный канал: уведомления Discord, безопасность и автомодерация", PRIVATE, 0),

    # the original «новости» channel (only had a bot post) became the news feed
    ("feed_news", "1552736799762415776", "📰новости", "cat_feed", "Игровые новости дня — автоматически с сайта NEXUS PULSE", RO, 0),
    ("feed_deals", "1552736900630974555", "💸скидки", "cat_feed", "Лучшие скидки Steam (от −50%) — автоматически. Роль 🔔 Скидки в #🎭роли", RO, 0),
    ("feed_freebies", None, "🎁раздачи", "cat_feed", "Бесплатные игры Epic / Steam / GOG — как только появляются. Роль 🔔 Раздачи в #🎭роли", RO, 0),
    ("feed_esports", None, "🏆киберспорт", "cat_feed", "Топ-матчи CS2 / Dota 2 / Valorant / LoL: расписание, лайвы, результаты. Роль 🔔 Матчи", RO, 0),
    ("feed_patches", None, "🛠патчи", "cat_feed", "Свежие патчи и обновления игр", RO, 0),
    ("feed_videos", None, "🎬видео", "cat_feed", "Трейлеры и игровые видео", RO, 0),
    ("feed_releases", None, "📅релизы", "cat_feed", "Календарь релизов на неделю", RO, 0),
    ("feed_gotd", None, "🎮игра-дня", "cat_feed", "Каждый день — одна игра, в которую стоит залипнуть", RO, 0),

    ("welcome", "1552771388262064250", "👋приветствие", "cat_chat", "Добро пожаловать на NEXUS PULSE! Скажи привет 👋", None, 0),
    ("general", "1552735502711652465", "💬общий", "cat_chat", "Основной чат сообщества", None, 0),
    ("intro", None, "🤝знакомства", "cat_chat", "Расскажи о себе: ник, игры, ранг, прайм-тайм", None, 0),
    ("clips", "1552736952325898330", "📸скриншоты-клипы", "cat_chat", "Лучшие моменты: скрины, клипы, эйсы и фейлы", None, 0),
    ("memes", "1552771394301993183", "😂мемы", "cat_chat", "Мемы и флуд по-доброму", None, 0),
    ("ideas", "1552771399511449630", "💡предложения", "cat_chat", "Идеи для сайта и сервера", None, 0),

    ("lfg", "1552736838555402431", "🔎поиск-тимы", "cat_games", "Ищешь пати? Пиши: игра + ранг + платформа + время (МСК)", None, 0),
    ("cs2", "1552771404729159782", "💣cs2", "cat_games", "Counter-Strike 2", None, 0),
    ("valorant", "1552771412337631373", "🎯valorant", "cat_games", "Valorant", None, 0),
    ("dota2", "1552771415382695969", "🐉dota2", "cat_games", "Dota 2", None, 0),
    ("other_games", "1552771418280955904", "🕹другие-игры", "cat_games", "Minecraft, Fortnite, Apex, GTA, Rust и всё остальное", None, 0),

    ("voice_create", None, "➕ Создать комнату", "cat_voice", None, None, 2),  # bot: personal rooms
    ("voice_lobby", "1552735502711652466", "🔊голос-лобби", "cat_voice", None, None, 2),
    ("voice_gamenight", None, "🔊 Игровой вечер", "cat_voice", None, None, 2),  # weekly event
    ("voice_duo", "1552771422655614976", "🎧дуо", "cat_voice", None, None, 2),
    ("voice_squad", "1552771432642248795", "👥сквад", "cat_voice", None, None, 2),
    ("voice_raid", "1552771437562175610", "⚔рейд", "cat_voice", None, None, 2),
    ("voice_afk", "1552771440535797874", "🎵музыка-afk", "cat_voice", None, None, 2),
]

FEED_KEYS = [c[0] for c in CHANNELS if c[0].startswith("feed_")]

# key, name, color, emoji (reaction picker), onboarding channel keys
GAME_ROLES = [
    ("role_cs2", "CS2", 0xF5A623, "💣", ["cs2", "feed_esports"]),
    ("role_valorant", "Valorant", 0xFF4655, "🎯", ["valorant", "feed_esports"]),
    ("role_dota2", "Dota 2", 0xB8382B, "🐉", ["dota2", "feed_esports"]),
    ("role_lol", "League of Legends", 0xC89B3C, "🧙", ["other_games"]),
    ("role_fortnite", "Fortnite", 0x9D4DFF, "🦙", ["other_games"]),
    ("role_minecraft", "Minecraft", 0x5DBB63, "🧱", ["other_games"]),
    ("role_apex", "Apex Legends", 0xE0533D, "🦅", ["other_games"]),
    ("role_pubg", "PUBG", 0xF2C94C, "🍳", ["other_games"]),
    ("role_gta", "GTA", 0x2ECC71, "🚗", ["other_games"]),
    ("role_rust", "Rust", 0xCE422B, "🪓", ["other_games"]),
]
NOTIFY_ROLES = [
    ("role_n_freebies", "🔔 Раздачи", 0x3DFF9A, "🎁", ["feed_freebies"]),
    ("role_n_deals", "🔔 Скидки", 0x00D1FF, "💸", ["feed_deals"]),
    ("role_n_matches", "🔔 Матчи", 0xFFB020, "🏆", ["feed_esports"]),
]

# XP levels (bot): min level → role; only the highest reached role is kept
LEVEL_ROLES = [
    ("role_lvl_1", "Новичок", 0x9AA4B2, 1),
    ("role_lvl_5", "Игрок", 0x3DFF9A, 5),
    ("role_lvl_15", "Ветеран", 0x00D1FF, 15),
    ("role_lvl_30", "Легенда", 0xFFB020, 30),
]

DESCRIPTION = ("Игровое комьюнити NEXUS PULSE: поиск тимы, новости, халява, скидки и "
               "киберспорт — всё автоматически каждый день. CS2 · Dota 2 · Valorant и не только.")


def now_iso() -> str:
    return datetime.now(MSK).isoformat(timespec="seconds")


def norm(name: str) -> str:
    """channel name without emoji / punctuation → for matching renamed channels"""
    return re.sub(r"[^0-9a-zа-яё-]", "", (name or "").lower()).strip("-")


class Setup:
    def __init__(self, bot: Bot, check_only: bool = False, announce: bool = False):
        self.bot = bot
        self.announce = announce
        self.check_only = check_only
        self.notes: list[str] = []
        self.missing: set[str] = set()
        self.saved = json.loads(CHANNELS_FILE.read_text(encoding="utf-8")) if CHANNELS_FILE.is_file() else {}
        self.ids: dict[str, str] = {}
        self.role_ids: dict[str, str] = {}

    def log(self, msg: str) -> None:
        print(msg, flush=True)

    def api(self, *a, **kw):
        return self.bot.api(*a, **kw)

    # ------------------------------------------------ permissions
    def load_perms(self) -> None:
        self.perms, info = self.bot.guild_permissions()
        self.me = info["me"]
        self.member = info["member"]
        self.roles = info["roles"]
        self.bot_role = next((r for r in self.roles if r.get("managed") and r.get("tags", {}).get("bot_id") == self.me["id"]), None)
        want = ["MANAGE_CHANNELS", "MANAGE_ROLES", "MANAGE_GUILD", "MANAGE_WEBHOOKS", "MANAGE_EVENTS",
                "CREATE_EVENTS", "SEND_MESSAGES", "EMBED_LINKS", "MANAGE_MESSAGES", "ADD_REACTIONS",
                "CREATE_INSTANT_INVITE", "MENTION_EVERYONE"]
        have = {k: bool(self.perms & PERM[k]) for k in want}
        self.have = have
        self.log("Bot permissions: " + ", ".join(f"{k}={'yes' if v else 'NO'}" for k, v in have.items()))
        have["PIN_MESSAGES"] = bool(self.perms & PERM["PIN_MESSAGES"])
        have["MOVE_MEMBERS"] = bool(self.perms & PERM["MOVE_MEMBERS"])
        have["MODERATE_MEMBERS"] = bool(self.perms & PERM["MODERATE_MEMBERS"])
        for k in ("MANAGE_GUILD", "MANAGE_WEBHOOKS", "MANAGE_EVENTS", "PIN_MESSAGES", "MOVE_MEMBERS", "MODERATE_MEMBERS"):
            if not have[k]:
                self.missing.add(k)

    def can(self, perm: str) -> bool:
        return bool(self.perms & PERM[perm])

    # ------------------------------------------------ structure
    def ensure_structure(self) -> None:
        chans = self.api("GET", f"/guilds/{GUILD_ID}/channels")
        by_id = {c["id"]: c for c in chans}
        cats = {}
        for pos, (key, known, name) in enumerate(CATEGORIES):
            cid = self.saved.get(key) or known
            ch = by_id.get(cid) if cid else None
            if not ch:
                ch = next((c for c in chans if c["type"] == 4 and norm(c["name"]) == norm(name)), None)
            if not ch:
                if self.check_only:
                    self.log(f"[check] would create category {name}")
                    continue
                ch = self.api("POST", f"/guilds/{GUILD_ID}/channels", {"name": name, "type": 4}, reason="NEXUS PULSE setup")
                self.log(f"+ category {name}")
                by_id[ch["id"]] = ch
                chans.append(ch)
            elif ch["name"] != name and not self.check_only:
                self.api("PATCH", f"/channels/{ch['id']}", {"name": name}, reason="NEXUS PULSE setup")
                self.log(f"~ category {ch['name']} → {name}")
            cats[key] = ch["id"]
            self.ids[key] = ch["id"]

        claimed: set[str] = set()
        for key, known, name, cat_key, topic, mode, ctype in CHANNELS:
            cid = self.saved.get(key) or known
            ch = by_id.get(cid) if cid and cid not in claimed else None
            if not ch:
                ch = next((c for c in chans if c["type"] == ctype and c["id"] not in claimed
                           and norm(c["name"]) == norm(name)), None)
            parent = cats.get(cat_key)
            if not ch:
                if self.check_only:
                    self.log(f"[check] would create #{name}")
                    continue
                body = {"name": name, "type": ctype, "parent_id": parent}
                if topic:
                    body["topic"] = topic
                ch = self.api("POST", f"/guilds/{GUILD_ID}/channels", body, reason="NEXUS PULSE setup")
                self.log(f"+ #{name}")
                by_id[ch["id"]] = ch
                chans.append(ch)
            else:
                patch = {}
                if ch.get("name") != name:
                    patch["name"] = name
                if parent and ch.get("parent_id") != parent:
                    patch["parent_id"] = parent
                if topic and ctype == 0 and (ch.get("topic") or "") != topic:
                    patch["topic"] = topic
                if patch and not self.check_only:
                    self.api("PATCH", f"/channels/{ch['id']}", patch, reason="NEXUS PULSE setup")
                    self.log(f"~ #{ch['name']} → {', '.join(f'{k}' for k in patch)}")
            self.ids[key] = ch["id"]
            claimed.add(ch["id"])
            if mode and not self.check_only:
                self.ensure_overwrites(ch, mode)

        # order: categories, then channels inside each category by spec order
        if not self.check_only:
            positions = []
            for i, (key, _k, _n) in enumerate(CATEGORIES):
                if key in self.ids:
                    positions.append({"id": self.ids[key], "position": i})
            per_cat: dict[str, int] = {}
            for key, _k, _n, cat_key, _t, _m, _ty in CHANNELS:
                if key in self.ids:
                    per_cat[cat_key] = per_cat.get(cat_key, -1) + 1
                    positions.append({"id": self.ids[key], "position": per_cat[cat_key]})
            fresh = {c["id"]: c for c in self.api("GET", f"/guilds/{GUILD_ID}/channels")}
            positions = [p for p in positions if fresh.get(p["id"], {}).get("position") != p["position"]]
            if positions:
                try:
                    self.api("PATCH", f"/guilds/{GUILD_ID}/channels", positions, reason="NEXUS PULSE order")  # type: ignore[arg-type]
                    self.log(f"~ reordered {len(positions)} channels")
                except DiscordError as e:
                    self.notes.append(f"reorder failed: {e.code}")

    def ensure_overwrites(self, ch: dict, mode: str) -> None:
        everyone = GUILD_ID
        allow_mask = self.perms  # can only allow/deny what we have
        if mode == RO:
            e_allow = PERM["VIEW_CHANNEL"] | PERM["READ_MESSAGE_HISTORY"] | PERM["ADD_REACTIONS"]
            e_deny = (PERM["SEND_MESSAGES"] | PERM["CREATE_PUBLIC_THREADS"] | PERM["CREATE_PRIVATE_THREADS"]
                      | PERM["SEND_MESSAGES_IN_THREADS"] | PERM["SEND_POLLS"])
        else:  # PRIVATE
            e_allow = 0
            e_deny = PERM["VIEW_CHANNEL"]
        b_allow = (PERM["VIEW_CHANNEL"] | PERM["SEND_MESSAGES"] | PERM["EMBED_LINKS"] | PERM["ATTACH_FILES"]
                   | PERM["READ_MESSAGE_HISTORY"] | PERM["ADD_REACTIONS"] | PERM["MENTION_EVERYONE"])
        wanted = {}
        if self.bot_role:  # bot first, so hiding a channel from @everyone never locks the bot out
            wanted[self.bot_role["id"]] = (b_allow & allow_mask, 0)
        wanted[everyone] = (e_allow & allow_mask, e_deny & allow_mask)
        if mode == PRIVATE:
            for r in self.roles:
                if r["name"] in ("Админ", "Модератор"):
                    wanted[r["id"]] = ((PERM["VIEW_CHANNEL"] | PERM["SEND_MESSAGES"] | PERM["READ_MESSAGE_HISTORY"]) & allow_mask, 0)
        current = {o["id"]: (int(o["allow"]), int(o["deny"])) for o in ch.get("permission_overwrites") or []}
        for oid, (allow, deny) in wanted.items():
            if current.get(oid) == (allow, deny):
                continue
            try:
                self.api("PUT", f"/channels/{ch['id']}/permissions/{oid}", {"type": 0, "allow": str(allow), "deny": str(deny)}, reason="NEXUS PULSE read-only feed")
            except DiscordError as e:
                if mode == PRIVATE and e.code == 403 and int(current.get(everyone, (0, 0))[1]) & PERM["VIEW_CHANNEL"]:
                    self.notes.append(f"#{ch['name']} is private (hidden from @everyone); bot has no access there — OK")
                    break
                self.notes.append(f"overwrite #{ch['name']} failed {e.code}")

    # ------------------------------------------------ roles
    def ensure_roles(self) -> None:
        roles = self.api("GET", f"/guilds/{GUILD_ID}/roles")
        by_name = {r["name"]: r for r in roles}
        by_id = {r["id"]: r for r in roles}
        for key, name, color, _emoji, _ch in GAME_ROLES + NOTIFY_ROLES:
            r = by_id.get(self.saved.get(key, "")) or by_name.get(name)
            if not r:
                if self.check_only or not self.can("MANAGE_ROLES"):
                    self.log(f"[skip] role {name}")
                    continue
                r = self.api("POST", f"/guilds/{GUILD_ID}/roles", {"name": name, "color": color, "hoist": False, "mentionable": False, "permissions": "0"}, reason="NEXUS PULSE roles")
                self.log(f"+ role {name}")
            elif (r["name"] != name or r["color"] != color) and not self.check_only:
                try:
                    self.api("PATCH", f"/guilds/{GUILD_ID}/roles/{r['id']}", {"name": name, "color": color}, reason="NEXUS PULSE roles")
                except DiscordError as e:
                    self.notes.append(f"role {name} edit failed {e.code}")
            self.role_ids[key] = r["id"]
            self.ids[key] = r["id"]
        for key, name, color, _lvl in LEVEL_ROLES:
            r = by_id.get(self.saved.get(key, "")) or by_name.get(name)
            if not r:
                if self.check_only or not self.can("MANAGE_ROLES"):
                    self.log(f"[skip] role {name}")
                    continue
                r = self.api("POST", f"/guilds/{GUILD_ID}/roles", {"name": name, "color": color, "hoist": False, "mentionable": False, "permissions": "0"}, reason="NEXUS PULSE levels")
                self.log(f"+ role {name}")
            self.role_ids[key] = r["id"]
            self.ids[key] = r["id"]

    # ------------------------------------------------ messages
    def bot_messages(self, channel_id: str, limit: int = 50) -> list[dict]:
        msgs = self.api("GET", f"/channels/{channel_id}/messages?limit={limit}") or []
        return [m for m in msgs if m["author"]["id"] == self.me["id"]]

    def upsert(self, key: str, channel_id: str, embeds: list[dict], content: str = "", pin: bool = False,
               legacy_title: str | None = None, reactions: list[str] | None = None) -> str | None:
        """Create or edit the bot's own message identified by footer marker `key`."""
        tag = f"{MARK} · {key}"
        for e in embeds:
            e.setdefault("footer", {"text": tag, "icon_url": LOGO})
        embeds[-1]["footer"] = {"text": tag, "icon_url": LOGO}
        body = {"content": content, "embeds": embeds, "allowed_mentions": {"parse": []}}
        mine = self.bot_messages(channel_id)
        msg = next((m for m in mine if any((e.get("footer") or {}).get("text") == tag for e in m.get("embeds") or [])), None)
        if not msg and legacy_title:
            msg = next((m for m in mine if any(e.get("title") == legacy_title for e in m.get("embeds") or [])), None)
        if self.check_only:
            self.log(f"[check] message {key}: {'exists' if msg else 'missing'}")
            return msg["id"] if msg else None
        if msg:
            self.api("PATCH", f"/channels/{channel_id}/messages/{msg['id']}", body)
            mid = msg["id"]
        else:
            mid = self.api("POST", f"/channels/{channel_id}/messages", body)["id"]
            self.log(f"+ message {key}")
        if pin and not (msg or {}).get("pinned"):
            try:
                self.api("PUT", f"/channels/{channel_id}/pins/{mid}", reason="NEXUS PULSE welcome")
            except DiscordError as e:
                self.notes.append(f"pin {key} failed {e.code}")
        for emo in reactions or []:
            try:
                from urllib.parse import quote
                self.api("PUT", f"/channels/{channel_id}/messages/{mid}/reactions/{quote(emo)}/@me")
                time.sleep(0.3)
            except DiscordError as e:
                self.notes.append(f"reaction {emo} failed {e.code}")
        return mid

    def ch(self, key: str) -> str:
        return f"<#{self.ids[key]}>"

    def ensure_messages(self) -> None:
        if self.check_only:
            return
        invite = self.ids.get("invite_url") or "https://discord.gg/c7UHcM2UR"
        rules = [
            "**1. Уважай других.** Без оскорблений, травли, токсика и дискриминации.",
            "**2. Без спама и рекламы.** Никаких чужих инвайтов, ссылок-приманок и флуда упоминаниями.",
            "**3. Пиши по теме канала.** Поиск тимы — в " + self.ch("lfg") + ", мемы — в " + self.ch("memes") + ".",
            "**4. Без читов, скама и пиратки.** Продажа аккаунтов и буст — мимо.",
            "**5. 18+ контенту здесь не место.** Держим сервер чистым.",
            "**6. Модераторы — тоже игроки.** Их решение финальное, спорные моменты — в личку админам.",
        ]
        self.upsert("rules", self.ids["rules"], [{
            "title": "📜 Правила NEXUS PULSE",
            "description": "Коротко: играем, общаемся и помогаем друг другу 🤝\n\n" + "\n".join(rules)
                           + "\n\nНарушения → предупреждение → мут → бан. Хорошей игры! 🎮",
            "color": BRAND,
        }], legacy_title="⚡ Правила NEXUS PULSE")

        welcome = (
            "Мы — игровое комьюнити сайта **NEXUS PULSE**. Здесь собирают пати, делятся клипами и "
            "первыми узнают о раздачах, скидках и больших матчах.\n\n"
            f"**С чего начать**\n"
            f"1️⃣ Прочитай {self.ch('rules')}\n"
            f"2️⃣ Выбери игры и уведомления в {self.ch('roles')}\n"
            f"3️⃣ Представься в {self.ch('intro')}\n"
            f"4️⃣ Ищи тиму в {self.ch('lfg')} и заходи в голосовые каналы\n\n"
            f"**Автолента 📡**\n"
            f"{self.ch('feed_freebies')} бесплатные игры · {self.ch('feed_deals')} скидки · "
            f"{self.ch('feed_esports')} матчи · {self.ch('feed_news')} новости · {self.ch('feed_gotd')} игра дня\n\n"
            f"🌐 Сайт: {SITE}\n"
            f"🔗 Позови друзей: {invite}"
        )
        self.upsert("welcome", self.ids["welcome"], [{
            "title": "👋 Добро пожаловать на NEXUS PULSE!",
            "description": welcome, "url": SITE, "color": BRAND,
            "thumbnail": {"url": LOGO},
        }], pin=True, legacy_title="Добро пожаловать в NEXUS PULSE")

        if self.role_ids:
            games = "\n".join(f"{emo} — <@&{self.role_ids[k]}>" for k, _n, _c, emo, _ch in GAME_ROLES if k in self.role_ids)
            self.upsert("roles-games", self.ids["roles"], [{
                "title": "🎮 Во что играешь?",
                "description": "Нажми на реакцию — получишь роль игры (так проще найти тиммейтов). "
                               "Убери реакцию — роль снимется.\n\n" + games
                               + "\n\n_Роли выдаются автоматически в течение нескольких минут._",
                "color": 0x00F5FF,
            }], reactions=[emo for k, _n, _c, emo, _ch in GAME_ROLES if k in self.role_ids])
            notes = "\n".join(f"{emo} — <@&{self.role_ids[k]}>" for k, _n, _c, emo, _ch in NOTIFY_ROLES if k in self.role_ids)
            self.upsert("roles-notify", self.ids["roles"], [{
                "title": "🔔 Какие уведомления нужны?",
                "description": "Пингуем редко и только по делу: новая бесплатная игра, мощная скидка, "
                               "лайв большого матча.\n\n" + notes
                               + "\n\n_Роли выдаются автоматически в течение нескольких минут._",
                "color": 0xFFB020,
            }], reactions=[emo for k, _n, _c, emo, _ch in NOTIFY_ROLES if k in self.role_ids])

        self.upsert("intro", self.ids["intro"], [{
            "title": "🤝 Давай знакомиться!",
            "description": "Скопируй и заполни:\n```\nНик:\nИгры:\nРанг:\nПрайм-тайм (МСК):\nМикрофон: да/нет\nО себе:\n```"
                           f"Нашёл своих? Зови в голос и ищи ещё людей в {self.ch('lfg')} 🎧",
            "color": 0x3DFF9A,
        }], pin=True)

        self.upsert("giveaways", self.ids["giveaways"], [{
            "title": "🎉 Розыгрыши и ивенты",
            "description": "Здесь будут объявления о розыгрышах, турнирах и ивентах сервера — с понятными "
                           "условиями и сроками.\n\n"
                           f"Пока ждёшь — каждый день забирай бесплатные игры в {self.ch('feed_freebies')} "
                           f"и включи роль <@&{self.role_ids.get('role_n_freebies', '0')}> в {self.ch('roles')}.",
            "color": 0xFF5EA8,
        }])

        self.upsert("lfg-howto", self.ids["lfg"], [{
            "title": "🔎 Как быстро найти тиму",
            "description": "**Самый быстрый способ — команда `/лфг`**: выбери игру, ранг, режим и время — "
                           "бот оформит карточку с кнопкой «✋ Я в деле», и откликнувшиеся сразу появятся в списке.\n\n"
                           "Можно и просто сообщением:\n**игра · ранг · платформа · время (МСК) · микрофон**\n"
                           "Пример: `CS2 · Premier 12k · PC · 21:00–00:00 · мик есть`\n\n"
                           f"Карточку можно собрать и на сайте: {SITE}#lfg\n"
                           "Нашлись? Жми **➕ Создать комнату** — получите свой голосовой канал.",
            "color": 0x8B5CFF,
        }], pin=True)

        # one-time server-upgrade announcement (no mass mentions)
        self.upsert("upgrade-2026-09", self.ids["announcements"], [{
            "title": "🚀 Сервер прокачан!",
            "description": (
                "Что нового:\n"
                f"• 📡 **Автолента** — {self.ch('feed_news')}, {self.ch('feed_deals')}, {self.ch('feed_freebies')}, "
                f"{self.ch('feed_esports')}, {self.ch('feed_patches')}, {self.ch('feed_videos')}, "
                f"{self.ch('feed_releases')}, {self.ch('feed_gotd')} — обновляются сами, каждый день\n"
                f"• 🎭 **Роли игр и уведомлений** — выбери в {self.ch('roles')}\n"
                f"• 🤝 {self.ch('intro')} и 📸 {self.ch('clips')} — знакомься и хвастайся моментами\n"
                "• 🏆 Большие матчи появляются в **Событиях** сервера\n\n"
                f"Зови друзей: {invite}\nСайт: {SITE}"
            ),
            "url": SITE, "color": BRAND, "thumbnail": {"url": LOGO},
        }])

    def announce_bot(self) -> None:
        """One-time «new features» post in #анонсы (created only with --announce-bot, then just kept current)."""
        if self.check_only:
            return
        key = "bot-2026-09"
        exists = any(any((e.get("footer") or {}).get("text") == f"{MARK} · {key}" for e in m.get("embeds") or [])
                     for m in self.bot_messages(self.ids["announcements"]))
        if not exists and not self.announce:
            return
        self.upsert(key, self.ids["announcements"], [{
            "title": "🤖 У сервера появился свой бот",
            "description": (
                "Теперь всё работает само, 24/7:\n"
                f"• 🔎 **`/лфг`** — карточка поиска тимы в {self.ch('lfg')} с кнопкой «✋ Я в деле»\n"
                "• 💰 **`/цена`**, **`/скидки`**, **`/раздачи`**, **`/матчи`** — всё с сайта прямо в чате\n"
                "• 🖥 **`/сборка`** и 📡 **`/пинг`** — конструктор ПК и карта пинга\n"
                "• 🎖 **Уровни за общение**: Новичок → Игрок → Ветеран → Легенда · **`/ранг`**, **`/топ`**\n"
                "• 🔊 Зайди в **➕ Создать комнату** — получишь личный голосовой канал\n"
                "• 🗳 По пятницам — опрос «Во что играем в выходные?», в субботу в 20:00 — **Игровой вечер** в Событиях, "
                "по воскресеньям — «Итоги недели»\n"
                "• 🛡 Автомодерация: без спама, скама и чужой рекламы\n\n"
                "Все команды — **`/помощь`**. Хорошей игры! 🎮"
            ),
            "url": SITE, "color": BRAND, "thumbnail": {"url": LOGO},
        }])

    def cleanup_duplicate_alerts(self) -> None:
        """Remove repeated identical bot price alerts in #анонсы (bot's own messages only, keep newest)."""
        seen = set()
        for m in self.bot_messages(self.ids["announcements"], 100):  # newest first
            embeds = m.get("embeds") or []
            if not embeds or not (embeds[0].get("footer") or {}).get("text", "").startswith("NEXUS PULSE · price alert"):
                continue
            sig = (embeds[0].get("title"), embeds[0].get("description"))
            if sig in seen and not self.check_only:
                try:
                    self.api("DELETE", f"/channels/{self.ids['announcements']}/messages/{m['id']}", reason="duplicate bot alert")
                    self.log(f"- duplicate bot alert {m['id']}")
                except DiscordError as e:
                    self.notes.append(f"delete dup failed {e.code}")
            seen.add(sig)

    # ------------------------------------------------ invite
    def ensure_invite(self) -> None:
        code = self.saved.get("invite_code")
        if code:
            try:
                inv = self.api("GET", f"/invites/{code}")
                if inv and not inv.get("expires_at"):
                    self.ids["invite_code"] = code
                    self.ids["invite_url"] = f"https://discord.gg/{code}"
                    return
            except DiscordError:
                pass
        if self.check_only or not self.can("CREATE_INSTANT_INVITE"):
            return
        inv = self.api("POST", f"/channels/{self.ids['welcome']}/invites", {"max_age": 0, "max_uses": 0, "unique": False, "temporary": False}, reason="NEXUS PULSE permanent invite")
        self.ids["invite_code"] = inv["code"]
        self.ids["invite_url"] = f"https://discord.gg/{inv['code']}"
        self.log(f"invite: https://discord.gg/{inv['code']} (permanent)")

    # ------------------------------------------------ guild-level (MANAGE_GUILD)
    def ensure_guild_settings(self) -> None:
        if not self.can("MANAGE_GUILD"):
            self.notes.append("MANAGE_GUILD missing → skipped: description, system/rules channel, Community, Onboarding, Welcome Screen, widget")
            return
        if self.check_only:
            return
        g = self.api("GET", f"/guilds/{GUILD_ID}")
        patch = {
            "description": DESCRIPTION,
            "system_channel_id": self.ids["welcome"],
            "preferred_locale": "ru",
        }
        if g.get("verification_level", 0) < 1:
            patch["verification_level"] = 1
        if g.get("explicit_content_filter", 0) < 2:
            patch["explicit_content_filter"] = 2
        # Community updates + safety alerts go to a staff channel the bot can see:
        # #🔒служебное (created by the bot), or #🛡модерация if the bot has access there
        staff = None
        for key in ("staff", "mod"):
            if not self.ids.get(key):
                continue
            try:
                self.api("GET", f"/channels/{self.ids[key]}")
                staff = self.ids[key]
                break
            except DiscordError:
                continue
        feats = list(g.get("features") or [])
        community = "COMMUNITY" in feats
        admin = self.can("ADMINISTRATOR")
        patch["rules_channel_id"] = self.ids["rules"]
        if staff:
            patch["safety_alerts_channel_id"] = staff
            if community or admin:
                patch["public_updates_channel_id"] = staff  # only settable on Community servers
        if not community and admin and staff:
            feats.append("COMMUNITY")
            patch["features"] = feats
        elif not community:
            # Discord lets only ADMINISTRATOR turn Community on; the owner does it once in
            # Server Settings → Enable Community. The box routine notices it and finishes the setup.
            self.notes.append("Community is off: enabling it needs Administrator — owner: Server Settings → "
                              "Enable Community (rules: #📜правила, updates: #🔒служебное); the rest is automatic")
        mod_ok = community or ("features" in patch)
        try:
            self.api("PATCH", f"/guilds/{GUILD_ID}", patch, reason="NEXUS PULSE community")
            self.log("~ guild: description, system/rules/safety channels" + (", Community" if mod_ok else ""))
        except DiscordError as e:
            self.notes.append(f"guild patch failed {e.code}: {e.body[:200]}")
            patch.pop("features", None)
            try:
                self.api("PATCH", f"/guilds/{GUILD_ID}", patch, reason="NEXUS PULSE settings")
            except DiscordError as e2:
                self.notes.append(f"guild patch (no community) failed {e2.code}")
        # widget
        try:
            self.api("PATCH", f"/guilds/{GUILD_ID}/widget", {"enabled": True, "channel_id": self.ids["welcome"]}, reason="site widget")
            self.ids["widgetEnabled"] = True
            self.log("~ widget enabled")
        except DiscordError as e:
            self.notes.append(f"widget failed {e.code}")
        if not mod_ok:
            return  # welcome screen + onboarding need Community
        # welcome screen (Community only)
        try:
            self.api("PATCH", f"/guilds/{GUILD_ID}/welcome-screen", {
                "enabled": True,
                "description": "Игровое комьюнити: пати, халява, скидки и киберспорт каждый день",
                "welcome_channels": [
                    {"channel_id": self.ids["roles"], "description": "Выбери свои игры и уведомления", "emoji_name": "🎭"},
                    {"channel_id": self.ids["lfg"], "description": "Найди тиму на вечер", "emoji_name": "🔎"},
                    {"channel_id": self.ids["feed_freebies"], "description": "Бесплатные игры каждый день", "emoji_name": "🎁"},
                    {"channel_id": self.ids["feed_esports"], "description": "Большие матчи и лайвы", "emoji_name": "🏆"},
                    {"channel_id": self.ids["general"], "description": "Общий чат — скажи привет", "emoji_name": "💬"},
                ],
            }, reason="welcome screen")
            self.log("~ welcome screen")
        except DiscordError as e:
            self.notes.append(f"welcome screen failed {e.code}: {e.body[:160]}")
        self.ensure_onboarding()

    def ensure_onboarding(self) -> None:
        try:
            cur = self.api("GET", f"/guilds/{GUILD_ID}/onboarding")
        except DiscordError as e:
            self.notes.append(f"onboarding get failed {e.code}")
            return
        existing = {p["title"]: p for p in cur.get("prompts") or []}
        seq = [int(time.time() * 1000)]

        def snow() -> str:
            seq[0] += 1
            return str((seq[0] - 1420070400000) << 22)

        def opt(prompt: dict | None, title: str, emoji: str, desc: str, role_key: str, ch_keys: list[str]) -> dict:
            old = next((o for o in (prompt or {}).get("options") or [] if o.get("title") == title), None)
            return {
                "id": old["id"] if old else snow(),
                "title": title, "description": desc,
                "emoji": {"name": emoji},
                "role_ids": [self.role_ids[role_key]] if role_key in self.role_ids else [],
                "channel_ids": [self.ids[k] for k in ch_keys if k in self.ids],
            }

        p1t, p2t = "Во что играешь?", "Какие уведомления нужны?"
        p1, p2 = existing.get(p1t), existing.get(p2t)
        prompts = [
            {"id": p1["id"] if p1 else snow(), "type": 0, "title": p1t, "single_select": False, "required": False, "in_onboarding": True,
             "options": [opt(p1, n, e, "Роль и каналы по игре", k, chs) for k, n, _c, e, chs in GAME_ROLES]},
            {"id": p2["id"] if p2 else snow(), "type": 0, "title": p2t, "single_select": False, "required": False, "in_onboarding": True,
             "options": [opt(p2, n.replace("🔔 ", ""), e, "Пинг только по важному", k, chs) for k, n, _c, e, chs in NOTIFY_ROLES]},
        ]
        defaults = [self.ids[k] for k in ("rules", "announcements", "welcome", "general", "intro", "clips", "memes",
                                         "ideas", "lfg", "feed_news", "feed_freebies", "feed_deals", "feed_gotd") if k in self.ids]
        try:
            self.api("PUT", f"/guilds/{GUILD_ID}/onboarding", {"prompts": prompts, "default_channel_ids": defaults, "enabled": True, "mode": 0}, reason="NEXUS PULSE onboarding")
            self.log("~ onboarding enabled")
        except DiscordError as e:
            self.notes.append(f"onboarding failed {e.code}: {e.body[:300]}")

    # ------------------------------------------------ save
    def save(self) -> None:
        out = dict(self.saved)
        out.update({k: (v if isinstance(v, bool) else str(v)) for k, v in self.ids.items()})
        out["guild_id"] = GUILD_ID
        # legacy keys used by older scripts / site
        out["channel_lfg"] = self.ids.get("lfg", out.get("channel_lfg"))
        out["channel_announcements"] = self.ids.get("announcements", out.get("channel_announcements"))
        out["channel_lfg_name"] = "🔎поиск-тимы"
        out["channel_announcements_name"] = "📢анонсы"
        out.pop("category_games", None)
        out.pop("server_news", None)
        out.setdefault("feedMode", "bot")
        out["feeds"] = {k.replace("feed_", ""): self.ids[k] for k in FEED_KEYS if k in self.ids}
        out["reactionRoles"] = {e: self.role_ids[k] for k, _n, _c, e, _ch in GAME_ROLES + NOTIFY_ROLES if k in self.role_ids}
        out["levelRoles"] = {str(lvl): self.role_ids[k] for k, _n, _c, lvl in LEVEL_ROLES if k in self.role_ids}
        out["updatedAt"] = now_iso()
        CHANNELS_FILE.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def run(self) -> None:
        self.load_perms()
        self.ensure_structure()
        self.ensure_roles()
        self.ensure_invite()
        if not self.check_only:
            self.save()
        self.ensure_messages()
        self.announce_bot()
        self.cleanup_duplicate_alerts()
        self.ensure_guild_settings()
        if not self.check_only:
            self.save()
        if self.missing:
            need = (PERM["MANAGE_GUILD"] | PERM["MANAGE_WEBHOOKS"] | PERM["MANAGE_EVENTS"]
                    | PERM["CREATE_EVENTS"] | PERM["PIN_MESSAGES"] | PERM["MOVE_MEMBERS"] | PERM["MODERATE_MEMBERS"])
            base = int(self.bot_role["permissions"]) if self.bot_role else 0
            self.log(f"MISSING permissions: {', '.join(sorted(self.missing))}")
            self.log("Re-invite URL: https://discord.com/oauth2/authorize?client_id=" + CLIENT_ID
                     + f"&scope=bot%20applications.commands&permissions={base | need}")
        for n in self.notes:
            self.log("note: " + n)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--announce-bot", action="store_true", help="post the one-time bot features announcement")
    args = ap.parse_args()
    Setup(Bot(), check_only=args.check, announce=args.announce_bot).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
