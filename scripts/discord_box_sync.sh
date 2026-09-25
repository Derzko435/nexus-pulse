#!/usr/bin/env bash
# NEXUS PULSE — Discord box routine (run hourly on the box; the bot token never leaves it).
#   * watchdog for the 24/7 bot (scripts/discord_bot_run.sh ensure)
#   * when the bot's permissions / intents change → setup-server (+ AutoMod) automatically
#   * AutoMod rules kept in sync, auto-feed via bot while feedMode == "bot"
#   * scheduled events for top matches, weekly poll / digest / game night
#   * reaction roles: real time by the bot; hourly fallback only while the bot is down
#   * LFG snapshot for the site, Telegram autopost (when configured)
#   * commits data/discord_posted.json (+ telegram state, LFG snapshot) to the repo
set -uo pipefail
DEPLOY="${NP_DEPLOY:-/workspace/nexus-pulse-deploy}"
SRC="${NP_SRC:-/workspace/gaming-portal}"
CACHE="/home/box/.cache/nexus-pulse"
mkdir -p "$CACHE"
cd "$DEPLOY" || exit 1
if [ -z "${GH_TOKEN:-}" ] && [ -f /home/box/.config/gh-token ]; then
  GH_TOKEN="$(cat /home/box/.config/gh-token)"; export GH_TOKEN
fi

git fetch -q origin main && git rebase -q --autostash origin/main || { git rebase --abort 2>/dev/null; echo "[warn] rebase failed — using local tree"; }

bash scripts/discord_bot_run.sh ensure || echo "[warn] bot watchdog failed"

# permissions / intents changed (e.g. after a re-invite) → apply the full server setup once
sig="$(python3 scripts/discord_post.py perms-signature 2>/dev/null || true)"
if [ -n "$sig" ] && [ "$sig" != "$(cat "$CACHE/perms_signature" 2>/dev/null)" ]; then
  echo "bot permissions changed → setup-server"
  python3 scripts/discord_post.py setup-server && echo "$sig" > "$CACHE/perms_signature"
fi
python3 scripts/discord_post.py setup-automod || echo "[warn] automod failed"

python3 scripts/discord_feeds.py --mode bot --require-mode bot || echo "[warn] feeds failed"
python3 scripts/discord_post.py sync-events || echo "[warn] events failed"
python3 scripts/discord_post.py weekly || echo "[warn] weekly failed"
if python3 scripts/discord_post.py bot-alive; then
  echo "reaction roles: handled live by the bot"
else
  python3 scripts/discord_post.py sync-roles || echo "[warn] roles failed"
fi

# Telegram (only when a token + channel are configured on the box)
if [ -f /home/box/.config/telegram-bot-token ]; then
  TELEGRAM_BOT_TOKEN="$(cat /home/box/.config/telegram-bot-token)" python3 scripts/telegram_post.py --runner box || echo "[warn] telegram failed"
fi

# LFG snapshot for the site feed: keep only real changes (not a new timestamp)
python3 scripts/discord_post.py snapshot-lfg >/dev/null || echo "[warn] lfg snapshot failed"
python3 - <<'PY' || git checkout -q -- data/lfg_snapshot.json 2>/dev/null
import json, subprocess, sys
try:
    old = json.loads(subprocess.run(["git", "show", "HEAD:data/lfg_snapshot.json"], capture_output=True, text=True).stdout or "{}")
except Exception:
    old = {}
new = json.load(open("data/lfg_snapshot.json", encoding="utf-8"))
sys.exit(0 if (old.get("items") or []) != (new.get("items") or []) else 1)
PY

# server config: commit only real changes (setup-server rewrites "updatedAt" every run)
python3 - <<'PY' || git checkout -q -- data/discord_channels.json 2>/dev/null
import json, subprocess, sys
old = json.loads(subprocess.run(["git", "show", "HEAD:data/discord_channels.json"], capture_output=True, text=True).stdout or "{}")
new = json.load(open("data/discord_channels.json", encoding="utf-8"))
old.pop("updatedAt", None); new.pop("updatedAt", None)
sys.exit(0 if old != new else 1)
PY

committed=0
state_files=""
for f in data/discord_posted.json data/telegram_posted.json; do
  [ -f "$f" ] && [ -n "$(git status --porcelain -- "$f")" ] && state_files="$state_files $f"
done
if [ -n "$state_files" ]; then
  git add $state_files
  # [skip ci]: state files are not needed on the site, no Pages redeploy for them
  git commit -q -m "chore(discord): posted state [skip ci]" && committed=1
fi
site_files=""
for f in data/lfg_snapshot.json data/discord_channels.json; do
  [ -n "$(git status --porcelain -- "$f")" ] && site_files="$site_files $f"
done
if [ -n "$site_files" ]; then
  git add $site_files
  # last commit = head of the push → Pages redeploys (the site shows the LFG feed)
  git commit -q -m "chore(discord): LFG feed / server config" && committed=1
fi
if [ "$committed" = 1 ]; then
  for i in 1 2 3; do
    git pull -q --rebase --autostash origin main && git push -q origin HEAD:main && break
    echo "[warn] push attempt $i failed"; sleep $((i * 5))
  done
fi
cp -f data/discord_posted.json data/discord_channels.json data/lfg_snapshot.json "$SRC/data/" 2>/dev/null || true
[ -f data/telegram_posted.json ] && cp -f data/telegram_posted.json "$SRC/data/" 2>/dev/null
echo "discord box sync done $(TZ=Europe/Moscow date '+%F %H:%M') MSK"
