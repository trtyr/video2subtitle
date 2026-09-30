"""Tests for the subtitle output formats (SRT / VTT / ASS / TXT)."""

from video2subtitle.engines.base import Segment
from video2subtitle.formats import FORMATS, to_ass, to_srt, to_txt, to_vtt

SEGS = [Segment(0.0, 1.5, "你好。"), Segment(61.25, 62.0, "Hello world")]


def test_srt_format():
    blocks = to_srt(SEGS).strip().split("\n\n")
    assert blocks[0].splitlines() == ["1", "00:00:00,000 --> 00:00:01,500", "你好。"]
    assert blocks[1].splitlines() == ["2", "00:01:01,250 --> 00:01:02,000", "Hello world"]


def test_vtt_format():
    vtt = to_vtt(SEGS)
    assert vtt.startswith("WEBVTT")
    blocks = vtt.strip().split("\n\n")[1:]  # drop the WEBVTT header
    assert blocks[0].splitlines() == ["1", "00:00:00.000 --> 00:00:01.500", "你好。"]
    assert "00:01:01.250 --> 00:01:02.000" in blocks[1]


def test_ass_format():
    ass = to_ass(SEGS)
    assert ass.startswith("[Script Info]")
    assert "[Events]" in ass
    assert "Dialogue: 0,0:00:00.00,0:00:01.50,Default,,0,0,0,,你好。" in ass
    assert "Dialogue: 0,0:01:01.25,0:01:02.00,Default,,0,0,0,,Hello world" in ass


def test_txt_format():
    txt = to_txt(SEGS)
    assert txt == "你好。\nHello world\n"


def test_all_formats_registered():
    assert set(FORMATS) == {"srt", "vtt", "ass", "txt"}


def test_empty_and_zero_span_skipped():
    segs = [Segment(5.0, 5.0, "x"), Segment(9.0, 9.5, "  ")]
    srt = to_srt(segs)
    assert srt.count("\n\n") == 0
    assert srt.startswith("1\n00:00:05,000 --> 00:00:05,500\nx\n")
    vtt = to_vtt(segs)
    assert vtt.count("\n\n") == 1  # header separator + single cue
    assert to_ass(segs).count("Dialogue:") == 1
    assert to_txt(segs) == "x\n"
