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

設定例は [config.example.toml](/Users/kk6/CascadeProjects/meeting-minutes/config.example.toml) を参照してください。

## Notes

- 音声と文字起こし内容はクラウドAPIへ送信しません。
- 議事録生成はローカルOllama API (`http://localhost:11434`) を使います。
- `live` はCtrl+Cで停止し、`metadata.json` を保存します。
