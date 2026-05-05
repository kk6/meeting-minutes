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

if [ -z "${MEETING_MINUTES_REPO:-}" ]; then
    echo "MEETING_MINUTES_REPO が設定されていません。" >&2
    echo "Raycast の Configure Script > Environment Variables で MEETING_MINUTES_REPO にリポジトリの絶対パスを設定してください。" >&2
    exit 1
fi

if [ ! -d "${MEETING_MINUTES_REPO}" ]; then
    echo "リポジトリが見つかりません: ${MEETING_MINUTES_REPO}" >&2
    exit 1
fi

# 二重起動防止: PID ファイルで自分が起動した daemon のみを確認する
if [ -f "${PID_FILE}" ]; then
    existing_pid=$(cat "${PID_FILE}")
    if kill -0 "${existing_pid}" 2>/dev/null; then
        echo "daemon は既に起動しています (PID=${existing_pid})。" >&2
        echo "停止するには serve-stop.sh を実行してください。" >&2
        exit 1
    else
        # プロセスが存在しない古い PID ファイルを削除して続行
        rm -f "${PID_FILE}"
    fi
fi

mkdir -p "${LOG_DIR}"

nohup uv run --directory "${MEETING_MINUTES_REPO}" meeting-minutes daemon serve --port "${PORT}" >> "${LOG_FILE}" 2>&1 &
server_pid=$!
echo "${server_pid}" > "${PID_FILE}"

# uvicorn の起動（モデルロードを含む）を最大60秒待つ
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

echo "daemon が ${i}秒以内に応答しませんでした。ログを確認してください: ${LOG_FILE}" >&2
exit 1
