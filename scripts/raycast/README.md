# Raycast Script Commands

Raycast から `meeting-minutes daemon` を制御するためのサンプルスクリプトです。
内部では curl で `http://127.0.0.1:8765` の HTTP API を直接叩きます。

| ファイル     | 役割                          | 対応エンドポイント       |
| ------------ | ----------------------------- | ------------------------ |
| `start.sh`   | 録音セッションを開始する      | `POST /sessions/start`   |
| `stop.sh`    | 録音セッションを停止する      | `POST /sessions/stop`    |
| `status.sh`  | 現在のセッション状態を表示する | `GET /sessions/current`  |

## 前提

- macOS の `python3`（標準で利用可能）と `curl` が使えること
- 別ターミナルで daemon を起動しておくこと

  ```bash
  uv run meeting-minutes daemon serve
  ```

## Raycast に取り込む手順

1. 各スクリプトに実行権限を付与する。

   ```bash
   chmod +x scripts/raycast/*.sh
   ```

2. Raycast を開き `Settings → Extensions → Script Commands → Add Script Directory` で
   このディレクトリの絶対パス（例: `/Users/<you>/CascadeProjects/meeting-minutes/scripts/raycast`）を追加する。

3. Raycast のルート検索から `Meeting Minutes Start` / `Meeting Minutes Stop` /
   `Meeting Minutes Status` が呼び出せることを確認する。

## ポートを変える場合

daemon を `--port 9000` などで起動している場合は、Raycast 側で各スクリプトに
環境変数 `MEETING_MINUTES_DAEMON_PORT` を設定する。

Raycast の各 Script Command 設定画面 → `Configure Script` → `Environment Variables` で
以下を追加する。

| Key                              | Value  |
| -------------------------------- | ------ |
| `MEETING_MINUTES_DAEMON_PORT`    | `9000` |

未設定時は `8765` が使われる。

## 出力例

```
state=running | started=2026-05-04T10:00:00+09:00 | dir=/path/to/output/<session>
```

エラー時は stderr に詳細を出して終了コード 1 で終わる。daemon が起動していない
場合は接続エラーとして案内メッセージが表示される。
