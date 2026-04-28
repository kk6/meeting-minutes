# リアルタイム音声文字起こし・議事録生成ツール 要件定義書

## 1. 背景

ユーザーは音声会議で議事録を取るのが苦手であり、特に「聞きながら書く」ことに強い負荷を感じている。

録音後に音声ファイルを文字起こしするだけでは、会議中に内容を確認しながら議事録の骨子を作る用途には十分ではない。

そのため、本ツールではリアルタイム文字起こしを最優先のMVPとし、会議中に逐次表示される文字起こしを見ながら、必要に応じて議事録ドラフトを生成できるローカルツールを開発する。

## 2. 目的

Mac上でローカル実行できる、無料範囲のリアルタイム文字起こし・議事録生成ツールを作成する。

主目的:

- 会議中の音声をリアルタイムに文字起こしする
- 文字起こし結果を逐次画面表示する
- 文字起こしログをMarkdownとして保存する
- 任意のタイミングでOllama上のGemma 4により議事録ドラフトを生成する
- 会議終了後に最終議事録Markdownを生成する

## 3. 前提

### 3.1 実行環境

- OS: macOS
- Python: 3.12以上
- パッケージ管理: uv
- 文字起こし: faster-whisper または whisper.cpp 相当
- 音声入力: sounddevice
- 仮想オーディオ: BlackHole
- LLM実行環境: Ollama
- 要約モデル: gemma4
- 音声処理: ffmpeg

### 3.2 既に利用可能なもの

- Ollamaはインストール済み
- Gemma 4はOllama上で実行経験あり
- BlackHoleはインストール済み
- PythonでのCLI開発が可能
- 必要に応じてReactでUI開発も可能

## 4. 重要な設計方針

本ツールでは、録音済み音声ファイルのバッチ処理ではなく、リアルタイム文字起こしをMVPの中心にする。

ただし、リアルタイム処理は不安定になりやすいため、最初から複雑なGUIや話者分離は入れない。

初期MVPでは以下を優先する。

```text
音声入力デバイス
  ↓
短時間バッファ
  ↓
Whisper系エンジン
  ↓
逐次文字起こし
  ↓
ターミナル表示
  ↓
transcript_live.md に追記
  ↓
任意タイミングでGemma 4による議事録ドラフト生成
```

## 5. スコープ

## 5.1 初期MVPの対象

対象機能:

1. 入力音声デバイス一覧の表示
2. 入力音声デバイスの指定
3. マイク入力またはBlackHole入力からの音声取得
4. 5〜10秒程度の音声チャンク作成
5. チャンク単位の文字起こし
6. 文字起こし結果のターミナル逐次表示
7. 文字起こし結果のMarkdown追記保存
8. 現在までの文字起こしから議事録ドラフト生成
9. 会議終了時の最終議事録生成
10. 設定ファイルによるモデル名・デバイス名・チャンク秒数等の変更

## 5.2 初期MVPでは対象外

以下は初期MVPでは対象外とする。

- React GUI
- 完全な話者分離
- ZoomやGoogle Meetとの直接連携
- 自動会議参加
- クラウドLLM連携
- 高度な編集UI
- 音声ファイルのバッチ文字起こしを主機能にすること
- 完全なリアルタイム低遅延字幕

ただし、後続フェーズで追加しやすい設計にする。

## 6. 想定利用方法

## 6.1 入力デバイス一覧確認

```bash
uv run meeting-minutes devices
```

期待される出力例:

```text
Available input devices:

[0] MacBook Pro Microphone
[1] BlackHole 2ch
[2] Steinberg UR22C
[3] Steinberg UR22C DAW
```

## 6.2 リアルタイム文字起こし開始

```bash
uv run meeting-minutes live --device "BlackHole 2ch"
```

または

```bash
uv run meeting-minutes live --device-index 1
```

## 6.3 マイク入力でテスト

```bash
uv run meeting-minutes live --device "MacBook Pro Microphone"
```

## 6.4 議事録ドラフト生成

別コマンドとして、現在までの文字起こしログから議事録ドラフトを生成する。

```bash
uv run meeting-minutes draft ./output/current/transcript_live.md
```

## 6.5 会議終了後の最終議事録生成

```bash
uv run meeting-minutes finalize ./output/current/transcript_live.md
```

## 7. CLI要件

CLIコマンド名は `meeting-minutes` とする。

## 7.1 devices

入力デバイス一覧を表示する。

```bash
meeting-minutes devices
```

要件:

- sounddeviceで認識できる入力デバイスを列挙する
- device index、device name、入力チャンネル数、サンプルレートを表示する
- BlackHoleが存在する場合、分かるように表示する

## 7.2 live

リアルタイム文字起こしを開始する。

```bash
meeting-minutes live
```

オプション:

- `--device DEVICE_NAME`
- `--device-index DEVICE_INDEX`
- `--sample-rate 16000`
- `--chunk-seconds 8`
- `--language ja`
- `--whisper-model small`
- `--output-dir ./output`
- `--ollama-model gemma4`
- `--config ./config.toml`
- `--no-save`
- `--draft-interval-minutes 0`

仕様:

- 音声入力を継続的に取得する
- 指定秒数ごとに音声チャンクを作成する
- 各チャンクをWhisper系エンジンに渡して文字起こしする
- 結果をターミナルに表示する
- 結果を `transcript_live.md` に追記する
- Ctrl+Cで安全に停止する
- 停止時にmetadataを保存する

## 7.3 draft

現在までの文字起こしから議事録ドラフトを生成する。

```bash
meeting-minutes draft TRANSCRIPT_FILE
```

出力:

- `minutes_draft.md`

用途:

- 会議中または休憩中に、途中までの内容を議事録形式で確認する

## 7.4 finalize

文字起こし全体から最終議事録を生成する。

```bash
meeting-minutes finalize TRANSCRIPT_FILE
```

出力:

- `minutes.md`

用途:

- 会議終了後に最終議事録を生成する

## 7.5 check

実行環境の確認を行う。

```bash
meeting-minutes check
```

確認項目:

- ffmpegが利用可能か
- sounddeviceで入力デバイスを取得できるか
- BlackHoleが認識されているか
- Ollama APIに接続できるか
- 指定モデルがOllamaで利用可能か
- Whisperモデルがロード可能か

## 8. 音声入力要件

## 8.1 入力方式

初期MVPでは sounddevice を利用する。

理由:

- Pythonから扱いやすい
- 入力デバイス一覧を取得できる
- マイク入力とBlackHole入力を同じ処理で扱える
- リアルタイム録音処理を実装しやすい

## 8.2 対応入力

最低限、以下を想定する。

- Mac内蔵マイク
- BlackHole 2ch
- オーディオインターフェース入力
- Steinberg UR-C系デバイス

## 8.3 BlackHole利用時の想定

Zoom、Google Meet、Teamsなどの会議音声を文字起こししたい場合、Macの音声出力をBlackHoleにルーティングする必要がある。

初期MVPではルーティング自体はツール側で制御しない。

ユーザーがmacOSのオーディオ設定、またはAudio MIDI設定、または外部ミキサー構成でBlackHoleに音声を流す前提とする。

## 8.4 サンプルレート

デフォルトは 16000 Hz とする。

ただし、デバイスによっては48000 Hzが標準になるため、設定可能にする。

必要に応じてWhisperに渡す前にリサンプリングする。

## 8.5 チャンク秒数

デフォルトは8秒とする。

設定可能範囲:

- 3秒
- 5秒
- 8秒
- 10秒
- 15秒

短すぎると認識精度が落ちやすく、長すぎると遅延が大きくなるため、初期値は8秒とする。

## 9. 文字起こし要件

## 9.1 エンジン

初期実装では faster-whisper を第一候補とする。

理由:

- Pythonから扱いやすい
- ローカル実行できる
- CPUでも検証しやすい
- 後からwhisper.cppに差し替えやすい

## 9.2 モデル

デフォルトは `small` とする。

設定可能:

- `tiny`
- `base`
- `small`
- `medium`
- `large-v3`

リアルタイム性を優先する場合は `base` または `small` を推奨する。

## 9.3 出力形式

`transcript_live.md` に追記する。

例:

```markdown
# Live Transcript

## Metadata

- Started at: 2026-04-28 19:30:00
- Input device: BlackHole 2ch
- Language: ja
- Whisper model: small

## Body

[00:00:08] 今日は新機能の仕様について確認します。
[00:00:16] まずログイン周りですが、既存仕様を大きく変えない方針です。
[00:00:24] 次に権限設定についてです。
```

## 9.4 重複対策

リアルタイムチャンクでは、前後の文脈保持のためにオーバーラップを入れる場合がある。

その場合、重複した文字起こしが出やすい。

初期MVPでは高度な重複除去は不要だが、最低限以下を行う。

- 完全一致行は追記しない
- 直前テキストと高い類似度の行はスキップ可能にする
- 重複除去は独立モジュールにする

## 10. 要約・議事録生成要件

## 10.1 LLM

Ollama上のGemma 4を利用する。

デフォルトモデル名:

```text
gemma4
```

ただし、Ollamaでの実際のモデル名が異なる可能性があるため、設定で変更可能にする。

## 10.2 Ollama API

デフォルトURL:

```text
http://localhost:11434/api/generate
```

設定可能項目:

- `ollama_base_url`
- `ollama_model`
- `temperature`
- `num_ctx`
- `timeout_seconds`

## 10.3 draft

`draft` コマンドでは、現在までの文字起こしから議事録ドラフトを作成する。

出力形式:

```markdown
# 議事録ドラフト

## ここまでの概要

## 決定事項

## TODO

| 担当者 | 内容 | 期限 | 備考 |
| --- | --- | --- | --- |

## 論点

## 未決事項

## 次回確認事項

## 重要そうな発言

## 不明点
```

## 10.4 finalize

`finalize` コマンドでは、会議全体の文字起こしから最終議事録を生成する。

出力形式:

```markdown
# 議事録

## 概要

## 決定事項

## TODO

| 担当者 | 内容 | 期限 | 備考 |
| --- | --- | --- | --- |

## 論点

## 未決事項

## 次回確認事項

## 補足

## 原文参照メモ
```

## 10.5 長文対策

文字起こしが長い場合、以下の2段階要約を行う。

```text
transcript_live.md
  ↓
一定文字数で分割
  ↓
チャンクごとの要約
  ↓
チャンク要約の統合
  ↓
minutes.md
```

## 11. 設定ファイル要件

TOML形式をサポートする。

例:

```toml
[audio]
device = "BlackHole 2ch"
device_index = null
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

CLIオプションが設定ファイルより優先される。

## 12. 出力ディレクトリ

`live` 実行時にセッションごとのディレクトリを作成する。

例:

```text
output/
  2026-04-28_193000_live_meeting/
    transcript_live.md
    minutes_draft.md
    minutes.md
    metadata.json
```

## 13. メタデータ

`metadata.json` に以下を保存する。

- セッション開始日時
- セッション終了日時
- 入力デバイス名
- 入力デバイスindex
- sample rate
- chunk seconds
- Whisper model
- Ollama model
- language
- 出力ファイルパス
- エラー情報
- 処理時間

## 14. 非機能要件

## 14.1 ローカル実行

音声データ、文字起こし、要約はローカルで完結する。

外部クラウドAPIには送信しない。

OllamaのローカルAPIへのHTTP通信は許容する。

## 14.2 プライバシー

- 音声内容を外部送信しない
- ログに全文を不用意に出さない
- エラー出力に音声内容を含めない
- 保存先はユーザーが指定可能にする

## 14.3 安定性

- Ctrl+Cで安全に終了できる
- 終了時に途中までの文字起こしを失わない
- 文字起こし中に要約エラーが起きてもtranscriptは保持する
- Ollama未起動でもlive文字起こし自体は動作可能にする

## 14.4 保守性

責務を分離する。

推奨モジュール構成:

```text
src/
  meeting_minutes/
    __init__.py
    cli.py
    config.py
    devices.py
    audio_stream.py
    transcribe.py
    live.py
    dedupe.py
    summarize.py
    ollama_client.py
    prompts.py
    output.py
    metadata.py
    errors.py
```

## 15. 技術要件

## 15.1 推奨パッケージ

- `typer`
- `rich`
- `pydantic`
- `pydantic-settings`
- `sounddevice`
- `numpy`
- `faster-whisper`
- `httpx`
- `pytest`
- `ruff`
- `mypy`

## 15.2 開発方針

- uv管理
- Python 3.12以上
- 型ヒントを明確に書く
- ruffを通す
- mypyを通す
- pytestを書く
- Googleスタイルdocstringを使用する
- docstringは自明なWhatではなくWhyや制約を中心に書く

## 16. エラーハンドリング

想定エラー:

- 入力デバイスが見つからない
- BlackHoleが認識されていない
- sounddeviceが音声入力を開始できない
- sample rateがデバイス非対応
- Whisperモデルロード失敗
- Ollama未起動
- Gemma 4モデル未取得
- 出力先に書き込めない
- Ctrl+C終了

エラー表示例:

```text
指定された入力デバイスが見つかりませんでした: BlackHole 2ch

以下のコマンドで利用可能な入力デバイスを確認してください:

  uv run meeting-minutes devices
```

## 17. プロンプト

## 17.1 議事録ドラフト生成プロンプト

```text
以下は会議中のリアルタイム文字起こしです。
現時点までの内容を議事録ドラフトとして整理してください。

出力形式:
# 議事録ドラフト

## ここまでの概要
## 決定事項
## TODO
| 担当者 | 内容 | 期限 | 備考 |
| --- | --- | --- | --- |
## 論点
## 未決事項
## 次回確認事項
## 重要そうな発言
## 不明点

制約:
- 文字起こしにない内容を推測で補完しない
- 聞き間違いの可能性がある箇所は断定しない
- 不明なものは「不明」と書く
- TODOは担当者、内容、期限が分かる範囲で書く
- 雑談、言い直し、相槌は省略する
- 固有名詞、日付、数値は可能な限り保持する

文字起こし:
{transcript}
```

## 17.2 最終議事録生成プロンプト

```text
以下は会議のリアルタイム文字起こしです。
内容を整理し、最終的な議事録Markdownを作成してください。

出力形式:
# 議事録

## 概要
## 決定事項
## TODO
| 担当者 | 内容 | 期限 | 備考 |
| --- | --- | --- | --- |
## 論点
## 未決事項
## 次回確認事項
## 補足
## 原文参照メモ

制約:
- 文字起こしにない内容を作らない
- 決定事項と未決事項を混同しない
- TODOは表形式にする
- 不明な項目は「不明」とする
- 重要な日付、数値、担当者名を保持する
- 議事録として読みやすい日本語に整える
- 誤認識の可能性がある箇所は「要確認」とする

文字起こし:
{transcript}
```

## 18. 受け入れ条件

## 18.1 環境確認

- `uv run meeting-minutes check` が実行できる
- `uv run meeting-minutes devices` で入力デバイス一覧が表示される
- BlackHoleが存在する場合、一覧に表示される

## 18.2 リアルタイム文字起こし

- `uv run meeting-minutes live --device "MacBook Pro Microphone"` でマイク音声を文字起こしできる
- `uv run meeting-minutes live --device "BlackHole 2ch"` でBlackHole入力を文字起こしできる
- 結果がターミナルに逐次表示される
- `transcript_live.md` に追記保存される
- Ctrl+Cで安全に終了できる

## 18.3 議事録生成

- `uv run meeting-minutes draft transcript_live.md` で `minutes_draft.md` が生成される
- `uv run meeting-minutes finalize transcript_live.md` で `minutes.md` が生成される
- Gemma 4モデル名は設定で変更できる

## 18.4 品質

- ruffが通る
- mypyが通る
- pytestが通る
- デバイス未検出時に分かりやすいエラーを出す
- Ollama未起動時に分かりやすいエラーを出す

## 19. 実装優先順位

## Phase 1: CLIと環境確認

- uvプロジェクト作成
- Typer CLI作成
- devicesコマンド
- checkコマンド
- 設定ファイル読み込み

## Phase 2: リアルタイム音声入力

- sounddeviceで指定デバイスから入力
- 音声チャンク作成
- Ctrl+C安全停止
- WAV一時バッファ生成

## Phase 3: リアルタイム文字起こし

- faster-whisper連携
- チャンク単位で文字起こし
- ターミナル逐次表示
- transcript_live.md追記保存

## Phase 4: 議事録ドラフト生成

- Ollama client作成
- draftコマンド
- finalizeコマンド
- 長文時の分割要約

## Phase 5: 実用性改善

- 重複除去
- 無音区間スキップ
- チャンク秒数調整
- README整備
- サンプル設定ファイル追加

## Phase 6: 将来拡張

- React UI
- FastAPI化
- リアルタイム字幕UI
- Obsidian連携
- 話者分離
- 音声ファイルバッチ処理

## 20. Codex appへの初回依頼文

```text
この要件定義書に従って、Python製のローカルリアルタイム文字起こし・議事録生成CLIを実装してください。

最優先:
- 録音済み音声ファイルのバッチ処理ではなく、リアルタイム文字起こしをMVPの中心にしてください
- Phase 1からPhase 4までを実装してください
- React UI、話者分離、Zoom直接連携は実装しないでください

技術要件:
- uv前提
- Python 3.12以上
- CLIはTyper
- 設定はTOML + pydantic-settings
- 音声入力はsounddevice
- 文字起こしはfaster-whisper
- 要約はOllamaローカルAPI
- デフォルトLLMモデル名はgemma4
- 入力デバイスとしてBlackHoleを指定できるようにしてください
- ruff, mypy, pytest が通る状態にしてください

実装上の注意:
- devicesコマンドで入力デバイス一覧を確認できるようにしてください
- liveコマンドで指定デバイスから音声を取得し、数秒ごとに文字起こししてください
- 文字起こし結果はターミナル表示と transcript_live.md への追記保存をしてください
- draft/finalizeコマンドでGemma 4による議事録生成を行ってください
- 音声入力、文字起こし、要約、出力保存の責務を分離してください
- 外部クラウドAPIには送信しない設計にしてください
```
