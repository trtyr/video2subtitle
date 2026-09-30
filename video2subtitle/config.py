"""Runtime configuration — everything via environment variables (V2S_* prefix)."""

import os
from pathlib import Path


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name, "")
    try:
        return int(raw) if raw else default
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    raw = os.environ.get(name, "")
    try:
        return float(raw) if raw else default
    except ValueError:
        return default


class Settings:
    def __init__(self) -> None:
        env = os.environ
        self.host: str = env.get("V2S_HOST", "127.0.0.1")
        self.port: int = _int("V2S_PORT", 8765)
        self.token: str = env.get("V2S_TOKEN", "")
        self.allow_no_token: bool = env.get("V2S_ALLOW_NO_TOKEN", "") == "1"
        self.data_dir: Path = Path(env.get("V2S_DATA_DIR", "data")).resolve()

        # qwen3 (default) | sensevoice
        self.engine_name: str = env.get("V2S_ENGINE", "qwen3").strip().lower()

        self.sensevoice_model_dir: Path = Path(
            env.get(
                "V2S_SENSEVOICE_MODEL_DIR",
                str(Path.home() / ".local/share/video2subtitle/models/sensevoice-small-int8"),
            )
        ).resolve()
        self.qwen3_model_dir: Path = Path(
            env.get(
                "V2S_QWEN3_MODEL_DIR",
                str(Path.home() / ".local/share/video2subtitle/models/qwen3-asr-0.6b-int8"),
            )
        ).resolve()

        self.max_upload_mb: int = _int("V2S_MAX_UPLOAD_MB", 100)
        self.max_duration_s: int = _int("V2S_MAX_DURATION_S", 7200)
        self.result_ttl_hours: int = _int("V2S_RESULT_TTL_HOURS", 168)
        self.queue_timeout_s: int = _int("V2S_QUEUE_TIMEOUT_S", 1800)
        self.num_threads: int = _int("V2S_THREADS", os.cpu_count() or 4)
        self.chunk_seconds: float = _float("V2S_CHUNK_SECONDS", 30.0)
        self.qwen3_chunk_seconds: float = _float("V2S_QWEN3_CHUNK_SECONDS", 15.0)
        self.qwen3_max_new_tokens: int = _int("V2S_QWEN3_MAX_NEW_TOKENS", 256)
        self.hotwords: str = env.get("V2S_HOTWORDS", "")
        self.ffmpeg: str = env.get("V2S_FFMPEG", "ffmpeg")
        self.ffprobe: str = env.get("V2S_FFPROBE", "ffprobe")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    def model_dir_for(self, engine_name: str) -> Path:
        return self.qwen3_model_dir if engine_name.startswith("qwen3") else self.sensevoice_model_dir
