"""ユーザー向けメッセージを持つドメイン固有の例外。"""


class MeetingMinutesError(Exception):
    """想定内のアプリケーション障害の基底例外。"""


class DeviceNotFoundError(MeetingMinutesError):
    """要求されたオーディオ入力デバイスを解決できない場合に送出される。"""


class OllamaError(MeetingMinutesError):
    """ローカルの Ollama API が生成を完了できない場合に送出される。"""


class TranscriptionError(MeetingMinutesError):
    """Whisper のセットアップまたは文字起こしが失敗した場合に送出される。"""
