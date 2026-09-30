"""Task store — in-memory dict + per-task JSON persistence (survives restarts)."""

import json
import os
import shutil
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_iso(s: str) -> float:
    return datetime.fromisoformat(s).timestamp()


class TaskStore:
    def __init__(self, data_dir: Path) -> None:
        self.tasks_dir = Path(data_dir) / "tasks"
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self._tasks: dict[str, dict] = {}
        self._lock = threading.RLock()
        self._load_all()

    # -- layout ------------------------------------------------------------
    def _dir(self, task_id: str) -> Path:
        return self.tasks_dir / task_id

    def audio_path(self, task_id: str) -> Path:
        return self._dir(task_id) / "audio.original"

    def wav_path(self, task_id: str) -> Path:
        return self._dir(task_id) / "audio16k.wav"

    # -- persistence ---------------------------------------------------------
    def _load_all(self) -> None:
        for meta in sorted(self.tasks_dir.glob("*/task.json")):
            try:
                rec = json.loads(meta.read_text(encoding="utf-8"))
                self._tasks[rec["task_id"]] = rec
            except Exception:
                continue  # corrupt record: ignore
        # crash recovery: anything stuck in processing goes back to queued
        for rec in list(self._tasks.values()):
            if rec.get("state") == "processing":
                rec["state"] = "queued"
                rec["progress"] = 0
                self._save(rec)

    def _save(self, rec: dict) -> None:
        d = self._dir(rec["task_id"])
        d.mkdir(parents=True, exist_ok=True)
        tmp = d / "task.json.tmp"
        tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, d / "task.json")

    # -- api -----------------------------------------------------------------
    def create(self) -> dict:
        task_id = uuid.uuid4().hex[:12]
        rec = {
            "task_id": task_id,
            "state": "queued",
            "progress": 0,
            "engine": None,
            "audio_duration_s": None,
            "timings": {},
            "error": None,
            "result": None,
            "created_at": _now_iso(),
            "started_at": None,
            "finished_at": None,
        }
        with self._lock:
            self._tasks[task_id] = rec
            self._save(rec)
        return rec

    def get(self, task_id: str) -> dict | None:
        with self._lock:
            return self._tasks.get(task_id)

    def all(self) -> list[dict]:
        with self._lock:
            return sorted(self._tasks.values(), key=lambda r: r["created_at"])

    def pending(self) -> list[dict]:
        with self._lock:
            return sorted(
                (r for r in self._tasks.values() if r["state"] == "queued"),
                key=lambda r: r["created_at"],
            )

    def queue_position(self, task_id: str) -> int | None:
        pend = self.pending()
        for i, r in enumerate(pend):
            if r["task_id"] == task_id:
                return i + 1
        return None

    def update(self, rec: dict, **fields) -> None:
        with self._lock:
            rec.update(fields)
            self._save(rec)

    def save_audio(self, task_id: str, data: bytes) -> None:
        d = self._dir(task_id)
        d.mkdir(parents=True, exist_ok=True)
        self.audio_path(task_id).write_bytes(data)

    def delete(self, task_id: str) -> bool:
        with self._lock:
            rec = self._tasks.pop(task_id, None)
        if rec is None:
            return False
        shutil.rmtree(self._dir(task_id), ignore_errors=True)
        return True

    def age_seconds(self, rec: dict) -> float:
        try:
            return max(0.0, datetime.now(timezone.utc).timestamp() - _parse_iso(rec["created_at"]))
        except Exception:
            return 0.0

    def sweep(self, ttl_hours: int, now: float | None = None) -> int:
        """Delete finished tasks older than TTL. Returns number removed."""
        now = now if now is not None else datetime.now(timezone.utc).timestamp()
        removed = 0
        for rec in self.all():
            if rec["state"] not in ("completed", "failed"):
                continue
            fin = rec.get("finished_at")
            if not fin:
                continue
            try:
                if now - _parse_iso(fin) > timedelta(hours=ttl_hours).total_seconds():
                    removed += 1 if self.delete(rec["task_id"]) else 0
            except Exception:
                continue
        return removed
