"""Subtitle output formats: SRT / VTT / ASS / TXT."""

from pathlib import Path
from typing import Iterable

from .engines.base import Segment


def _fmt_srt(t: float) -> str:
    ms = max(0, int(round(t * 1000)))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _fmt_vtt(t: float) -> str:
    ms = max(0, int(round(t * 1000)))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d}.{ms:03d}"


def _fmt_ass(t: float) -> str:
    cs = max(0, int(round(t * 100)))
    h, rem = divmod(cs, 360_000)
    m, rem = divmod(rem, 6_000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _clean(segments: Iterable[Segment]):
    """Normalize spans: skip empty text, fix zero-length cues."""
    for seg in segments:
        text = (seg.text or "").strip()
        if not text:
            continue
        end = seg.end if seg.end > seg.start else seg.start + 0.5
        yield seg.start, end, text


def to_srt(segments: Iterable[Segment]) -> str:
    lines: list[str] = []
    for i, (start, end, text) in enumerate(_clean(segments), 1):
        lines.append(f"{i}\n{_fmt_srt(start)} --> {_fmt_srt(end)}\n{text}\n")
    return "\n".join(lines)


def to_vtt(segments: Iterable[Segment]) -> str:
    lines: list[str] = ["WEBVTT", ""]
    for i, (start, end, text) in enumerate(_clean(segments), 1):
        lines.append(f"{i}\n{_fmt_vtt(start)} --> {_fmt_vtt(end)}\n{text}\n")
    return "\n".join(lines)


_ASS_HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Arial,60,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,2,2,80,80,60,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def to_ass(segments: Iterable[Segment]) -> str:
    lines: list[str] = [_ASS_HEADER]
    for start, end, text in _clean(segments):
        lines.append(f"Dialogue: 0,{_fmt_ass(start)},{_fmt_ass(end)},Default,,0,0,0,,{text}\n")
    return "\n".join(lines)


def to_txt(segments: Iterable[Segment]) -> str:
    return "".join(f"{text}\n" for _, _, text in _clean(segments))


FORMATS = {"srt": to_srt, "vtt": to_vtt, "ass": to_ass, "txt": to_txt}


def write_subtitle(segments: Iterable[Segment], fmt: str, path: Path) -> Path:
    if fmt not in FORMATS:
        raise ValueError(f"unknown subtitle format: {fmt!r} (expected {sorted(FORMATS)})")
    path = Path(path)
    path.write_text(FORMATS[fmt](segments), encoding="utf-8")
    return path
