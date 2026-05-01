import numpy as np

from meeting_minutes.config import PreprocessingConfig
from meeting_minutes.preprocess import AudioPreprocessor


def test_preprocessor_is_noop_when_disabled() -> None:
    audio = np.array([0.1, -0.2], dtype=np.float32)

    processed = AudioPreprocessor(PreprocessingConfig(enabled=False)).process(audio)

    assert np.array_equal(processed, audio)


def test_preprocessor_normalizes_peak_upward() -> None:
    audio = np.array([0.1, -0.2], dtype=np.float32)

    processed = AudioPreprocessor(
        PreprocessingConfig(enabled=True, target_peak=0.8),
    ).process(audio)

    assert processed.dtype == np.float32
    assert np.max(np.abs(processed)) == np.float32(0.8)


def test_preprocessor_normalizes_peak_downward() -> None:
    audio = np.array([0.5, -1.0], dtype=np.float32)

    processed = AudioPreprocessor(
        PreprocessingConfig(enabled=True, target_peak=0.8),
    ).process(audio)

    assert processed.dtype == np.float32
    assert np.max(np.abs(processed)) == np.float32(0.8)


def test_preprocessor_does_not_amplify_silence() -> None:
    audio = np.zeros(4, dtype=np.float32)

    processed = AudioPreprocessor(PreprocessingConfig(enabled=True)).process(audio)

    assert np.array_equal(processed, audio)


def test_preprocessor_applies_noise_gate() -> None:
    audio = np.array([0.001, 0.01, -0.002], dtype=np.float32)

    processed = AudioPreprocessor(
        PreprocessingConfig(
            enabled=True,
            normalize_peak=False,
            noise_gate_enabled=True,
            noise_gate_threshold=0.003,
        ),
    ).process(audio)

    assert processed.dtype == np.float32
    assert np.array_equal(processed, np.array([0.0, 0.01, 0.0], dtype=np.float32))
