# video2subtitle

> Self-hosted video → subtitles. Drag a video into your browser (or run one CLI command), get SRT/VTT/ASS/TXT out.

**Work in progress — v0.1.0 coming soon.**
See [PRODUCT.md](PRODUCT.md) for the product definition, engine matrix and benchmarks.

## Quickstart (dev preview)

Needs Python 3.10+ and `ffmpeg` on PATH.

```bash
pip install -e .
export V2S_TOKEN=change-me
python -m video2subtitle.main
```

First start auto-downloads the model for the selected engine
(Qwen3-ASR ≈950 MB by default; set `V2S_ENGINE=sensevoice` for the ≈240 MB SenseVoice).
Models land in `~/.local/share/video2subtitle/models/` — override with
`V2S_QWEN3_MODEL_DIR` / `V2S_SENSEVOICE_MODEL_DIR` to reuse existing copies.
Poor GitHub connectivity? Set `V2S_GH_MIRROR=https://ghfast.top/` (or any prefix mirror).
Air-gapped? Set `V2S_AUTO_DOWNLOAD=0` and provision the model dirs yourself.

- Web UI: <http://127.0.0.1:8765/>
- API docs: <http://127.0.0.1:8765/docs>
- Health: <http://127.0.0.1:8765/healthz>

