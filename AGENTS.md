# meeting-minutes

Guidance for coding agents working in this repository.

## Project Stance (read this first)

This is a **personal tool** the author runs locally on their own Mac. The repo is public but is not meant to be a general-purpose product:

- The author is the only intended user. There is no support, no roadmap, no release process.
- External contributions are not solicited. Users who want changes should fork and edit freely.
- **Avoid over-engineering for hypothetical other users.** Things like multi-user support, remote connectivity, IPv6, exhaustive input validation, defensive guards against contrived inputs, and elaborate error UX are explicitly out of scope unless the author needs them.
- Prefer the simplest implementation that works for the author's own usage. If a code review (human or AI) suggests adding generality "for users", push back and only adopt the change if it benefits the author's actual workflow or fixes a real defect.

## Project Overview

`meeting-minutes` is a local macOS CLI for realtime transcription and meeting-minutes generation.

- Audio capture uses `sounddevice`.
- Transcription uses `faster-whisper`.
- Minutes generation uses the local Ollama API, default model `gemma4`.
- The CLI is implemented with Typer and Rich.
- Audio and transcript content should stay local; do not introduce cloud API dependencies unless explicitly requested.

## Repository Layout

- `src/meeting_minutes/`: application code
- `tests/`: pytest tests
- `docs/`: user-facing documentation
- `src/meeting_minutes/config/templates/config.example.toml`: example runtime configuration (packaged as wheel data so `meeting-minutes config init` can write it out after `uv tool install .`)
- `output/`: generated runtime artifacts when `[output] base_dir = "output"` is set in config; do not treat as source. Default for global install is `$XDG_DATA_HOME/meeting-minutes/output/`

Important modules:

- `cli.py`: Typer command definitions and CLI override wiring. **As command groups grow, extract them into a subpackage (e.g. `daemon/cli.py` for `daemon` subcommands, `config/cli.py` for `config` subcommands) instead of accumulating helper functions directly in `cli.py`.** Existing top-level commands such as `devices`, `check`, `live`, `draft`, `finalize`, and `clean` remain in `cli.py` for now; refactor them out the same way once their helpers start to grow.
- `live.py`: realtime recording/transcription loop
- `audio_stream.py`: input stream buffering
- `transcribe.py`: faster-whisper wrapper
- `summarize.py`: chunking and minutes generation workflow
- `ollama_client.py`: Ollama HTTP client
- `config/__init__.py`: Pydantic settings, overrides, and `resolve_config_source` / `read_template_config_text` helpers
- `config/cli.py`: `meeting-minutes config` subcommands (init / path / show / edit) and `describe_config_source` shared with `daemon serve` startup logging
- `metadata.py`: session metadata model and JSON output
- `output.py`: transcript/session file helpers
- `dedupe.py`: transcript duplicate suppression
- `checks.py`: environment checks
- `errors.py`: domain exceptions with user-facing messages

## Development Commands

Use `uv` for dependency management and command execution.

```bash
uv sync
uv run ruff format src tests
uv run ruff check src tests
uv run mypy src
uv run pytest
```

Useful CLI smoke commands:

```bash
uv run meeting-minutes check
uv run meeting-minutes devices
uv run meeting-minutes live --device "BlackHole 64ch"
uv run meeting-minutes draft ./output/<session>/transcript_live.md
uv run meeting-minutes finalize ./output/<session>/transcript_live.md
```

Daemon mode (HTTP API control):

```bash
# Terminal 1: start the control server
uv run meeting-minutes daemon serve

# Terminal 2: control the recording session
uv run meeting-minutes daemon start
uv run meeting-minutes daemon status
uv run meeting-minutes daemon stop
```

Config management:

```bash
uv run meeting-minutes config init        # write template to XDG default path
uv run meeting-minutes config path        # show resolved config path
uv run meeting-minutes config show        # dump resolved AppConfig as TOML
uv run meeting-minutes config edit        # open in $EDITOR
```

## Python Style

- Target Python 3.12+.
- Keep source under `src/` and tests under `tests/`.
- Prefer small modules with clear responsibility over broad utility modules.
- Use type hints for public functions and non-obvious internal values.
- Follow existing Pydantic v2 patterns:
  - Keep structured config as `BaseModel` fields.
  - Use `model_copy(update=...)` for typed config updates.
  - Use `model_dump(mode="json")` when serializing models containing `datetime` or `Path`.
- Keep comments sparse. Comments should explain why a choice exists, not restate what the code does.
- Avoid adding abstractions unless they remove real duplication or clarify a boundary.

## Exception Handling

Errors should be visible. Silent failure is worse than a crash.

- Do not use `except Exception: pass`.
- Do not catch broad exceptions around large blocks of internal logic.
- Catch specific, expected exceptions at system boundaries:
  - file I/O
  - audio device access
  - network calls to Ollama
  - optional dependency imports
- When continuing after an expected failure, log context with `logger.exception(...)` or `logger.warning(...)` as appropriate.
- Let unexpected programming errors propagate.
- Domain-level failures that should be shown cleanly by the CLI should inherit from `MeetingMinutesError`.

## Testing Guidance

- Use pytest.
- Test behavior, not implementation details.
- Prefer testing private helpers through public behavior. Private functions and methods are
  implementation details, and direct tests for them often make refactoring harder.
- If a private helper feels important enough to test directly, first consider whether the
  responsibility should be extracted into a public collaborator or whether the public
  behavior test is missing an important case.
- Prefer concise names such as `test_<subject>_<expected_behavior>_when_<condition>`.
- Use Arrange-Act-Assert structure for longer tests.
- Add tests for:
  - boundary values
  - guard clauses
  - exception paths
  - chunking and dedupe behavior
  - JSON serialization behavior
- Mock or isolate external dependencies such as audio devices, Ollama, filesystem paths, and clocks.
- Do not require live audio hardware or a running Ollama server in unit tests.

## Runtime Boundaries

- `audio_stream.py` should remain focused on stream buffering and overflow reporting.
- `transcribe.py` should wrap faster-whisper setup and inference only.
- `ollama_client.py` should contain HTTP details and translate HTTP failures into `OllamaError`.
- `summarize.py` should orchestrate chunking, prompts, and client calls.
- `live.py` may coordinate the realtime flow, but avoid moving low-level audio, HTTP, or formatting logic into it.
- Shared formatting belongs in helper modules such as `output.py`.

## Generated Files

- Do not commit generated sessions from `output/`.
- Session artifacts may include:
  - `transcript_live.md`
  - `minutes_draft.md`
  - `minutes.md`
  - `metadata.json`
- Keep documentation examples in sync with actual generated outputs and CLI options.

## Git and Review

- Prefer focused changes with tests.
- Use conventional commit style when creating commits.
- Before handing off, run:

```bash
uv run ruff check src tests
uv run mypy src
uv run pytest
```

Run `uv run ruff format src tests` when code formatting may have changed.
