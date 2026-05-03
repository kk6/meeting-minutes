# meeting-minutes

Macローカルで動かすリアルタイム音声文字起こし・議事録生成CLIです。

## Setup

```bash
uv sync
```

必要な外部ツール:

- ffmpeg
- Ollama
- Ollama上の `gemma4` または設定したモデル
- BlackHoleなどの仮想オーディオデバイス（会議音声を拾う場合）

## Commands

```bash
uv run meeting-minutes check
uv run meeting-minutes devices
uv run meeting-minutes live --device "BlackHole 2ch"
uv run meeting-minutes draft ./output/current/transcript_live.md
uv run meeting-minutes finalize ./output/current/transcript_live.md
# 任意: clean で整形してから finalize すると議事録の入力品質が上がる
uv run meeting-minutes clean ./output/current/transcript_live.md
uv run meeting-minutes finalize ./output/current/transcript_clean.md
# liveを再起動して transcript が分かれた場合
uv run meeting-minutes finalize ./output/session-1/transcript_live.md ./output/session-2/transcript_live.md
```

HTTP API 経由で制御する場合（daemon モード）:

```bash
# ターミナル A: サーバを起動（Ctrl+C で停止）
uv run meeting-minutes daemon serve
# → http://127.0.0.1:8765/docs で API ドキュメントを参照できます

# ターミナル B: CLI から制御
uv run meeting-minutes daemon start
uv run meeting-minutes daemon status
uv run meeting-minutes daemon stop
```

設定例は [config.example.toml](./config.example.toml) を参照してください。

詳しいCLI説明は [docs/cli.md](./docs/cli.md) を参照してください。

## Notes

- 音声と文字起こし内容はクラウドAPIへ送信しません。
- 議事録生成はローカルOllama API (`http://localhost:11434`) を使います。
- `live` はデフォルトでセッションディレクトリに `audio_live.wav` を保存します。保存は `--no-save-audio` または `output.save_audio=false` で無効化できます。
- `live` はデフォルトでVADを使い、発話単位で文字起こしします。固定秒数チャンクに戻す場合は `--no-vad` または `vad.enabled=false` を使います。
- `live` はCtrl+Cで停止し、`metadata.json` を保存します。
- 音声取り逃がし時は既定で停止します。少量の欠落を許容して続行する場合は `--continue-on-overflow` または `audio.abort_on_overflow=false` を使います。
- 用語集と参加者名のテキストファイルを `[vocabulary]` セクションで指定すると、固有名詞の誤認識と表記揺れを抑制できます。詳しくは [docs/cli.md](./docs/cli.md#語彙ヒントvocabulary) を参照してください。
