"""Stable error codes — HTTP status + machine code double layer."""

from typing import Optional


class Codes:
    UNAUTHORIZED = "unauthorized"                # 401
    TASK_NOT_FOUND = "task_not_found"            # 404
    PAYLOAD_TOO_LARGE = "payload_too_large"      # 413
    UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"  # 415
    INVALID_AUDIO = "invalid_audio"              # 422
    MODEL_NOT_READY = "model_not_ready"          # 503
    QUEUE_TIMEOUT = "queue_timeout"              # 504 (task-level)
    INFERENCE_FAILED = "inference_failed"        # 500 (task-level)
    BAD_REQUEST = "bad_request"                  # 400 (protocol-level junk)
    INTERNAL_ERROR = "internal_error"            # 500 (catch-all)


STATUS_FOR = {
    Codes.UNAUTHORIZED: 401,
    Codes.TASK_NOT_FOUND: 404,
    Codes.PAYLOAD_TOO_LARGE: 413,
    Codes.UNSUPPORTED_MEDIA_TYPE: 415,
    Codes.INVALID_AUDIO: 422,
    Codes.MODEL_NOT_READY: 503,
    Codes.QUEUE_TIMEOUT: 504,
    Codes.INFERENCE_FAILED: 500,
    Codes.BAD_REQUEST: 400,
    Codes.INTERNAL_ERROR: 500,
}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, headers: Optional[dict] = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.headers = headers or {}


def api_error(code: str, message: str, headers: Optional[dict] = None) -> ApiError:
    return ApiError(STATUS_FOR[code], code, message, headers)
