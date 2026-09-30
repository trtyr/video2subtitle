"""Engine abstraction — swap engines (Qwen3-ASR / SenseVoice / future) here."""

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Protocol


@dataclass
class Segment:
    start: float  # seconds, float
    end: float
    text: str


@dataclass
class Transcript:
    lang: str
    text: str
    segments: list[Segment]


ProgressCb = Optional[Callable[[int], None]]


class TranscriptionEngine(Protocol):
    name: str
    backend: str
    sample_rate: int

    def load(self) -> None:
        """Load the model once; must be called before transcribe()."""
        ...

    @property
    def ready(self) -> bool:
        ...

    def transcribe(self, wav_path: Path, progress: ProgressCb = None) -> Transcript:
        """wav_path is a normalized 16 kHz mono s16 wav."""
        ...
