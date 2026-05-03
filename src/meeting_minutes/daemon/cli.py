"""daemon サブコマンド群の定義。"""

from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

if TYPE_CHECKING:
    import httpx

    from meeting_minutes.daemon.client import DaemonClient as DaemonClientType
    from meeting_minutes.daemon.schema import SessionStatus as SessionStatusType

import typer
from rich.console import Console

from meeting_minutes.config import load_config

daemon_app = typer.Typer(no_args_is_help=True, help="ローカル制御サーバを管理します。")
_console = Console()


def _make_daemon_client(host: str, port: int) -> "DaemonClientType":
    from meeting_minutes.daemon.client import DaemonClient

    return DaemonClient(f"http://{host}:{port}")


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


_LOCAL_HOSTS = {"127.0.0.1", "localhost"}


def _daemon_connect_error(host: str, port: int) -> None:
    if host not in _LOCAL_HOSTS:
        # serve は 127.0.0.1 にのみバインドするためリモートには直接届かない
        _console.print(
            f"[red]http://{host}:{port} に接続できません。"
            " daemon serve はループバックにのみバインドするため、"
            " リモートホストへの接続にはポートフォワーディングが必要です。[/red]"
        )
    else:
        port_opt = f" --port {port}" if port != 8765 else ""
        _console.print(
            f"[red]http://{host}:{port} に接続できません。"
            f" 先に meeting-minutes daemon serve{port_opt} を起動してください。[/red]"
        )


def _daemon_timeout_error(host: str, port: int) -> None:
    _console.print(
        f"[red]http://{host}:{port} が応答しませんでした。"
        " デーモンが起動中の場合はしばらく待ってから再試行してください。[/red]"
    )


def _http_error_detail(exc: "httpx.HTTPStatusError") -> str:
    try:
        return str(exc.response.json().get("detail", exc))
    except (ValueError, AttributeError):
        return str(exc)


def _invoke_daemon(
    host: str,
    port: int,
    action: Callable[["DaemonClientType"], "SessionStatusType"],
) -> "SessionStatusType":
    """daemon API 呼び出しの共通例外処理。CLI 層のエラー表示と Exit を一元化する。"""
    import httpx

    client = _make_daemon_client(host, port)
    try:
        return action(client)
    except httpx.ConnectError:
        _daemon_connect_error(host, port)
        raise typer.Exit(code=1) from None
    except httpx.TimeoutException:
        _daemon_timeout_error(host, port)
        raise typer.Exit(code=1) from None
    except httpx.HTTPStatusError as exc:
        _console.print(f"[red]{_http_error_detail(exc)}[/red]")
        raise typer.Exit(code=1) from exc


@daemon_app.command("serve")
def daemon_serve(
    port: Annotated[int, typer.Option("--port", min=1, max=65535)] = 8765,
    config: Annotated[Path | None, typer.Option("--config", help="TOML設定ファイル")] = None,
) -> None:
    """ローカル制御サーバを起動します（Ctrl+C で停止）。127.0.0.1 のみに bind します。"""
    import uvicorn

    from meeting_minutes.daemon.server import app as daemon_server_app
    from meeting_minutes.daemon.server import configure

    app_config = load_config(config)
    configure(app_config)
    uvicorn.run(daemon_server_app, host="127.0.0.1", port=port)


@daemon_app.command("start")
def daemon_start(
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", min=1, max=65535)] = 8765,
    draft_interval_minutes: Annotated[
        int, typer.Option("--draft-interval-minutes", help="0なら自動ドラフト生成なし", min=0)
    ] = 0,
) -> None:
    """録音セッションを開始します。"""
    from meeting_minutes.daemon.schema import StartRequest

    req = StartRequest(draft_interval_minutes=draft_interval_minutes)
    _print_session_status(_invoke_daemon(host, port, lambda c: c.start(req)))


@daemon_app.command("stop")
def daemon_stop(
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", min=1, max=65535)] = 8765,
) -> None:
    """録音セッションを停止します。"""
    _print_session_status(_invoke_daemon(host, port, lambda c: c.stop()))


@daemon_app.command("status")
def daemon_status(
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", min=1, max=65535)] = 8765,
) -> None:
    """現在のセッション状態を表示します。"""
    _print_session_status(_invoke_daemon(host, port, lambda c: c.current()))
