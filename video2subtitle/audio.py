"""Audio validation + normalization via ffmpeg/ffprobe."""

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .errors import ApiError, Codes

# ffprobe format_name values we accept (substring match against the comma list)
ALLOWED_FORMATS = {
    "wav", "mp3", "ogg", "opus", "m4a", "mp4", "flac",
    "webm", "matroska", "aiff", "aif", "wma", "amr", "aac",
}


@dataclass
class AudioInfo:
    duration_s: float
    format_name: str
    sample_rate: int
    channels: int
    codec: str


def probe(ffprobe: str, path: Path) -> AudioInfo:
    """Identify a media file. Raises 415 if unidentifiable / not audio."""
    cmd = [
        ffprobe, "-v", "error", "-print_format", "json",
        "-show_format", "-show_streams", str(path),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=120)
    except FileNotFoundError as e:
        raise ApiError(500, Codes.INTERNAL_ERROR, f"ffprobe not available: {e}") from e
    if proc.returncode != 0:
        raise ApiError(
            415, Codes.UNSUPPORTED_MEDIA_TYPE,
            "unrecognized or corrupted media file",
        )
    try:
        data = json.loads(proc.stdout.decode("utf-8", "replace"))
    except json.JSONDecodeError as e:
        raise ApiError(415, Codes.UNSUPPORTED_MEDIA_TYPE, "unidentifiable media file") from e

    fmt = data.get("format", {})
    fmt_name = (fmt.get("format_name") or "").lower()
    if not fmt_name:
        raise ApiError(415, Codes.UNSUPPORTED_MEDIA_TYPE, "unidentifiable media file")
    if not any(f in fmt_name for f in ALLOWED_FORMATS):
        raise ApiError(415, Codes.UNSUPPORTED_MEDIA_TYPE, f"unsupported container: {fmt_name}")

    audio_streams = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
    if not audio_streams:
        raise ApiError(415, Codes.UNSUPPORTED_MEDIA_TYPE, "no audio stream found")
    st = audio_streams[0]
    try:
        duration = float(fmt.get("duration") or st.get("duration") or 0)
    except (TypeError, ValueError):
        duration = 0.0
    return AudioInfo(
        duration_s=duration,
        format_name=fmt_name,
        sample_rate=int(st.get("sample_rate") or 0),
        channels=int(st.get("channels") or 0),
        codec=str(st.get("codec_name") or ""),
    )


def normalize(ffmpeg: str, src: Path, dst: Path) -> None:
    """Decode any supported input to 16 kHz mono s16 PCM wav."""
    cmd = [
        ffmpeg, "-y", "-v", "error",
        "-i", str(src),
        "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
        str(dst),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=1800)
    except FileNotFoundError as e:
        raise ApiError(500, Codes.INTERNAL_ERROR, f"ffmpeg not available: {e}") from e
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace")[-300:]
        raise ApiError(422, Codes.INVALID_AUDIO, f"ffmpeg failed to decode audio: {detail}")


def load_wav_f32(path: Path):
    """Read the normalized 16k mono s16 wav as float32 samples in [-1, 1)."""
    import wave

    import numpy as np

    with wave.open(str(path), "rb") as w:
        if w.getnchannels() != 1 or w.getframerate() != 16000 or w.getsampwidth() != 2:
            raise ApiError(422, Codes.INVALID_AUDIO, "expected normalized 16 kHz mono s16 wav")
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
