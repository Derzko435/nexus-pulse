#!/usr/bin/env python3
"""Minimal Discord REST v10 client shared by NEXUS PULSE scripts.

- Bot token: env DISCORD_BOT_TOKEN or /home/box/.config/discord-bot-token (box only).
- Never prints tokens or webhook URLs.
- Respects 429 retry_after.
"""
from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://discord.com/api/v10"
UA = "DiscordBot (https://derzko435.github.io/nexus-pulse, 1.0)"
TOKEN_FILE = Path("/home/box/.config/discord-bot-token")
GUILD_ID = "1552735502266794204"

PERM = {
    "CREATE_INSTANT_INVITE": 1 << 0,
    "ADMINISTRATOR": 1 << 3,
    "MANAGE_CHANNELS": 1 << 4,
    "MANAGE_GUILD": 1 << 5,
    "ADD_REACTIONS": 1 << 6,
    "VIEW_CHANNEL": 1 << 10,
    "SEND_MESSAGES": 1 << 11,
    "MANAGE_MESSAGES": 1 << 13,
    "EMBED_LINKS": 1 << 14,
    "ATTACH_FILES": 1 << 15,
    "READ_MESSAGE_HISTORY": 1 << 16,
    "MENTION_EVERYONE": 1 << 17,
    "USE_EXTERNAL_EMOJIS": 1 << 18,
    "CONNECT": 1 << 20,
    "MOVE_MEMBERS": 1 << 24,
    "MANAGE_ROLES": 1 << 28,
    "MANAGE_WEBHOOKS": 1 << 29,
    "MANAGE_EVENTS": 1 << 33,
    "CREATE_PUBLIC_THREADS": 1 << 35,
    "CREATE_PRIVATE_THREADS": 1 << 36,
    "SEND_MESSAGES_IN_THREADS": 1 << 38,
    "MODERATE_MEMBERS": 1 << 40,
    "CREATE_EVENTS": 1 << 44,
    "SEND_POLLS": 1 << 49,
    "PIN_MESSAGES": 1 << 51,
}


class DiscordError(RuntimeError):
    def __init__(self, method: str, path: str, code: int, body: str):
        self.code = code
        self.body = body
        try:
            self.json = json.loads(body)
        except Exception:  # noqa: BLE001
            self.json = {}
        # path never contains secrets for bot calls; webhook paths are masked by caller
        super().__init__(f"Discord {method} {path} -> {code}: {body[:400]}")


def load_token() -> str:
    env = (os.environ.get("DISCORD_BOT_TOKEN") or "").strip()
    if env:
        return env
    if TOKEN_FILE.is_file():
        return TOKEN_FILE.read_text(encoding="utf-8").strip()
    raise SystemExit("No Discord bot token (env DISCORD_BOT_TOKEN or token file)")


def request(method: str, url: str, headers: dict, body: dict | None = None, label: str = "", tries: int = 6):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    h = {"User-Agent": UA, "Content-Type": "application/json"}
    h.update(headers)
    last = None
    for _ in range(tries):
        req = urllib.request.Request(url, data=data, headers=h, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                # be gentle with per-route buckets
                if resp.headers.get("X-RateLimit-Remaining") == "0":
                    try:
                        time.sleep(float(resp.headers.get("X-RateLimit-Reset-After") or 1) + 0.1)
                    except ValueError:
                        time.sleep(1)
                return json.loads(raw.decode("utf-8")) if raw else None
        except urllib.error.HTTPError as e:
            txt = e.read().decode("utf-8", "replace")
            if e.code == 429:
                try:
                    wait = float(json.loads(txt).get("retry_after", 2))
                except Exception:  # noqa: BLE001
                    wait = 2.0
                time.sleep(min(wait, 60) + 0.25)
                last = DiscordError(method, label, e.code, txt)
                continue
            if e.code in (500, 502, 503, 504):
                time.sleep(2)
                last = DiscordError(method, label, e.code, txt)
                continue
            raise DiscordError(method, label, e.code, txt) from None
        except urllib.error.URLError as e:
            last = RuntimeError(f"network error {method} {label}: {e.reason}")
            time.sleep(2)
    raise last or RuntimeError("request failed")


class Bot:
    def __init__(self, token: str | None = None):
        self._token = token or load_token()

    def api(self, method: str, path: str, body: dict | None = None, reason: str | None = None):
        headers = {"Authorization": f"Bot {self._token}"}
        if reason:
            headers["X-Audit-Log-Reason"] = urllib.request.quote(reason)
        return request(method, API + path, headers, body, label=path)

    def guild_permissions(self, guild_id: str = GUILD_ID) -> tuple[int, dict]:
        me = self.api("GET", "/users/@me")
        member = self.api("GET", f"/guilds/{guild_id}/members/{me['id']}")
        roles = self.api("GET", f"/guilds/{guild_id}/roles")
        perms = 0
        mine = set(member.get("roles") or []) | {guild_id}
        for r in roles:
            if r["id"] in mine:
                perms |= int(r["permissions"])
        if perms & PERM["ADMINISTRATOR"]:
            perms = (1 << 53) - 1
        return perms, {"me": me, "member": member, "roles": roles}


def webhook_execute(url: str, body: dict, wait: bool = True):
    """POST to a webhook URL. The URL is a secret: never logged."""
    sep = "&" if "?" in url else "?"
    full = url + (f"{sep}wait=true" if wait else "")
    return request("POST", full, {}, body, label="/webhooks/[REDACTED]")
