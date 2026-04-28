# CLI説明書

`meeting-minutes` は、Macローカルでリアルタイム文字起こしと議事録生成を行うCLIです。

## 前提

```bash
uv sync
```

必要なもの:

- ffmpeg
- Ollama
- Ollama上の議事録生成モデル。デフォルトは `gemma4`
- 会議音声を取り込む場合はBlackHoleなどの仮想オーディオデバイス

## 基本フロー

1. 環境を確認する
2. 入力デバイスを確認する
3. `live` でリアルタイム文字起こしを実行する
4. `draft` または `finalize` で議事録Markdownを生成する

```bash
uv run meeting-minutes check
uv run meeting-minutes devices
uv run meeting-minutes live --device "BlackHole 64ch"
uv run meeting-minutes draft ./output/2026-04-28_193822_live_meeting/transcript_live.md
uv run meeting-minutes finalize ./output/2026-04-28_193822_live_meeting/transcript_live.md
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
uv run meeting-minutes check --config ./config.example.toml
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

指定した入力デバイスから音声を取得し、数秒ごとに文字起こしします。

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
| `--chunk-seconds` | `8` | 文字起こし1単位の秒数 |
| `--language` | `ja` | Whisperに渡す言語 |
| `--whisper-model` | `small` | faster-whisperのモデル名 |
| `--output-dir` | `output` | セッション出力先 |
| `--ollama-model` | `gemma4` | 自動ドラフト生成で使うOllamaモデル |
| `--config` | なし | TOML設定ファイル |
| `--no-save` | `false` | transcriptを保存しない |
| `--draft-interval-minutes` | `0` | 指定分ごとにドラフト生成。`0`なら無効 |

出力先の例:

```text
output/
  2026-04-28_193822_live_meeting/
    transcript_live.md
    minutes_draft.md
    metadata.json
```

停止するには `Ctrl+C` を押します。停止時に `metadata.json` が保存されます。

### BlackHole 64chを使う場合

通常はそのまま使えます。

```bash
uv run meeting-minutes live --device "BlackHole 64ch"
```

入力チャンネル数を明示したい場合:

```bash
uv run meeting-minutes live --device "BlackHole 64ch" --channels 2
```

## draft

途中までの文字起こしから、議事録ドラフトを生成します。

```bash
uv run meeting-minutes draft ./output/2026-04-28_193822_live_meeting/transcript_live.md
```

既定の出力先:

```text
minutes_draft.md
```

出力先を指定する場合:

```bash
uv run meeting-minutes draft ./output/current/transcript_live.md --output ./output/current/draft.md
```

設定ファイルを使う場合:

```bash
uv run meeting-minutes draft ./output/current/transcript_live.md --config ./config.example.toml
```

## finalize

会議全体の文字起こしから、最終議事録を生成します。

```bash
uv run meeting-minutes finalize ./output/2026-04-28_193822_live_meeting/transcript_live.md
```

既定の出力先:

```text
minutes.md
```

出力先を指定する場合:

```bash
uv run meeting-minutes finalize ./output/current/transcript_live.md --output ./output/current/minutes.md
```

## 設定ファイル

TOML形式の設定ファイルを指定できます。

```bash
uv run meeting-minutes live --config ./config.example.toml
```

CLIオプションは設定ファイルより優先されます。

```toml
[audio]
device = "BlackHole 64ch"
# device_index = 0
sample_rate = 16000
channels = 1
chunk_seconds = 8

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

[output]
base_dir = "output"
save_transcript = true

[chunking]
chunk_size = 6000
chunk_overlap = 500
```

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
