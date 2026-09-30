"""Long-audio chunking with silence-snapped boundaries.

Fixed-size windows whose cut points slide to the quietest ~100 ms spot
within +-snap_radius, so we never cut through a word. This gives
incremental progress and bounded memory without hurting quality.
"""

import numpy as np


def split_chunks(
    samples: np.ndarray,
    sr: int,
    chunk_seconds: float,
    snap_radius_s: float = 4.0,
) -> list[tuple[int, int]]:
    n = len(samples)
    chunk = int(chunk_seconds * sr)
    if n <= chunk:
        return [(0, n)]

    block = max(1, sr // 10)  # 100 ms energy blocks
    nblocks = n // block
    if nblocks == 0:
        return [(0, n)]
    energy = (samples[: nblocks * block].astype(np.float32) ** 2).reshape(nblocks, block).mean(axis=1)

    rad = int(snap_radius_s * sr)
    bounds = [0]
    target = chunk
    while target < n:
        lo = max(bounds[-1] + block, target - rad)
        hi = min(n - block, target + rad)
        lo_i, hi_i = lo // block, hi // block
        if hi_i <= lo_i:
            cut = target
        else:
            quiet = lo_i + int(np.argmin(energy[lo_i : hi_i + 1]))
            cut = quiet * block + block // 2
            cut = max(bounds[-1] + block, min(cut, n - block))
        bounds.append(cut)
        target = cut + chunk
    if n - bounds[-1] < block:
        bounds.pop()
    bounds.append(n)

    return [(a, b) for a, b in zip(bounds[:-1], bounds[1:]) if b > a]
