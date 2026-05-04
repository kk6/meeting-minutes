#!/bin/bash
#
# @raycast.schemaVersion 1
# @raycast.title Meeting Minutes Status
# @raycast.mode compact
# @raycast.packageName Meeting Minutes
# @raycast.icon 📋
# @raycast.description 現在のセッション状態を表示する (GET /sessions/current)

set -euo pipefail

PORT="${MEETING_MINUTES_DAEMON_PORT:-8765}"
BASE="http://127.0.0.1:${PORT}"

set +e
body=$(curl --silent --fail-with-body --max-time 10 \
    "${BASE}/sessions/current" 2>/dev/null)
status=$?
set -e

case "${status}" in
    0) ;;
    7)
        echo "daemon に接続できません (${BASE})。" >&2
        echo "別ターミナルで 'uv run meeting-minutes daemon serve --port ${PORT}' を起動してください。" >&2
        exit 1
        ;;
    28)
        echo "status がタイムアウトしました (${BASE})。" >&2
        exit 1
        ;;
    *)
        echo "status に失敗しました (curl exit ${status})。" >&2
        if [ -n "${body}" ]; then echo "${body}" >&2; fi
        exit 1
        ;;
esac

JSON="${body}" python3 - <<'PY'
import json, os, sys

data = json.loads(os.environ["JSON"])
state = data.get("state", "?")
parts = [f"state={state}"]
if data.get("elapsed_seconds", 0) > 0:
    parts.append(f"elapsed={data['elapsed_seconds']}s")
if data.get("started_at"):
    parts.append(f"started={data['started_at']}")
if data.get("session_dir"):
    parts.append(f"dir={data['session_dir']}")
print(" | ".join(parts))
for err in data.get("errors") or []:
    print(f"error: {err}", file=sys.stderr)
PY
