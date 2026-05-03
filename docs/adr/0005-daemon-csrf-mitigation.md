# ADR-0005: CSRF Mitigation for Local HTTP Daemon

## Status

accepted

## Date

2026-05-03

## Context (Why)

`meeting-minutes daemon` は `127.0.0.1` にのみ bind するため、外部ホストから TCP 接続することはできない。しかし、ブラウザからは悪意あるページ経由で `http://127.0.0.1:8765/sessions/start` へのフォーム POST を誘導できる（CSRF）。

`POST /sessions/start`・`POST /sessions/stop` は録音を開始・停止する副作用を持つため、意図しないリクエストで実行されると困る。ローカル専用 API であっても CSRF 対策は必要と判断した。

## Intent (What)

ブラウザが発信するクロスオリジンリクエストを拒否しつつ、curl や CLI からの Origin ヘッダーなしリクエストは通過させる。

## Decision (How)

**二層の防御を組み合わせる。**

1. **CORS ミドルウェア**（`CORSMiddleware`、`allow_origin_regex`）  
   `https?://(localhost|127\.0\.0\.1)(:\d+)?` にマッチするオリジンのみプリフライト応答を許可する。JSON POST はシンプルリクエストではないためプリフライトが必須となり、許可されていないオリジンからの実際のリクエストはブラウザにブロックされる。

2. **Origin ヘッダー検証依存**（`_require_local_origin` Depends）  
   `POST /sessions/start`・`POST /sessions/stop` に適用する。`Origin` ヘッダーが存在し、かつ localhost / 127.0.0.1 以外の場合は 403 を返す。`Origin` ヘッダーがない場合（curl・CLI 等）は通過させる。

CORS だけでは「Content-Type: application/x-www-form-urlencoded」の単純 POST（一部ブラウザ）を防げない可能性があるため、Origin 検証を明示的に追加した。

## Alternatives Considered

**CSRF トークン**  
クライアントがトークンを取得してから POST に含める標準的な手法。ステートフルなフロントエンドがある場合に有効だが、curl 利用やシンプルな CLI クライアントでの扱いが煩雑になる。本プロジェクトのユースケースに対してオーバーエンジニアリングと判断した。

**Content-Type: application/json の強制**  
`application/json` 以外を 415 で拒否する方法。フォーム POST の大部分を弾けるが、任意の `Content-Type` を偽装したリクエストを完全には防げない。Origin 検証と比べて意図が不明確になるため採用しなかった。

**API キー / 認証**  
`Authorization` ヘッダーやトークンによる認証。セキュリティは強いが、ローカル個人ツールで毎回トークン管理を強いるのはユーザビリティとのバランスが悪いと判断した。

## Consequences

- ブラウザから `http://127.0.0.1:8765/sessions/start` への悪意ある誘導を二層で防ぐ
- curl・httpx などの非ブラウザクライアントは Origin ヘッダーを送らないため、制限なく利用できる
- `GET /sessions/current` は副作用がないため Origin 検証を適用しない
