"""video2subtitle server — FastAPI app: REST API + resident engines + static web."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, File, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import __version__
from .auth import require_token
from .config import Settings
from .engines import create_engine, engine_matrix
from .engines.base import TranscriptionEngine
from .errors import ApiError, Codes
from .models import Health, TaskStatus
from .queue import SerialWorker
from .store import TaskStore

log = logging.getLogger("video2subtitle")

_SLACK = 64 * 1024  # multipart framing overhead allowance


def create_app(settings: Settings | None = None, engine: TranscriptionEngine | None = None) -> FastAPI:
    settings = settings or Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        s: Settings = app.state.settings
        if not s.token and not s.allow_no_token:
            raise RuntimeError("V2S_TOKEN is required (refusing to start without auth)")
        s.data_dir.mkdir(parents=True, exist_ok=True)
        eng = app.state.engine
        try:
            # fresh install: auto-download the model archive on first start
            if s.auto_download:
                from .model_dl import ensure_model

                ensure_model("qwen3" if eng.name.startswith("qwen3") else "sensevoice",
                             s.model_dir_for(eng.name))
            eng.load()  # model loads once, stays resident
        except Exception:
            # degraded mode: server still answers, /healthz shows what's wrong
            log.exception("engine %s failed to load — serving in degraded mode", eng.name)
        store = TaskStore(s.data_dir)
        store.sweep(s.result_ttl_hours)
        worker = SerialWorker(store, eng, s)
        app.state.store = store
        app.state.worker = worker
        worker.start()
        try:
            yield
        finally:
            worker.stop()

    app = FastAPI(
        title="video2subtitle",
        version=__version__,
        description="Self-hosted video → subtitles. Upload a video/audio file, "
                    "poll for progress, download SRT/VTT/ASS/TXT.",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url=None,
        openapi_url="/openapi.json",
    )
    app.state.settings = settings
    app.state.engine = engine if engine is not None else create_engine(settings)

    # ---------------- exception handlers (error contract) ----------------
    @app.exception_handler(ApiError)
    async def _api_error(_req: Request, exc: ApiError):
        return JSONResponse(
            status_code=exc.status,
            content={"error": {"code": exc.code, "message": exc.message}},
            headers=exc.headers,
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_req: Request, _exc: RequestValidationError):
        return JSONResponse(
            status_code=400,
            content={"error": {"code": Codes.BAD_REQUEST, "message": "malformed request"}},
        )

    @app.exception_handler(Exception)
    async def _unhandled(_req: Request, _exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"error": {"code": Codes.INTERNAL_ERROR, "message": "internal server error"}},
        )

    # ---------------- health / version (no auth) ----------------
    @app.get("/healthz", response_model=Health)
    def healthz(request: Request) -> Health:
        eng: TranscriptionEngine = request.app.state.engine
        worker: SerialWorker | None = getattr(request.app.state, "worker", None)
        return Health(
            status="ok" if eng.ready else "degraded",
            version=__version__,
            engine={
                "name": eng.name,
                "backend": eng.backend,
                "sample_rate": eng.sample_rate,
                "threads": request.app.state.settings.num_threads,
            },
            engines=engine_matrix(request.app.state.settings),
            model_ready=eng.ready,
            queue_depth=worker.queue_depth() if worker else 0,
        )

    @app.get("/version")
    def version() -> dict:
        return {"name": "video2subtitle", "version": __version__}

    # ---------------- v1 API ----------------
    @app.post("/v1/transcripts", status_code=202)
    async def submit_transcript(
        request: Request,
        file: UploadFile | None = File(default=None),
        _=Depends(require_token),
    ) -> dict:
        s: Settings = request.app.state.settings
        store: TaskStore = request.app.state.store
        worker: SerialWorker = request.app.state.worker

        if not request.app.state.engine.ready:
            raise ApiError(503, Codes.MODEL_NOT_READY,
                           "model is loading or unavailable", headers={"Retry-After": "30"})

        cl = request.headers.get("content-length")
        if cl and cl.isdigit() and int(cl) > s.max_upload_bytes + _SLACK:
            raise ApiError(413, Codes.PAYLOAD_TOO_LARGE,
                           f"upload exceeds {s.max_upload_mb} MB limit")

        if file is None:
            raise ApiError(422, Codes.INVALID_AUDIO, "multipart field 'file' is required")
        data = await file.read(s.max_upload_bytes + 1)
        if len(data) > s.max_upload_bytes:
            raise ApiError(413, Codes.PAYLOAD_TOO_LARGE,
                           f"upload exceeds {s.max_upload_mb} MB limit")
        if not data:
            raise ApiError(422, Codes.INVALID_AUDIO, "empty upload")

        rec = store.create()
        store.save_audio(rec["task_id"], data)
        store.sweep(s.result_ttl_hours)
        worker.notify()
        return {
            "task_id": rec["task_id"],
            "state": "queued",
            "queue_position": store.queue_position(rec["task_id"]),
        }

    @app.get("/v1/transcripts")
    def list_transcripts(request: Request, _=Depends(require_token)) -> dict:
        store: TaskStore = request.app.state.store
        return {"tasks": [TaskStatus(**r).model_dump() for r in store.all()]}

    @app.get("/v1/transcripts/{task_id}")
    def task_status(task_id: str, request: Request, _=Depends(require_token)) -> TaskStatus:
        store: TaskStore = request.app.state.store
        rec = store.get(task_id)
        if rec is None:
            raise ApiError(404, Codes.TASK_NOT_FOUND, f"no such task: {task_id}")
        body = TaskStatus(**rec)
        if rec["state"] == "queued":
            body.queue_position = store.queue_position(task_id)
        return body

    @app.delete("/v1/transcripts/{task_id}", status_code=204)
    def delete_transcript(task_id: str, request: Request, _=Depends(require_token)) -> Response:
        store: TaskStore = request.app.state.store
        if not store.delete(task_id):
            raise ApiError(404, Codes.TASK_NOT_FOUND, f"no such task: {task_id}")
        return Response(status_code=204)

    # ---------------- static web (mounted last; API routes take precedence) ----------------
    web_dir = Path(__file__).resolve().parent / "web_static"
    if web_dir.is_dir():
        app.mount("/", StaticFiles(directory=str(web_dir), html=True), name="web")

    return app


def main() -> None:
    import uvicorn

    s = Settings()
    if not s.token and not s.allow_no_token:
        raise SystemExit("V2S_TOKEN is required")
    uvicorn.run(create_app(s), host=s.host, port=s.port, log_level="info")


if __name__ == "__main__":
    main()
