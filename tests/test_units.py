"""Unit tests — srt formatting, segmentation, chunking."""

import numpy as np

from video2subtitle.engines.chunking import split_chunks
from video2subtitle.engines.segmentation import build_segments
from video2subtitle.srt import to_srt
from video2subtitle.engines.base import Segment


def test_srt_format():
    segs = [Segment(0.0, 1.5, "你好。"), Segment(61.25, 62.0, "Hello world")]
    srt = to_srt(segs)
    blocks = srt.strip().split("\n\n")
    assert len(blocks) == 2
    assert blocks[0].splitlines() == ["1", "00:00:00,000 --> 00:00:01,500", "你好。"]
    assert blocks[1].splitlines() == ["2", "00:01:01,250 --> 00:01:02,000", "Hello world"]


def test_srt_skips_empty_and_fixes_zero_span():
    segs = [Segment(5.0, 5.0, "x"), Segment(9.0, 9.5, "")]
    srt = to_srt(segs)
    assert "00:00:05,000 --> 00:00:05,500" in srt
    assert srt.count("\n\n") == 0


def test_segmentation_by_pause():
    toks = ["你", "好", "。", "世", "界", "。"]
    tss = [0.0, 0.2, 0.4, 3.0, 3.2, 3.4]
    segs = build_segments(toks, tss, pause_s=1.5)
    assert len(segs) == 2
    assert segs[0] == (0.0, 0.4, "你好。")
    assert segs[1] == (3.0, 3.4, "世界。")


def test_segmentation_by_terminal_punct():
    toks = ["你", "好", "。", "世", "界"]
    tss = [0.0, 0.2, 0.4, 0.5, 0.7]  # no big pause, but 。 terminates
    segs = build_segments(toks, tss, pause_s=1.5)
    assert len(segs) == 2
    assert segs[0][2] == "你好。"
    assert segs[1][2] == "世界"


def test_segmentation_single():
    segs = build_segments(["一", "二", "三"], [1.0, 1.1, 1.2])
    assert segs == [(1.0, 1.2, "一二三")]


def test_segmentation_max_dur_force_split():
    # 60 s of dense tokens with no pauses: must be force-split
    toks = [f"w{i}" for i in range(60)]
    tss = [i * 1.0 for i in range(60)]
    segs = build_segments(toks, tss, pause_s=1.5, max_dur=20.0)
    assert len(segs) >= 3
    for s, e, _ in segs:
        assert e - s <= 20.0
    # pieces cover the whole span without gaps/overlap
    assert segs[0][0] == 0.0 and segs[-1][1] == 59.0
    for (a1, b1, _), (a2, _, _) in zip(segs, segs[1:]):
        assert b1 <= a2 + 1e-6


def test_segmentation_max_dur_no_effect_when_short():
    toks = ["你", "好"]
    tss = [0.0, 0.5]
    assert build_segments(toks, tss, max_dur=20.0) == [(0.0, 0.5, "你好")]


def test_chunking_short_returns_single():
    sr = 16000
    samples = np.zeros(sr * 2, dtype=np.float32)
    assert split_chunks(samples, sr, chunk_seconds=30.0) == [(0, len(samples))]


def test_chunking_long_monotonic_silence_snapped():
    sr = 16000
    # 10 s: speech 0-3s, silence 3-4s, speech 4-7s, silence 7-8s, speech 8-10s
    samples = np.zeros(sr * 10, dtype=np.float32)
    for a, b in [(0, 3), (4, 7), (8, 10)]:
        samples[a * sr : b * sr] = 0.5
    chunks = split_chunks(samples, sr, chunk_seconds=3.0, snap_radius_s=1.5)
    assert len(chunks) >= 3
    bounds = [c[0] for c in chunks] + [chunks[-1][1]]
    assert bounds == sorted(bounds)
    assert bounds[0] == 0
    assert bounds[-1] == len(samples)
    # first cut should land inside the 3-4s silence (24000..32000)
    first_cut = chunks[0][1]
    assert 3.0 * sr <= first_cut <= 4.0 * sr
    # no chunk slices audio in half at full volume: every cut is in a quiet spot
    for (a, b) in chunks[:-1]:
        cut_zone = samples[max(0, a - 1600): min(len(samples), a + 1600)]
        assert np.abs(cut_zone).max() <= 0.5
