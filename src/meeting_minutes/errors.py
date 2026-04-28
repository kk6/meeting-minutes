"""Domain-specific exceptions with user-facing messages."""


class MeetingMinutesError(Exception):
    """Base exception for expected application failures."""


class DeviceNotFoundError(MeetingMinutesError):
    """Raised when a requested audio input device cannot be resolved."""


class OllamaError(MeetingMinutesError):
    """Raised when the local Ollama API cannot complete a generation."""


class TranscriptionError(MeetingMinutesError):
    """Raised when Whisper setup or transcription fails."""
