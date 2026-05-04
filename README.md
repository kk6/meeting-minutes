# meeting-minutes

Macローカルで動かすリアルタイム音声文字起こし・議事録生成CLIです。

## このリポジトリについて

このツールは作者個人が自分の Mac 上で会議のリアルタイム文字起こし、議事録作成、YouTube/podcast の文字起こしや要約、英語音声の翻訳などに使うために作っているものです。
ソースコードは公開していますが、汎用ツールとして他の人が使うことは特に想定していません。
そのため、個人用途には不要な抽象化・汎化（例: マルチユーザー対応、リモート接続、IPv6 対応、複雑な入力バリデーション、過剰な防御的コーディング）は意図的に入れていません。

機能追加・改修・バグ修正をしたい場合は、Issue や PR ではなく fork してご自身の用途に合わせて自由に改変してください。作者は基本的に外部からの貢献やリクエストには対応しません。

## Setup

開発しながら使う場合（リポジトリ内で実行）:

```bash
uv sync
```

グローバルにインストールして任意ディレクトリ・Raycast 等から呼び出す場合:

```bash
uv tool install .
# 以降は `uv run` を介さずに直接呼び出せる
meeting-minutes --help
```

必要な外部ツール:

- ffmpeg
- Ollama
- Ollama上の `gemma4` または設定したモデル
- BlackHoleなどの仮想オーディオデバイス（会議音声を拾う場合）

### 設定ファイル

`--config` を渡さない場合、以下を auto-discovery します（XDG Base Directory 準拠）。

| 項目 | 既定パス | 上書き |
| --- | --- | --- |
| 設定ファイル | `~/.config/meeting-minutes/config.toml` | `$XDG_CONFIG_HOME` または `--config` |
| 出力先 (`output.base_dir`) | `~/.local/share/meeting-minutes/output/` | `$XDG_DATA_HOME` または config の `[output] base_dir` |

グローバルインストール時は、雛形を生成してから必要なフィールドだけ残すのが楽です。

```bash
meeting-minutes config init   # ~/.config/meeting-minutes/config.toml を生成
meeting-minutes config edit   # $EDITOR で開く（未設定時は macOS の open(1) が起動）
meeting-minutes config path   # auto-discovery で参照されるパスを表示
meeting-minutes config show   # 解決後の AppConfig を TOML/JSON で表示
```

最小構成を直接書く場合:

```bash
mkdir -p ~/.config/meeting-minutes
cat > ~/.config/meeting-minutes/config.toml <<'EOF'
[audio]
device = "BlackHole 2ch"
EOF
```

利用可能な全フィールドのリファレンスは [src/meeting_minutes/config/templates/config.example.toml](./src/meeting_minutes/config/templates/config.example.toml) を参照してください。
（雛形を丸ごとコピーすると `[output] base_dir = "output"` を引き継いで XDG 既定が無効化される点に注意。）

## Commands

グローバルインストール済みなら `uv run` を外して `meeting-minutes ...` で直接呼べます。
以下の `<base_dir>` は `output.base_dir` の解決結果です（XDG 既定なら `~/.local/share/meeting-minutes/output`、雛形を `--config src/meeting_minutes/config/templates/config.example.toml` で渡したリポジトリ内ワークフローなら `<repo>/output`）。

```bash
uv run meeting-minutes check
uv run meeting-minutes devices
uv run meeting-minutes live --device "BlackHole 2ch"
uv run meeting-minutes draft <base_dir>/<session>/transcript_live.md
uv run meeting-minutes finalize <base_dir>/<session>/transcript_live.md
# 任意: clean で整形してから finalize すると議事録の入力品質が上がる
uv run meeting-minutes clean <base_dir>/<session>/transcript_live.md
uv run meeting-minutes finalize <base_dir>/<session>/transcript_clean.md
# liveを再起動して transcript が分かれた場合
uv run meeting-minutes finalize <base_dir>/session-1/transcript_live.md <base_dir>/session-2/transcript_live.md
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

Raycast から daemon を制御したい場合は [scripts/raycast/README.md](./scripts/raycast/README.md) を参照してください。

設定例は [src/meeting_minutes/config/templates/config.example.toml](./src/meeting_minutes/config/templates/config.example.toml) を参照してください。`meeting-minutes config init` で雛形を XDG 既定パスに書き出せます。

詳しいCLI説明は [docs/cli.md](./docs/cli.md) を参照してください。

## Notes

- 音声と文字起こし内容はクラウドAPIへ送信しません。
- 議事録生成はローカルOllama API (`http://localhost:11434`) を使います。
- `live` はデフォルトでセッションディレクトリに `audio_live.wav` を保存します。保存は `--no-save-audio` または `output.save_audio=false` で無効化できます。
- `live` はデフォルトでVADを使い、発話単位で文字起こしします。固定秒数チャンクに戻す場合は `--no-vad` または `vad.enabled=false` を使います。
- `live` はCtrl+Cで停止し、`metadata.json` を保存します。
- 音声取り逃がし時は既定で停止します。少量の欠落を許容して続行する場合は `--continue-on-overflow` または `audio.abort_on_overflow=false` を使います。
- 用語集と参加者名のテキストファイルを `[vocabulary]` セクションで指定すると、固有名詞の誤認識と表記揺れを抑制できます。詳しくは [docs/cli.md](./docs/cli.md#語彙ヒントvocabulary) を参照してください。
