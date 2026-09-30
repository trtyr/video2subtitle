"""Qwen3-ASR 0.6B int8 engine (sherpa-onnx) — default quality engine.

API verified against sherpa-onnx (offline_recognizer.py):
  OfflineRecognizer.from_qwen3_asr(conv_frontend, encoder, decoder, tokenizer,
      num_threads, feature_dim=128, max_new_tokens, hotwords=...)

Note: KV-cache LLM decoder (max_total_len=512) -> audio MUST be chunked;
default 15 s chunks keep output well under max_new_tokens.
"""

from pathlib import Path

from ..audio import load_wav_f32
from .base import ProgressCb, Segment, Transcript
from .chunking import split_chunks
from .segmentation import build_segments, join_texts


def _guess_lang(text: str) -> str:
    for ch in text:
        if "\u4e00" <= ch <= "\u9fff":
            return "zh"
    return "en"


def _clean_lang(lang: str) -> str:
    return (lang or "").strip().strip("<|>")


class Qwen3AsrEngine:
    name = "qwen3-asr"
    backend = "sherpa-onnx Qwen3-ASR 0.6B int8"
    sample_rate = 16000

    def __init__(
        self,
        model_dir: Path,
        num_threads: int,
        chunk_seconds: float = 15.0,
        max_new_tokens: int = 256,
        hotwords: str = "",
    ) -> None:
        self.model_dir = Path(model_dir)
        self.num_threads = num_threads
        self.chunk_seconds = chunk_seconds
        self.max_new_tokens = max_new_tokens
        self.hotwords = hotwords
        self._rec = None

    def load(self) -> None:
        import sherpa_onnx

        d = self.model_dir
        for f in ("conv_frontend.onnx", "encoder.int8.onnx", "decoder.int8.onnx"):
            if not (d / f).exists():
                raise FileNotFoundError(f"Qwen3-ASR model file missing: {d / f}")
        if not (d / "tokenizer").is_dir():
            raise FileNotFoundError(f"Qwen3-ASR tokenizer dir missing: {d / 'tokenizer'}")
        self._rec = sherpa_onnx.OfflineRecognizer.from_qwen3_asr(
            conv_frontend=str(d / "conv_frontend.onnx"),
            encoder=str(d / "encoder.int8.onnx"),
            decoder=str(d / "decoder.int8.onnx"),
            tokenizer=str(d / "tokenizer"),
            num_threads=self.num_threads,
            feature_dim=128,
            max_new_tokens=self.max_new_tokens,
            temperature=1e-6,
            top_p=0.8,
            seed=42,
            hotwords=self.hotwords,
            debug=False,
        )

    @property
    def ready(self) -> bool:
        return self._rec is not None

    def transcribe(self, wav_path: Path, progress: ProgressCb = None) -> Transcript:
        samples = load_wav_f32(wav_path)
        chunks = split_chunks(samples, self.sample_rate, self.chunk_seconds)

        chunk_texts: list[str] = []
        langs: list[str] = []
        toks: list[str] = []
        tss: list[float] = []

        total = len(chunks)
        for i, (a, b) in enumerate(chunks):
            stream = self._rec.create_stream()
            stream.accept_waveform(self.sample_rate, samples[a:b])
            self._rec.decode_stream(stream)
            r = stream.result

            chunk_texts.append((getattr(r, "text", "") or "").strip())
            lang = _clean_lang(getattr(r, "lang", "") or "")
            if lang:
                langs.append(lang)

            r_tokens = list(getattr(r, "tokens", None) or [])
            r_ts = list(getattr(r, "timestamps", None) or [])
            if r_tokens and r_ts and len(r_tokens) == len(r_ts):
                offset = a / self.sample_rate
                for tok, ts in zip(r_tokens, r_ts):
                    if ts is None:
                        continue
                    toks.append(tok)
                    tss.append(float(ts) + offset)

            if progress:
                progress(int((i + 1) * 100 / total))

        if toks:
            segments = build_segments(toks, tss, max_dur=20.0)
        else:
            # no token timestamps -> chunk-level segments (chunks are
            # silence-snapped, so boundaries are natural pauses)
            segments = [
                (a / self.sample_rate, b / self.sample_rate, t)
                for (a, b), t in zip(chunks, chunk_texts)
                if t
            ]
        text = join_texts(chunk_texts)
        if langs:
            lang = max(set(langs), key=langs.count)
        else:
            lang = _guess_lang(text)
        return Transcript(
            lang=lang,
            text=text,
            segments=[Segment(s, e, t) for s, e, t in segments],
        )
