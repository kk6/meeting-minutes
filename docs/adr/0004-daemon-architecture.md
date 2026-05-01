# ADR-0004: Daemon Architecture for Session Control

## Status

proposed

## Date

2026-05-02

## Context (Why)

現在の `meeting-minutes live` は CLI プロセスとして起動し、`KeyboardInterrupt` で停止する設計になっている。この前提では、ブラウザ UI・Raycast Script Commands・macOS LaunchAgent といった外部クライアントから録音の開始・停止・状態確認を行う方法がない。

外部クライアントが録音を制御するには、常駐する制御プロセスと、それを操作するための通信インターフェースが必要になる。

## Intent (What)

`meeting-minutes daemon` コマンドを追加し、録音セッションを所有・管理する常駐プロセスとして機能させる。

CLI・Raycast・Web UI は、daemon が提供するローカル HTTP API 経由で start / stop / status を呼び出す。これにより、各クライアントは録音の実装詳細を持たず、daemon が単一の制御点となる。

## Constraints

- 音声・文字起こし内容はローカル外へ送らない
- API は `127.0.0.1` にのみ bind し、外部ネットワークからアクセスできないようにする
- 既存の `live` コマンドの動作を変えない（後方互換を保つ）

## Decision (How)

以下の設計を採用する。

**セッション所有モデル**  
daemon が録音セッションを所有する。CLI が `live` プロセスを起動・監視する構成ではなく、録音ループを daemon プロセス内で直接実行する。

**単一セッション制限**  
同時録音セッションは 1 つに制限する。複数セッション・複数デバイスの管理は初期スコープ外とし、設計を単純に保つ。

**停止制御**  
daemon 管理下の録音セッションでは、`POST /sessions/stop` への HTTP リクエストを停止シグナルとして扱う。既存の `meeting-minutes live` は引き続き `KeyboardInterrupt` で停止する。

**セッション状態の保持**  
セッション状態はメモリ上で管理する。`output/<session>/metadata.json` との同期は、セッション完了時のみ行う（ライブ中のポーリングには使わない）。

**API エンドポイント候補**

| メソッド | パス | 説明 |
|---|---|---|
| `POST` | `/sessions/start` | 録音セッションを開始する |
| `POST` | `/sessions/stop` | 実行中のセッションを停止する |
| `GET` | `/sessions/current` | 現在のセッション状態を返す |
| `GET` | `/config` | 現在の設定を返す（候補） |
| `PUT` | `/config` | 設定を更新する（候補・次回セッションから反映） |

**MVP エンドポイント**  
`#13` の初期実装は `/sessions/start`・`/sessions/stop`・`/sessions/current` の 3 エンドポイントに絞る。`/config` 系は候補として記録するが、MVP スコープ外とする。

**実装フレームワーク**  
HTTP API の実装には `FastAPI` + `uvicorn` を使用する。既存の Pydantic 利用と統合が自然で、`httpx`（既存依存）を CLI クライアント側でそのまま再利用できる。

## Alternatives Considered

**CLI が `live` プロセスを起動・監視する構成**  
daemon が子プロセスとして `live` を起動し、プロセス間通信で制御する案を検討した。既存コードへの変更が少ないが、停止シグナルの伝達・状態同期・クラッシュリカバリが複雑になる。daemon がセッションを直接所有する構成のほうがシンプルに保てると判断した。

**複数セッション対応**  
将来の拡張性のために複数セッションを許可する設計を検討した。しかし、初期段階から複数セッション・常駐管理まで広げると設計が重くなる。単一セッション制限で始め、需要が明確になってから拡張する方が現実的と判断した。

**Unix ドメインソケット**  
HTTP ではなく Unix ドメインソケットで制御する案を検討した。よりシンプルだが、ブラウザ UI や Raycast との統合が困難になる。HTTP API のほうがクライアント多様性に対応しやすい。

## Consequences

- CLI・Raycast・Web UI が同一の HTTP API を使うことで、クライアント実装の重複がなくなる
- daemon 管理下の録音セッションでは HTTP リクエストで停止できる必要があるため、既存の `run_live()` から録音ループと停止制御を分離する必要がある
- 単一セッション制限により、初期設計はシンプルに保てる
- daemon プロセスのクラッシュ時にメモリ上のセッション状態が失われる。クラッシュリカバリやライブ中の状態永続化は初期スコープ外とする
