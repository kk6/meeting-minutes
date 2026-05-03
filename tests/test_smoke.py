from unittest.mock import patch

from typer.testing import CliRunner

from meeting_minutes.cli import app


def test_cli_help() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "devices" in result.output


def test_daemon_help() -> None:
    result = CliRunner().invoke(app, ["daemon", "--help"])

    assert result.exit_code == 0
    assert "--port" in result.output


def test_daemon_wires_config_and_runs() -> None:
    with (
        patch("meeting_minutes.daemon.server.configure") as mock_configure,
        patch("uvicorn.run") as mock_uvicorn_run,
    ):
        result = CliRunner().invoke(app, ["daemon", "--port", "9999"])

    assert result.exit_code == 0
    mock_configure.assert_called_once()
    mock_uvicorn_run.assert_called_once_with(
        mock_uvicorn_run.call_args[0][0],
        host="127.0.0.1",
        port=9999,
    )
