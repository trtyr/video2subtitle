"""SRT generation from segments — standard HH:MM:SS,mmm blocks."""

from typing import Iterable

from .engines.base import Segment


def _fmt_ts(t: float) -> str:
    ms = max(0, int(round(t * 1000)))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def to_srt(segments: Iterable[Segment]) -> str:
    lines: list[str] = []
    for i, seg in enumerate(segments, 1):
        start, end = seg.start, seg.end
        if end <= start:
            end = start + 0.5
        text = (seg.text or "").strip()
        if not text:
            continue
        lines.append(f"{i}\n{_fmt_ts(start)} --> {_fmt_ts(end)}\n{text}\n")
    return "\n".join(lines)
