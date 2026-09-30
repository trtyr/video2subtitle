import io
import math
import struct
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from video2subtitle.config import Settings
from video2subtitle.engines.base import Segment, Transcript
from video2subtitle.main import create_app

AUTH = {"Authorization": "Bearer test-token"}


class FakeEngine:
    name = "fake"
    backend = "fake-backend"
    sample_rate = 16000

    def __init__(self) -> None:
        self._ready = False
        self.calls = 0

    def load(self) -> None:
        self._ready = True

    @property
    def ready(self) -> bool:
        return self._ready

    def transcribe(self, wav_path: Path, progress=None) -> Transcript:
        self.calls += 1
        if progress:
            progress(50)
            progress(100)
        return Transcript(
            lang="zh",
            text="你好世界。测试完成。",
            segments=[Segment(0.0, 0.8, "你好世界。"), Segment(1.2, 2.0, "测试完成。")],
        )


def wav_bytes(seconds: float = 0.5, sr: int = 16000) -> bytes:
    n = int(seconds * sr)
    frames = struct.pack(
        f"<{n}h", *[int(8000 * math.sin(2 * math.pi * 220 * i / sr)) for i in range(n)]
    )
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(frames)
    return buf.getvalue()


def make_settings(tmp_path: Path, **overrides) -> Settings:
    s = Settings()
    s.token = "test-token"
    s.allow_no_token = False
    s.data_dir = tmp_path / "data"
    for k, v in overrides.items():
        setattr(s, k, v)
    return s


def make_client(settings: Settings, engine=None):
    eng = engine or FakeEngine()
    app = create_app(settings=settings, engine=eng)
    client = TestClient(app)
    return client, eng


@pytest.fixture
def settings(tmp_path):
    return make_settings(tmp_path)


@pytest.fixture
def ctx(settings):
    client, engine = make_client(settings)
    with client:
        yield {"client": client, "engine": engine, "settings": settings}


def wait_terminal(client: TestClient, task_id: str, timeout: float = 10.0) -> dict:
    import time

    deadline = time.time() + timeout
    while time.time() < deadline:
        r = client.get(f"/v1/transcripts/{task_id}", headers=AUTH)
        assert r.status_code == 200, r.text
        st = r.json()
        if st["state"] in ("completed", "failed"):
            return st
        time.sleep(0.05)
    raise AssertionError("timeout waiting for terminal state")


def submit(client: TestClient, data: bytes | None = None, filename: str = "a.wav") -> dict:
    if data is None:
        data = wav_bytes()
    r = client.post(
        "/v1/transcripts",
        headers=AUTH,
        files={"file": (filename, data, "audio/wav")},
    )
    return r
