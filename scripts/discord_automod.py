#!/usr/bin/env python3
"""NEXUS PULSE — native Discord AutoMod rules (idempotent, safe to re-run).

  python scripts/discord_automod.py            # create / update rules
  python scripts/discord_automod.py --check    # show what exists / would change
  (also: python scripts/discord_post.py setup-automod)

Rules are matched by name («NP · …») and updated in place, never duplicated.
Needs MANAGE_GUILD; timeouts are added only when the bot has MODERATE_MEMBERS
(the hourly box routine re-runs this whenever the bot's permissions change).
Alerts go to #🛡модерация if the bot can see it, else to the bot-visible #🔒служебное.
The bot role, «Админ» and «Модератор» are exempt (members with Manage Server are
always exempt by Discord itself), so the auto-feed is never blocked.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from discord_api import GUILD_ID, PERM, Bot, DiscordError  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
CHANNELS_FILE = ROOT / "data" / "discord_channels.json"
INVITE_CODE_DEFAULT = "7JvfzNrt4x"

# Russian mat / insults. AutoMod wildcard rules: "word" = whole word, "word*" = prefix,
# "*word*" = substring. Prefix forms are used to avoid false positives
# («учеба», «страхуй», «мандарин» stay allowed).
RU_BAD = [
    "хуй*", "хуе*", "хуя*", "хуи*", "хуё*", "нахуй*", "нахуя", "похуй*", "похуи*", "охуе*", "охуи*", "ахуе*",
    "*пизд*", "еба*", "ебу*", "ебл*", "ебн*", "ебош*", "ёб*", "уеба*", "уебо*", "уёб*", "заеба*", "выеб*",
    "долбоеб*", "долбоёб*", "долбаеб*", "далбаеб*", "бля", "блять", "бляд*", "блят*", "выблядок",
    "сука", "суки", "сучар*", "пидор*", "пидар*", "пидр*", "педик*", "гандон*", "гондон*", "мудак*",
    "мудил*", "мудоз*", "шлюх*", "залуп*", "хуесос*", "чмо", "чмошн*", "дебил*", "даун", "дауны",
    "ублюд*", "мразь", "мрази", "уебище", "уёбище", "еблан*", "ебанат*", "конч*ный", "кончен*",
    "сдохни", "убей себя", "убейся", "мать ебал", "твою мать",
]
EN_BAD = ["kys", "kill yourself", "retard*", "faggot*", "nigg*", "motherfuck*", "fuck*", "*fucking*", "cunt*"]
SCAM_WORDS = [
    "free nitro", "nitro free", "free discord nitro", "discord nitro for free", "nitro giveaway",
    "бесплатный нитро", "бесплатное нитро", "бесплатная нитро", "нитро бесплатно", "нитро на месяц бесплатно",
    "steam gift 50$", "free steam gift", "раздаю скины", "раздача скинов бесплатно", "забери скины",
    "i'm leaving cs", "giving away my inventory", "ухожу из кс раздаю", "first 100 users",
    "продам аккаунт", "куплю аккаунт",
]
SCAM_REGEX = [
    # look-alike domains of discord / steam
    r"(?i)\b(dlscord|disc0rd|discorcl|dicsord|discrod|discordd|d1scord|discord-?gift|discord-?nitro|discordgifts?)\.[a-z]{2,}",
    r"(?i)\b(steamcommunlty|stearncommunity|steamcomunity|steamcommnuity|steancommunity|steamcommunity-?[a-z0-9]+|steampowered-?[a-z0-9]+|stearnpowered)\.[a-z]{2,}",
]


def invite_regex() -> list[str]:
    return [r"(?i)(discord(app)?\.com/invite|discord\.gg|dsc\.gg|discord\.me|discord\.io|invite\.gg)/[a-z0-9-]+"]


def load_channels() -> dict:
    try:
        return json.loads(CHANNELS_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def build_rules(ch: dict, alert_channel: str | None, can_timeout: bool) -> list[dict]:
    code = ch.get("invite_code") or INVITE_CODE_DEFAULT

    def actions(msg: str, timeout: int = 0) -> list[dict]:
        acts = [{"type": 1, "metadata": {"custom_message": msg[:150]}}]
        if alert_channel:
            acts.append({"type": 2, "metadata": {"channel_id": alert_channel}})
        if timeout and can_timeout:
            acts.append({"type": 3, "metadata": {"duration_seconds": timeout}})
        return acts

    return [
        {"name": "NP · Спам", "trigger_type": 3, "trigger_metadata": {},
         "actions": actions("Похоже на спам — сообщение скрыто. Если это ошибка, напиши модераторам.")},
        {"name": "NP · Флуд упоминаниями", "trigger_type": 5,
         "trigger_metadata": {"mention_total_limit": 5, "mention_raid_protection_enabled": True},
         "actions": actions("Слишком много упоминаний в одном сообщении (максимум 5).", timeout=600)},
        {"name": "NP · Мат и оскорбления", "trigger_type": 1,
         "trigger_metadata": {"keyword_filter": RU_BAD + EN_BAD, "allow_list": ["бляха", "сучок"]},
         "actions": actions("Давай без мата и оскорблений 🙏 Сообщение не отправлено — перефразируй, пожалуйста.")},
        {"name": "NP · Скам и накрутка", "trigger_type": 1,
         "trigger_metadata": {"keyword_filter": SCAM_WORDS, "regex_patterns": SCAM_REGEX},
         "actions": actions("Похоже на скам/фишинг — сообщение заблокировано. Не переходи по таким ссылкам!", timeout=3600)},
        {"name": "NP · Чужие приглашения", "trigger_type": 1,
         "trigger_metadata": {"regex_patterns": invite_regex(),
                              "allow_list": [f"discord.gg/{code}", f"discord.com/invite/{code}",
                                             f"discordapp.com/invite/{code}", f"https://discord.gg/{code}",
                                             f"https://discord.com/invite/{code}"]},
         "actions": actions("Реклама других серверов запрещена (правило 2).")},
        {"name": "NP · Фильтр Discord", "trigger_type": 4,
         "trigger_metadata": {"presets": [1, 2, 3], "allow_list": []},
         "actions": actions("Сообщение скрыто фильтром сервера. Давай без грубостей 🙏")},
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    bot = Bot()
    perms, info = bot.guild_permissions()
    if not perms & PERM["MANAGE_GUILD"]:
        print("automod: MANAGE_GUILD missing — skipped (will apply automatically once granted)")
        return 3
    can_timeout = bool(perms & PERM["MODERATE_MEMBERS"])
    ch = load_channels()
    alert = None
    for key in ("mod", "staff"):  # #🛡модерация if the bot can see it, else the bot's #🔒служебное
        cid = ch.get(key)
        if not cid:
            continue
        try:
            bot.api("GET", f"/channels/{cid}")
            alert = cid
            break
        except DiscordError:
            continue
    if not alert:
        print("automod: no staff channel visible to the bot — alerts off (run setup-server)")
    me = info["me"]
    exempt_roles = [r["id"] for r in info["roles"]
                    if r["name"] in ("Админ", "Модератор") or (r.get("managed") and (r.get("tags") or {}).get("bot_id") == me["id"])]
    exempt_channels = [c for c in [ch.get("mod"), ch.get("staff")] if c]
    existing = {r["name"]: r for r in bot.api("GET", f"/guilds/{GUILD_ID}/auto-moderation/rules") or []}
    created = updated = same = 0
    for rule in build_rules(ch, alert, can_timeout):
        body = dict(rule, event_type=1, enabled=True, exempt_roles=exempt_roles, exempt_channels=exempt_channels)
        cur = existing.get(rule["name"])
        if cur:
            if cur.get("trigger_type") != rule["trigger_type"]:
                print(f"[warn] {rule['name']}: trigger type differs — leaving as is")
                continue
            patch = {k: v for k, v in body.items() if k != "trigger_type"}
            if rule["trigger_type"] == 3:
                patch.pop("trigger_metadata", None)

            def norm(r):
                return json.dumps({"a": sorted(json.dumps(x, sort_keys=True) for x in r.get("actions") or []),
                                   "m": {k: sorted(v) if isinstance(v, list) else v for k, v in (r.get("trigger_metadata") or {}).items()
                                         if k in (rule.get("trigger_metadata") or {})},
                                   "er": sorted(r.get("exempt_roles") or []), "ec": sorted(r.get("exempt_channels") or []),
                                   "en": r.get("enabled")}, sort_keys=True, ensure_ascii=False)
            if norm(cur) == norm(body):
                same += 1
                continue
            if args.check:
                print(f"[check] would update {rule['name']}")
                continue
            try:
                bot.api("PATCH", f"/guilds/{GUILD_ID}/auto-moderation/rules/{cur['id']}", patch, reason="NEXUS PULSE automod")
                updated += 1
            except DiscordError as e:
                print(f"[warn] update {rule['name']} failed ({e.code}): {e.body[:300]}")
        else:
            if args.check:
                print(f"[check] would create {rule['name']}")
                continue
            try:
                bot.api("POST", f"/guilds/{GUILD_ID}/auto-moderation/rules", body, reason="NEXUS PULSE automod")
                created += 1
            except DiscordError as e:
                print(f"[warn] create {rule['name']} failed ({e.code}): {e.body[:300]}")
    print(f"automod: +{created} created, ~{updated} updated, ={same} unchanged · alerts={'on' if alert else 'off'} · timeouts={'on' if can_timeout else 'off (needs Timeout Members)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
