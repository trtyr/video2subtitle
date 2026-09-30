"""Sentence segmentation from token timestamps.

Split on >=1.5 s inter-token pauses or right after terminal punctuation.
Segments longer than max_dur are force-split at their largest internal
token gap (handles languages/audio without natural pauses, e.g. fluent
English TTS where neither pauses nor punctuation tokens occur).
"""

TERMINAL_PUNCT = set("。！？!?；;…")

# special tokens like <|zh|>, <|NEUTRAL|> — never part of text
SPECIAL_PREFIX = "<|"


def is_special(tok: str) -> bool:
    return tok.startswith(SPECIAL_PREFIX)


def _display(tok: str) -> str:
    if not tok:
        return ""
    # sentencepiece-style word marker -> space (latin); CJK tokens have none
    return tok.replace("▁", " ")


def join_texts(texts: list[str]) -> str:
    """Join chunk texts; insert a space between ascii-alnum boundaries only."""
    out = ""
    for t in texts:
        t = t.strip()
        if not t:
            continue
        if out and out[-1].isascii() and out[-1].isalnum() and t[0].isascii() and t[0].isalnum():
            out += " "
        out += t
    return out


def _force_split(tokens: list[str], ts: list[float], max_dur: float):
    dur = ts[-1] - ts[0]
    text = "".join(_display(t) for t in tokens).strip()
    if len(tokens) < 2 or dur <= max_dur:
        return [(ts[0], ts[-1], text)]
    gaps = [ts[i + 1] - ts[i] for i in range(len(ts) - 1)]
    i = gaps.index(max(gaps))
    if gaps[i] <= 0:
        return [(ts[0], ts[-1], text)]
    left = _force_split(tokens[: i + 1], ts[: i + 1], max_dur)
    right = _force_split(tokens[i + 1:], ts[i + 1:], max_dur)
    return left + right


def build_segments(
    tokens: list[str],
    timestamps: list[float],
    pause_s: float = 1.5,
    max_dur: float | None = None,
) -> list[tuple[float, float, str]]:
    groups: list[tuple[list[str], list[float]]] = []  # (tokens, ts) per segment
    cur_t: list[str] = []
    cur_s: list[float] = []
    prev_ts: float | None = None

    for tok, ts in zip(tokens, timestamps):
        if tok is None or ts is None:
            continue
        if cur_t and ((prev_ts is not None and ts - prev_ts >= pause_s) or (
                _display(cur_t[-1]) and _display(cur_t[-1])[-1] in TERMINAL_PUNCT)):
            groups.append((cur_t, cur_s))
            cur_t, cur_s = [], []
        cur_t.append(tok)
        cur_s.append(ts)
        prev_ts = ts

    if cur_t:
        groups.append((cur_t, cur_s))

    segs: list[tuple[float, float, str]] = []
    for t_list, s_list in groups:
        if max_dur and len(s_list) >= 2 and (s_list[-1] - s_list[0]) > max_dur:
            segs.extend(_force_split(t_list, s_list, max_dur))
        else:
            text = "".join(_display(t) for t in t_list).strip()
            if text:
                segs.append((s_list[0], s_list[-1], text))
    return [(s, e, t) for s, e, t in segs if t]
