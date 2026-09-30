"""SenseVoice-Small int8 engine (sherpa-onnx), the fast fallback."""

from pathlib import Path

from ..audio import load_wav_f32
from .base import ProgressCb, Segment, Transcript
from .chunking import split_chunks
from .segmentation import build_segments, is_special, join_texts


def _clean_lang(lang: str) -> str:
    lang = (lang or "").strip().strip("<|>")
    return lang or "zh"


class SenseVoiceEngine:
    name = "sensevoice"
    backend = "sherpa-onnx SenseVoiceSmall int8"
    sample_rate = 16000

    def __init__(self, model_dir: Path, num_threads: int, chunk_seconds: float = 30.0) -> None:
        self.model_dir = Path(model_dir)
        self.num_threads = num_threads
        self.chunk_seconds = chunk_seconds
        self._rec = None

    def load(self) -> None:
        import sherpa_onnx

        model = self.model_dir / "model.int8.onnx"
        tokens = self.model_dir / "tokens.txt"
        if not model.exists() or not tokens.exists():
            raise FileNotFoundError(f"SenseVoice model files not found under {self.model_dir}")
        self._rec = sherpa_onnx.OfflineRecognizer.from_sense_voice(
            model=str(model),
            tokens=str(tokens),
            num_threads=self.num_threads,
            use_itn=True,
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

            chunk_texts.append((r.text or "").strip())
            langs.append(_clean_lang(getattr(r, "lang", "") or ""))
            r_tokens = list(getattr(r, "tokens", None) or [])
            r_ts = list(getattr(r, "timestamps", None) or [])
            offset = a / self.sample_rate
            for tok, ts in zip(r_tokens, r_ts):
                if is_special(tok) or ts is None:
                    continue
                toks.append(tok)
                tss.append(float(ts) + offset)

            if progress:
                progress(int((i + 1) * 100 / total))

        segments = build_segments(toks, tss, max_dur=20.0)
        if not segments and chunk_texts:
            # timestamps unavailable -> fall back to chunk-level segments
            segments = [
                (a / self.sample_rate, b / self.sample_rate, t)
                for (a, b), t in zip(chunks, chunk_texts)
                if t
            ]
        lang = max(set(langs), key=langs.count) if langs else "zh"
        return Transcript(
            lang=lang,
            text=join_texts(chunk_texts),
            segments=[Segment(s, e, t) for s, e, t in segments],
        )
