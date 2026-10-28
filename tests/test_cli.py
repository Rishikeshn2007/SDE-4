import json

from academia_audio.cli import main


def test_cli_happy_path(capsys):
    assert main(["--duration", "0.1", "--chunk-ms", "20"]) == 0
    out = capsys.readouterr().out
    assert "16000Hz/1ch/pcm_s16le" in out
    assert "done | chunks=5 bytes=3200" in out


def test_cli_is_deterministic(capsys):
    main(["--duration", "0.5"])
    first = capsys.readouterr().out
    main(["--duration", "0.5"])
    assert first == capsys.readouterr().out


def test_cli_json_and_limit(capsys):
    assert main(["--duration", "1", "--json", "--limit", "3"]) == 0
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [r["sequence_id"] for r in rows] == [0, 1, 2]
    assert rows[1]["timestamp_s"] == 0.02
    assert rows[0]["size_bytes"] == 640


def test_cli_rejects_bad_sample_rate(capsys):
    assert main(["--sample-rate", "12345"]) == 2
    assert "invalid_sample_rate" in capsys.readouterr().err


def test_cli_rejects_bad_channels(capsys):
    assert main(["--channels", "5"]) == 2
    assert "invalid_channels" in capsys.readouterr().err
