"""daemon サブコマンド群の定義。"""

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    import logging

    import httpx

    from meeting_minutes.daemon.client import DaemonClient as DaemonClientType
    from meeting_minutes.daemon.schema import SessionStatus as SessionStatusType

import typer
from rich.console import Console

from meeting_minutes.config import load_config, resolve_config_source
from meeting_minutes.config.cli import describe_config_source

daemon_app = typer.Typer(no_args_is_help=True, help="ローカル制御サーバを管理します。")
_console = Console()


def _make_daemon_client(port: int) -> "DaemonClientType":
    from meeting_minutes.daemon.client import DaemonClient

    return DaemonClient(f"http://127.0.0.1:{port}")


def _print_session_status(status: "SessionStatusType") -> None:
    state_color = {
        "idle": "white",
        "running": "green",
        "stopping": "yellow",
        "failed": "red",
    }.get(status.state, "white")
    _console.print(f"[bold]State:[/bold] [{state_color}]{status.state}[/{state_color}]")
    if status.started_at:
        _console.print(f"[bold]Started:[/bold] {status.started_at}")
    if status.elapsed_seconds > 0:
        _console.print(f"[bold]Elapsed:[/bold] {status.elapsed_seconds}s")
    if status.session_dir:
        _console.print(f"[bold]Session dir:[/bold] {status.session_dir}")
    if status.transcript_path:
        _console.print(f"[bold]Transcript:[/bold] {status.transcript_path}")
    for err in status.errors:
        _console.print(f"[red]Error:[/red] {err}")


def _http_error_detail(exc: "httpx.HTTPStatusError") -> str:
    try:
        return str(exc.response.json().get("detail", exc))
    except (ValueError, AttributeError):
        return str(exc)


def _invoke_daemon(
    port: int,
    action: Callable[["DaemonClientType"], "SessionStatusType"],
) -> "SessionStatusType":
    """daemon API 呼び出しの共通例外処理。"""
    import httpx

    client = _make_daemon_client(port)
    try:
        return action(client)
    except (httpx.ConnectError, httpx.TimeoutException):
        _console.print(
            f"[red]http://127.0.0.1:{port} の daemon に接続できません。"
            " 先に meeting-minutes daemon serve を起動してください。[/red]"
        )
        raise typer.Exit(code=1) from None
    except httpx.HTTPStatusError as exc:
        _console.print(f"[red]{_http_error_detail(exc)}[/red]")
        raise typer.Exit(code=1) from exc


_DAEMON_LOGGER_NAME = "meeting_minutes.daemon"


def _ensure_daemon_logger() -> "logging.Logger":
    """daemon serve 起動時に使うロガーを準備する。

    uvicorn は自身のログ設定で root ロガーを書き換えるため、専用のハンドラを
    `propagate=False` で持たせ、書式を固定する。再呼び出し時に重複ハンドラを
    付けないようガードする。
    """
    import logging

    logger = logging.getLogger(_DAEMON_LOGGER_NAME)
    if not any(getattr(h, "_meeting_minutes_daemon", False) for h in logger.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
        handler._meeting_minutes_daemon = True  # type: ignore[attr-defined]
        logger.addHandler(handler)
        logger.propagate = False
    logger.setLevel(logging.INFO)
    return logger


def _log_daemon_startup(
    logger: "logging.Logger",
    *,
    source_description: str,
    output_base_dir: Path,
    port: int,
) -> None:
    """daemon 起動時の参照先 / 待ち受け先を一括で INFO 出力する。"""
    logger.info("config source: %s", source_description)
    logger.info("output base_dir: %s", output_base_dir)
    logger.info("listening on http://127.0.0.1:%d", port)


@daemon_app.command("serve")
def daemon_serve(
    port: Annotated[int, typer.Option("--port", min=1, max=65535)] = 8765,
    config: Annotated[Path | None, typer.Option("--config", help="TOML設定ファイル")] = None,
) -> None:
    """ローカル制御サーバを起動します（Ctrl+C で停止）。127.0.0.1 のみに bind します。"""
    import uvicorn

    from meeting_minutes.daemon.server import app as daemon_server_app
    from meeting_minutes.daemon.server import configure

    source = resolve_config_source(config)
    app_config = load_config(config)
    configure(app_config)

    # uvicorn の起動ログ (`Uvicorn running on http://127.0.0.1:8765`) より前に
    # config / output 解決結果を出すことで、どの設定で動いているかを最初の数行で把握できる。
    _log_daemon_startup(
        _ensure_daemon_logger(),
        source_description=describe_config_source(source),
        output_base_dir=app_config.output.base_dir,
        port=port,
    )

    uvicorn.run(daemon_server_app, host="127.0.0.1", port=port)


@daemon_app.command("start")
def daemon_start(
    port: Annotated[int, typer.Option("--port", min=1, max=65535)] = 8765,
    draft_interval_minutes: Annotated[
        int, typer.Option("--draft-interval-minutes", help="0なら自動ドラフト生成なし", min=0)
    ] = 0,
) -> None:
    """録音セッションを開始します。"""
    from meeting_minutes.daemon.schema import StartRequest

    req = StartRequest(draft_interval_minutes=draft_interval_minutes)
    _print_session_status(_invoke_daemon(port, lambda c: c.start(req)))


@daemon_app.command("stop")
def daemon_stop(
    port: Annotated[int, typer.Option("--port", min=1, max=65535)] = 8765,
) -> None:
    """録音セッションを停止します。"""
    _print_session_status(_invoke_daemon(port, lambda c: c.stop()))


@daemon_app.command("status")
def daemon_status(
    port: Annotated[int, typer.Option("--port", min=1, max=65535)] = 8765,
) -> None:
    """現在のセッション状態を表示します。"""
    _print_session_status(_invoke_daemon(port, lambda c: c.current()))
