"""Tests for the Devin-primary generation path.

Covers:
- No Devin credentials → template / local fallback
- Devin configured → generate_course_app called and returns files
- Malformed Devin output → fallback
- Unsafe generated paths rejected
- Missing package.json rejected
- Build failure → fallback (repair not implemented yet)
- DevinError → graceful fallback

All tests use mocks; no real Devin API calls.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from src.services.devin.client import DevinError
from src.services.generation.devin_codegen import (
    _validate_files,
    generate_course_app,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_SPEC = {"title": "Test Course", "chapters": []}
SAMPLE_ASSET_MAP = {"img01": "https://example.com/img.png"}

GOOD_DEVIN_OUTPUT = {
    "files": [
        {
            "path": "package.json",
            "content": json.dumps(
                {"name": "course", "scripts": {"build": "vite build"}}
            ),
        },
        {"path": "vite.config.ts", "content": "export default {}"},
        {"path": "src/main.tsx", "content": "console.log('hello')"},
        {"path": "index.html", "content": "<html></html>"},
    ]
}


# ── 1. No Devin credentials → template path ──────────────────────────────────


async def test_disabled_flag_returns_none():
    """course_build_mode=template → (None, None)."""
    with patch("src.services.generation.devin_codegen.settings") as mock_settings:
        mock_settings.course_build_mode = "template"
        sid, files = await generate_course_app(SAMPLE_SPEC, SAMPLE_ASSET_MAP)
    assert sid is None
    assert files is None


async def test_enabled_but_no_api_key_returns_none():
    """Flag on but DEVIN_API_KEY empty → (None, None)."""
    with patch("src.services.generation.devin_codegen.settings") as mock_settings:
        mock_settings.course_build_mode = "devin"
        mock_settings.course_build_repair_max_retries = 2
        with patch(
            "src.services.generation.devin_codegen.DevinClient"
        ) as MockClient:
            instance = MockClient.return_value
            instance.enabled = False
            sid, files = await generate_course_app(SAMPLE_SPEC, SAMPLE_ASSET_MAP)
    assert sid is None
    assert files is None


async def test_enabled_but_no_org_id_returns_none():
    """Flag on, API key set, but org_id empty → client.enabled is False."""
    with patch("src.services.generation.devin_codegen.settings") as mock_settings:
        mock_settings.course_build_mode = "devin"
        mock_settings.course_build_repair_max_retries = 2
        with patch(
            "src.services.generation.devin_codegen.DevinClient"
        ) as MockClient:
            instance = MockClient.return_value
            instance.enabled = False  # api_key set but org_id missing
            sid, files = await generate_course_app(SAMPLE_SPEC, SAMPLE_ASSET_MAP)
    assert sid is None
    assert files is None


# ── 2. Devin configured → generate_course_app called ─────────────────────────


async def test_devin_configured_returns_session_and_files():
    """Happy path: Devin returns well-formed structured output."""
    with patch("src.services.generation.devin_codegen.settings") as mock_settings:
        mock_settings.course_build_mode = "devin"
        mock_settings.course_build_repair_max_retries = 2
        with patch(
            "src.services.generation.devin_codegen.DevinClient"
        ) as MockClient, patch(
            "src.services.generation.devin_codegen.try_build_from_sources"
        ):
            instance = MockClient.return_value
            instance.enabled = True
            instance.run = AsyncMock(return_value=("sess-123", GOOD_DEVIN_OUTPUT))
            sid, files = await generate_course_app(SAMPLE_SPEC, SAMPLE_ASSET_MAP)
    assert sid == "sess-123"
    assert files is not None
    assert "package.json" in files
    assert "src/main.tsx" in files
    assert len(files) == 4


async def test_devin_run_receives_correct_arguments():
    """Verify the prompt/schema/title/tags forwarded to client.run()."""
    with patch("src.services.generation.devin_codegen.settings") as mock_settings:
        mock_settings.course_build_mode = "devin"
        mock_settings.course_build_repair_max_retries = 2
        with patch(
            "src.services.generation.devin_codegen.DevinClient"
        ) as MockClient, patch(
            "src.services.generation.devin_codegen.try_build_from_sources"
        ):
            instance = MockClient.return_value
            instance.enabled = True
            instance.run = AsyncMock(return_value=("sess-1", GOOD_DEVIN_OUTPUT))
            await generate_course_app(
                {"title": "Safety 101", "chapters": []}, {}
            )
            # First call is the generation call
            first_call = instance.run.call_args_list[0]
            _args, kwargs = first_call
            prompt = _args[0]
            assert "Safety 101" in prompt
            assert kwargs["tags"] == ["coursive", "course-app"]
            assert kwargs["structured_output_schema"] is not None


# ── 3. Malformed Devin output → fallback ─────────────────────────────────────


@pytest.mark.parametrize(
    "bad_output,desc",
    [
        (None, "None output"),
        ("just a string", "string instead of dict"),
        (42, "integer instead of dict"),
        ({}, "empty dict – no 'files' key"),
        ({"files": None}, "files is None"),
        ({"files": "not a list"}, "files is a string"),
        ({"files": []}, "files is empty list"),
        ({"files": [42, "nope"]}, "files contains non-dicts"),
        (
            {"files": [{"path": 123, "content": "x"}]},
            "path is not a string",
        ),
        (
            {"files": [{"path": "a.txt", "content": 999}]},
            "content is not a string",
        ),
    ],
    ids=lambda d: d if isinstance(d, str) else "",
)
async def test_malformed_output_falls_back(bad_output, desc):
    """Various malformed outputs all result in files=None (fallback)."""
    with patch("src.services.generation.devin_codegen.settings") as mock_settings:
        mock_settings.course_build_mode = "devin"
        mock_settings.course_build_repair_max_retries = 2
        with patch(
            "src.services.generation.devin_codegen.DevinClient"
        ) as MockClient:
            instance = MockClient.return_value
            instance.enabled = True
            instance.run = AsyncMock(return_value=("sess-bad", bad_output))
            sid, files = await generate_course_app(SAMPLE_SPEC, SAMPLE_ASSET_MAP)
    # session_id is returned so the caller can log/audit which session failed
    assert sid == "sess-bad"
    assert files is None


async def test_devin_error_returns_none():
    """DevinError during client.run → (None, None), not an exception."""
    with patch("src.services.generation.devin_codegen.settings") as mock_settings:
        mock_settings.course_build_mode = "devin"
        mock_settings.course_build_repair_max_retries = 2
        with patch(
            "src.services.generation.devin_codegen.DevinClient"
        ) as MockClient:
            instance = MockClient.return_value
            instance.enabled = True
            instance.run = AsyncMock(side_effect=DevinError("timeout"))
            sid, files = await generate_course_app(SAMPLE_SPEC, SAMPLE_ASSET_MAP)
    assert sid is None
    assert files is None


# ── 4. Unsafe generated paths rejected ───────────────────────────────────────


@pytest.mark.parametrize(
    "unsafe_path",
    [
        "../etc/passwd",
        "foo/../../bar",
        "",
        "///",
    ],
)
def test_validate_files_rejects_traversal_and_empty(unsafe_path):
    """Paths with traversal or empty → skipped; valid files survive."""
    out = _validate_files(
        {
            "files": [
                {"path": "package.json", "content": '{"scripts":{"build":"vite build"}}'},
                {"path": "index.html", "content": "<html></html>"},
                {"path": "src/main.tsx", "content": "import React from 'react';"},
                {"path": unsafe_path, "content": "evil"},
            ]
        }
    )
    assert out is not None
    assert "package.json" in out
    # unsafe path should be filtered out — check it is NOT in the result
    for key in out:
        assert ".." not in key.split("/")
    # Only valid files should remain
    assert len(out) == 3  # package.json, index.html, src/main.tsx


def test_validate_files_leading_slash_normalised():
    """A leading slash is stripped, path is kept if otherwise safe."""
    out = _validate_files(
        {
            "files": [
                {"path": "package.json", "content": '{"scripts":{"build":"vite build"}}'},
                {"path": "index.html", "content": "<html></html>"},
                {"path": "/src/app.tsx", "content": "ok"},
            ]
        }
    )
    assert out is not None
    assert "src/app.tsx" in out


# ── 5. Missing package.json rejected ─────────────────────────────────────────


def test_validate_files_rejects_no_package_json():
    """A project without package.json is rejected entirely."""
    assert _validate_files({"files": [{"path": "src/main.tsx", "content": "x"}]}) is None


async def test_generate_rejects_output_missing_package_json():
    """End-to-end: Devin returns files without package.json → files is None."""
    bad = {"files": [{"path": "src/main.tsx", "content": "x"}]}
    with patch("src.services.generation.devin_codegen.settings") as mock_settings:
        mock_settings.course_build_mode = "devin"
        mock_settings.course_build_repair_max_retries = 2
        with patch(
            "src.services.generation.devin_codegen.DevinClient"
        ) as MockClient:
            instance = MockClient.return_value
            instance.enabled = True
            instance.run = AsyncMock(return_value=("sess-nopkg", bad))
            sid, files = await generate_course_app(SAMPLE_SPEC, SAMPLE_ASSET_MAP)
    assert sid == "sess-nopkg"
    assert files is None


# ── 6 & 7. Build failure → fallback (no repair loop yet) ─────────────────────


def test_build_from_sources_subprocess_failure_returns_none():
    """If npm build fails, _build_from_sources returns None (fallback)."""
    from src.services.generation.builder import _build_from_sources

    source_files = {
        "package.json": json.dumps({"name": "bad", "scripts": {"build": "exit 1"}}),
        "src/main.tsx": "console.log('hi')",
    }
    # Patch _npm to return a fake npm that will fail
    with patch(
        "src.services.generation.builder._npm", return_value="/usr/bin/false"
    ):
        result = _build_from_sources(source_files, {"title": "T"}, {})
    assert result is None


def test_build_from_sources_no_npm_returns_none():
    """No npm on PATH → _build_from_sources returns None immediately."""
    from src.services.generation.builder import _build_from_sources

    with patch("src.services.generation.builder._npm", return_value=None):
        result = _build_from_sources({"package.json": "{}"}, {"title": "T"}, {})
    assert result is None


def test_publish_built_course_falls_back_to_static_when_build_fails():
    """publish_built_course uses static fallback when source build AND template
    build both fail (e.g., npm not available)."""
    from src.services.generation.builder import publish_built_course

    source_files = {"package.json": "{}", "src/main.tsx": "x"}
    with (
        patch("src.services.generation.builder._npm", return_value=None),
        patch("src.services.generation.builder.ensure_bucket_exists"),
        patch("src.services.generation.builder.put_bytes") as mock_put,
        patch("src.services.generation.builder.settings") as mock_settings,
    ):
        mock_settings.course_build_enabled = True
        mock_settings.courses_bucket = "courses"
        mock_settings.minio_public_url = "http://localhost/storage"
        mock_settings.minio_secure = False
        mock_settings.minio_endpoint = "minio:9000"
        result = publish_built_course(
            "acme", "course-1", 1, {"title": "T"}, {}, source_files=source_files
        )
    assert result["built"] is False
    # Static fallback HTML was uploaded
    html_calls = [
        c
        for c in mock_put.call_args_list
        if c.args[1].endswith("index.html")
    ]
    assert html_calls
    uploaded_html = html_calls[0].args[0].decode()
    assert "<html" in uploaded_html


def test_publish_built_course_prefers_devin_sources_over_template():
    """When source_files are provided and build succeeds, the template is NOT
    used (dist comes from the Devin-authored project)."""
    from src.services.generation.builder import publish_built_course

    with (
        patch(
            "src.services.generation.builder._build_from_sources"
        ) as mock_devin_build,
        patch(
            "src.services.generation.builder._build_vite_app"
        ) as mock_tpl_build,
        patch("src.services.generation.builder._upload_dir"),
        patch("src.services.generation.builder.ensure_bucket_exists"),
        patch("src.services.generation.builder.put_bytes"),
        patch("src.services.generation.builder.settings") as mock_settings,
    ):
        mock_settings.course_build_enabled = True
        mock_settings.courses_bucket = "courses"
        mock_settings.minio_public_url = "http://localhost/storage"
        mock_settings.minio_secure = False
        mock_settings.minio_endpoint = "minio:9000"
        # Simulate successful Devin build
        fake_dist = Path("/tmp/fake-dist")
        fake_dist.mkdir(exist_ok=True)
        (fake_dist / "index.html").write_text("<html></html>")
        mock_devin_build.return_value = fake_dist

        result = publish_built_course(
            "acme", "c1", 1, {"title": "T"}, {}, source_files={"package.json": "{}"}
        )
    assert result["built"] is True
    mock_devin_build.assert_called_once()
    mock_tpl_build.assert_not_called()


def test_publish_built_course_no_sources_uses_template():
    """When source_files is None, the template path is used instead."""
    from src.services.generation.builder import publish_built_course

    with (
        patch(
            "src.services.generation.builder._build_from_sources"
        ) as mock_devin_build,
        patch(
            "src.services.generation.builder._build_vite_app"
        ) as mock_tpl_build,
        patch("src.services.generation.builder._upload_dir"),
        patch("src.services.generation.builder.ensure_bucket_exists"),
        patch("src.services.generation.builder.put_bytes"),
        patch("src.services.generation.builder.settings") as mock_settings,
    ):
        mock_settings.course_build_enabled = True
        mock_settings.courses_bucket = "courses"
        mock_settings.minio_public_url = "http://localhost/storage"
        mock_settings.minio_secure = False
        mock_settings.minio_endpoint = "minio:9000"
        fake_dist = Path("/tmp/fake-dist-tpl")
        fake_dist.mkdir(exist_ok=True)
        (fake_dist / "index.html").write_text("<html></html>")
        mock_tpl_build.return_value = fake_dist

        publish_built_course(
            "acme", "c2", 1, {"title": "T"}, {}, source_files=None
        )
    mock_devin_build.assert_not_called()
    mock_tpl_build.assert_called_once()


# ── Concept generation (Devin-primary) ────────────────────────────────────────


async def test_generate_concept_no_credentials_uses_local():
    """generate_concept falls back to local_concept when Devin is unconfigured."""
    from src.services.generation.concept import generate_concept

    with patch("src.services.generation.concept.DevinClient") as MockClient:
        MockClient.return_value.enabled = False
        sid, concept = await generate_concept(
            {"title": "Safety", "topics": ["PPE"]}, {}, "Acme", "#ff0000"
        )
    assert sid is None
    assert concept["title"] == "Safety"
    assert concept["companyName"] == "Acme"
    assert concept["primaryColor"] == "#ff0000"
    assert len(concept["chapters"]) >= 1


async def test_generate_concept_devin_error_falls_back():
    """DevinError during concept generation → local fallback, not exception."""
    from src.services.generation.concept import generate_concept

    with patch("src.services.generation.concept.DevinClient") as MockClient:
        instance = MockClient.return_value
        instance.enabled = True
        instance.run = AsyncMock(side_effect=DevinError("503"))
        sid, concept = await generate_concept(
            {"title": "Safety"}, {}, "Acme", "#ff0000"
        )
    assert sid is None
    assert concept["title"] == "Safety"


async def test_generate_concept_devin_success():
    """Devin returns valid concept → session_id and output returned."""
    from src.services.generation.concept import generate_concept

    devin_concept = {
        "title": "From Devin",
        "description": "AI-generated",
        "chapters": [{"id": "1", "title": "Ch1", "blocks": [], "quiz": []}],
    }
    with patch("src.services.generation.concept.DevinClient") as MockClient:
        instance = MockClient.return_value
        instance.enabled = True
        instance.run = AsyncMock(return_value=("sess-ok", devin_concept))
        sid, concept = await generate_concept(
            {"title": "From Devin"}, {}, "Acme", "#123"
        )
    assert sid == "sess-ok"
    assert concept["title"] == "From Devin"
    # Defaults are backfilled
    assert concept["companyName"] == "Acme"
    assert concept["primaryColor"] == "#123"


# ── Edited concept (Devin-primary) ────────────────────────────────────────────


async def test_edited_concept_no_credentials_uses_local():
    from src.services.generation.concept import generate_edited_concept

    with patch("src.services.generation.concept.DevinClient") as MockClient:
        MockClient.return_value.enabled = False
        sid, edited = await generate_edited_concept(
            {"title": "T", "chapters": [{"id": "1", "blocks": []}]},
            "make it shorter",
            "some text",
        )
    assert sid is None
    assert edited["chapters"][0]["blocks"][0]["type"] == "callout"
    assert "make it shorter" in edited["chapters"][0]["blocks"][0]["text"]


async def test_edited_concept_devin_error_falls_back():
    from src.services.generation.concept import generate_edited_concept

    with patch("src.services.generation.concept.DevinClient") as MockClient:
        instance = MockClient.return_value
        instance.enabled = True
        instance.run = AsyncMock(side_effect=DevinError("network"))
        sid, edited = await generate_edited_concept(
            {"title": "T", "chapters": [{"id": "1", "blocks": []}]},
            "reword",
            None,
        )
    assert sid is None
    assert "reword" in str(edited)
