from typer.testing import CliRunner

from meeting_minutes.cli import app


def test_cli_help() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "devices" in result.output
