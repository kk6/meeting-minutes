# meeting-minutes development tasks

set shell := ["bash", "-euo", "pipefail", "-c"]

# Show all available recipes
default:
    @just --list --unsorted

# ─── Environment ──────────────────────────────────────────────────────────────

# Install development dependencies
[group('env')]
sync:
    uv sync

# ─── Development ──────────────────────────────────────────────────────────────

# Format code (auto-fix)
[group('dev')]
fmt:
    uv run ruff format .

# Format check only (CI)
[group('dev')]
fmt-check:
    uv run ruff format --check .

# Lint code (auto-fix)
[group('dev')]
lint:
    uv run ruff check . --fix

# Lint check only (CI)
[group('dev')]
lint-check:
    uv run ruff check .

# Type check
[group('dev')]
typecheck:
    uv run mypy .

# Run tests (pass args: just test -v)
[group('dev')]
test *args:
    uv run pytest {{ args }}

# Lint・format・型検査のみ（テストなし）
[group('dev')]
check-lint: fmt-check lint-check typecheck

# Run all quality checks without auto-fix (for CI / pre-push)
[group('dev')]
check: fmt-check lint-check typecheck test

# ─── Application ──────────────────────────────────────────────────────────────

# Run meeting-minutes CLI (pass args: just mm --help)
[group('app')]
mm *args:
    uv run meeting-minutes {{ args }}
