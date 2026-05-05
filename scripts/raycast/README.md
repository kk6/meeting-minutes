# Raycast Script Commands

Raycast から `meeting-minutes daemon` を制御するためのサンプルスクリプトです。
`serve-start.sh` / `serve-stop.sh` でサーバ自体の起動・停止を行い、
`start.sh` / `stop.sh` / `status.sh` で録音セッションを制御します。

| ファイル          | 役割                           | 仕組み                     |
| ----------------- | ------------------------------ | -------------------------- |
| `serve-start.sh`  | ローカル制御サーバを起動する   | `daemon serve` をバックグラウンドで起動 |
| `serve-stop.sh`   | ローカル制御サーバを停止する   | SIGTERM → SIGKILL でプロセス終了 |
| `start.sh`        | 録音セッションを開始する       | `POST /sessions/start`   |
| `stop.sh`         | 録音セッションを停止する       | `POST /sessions/stop`    |
| `status.sh`       | 現在のセッション状態を表示する | `GET /sessions/current`  |

## 前提

- `python3` と `curl` が使えること
  - macOS でも環境によっては `python3` がプリインストールされていません。
  - 事前に以下で確認してください。

    ```bash
    python3 --version
    curl --version
    ```

  - `python3` が見つからない場合は、Python 3.12+ を別途インストールしてください。
    例: Homebrew を使う場合

    ```bash
    brew install python@3.12
    ```

  - Raycast から `python3` を見つけられない場合は、Raycast が参照する PATH に
    インストール先が含まれているか確認してください。

- `uv` が使えること（`serve-start.sh` が必要とする）
  - 事前に以下で確認してください。

    ```bash
    uv --version
    ```

  - インストールされていない場合は [uv 公式ドキュメント](https://docs.astral.sh/uv/getting-started/installation/) を参照してください。
  - Raycast から `uv` を見つけられない場合は、Raycast が参照する PATH にインストール先が含まれているか確認してください。
    `uv` を Homebrew でインストールした場合は `/opt/homebrew/bin` が PATH に含まれている必要があります。

## 使い方の流れ

1. `Meeting Minutes Daemon Start` で daemon を起動する。
2. `Meeting Minutes Start` で録音を開始し、`Meeting Minutes Status` で状態を確認、`Meeting Minutes Stop` で録音を停止する。
3. 会議が終わったら `Meeting Minutes Daemon Stop` で daemon を停止する。

ターミナルから `uv run meeting-minutes daemon serve` で手動起動した daemon も `serve-stop.sh` で停止できる。

## Raycast に取り込む手順

1. 各スクリプトに実行権限を付与する。

   ```bash
   chmod +x scripts/raycast/*.sh
   ```

2. Raycast を開き `Settings → Extensions → Script Commands → Add Script Directory` で
   このディレクトリの絶対パス（例: `/Users/<you>/CascadeProjects/meeting-minutes/scripts/raycast`）を追加する。

3. Raycast のルート検索から以下のコマンドが呼び出せることを確認する。

   - `Meeting Minutes Daemon Start`
   - `Meeting Minutes Daemon Stop`
   - `Meeting Minutes Start`
   - `Meeting Minutes Stop`
   - `Meeting Minutes Status`

## 環境変数

Raycast の各 Script Command 設定画面 → `Configure Script` → `Environment Variables` で設定する。

| Key                           | 必須 | デフォルト | 説明                                             |
| ----------------------------- | ---- | ---------- | ------------------------------------------------ |
| `MEETING_MINUTES_REPO`        | ✓    | —          | リポジトリの絶対パス（`serve-start.sh` 必須）    |
| `MEETING_MINUTES_DAEMON_PORT` |      | `8765`     | daemon が待ち受けるポート番号                     |

設定例:

| Key                           | Value                                          |
| ----------------------------- | ---------------------------------------------- |
| `MEETING_MINUTES_REPO`        | `/Users/yourname/CascadeProjects/meeting-minutes` |
| `MEETING_MINUTES_DAEMON_PORT` | `8765`                                         |

## 出力例

```
state=running | started=2026-05-04T10:00:00+09:00 | dir=/path/to/output/<session>
```

エラー時は stderr に詳細を出して終了コード 1 で終わる。daemon が起動していない
場合は接続エラーとして案内メッセージが表示される。
