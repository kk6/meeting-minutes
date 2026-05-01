"""PortAudio (sounddevice) から入力デバイス一覧を取得し、名前/index で解決する。"""

from dataclasses import dataclass
from typing import Any

import sounddevice as sd

from meeting_minutes.errors import DeviceNotFoundError


@dataclass(frozen=True)
class InputDevice:
    """利用可能な音声入力デバイスのメタ情報。"""

    index: int
    name: str
    channels: int
    default_sample_rate: float
    is_blackhole: bool


def list_input_devices() -> list[InputDevice]:
    """入力チャンネル数 1 以上のデバイスのみを抽出して返す。"""
    raw_devices = sd.query_devices()
    devices: list[InputDevice] = []
    for index, device in enumerate(raw_devices):
        device_info = dict(device)
        channels = int(device_info.get("max_input_channels", 0))
        if channels <= 0:
            continue
        name = str(device_info.get("name", "Unknown"))
        devices.append(
            InputDevice(
                index=index,
                name=name,
                channels=channels,
                default_sample_rate=float(device_info.get("default_samplerate", 0)),
                is_blackhole="blackhole" in name.lower(),
            )
        )
    return devices


def resolve_input_device(device_name: str | None, device_index: int | None) -> InputDevice:
    """index → 完全一致名 → 部分一致名 → OS 既定 → 先頭 の優先順位でデバイスを解決する。

    Raises:
        DeviceNotFoundError: 指定条件に一致するデバイスも、利用可能なデバイスも存在しない場合。
    """
    devices = list_input_devices()
    if device_index is not None:
        for device in devices:
            if device.index == device_index:
                return device
        raise DeviceNotFoundError(
            f"指定された入力デバイスindexが見つかりませんでした: {device_index}"
        )

    if device_name:
        lowered = device_name.lower()
        for device in devices:
            if device.name.lower() == lowered:
                return device
        for device in devices:
            if lowered in device.name.lower():
                return device
        raise DeviceNotFoundError(f"指定された入力デバイスが見つかりませんでした: {device_name}")

    defaults = sd.query_devices(kind="input")
    default_info: dict[str, Any] = dict(defaults)
    default_name = str(default_info.get("name", ""))
    for device in devices:
        if device.name == default_name:
            return device

    if devices:
        return devices[0]
    raise DeviceNotFoundError("利用可能な入力デバイスが見つかりませんでした")
