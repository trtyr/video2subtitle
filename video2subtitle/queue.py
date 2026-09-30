"""Serial inference worker — one task at a time, FIFO, disk-backed state."""

import threading
import time
import traceback

from .audio import normalize, probe
from .config import Settings
from .engines.base import TranscriptionEngine
from .errors import ApiError, Codes
from .formats import to_srt
from .store import TaskStore


class SerialWorker:
    def __init__(self, store: TaskStore, engine: TranscriptionEngine, settings: Settings) -> None:
        self.store = store
        self.engine = engine
        self.settings = settings
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="transcribe-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=15)

    def notify(self) -> None:
        self._wake.set()

    def queue_depth(self) -> int:
        return len(self.store.pending())

    # ------------------------------------------------------------------
    def _run(self) -> None:
        while not self._stop.is_set():
            pend = self.store.pending()
            if not pend:
                self._wake.wait(timeout=2.0)
                self._wake.clear()
                continue
            self._process(pend[0])

    def _process(self, rec: dict) -> None:
        task_id = rec["task_id"]

        if self.store.age_seconds(rec) > self.settings.queue_timeout_s:
            self._finish(rec, state="failed",
                         error={"code": Codes.QUEUE_TIMEOUT, "message": "queued too long"})
            return
        if not self.engine.ready:
            self._finish(rec, state="failed",
                         error={"code": Codes.MODEL_NOT_READY, "message": "model not loaded"})
            return

        self.store.update(rec, state="processing", started_at=self._now())
        t0 = time.time()
        try:
            src = self.store.audio_path(task_id)
            wav = self.store.wav_path(task_id)
            info = probe(self.settings.ffprobe, src)
            if info.duration_s > self.settings.max_duration_s + 1:
                raise ApiError(422, Codes.INVALID_AUDIO,
                               f"audio duration {info.duration_s:.0f}s exceeds limit "
                               f"{self.settings.max_duration_s}s")
            # already 16k mono pcm_s16 wav? use as-is, skip re-encode
            direct = (info.format_name.startswith("wav") and info.sample_rate == 16000
                      and info.channels == 1 and info.codec == "pcm_s16le")
            if direct:
                wav = src
            else:
                normalize(self.settings.ffmpeg, src, wav)
            t_decode = time.time()

            def cb(pct: int) -> None:
                self.store.update(rec, progress=max(0, min(99, pct)))

            transcript = self.engine.transcribe(wav, progress=cb)
            t_infer = time.time()

            result = {
                "lang": transcript.lang,
                "text": transcript.text,
                "segments": [
                    {"start": round(s.start, 3), "end": round(s.end, 3), "text": s.text}
                    for s in transcript.segments
                ],
                "srt": to_srt(transcript.segments),
            }
            self._finish(
                rec, state="completed", result=result, progress=100,
                engine=self.engine.name, audio_duration_s=round(info.duration_s, 3),
                timings={
                    "decode_s": round(t_decode - t0, 3),
                    "infer_s": round(t_infer - t_decode, 3),
                    "total_s": round(time.time() - t0, 3),
                },
            )
        except ApiError as e:
            self._finish(rec, state="failed", error={"code": e.code, "message": e.message})
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            self._finish(rec, state="failed",
                         error={"code": Codes.INFERENCE_FAILED, "message": f"inference failed: {e}"})

    def _finish(self, rec: dict, **fields) -> None:
        # record may have been DELETEd while processing — don't resurrect it
        if self.store.get(rec["task_id"]) is None:
            return
        fields.setdefault("finished_at", self._now())
        self.store.update(rec, **fields)

    @staticmethod
    def _now() -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat(timespec="seconds")
