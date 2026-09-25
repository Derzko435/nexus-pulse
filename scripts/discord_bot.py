#!/usr/bin/env python3
"""NEXUS PULSE — 24/7 Discord bot (discord.py 2.x). Runs on the box, token never leaves it.

  slash: /цена /скидки /раздачи /сборка /пинг /матчи /лфг /роль /ранг /топ /помощь
  XP levels for messages (60 s cooldown) → roles Новичок / Игрок / Ветеран / Легенда
  auto voice rooms: join «➕ Создать комнату» → personal room, deleted when empty
  real-time reaction roles in #🎭роли (hourly `discord_post.py sync-roles` stays as fallback)
  welcome card in #👋приветствие on join (no DMs)
  «Игровой вечер» event: started / finished on time

Privileged intents are used only if enabled in the Developer Portal (checked at start and every
30 min; the bot restarts itself when they change). Without «Server Members» the welcome card is
triggered by Discord's own join message; without «Message Content» XP still counts messages.

State: /home/box/.cache/nexus-pulse/ (xp.json, temp_rooms.json, bot_heartbeat.json).
Start: bash scripts/discord_bot_run.sh  (supervised loop; watchdog in discord_box_sync.sh)
"""
from __future__ import annotations

import asyncio
import fcntl
import hashlib
import json
import logging
import os
import random
import re
import sys
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import aiohttp
import discord
from discord import app_commands

sys.path.insert(0, str(Path(__file__).resolve().parent))
from discord_api import load_token  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CACHE = Path(os.environ.get("NP_CACHE", "/home/box/.cache/nexus-pulse"))
XP_FILE = CACHE / "xp.json"
ROOMS_FILE = CACHE / "temp_rooms.json"
ROLES_STATE = CACHE / "reaction_roles.json"
ROLES_LOCK = CACHE / "reaction_roles.lock"
HEARTBEAT = CACHE / "bot_heartbeat.json"
GUILD_ID = 1552735502266794204
GUILD = discord.Object(id=GUILD_ID)
SITE = "https://derzko435.github.io/nexus-pulse/"
LOGO = SITE + "assets/nexus-pulse-icon.png"
BRAND = 0x8B5CFF
MSK = timezone(timedelta(hours=3), name="MSK")
CODE_HASH = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]
FLAG_MEMBERS = (1 << 14) | (1 << 15)
FLAG_CONTENT = (1 << 18) | (1 << 19)
XP_COOLDOWN = 60
LEVELS = [(1, "Новичок"), (5, "Игрок"), (15, "Ветеран"), (30, "Легенда")]
LFG_GAMES = ["CS2", "Valorant", "Dota 2", "League of Legends", "Apex Legends", "Fortnite", "Minecraft",
             "PUBG", "GTA Online", "Rust", "Overwatch 2", "Lethal Company", "Другое"]
CPUS = {"r5_5500": "Ryzen 5 5500", "i5_12400f": "Intel i5-12400F", "r5_7600": "Ryzen 5 7600",
        "i7_14700k": "Intel i7-14700K", "r9_7950x": "Ryzen 9 7950X"}
GPUS = {"gtx1650": "GTX 1650", "rtx3060": "RTX 3060 12GB", "rtx4060": "RTX 4060", "rtx4070": "RTX 4070",
        "rtx4080": "RTX 4080 / 7900 XT"}
GAME_NAMES = {"cs2": "CS2", "dota2": "Dota 2", "valorant": "Valorant", "lol": "LoL"}

log = logging.getLogger("nexus-bot")


# ------------------------------------------------------------------ small utils
def read_json(p: Path, default):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def write_json(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    tmp.replace(p)


@contextmanager
def roles_lock():
    CACHE.mkdir(parents=True, exist_ok=True)
    with open(ROLES_LOCK, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def roles_state_get(rid: int) -> set[str]:
    with roles_lock():
        return set(read_json(ROLES_STATE, {}).get(str(rid)) or [])


def roles_state_update(rid: int, uid: int, add: bool) -> bool:
    """add/remove uid in the reaction-role state (shared with discord_post.py sync-roles).
    Returns whether uid was present before."""
    with roles_lock():
        st = read_json(ROLES_STATE, {})
        cur = set(st.get(str(rid)) or [])
        was = str(uid) in cur
        cur = cur | {str(uid)} if add else cur - {str(uid)}
        st[str(rid)] = sorted(cur)
        write_json(ROLES_STATE, st)
        return was


def md(s) -> str:
    return re.sub(r"([\\*_~`|>\[\]()])", r"\\\1", "" if s is None else str(s)).replace("@", "@\u200b")


def clip(s, n: int) -> str:
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def xp_for_next(level: int) -> int:
    return 5 * level * level + 50 * level + 100


def level_from_xp(xp: int) -> tuple[int, int, int]:
    """→ (level, xp into current level, xp needed for next level)"""
    lvl = 0
    while xp >= xp_for_next(lvl):
        xp -= xp_for_next(lvl)
        lvl += 1
    return lvl, xp, xp_for_next(lvl)


def parse_dt(s):
    if not s:
        return None
    try:
        s = str(s)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
            return datetime.fromisoformat(s).replace(tzinfo=MSK)
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=MSK)
    except ValueError:
        return None


def footer(e: discord.Embed, label: str) -> discord.Embed:
    e.set_footer(text=f"NEXUS PULSE · {label}", icon_url=LOGO)
    return e


# ------------------------------------------------------------------ bot
class NexusBot(discord.Client):
    def __init__(self, members_intent: bool, content_intent: bool, app_flags: int):
        intents = discord.Intents.default()  # guilds, guild messages, reactions, voice states, events
        intents.members = members_intent
        intents.message_content = content_intent
        intents.presences = False
        super().__init__(intents=intents, allowed_mentions=discord.AllowedMentions.none(),
                         activity=discord.Game("NEXUS PULSE · /помощь"))
        self.tree = app_commands.CommandTree(self)
        self.members_intent = members_intent
        self.content_intent = content_intent
        self.app_flags = app_flags
        self.cfg: dict = {}
        self.cfg_loaded = 0.0
        self.http_session: aiohttp.ClientSession | None = None
        self.data_cache: dict[str, tuple[float, dict]] = {}
        self.xp = read_json(XP_FILE, {"users": {}, "welcomed": {}})
        self.xp.setdefault("users", {})
        self.xp.setdefault("welcomed", {})
        self.xp_dirty = False
        self.cooldown: dict[int, float] = {}
        self.rooms = read_json(ROOMS_FILE, {})  # channel_id -> {"owner": id, "created": ts, "empty_since": ts|None}
        self.lfg_cooldown: dict[int, float] = {}
        self.exit_code = 0
        self.started = time.time()

    # -------------------------------------------------------------- config / data
    def conf(self) -> dict:
        if time.time() - self.cfg_loaded > 300 or not self.cfg:
            self.cfg = read_json(DATA / "discord_channels.json", self.cfg or {})
            self.cfg_loaded = time.time()
        return self.cfg

    def cid(self, key: str) -> int | None:
        v = self.conf().get(key)
        return int(v) if v and str(v).isdigit() else None

    async def site_json(self, name: str) -> dict:
        now = time.time()
        hit = self.data_cache.get(name)
        if hit and now - hit[0] < 600:
            return hit[1]
        data = None
        try:
            assert self.http_session
            async with self.http_session.get(f"{SITE}data/{name}?t={int(now // 600)}", timeout=aiohttp.ClientTimeout(total=10)) as r:
                if r.status == 200:
                    data = json.loads(await r.text())
        except Exception as e:  # noqa: BLE001
            log.warning("site json %s: %s", name, e)
        if data is None:
            data = read_json(DATA / name, {})
        self.data_cache[name] = (now, data)
        return data

    # -------------------------------------------------------------- lifecycle
    async def setup_hook(self) -> None:
        self.http_session = aiohttp.ClientSession(headers={"User-Agent": "NexusPulseBot/1.0"})
        register_commands(self)
        self.tree.copy_global_to(guild=GUILD)
        synced = await self.tree.sync(guild=GUILD)
        log.info("synced %d guild commands", len(synced))
        self.loop.create_task(self.ticker())

    async def close(self) -> None:
        self.save_xp(force=True)
        if self.http_session:
            await self.http_session.close()
        await super().close()

    async def on_ready(self) -> None:
        log.info("ready as %s · members_intent=%s content_intent=%s", self.user, self.members_intent, self.content_intent)
        self.heartbeat()
        # reconcile reaction roles once (same logic as the hourly fallback)
        self.loop.run_in_executor(None, self.reconcile_roles)
        await self.sweep_rooms()

    def reconcile_roles(self) -> None:
        try:
            import argparse
            import discord_post
            discord_post.cmd_sync_roles(load_token(), argparse.Namespace())
        except SystemExit as e:
            log.warning("reconcile roles: %s", e)
        except Exception as e:  # noqa: BLE001
            log.warning("reconcile roles failed: %s", e)

    def heartbeat(self) -> None:
        write_json(HEARTBEAT, {"ts": int(time.time()), "pid": os.getpid(), "code": CODE_HASH,
                               "user": str(self.user), "latency_ms": round((self.latency or 0) * 1000),
                               "members_intent": self.members_intent, "content_intent": self.content_intent,
                               "started": int(self.started)})

    async def ticker(self) -> None:
        await self.wait_until_ready()
        n = 0
        while not self.is_closed():
            try:
                self.heartbeat()
                self.save_xp()
                await self.sweep_rooms()
                if n % 5 == 0:
                    await self.game_night()
                if n % 30 == 29:
                    await self.check_intents()
            except Exception as e:  # noqa: BLE001
                log.exception("ticker: %s", e)
            n += 1
            await asyncio.sleep(60)

    async def check_intents(self) -> None:
        try:
            app = await self.application_info()
            flags = int(getattr(app, "flags", discord.ApplicationFlags()).value)
        except Exception:  # noqa: BLE001
            return
        if bool(flags & FLAG_MEMBERS) != self.members_intent or bool(flags & FLAG_CONTENT) != self.content_intent:
            log.info("privileged intents changed (flags %s) → restart", flags)
            self.exit_code = 3
            await self.close()

    # -------------------------------------------------------------- XP
    def save_xp(self, force: bool = False) -> None:
        if self.xp_dirty or force:
            write_json(XP_FILE, self.xp)
            self.xp_dirty = False

    async def on_message(self, message: discord.Message) -> None:
        if not message.guild or message.guild.id != GUILD_ID:
            return
        if message.type == discord.MessageType.new_member and not self.members_intent:
            await self.welcome(message.author, reply_to=message)
            return
        if message.author.bot or message.type not in (discord.MessageType.default, discord.MessageType.reply):
            return
        if message.channel.id == self.cid("lfg") and message.content:
            if await self.lfg_from_text(message):
                return
        await self.add_xp(message)

    async def add_xp(self, message: discord.Message) -> None:
        uid = message.author.id
        now = time.time()
        if now - self.cooldown.get(uid, 0) < XP_COOLDOWN:
            return
        self.cooldown[uid] = now
        u = self.xp["users"].setdefault(str(uid), {"xp": 0, "lvl": 0, "msgs": 0})
        u["xp"] += random.randint(15, 25)
        u["msgs"] = u.get("msgs", 0) + 1
        u["name"] = message.author.display_name
        self.xp_dirty = True
        lvl = level_from_xp(u["xp"])[0]
        if lvl != u.get("lvl"):
            u["lvl"] = lvl
            new_role = await self.sync_level_role(message.author, lvl)
            if new_role and new_role != "Новичок":
                try:
                    await message.channel.send(
                        f"🎉 {message.author.mention} получает **{lvl} уровень** и роль **{new_role}**! Так держать 🎮",
                        allowed_mentions=discord.AllowedMentions(users=[message.author]))
                except discord.HTTPException:
                    pass

    async def sync_level_role(self, member, lvl: int) -> str | None:
        """Keep only the highest reached level role. Returns the new role name if it changed."""
        ids = self.conf().get("levelRoles") or {}
        if not ids or not isinstance(member, discord.Member):
            return None
        want_name, want_id = None, None
        for min_lvl, name in LEVELS:
            if lvl >= min_lvl and str(min_lvl) in ids:
                want_name, want_id = name, int(ids[str(min_lvl)])
        all_ids = {int(v) for v in ids.values()}
        have = {r.id for r in member.roles}
        try:
            drop = [discord.Object(id=r) for r in (have & all_ids) - ({want_id} if want_id else set())]
            if drop:
                await member.remove_roles(*drop, reason="XP level")
            if want_id and want_id not in have:
                await member.add_roles(discord.Object(id=want_id), reason=f"XP level {lvl}")
                return want_name
        except discord.HTTPException as e:
            log.warning("level role: %s", e)
        return None

    # -------------------------------------------------------------- welcome
    async def on_member_join(self, member: discord.Member) -> None:
        if member.guild.id == GUILD_ID and not member.bot:
            await self.welcome(member)

    async def welcome(self, member, reply_to: discord.Message | None = None) -> None:
        if getattr(member, "bot", False):
            return
        last = self.xp["welcomed"].get(str(member.id), 0)
        if time.time() - last < 86400:
            return
        ch = self.get_channel(self.cid("welcome") or 0)
        if not isinstance(ch, discord.TextChannel):
            return
        c = self.conf()
        e = discord.Embed(
            title=f"👋 Привет, {clip(member.display_name, 60)}!",
            description=(f"Рады видеть тебя на **NEXUS PULSE** 🎮\n\n"
                         f"1️⃣ Загляни в <#{c.get('rules')}>\n"
                         f"2️⃣ Выбери игры в <#{c.get('roles')}> — так проще найти тиму\n"
                         f"3️⃣ Представься в <#{c.get('intro')}>\n"
                         f"4️⃣ Ищи пати в <#{c.get('lfg')}> или командой `/лфг`\n\n"
                         f"Халява, скидки и матчи — в ленте 📡, а всё остальное на [сайте]({SITE})."),
            color=BRAND)
        e.set_thumbnail(url=member.display_avatar.url if hasattr(member, "display_avatar") else LOGO)
        footer(e, "добро пожаловать")
        try:
            await ch.send(content=member.mention, embed=e, allowed_mentions=discord.AllowedMentions(users=[member]),
                          reference=reply_to if reply_to and reply_to.channel.id == ch.id else None, mention_author=False)
            self.xp["welcomed"][str(member.id)] = int(time.time())
            self.xp_dirty = True
        except discord.HTTPException as e2:
            log.warning("welcome failed: %s", e2)

    # -------------------------------------------------------------- reaction roles (real time)
    def role_for(self, payload) -> int | None:
        if payload.guild_id != GUILD_ID or payload.channel_id != self.cid("roles"):
            return None
        if payload.user_id == (self.user.id if self.user else 0):
            return None
        rid = (self.conf().get("reactionRoles") or {}).get(str(payload.emoji.name))
        return int(rid) if rid else None

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        rid = self.role_for(payload)
        if not rid or (payload.member and payload.member.bot):
            return
        try:
            await self.http.add_role(GUILD_ID, payload.user_id, rid, reason="reaction role")
            await asyncio.to_thread(roles_state_update, rid, payload.user_id, True)
        except discord.HTTPException as e:
            log.warning("reaction add role: %s", e)

    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent) -> None:
        rid = self.role_for(payload)
        if not rid:
            return
        granted = await asyncio.to_thread(roles_state_get, rid)
        if str(payload.user_id) not in granted:
            return  # role was not granted by reaction — leave it alone
        try:
            await self.http.remove_role(GUILD_ID, payload.user_id, rid, reason="reaction removed")
        except discord.NotFound:
            pass
        except discord.HTTPException as e:
            log.warning("reaction remove role: %s", e)
            return
        await asyncio.to_thread(roles_state_update, rid, payload.user_id, False)

    # -------------------------------------------------------------- auto voice rooms
    async def on_voice_state_update(self, member: discord.Member, before, after) -> None:
        if member.guild.id != GUILD_ID:
            return
        create_id = self.cid("voice_create")
        if after.channel and after.channel.id == create_id and not member.bot:
            await self.create_room(member, after.channel)
        if before.channel and str(before.channel.id) in self.rooms and before.channel != after.channel:
            if not [m for m in before.channel.members if not m.bot]:
                await self.delete_room(before.channel)

    async def create_room(self, member: discord.Member, hub: discord.VoiceChannel, move: bool = True):
        # one room per owner: reuse an existing one
        for cid, r in self.rooms.items():
            if r.get("owner") == member.id:
                ch = self.get_channel(int(cid))
                if isinstance(ch, discord.VoiceChannel):
                    if move:
                        await self._move(member, ch)
                    return ch
        overwrites = dict(hub.category.overwrites) if hub.category else {}
        overwrites[member] = discord.PermissionOverwrite(view_channel=True, connect=True, speak=True,
                                                         manage_channels=True)
        try:
            ch = await hub.guild.create_voice_channel(
                name=clip(f"🎮 {member.display_name}", 90), category=hub.category, overwrites=overwrites,
                position=hub.position + 1, reason=f"personal room for {member}")
        except discord.HTTPException as e:
            log.warning("create room failed: %s", e)
            return None
        self.rooms[str(ch.id)] = {"owner": member.id, "created": int(time.time()), "empty_since": None}
        write_json(ROOMS_FILE, self.rooms)
        if move:
            await self._move(member, ch)
        return ch

    async def _move(self, member: discord.Member, ch: discord.VoiceChannel) -> None:
        try:
            await member.move_to(ch, reason="personal room")
            try:
                await ch.send(f"{member.mention}, это твоя комната 🎧 Меняй название и лимит в настройках канала. "
                              "Когда все выйдут — она удалится сама.",
                              allowed_mentions=discord.AllowedMentions(users=[member]))
            except discord.HTTPException:
                pass
        except discord.Forbidden:
            # no «Move Members» permission yet → invite the user to click the room
            try:
                await ch.send(f"{member.mention}, твоя комната готова — нажми на **{ch.name}**, чтобы зайти 🎧",
                              allowed_mentions=discord.AllowedMentions(users=[member]))
            except discord.HTTPException:
                pass
        except discord.HTTPException as e:
            log.warning("move failed: %s", e)

    async def delete_room(self, ch) -> None:
        try:
            await ch.delete(reason="personal room is empty")
        except discord.NotFound:
            pass
        except discord.HTTPException as e:
            log.warning("delete room failed: %s", e)
            return
        self.rooms.pop(str(ch.id), None)
        write_json(ROOMS_FILE, self.rooms)

    async def sweep_rooms(self) -> None:
        """Delete tracked rooms that are empty for > 2 min (covers restarts and never-joined rooms)."""
        changed = False
        now = int(time.time())
        for cid, r in list(self.rooms.items()):
            ch = self.get_channel(int(cid))
            if ch is None:
                if self.is_ready():
                    self.rooms.pop(cid)
                    changed = True
                continue
            humans = [m for m in getattr(ch, "members", []) if not m.bot]
            if humans:
                if r.get("empty_since"):
                    r["empty_since"] = None
                    changed = True
                continue
            if not r.get("empty_since"):
                r["empty_since"] = now
                changed = True
            elif now - r["empty_since"] >= 120:
                await self.delete_room(ch)
        if changed:
            write_json(ROOMS_FILE, self.rooms)

    # -------------------------------------------------------------- game night event
    async def game_night(self) -> None:
        g = self.get_guild(GUILD_ID)
        vc = self.cid("voice_gamenight")
        if not g or not vc:
            return
        now = datetime.now(timezone.utc)
        for ev in g.scheduled_events:
            if ev.channel_id != vc or (ev.creator_id and self.user and ev.creator_id != self.user.id):
                continue
            try:
                if ev.status == discord.EventStatus.scheduled and ev.start_time <= now:
                    await ev.start(reason="game night time")
                elif ev.status == discord.EventStatus.active and now - ev.start_time > timedelta(hours=3, minutes=30):
                    ch = g.get_channel(vc)
                    if not ch or not [m for m in getattr(ch, "members", []) if not m.bot]:
                        await ev.end(reason="game night over")
            except discord.HTTPException as e:
                log.warning("game night event: %s", e)

    # -------------------------------------------------------------- LFG
    def lfg_embed(self, author, game: str, rank: str, mode: str, region: str, voice: bool | None,
                  when: str, contact: str, note: str, joined: list[int] | None = None) -> discord.Embed:
        e = discord.Embed(title=f"LFG · {clip(game, 60)}", description=clip(note, 600) or "Ищу тиммейтов 🎮", color=BRAND,
                          timestamp=datetime.now(timezone.utc))
        e.set_author(name=clip(author.display_name, 60), icon_url=author.display_avatar.url)
        e.add_field(name="Ник", value=clip(contact or author.display_name, 60), inline=True)
        e.add_field(name="Ранг", value=clip(rank, 60) or "—", inline=True)
        e.add_field(name="Режим", value=clip(mode, 60) or "—", inline=True)
        e.add_field(name="Регион", value=clip(region, 40) or "—", inline=True)
        e.add_field(name="Время", value=clip(when, 60) or "—", inline=True)
        e.add_field(name="Голос", value="да" if voice else ("нет" if voice is False else "—"), inline=True)
        e.add_field(name="Автор", value=author.mention, inline=True)
        e.add_field(name="В деле", value=" ".join(f"<@{u}>" for u in (joined or [])) or "пока никого — будь первым!", inline=False)
        return footer(e, "поиск тимы · /лфг")

    def lfg_view(self, author_id: int, closed: bool = False, count: int = 0) -> discord.ui.View:
        v = discord.ui.View(timeout=None)
        v.add_item(discord.ui.Button(label=f"✋ Я в деле{f' · {count}' if count else ''}", style=discord.ButtonStyle.success,
                                     custom_id="np_lfg_join", disabled=closed))
        v.add_item(discord.ui.Button(label="🔒 Собрались" if not closed else "Набор закрыт", style=discord.ButtonStyle.secondary,
                                     custom_id=f"np_lfg_close:{author_id}", disabled=closed))
        return v

    async def post_lfg(self, author, **kw) -> discord.Message | None:
        ch = self.get_channel(self.cid("lfg") or 0)
        if not isinstance(ch, discord.TextChannel):
            return None
        return await ch.send(embed=self.lfg_embed(author, **kw), view=self.lfg_view(author.id))

    async def lfg_from_text(self, message: discord.Message) -> bool:
        """Site form text («🔎 Ищу тиму …») → nice card with buttons (needs Message Content intent)."""
        text = message.content.strip()
        if not re.match(r"^\W{0,3}(ищу тиму|lfg)\b", text, re.I):
            return False
        f = {}
        for line in text.splitlines()[1:]:
            for part in line.split("·"):
                m = re.match(r"\s*([А-Яа-яЁёA-Za-z ]{3,20})\s*:\s*(.+?)\s*$", part)
                if m:
                    f[m.group(1).strip().lower()] = m.group(2).strip()
        head = re.sub(r"^\W{0,3}(ищу тиму|lfg)\s*[·:\-—]?\s*", "", text.splitlines()[0], flags=re.I).strip()
        note = "\n".join(l for l in text.splitlines()[1:] if ":" not in l and "NEXUS PULSE" not in l).strip()
        voice = f.get("голос", "").lower()
        try:
            await self.post_lfg(message.author, game=head or f.get("игра", "Игра"), rank=f.get("ранг", ""),
                                mode=f.get("режим", ""), region=f.get("регион", ""),
                                voice=True if voice.startswith(("да", "yes", "есть")) else (False if voice else None),
                                when=f.get("время", ""), contact=f.get("discord", "") or f.get("ник", ""),
                                note=f.get("комментарий", "") or note)
            await message.delete()
        except discord.HTTPException as e:
            log.warning("lfg from text: %s", e)
            return False
        return True

    async def on_interaction(self, inter: discord.Interaction) -> None:
        if inter.type != discord.InteractionType.component:
            return
        cid = (inter.data or {}).get("custom_id", "")
        if not cid.startswith("np_lfg") or not inter.message or not inter.message.embeds:
            return
        e = inter.message.embeds[0]
        idx = next((i for i, f in enumerate(e.fields) if f.name == "В деле"), None)
        joined = [int(x) for x in re.findall(r"<@!?(\d+)>", e.fields[idx].value)] if idx is not None else []
        author_field = next((f.value for f in e.fields if f.name == "Автор"), "")
        author_id = int((re.findall(r"\d+", author_field) or ["0"])[0])
        if cid == "np_lfg_join":
            if inter.user.id == author_id:
                await inter.response.send_message("Это твоя заявка 🙂 Жди откликов — участники появятся в списке.", ephemeral=True)
                return
            if inter.user.id in joined:
                joined.remove(inter.user.id)
                msg = "Ок, убрал тебя из списка."
            else:
                if len(joined) >= 20:
                    await inter.response.send_message("Список уже полный.", ephemeral=True)
                    return
                joined.append(inter.user.id)
                msg = None
            if idx is not None:
                e.set_field_at(idx, name="В деле", value=" ".join(f"<@{u}>" for u in joined) or "пока никого — будь первым!", inline=False)
            await inter.response.edit_message(embed=e, view=self.lfg_view(author_id, count=len(joined)))
            if msg:
                await inter.followup.send(msg, ephemeral=True)
            elif author_id:
                try:
                    await inter.followup.send(f"<@{author_id}>, {inter.user.mention} в деле! Пишите друг другу и залетайте в голос 🎧",
                                              allowed_mentions=discord.AllowedMentions(users=True))
                except discord.HTTPException:
                    pass
        elif cid.startswith("np_lfg_close:"):
            owner = int(cid.split(":", 1)[1] or 0)
            perms = inter.user.guild_permissions if isinstance(inter.user, discord.Member) else None
            if inter.user.id != owner and not (perms and perms.manage_messages):
                await inter.response.send_message("Закрыть набор может только автор заявки.", ephemeral=True)
                return
            e.title = (e.title or "LFG") + " (собрано)"
            e.color = discord.Color.dark_grey()
            await inter.response.edit_message(embed=e, view=self.lfg_view(owner, closed=True, count=len(joined)))


# ------------------------------------------------------------------ slash commands
def register_commands(bot: NexusBot) -> None:
    tree = bot.tree

    async def price_names() -> list[tuple[str, str]]:
        prices = (await bot.site_json("prices.json")).get("prices") or {}
        cat = (await bot.site_json("catalog.json")).get("games") or {}
        out = [(cat.get(k, {}).get("name") or k, "p:" + k) for k in prices]
        for d in (await bot.site_json("deals.json")).get("deals") or []:
            if d.get("title"):
                out.append((d["title"], "d:" + str(d.get("id") or d["title"])))
        return out

    @tree.command(name="цена", description="Цена игры в Steam и скидка (по данным NEXUS PULSE)")
    @app_commands.rename(query="игра")
    @app_commands.describe(query="Название игры")
    async def price(inter: discord.Interaction, query: str):
        await inter.response.defer()
        names = await price_names()
        q = query.strip().lower()
        hit = next((v for n, v in names if v == query or n.lower() == q), None) or \
            next((v for n, v in names if q and q in n.lower()), None)
        if not hit:
            await inter.followup.send(embed=footer(discord.Embed(
                title=f"🔎 «{clip(query, 60)}» пока не отслеживаю",
                description=f"Посмотри все скидки на [сайте]({SITE}#deals) или добавь игру в «Отслеживаю цены» — "
                            f"сайт сам напомнит, когда она подешевеет.", color=BRAND), "цены"))
            return
        kind, key = hit.split(":", 1)
        if kind == "p":
            p = ((await bot.site_json("prices.json")).get("prices") or {}).get(key) or {}
            g = ((await bot.site_json("catalog.json")).get("games") or {}).get(key) or {}
            name = g.get("name") or key
            pct = int(p.get("pct") or 0)
            line = (f"~~{p.get('initial')} ₽~~ → **{p.get('final')} ₽** (−{pct}%)" if pct else f"**{p.get('final')} ₽**")
            e = discord.Embed(title=f"💰 {clip(name, 200)}", url=g.get("url") or f"https://store.steampowered.com/app/{p.get('appid')}/",
                              description=f"{line} · Steam\n\n[Следить за ценой на NEXUS PULSE →]({SITE}#watchlist)",
                              color=0x3DFF9A if pct else BRAND)
            if g.get("img"):
                e.set_thumbnail(url=g["img"])
        else:
            d = next((d for d in (await bot.site_json("deals.json")).get("deals") or [] if str(d.get("id") or d.get("title")) == key), {})
            e = discord.Embed(title=f"🔥 −{d.get('pct')}% · {clip(d.get('title'), 200)}", url=d.get("url") or SITE + "#deals",
                              description=f"~~{d.get('old')} ₽~~ → **{d.get('neu')} ₽** · {d.get('store') or 'Steam'}\n\n"
                                          f"[Все скидки на NEXUS PULSE →]({SITE}#deals)", color=0x00D1FF)
            if str(d.get("steamAppId") or "").isdigit():
                e.set_thumbnail(url=f"https://cdn.cloudflare.steamstatic.com/steam/apps/{d['steamAppId']}/header.jpg")
        await inter.followup.send(embed=footer(e, "цены"))

    @price.autocomplete("query")
    async def price_ac(inter: discord.Interaction, current: str):
        cur = current.lower().strip()
        names = await price_names()
        res = [app_commands.Choice(name=clip(n, 95), value=v) for n, v in names if not cur or cur in n.lower()]
        return res[:25]

    @tree.command(name="скидки", description="Лучшие скидки прямо сейчас")
    async def deals(inter: discord.Interaction):
        await inter.response.defer()
        ds = [d for d in (await bot.site_json("deals.json")).get("deals") or [] if d.get("title")]
        ds.sort(key=lambda d: -float(d.get("pct") or 0))
        lines = [f"**−{d.get('pct')}%** [{md(clip(d['title'], 55))}]({d.get('url') or SITE + '#deals'}) — ~~{d.get('old')}~~ **{d.get('neu')} ₽**" for d in ds[:10]]
        e = discord.Embed(title="💸 Топ скидок сейчас", url=SITE + "#deals", color=0x00D1FF,
                          description="\n".join(lines) or "Сейчас больших скидок нет — загляни позже.")
        e.add_field(name="\u200b", value=f"[Все скидки и «Отслеживаю цены» на NEXUS PULSE →]({SITE}#deals)")
        await inter.followup.send(embed=footer(e, "скидки"))

    @tree.command(name="раздачи", description="Бесплатные игры, которые можно забрать сейчас")
    async def freebies(inter: discord.Interaction):
        await inter.response.defer()
        today = datetime.now(MSK).date()
        lines = []
        for it in (await bot.site_json("freebies.json")).get("items") or []:
            fid = str(it.get("id") or "")
            if re.search(r"(-always$|^gog-giveaway|^prime-)", fid) or not it.get("title"):
                continue
            until = parse_dt(it.get("until"))
            if until and until.date() < today:
                continue
            soon = "скоро" in str(it.get("note") or "").lower()
            lines.append(f"{'⏳ **Скоро:**' if soon else '🎁'} [{md(clip(it['title'], 60))}]({it.get('claimUrl') or SITE + '#freebies'})"
                         f" · {md(it.get('store'))}{f' · до {until:%d.%m}' if until else ''}")
        e = discord.Embed(title="🎁 Раздачи", url=SITE + "#freebies", color=0x3DFF9A,
                          description="\n".join(lines[:10]) or "Сейчас активных раздач нет.")
        e.add_field(name="\u200b", value=f"Включи роль 🔔 Раздачи в <#{bot.conf().get('roles')}> — пришлём, как только появится новая.")
        await inter.followup.send(embed=footer(e, "раздачи"))

    @tree.command(name="сборка", description="Открыть конструктор ПК на сайте с твоими комплектующими")
    @app_commands.rename(cpu="процессор", gpu="видеокарта")
    @app_commands.choices(cpu=[app_commands.Choice(name=n, value=k) for k, n in CPUS.items()],
                          gpu=[app_commands.Choice(name=n, value=k) for k, n in GPUS.items()])
    async def build(inter: discord.Interaction, cpu: app_commands.Choice[str], gpu: app_commands.Choice[str]):
        url = f"{SITE}?{urlencode({'cpu': cpu.value, 'gpu': gpu.value, 'share': '1'})}#tools"
        e = discord.Embed(title=f"🖥 {cpu.name} + {gpu.name}", url=url, color=BRAND,
                          description=f"Сборка открыта в конструкторе: FPS в популярных играх, узкие места и советы по апгрейду.\n\n[Открыть сборку →]({url})")
        await inter.response.send_message(embed=footer(e, "конструктор ПК"))

    @tree.command(name="пинг", description="Карта пинга до игровых серверов")
    async def ping(inter: discord.Interaction):
        e = discord.Embed(title="📡 Карта пинга", url=SITE + "#pingMapCard", color=0x00F5FF,
                          description="Проверь пинг до серверов CS2, Dota 2, Valorant и других игр прямо из браузера — "
                                      f"и выбери лучший регион.\n\n[Открыть карту пинга →]({SITE}#pingMapCard)")
        e.add_field(name="Бот", value=f"{round(bot.latency * 1000)} мс до Discord", inline=True)
        await inter.response.send_message(embed=footer(e, "пинг"))

    @tree.command(name="матчи", description="Большие матчи сегодня (время МСК)")
    async def matches(inter: discord.Interaction):
        await inter.response.defer()
        now = datetime.now(MSK)
        ms = []
        for m in (await bot.site_json("matches.json")).get("matches") or []:
            st = parse_dt(m.get("startsAt"))
            if not st or not m.get("teamA"):
                continue
            st = st.astimezone(MSK)
            if m.get("status") == "live" or (st.date() == now.date() and m.get("tier") in ("S", "A")):
                ms.append((0 if m.get("status") == "live" else (1 if m.get("status") == "upcoming" else 2), st, m))
        ms.sort(key=lambda x: (x[0], x[1]))
        lines = []
        for _o, st, m in ms[:15]:
            game = GAME_NAMES.get(m.get("gameKey"), m.get("game") or "")
            if m.get("status") == "live":
                tag = f"🔴 **{m.get('scoreA', 0)}:{m.get('scoreB', 0)}**"
            elif m.get("status") == "finished":
                tag = f"✅ {m.get('scoreA', '')}:{m.get('scoreB', '')}"
            else:
                tag = f"`{st:%H:%M}`"
            lines.append(f"{tag} {md(game)} · **{md(m['teamA'])}** vs **{md(m['teamB'])}**{' ⭐' if m.get('tier') == 'S' else ''}")
        e = discord.Embed(title=f"🏆 Матчи на {now:%d.%m}", url=SITE + "#esports", color=0xFFB020,
                          description="\n".join(lines) or "Сегодня больших матчей нет.")
        e.add_field(name="\u200b", value=f"⭐ S-тир · [Трансляции и расписание →]({SITE}#esports)")
        await inter.followup.send(embed=footer(e, "киберспорт"))

    @tree.command(name="лфг", description="Найти тиму: карточка в #поиск-тимы с кнопкой «Я в деле»")
    @app_commands.rename(game="игра", rank="ранг", mode="режим", region="регион", voice="голос", when="время",
                         contact="ник", note="комментарий")
    @app_commands.describe(game="Во что играем", rank="Твой ранг / уровень", mode="Режим: ранкед, фан, турнир…",
                           region="Регион серверов", voice="Есть микрофон / голосовой чат", when="Когда играем (МСК)",
                           contact="Ник в игре (если отличается)", note="Пара слов о себе")
    @app_commands.choices(game=[app_commands.Choice(name=g, value=g) for g in LFG_GAMES],
                          region=[app_commands.Choice(name=r, value=r) for r in ["RU / СНГ", "EU", "Любой"]])
    async def lfg(inter: discord.Interaction, game: app_commands.Choice[str], rank: str = "", mode: str = "",
                  region: app_commands.Choice[str] | None = None, voice: bool | None = None, when: str = "",
                  contact: str = "", note: str = ""):
        last = bot.lfg_cooldown.get(inter.user.id, 0)
        if time.time() - last < 600:
            await inter.response.send_message("Одна заявка раз в 10 минут 🙂 Старая ещё висит в канале.", ephemeral=True)
            return
        await inter.response.defer(ephemeral=True)
        msg = await bot.post_lfg(inter.user, game=game.value, rank=rank, mode=mode, region=region.value if region else "",
                                 voice=voice, when=when, contact=contact, note=note)
        if not msg:
            await inter.followup.send("Не нашёл канал поиска тимы — сообщи модераторам.", ephemeral=True)
            return
        bot.lfg_cooldown[inter.user.id] = time.time()
        await inter.followup.send(f"Готово! Твоя заявка: {msg.jump_url}\nОна появится и в ленте на сайте: {SITE}#lfg", ephemeral=True)

    async def role_choices() -> list[tuple[str, int]]:
        g = bot.get_guild(GUILD_ID)
        out = []
        for emo, rid in (bot.conf().get("reactionRoles") or {}).items():
            r = g.get_role(int(rid)) if g else None
            if r:
                out.append((f"{emo} {r.name}", r.id))
        return out

    @tree.command(name="роль", description="Взять или снять роль игры / уведомлений")
    @app_commands.rename(role="роль")
    @app_commands.describe(role="Какую роль переключить")
    async def role(inter: discord.Interaction, role: str):
        choices = dict((str(v), n) for n, v in await role_choices())
        if role not in choices or not isinstance(inter.user, discord.Member):
            await inter.response.send_message("Выбери роль из списка 🙂", ephemeral=True)
            return
        rid = int(role)
        try:
            if any(r.id == rid for r in inter.user.roles):
                await inter.user.remove_roles(discord.Object(id=rid), reason="/роль")
                # also drop the matching reaction so the hourly fallback stays consistent
                was = await asyncio.to_thread(roles_state_update, rid, inter.user.id, False)
                if was:
                    emo = next((e for e, r in (bot.conf().get("reactionRoles") or {}).items() if int(r) == rid), None)
                    await remove_user_reaction(bot, emo, inter.user.id)
                await inter.response.send_message(f"Снял роль **{choices[role]}**.", ephemeral=True)
            else:
                await inter.user.add_roles(discord.Object(id=rid), reason="/роль")
                await inter.response.send_message(f"Выдал роль **{choices[role]}** ✅", ephemeral=True)
        except discord.HTTPException:
            await inter.response.send_message("Не получилось изменить роль — попробуй через реакции в канале ролей.", ephemeral=True)

    @role.autocomplete("role")
    async def role_ac(inter: discord.Interaction, current: str):
        cur = current.lower()
        return [app_commands.Choice(name=n, value=str(v)) for n, v in await role_choices() if cur in n.lower()][:25]

    @tree.command(name="ранг", description="Твой уровень и опыт на сервере")
    @app_commands.rename(member="участник")
    async def rank(inter: discord.Interaction, member: discord.Member | None = None):
        m = member or inter.user
        u = bot.xp["users"].get(str(m.id)) or {"xp": 0, "msgs": 0}
        lvl, cur, need = level_from_xp(int(u.get("xp", 0)))
        order = sorted(bot.xp["users"].items(), key=lambda kv: -kv[1].get("xp", 0))
        place = next((i + 1 for i, (k, _v) in enumerate(order) if k == str(m.id)), None)
        title = next((n for lv, n in reversed(LEVELS) if lvl >= lv), "—")
        filled = int(10 * cur / need) if need else 0
        e = discord.Embed(title=f"🎖 {clip(m.display_name, 60)} · уровень {lvl}", color=BRAND,
                          description=f"`{'█' * filled}{'░' * (10 - filled)}` {cur} / {need} XP до следующего уровня")
        e.add_field(name="Звание", value=title, inline=True)
        e.add_field(name="Всего XP", value=str(u.get("xp", 0)), inline=True)
        e.add_field(name="Место", value=f"#{place}" if place else "—", inline=True)
        e.set_thumbnail(url=m.display_avatar.url)
        e.add_field(name="\u200b", value="Опыт даётся за общение (раз в минуту). Звания: Новичок → Игрок (5) → Ветеран (15) → Легенда (30).", inline=False)
        await inter.response.send_message(embed=footer(e, "уровни"))

    @tree.command(name="топ", description="Самые активные участники сервера")
    async def top(inter: discord.Interaction):
        order = sorted(bot.xp["users"].items(), key=lambda kv: -kv[1].get("xp", 0))[:10]
        medals = ["🥇", "🥈", "🥉"]
        lines = [f"{medals[i] if i < 3 else f'`{i + 1}.`'} <@{k}> — ур. {level_from_xp(v.get('xp', 0))[0]} · {v.get('xp', 0)} XP"
                 for i, (k, v) in enumerate(order)]
        e = discord.Embed(title="🏆 Топ активности", color=0xFFB020,
                          description="\n".join(lines) or "Пока пусто — общайся в чатах, и ты будешь первым!")
        await inter.response.send_message(embed=footer(e, "уровни"), allowed_mentions=discord.AllowedMentions.none())

    @tree.command(name="помощь", description="Что умеет бот NEXUS PULSE")
    async def help_cmd(inter: discord.Interaction):
        e = discord.Embed(title="🤖 Бот NEXUS PULSE", color=BRAND, url=SITE, description=(
            "`/лфг` — найти тиму (карточка с кнопкой «Я в деле»)\n"
            "`/цена` — цена игры в Steam · `/скидки` — топ скидок · `/раздачи` — бесплатные игры\n"
            "`/матчи` — большие матчи сегодня · `/сборка` — конструктор ПК · `/пинг` — карта пинга\n"
            "`/роль` — роли игр и уведомлений · `/ранг` и `/топ` — уровни за активность\n\n"
            f"🔊 Зайди в **➕ Создать комнату** — получишь личный голосовой канал.\n🌐 {SITE}"))
        await inter.response.send_message(embed=footer(e, "помощь"), ephemeral=True)


async def remove_user_reaction(bot: NexusBot, emoji: str | None, user_id: int) -> None:
    ch = bot.get_channel(bot.cid("roles") or 0)
    if not emoji or not isinstance(ch, discord.TextChannel):
        return
    async for m in ch.history(limit=20):
        if m.author.id == (bot.user.id if bot.user else 0) and any(str(r.emoji) == emoji for r in m.reactions):
            try:
                await m.remove_reaction(emoji, discord.Object(id=user_id))
            except discord.HTTPException:
                pass


async def app_flags(token: str) -> int:
    async with aiohttp.ClientSession() as s:
        async with s.get("https://discord.com/api/v10/applications/@me", headers={"Authorization": f"Bot {token}"}) as r:
            if r.status != 200:
                return 0
            return int((await r.json()).get("flags") or 0)


def main() -> int:
    CACHE.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("discord.gateway").setLevel(logging.WARNING)
    token = load_token()
    flags = asyncio.run(app_flags(token))
    members, content = bool(flags & FLAG_MEMBERS), bool(flags & FLAG_CONTENT)
    if not members:
        log.info("Server Members intent is OFF in the Developer Portal → welcome via Discord join messages")
    if not content:
        log.info("Message Content intent is OFF → XP counts messages; site LFG text is not converted to cards")
    bot = NexusBot(members, content, flags)
    try:
        bot.run(token, log_handler=None)
    except discord.PrivilegedIntentsRequired:
        log.error("privileged intents rejected — restarting without them")
        return 4
    return bot.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
