from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.main as main
from app.dialogue import TurnResult
from app.providers import ProviderFailure


def test_browser_voice_uses_provider_transcript_and_reports_tts_fallback(monkeypatch):
    transcript = "Book a table for four tomorrow"
    seen = []

    async def fake_stt(wav):
        assert wav == b"normalized audio"
        return transcript, "fake-prisma"

    async def fake_tts(_text):
        raise ProviderFailure("TTS unavailable")

    async def fake_turn(text, session_id=None, **kwargs):
        seen.append((text, session_id, kwargs.get("source")))
        return TurnResult("CALL-VOICE-REGRESSION", text, "What time should I book?",
                          "test_parser", "needs_details")

    monkeypatch.setattr(main, "convert_to_wav", lambda *_: b"normalized audio")
    monkeypatch.setattr(main, "gnani_stt", fake_stt)
    monkeypatch.setattr(main, "gnani_tts", fake_tts)
    monkeypatch.setattr(main, "dialogue", SimpleNamespace(turn=fake_turn))

    response = TestClient(main.app).post(
        "/api/voice/turn",
        files={"audio": ("utterance.webm", b"browser audio", "audio/webm")},
        data={"session_id": "CALL-VOICE-REGRESSION"},
    )

    assert response.status_code == 200
    result = response.json()
    assert result["user_text"] == transcript
    assert result["stt_model"] == "fake-prisma"
    assert result["tts_status"] == "unavailable"
    assert result["audio_url"] is None
    assert seen == [(transcript, "CALL-VOICE-REGRESSION", "voice")]


def test_browser_voice_stt_failure_does_not_create_dialogue_turn(monkeypatch):
    async def failed_stt(_wav):
        raise ProviderFailure("STT unavailable")

    def forbidden_turn(*_args, **_kwargs):
        raise AssertionError("Dialogue must not receive a fabricated transcript")

    monkeypatch.setattr(main, "convert_to_wav", lambda *_: b"normalized audio")
    monkeypatch.setattr(main, "gnani_stt", failed_stt)
    monkeypatch.setattr(main, "dialogue", SimpleNamespace(turn=forbidden_turn))

    response = TestClient(main.app).post(
        "/api/voice/turn",
        files={"audio": ("utterance.webm", b"browser audio", "audio/webm")},
    )

    assert response.status_code == 503
    assert response.json()["mode"] == "provider_error"
    assert response.json()["error"] == "STT unavailable"
