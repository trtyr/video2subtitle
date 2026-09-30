<div align="center">

# video2subtitle

**Self-hosted video → subtitles.**
**Drag a video into your browser (or run one CLI command), get SRT / VTT / ASS / TXT out.**

[Quickstart](#quickstart-docker--recommended) · [中文文档](README.zh-CN.md) · [Product definition](PRODUCT.md)

![status](https://img.shields.io/badge/status-v0.1.0-blue) ![license](https://img.shields.io/badge/license-MIT-green) ![python](https://img.shields.io/badge/python-3.10%2B-informational)

Multi-engine speech recognition (Qwen3-ASR · SenseVoice) · CPU-friendly, no GPU required · Your videos never leave your machine

</div>

---

## Why video2subtitle

- **Private by default** — self-hosted; uploads go to your own server, nothing leaves your tailnet/LAN
- **One command to run** — `docker compose up`, browser opens, drag video in, download subtitles
- **Multi-engine** — [Qwen3-ASR 0.6B](https://github.com/QwenLM/Qwen3-ASR) (quality, 30 languages + Chinese dialects) and [SenseVoice-Small](https://github.com/FunAudioLLM/SenseVoice) (fast) behind one engine interface; switch with an env var
- **URL → subtitles** — paste a public media URL, the generic yt-dlp layer downloads it (no site-specific hacks)
- **Real subtitles** — token-timestamp sentence segmentation with silence-snapped chunking: proper cue boundaries, ITN ("2025年9月"), and SRT/VTT/ASS/TXT output
- **Zero build chain** — the web UI is a single static page served by the API server

## Quickstart (Docker — recommended)

Requires Docker with Compose v2.

```bash
git clone https://github.com/trtyr/video2subtitle
cd video2subtitle
echo "V2S_TOKEN=change-me" > .env
docker compose up -d
```

Open **http://localhost:8765**, paste the same token, drop a video, download subtitles.

Prefer pulling without cloning? `docker pull ghcr.io/trtyr/video2subtitle:latest` (image is
built for `linux/amd64` + `linux/arm64`).

> First start downloads the ASR model automatically — ≈950 MB for the default
> Qwen3-ASR, or set `V2S_ENGINE=sensevoice` in `.env` for the ≈240 MB SenseVoice
> (runs ~6× faster, a bit lower quality). Models are cached in `./models/`.
> Slow GitHub access? Add `V2S_GH_MIRROR=https://ghfast.top/` to `.env`.

## Quickstart (pip / CLI)

Requires Python 3.10+ and `ffmpeg` on PATH.

```bash
pip install -e .
export V2S_TOKEN=change-me
python -m video2subtitle.main        # server + web UI on :8765
```

CLI — a file or a public URL in, a subtitle file out:

```bash
video2subtitle talk.mp4                          # -> talk.srt  (local engine)
video2subtitle talk.mp4 -f vtt -o out.vtt        # pick the format
video2subtitle https://example.com/video.mp4     # generic URL via yt-dlp
video2subtitle talk.mp4 --server http://box:8765 --token SECRET
                                                 # use a remote server, no local model
```

## Benchmark (measured, not estimated)

AMD Ryzen 7 5800H · 8 onnxruntime threads · real HTTP round-trip · edge-tts spoken audio (zh 201.8 s / en 197.3 s):

| Engine | Audio | Audio length | Inference | RTF | Cues |
|---|---|---|---|---|---|
| Qwen3-ASR 0.6B int8 | Chinese | 201.8 s | 37.5 s | **0.186** | 14 |
| Qwen3-ASR 0.6B int8 | English | 197.3 s | 42.8 s | **0.217** | 14 |
| SenseVoice-Small int8 | Chinese | 201.8 s | 5.7 s | **0.028** | 29 |
| SenseVoice-Small int8 | English | 197.3 s | 5.8 s | **0.030** | 17 |

An 18-minute video ⇒ **~3.4 min** (Qwen3-ASR) or **~31 s** (SenseVoice). English quality note: Qwen3-ASR produced complete punctuation and correct words where SenseVoice misheard ("Tonight"→"Toight").

## API

Interactive docs at `/docs` (OpenAPI). Core endpoints:

| Method | Path | Description |
|---|---|---|
| POST | `/v1/transcripts` | Upload audio/video (multipart `file`) → `202 {task_id, state, queue_position}` |
| GET | `/v1/transcripts/{id}` | State (`queued→processing→completed/failed`), `progress`, `result` |
| DELETE | `/v1/transcripts/{id}` | Delete task + result |
| GET | `/healthz` | Version, active engine, per-engine model status, queue depth |

Result shape:

```json
{"lang": "zh", "text": "…",
 "segments": [{"start": 0.18, "end": 4.14, "text": "…"}],
 "srt": "1\n00:00:00,180 --> 00:00:04,140\n…\n"}
```

Errors are two-layer: HTTP status + `{"error": {"code", "message"}}` with stable codes
(`invalid_audio`, `model_not_ready`, `queue_timeout`, `inference_failed`, …).

## Architecture

```
browser (drag & drop) ─┐
CLI (file / URL)      ─┼─▶ REST API ─▶ serial queue ─▶ engine (resident model)
3rd-party scripts     ─┘   Bearer auth   disk-backed     ├─ qwen3-asr  (default)
                           ffmpeg probe/normalize        └─ sensevoice (fast)
                                 ▲                    token-timestamp segmentation
                                 └── SRT / VTT / ASS / TXT writers
```

Serial queue by design: one inference at a time (single-user self-hosting), tasks and
results persisted on disk — restarts don't lose completed work; clients may disconnect
and collect later. Results are kept for 7 days (configurable).

## Configuration (env vars)

| Variable | Default | Meaning |
|---|---|---|
| `V2S_TOKEN` | — (required) | Bearer token for the API |
| `V2S_ENGINE` | `qwen3` | `qwen3` or `sensevoice` |
| `V2S_HOST` / `V2S_PORT` | `127.0.0.1` / `8765` | Bind address; **bind a tailnet/LAN IP in production** |
| `V2S_QWEN3_MODEL_DIR` / `V2S_SENSEVOICE_MODEL_DIR` | `~/.local/share/video2subtitle/models/…` | Reuse existing model files |
| `V2S_AUTO_DOWNLOAD` | `1` | Set `0` for air-gapped hosts |
| `V2S_GH_MIRROR` | — | Prefix mirror for model downloads, e.g. `https://ghfast.top/` |
| `V2S_HOTWORDS` | — | Comma-separated biasing words for Qwen3-ASR |
| `V2S_MAX_UPLOAD_MB` / `V2S_MAX_DURATION_S` | `100` / `7200` | Limits |

## Roadmap

- [ ] v0.2: faster-whisper engine · GPU (CUDA) inference
- [ ] v0.3: translation / bilingual subtitles · ASS styling presets
- [ ] later: multi-user auth, edit-and-refine loop in the browser

## License

[MIT](LICENSE)
