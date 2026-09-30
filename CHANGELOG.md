# Changelog

All notable changes to this project will be documented in this file.
Format based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [0.1.0] - 2026-09-30

First public release.

### Added
- Async transcription REST API: submit → task_id → poll progress/queue position → result (`lang` / `text` / `segments` / `srt`), stable two-layer error codes, bearer-token auth
- Resident multi-engine ASR behind an engine interface: **Qwen3-ASR 0.6B int8** (default) and **SenseVoice-Small int8** (fallback), switchable via `V2S_ENGINE`
- First-start model auto-download with mirror failover (direct GitHub → prefix mirrors), recent-throughput slow-link detection, and interrupted-extract resume
- Serial FIFO queue, disk-backed task store (survives restarts), 7-day result retention, TTL sweep
- Sentence segmentation from token timestamps: ≥1.5 s pauses, terminal punctuation, long-cue force-split at largest gaps, punctuation-only cue filtering
- Subtitle writers: SRT / VTT / ASS / TXT
- Web UI (single static page, zero build chain): drag & drop upload, live progress with queue position, editable cue preview, client-side multi-format download, task history, health pill
- CLI: local files, generic URLs (yt-dlp), and `--server` remote mode; format selection
- `docker compose` one-command deployment; health/version endpoints; OpenAPI docs at `/docs`
