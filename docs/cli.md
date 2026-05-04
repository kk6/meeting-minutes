# CLI説明書

`meeting-minutes` は、Macローカルでリアルタイム文字起こしと議事録生成を行うCLIです。

## 前提

リポジトリ内で開発しながら使う場合:

```bash
uv sync
# 以降は `uv run meeting-minutes ...` で呼び出す
```

任意ディレクトリ・Raycast 等から呼び出したい場合はグローバルインストール:

```bash
uv tool install .
# 以降は `meeting-minutes ...` で直接呼び出せる
```

必要なもの:

- ffmpeg
- Ollama
- Ollama上の議事録生成モデル。デフォルトは `gemma4`
- 会議音声を取り込む場合はBlackHoleなどの仮想オーディオデバイス

### 設定ファイル auto-discovery

`--config` を渡さない場合、`$XDG_CONFIG_HOME/meeting-minutes/config.toml`
（未設定時は `~/.config/meeting-minutes/config.toml`）を自動で読み込みます。
存在しなければ環境変数と組み込み既定値だけで動作します。

雛形の生成・参照先の確認・編集は `config` サブコマンドで完結します。詳しくは [config](#config) を参照してください。

`output.base_dir` の既定値は `$XDG_DATA_HOME/meeting-minutes/output/`
（未設定時は `~/.local/share/meeting-minutes/output/`）です。

明示的に上書きする方法:

- 設定ファイルで指定: TOML 中の相対パスは設定ファイル自身のディレクトリ基準で解決されます。
  例えば雛形 `src/meeting_minutes/config/templates/config.example.toml` を `--config` で渡すと、
  `base_dir = "output"` がそのディレクトリ基準で解決されます（リポジトリ内では
  `src/meeting_minutes/config/templates/output/` になるので、通常は `meeting-minutes config init`
  で `~/.config/meeting-minutes/config.toml` にコピーしてから編集します）。
- 環境変数で指定: `MEETING_MINUTES_OUTPUT__BASE_DIR=path` を設定すると env 経路で
  上書きされ、相対パスは cwd 基準（=従来どおり）として扱われます。設定ファイル
  と異なり anchor されません。
- 任意の場所に固定したい場合は絶対パスを指定してください。

## 基本フロー

1. 環境を確認する
2. 入力デバイスを確認する
3. `live` でリアルタイム文字起こしを実行する
4. 必要に応じて `clean` で文字起こしを整形する
5. `draft` または `finalize` で議事録Markdownを生成する

以下の例の `<base_dir>` は `output.base_dir` の解決結果（XDG 既定なら `~/.local/share/meeting-minutes/output`、雛形 `src/meeting_minutes/config/templates/config.example.toml` を `--config` で渡せばそのディレクトリ基準）。
本ドキュメント内の他コマンド例も同様に読み替えてください。

```bash
uv run meeting-minutes check
uv run meeting-minutes devices
uv run meeting-minutes live --device "BlackHole 64ch"
uv run meeting-minutes draft <base_dir>/2026-04-28_193822_live_meeting/transcript_live.md
uv run meeting-minutes finalize <base_dir>/2026-04-28_193822_live_meeting/transcript_live.md
# 任意: clean で整形してから finalize すると議事録の入力品質が上がる
uv run meeting-minutes clean <base_dir>/2026-04-28_193822_live_meeting/transcript_live.md
uv run meeting-minutes finalize <base_dir>/2026-04-28_193822_live_meeting/transcript_clean.md
```

## check

実行環境を確認します。

```bash
uv run meeting-minutes check
```

確認内容:

- `ffmpeg` が利用可能か
- `sounddevice` で入力デバイスを取得できるか
- BlackHoleが認識されているか
- Ollama APIに接続できるか
- 指定したOllamaモデルが存在するか
- `faster-whisper` をimportできるか

設定ファイルを指定する場合:

```bash
uv run meeting-minutes check --config ./src/meeting_minutes/config/templates/config.example.toml
```

## devices

入力音声デバイスを一覧表示します。

```bash
uv run meeting-minutes devices
```

表示される情報:

- device index
- device name
- 入力チャンネル数
- デフォルトサンプルレート
- BlackHoleかどうか

`live` では、ここに出た名前またはindexを指定します。

## live

指定した入力デバイスから音声を取得し、VADで検出した発話単位で文字起こしします。

```bash
uv run meeting-minutes live --device "BlackHole 64ch"
```

デバイスindexで指定する場合:

```bash
uv run meeting-minutes live --device-index 1
```

主なオプション:

| オプション | 既定値 | 説明 |
| --- | --- | --- |
| `--device` | 設定ファイルまたは既定入力 | 入力デバイス名 |
| `--device-index` | 設定ファイルまたは既定入力 | 入力デバイスindex |
| `--sample-rate` | `16000` | サンプルレート |
| `--channels` | `1` | 入力チャンネル数 |
| `--chunk-seconds` | `8` | 音声取得チャンクの秒数 |
| `--language` | `ja` | Whisperに渡す言語 |
| `--whisper-model` | `small` | faster-whisperのモデル名 |
| `--output-dir` | 設定ファイルまたは XDG 既定 (`~/.local/share/meeting-minutes/output`) | セッション出力先 |
| `--ollama-model` | `gemma4` | 自動ドラフト生成で使うOllamaモデル |
| `--config` | なし | TOML設定ファイル |
| `--no-save` | `false` | transcriptを保存しない |
| `--no-save-audio` | `false` | 録音WAVを保存しない |
| `--no-vad` | `false` | VADによる発話単位分割を無効化し、固定秒数チャンクで文字起こし |
| `--continue-on-overflow` | `false` | 音声取り逃がし時も `metadata.json` に記録して続行 |
| `--abort-on-overflow` | 設定ファイルまたは `true` | 音声取り逃がし時に停止 |
| `--draft-interval-minutes` | `0` | 指定分ごとにドラフト生成。`0`なら無効 |

出力先の例（`<base_dir>` は `output.base_dir` の解決結果。XDG 既定なら `~/.local/share/meeting-minutes/output`）:

```text
<base_dir>/
  2026-04-28_193822_live_meeting/
    transcript_live.md
    audio_live.wav
    minutes_draft.md
    metadata.json
```

`transcript_live.md` の本文は、後から音声と照合しやすいように `[開始 - 終了] text` 形式で保存されます。

停止するには `Ctrl+C` を押します。停止時に `metadata.json` が保存されます。

VADは既定で有効です。無音が続いたところで発話終了とみなし、短すぎる音声はノイズとして捨てます。長すぎる発話は `vad.max_speech_seconds` で強制分割します。固定秒数チャンクの従来動作に戻したい場合は `--no-vad` または設定ファイルの `vad.enabled = false` を使います。

音声入力の処理が追いつかず一部ブロックを取り逃がした場合、既定では停止します。長時間会議で少量の欠落を許容して継続したい場合は `--continue-on-overflow` または設定ファイルの `audio.abort_on_overflow = false` を使います。継続時も取り逃がしは `metadata.json` の `errors` に記録されます。

### BlackHole 64chを使う場合

通常はそのまま使えます。

```bash
uv run meeting-minutes live --device "BlackHole 64ch"
```

入力チャンネル数を明示したい場合:

```bash
uv run meeting-minutes live --device "BlackHole 64ch" --channels 2
```

## daemon

HTTP API 経由で録音セッションを制御するモードです。`daemon serve` でサーバを起動し、別ターミナルから `daemon start` / `daemon stop` / `daemon status` で操作します。

### 基本的な使い方

```bash
# ターミナル1: サーバを起動する
uv run meeting-minutes daemon serve

# ターミナル2: 録音を開始・停止する
uv run meeting-minutes daemon start
uv run meeting-minutes daemon stop
uv run meeting-minutes daemon status
```

### daemon serve

ローカル制御サーバを起動します。

```bash
uv run meeting-minutes daemon serve
```

ポートを変更する場合:

```bash
uv run meeting-minutes daemon serve --port 9000
```

設定ファイルを指定する場合:

```bash
uv run meeting-minutes daemon serve --config ./src/meeting_minutes/config/templates/config.example.toml
```

| オプション | 既定値 | 説明 |
| --- | --- | --- |
| `--port` | `8765` | 待ち受けポート |
| `--config` | なし | TOML設定ファイル |

`127.0.0.1` のみに bind するため、外部ホストから TCP 接続することはできません。ブラウザ経由の CSRF は Origin ヘッダー検証（localhost / 127.0.0.1 以外を 403 で拒否）と CORS ポリシーの組み合わせで防いでいます。停止するには `Ctrl+C` を押します。

起動直後に以下の INFO ログを出します。どの設定で動いているかを最初の数行で把握できます。

```text
INFO: config source: auto_discovered (/Users/<you>/.config/meeting-minutes/config.toml)
INFO: output base_dir: /Users/<you>/.local/share/meeting-minutes/output
INFO: listening on http://127.0.0.1:8765
```

`config source` は次のいずれかの形式で出ます。

- `explicit (<path>)` — `--config` で明示指定された場合
- `auto_discovered (<path>)` — XDG 既定パスを auto-discovery で拾った場合
- `defaults (no config file at <would-be-path>)` — 設定ファイルが無く組み込み既定値だけで動いている場合

#### API ドキュメント

daemon 起動中は以下の URL で対話型ドキュメントを参照できます（`--port` を変更した場合は `8765` を置き換えてください）。

| URL | 説明 |
| --- | --- |
| http://127.0.0.1:8765/docs | Swagger UI（ブラウザから直接リクエストを試せる） |
| http://127.0.0.1:8765/redoc | ReDoc（読みやすいリファレンス形式） |

curl でのリクエスト例（`--port` を変更した場合は `8765` を置き換えてください）:

```bash
# セッション開始
curl -s -X POST http://127.0.0.1:8765/sessions/start \
  -H "Content-Type: application/json" \
  -d '{}' | jq

# セッション停止
curl -s -X POST http://127.0.0.1:8765/sessions/stop | jq

# 現在の状態確認
curl -s http://127.0.0.1:8765/sessions/current | jq
```

### daemon start

録音セッションを開始します。事前に `daemon serve` でサーバを起動しておく必要があります。

```bash
uv run meeting-minutes daemon start
```

| オプション | 既定値 | 説明 |
| --- | --- | --- |
| `--port` | `8765` | daemon のポート |
| `--draft-interval-minutes` | `0` | 指定分ごとにドラフト生成。`0` なら無効 |

### daemon stop

実行中の録音セッションを停止します。

```bash
uv run meeting-minutes daemon stop
```

| オプション | 既定値 | 説明 |
| --- | --- | --- |
| `--port` | `8765` | daemon のポート |

### daemon status

現在のセッション状態を表示します。

```bash
uv run meeting-minutes daemon status
```

| オプション | 既定値 | 説明 |
| --- | --- | --- |
| `--port` | `8765` | daemon のポート |

### Raycast Script Commands

Raycast から daemon を start / stop / status できるサンプルスクリプトを `scripts/raycast/` に置いています。curl で HTTP API を直接叩くため、起動オーバーヘッドはほぼありません。導入手順は [scripts/raycast/README.md](../scripts/raycast/README.md) を参照してください。

## clean

文字起こしのフィラー・言い直し・重複・句読点不足を LLM で機械的に整形し、読みやすいテキストとして保存します。

要約や解釈は行わず、原文に近い形のまま整えます。整形済み transcript は `draft` や `finalize` にそのまま渡せます。

```bash
uv run meeting-minutes clean <base_dir>/2026-04-28_193822_live_meeting/transcript_live.md
```

既定の出力先:

```text
先頭 transcript と同じディレクトリの transcript_clean.md
```

出力先を指定する場合:

```bash
uv run meeting-minutes clean <base_dir>/current/transcript_live.md --output <base_dir>/current/clean.md
```

整形済み transcript を最終議事録生成に使う場合:

```bash
uv run meeting-minutes clean <base_dir>/current/transcript_live.md
uv run meeting-minutes finalize <base_dir>/current/transcript_clean.md
```

設定ファイルで挙動を変更できます（`[cleaning]` セクション参照）。

## draft

途中までの文字起こしから、議事録ドラフトを生成します。

```bash
uv run meeting-minutes draft <base_dir>/2026-04-28_193822_live_meeting/transcript_live.md
```

途中で `live` を再起動した場合など、複数の transcript を順番に指定できます。

```bash
uv run meeting-minutes draft \
  <base_dir>/session-1/transcript_live.md \
  <base_dir>/session-2/transcript_live.md
```

既定の出力先:

```text
先頭 transcript と同じディレクトリの minutes_draft.md
```

出力先を指定する場合:

```bash
uv run meeting-minutes draft <base_dir>/current/transcript_live.md --output <base_dir>/current/draft.md
```

設定ファイルを使う場合:

```bash
uv run meeting-minutes draft <base_dir>/current/transcript_live.md --config ./src/meeting_minutes/config/templates/config.example.toml
```

## finalize

会議全体の文字起こしから、最終議事録を生成します。

```bash
uv run meeting-minutes finalize <base_dir>/2026-04-28_193822_live_meeting/transcript_live.md
```

途中で `live` を再起動した場合など、複数の transcript を順番に指定できます。

```bash
uv run meeting-minutes finalize \
  <base_dir>/session-1/transcript_live.md \
  <base_dir>/session-2/transcript_live.md
```

既定の出力先:

```text
先頭 transcript と同じディレクトリの minutes.md
```

出力先を指定する場合:

```bash
uv run meeting-minutes finalize <base_dir>/current/transcript_live.md --output <base_dir>/current/minutes.md
```

## config

設定ファイルの初期化・参照先確認・編集をまとめた管理コマンドです。

### config init

XDG 既定パス (`~/.config/meeting-minutes/config.toml`) に同梱の雛形を書き出します。
既存ファイルがある場合は `--force` を付けないと上書きしません。

```bash
meeting-minutes config init
meeting-minutes config init --force   # 既存を上書きする
```

### config path

現在 `--config` 未指定時に参照される config パスを表示します。

```bash
meeting-minutes config path
# 例: source: auto_discovered
#     path:   /Users/<you>/.config/meeting-minutes/config.toml
```

`--config` を指定するとそのパスを `explicit` 表示で確認できます。設定ファイルが
未作成のときは `defaults (no config file)` と `would-be path:`（`config init` が
作成するパス）を出します。

### config show

env / TOML / 既定値を解決した後の `AppConfig` を出力します。

```bash
meeting-minutes config show               # TOML 形式（既定）
meeting-minutes config show --format json # JSON 形式
meeting-minutes config show --config ./foo.toml
```

`AppConfig` の None フィールド（`audio.device` 未指定など）は TOML が null を
表現できないため出力から省かれます。

### config edit

auto-discovery で解決された config を `$EDITOR` で開きます。`$EDITOR` 未設定時は
macOS の `open(1)` でデフォルトアプリに渡します。設定ファイルが未作成のときは
先に `config init` するよう案内します。

```bash
meeting-minutes config edit
```

## 設定ファイル

TOML形式の設定ファイルを指定できます。

```bash
uv run meeting-minutes live --config ./src/meeting_minutes/config/templates/config.example.toml
```

CLIオプションは設定ファイルより優先されます。

```toml
[audio]
device = "BlackHole 64ch"
# device_index = 0
sample_rate = 16000
channels = 1
chunk_seconds = 8
# true: 音声取り逃がし時に停止する。false: metadataに記録して続行する。
abort_on_overflow = true

[vad]
enabled = true
frame_ms = 30
speech_threshold = 0.01
silence_seconds = 0.8
min_speech_seconds = 0.3
max_speech_seconds = 15.0
padding_seconds = 0.2

[transcription]
whisper_model = "small"
language = "ja"
device = "cpu"
compute_type = "int8"

[summarization]
ollama_base_url = "http://localhost:11434"
ollama_model = "gemma4"
temperature = 0.2
num_ctx = 8192
timeout_seconds = 600
think = false

[output]
base_dir = "output"
save_transcript = true
save_audio = true

[chunking]
chunk_size = 6000
chunk_overlap = 500

[cleaning]
chunk_size = 4000
output_filename = "transcript_clean.md"

[vocabulary]
# glossary_file = "vocab/glossary.txt"
# participants_file = "vocab/participants.txt"
max_prompt_chars = 200
```

### 要約・整形（summarization）

`[summarization]` セクションで Ollama の接続先やモデルを設定します。

| キー | 既定値 | 説明 |
| --- | --- | --- |
| `ollama_base_url` | `http://localhost:11434` | Ollama API のベース URL |
| `ollama_model` | `gemma4` | 使用するモデル名 |
| `temperature` | `0.2` | 生成の温度。低いほど安定した出力 |
| `num_ctx` | `8192` | コンテキストウィンドウのトークン数 |
| `timeout_seconds` | `600` | API リクエストのタイムアウト秒数 |
| `think` | `false` | thinking 対応モデルの推論ステップ出力の有効化。`false` 推奨 |

`think = true` にすると、gemma4 等の thinking 対応モデルが推論ステップを出力します。ただし推論トークンが `num_ctx` を使い切り応答が空になる場合があるため、整形・要約タスクでは `false` のままにしてください。

### 語彙ヒント（vocabulary）

会議ごとに用意した語彙ファイルを指定すると、固有名詞・参加者名の誤認識を抑制し、議事録の表記揺れも減らせます。

- `glossary_file`: 1行1語の用語集（製品名、社内略語、専門用語など）
- `participants_file`: 1行1名の参加者一覧
- ファイル形式: UTF-8テキスト、空行と `#` で始まる行は無視
- `max_prompt_chars`: 文字起こしモデルに渡すヒントの文字数上限（既定 200）。先頭ほど強く効くため、超過分は末尾から切り詰めます。`0` で無効化。
- `max_summary_chars`: 要約プロンプトへの語彙注入の文字数上限（既定 1000）。上限を超える語彙は末尾から項目単位で切り落とします。`0` で無効化。

ヒントは文字起こし時の `initial_prompt` と要約プロンプトの両方に注入されます。ファイル不在は警告のみで処理は継続します。

機微情報を含む可能性があるため、語彙ファイルは `.gitignore` に登録するなどしてリポジトリにコミットしないでください。

## トラブルシュート

### 入力デバイスが見つからない

```bash
uv run meeting-minutes devices
```

デバイス名を完全一致で指定するか、`--device-index` を使ってください。

### 文字起こしが少ない、または不自然

まずBlackHoleやmacOS側の音声ルーティングを確認してください。

```bash
uv run meeting-minutes live --device "BlackHole 64ch" --channels 2
```

音声は拾えているが精度が低い場合は、モデルを大きくします。

```bash
uv run meeting-minutes live --device "BlackHole 64ch" --whisper-model medium
```

### Ollamaに接続できない

Ollamaを起動し、モデルが存在するか確認してください。

```bash
ollama list
uv run meeting-minutes check
```

モデル名が違う場合は `--ollama-model` または設定ファイルで変更します。

### clean / draft / finalize で「Ollama APIから空の応答が返りました」

gemma4 等の thinking 対応モデルでは、デフォルトで推論ステップに大量のトークンを消費し、`num_ctx` を使い切って実際の応答が空になる場合があります。設定ファイルの `[summarization]` セクションで `think = false` を設定してください（既定値は `false`）。

```toml
[summarization]
think = false
```
