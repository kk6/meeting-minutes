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

- `meeting-minutes` コマンドが使えること
  - 事前に以下で確認してください。

    ```bash
    meeting-minutes --help
    ```

  - 未インストールの場合は、このプロジェクトをインストールしてください。

    ```bash
    uv tool install .
    ```

  - `serve-start.sh` は Raycast から見つかりやすいように `~/.local/bin`、
    `/opt/homebrew/bin`、`/usr/local/bin` を PATH に追加してから
    `meeting-minutes daemon serve` を起動します。

## 使い方の流れ

1. `Meeting Minutes Daemon Start` で daemon を起動する。
2. `Meeting Minutes Start` で録音を開始し、`Meeting Minutes Status` で状態を確認、`Meeting Minutes Stop` で録音を停止する。
3. 会議が終わったら `Meeting Minutes Daemon Stop` で daemon を停止する。

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

## 設定

Raycast の Script Commands には、各コマンドの設定画面で任意の環境変数を登録する
`Environment Variables` 項目はありません。公式の Script Commands 仕様で設定できる
メタデータは `@raycast.argument1` などの引数、表示名、出力モード、実行ディレクトリなどです。

| Key                           | 必須 | デフォルト | 説明                                             |
| ----------------------------- | ---- | ---------- | ------------------------------------------------ |
| `MEETING_MINUTES_DAEMON_PORT` |      | `8765`     | daemon が待ち受けるポート番号                     |

通常は何も設定せずに使えます。

daemon ポートを変更したい場合は、Raycast を起動するプロセス側で
`MEETING_MINUTES_DAEMON_PORT` を渡すか、各スクリプト内のデフォルト値を直接編集してください。

## 出力例

```
state=running | started=2026-05-04T10:00:00+09:00 | dir=/path/to/output/<session>
```

エラー時は stderr に詳細を出して終了コード 1 で終わる。daemon が起動していない
場合は接続エラーとして案内メッセージが表示される。
