"""Provider unit tests (offline: no network, no API keys required).

Cover the pure parsing/selection/validation logic of the 5 provider integrations
and verify every provider degrades gracefully to the deterministic fallback.
"""

import io
import wave

import pytest

from src.services.agents.cala import (
    CalaKnowledge,
    _extract_snippets,
    _McpHttpClient,
    cala_configured,
)
from src.services.agents.knowledge import KnowledgeResult
from src.services.agents.schemas import AssetSpec
from src.services.generation.devin_codegen import _build_prompt, _validate_files, generate_course_app
from src.services.generation.providers.composite import CompositeAssetProvider
from src.services.generation.providers.gemini_media import (
    GeminiTTSProvider,
    NanoBananaImageProvider,
    _inline_parts,
    _pcm_to_wav,
    _rate_from_mime,
)
from src.services.generation.providers.pixverse import PixVerseProvider, _aspect_ratio


# ── Cala MCP ─────────────────────────────────────────────────────────────────
def test_cala_extract_snippets_from_content_and_structured():
    assert _extract_snippets({"content": [{"type": "text", "text": "hello"}]}) == ["hello"]
    out = _extract_snippets({"structuredContent": {"a": "x", "b": ["y", "z"]}})
    assert set(out) == {"x", "y", "z"}
    assert _extract_snippets({}) == []


def test_cala_parse_sse_response():
    class FakeResp:
        headers = {"content-type": "text/event-stream"}
        text = 'event: message\ndata: {"jsonrpc":"2.0","id":1,"result":{"ok":true}}\n\n'

    msg = _McpHttpClient._parse_response(FakeResp())
    assert msg["result"] == {"ok": True}


def test_cala_not_configured_by_default():
    assert cala_configured() is False


def test_cala_knowledge_falls_back_on_error(monkeypatch):
    k = CalaKnowledge(company_name="Acme")

    def boom(*a, **kw):
        raise RuntimeError("no server")

    monkeypatch.setattr(k._client, "call_tool", boom)
    result = k.compliance_search("gdpr")
    assert isinstance(result, KnowledgeResult)
    assert "(placeholder)" in result.render()


def test_cala_knowledge_uses_mcp_results(monkeypatch):
    k = CalaKnowledge(company_name="Acme")
    monkeypatch.setattr(k._client, "call_tool", lambda *a, **kw: ["real SOP doc"])
    result = k.sop_search("lockout")
    assert result.snippets == ["real SOP doc"]
    assert result.source == "sop"


# ── Gemini media (Nano-Banana + TTS) ─────────────────────────────────────────
def test_pcm_to_wav_is_valid_wav():
    pcm = b"\x00\x01" * 1000
    data = _pcm_to_wav(pcm, 24000)
    with wave.open(io.BytesIO(data), "rb") as w:
        assert w.getframerate() == 24000
        assert w.getnchannels() == 1
        assert w.getsampwidth() == 2


def test_rate_from_mime():
    assert _rate_from_mime("audio/L16;codec=pcm;rate=16000") == 16000
    assert _rate_from_mime("audio/L16") == 24000


def test_inline_parts_extraction():
    resp = {
        "candidates": [
            {"content": {"parts": [{"inlineData": {"data": "AAAA", "mimeType": "image/png"}}]}}
        ]
    }
    parts = _inline_parts(resp)
    assert parts and parts[0]["data"] == "AAAA"


def test_gemini_providers_unconfigured_without_key(monkeypatch):
    monkeypatch.setattr("src.services.generation.providers.gemini_media._gemini_key", lambda: "")
    assert NanoBananaImageProvider.configured() is False
    assert GeminiTTSProvider.configured() is False


# ── PixVerse ─────────────────────────────────────────────────────────────────
def test_pixverse_aspect_ratio():
    assert _aspect_ratio("16:9") == "16:9"
    assert _aspect_ratio("800x600") == "4:3"
    assert _aspect_ratio("") == "16:9"


def test_pixverse_not_configured_by_default():
    assert PixVerseProvider.configured() is False


# ── Composite provider (graceful fallback) ───────────────────────────────────
def test_composite_falls_back_to_placeholder_svg():
    provider = CompositeAssetProvider()
    spec = AssetSpec(
        template_link="/resources/images/01",
        type="image",
        dimensions="16:9",
        description="a safety helmet",
        purpose="hero image",
    )
    content, ext, ctype = provider.produce(spec, "#5145E5")
    assert ext == "svg"
    assert ctype == "image/svg+xml"
    assert b"<svg" in content


def test_composite_audio_and_video_raise_without_provider():
    provider = CompositeAssetProvider()
    video = AssetSpec(template_link="/resources/video/01", type="video", description="x")
    with pytest.raises(RuntimeError, match="video provider|no video provider|pixverse"):
        provider.produce(video, "#000000")

    audio = AssetSpec(template_link="/resources/audio/01", type="audio", description="x")
    with pytest.raises(RuntimeError, match="audio provider|no audio provider|gemini-tts"):
        provider.produce(audio, "#000000")


# ── Devin code-gen ───────────────────────────────────────────────────────────
def test_validate_files_accepts_good_project():
    out = _validate_files(
        {
            "files": [
                {"path": "package.json", "content": "{}"},
                {"path": "src/main.tsx", "content": "x"},
            ]
        }
    )
    assert out == {"package.json": "{}", "src/main.tsx": "x"}


def test_validate_files_rejects_missing_package_json():
    assert _validate_files({"files": [{"path": "src/main.tsx", "content": "x"}]}) is None


def test_validate_files_rejects_path_traversal():
    out = _validate_files(
        {"files": [{"path": "package.json", "content": "{}"}, {"path": "../evil", "content": "x"}]}
    )
    assert out == {"package.json": "{}"}


def test_devin_prompt_requires_page_subagents():
    prompt = _build_prompt({"title": "t", "chapters": [{"title": "c"}]}, {})
    assert "Mandatory subagent workflow" in prompt
    assert "subagent for EVERY PAGE" in prompt
    assert "Do not skip subagents" in prompt


async def test_generate_course_app_disabled_returns_none():
    session_id, files = await generate_course_app({"title": "t"}, {})
    assert session_id is None
    assert files is None
