"""CLI tests — local mode end-to-end with a fake engine, format selection."""

from conftest import FakeEngine, wav_bytes

import video2subtitle.cli as cli


def _patch_engine(monkeypatch):
    fake = FakeEngine()
    monkeypatch.setattr(cli, "create_engine", lambda settings: fake)
    monkeypatch.setenv("V2S_AUTO_DOWNLOAD", "0")
    monkeypatch.setenv("V2S_TOKEN", "cli-token")
    return fake


def test_cli_local_writes_srt(tmp_path, monkeypatch, capsys):
    _patch_engine(monkeypatch)
    wav = tmp_path / "a.wav"
    wav.write_bytes(wav_bytes())
    out = tmp_path / "a.srt"

    rc = cli.main([str(wav), "-o", str(out)])

    assert rc == 0
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "00:00:00,000 --> 00:00:00,800" in text
    assert "你好世界。" in text
    assert "wrote" in capsys.readouterr().out


def test_cli_format_selection(tmp_path, monkeypatch):
    _patch_engine(monkeypatch)
    wav = tmp_path / "a.wav"
    wav.write_bytes(wav_bytes())
    out = tmp_path / "a.txt"

    rc = cli.main([str(wav), "-f", "txt", "-o", str(out)])

    assert rc == 0
    assert out.read_text(encoding="utf-8") == "你好世界。\n测试完成。\n"


def test_cli_default_output_alongside_input(tmp_path, monkeypatch):
    _patch_engine(monkeypatch)
    wav = tmp_path / "b.wav"
    wav.write_bytes(wav_bytes())

    rc = cli.main([str(wav), "-f", "vtt"])

    assert rc == 0
    vtt = tmp_path / "b.vtt"
    assert vtt.exists()
    assert vtt.read_text(encoding="utf-8").startswith("WEBVTT")


def test_cli_missing_input_errors(tmp_path, monkeypatch, capsys):
    _patch_engine(monkeypatch)
    try:
        cli.main([str(tmp_path / "nope.wav")])
        raised = False
    except SystemExit as e:
        raised = e.code != 0
    assert raised
