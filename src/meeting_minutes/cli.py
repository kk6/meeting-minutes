"""`meeting-minutes` コマンドのエントリポイントを定義する Typer アプリ。"""

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from meeting_minutes.checks import run_checks
from meeting_minutes.config import apply_overrides, load_config
from meeting_minutes.devices import list_input_devices
from meeting_minutes.errors import MeetingMinutesError
from meeting_minutes.summarize import MinutesMode

app = typer.Typer(no_args_is_help=True)
console = Console()


def _disabled_when(flag: bool) -> bool | None:
    return False if flag else None


def _overflow_abort_setting(continue_on_overflow: bool, abort_on_overflow: bool) -> bool | None:
    if continue_on_overflow and abort_on_overflow:
        raise typer.BadParameter(
            "--continue-on-overflow と --abort-on-overflow は同時に指定できません"
        )
    if continue_on_overflow:
        return False
    if abort_on_overflow:
        return True
    return None


def _generate_minutes_command(
    transcript_files: list[Path],
    mode: MinutesMode,
    output: Path | None,
    config: Path | None,
) -> None:
    from meeting_minutes.summarize import generate_minutes

    app_config = load_config(config)
    try:
        output_path = generate_minutes(
            transcript_files,
            mode,
            output,
            app_config,
        )
    except MeetingMinutesError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(f"[green]Generated:[/green] {output_path}")


@app.command()
def devices() -> None:
    """入力音声デバイスを一覧表示します。"""
    table = Table(title="Available input devices")
    table.add_column("Index", justify="right")
    table.add_column("Name")
    table.add_column("Input Channels", justify="right")
    table.add_column("Default Sample Rate", justify="right")
    table.add_column("Note")

    for device in list_input_devices():
        table.add_row(
            str(device.index),
            device.name,
            str(device.channels),
            f"{device.default_sample_rate:.0f}",
            "BlackHole" if device.is_blackhole else "",
        )
    console.print(table)


@app.command()
def check(
    config: Annotated[Path | None, typer.Option("--config", help="TOML設定ファイル")] = None,
) -> None:
    """実行環境を確認します。"""
    app_config = load_config(config)
    table = Table(title="Environment check")
    table.add_column("Item")
    table.add_column("Status")
    table.add_column("Detail")

    failed = False
    for item, ok, detail in run_checks(app_config):
        failed = failed or not ok
        table.add_row(item, "[green]OK[/green]" if ok else "[red]NG[/red]", detail)
    console.print(table)
    if failed:
        raise typer.Exit(code=1)


@app.command()
def live(
    device: Annotated[str | None, typer.Option("--device", help="入力デバイス名")] = None,
    device_index: Annotated[
        int | None, typer.Option("--device-index", help="入力デバイスindex")
    ] = None,
    sample_rate: Annotated[int | None, typer.Option("--sample-rate")] = None,
    channels: Annotated[int | None, typer.Option("--channels", help="入力チャンネル数")] = None,
    chunk_seconds: Annotated[int | None, typer.Option("--chunk-seconds")] = None,
    language: Annotated[str | None, typer.Option("--language")] = None,
    whisper_model: Annotated[str | None, typer.Option("--whisper-model")] = None,
    output_dir: Annotated[Path | None, typer.Option("--output-dir")] = None,
    ollama_model: Annotated[str | None, typer.Option("--ollama-model")] = None,
    config: Annotated[Path | None, typer.Option("--config", help="TOML設定ファイル")] = None,
    no_save: Annotated[bool, typer.Option("--no-save")] = False,
    no_save_audio: Annotated[bool, typer.Option("--no-save-audio")] = False,
    no_vad: Annotated[bool, typer.Option("--no-vad", help="VADによる発話単位分割を無効化")] = False,
    continue_on_overflow: Annotated[
        bool,
        typer.Option("--continue-on-overflow", help="音声取り逃がし時も記録して続行する"),
    ] = False,
    abort_on_overflow: Annotated[
        bool,
        typer.Option("--abort-on-overflow", help="音声取り逃がし時に停止する"),
    ] = False,
    draft_interval_minutes: Annotated[
        int, typer.Option("--draft-interval-minutes", help="0なら自動ドラフト生成なし")
    ] = 0,
) -> None:
    """リアルタイム文字起こしを開始します。"""
    from meeting_minutes.live import run_live

    app_config = apply_overrides(
        load_config(config),
        {
            "audio.device": device,
            "audio.device_index": device_index,
            "audio.sample_rate": sample_rate,
            "audio.channels": channels,
            "audio.chunk_seconds": chunk_seconds,
            "transcription.language": language,
            "transcription.whisper_model": whisper_model,
            "output.base_dir": output_dir,
            "summarization.ollama_model": ollama_model,
            "output.save_transcript": _disabled_when(no_save),
            "output.save_audio": _disabled_when(no_save_audio),
            "vad.enabled": _disabled_when(no_vad),
            "audio.abort_on_overflow": _overflow_abort_setting(
                continue_on_overflow,
                abort_on_overflow,
            ),
        },
    )
    try:
        run_live(app_config, draft_interval_minutes=draft_interval_minutes)
    except MeetingMinutesError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc


@app.command()
def draft(
    transcript_files: Annotated[list[Path], typer.Argument(exists=True, readable=True)],
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
    config: Annotated[Path | None, typer.Option("--config", help="TOML設定ファイル")] = None,
) -> None:
    """現在までの文字起こしから議事録ドラフトを生成します。"""
    _generate_minutes_command(transcript_files, "draft", output, config)


@app.command()
def finalize(
    transcript_files: Annotated[list[Path], typer.Argument(exists=True, readable=True)],
    output: Annotated[Path | None, typer.Option("--output", "-o")] = None,
    config: Annotated[Path | None, typer.Option("--config", help="TOML設定ファイル")] = None,
) -> None:
    """文字起こし全体から最終議事録を生成します。"""
    _generate_minutes_command(transcript_files, "final", output, config)


if __name__ == "__main__":
    app()
