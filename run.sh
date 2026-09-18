#!/bin/bash
# Launch the menu bar app.
#
#   ./run.sh                 run here; Ctrl-C (or Quit in the menu) stops it
#   ./run.sh --background    detach, so the icon stays after this window closes
#   ./run.sh --stop          quit a copy that's already running
#
# macOS only lets programs it launches for you (Login Items, LaunchAgents, app
# bundles) read Desktop, Documents, and Downloads if you grant permission first.
# Starting from a terminal sidesteps that, which is why --background exists.

HERE="$(cd "$(dirname "$0")" && pwd)"
PY="$HERE/.venv/bin/python"
APP="$HERE/menubar_flash.py"

running_pid() { pgrep -f "^.*Python .*${APP}$" 2>/dev/null | head -1; }

case "${1:-}" in
  -b|--background)
    if [ -n "$(running_pid)" ]; then
      echo "Already running (pid $(running_pid))."
      exit 0
    fi
    [ -x "$PY" ] || { echo "No virtualenv yet. Run:  python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt" >&2; exit 1; }
    nohup "$PY" "$APP" >/dev/null 2>&1 &
    PID=$!
    sleep 1.5  # long enough for a failed start to have exited
    if kill -0 "$PID" 2>/dev/null; then
      echo "Running in the background (pid $PID). Close this window whenever you like."
      echo "To stop it: ./run.sh --stop, or right-click the menu bar icon and choose Quit."
    else
      echo "Failed to start. Run ./run.sh on its own to see the error." >&2
      exit 1
    fi
    ;;
  --stop)
    PID="$(running_pid)"
    if [ -z "$PID" ]; then echo "Not running."; else kill "$PID" && echo "Stopped (pid $PID)."; fi
    ;;
  -h|--help)
    sed -n '3,6p' "$0" | sed 's/^# \{0,1\}//'
    ;;
  *)
    exec "$PY" "$APP" "$@"
    ;;
esac
