#!/bin/bash
#
# @raycast.schemaVersion 1
# @raycast.title Meeting Minutes Stop
# @raycast.mode compact
# @raycast.packageName Meeting Minutes
# @raycast.icon ⏹️
# @raycast.description 録音セッションを停止する (POST /sessions/stop)

set -euo pipefail

PORT="${MEETING_MINUTES_DAEMON_PORT:-8765}"
BASE="http://127.0.0.1:${PORT}"

set +e
body=$(curl --silent --fail-with-body --max-time 10 \
    -X POST "${BASE}/sessions/stop" 2>/dev/null)
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
        echo "stop がタイムアウトしました (${BASE})。" >&2
        exit 1
        ;;
    *)
        echo "stop に失敗しました (curl exit ${status})。" >&2
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
if data.get("transcript_path"):
    parts.append(f"transcript={data['transcript_path']}")
print(" | ".join(parts))
for err in data.get("errors") or []:
    print(f"error: {err}", file=sys.stderr)
PY
