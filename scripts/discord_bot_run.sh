#!/usr/bin/env bash
# NEXUS PULSE 24/7 Discord bot — supervisor (box only; there is no systemd on the box).
#   bash scripts/discord_bot_run.sh start    # start in background if not running
#   bash scripts/discord_bot_run.sh ensure   # watchdog: (re)start if dead/hung or code changed
#   bash scripts/discord_bot_run.sh stop | restart | status
#   bash scripts/discord_bot_run.sh run      # foreground restart loop (used by start)
set -u
DEPLOY="${NP_DEPLOY:-/workspace/nexus-pulse-deploy}"
VENV="${NP_BOT_VENV:-/home/box/.local/share/nexus-pulse-bot/venv}"
CACHE="/home/box/.cache/nexus-pulse"
LOG="$CACHE/bot.log"
PIDF="$CACHE/bot_runner.pid"
HB="$CACHE/bot_heartbeat.json"
mkdir -p "$CACHE"

runner_alive() { [ -f "$PIDF" ] && kill -0 "$(cat "$PIDF")" 2>/dev/null; }
hb_field() { python3 -c "import json,sys;print(json.load(open('$HB')).get('$1',''))" 2>/dev/null; }

ensure_venv() {
  if [ ! -x "$VENV/bin/python" ] || ! "$VENV/bin/python" -c "import discord" 2>/dev/null; then
    python3 -m venv "$VENV" && "$VENV/bin/pip" install -q "discord.py>=2.4" >>"$LOG" 2>&1
  fi
}

do_run() {
  echo $$ > "$PIDF"
  rm -f "$CACHE/bot.stop"
  backoff=5
  while true; do
    [ -f "$CACHE/bot.stop" ] && break
    if [ -f "$LOG" ] && [ "$(stat -c%s "$LOG")" -gt 5000000 ]; then mv -f "$LOG" "$LOG.1"; fi
    ensure_venv
    start=$(date +%s)
    "$VENV/bin/python" "$DEPLOY/scripts/discord_bot.py" >>"$LOG" 2>&1
    code=$?
    [ -f "$CACHE/bot.stop" ] && break
    if [ $(( $(date +%s) - start )) -gt 300 ] || [ "$code" = 3 ]; then backoff=5; else backoff=$(( backoff * 2 > 300 ? 300 : backoff * 2 )); fi
    echo "$(date '+%F %T') bot exited (code $code), restart in ${backoff}s" >>"$LOG"
    sleep "$backoff"
  done
  rm -f "$PIDF"
}

do_start() {
  if runner_alive; then echo "bot: already running (runner $(cat "$PIDF"))"; return 0; fi
  rm -f "$CACHE/bot.stop"
  setsid nohup bash "$0" run >/dev/null 2>&1 < /dev/null &
  sleep 1
  echo "bot: started (runner $(cat "$PIDF" 2>/dev/null))"
}

do_stop() {
  touch "$CACHE/bot.stop"
  local bpid; bpid="$(hb_field pid)"
  if runner_alive; then kill "$(cat "$PIDF")" 2>/dev/null; fi
  [ -n "$bpid" ] && kill "$bpid" 2>/dev/null
  pkill -f "$DEPLOY/scripts/discord_bot.py" 2>/dev/null
  sleep 2
  rm -f "$PIDF"
  echo "bot: stopped"
}

do_ensure() {
  if ! runner_alive; then echo "[watchdog] bot runner not running → start"; do_start; return; fi
  local age=999999 ts now started code want
  now=$(date +%s)
  ts="$(hb_field ts)"; [ -n "$ts" ] && age=$(( now - ts ))
  started=$(stat -c %Y "$PIDF" 2>/dev/null || echo "$now")
  if [ "$age" -gt 300 ] && [ $(( now - started )) -gt 300 ]; then
    echo "[watchdog] heartbeat ${age}s old → restart"; do_stop; do_start; return
  fi
  code="$(hb_field code)"
  want="$(sha256sum "$DEPLOY/scripts/discord_bot.py" | cut -c1-16)"
  if [ -n "$code" ] && [ "$code" != "$want" ]; then
    echo "[watchdog] bot code updated → reload"; kill "$(hb_field pid)" 2>/dev/null  # runner restarts it
    return
  fi
  echo "bot: ok (heartbeat ${age}s ago)"
}

case "${1:-status}" in
  run) do_run ;;
  start) do_start ;;
  stop) do_stop ;;
  restart) do_stop; do_start ;;
  ensure) do_ensure ;;
  status)
    if runner_alive; then echo "runner $(cat "$PIDF") alive"; else echo "runner not running"; fi
    [ -f "$HB" ] && echo "heartbeat: $(cat "$HB")" ;;
  *) echo "usage: $0 start|stop|restart|ensure|status|run"; exit 2 ;;
esac
