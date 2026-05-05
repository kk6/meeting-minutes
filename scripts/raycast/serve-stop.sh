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
PID_FILE="${HOME}/Library/Logs/meeting-minutes/daemon.${PORT}.pid"

# 停止対象 PID を決定する: PID ファイル優先、なければポートで LISTEN している
# meeting-minutes daemon serve を採用する
target_pid=""
if [ -f "${PID_FILE}" ]; then
    pid_from_file=$(cat "${PID_FILE}")
    if kill -0 "${pid_from_file}" 2>/dev/null && \
       ps -p "${pid_from_file}" -o args= 2>/dev/null | grep -q "meeting-minutes daemon serve"; then
        target_pid="${pid_from_file}"
    else
        # プロセスが存在しない、または PID が別プロセスに再利用されている
        rm -f "${PID_FILE}"
    fi
fi

if [ -z "${target_pid}" ]; then
    listen_pid=$(lsof -nP -iTCP:"${PORT}" -sTCP:LISTEN -t 2>/dev/null || true)
    if [ -n "${listen_pid}" ] && \
       ps -p "${listen_pid}" -o args= 2>/dev/null | grep -q "meeting-minutes daemon serve"; then
        target_pid="${listen_pid}"
    elif [ -n "${listen_pid}" ]; then
        echo "ポート ${PORT} は meeting-minutes daemon serve 以外のプロセス (PID=${listen_pid}) が使用しています。" >&2
        echo "このスクリプトでは停止しません。" >&2
        exit 1
    fi
fi

if [ -z "${target_pid}" ]; then
    echo "daemon は起動していません (port=${PORT})。"
    exit 0
fi

kill -TERM "${target_pid}"

# graceful shutdown を最大35秒待つ (LiveSession.shutdown timeout=30s + 余裕5s)
for _ in $(seq 1 70); do
    if ! kill -0 "${target_pid}" 2>/dev/null; then
        rm -f "${PID_FILE}"
        echo "daemon stopped | pid=${target_pid}"
        exit 0
    fi
    sleep 0.5
done

# SIGTERM で落ちなかった場合は強制終了
kill -KILL "${target_pid}" 2>/dev/null || true
rm -f "${PID_FILE}"
echo "graceful shutdown が間に合わなかったため強制終了しました (SIGKILL)。" >&2
echo "daemon stopped | pid=${target_pid}"
