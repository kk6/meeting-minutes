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
```

設定例は [config.example.toml](./config.example.toml) を参照してください。

詳しいCLI説明は [docs/cli.md](./docs/cli.md) を参照してください。

## Notes

- 音声と文字起こし内容はクラウドAPIへ送信しません。
- 議事録生成はローカルOllama API (`http://localhost:11434`) を使います。
- `live` はデフォルトでセッションディレクトリに `audio_live.wav` を保存します。保存は `--no-save-audio` または `output.save_audio=false` で無効化できます。
- `live` はCtrl+Cで停止し、`metadata.json` を保存します。
- 用語集と参加者名のテキストファイルを `[vocabulary]` セクションで指定すると、固有名詞の誤認識と表記揺れを抑制できます。詳しくは [docs/cli.md](./docs/cli.md#語彙ヒントvocabulary) を参照してください。
