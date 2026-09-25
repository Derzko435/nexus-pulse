#!/usr/bin/env bash
# NEXUS PULSE — Discord box routine (run hourly on the box; the bot token never leaves it).
#   * auto-feed via bot while data/discord_channels.json has "feedMode": "bot"
#     (after `discord_post.py setup-webhooks` GitHub Actions takes over the feed)
#   * scheduled events for top matches, reaction role-picker
#   * commits data/discord_posted.json (dedupe state) to the repo
set -uo pipefail
DEPLOY="${NP_DEPLOY:-/workspace/nexus-pulse-deploy}"
SRC="${NP_SRC:-/workspace/gaming-portal}"
cd "$DEPLOY" || exit 1
if [ -z "${GH_TOKEN:-}" ] && [ -f /home/box/.config/gh-token ]; then
  GH_TOKEN="$(cat /home/box/.config/gh-token)"; export GH_TOKEN
fi

git fetch -q origin main && git rebase -q --autostash origin/main || { git rebase --abort 2>/dev/null; echo "[warn] rebase failed — using local tree"; }

python3 scripts/discord_feeds.py --mode bot --require-mode bot || echo "[warn] feeds failed"
python3 scripts/discord_post.py sync-events || echo "[warn] events failed"
python3 scripts/discord_post.py sync-roles || echo "[warn] roles failed"

if [ -n "$(git status --porcelain -- data/discord_posted.json)" ]; then
  git add data/discord_posted.json
  # [skip ci]: the state file is not needed on the site, no Pages redeploy for it
  git commit -q -m "chore(discord): posted state [skip ci]"
  for i in 1 2 3; do
    git pull -q --rebase --autostash origin main && git push -q origin HEAD:main && break
    echo "[warn] push attempt $i failed"; sleep $((i * 5))
  done
fi
cp -f data/discord_posted.json data/discord_channels.json "$SRC/data/" 2>/dev/null || true
echo "discord box sync done $(TZ=Europe/Moscow date '+%F %H:%M') MSK"
