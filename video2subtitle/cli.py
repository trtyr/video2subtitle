"""video2subtitle CLI — a video/audio file or public URL in, a subtitle file out.

Examples:
    video2subtitle talk.mp4                     # -> talk.srt (local engine)
    video2subtitle talk.mp4 -f vtt -o out.vtt
    video2subtitle https://example.com/watch    # generic URL via yt-dlp
    video2subtitle talk.mp4 --server http://box:8765 --token SECRET
"""

import argparse
import os
import sys
import tempfile
import time
from pathlib import Path

from .config import Settings
from .engines import create_engine
from .engines.base import Segment
from .formats import FORMATS, write_subtitle


def _is_url(s: str) -> bool:
    return s.startswith(("http://", "https://"))


def _fetch_url(url: str, dest_dir: Path) -> Path:
    """Download the audio/video track of a public URL via yt-dlp (generic)."""
    import yt_dlp

    dest_dir.mkdir(parents=True, exist_ok=True)
    opts = {
        "format": "bestaudio/best",
        "outtmpl": str(dest_dir / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return Path(ydl.prepare_filename(info))


def _local_transcribe(path: Path, settings: Settings, progress=None):
    from .audio import normalize, probe
    from .model_dl import ensure_model

    eng = create_engine(settings)
    key = "qwen3" if eng.name.startswith("qwen3") else "sensevoice"
    if settings.auto_download:
        ensure_model(key, settings.model_dir_for(eng.name))
    eng.load()

    with tempfile.TemporaryDirectory(prefix="v2s-cli-") as td:
        wav = Path(td) / "audio16k.wav"
        info = probe(settings.ffprobe, path)
        already = (info.format_name.startswith("wav") and info.sample_rate == 16000
                   and info.channels == 1 and info.codec == "pcm_s16le")
        if already:
            wav = path
        else:
            normalize(settings.ffmpeg, path, wav)
        transcript = eng.transcribe(wav, progress=progress)
    return transcript, eng.name


def _remote_transcribe(server: str, token: str, path: Path, progress=None) -> list[Segment]:
    import json
    import urllib.request
    import uuid

    base = server.rstrip("/")
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f"Content-Disposition: form-data; name=\"file\"; filename=\"{path.name}\"\r\n"
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode() + path.read_bytes() + f"\r\n--{boundary}--\r\n".encode()
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(
        f"{base}/v1/transcripts", data=body, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=300) as resp:
        task = json.loads(resp.read())
    task_id = task["task_id"]
    print(f"  task {task_id} queued")

    deadline = time.time() + 4 * 3600
    last = None
    while time.time() < deadline:
        q = urllib.request.Request(f"{base}/v1/transcripts/{task_id}", headers=headers)
        with urllib.request.urlopen(q, timeout=30) as resp:
            st = json.loads(resp.read())
        if st["state"] != last:
            print(f"  {st['state']} {st.get('progress', 0)}%")
            last = st["state"]
        if progress and st["state"] == "processing":
            progress(int(st.get("progress") or 0))
        if st["state"] in ("completed", "failed"):
            if st["state"] == "failed":
                err = st.get("error") or {}
                raise RuntimeError(f"remote task failed: {err.get('code')}: {err.get('message')}")
            result = st["result"]
            return [Segment(s["start"], s["end"], s["text"]) for s in result["segments"]]
        time.sleep(2)
    raise RuntimeError("remote task timed out")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="video2subtitle",
        description="Self-hosted video → subtitles: a video/audio file or public "
                    "URL in, an SRT/VTT/ASS/TXT file out.",
    )
    parser.add_argument("input", help="video/audio file path, or a public media URL")
    parser.add_argument("-o", "--output", help="output path (default: alongside input, .<fmt>)")
    parser.add_argument("-f", "--format", choices=sorted(FORMATS), default="srt",
                        help="subtitle format (default: srt)")
    parser.add_argument("--engine", choices=["qwen3", "sensevoice"],
                        help="transcription engine for local mode (default: V2S_ENGINE or qwen3)")
    parser.add_argument("--server", help="remote video2subtitle server URL; "
                                         "skips the local engine entirely")
    parser.add_argument("--token", help="bearer token for --server (default: V2S_TOKEN)")
    parser.add_argument("--threads", type=int, help="inference threads for local mode")
    args = parser.parse_args(argv)

    tmp_url_dir: tempfile.TemporaryDirectory | None = None
    try:
        if _is_url(args.input):
            print(f"downloading {args.input} ...")
            tmp_url_dir = tempfile.TemporaryDirectory(prefix="v2s-url-")
            src = _fetch_url(args.input, Path(tmp_url_dir.name))
            print(f"downloaded -> {src.name}")
        else:
            src = Path(args.input)
            if not src.exists():
                parser.error(f"input not found: {src}")

        out = Path(args.output) if args.output else src.with_suffix(f".{args.format}")

        if args.server:
            segments = _remote_transcribe(
                args.server, args.token or os.environ.get("V2S_TOKEN", ""), src)
        else:
            settings = Settings()
            if args.engine:
                settings.engine_name = args.engine
            if args.threads:
                settings.num_threads = args.threads

            def progress(pct: int) -> None:
                print(f"\r  transcribing {pct:3d}%", end="", flush=True)

            transcript, engine_name = _local_transcribe(src, settings, progress=progress)
            print(f"\n  engine: {engine_name}")
            segments = transcript.segments

        write_subtitle(segments, args.format, out)
        print(f"wrote {out} ({len(list(segments))} cues)")
        return 0
    finally:
        if tmp_url_dir:
            tmp_url_dir.cleanup()


if __name__ == "__main__":
    sys.exit(main())
