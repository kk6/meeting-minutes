"""`meeting-minutes config` サブコマンド群の定義。"""

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Annotated

import tomli_w
import typer
from rich.console import Console

from meeting_minutes.config import (
    AppConfig,
    ConfigSource,
    default_config_path,
    load_config,
    read_template_config_text,
    resolve_config_source,
)

config_app = typer.Typer(no_args_is_help=True, help="設定ファイルを管理します。")
_console = Console()


def _appconfig_to_dict(config: AppConfig) -> dict[str, object]:
    """`AppConfig` を JSON / TOML どちらにも流せるプリミティブな dict に落とす。

    `mode="json"` で `Path` / `datetime` を文字列化する。`exclude_none=True` で
    None フィールドを落とすのは TOML が null を表現できないため（dotted key を
    `None` のまま `tomli_w.dumps` に渡すと `TypeError` になる）。
    """
    return config.model_dump(mode="json", exclude_none=True)


@config_app.command("path")
def config_path(
    config: Annotated[
        Path | None,
        typer.Option("--config", help="このパスを評価対象として表示する"),
    ] = None,
) -> None:
    """現在 auto-discovery される config のパスを表示します。

    - `--config` を指定: そのパスを `explicit` として表示。
    - 指定なし & XDG 既定パスが存在: `auto_discovered` として表示。
    - いずれでもない: 既定パスを `defaults` として表示（このパスに `config init` で作成可）。
    """
    source = resolve_config_source(config)
    # 長いパスがターミナル幅で折り返されないよう soft_wrap=True で 1 行を保つ。
    if source.kind == "explicit":
        assert source.path is not None
        _console.print("[bold]source:[/bold] explicit")
        _console.print(f"[bold]path:[/bold] {source.path}", soft_wrap=True)
        return
    if source.kind == "auto_discovered":
        assert source.path is not None
        _console.print("[bold]source:[/bold] auto_discovered")
        _console.print(f"[bold]path:[/bold] {source.path}", soft_wrap=True)
        return
    # defaults: 設定ファイルは未作成。`config init` の作成先パスを併せて表示する。
    _console.print("[bold]source:[/bold] defaults (no config file)")
    _console.print(f"[bold]would-be path:[/bold] {default_config_path()}", soft_wrap=True)


@config_app.command("init")
def config_init(
    force: Annotated[
        bool,
        typer.Option("--force", "-f", help="既存ファイルを上書きする"),
    ] = False,
) -> None:
    """XDG 既定パスに config.example.toml の内容で雛形を生成します。"""
    target = default_config_path()
    if target.exists() and not force:
        _console.print(
            f"[red]既に設定ファイルが存在します: {target}[/red]\n"
            "[yellow]上書きする場合は --force を指定してください。[/yellow]"
        )
        raise typer.Exit(code=1)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(read_template_config_text(), encoding="utf-8")
    _console.print(f"[green]Created:[/green] {target}")


@config_app.command("show")
def config_show(
    output_format: Annotated[
        str,
        typer.Option("--format", help="出力形式（toml / json）"),
    ] = "toml",
    config: Annotated[
        Path | None,
        typer.Option("--config", help="TOML設定ファイル"),
    ] = None,
) -> None:
    """解決後の AppConfig 全体を出力します。"""
    if output_format not in ("toml", "json"):
        raise typer.BadParameter("--format は 'toml' または 'json' を指定してください")
    app_config = load_config(config)
    data = _appconfig_to_dict(app_config)
    if output_format == "json":
        _console.print_json(json.dumps(data, ensure_ascii=False))
    else:
        # `[section]` を Rich のマークアップとして解釈されないよう markup=False にする。
        _console.print(tomli_w.dumps(data), end="", soft_wrap=True, highlight=False, markup=False)


@config_app.command("edit")
def config_edit() -> None:
    """`$EDITOR` で config を開きます。未設定なら `open(1)` を試みます。

    対象は auto-discovery で解決される既定パスです。ファイルが未作成の場合は
    先に `meeting-minutes config init` を案内します。
    """
    source = resolve_config_source(None)
    if source.kind == "defaults":
        _console.print(
            f"[red]設定ファイルが存在しません: {default_config_path()}[/red]\n"
            "[yellow]先に `meeting-minutes config init` で作成してください。[/yellow]"
        )
        raise typer.Exit(code=1)
    assert source.path is not None
    _open_in_editor(source.path)


def _open_in_editor(path: Path) -> None:
    """`$EDITOR` が設定されていればそれで、なければ macOS の `open(1)` で開く。

    `$EDITOR` をシェルに通すと引数解釈の差異で誤動作するため、`shlex.split` で分解して
    直接 argv を組み立てる。
    """
    import shlex

    editor = os.environ.get("EDITOR")
    if editor:
        argv = shlex.split(editor) + [str(path)]
        subprocess.run(argv, check=True)
        return
    open_bin = shutil.which("open")
    if open_bin is None:
        _console.print(
            "[red]$EDITOR が未設定で、`open(1)` も見つかりません。[/red]\n"
            f"[yellow]手動で開いてください: {path}[/yellow]"
        )
        raise typer.Exit(code=1)
    subprocess.run([open_bin, str(path)], check=True)


def describe_config_source(source: ConfigSource) -> str:
    """ログ出力向けに `ConfigSource` を一行文字列に整形する（daemon serve から共有）。"""
    if source.kind == "explicit":
        return f"explicit ({source.path})"
    if source.kind == "auto_discovered":
        return f"auto_discovered ({source.path})"
    return f"defaults (no config file at {default_config_path()})"
