#!/usr/bin/env python3
"""NEXUS PULSE Discord bot helper — channels, alerts, LFG, freebies, snapshot.

Token from DISCORD_BOT_TOKEN or /home/box/.config/discord-bot-token.
Never prints the token.

Box routine (not GitHub Actions — no Discord secret there):
  python scripts/discord_post.py snapshot-lfg
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

CATEGORY_NAME = "ИГРЫ"
LFG_CHANNEL = "поиск-тимы"
ANNOUNCE_CHANNEL = "анонсы"


def load_token() -> str:
    env = (os.environ.get("DISCORD_BOT_TOKEN") or "").strip()
    if env:
        return env
    if TOKEN_FILE.is_file():
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    raise SystemExit("No Discord bot token (env DISCORD_BOT_TOKEN or token file)")


def api(method: str, path: str, token: str, body: dict | None = None) -> dict | list | None:
    data = None
    headers = {
        "Authorization": f"Bot {token}",
        "User-Agent": "NexusPulseBot/1.0",
        "Content-Type": "application/json",
    }
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            if not raw:
                return None
            return json.loads(raw.decode("utf-8"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", "replace")
        raise SystemExit(f"Discord API {method} {path} → {e.code}: {err[:500]}") from e


def load_channels() -> dict:
    if CHANNELS_FILE.is_file():
        return json.loads(CHANNELS_FILE.read_text(encoding="utf-8"))
    return {}


def save_channels(data: dict) -> None:
    CHANNELS_FILE.parent.mkdir(parents=True, exist_ok=True)
    # ids only — no secrets
    clean = {k: str(v) for k, v in data.items() if v is not None}
    CHANNELS_FILE.write_text(json.dumps(clean, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def ensure_channels(token: str) -> dict:
    channels = api("GET", f"/guilds/{GUILD_ID}/channels", token)
    if not isinstance(channels, list):
        raise SystemExit("Unexpected channels response")

    by_name: dict[str, dict] = {}
    categories: dict[str, dict] = {}
    for ch in channels:
        name = ch.get("name") or ""
        if ch.get("type") == 4:
            categories[name] = ch
        else:
            by_name[name] = ch

    cat = categories.get(CATEGORY_NAME)
    if not cat:
        cat = api(
            "POST",
            f"/guilds/{GUILD_ID}/channels",
            token,
            {"name": CATEGORY_NAME, "type": 4, "reason": "NEXUS PULSE setup"},
        )
        print(f"Created category {CATEGORY_NAME}")
    cat_id = str(cat["id"])

    def ensure_text(name: str) -> str:
        existing = by_name.get(name)
        if existing:
            # move under category if needed
            if str(existing.get("parent_id") or "") != cat_id and name == LFG_CHANNEL:
                try:
                    api(
                        "PATCH",
                        f"/channels/{existing['id']}",
                        token,
                        {"parent_id": cat_id},
                    )
                except SystemExit as exc:
                    print(f"[warn] could not reparent #{name}: {exc}", file=sys.stderr)
            return str(existing["id"])
        created = api(
            "POST",
            f"/guilds/{GUILD_ID}/channels",
            token,
            {
                "name": name,
                "type": 0,
                "parent_id": cat_id,
                "topic": "NEXUS PULSE · auto",
                "reason": "NEXUS PULSE setup",
            },
        )
        print(f"Created text channel #{name}")
        return str(created["id"])

    # Prefer existing анонсы anywhere; create under ИГРЫ if missing
    announce = by_name.get(ANNOUNCE_CHANNEL)
    if announce:
        announce_id = str(announce["id"])
    else:
        announce_id = ensure_text(ANNOUNCE_CHANNEL)

    lfg_id = ensure_text(LFG_CHANNEL)

    out = {
        "guild_id": GUILD_ID,
        "category_games": cat_id,
        "channel_lfg": lfg_id,
        "channel_announcements": announce_id,
        "channel_lfg_name": LFG_CHANNEL,
        "channel_announcements_name": ANNOUNCE_CHANNEL,
        "updatedAt": datetime.now(MSK).isoformat(timespec="seconds"),
    }
    save_channels(out)
    print(json.dumps({k: out[k] for k in ("channel_lfg", "channel_announcements", "category_games")}, ensure_ascii=False))
    return out


def post_message(token: str, channel_id: str, content: str = "", embeds: list | None = None) -> dict:
    body: dict = {}
    if content:
        body["content"] = content
    if embeds:
        body["embeds"] = embeds
    return api("POST", f"/channels/{channel_id}/messages", token, body)  # type: ignore[return-value]


def cmd_post_alert(token: str, args: argparse.Namespace) -> None:
    ch = load_channels()
    cid = ch.get("channel_announcements")
    if not cid:
        ch = ensure_channels(token)
        cid = ch["channel_announcements"]
    embed = {
        "title": f"🔥 {args.title}",
        "description": f"Скидка **−{args.pct}%** · {args.store or 'store'}",
        "url": args.url or None,
        "color": 0x00F5FF,
        "footer": {"text": "NEXUS PULSE · price alert"},
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    if not embed["url"]:
        embed.pop("url")
    post_message(token, cid, embeds=[embed])
    print(f"Posted alert to #{ANNOUNCE_CHANNEL} ({cid})")


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


def freebies_fingerprint(payload: dict) -> str:
    items = payload.get("items") or []
    parts = []
    for it in items:
        parts.append(f"{it.get('id')}|{it.get('title')}|{it.get('until')}|{it.get('store')}")
    return "\n".join(sorted(parts))


def cmd_post_freebies(token: str, _args: argparse.Namespace) -> None:
    if not FREEBIES_FILE.is_file():
        raise SystemExit(f"Missing {FREEBIES_FILE}")
    payload = json.loads(FREEBIES_FILE.read_text(encoding="utf-8"))
    items = payload.get("items") or []
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = CACHE_DIR / "freebies_last_posted.json"
    fp = freebies_fingerprint(payload)
    if stamp.is_file():
        try:
            prev = json.loads(stamp.read_text(encoding="utf-8"))
            if prev.get("fingerprint") == fp:
                print("Freebies unchanged — skip Discord post")
                return
        except Exception:  # noqa: BLE001
            pass

    ch = load_channels()
    cid = ch.get("channel_announcements")
    if not cid:
        ch = ensure_channels(token)
        cid = ch["channel_announcements"]

    lines = []
    for it in items[:12]:
        until = it.get("until") or "—"
        url = it.get("claimUrl") or ""
        title = it.get("title") or "?"
        store = it.get("store") or ""
        if url:
            lines.append(f"• **{title}** ({store}) до {until}\n  {url}")
        else:
            lines.append(f"• **{title}** ({store}) до {until}")
    desc = "\n".join(lines) if lines else "Список пуст"
    if len(desc) > 3900:
        desc = desc[:3900] + "…"
    embed = {
        "title": "🎁 Халява · бесплатные игры",
        "description": desc,
        "color": 0x3DFF9A,
        "footer": {"text": f"NEXUS PULSE · {payload.get('source', 'freebies')}"},
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
    post_message(token, cid, embeds=[embed])
    stamp.write_text(
        json.dumps(
            {
                "fingerprint": fp,
                "postedAt": datetime.now(MSK).isoformat(timespec="seconds"),
                "count": len(items),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Posted freebies ({len(items)} items) to #{ANNOUNCE_CHANNEL} ({cid})")


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
            if not title.upper().startswith("LFG"):
                continue
            fields = {f.get("name"): f.get("value") for f in (emb.get("fields") or []) if f.get("name")}
            nick = fields.get("Ник") or fields.get("Nick") or author.get("username") or "Bot"
            content = (emb.get("description") or title or "").strip()
            game = title.replace("LFG ·", "").replace("LFG · ", "").replace("LFG", "").strip() or ""
            items.append(
                {
                    "id": str(msg.get("id")),
                    "nick": nick,
                    "content": content[:280],
                    "game": game[:40],
                    "rank": (fields.get("Ранг") or fields.get("Rank") or "")[:40],
                    "prime": (fields.get("Прайм") or fields.get("Prime") or "")[:60],
                    "mic": str(fields.get("Мик") or fields.get("Mic") or "").lower() in {"да", "yes", "true", "1"},
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

    sub.add_parser("post-freebies")

    p_snap = sub.add_parser(
        "snapshot-lfg",
        help="Fetch #поиск-тимы → data/lfg_snapshot.json (run on box; Actions has no Discord token)",
    )

    args = parser.parse_args()
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
