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
PID_FILE="${HOME}/Library/Logs/meeting-minutes/daemon.pid"

if [ ! -f "${PID_FILE}" ]; then
    # PID ファイルなし: ポートを確認して手動起動の daemon を案内する
    if lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN -t >/dev/null 2>&1; then
        echo "PID ファイルが見つかりません。serve-start.sh 以外で起動した daemon serve がポート ${PORT} で動いています。" >&2
        echo "ターミナルで Ctrl+C を押して停止してください。" >&2
        exit 1
    fi
    echo "daemon は起動していません。"
    exit 0
fi

server_pid=$(cat "${PID_FILE}")

if ! kill -0 "${server_pid}" 2>/dev/null; then
    echo "daemon は既に停止しています (PID=${server_pid})。"
    rm -f "${PID_FILE}"
    exit 0
fi

# PID が meeting-minutes のプロセスであることを確認してから停止する
if ! ps -p "${server_pid}" -o args= 2>/dev/null | grep -q "meeting-minutes"; then
    echo "PID ${server_pid} は meeting-minutes daemon ではありません。PID ファイルが古い可能性があります。" >&2
    echo "${PID_FILE} を手動で削除してから serve-start.sh を再実行してください。" >&2
    exit 1
fi

kill -TERM "${server_pid}"

# graceful shutdown を最大35秒待つ (LiveSession.shutdown timeout=30s + 余裕5s)
for _ in $(seq 1 70); do
    if ! kill -0 "${server_pid}" 2>/dev/null; then
        rm -f "${PID_FILE}"
        echo "daemon stopped | pid=${server_pid}"
        exit 0
    fi
    sleep 0.5
done

# SIGTERM で落ちなかった場合は強制終了
kill -KILL "${server_pid}" 2>/dev/null || true
rm -f "${PID_FILE}"
echo "graceful shutdown が間に合わなかったため強制終了しました (SIGKILL)。" >&2
echo "daemon stopped | pid=${server_pid}"
