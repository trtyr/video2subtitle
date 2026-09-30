"""Engine factory — selection via V2S_ENGINE (qwen3 | sensevoice)."""

from ..config import Settings


def create_engine(settings: Settings):
    name = settings.engine_name
    if name in ("qwen3", "qwen3-asr", "qwen3_asr"):
        from .qwen3 import Qwen3AsrEngine

        return Qwen3AsrEngine(
            model_dir=settings.qwen3_model_dir,
            num_threads=settings.num_threads,
            chunk_seconds=settings.qwen3_chunk_seconds,
            max_new_tokens=settings.qwen3_max_new_tokens,
            hotwords=settings.hotwords,
        )
    if name == "sensevoice":
        from .sensevoice import SenseVoiceEngine

        return SenseVoiceEngine(
            model_dir=settings.sensevoice_model_dir,
            num_threads=settings.num_threads,
            chunk_seconds=settings.chunk_seconds,
        )
    raise ValueError(f"unknown V2S_ENGINE: {name!r} (expected qwen3 | sensevoice)")


def engine_matrix(settings: Settings) -> list[dict]:
    """Per-engine availability rows for /healthz."""
    from ..model_dl import files_present

    active_key = "qwen3" if settings.engine_name.startswith("qwen3") else "sensevoice"
    rows = []
    for name, model_dir, key in (
        ("qwen3-asr", settings.qwen3_model_dir, "qwen3"),
        ("sensevoice", settings.sensevoice_model_dir, "sensevoice"),
    ):
        rows.append(
            {
                "name": name,
                "model_dir": str(model_dir),
                "model_downloaded": files_present(model_dir, key),
                "active": key == active_key,
            }
        )
    return rows
