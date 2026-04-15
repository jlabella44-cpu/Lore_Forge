"""services/whisper.py — word-level transcription wrapper."""
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def test_transcribe_words_normalizes_to_plain_dicts(tmp_path):
    from app.config import settings
    from app.services import whisper

    mp3 = tmp_path / "narration.mp3"
    mp3.write_bytes(b"ID3fake")

    # Simulate the OpenAI SDK's verbose_json response: .words is a list of
    # objects with `.word`, `.start`, `.end` attributes.
    fake_words = [
        SimpleNamespace(word="Hello", start=0.04, end=0.35),
        SimpleNamespace(word="world", start=0.40, end=0.78),
    ]
    fake_resp = SimpleNamespace(words=fake_words)

    settings.openai_api_key = "sk-test"
    whisper._openai_client.cache_clear()

    with patch.object(whisper, "_openai_client") as c:
        c.return_value.audio.transcriptions.create.return_value = fake_resp
        out = whisper.transcribe_words(mp3)

    assert out == [
        {"word": "Hello", "start": 0.04, "end": 0.35},
        {"word": "world", "start": 0.40, "end": 0.78},
    ]

    # Verify the call shape — request verbose json + word granularity
    kwargs = c.return_value.audio.transcriptions.create.call_args.kwargs
    assert kwargs["model"] == "whisper-1"
    assert kwargs["response_format"] == "verbose_json"
    assert kwargs["timestamp_granularities"] == ["word"]


def test_transcribe_words_returns_empty_list_on_silence(tmp_path):
    from app.config import settings
    from app.services import whisper

    mp3 = tmp_path / "silent.mp3"
    mp3.write_bytes(b"ID3silent")

    settings.openai_api_key = "sk-test"
    whisper._openai_client.cache_clear()

    with patch.object(whisper, "_openai_client") as c:
        c.return_value.audio.transcriptions.create.return_value = SimpleNamespace(words=[])
        out = whisper.transcribe_words(mp3)

    assert out == []


def test_transcribe_words_missing_key_raises(tmp_path):
    from app.config import settings
    from app.services import whisper

    settings.openai_api_key = ""
    whisper._openai_client.cache_clear()

    try:
        whisper.transcribe_words(tmp_path / "x.mp3")
    except RuntimeError as exc:
        assert "OPENAI_API_KEY" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")
