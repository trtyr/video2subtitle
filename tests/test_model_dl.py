"""Model download helpers — offline paths only, no network in unit tests."""

from video2subtitle import model_dl


def test_files_present_and_ensure_skips_existing(tmp_path):
    (tmp_path / "model.int8.onnx").write_bytes(b"x")
    (tmp_path / "tokens.txt").write_bytes(b"x")
    assert model_dl.files_present(tmp_path, "sensevoice") is True
    # present -> returns immediately, never touches the network
    assert model_dl.ensure_model("sensevoice", tmp_path) == tmp_path


def test_files_present_false_when_partial(tmp_path):
    (tmp_path / "model.int8.onnx").write_bytes(b"x")
    assert model_dl.files_present(tmp_path, "sensevoice") is False


def test_ensure_model_unknown_engine(tmp_path):
    import pytest

    with pytest.raises(ValueError):
        model_dl.ensure_model("nope", tmp_path)
