"""First-start model auto-download for the bundled engines.

If the selected engine's model files are missing, fetch the official
sherpa-onnx release archive and unpack it into the configured model dir.
Mirror candidates are tried in order so downloads also work from networks
with poor GitHub connectivity; set V2S_GH_MIRROR to put your preferred
prefix mirror first.
"""

from __future__ import annotations

import logging
import os
import shutil
import tarfile
import time
import urllib.request
from pathlib import Path

log = logging.getLogger("video2subtitle.model_dl")

_RELEASE = "https://github.com/k2-fsa/sherpa-onnx/releases/download"
_DEFAULT_MIRRORS = ("", "https://ghfast.top/", "https://gh-proxy.com/")  # "" = direct

# minimum plausible archive size, to reject truncated/partial downloads
_MIN_ARCHIVE_BYTES = 100 * 1024 * 1024

SPECS: dict[str, dict] = {
    "sensevoice": {
        "archive": "asr-models/sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17.tar.bz2",
        "inner": "sherpa-onnx-sense-voice-zh-en-ja-ko-yue-2024-07-17",
        "entries": ["model.int8.onnx", "tokens.txt"],
        "size_mb": 240,
    },
    "qwen3": {
        "archive": "asr-models/sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25.tar.bz2",
        "inner": "sherpa-onnx-qwen3-asr-0.6B-int8-2026-03-25",
        "entries": ["conv_frontend.onnx", "encoder.int8.onnx", "decoder.int8.onnx", "tokenizer"],
        "size_mb": 950,
    },
}


def engine_key(engine_name: str) -> str:
    return "qwen3" if engine_name.startswith("qwen3") else "sensevoice"


def files_present(model_dir: Path, engine_key: str) -> bool:
    spec = SPECS[engine_key]
    d = Path(model_dir)
    return all((d / e).exists() for e in spec["entries"])


def _candidates() -> list[str]:
    """URL prefixes to try, user mirror first, direct GitHub last."""
    mirror = os.environ.get("V2S_GH_MIRROR", "").strip()
    candidates = []
    if mirror:
        candidates.append(mirror if mirror.endswith("/") else mirror + "/")
    candidates.extend(_DEFAULT_MIRRORS)
    return candidates


def _download(url: str, dst: Path, size_mb: int) -> None:
    log.info("downloading %s (%d MB) -> %s", url, size_mb, dst)
    req = urllib.request.Request(url, headers={"User-Agent": "video2subtitle/0.1"})
    started = time.monotonic()
    window_start, window_done = started, 0
    last_pct = -10
    with urllib.request.urlopen(req, timeout=120) as resp, open(dst, "wb") as f:
        total = int(resp.headers.get("Content-Length") or 0)
        done = 0
        while True:
            chunk = resp.read(1 << 20)
            if not chunk:
                break
            f.write(chunk)
            done += len(chunk)
            elapsed = time.monotonic() - started
            now = time.monotonic()
            # slow-but-alive connections must not stall the mirror chain:
            # judge by recent 10 s throughput, not the cumulative average
            if now - window_start >= 10:
                recent = (done - window_done) / (now - window_start)
                if recent < 256 * 1024:
                    raise RuntimeError(
                        f"download too slow ({recent / 1024:.0f} KB/s in last 10s), "
                        f"failing over to next candidate"
                    )
                window_start, window_done = now, done
            if total:
                pct = done * 100 // total
                if pct >= last_pct + 10:
                    last_pct = pct
                    log.info("  %d%% (%.0f / %d MB)", pct, done / 1e6, total / 1e6)
    log.info("downloaded %.0f MB", done / 1e6)


def ensure_model(engine_key: str, model_dir: Path) -> Path:
    """Make sure the model exists under model_dir; download + unpack if not."""
    if engine_key not in SPECS:
        raise ValueError(f"unknown engine key: {engine_key!r} (expected {sorted(SPECS)})")
    spec = SPECS[engine_key]
    model_dir = Path(model_dir)
    if files_present(model_dir, engine_key):
        return model_dir

    log.info("model for %s not found under %s — checking archives / downloading", engine_key, model_dir)
    model_dir.mkdir(parents=True, exist_ok=True)
    base = f"{_RELEASE}/{spec['archive']}"
    tmp = model_dir / (spec["inner"] + ".tar.bz2")
    last_err: Exception | None = None

    if tmp.exists() and tmp.stat().st_size >= _MIN_ARCHIVE_BYTES:
        log.info("complete archive already present (%.0f MB) — skipping download",
                 tmp.stat().st_size / 1e6)
    else:
        for prefix in _candidates():
            url = prefix + base
            try:
                _download(url, tmp, spec["size_mb"])
                actual = tmp.stat().st_size
                if actual < _MIN_ARCHIVE_BYTES:
                    raise RuntimeError(f"archive too small ({actual} bytes), likely truncated")
                break
            except Exception as e:  # noqa: BLE001
                last_err = e
                log.warning("download failed from %s: %s", prefix or "direct", e)
                tmp.unlink(missing_ok=True)
        if not tmp.exists():
            raise RuntimeError(
                f"could not download {spec['archive']} from any mirror: {last_err}. "
                f"Download it manually and set the engine model dir env var."
            )

    log.info("extracting %s", tmp.name)
    with tarfile.open(tmp, "r:bz2") as tf:
        tf.extractall(model_dir, filter="data")  # noqa: S202 - fixed upstream archive
    inner = model_dir / spec["inner"]
    if not inner.is_dir():
        raise RuntimeError(f"archive layout unexpected: {spec['inner']} not found after extract")
    for entry in spec["entries"]:
        shutil.move(str(inner / entry), str(model_dir / entry))
    shutil.rmtree(inner, ignore_errors=True)
    tmp.unlink(missing_ok=True)
    log.info("model ready: %s", model_dir)
    return model_dir
