#!/bin/bash
#
# @raycast.schemaVersion 1
# @raycast.title Meeting Minutes Daemon Stop
# @raycast.mode compact
# @raycast.packageName Meeting Minutes
# @raycast.icon 🛑
# @raycast.description ローカル制御サーバを停止する (daemon serve)

set -euo pipefail

PORT="${MEETING_MINUTES_DAEMON_PORT:-8765}"

server_pid=$(lsof -ti tcp:"${PORT}" 2>/dev/null || true)
if [ -z "${server_pid}" ]; then
    echo "daemon はポート ${PORT} で起動していません。"
    exit 0
fi

kill -TERM "${server_pid}"

# graceful shutdown を最大35秒待つ (LiveSession.shutdown timeout=30s + 余裕5s)
for _ in $(seq 1 70); do
    if ! kill -0 "${server_pid}" 2>/dev/null; then
        echo "daemon stopped | pid=${server_pid}"
        exit 0
    fi
    sleep 0.5
done

# SIGTERM で落ちなかった場合は強制終了
kill -KILL "${server_pid}" 2>/dev/null || true
echo "graceful shutdown が間に合わなかったため強制終了しました (SIGKILL)。" >&2
echo "daemon stopped | pid=${server_pid}"
