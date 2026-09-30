"""Contract tests — the client-facing API behavior."""

import re
import time

from conftest import AUTH, make_client, make_settings, submit, wait_terminal, wav_bytes

SRT_LINE = re.compile(r"^\d+\n\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}\n.+$")


def test_healthz_no_auth(ctx):
    r = ctx["client"].get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["model_ready"] is True
    assert body["engine"]["name"] == "fake"
    assert body["version"]
    assert body["queue_depth"] == 0


def test_auth_missing_token(ctx):
    r = ctx["client"].post("/v1/transcripts", files={"file": ("a.wav", wav_bytes())})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_auth_wrong_token(ctx):
    r = ctx["client"].post(
        "/v1/transcripts",
        headers={"Authorization": "Bearer nope"},
        files={"file": ("a.wav", wav_bytes())},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"


def test_auth_get_requires_token(ctx):
    r = ctx["client"].get("/v1/transcripts/whatever")
    assert r.status_code == 401


def test_full_flow(ctx):
    client = ctx["client"]
    r = submit(client)
    assert r.status_code == 202, r.text
    body = r.json()
    assert set(body) >= {"task_id", "state", "queue_position"}
    assert body["state"] == "queued"
    assert body["queue_position"] == 1

    st = wait_terminal(client, body["task_id"])
    assert st["state"] == "completed"
    assert st["progress"] == 100
    assert st["engine"] == "fake"
    assert st["audio_duration_s"] > 0
    assert "decode_s" in st["timings"] and "infer_s" in st["timings"]

    result = st["result"]
    assert result["lang"] == "zh"
    assert isinstance(result["text"], str) and result["text"]
    segs = result["segments"]
    assert len(segs) == 2
    for s in segs:
        assert set(s) == {"start", "end", "text"}
        assert isinstance(s["start"], float) and isinstance(s["end"], float)
        assert s["end"] > s["start"]
    srt = result["srt"]
    assert srt.strip()
    for block in srt.strip().split("\n\n"):
        assert SRT_LINE.match(block), block


def test_submit_without_file(ctx):
    r = ctx["client"].post("/v1/transcripts", headers=AUTH)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_audio"


def test_empty_upload(ctx):
    r = submit(ctx["client"], data=b"")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "invalid_audio"


def test_payload_too_large(tmp_path):
    s = make_settings(tmp_path, max_upload_mb=0)
    client, _ = make_client(s)
    with client:
        r = submit(client, data=b"x" * 1024)
        assert r.status_code == 413
        assert r.json()["error"]["code"] == "payload_too_large"


def test_task_not_found(ctx):
    r = ctx["client"].get("/v1/transcripts/deadbeef", headers=AUTH)
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "task_not_found"


def test_delete_flow(ctx):
    client = ctx["client"]
    tid = submit(client).json()["task_id"]
    wait_terminal(client, tid)
    r = client.delete(f"/v1/transcripts/{tid}", headers=AUTH)
    assert r.status_code == 204
    r = client.get(f"/v1/transcripts/{tid}", headers=AUTH)
    assert r.status_code == 404
    r = client.delete(f"/v1/transcripts/{tid}", headers=AUTH)
    assert r.status_code == 404


def test_delete_while_queued(ctx):
    client = ctx["client"]
    tid = submit(client).json()["task_id"]
    r = client.delete(f"/v1/transcripts/{tid}", headers=AUTH)
    assert r.status_code == 204
    assert client.get(f"/v1/transcripts/{tid}", headers=AUTH).status_code == 404


def test_persistence_across_restart(ctx):
    client = ctx["client"]
    settings = ctx["settings"]
    tid = submit(client).json()["task_id"]
    wait_terminal(client, tid)

    from video2subtitle.store import TaskStore

    store2 = TaskStore(settings.data_dir)
    rec = store2.get(tid)
    assert rec is not None
    assert rec["state"] == "completed"
    assert rec["result"]["text"]


def test_queue_timeout(tmp_path):
    s = make_settings(tmp_path, queue_timeout_s=0)
    client, _ = make_client(s)
    with client:
        tid = submit(client).json()["task_id"]
        time.sleep(0.3)
        st = wait_terminal(client, tid)
        assert st["state"] == "failed"
        assert st["error"]["code"] == "queue_timeout"


def test_garbage_audio_fails_with_stable_code(ctx):
    client = ctx["client"]
    tid = submit(client, data=b"this is not audio at all", filename="junk.wav").json()["task_id"]
    st = wait_terminal(client, tid)
    assert st["state"] == "failed"
    assert st["error"]["code"] == "unsupported_media_type"


def test_list_tasks(ctx):
    client = ctx["client"]
    tid = submit(client).json()["task_id"]
    wait_terminal(client, tid)
    r = client.get("/v1/transcripts", headers=AUTH)
    assert r.status_code == 200
    ids = [t["task_id"] for t in r.json()["tasks"]]
    assert tid in ids


def test_web_root_served(ctx):
    r = ctx["client"].get("/")
    assert r.status_code == 200
    assert "video2subtitle" in r.text
