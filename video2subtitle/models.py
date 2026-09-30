"""API response models (pydantic) — field names are contract."""

from typing import Any, Optional

from pydantic import BaseModel


class ErrorBody(BaseModel):
    code: str
    message: str


class SegmentModel(BaseModel):
    start: float
    end: float
    text: str


class ResultModel(BaseModel):
    lang: str
    text: str
    segments: list[SegmentModel]
    srt: str


class TaskStatus(BaseModel):
    task_id: str
    state: str  # queued | processing | completed | failed
    progress: int  # 0-100
    queue_position: Optional[int] = None
    engine: Optional[str] = None
    audio_duration_s: Optional[float] = None
    timings: dict[str, Any] = {}
    error: Optional[ErrorBody] = None
    result: Optional[ResultModel] = None
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class Health(BaseModel):
    status: str
    version: str
    engine: dict[str, Any]
    engines: list[dict[str, Any]] = []
    model_ready: bool
    queue_depth: int
