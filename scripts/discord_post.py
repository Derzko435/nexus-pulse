#!/usr/bin/env python3
"""NEXUS PULSE Discord bot helper — channels, alerts, LFG, freebies, snapshot.

Token from DISCORD_BOT_TOKEN or /home/box/.config/discord-bot-token.
Never prints the token.

Box routine (not GitHub Actions — the bot token never goes to GitHub):
  python scripts/discord_post.py snapshot-lfg
  python scripts/discord_post.py sync-roles     # reaction role-picker in #🎭роли
  python scripts/discord_post.py sync-events    # Discord scheduled events for top matches
  python scripts/discord_post.py post-feeds     # auto-feed via bot (only while feedMode == "bot")
  bash scripts/discord_box_sync.sh              # all of the above + commit posted state

Server setup (idempotent):   python scripts/discord_post.py setup-server
AutoMod rules (idempotent):  python scripts/discord_post.py setup-automod
Weekly activity (hourly):    python scripts/discord_post.py weekly
24/7 bot:                    bash scripts/discord_bot_run.sh start|ensure|status
Switch feeds to webhooks:    python scripts/discord_post.py setup-webhooks  (needs Manage Webhooks)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from discord_api import Bot, DiscordError  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CHANNELS_FILE = ROOT / "data" / "discord_channels.json"
FREEBIES_FILE = ROOT / "data" / "freebies.json"
LFG_SNAPSHOT_FILE = ROOT / "data" / "lfg_snapshot.json"
LFG_CHANNEL_ID_DEFAULT = "1552736838555402431"
CACHE_DIR = Path("/home/box/.cache/nexus-pulse")
TOKEN_FILE = Path("/home/box/.config/discord-bot-token")

GUILD_ID = "1552735502266794204"
API = "https://discord.com/api/v10"
MSK = timezone(timedelta(hours=3), name="MSK")

CATEGORY_NAME = "🎮 ИГРЫ"
LFG_CHANNEL = "🔎поиск-тимы"
ANNOUNCE_CHANNEL = "📢анонсы"
SITE = "https://derzko435.github.io/nexus-pulse/"
LOGO = SITE + "assets/nexus-pulse-icon.png"
EVENTS_STATE = CACHE_DIR / "discord_events.json"
ROLES_STATE = CACHE_DIR / "reaction_roles.json"
WEBHOOK_FEEDS = ["news", "deals", "freebies", "esports", "patches", "videos", "releases", "gotd"]


def load_token() -> str:
    env = (os.environ.get("DISCORD_BOT_TOKEN") or "").strip()
    if env:
        return env
    if TOKEN_FILE.is_file():
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    raise SystemExit("No Discord bot token (env DISCORD_BOT_TOKEN or token file)")


def api(method: str, path: str, token: str, body: dict | None = None) -> dict | list | None:
    try:
        return Bot(token).api(method, path, body)
    except DiscordError as e:
        raise SystemExit(str(e)) from None


def load_channels() -> dict:
    if CHANNELS_FILE.is_file():
        return json.loads(CHANNELS_FILE.read_text(encoding="utf-8"))
    return {}


def ensure_channels(token: str) -> dict:
    """Resolve LFG / announcements channel ids (by saved id first, then by name).

    Full server structure is managed by scripts/discord_setup.py (setup-server).
    """
    saved = load_channels()
    channels = api("GET", f"/guilds/{GUILD_ID}/channels", token)
    if not isinstance(channels, list):
        raise SystemExit("Unexpected channels response")
    by_id = {c["id"]: c for c in channels}

    def norm(n: str) -> str:
        import re
        return re.sub(r"[^0-9a-zа-яё-]", "", (n or "").lower())

    def find(key: str, name: str) -> str | None:
        cid = saved.get(key)
        if cid and cid in by_id:
            return cid
        for c in channels:
            if c.get("type") == 0 and norm(c.get("name")) == norm(name):
                return c["id"]
        return None

    lfg = find("channel_lfg", LFG_CHANNEL) or LFG_CHANNEL_ID_DEFAULT
    ann = find("channel_announcements", ANNOUNCE_CHANNEL)
    if not ann:
        raise SystemExit("announcements channel not found — run: python scripts/discord_post.py setup-server")
    saved.update({"guild_id": GUILD_ID, "channel_lfg": lfg, "channel_announcements": ann,
                  "updatedAt": datetime.now(MSK).isoformat(timespec="seconds")})
    CHANNELS_FILE.write_text(json.dumps(saved, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"channel_lfg": lfg, "channel_announcements": ann}, ensure_ascii=False))
    return saved


def post_message(token: str, channel_id: str, content: str = "", embeds: list | None = None) -> dict:
    body: dict = {}
    if content:
        body["content"] = content
    if embeds:
        body["embeds"] = embeds
    return api("POST", f"/channels/{channel_id}/messages", token, body)  # type: ignore[return-value]


def cmd_post_alert(token: str, args: argparse.Namespace) -> None:
    """Manual price alert → #💸скидки (deduped: same title+pct is posted once per 7 days)."""
    ch = load_channels()
    cid = (ch.get("feeds") or {}).get("deals") or ch.get("channel_announcements")
    if not cid:
        ch = ensure_channels(token)
        cid = ch["channel_announcements"]
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = CACHE_DIR / "price_alerts_posted.json"
    try:
        seen = json.loads(stamp.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        seen = {}
    key = f"{args.title.strip().lower()}|{args.pct}"
    cutoff = (datetime.now(MSK) - timedelta(days=7)).isoformat()
    seen = {k: v for k, v in seen.items() if v >= cutoff}
    if key in seen:
        print(f"Alert already posted {seen[key]} — skip")
        return
    embed = {
        "title": f"🔥 {args.title}",
        "description": f"Скидка **−{args.pct}%** · {args.store or 'store'}\n[Все скидки на NEXUS PULSE →]({SITE}#deals)",
        "url": args.url or None,
        "color": 0x00F5FF,
        "footer": {"text": "NEXUS PULSE · price alert"},
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if not embed["url"]:
        embed.pop("url")
    post_message(token, cid, embeds=[embed])
    seen[key] = datetime.now(MSK).isoformat(timespec="seconds")
    stamp.write_text(json.dumps(seen, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Posted alert ({cid})")


def cmd_post_lfg(token: str, args: argparse.Namespace) -> None:
    ch = load_channels()
    cid = ch.get("channel_lfg")
    if not cid:
        ch = ensure_channels(token)
        cid = ch["channel_lfg"]
    mic = args.mic
    if isinstance(mic, str):
        mic = mic.lower() in {"1", "true", "yes", "да", "y"}
    embed = {
        "title": f"LFG · {args.game}",
        "description": (args.note or "Ищу тиммейтов").strip(),
        "color": 0x8B5CFF,
        "fields": [
            {"name": "Ник", "value": args.nick or "Player", "inline": True},
            {"name": "Ранг", "value": args.rank or "—", "inline": True},
            {"name": "Прайм", "value": args.prime or "—", "inline": True},
            {"name": "Мик", "value": "да" if mic else "нет", "inline": True},
        ],
        "footer": {"text": "NEXUS PULSE · #поиск-тимы"},
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    post_message(token, cid, content=f"**{args.nick or 'Player'}** ищет команду", embeds=[embed])
    print(f"Posted LFG to #{LFG_CHANNEL} ({cid})")


def cmd_post_freebies(token: str, _args: argparse.Namespace) -> None:
    """Deprecated: freebies are posted by the auto-feed (#🎁раздачи, deduped)."""
    import subprocess
    subprocess.run([sys.executable, str(ROOT / "scripts" / "discord_feeds.py"), "--mode", "bot",
                    "--require-mode", "bot", "--only", "freebies"], check=False, timeout=120)


def parse_lfg_fields(content: str) -> dict:
    """Best-effort extract game/rank/prime/mic/note from free-form LFG text."""
    text = (content or "").strip()
    low = text.lower()
    game = ""
    patterns = [
        ("CS2", r"\bcs\s*2\b|\bcounter[- ]?strike\b|\bcsgo\b"),
        ("Valorant", r"\bvalorant\b|\bvalo\b"),
        ("Dota 2", r"\bdota\b"),
        ("LoL", r"\blol\b|\bleague\b|\bleague of legends\b"),
        ("Apex Legends", r"\bapex\b"),
        ("Overwatch 2", r"\boverwatch\b|\bow2\b"),
        ("Lethal Company", r"\blethal\b"),
        ("GTA V", r"\bgta\b"),
        ("Minecraft", r"\bminecraft\b|\bmc\b"),
        ("Rust", r"\brust\b"),
        ("Fortnite", r"\bfortnite\b"),
        ("PUBG", r"\bpubg\b"),
        ("Rainbow Six", r"\br6\b|\brainbow\b"),
        ("Warzone", r"\bwarzone\b|\bcod\b"),
    ]
    import re
    for name, pat in patterns:
        if re.search(pat, low):
            game = name
            break

    rank = ""
    # common: "ранг: X" / "rank: X" / "DMG" etc after game
    m = re.search(r"(?:ранг|rank)\s*[:\-–]?\s*([\w\s.+]{1,24})", text, re.I)
    if m:
        rank = m.group(1).strip()[:40]
    prime = ""
    m = re.search(r"(?:прайм|prime|время|time)\s*[:\-–]?\s*([^\n|]{2,40})", text, re.I)
    if m:
        prime = m.group(1).strip()[:60]
    mic = None
    if re.search(r"(?:без\s*мик|no\s*mic|безмикро)", low):
        mic = False
    elif re.search(r"(?:\bмик\b|\bmic\b|микрофон)", low):
        mic = True

    note = text
    if game and len(text) > 80:
        note = text
    return {
        "game": game or "",
        "rank": rank,
        "prime": prime,
        "mic": bool(mic) if mic is not None else False,
        "note": note[:280],
    }


def cmd_snapshot_lfg(token: str, _args: argparse.Namespace) -> None:
    """Fetch recent #поиск-тимы messages → data/lfg_snapshot.json (box routine).

    GitHub Actions typically has no Discord bot token — run this on the box:
      python scripts/discord_post.py snapshot-lfg
    """
    ch = load_channels()
    cid = ch.get("channel_lfg") or LFG_CHANNEL_ID_DEFAULT
    messages = api("GET", f"/channels/{cid}/messages?limit=15", token)
    if not isinstance(messages, list):
        raise SystemExit("Unexpected messages response")

    items = []
    for msg in messages:
        author = msg.get("author") or {}
        if author.get("bot"):
            # still allow bot-posted LFG embeds if they look like LFG
            embeds = msg.get("embeds") or []
            if not embeds:
                continue
            emb = embeds[0]
            title = emb.get("title") or ""
            if not title.upper().startswith("LFG") or "(собрано)" in title:
                continue
            fields = {f.get("name"): f.get("value") for f in (emb.get("fields") or []) if f.get("name")}
            nick = fields.get("Ник") or fields.get("Nick") or author.get("username") or "Bot"
            content = (emb.get("description") or title or "").strip()
            game = title.replace("LFG ·", "").replace("LFG · ", "").replace("LFG", "").strip() or ""
            extra = " · ".join(v for v in (fields.get("Режим"), fields.get("Регион")) if v and v != "—")
            if extra:
                content = f"{content} ({extra})" if content else extra
            items.append(
                {
                    "id": str(msg.get("id")),
                    "nick": nick,
                    "content": content[:280],
                    "game": game[:40],
                    "rank": (fields.get("Ранг") or fields.get("Rank") or "").replace("—", "")[:40],
                    "prime": (fields.get("Прайм") or fields.get("Время") or fields.get("Prime") or "").replace("—", "")[:60],
                    "mic": str(fields.get("Мик") or fields.get("Голос") or fields.get("Mic") or "").lower() in {"да", "yes", "true", "1"},
                    "note": content[:280],
                    "ts": msg.get("timestamp") or "",
                    "url": f"https://discord.com/channels/{GUILD_ID}/{cid}/{msg.get('id')}",
                }
            )
            continue

        content = (msg.get("content") or "").strip()
        if not content:
            continue
        parsed = parse_lfg_fields(content)
        nick = author.get("global_name") or author.get("username") or "Игрок"
        items.append(
            {
                "id": str(msg.get("id")),
                "nick": nick,
                "content": content[:280],
                "game": parsed["game"],
                "rank": parsed["rank"],
                "prime": parsed["prime"],
                "mic": parsed["mic"],
                "note": parsed["note"] if parsed["game"] else content[:280],
                "ts": msg.get("timestamp") or "",
                "url": f"https://discord.com/channels/{GUILD_ID}/{cid}/{msg.get('id')}",
            }
        )
        if len(items) >= 10:
            break

    # Prefer 5–10 newest user items (API returns newest first)
    items = items[:10]
    payload = {
        "updatedAt": datetime.now(MSK).isoformat(timespec="seconds"),
        "channel": LFG_CHANNEL,
        "items": items,
    }
    LFG_SNAPSHOT_FILE.parent.mkdir(parents=True, exist_ok=True)
    LFG_SNAPSHOT_FILE.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {LFG_SNAPSHOT_FILE} · {len(items)} items (channel #{LFG_CHANNEL})")


# ---------------------------------------------------------------- reaction roles
def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return default


def _save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def cmd_sync_roles(token: str, _args: argparse.Namespace) -> None:
    """Reaction role-picker without a gateway bot: poll reactions on the #🎭роли messages
    and add/remove the matching roles. Only removes roles this command granted itself."""
    from urllib.parse import quote
    bot = Bot(token)
    ch = load_channels()
    cid, mapping = ch.get("roles"), ch.get("reactionRoles") or {}
    if not cid or not mapping:
        raise SystemExit("roles channel / reactionRoles missing — run setup-server first")
    import fcntl
    ROLES_STATE.parent.mkdir(parents=True, exist_ok=True)
    lock = open(ROLES_STATE.with_name("reaction_roles.lock"), "w")  # shared with the 24/7 bot
    fcntl.flock(lock, fcntl.LOCK_EX)
    me = bot.api("GET", "/users/@me")
    msgs = [m for m in (bot.api("GET", f"/channels/{cid}/messages?limit=20") or [])
            if m["author"]["id"] == me["id"] and any("NEXUS PULSE · roles-" in ((e.get("footer") or {}).get("text") or "") for e in m.get("embeds") or [])]
    state = _load(ROLES_STATE, {})
    added = removed = 0
    for emoji, role_id in mapping.items():
        users: set[str] = set()
        for m in msgs:
            if not any((r.get("emoji") or {}).get("name") == emoji for r in m.get("reactions") or []):
                continue
            after = "0"
            while True:
                page = bot.api("GET", f"/channels/{cid}/messages/{m['id']}/reactions/{quote(emoji)}?limit=100&after={after}") or []
                users |= {u["id"] for u in page if not u.get("bot")}
                if len(page) < 100:
                    break
                after = page[-1]["id"]
        granted = set(state.get(role_id) or [])
        for uid in sorted(users - granted):
            try:
                bot.api("PUT", f"/guilds/{GUILD_ID}/members/{uid}/roles/{role_id}", reason="reaction role")
                granted.add(uid)
                added += 1
            except DiscordError as e:
                print(f"[warn] add role failed ({e.code})", file=sys.stderr)
        for uid in sorted(granted - users):
            try:
                bot.api("DELETE", f"/guilds/{GUILD_ID}/members/{uid}/roles/{role_id}", reason="reaction removed")
                removed += 1
            except DiscordError as e:
                if e.code != 404:
                    print(f"[warn] remove role failed ({e.code})", file=sys.stderr)
                    continue
            granted.discard(uid)
        state[role_id] = sorted(granted)
    _save(ROLES_STATE, state)
    fcntl.flock(lock, fcntl.LOCK_UN)
    lock.close()
    print(f"reaction roles: +{added} / -{removed}")


# ---------------------------------------------------------------- scheduled events
def cmd_sync_events(token: str, args: argparse.Namespace) -> None:
    """Create Discord scheduled events (external) for the next top-tier matches from
    data/matches.json; keep them in sync (start/finish/cancel). Needs CREATE_EVENTS."""
    bot = Bot(token)
    data = _load(ROOT / "data" / "matches.json", {})
    matches = {m["id"]: m for m in data.get("matches") or [] if m.get("id") and m.get("startsAt") and m.get("teamA")}
    now = datetime.now(timezone.utc)
    state = _load(EVENTS_STATE, {})  # match_id -> event_id
    events = {e["id"]: e for e in bot.api("GET", f"/guilds/{GUILD_ID}/scheduled-events") or []}
    me = bot.api("GET", "/users/@me")
    games = {"cs2": "CS2", "dota2": "Dota 2", "valorant": "Valorant", "lol": "LoL"}

    def times(m):
        st = datetime.fromisoformat(m["startsAt"]).astimezone(timezone.utc)
        try:
            bo = int(m.get("bo") or 3)
        except ValueError:
            bo = 3
        return st, st + timedelta(minutes=45 + 55 * bo)

    def iso(d):
        return d.strftime("%Y-%m-%dT%H:%M:%S.000Z")

    changed = 0
    # 1) update / close events we created
    for mid, eid in list(state.items()):
        ev = events.get(eid)
        if not ev:
            state.pop(mid)
            continue
        m = matches.get(mid)
        st_ev = ev["status"]  # 1 scheduled, 2 active, 3 completed, 4 canceled
        end_ev = datetime.fromisoformat(ev["scheduled_end_time"].replace("Z", "+00:00"))
        try:
            if m and m.get("status") == "live" and st_ev == 1:
                bot.api("PATCH", f"/guilds/{GUILD_ID}/scheduled-events/{eid}", {"status": 2}); changed += 1
            elif (m and m.get("status") == "finished") or (not m and now > end_ev):
                if st_ev == 2:
                    bot.api("PATCH", f"/guilds/{GUILD_ID}/scheduled-events/{eid}", {"status": 3}); changed += 1
                elif st_ev == 1:
                    bot.api("PATCH", f"/guilds/{GUILD_ID}/scheduled-events/{eid}", {"status": 4}); changed += 1
                state.pop(mid)
            elif m and m.get("status") == "upcoming" and st_ev == 1:
                st, en = times(m)
                if iso(st) != ev["scheduled_start_time"].replace("+00:00", ".000Z")[:24] and st > now:
                    bot.api("PATCH", f"/guilds/{GUILD_ID}/scheduled-events/{eid}",
                            {"scheduled_start_time": iso(st), "scheduled_end_time": iso(en)}); changed += 1
        except DiscordError as e:
            print(f"[warn] event {eid} update failed ({e.code})", file=sys.stderr)
            if e.code in (404, 400):
                state.pop(mid, None)

    # 2) create events for the next top matches (keep ~N upcoming)
    want = args.count
    active_upcoming = sum(1 for eid in state.values() if events.get(eid, {}).get("status") == 1)
    cands = sorted(
        [m for m in matches.values() if m.get("status") == "upcoming" and m.get("tier") == "S"
         and times(m)[0] > now + timedelta(minutes=10) and times(m)[0] < now + timedelta(days=7)
         and m["id"] not in state],
        key=lambda m: m["startsAt"])
    existing_names = {e["name"] for e in events.values() if (e.get("creator_id") == me["id"])}
    for m in cands:
        if active_upcoming >= want:
            break
        st, en = times(m)
        game = games.get(m.get("gameKey"), m.get("game") or "")
        name = f"🏆 {m['teamA']} vs {m['teamB']} · {game}"[:100]
        if name in existing_names:
            continue
        body = {
            "name": name,
            "description": (f"{m.get('event') or ''} · BO{m.get('bo') or '?'}\n"
                            f"Смотри трансляцию и следи за счётом на NEXUS PULSE: {SITE}#esports\n"
                            f"Обсуждаем в чате сервера 💬")[:1000],
            "privacy_level": 2,
            "entity_type": 3,
            "entity_metadata": {"location": f"{SITE}#esports"[:100]},
            "scheduled_start_time": iso(st),
            "scheduled_end_time": iso(en),
        }
        try:
            ev = bot.api("POST", f"/guilds/{GUILD_ID}/scheduled-events", body, reason="NEXUS PULSE match event")
            state[m["id"]] = ev["id"]
            active_upcoming += 1
            changed += 1
            print(f"+ event: {name} @ {st.astimezone(MSK):%d.%m %H:%M} MSK")
        except DiscordError as e:
            print(f"[warn] create event failed ({e.code}): {e.body[:200]}", file=sys.stderr)
            break
    _save(EVENTS_STATE, state)
    print(f"events: {changed} changes, tracking {len(state)}")


# ---------------------------------------------------------------- feeds / webhooks
def cmd_post_feeds(_token: str, args: argparse.Namespace) -> None:
    import subprocess
    cmd = [sys.executable, str(ROOT / "scripts" / "discord_feeds.py"), "--mode", "bot", "--require-mode", "bot"]
    if args.only:
        cmd += ["--only", args.only]
    raise SystemExit(subprocess.run(cmd, check=False, timeout=600).returncode)


def cmd_setup_webhooks(token: str, args: argparse.Namespace) -> None:
    """Create one «NEXUS PULSE» webhook per feed channel, store the mapping as the GitHub
    secret DISCORD_WEBHOOKS_JSON (never printed) and switch feedMode → webhook."""
    import base64
    import subprocess
    import urllib.request
    bot = Bot(token)
    ch = load_channels()
    feeds = ch.get("feeds") or {}
    avatar = None
    try:
        req = urllib.request.Request(LOGO, headers={"User-Agent": "NexusPulse/1.0"})
        raw = urllib.request.urlopen(req, timeout=20).read()
        avatar = "data:image/png;base64," + base64.b64encode(raw).decode()
    except Exception:  # noqa: BLE001
        pass
    hooks = {}
    for feed in WEBHOOK_FEEDS:
        cid = feeds.get(feed)
        if not cid:
            continue
        try:
            existing = [w for w in bot.api("GET", f"/channels/{cid}/webhooks") or [] if w.get("name") == "NEXUS PULSE" and w.get("token")]
            w = existing[0] if existing else bot.api("POST", f"/channels/{cid}/webhooks", {"name": "NEXUS PULSE", "avatar": avatar}, reason="NEXUS PULSE auto-feed")
        except DiscordError as e:
            raise SystemExit(f"webhook for {feed} failed ({e.code}) — does the bot have Manage Webhooks?") from None
        hooks[feed] = f"https://discord.com/api/webhooks/{w['id']}/{w['token']}"
    print(f"webhooks ready: {', '.join(hooks)}")
    env = dict(os.environ)
    if not env.get("GH_TOKEN") and Path("/home/box/.config/gh-token").is_file():
        env["GH_TOKEN"] = Path("/home/box/.config/gh-token").read_text().strip()
    r = subprocess.run(["gh", "secret", "set", "DISCORD_WEBHOOKS_JSON", "--repo", args.repo],
                       input=json.dumps(hooks), text=True, env=env, capture_output=True)
    if r.returncode != 0:
        raise SystemExit("gh secret set failed: " + r.stderr.strip()[:200])
    print(f"GitHub secret DISCORD_WEBHOOKS_JSON set in {args.repo}")
    ch["feedMode"] = "webhook"
    CHANNELS_FILE.write_text(json.dumps(ch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print('feedMode = "webhook" in data/discord_channels.json — commit & push it so Actions takes over')



def cmd_perms_signature(token: str, _args: argparse.Namespace) -> None:
    """Print a signature of what the bot can do (guild perms + #🛡модерация access + app intents).
    The box routine re-runs setup-server / setup-automod when it changes."""
    bot = Bot(token)
    perms, _info = bot.guild_permissions()
    mod = load_channels().get("mod")
    mod_ok = 0
    if mod:
        try:
            bot.api("GET", f"/channels/{mod}")
            mod_ok = 1
        except DiscordError:
            pass
    flags = int((bot.api("GET", "/applications/@me") or {}).get("flags") or 0) & ((0b11 << 14) | (0b11 << 18))
    print(f"{perms}:{mod_ok}:{flags}")


def bot_alive(max_age: int = 300) -> bool:
    try:
        hb = json.loads((CACHE_DIR / "bot_heartbeat.json").read_text(encoding="utf-8"))
        return datetime.now().timestamp() - int(hb.get("ts") or 0) < max_age
    except Exception:  # noqa: BLE001
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="NEXUS PULSE Discord poster")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("ensure-channels", help="Ensure ИГРЫ / поиск-тимы / анонсы")

    p_alert = sub.add_parser("post-alert")
    p_alert.add_argument("--title", required=True)
    p_alert.add_argument("--pct", required=True)
    p_alert.add_argument("--store", default="")
    p_alert.add_argument("--url", default="")

    p_lfg = sub.add_parser("post-lfg")
    p_lfg.add_argument("--game", required=True)
    p_lfg.add_argument("--rank", default="")
    p_lfg.add_argument("--prime", default="")
    p_lfg.add_argument("--mic", default="true")
    p_lfg.add_argument("--note", default="")
    p_lfg.add_argument("--nick", default="Player")

    sub.add_parser("post-freebies", help="(deprecated) → auto-feed #🎁раздачи")
    sub.add_parser("setup-server", help="Idempotent server setup (scripts/discord_setup.py)")
    sub.add_parser("sync-roles", help="Reaction role-picker → roles (box routine)")
    p_ev = sub.add_parser("sync-events", help="Scheduled events for top matches (box routine)")
    p_ev.add_argument("--count", type=int, default=3)
    p_feed = sub.add_parser("post-feeds", help="Auto-feed via bot (only while feedMode == bot)")
    p_feed.add_argument("--only", default="")
    p_wh = sub.add_parser("setup-webhooks", help="Create feed webhooks + GitHub secret, feedMode → webhook")
    p_wh.add_argument("--repo", default="Derzko435/nexus-pulse")

    sub.add_parser("setup-automod", help="Native AutoMod rules (idempotent; needs Manage Server)")
    p_wk = sub.add_parser("weekly", help="Friday poll / Sunday digest / Saturday game night (box routine)")
    p_wk.add_argument("--dry-run", action="store_true")
    sub.add_parser("perms-signature", help="print bot capability signature (box routine)")
    sub.add_parser("bot-alive", help="exit 0 if the 24/7 bot heartbeat is fresh")

    p_snap = sub.add_parser(
        "snapshot-lfg",
        help="Fetch #поиск-тимы → data/lfg_snapshot.json (run on box; Actions has no Discord token)",
    )

    args = parser.parse_args()
    if args.cmd in ("setup-automod", "weekly"):
        import subprocess
        script = "discord_automod.py" if args.cmd == "setup-automod" else "discord_weekly.py"
        extra = ["--dry-run"] if getattr(args, "dry_run", False) else []
        return subprocess.run([sys.executable, str(ROOT / "scripts" / script), *extra], check=False).returncode
    if args.cmd == "bot-alive":
        return 0 if bot_alive() else 1
    if args.cmd == "setup-server":
        import subprocess
        return subprocess.run([sys.executable, str(ROOT / "scripts" / "discord_setup.py")], check=False).returncode
    token = load_token()

    if args.cmd == "ensure-channels":
        ensure_channels(token)
    elif args.cmd == "post-alert":
        cmd_post_alert(token, args)
    elif args.cmd == "post-lfg":
        cmd_post_lfg(token, args)
    elif args.cmd == "post-freebies":
        cmd_post_freebies(token, args)
    elif args.cmd == "snapshot-lfg":
        cmd_snapshot_lfg(token, args)
    elif args.cmd == "sync-roles":
        cmd_sync_roles(token, args)
    elif args.cmd == "sync-events":
        cmd_sync_events(token, args)
    elif args.cmd == "post-feeds":
        cmd_post_feeds(token, args)
    elif args.cmd == "perms-signature":
        cmd_perms_signature(token, args)
    elif args.cmd == "setup-webhooks":
        cmd_setup_webhooks(token, args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
