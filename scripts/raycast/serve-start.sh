#!/bin/bash
#
# @raycast.schemaVersion 1
# @raycast.title Meeting Minutes Daemon Start
# @raycast.mode compact
# @raycast.packageName Meeting Minutes
# @raycast.icon 🚀
# @raycast.description ローカル制御サーバを起動する (daemon serve)

set -euo pipefail

PORT="${MEETING_MINUTES_DAEMON_PORT:-8765}"
BASE="http://127.0.0.1:${PORT}"
LOG_DIR="${HOME}/Library/Logs/meeting-minutes"
LOG_FILE="${LOG_DIR}/daemon.log"
PID_FILE="${LOG_DIR}/daemon.pid"

export PATH="${HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:${PATH}"

if ! command -v meeting-minutes >/dev/null 2>&1; then
    echo "meeting-minutes コマンドが見つかりません。" >&2
    echo "'uv tool install .' を実行し、Raycast が参照する PATH にインストール先を含めてください。" >&2
    exit 1
fi

# 二重起動防止: PID ファイルを確認する
if [ -f "${PID_FILE}" ]; then
    existing_pid=$(cat "${PID_FILE}")
    if kill -0 "${existing_pid}" 2>/dev/null && \
       ps -p "${existing_pid}" -o args= 2>/dev/null | grep -q "meeting-minutes daemon serve"; then
        echo "daemon は既に起動しています (PID=${existing_pid})。" >&2
        echo "停止するには serve-stop.sh を実行してください。" >&2
        exit 1
    else
        # プロセスが存在しない、または PID が別プロセスに再利用されている
        rm -f "${PID_FILE}"
    fi
fi

mkdir -p "${LOG_DIR}"

nohup meeting-minutes daemon serve --port "${PORT}" >> "${LOG_FILE}" 2>&1 &
server_pid=$!
echo "${server_pid}" > "${PID_FILE}"

# uvicorn の起動が完了するまで最大60秒待つ
for i in $(seq 1 60); do
    if ! kill -0 "${server_pid}" 2>/dev/null; then
        rm -f "${PID_FILE}"
        echo "daemon が起動直後に終了しました。ログを確認してください: ${LOG_FILE}" >&2
        exit 1
    fi
    if curl --silent --fail --max-time 1 "${BASE}/sessions/current" >/dev/null 2>&1; then
        echo "daemon started | port=${PORT} | pid=${server_pid} | log=${LOG_FILE}"
        exit 0
    fi
    sleep 1
done

echo "daemon が ${i}秒以内に応答しませんでした (PID=${server_pid})。" >&2
echo "プロセスは残っているため、ログ確認後に必要に応じて serve-stop.sh で停止してください: ${LOG_FILE}" >&2
exit 1
