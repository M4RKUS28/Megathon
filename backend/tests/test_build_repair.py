"""Tests for the Devin build-validate-repair loop.

All tests use mocked Devin outputs and subprocess calls — no real npm or
Devin API is required.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.devin.client import DevinError
from src.services.generation.builder import BuildError, try_build_from_sources
from src.services.generation.devin_codegen import (
    _repair_prompt,
    _validate_files,
    generate_course_app,
)

# ── fixtures ──────────────────────────────────────────────────────────────────

MINIMAL_SPEC: dict = {
    "title": "Test Course",
    "chapters": [{"id": "ch1", "title": "Chapter 1", "pages": []}],
}
ASSET_MAP: dict = {"/resources/images/01": "https://cdn.example.com/img.png"}

GOOD_FILES: dict[str, str] = {
    "package.json": json.dumps(
        {"name": "test-course", "scripts": {"build": "echo ok", "dev": "echo ok"}}
    ),
    "vite.config.ts": "export default {}",
    "tsconfig.json": "{}",
    "index.html": "<html><body><div id='root'></div></body></html>",
    "src/main.tsx": "console.log('hi')",
}

BAD_FILES: dict[str, str] = {
    **GOOD_FILES,
    "src/main.tsx": "const x: number = 'oops'",  # type error
}

REPAIRED_FILES: dict[str, str] = {
    **GOOD_FILES,
    "src/main.tsx": "const x: number = 42",
}


def _devin_output(files: dict[str, str]) -> dict:
    return {"files": [{"path": p, "content": c} for p, c in files.items()]}


# ── _validate_files ───────────────────────────────────────────────────────────


def test_validate_files_accepts_good_output():
    result = _validate_files(_devin_output(GOOD_FILES))
    assert result is not None
    assert "package.json" in result
    assert len(result) == len(GOOD_FILES)


def test_validate_files_rejects_missing_package_json():
    files = {k: v for k, v in GOOD_FILES.items() if k != "package.json"}
    assert _validate_files(_devin_output(files)) is None


def test_validate_files_rejects_path_traversal():
    output = {
        "files": [
            {"path": "../../../etc/passwd", "content": "evil"},
            {"path": "package.json", "content": '{"scripts":{"build":"vite build"}}'},
            {"path": "index.html", "content": "<html></html>"},
            {"path": "src/main.tsx", "content": "import React from 'react';"},
        ]
    }
    result = _validate_files(output)
    assert result is not None
    assert "../../../etc/passwd" not in result
    assert "etc/passwd" not in result


def test_validate_files_rejects_empty():
    assert _validate_files({}) is None
    assert _validate_files({"files": []}) is None
    assert _validate_files({"files": "not a list"}) is None


# ── _repair_prompt ────────────────────────────────────────────────────────────


def test_repair_prompt_contains_error_logs():
    prompt = _repair_prompt("ERR: missing module 'foo'", GOOD_FILES, MINIMAL_SPEC, ASSET_MAP)
    assert "ERR: missing module 'foo'" in prompt
    assert "Fix ONLY implementation" in prompt
    assert "Do NOT change the curriculum" in prompt
    assert ">=80%" in prompt
    assert "platform contracts" in prompt
    assert "COMPLETE corrected file map" in prompt


def test_repair_prompt_lists_all_files():
    prompt = _repair_prompt("error", GOOD_FILES, MINIMAL_SPEC, ASSET_MAP)
    for path in GOOD_FILES:
        assert path in prompt


def test_repair_prompt_truncates_long_logs():
    long_logs = "x" * 20000
    prompt = _repair_prompt(long_logs, GOOD_FILES, MINIMAL_SPEC, ASSET_MAP)
    # Logs are truncated to 12000 chars.
    assert len(long_logs) > 12000
    assert "x" * 12000 in prompt


# ── try_build_from_sources ────────────────────────────────────────────────────


@patch("src.services.generation.builder._npm", return_value=None)
def test_try_build_raises_when_npm_missing(mock_npm):
    with pytest.raises(BuildError, match="npm not found"):
        try_build_from_sources(GOOD_FILES, {}, {})


@patch("src.services.generation.builder._npm", return_value="/usr/bin/npm")
@patch("subprocess.run")
def test_try_build_raises_on_install_failure(mock_run, mock_npm):
    mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="ERR npm install")
    with pytest.raises(BuildError, match="npm install failed") as exc_info:
        try_build_from_sources(GOOD_FILES, {}, {})
    assert "ERR npm install" in exc_info.value.logs


@patch("src.services.generation.builder._npm", return_value="/usr/bin/npm")
@patch("subprocess.run")
def test_try_build_raises_on_build_failure(mock_run, mock_npm):
    def side_effect(cmd, **kwargs):
        # npm install succeeds, npm run build fails.
        if "install" in cmd:
            return MagicMock(returncode=0, stdout="", stderr="")
        return MagicMock(returncode=1, stdout="", stderr="Build failed: TS2322")

    mock_run.side_effect = side_effect
    with pytest.raises(BuildError, match="npm run build failed") as exc_info:
        try_build_from_sources(GOOD_FILES, {}, {}, run_quality_checks=False)
    assert "TS2322" in exc_info.value.logs


@patch("src.services.generation.builder._npm", return_value="/usr/bin/npm")
@patch("subprocess.run")
def test_try_build_raises_on_quality_check_failure(mock_run, mock_npm):
    files_with_typecheck = {
        **GOOD_FILES,
        "package.json": json.dumps(
            {"name": "test", "scripts": {"build": "echo ok", "typecheck": "tsc --noEmit"}}
        ),
    }

    call_count = 0

    def side_effect(cmd, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:  # npm install
            return MagicMock(returncode=0, stdout="", stderr="")
        if call_count == 2:  # npm run typecheck
            return MagicMock(returncode=1, stdout="", stderr="error TS2322: Type 'string'")
        return MagicMock(returncode=0, stdout="", stderr="")  # build

    mock_run.side_effect = side_effect
    with pytest.raises(BuildError, match="quality checks failed") as exc_info:
        try_build_from_sources(files_with_typecheck, {}, {}, run_quality_checks=True)
    assert "TS2322" in exc_info.value.logs


@patch("src.services.generation.builder._npm", return_value="/usr/bin/npm")
@patch("subprocess.run")
def test_try_build_raises_on_timeout(mock_run, mock_npm):
    mock_run.side_effect = subprocess.TimeoutExpired(cmd="npm", timeout=600)
    with pytest.raises(BuildError, match="build timed out"):
        try_build_from_sources(GOOD_FILES, {}, {})


# ── generate_course_app (repair loop) ────────────────────────────────────────


@patch("src.services.generation.devin_codegen.settings")
async def test_generate_skips_when_devin_disabled(mock_settings):
    mock_settings.course_build_use_devin = False
    sid, files = await generate_course_app(MINIMAL_SPEC, ASSET_MAP)
    assert sid is None
    assert files is None


@patch("src.services.generation.devin_codegen.try_build_from_sources")
@patch("src.services.generation.devin_codegen.DevinClient")
@patch("src.services.generation.devin_codegen.settings")
async def test_generate_returns_files_on_successful_build(
    mock_settings, mock_client_cls, mock_build
):
    mock_settings.course_build_use_devin = True
    mock_settings.course_build_repair_max_retries = 2

    client = AsyncMock()
    client.enabled = True
    client.run = AsyncMock(return_value=("sess-1", _devin_output(GOOD_FILES)))
    mock_client_cls.return_value = client

    mock_build.return_value = Path("/tmp/dist")

    sid, files = await generate_course_app(MINIMAL_SPEC, ASSET_MAP)
    assert sid == "sess-1"
    assert files is not None
    assert "package.json" in files
    mock_build.assert_called_once()


@patch("src.services.generation.devin_codegen.try_build_from_sources")
@patch("src.services.generation.devin_codegen.DevinClient")
@patch("src.services.generation.devin_codegen.settings")
async def test_generate_repairs_on_first_build_failure(
    mock_settings, mock_client_cls, mock_build
):
    mock_settings.course_build_use_devin = True
    mock_settings.course_build_repair_max_retries = 2

    client = AsyncMock()
    client.enabled = True
    # First call: initial generation. Second call: repair.
    client.run = AsyncMock(
        side_effect=[
            ("sess-1", _devin_output(BAD_FILES)),
            ("sess-2", _devin_output(REPAIRED_FILES)),
        ]
    )
    mock_client_cls.return_value = client

    # First build fails, second succeeds.
    mock_build.side_effect = [
        BuildError("build failed", "TS2322: type error"),
        Path("/tmp/dist"),
    ]

    sid, files = await generate_course_app(MINIMAL_SPEC, ASSET_MAP)
    assert sid == "sess-1"
    assert files is not None
    assert files["src/main.tsx"] == "const x: number = 42"
    assert mock_build.call_count == 2
    assert client.run.call_count == 2


@patch("src.services.generation.devin_codegen.try_build_from_sources")
@patch("src.services.generation.devin_codegen.DevinClient")
@patch("src.services.generation.devin_codegen.settings")
async def test_generate_falls_back_after_max_retries(
    mock_settings, mock_client_cls, mock_build
):
    mock_settings.course_build_use_devin = True
    mock_settings.course_build_repair_max_retries = 1

    client = AsyncMock()
    client.enabled = True
    client.run = AsyncMock(
        side_effect=[
            ("sess-1", _devin_output(BAD_FILES)),
            ("sess-2", _devin_output(BAD_FILES)),  # repair also bad
        ]
    )
    mock_client_cls.return_value = client

    # Both builds fail.
    mock_build.side_effect = [
        BuildError("build failed", "error 1"),
        BuildError("build failed", "error 2"),
    ]

    sid, files = await generate_course_app(MINIMAL_SPEC, ASSET_MAP)
    assert sid == "sess-1"
    assert files is None  # fell back to template
    assert mock_build.call_count == 2


@patch("src.services.generation.devin_codegen.try_build_from_sources")
@patch("src.services.generation.devin_codegen.DevinClient")
@patch("src.services.generation.devin_codegen.settings")
async def test_generate_falls_back_when_repair_returns_nothing(
    mock_settings, mock_client_cls, mock_build
):
    mock_settings.course_build_use_devin = True
    mock_settings.course_build_repair_max_retries = 2

    client = AsyncMock()
    client.enabled = True
    client.run = AsyncMock(
        side_effect=[
            ("sess-1", _devin_output(BAD_FILES)),
            DevinError("Devin API error"),  # repair session fails
        ]
    )
    mock_client_cls.return_value = client

    mock_build.side_effect = BuildError("build failed", "error")

    sid, files = await generate_course_app(MINIMAL_SPEC, ASSET_MAP)
    assert sid == "sess-1"
    assert files is None


@patch("src.services.generation.devin_codegen.try_build_from_sources")
@patch("src.services.generation.devin_codegen.DevinClient")
@patch("src.services.generation.devin_codegen.settings")
async def test_generate_falls_back_when_devin_generation_fails(
    mock_settings, mock_client_cls, mock_build
):
    mock_settings.course_build_use_devin = True

    client = AsyncMock()
    client.enabled = True
    client.run = AsyncMock(side_effect=DevinError("session timeout"))
    mock_client_cls.return_value = client

    sid, files = await generate_course_app(MINIMAL_SPEC, ASSET_MAP)
    assert sid is None
    assert files is None
    mock_build.assert_not_called()


@patch("src.services.generation.devin_codegen.try_build_from_sources")
@patch("src.services.generation.devin_codegen.DevinClient")
@patch("src.services.generation.devin_codegen.settings")
async def test_repair_respects_max_retries_config(
    mock_settings, mock_client_cls, mock_build
):
    """With max_retries=0, no repair is attempted."""
    mock_settings.course_build_use_devin = True
    mock_settings.course_build_repair_max_retries = 0

    client = AsyncMock()
    client.enabled = True
    client.run = AsyncMock(return_value=("sess-1", _devin_output(BAD_FILES)))
    mock_client_cls.return_value = client

    mock_build.side_effect = BuildError("build failed", "error")

    sid, files = await generate_course_app(MINIMAL_SPEC, ASSET_MAP)
    assert sid == "sess-1"
    assert files is None
    # Only the initial build attempt, no repair sessions.
    assert client.run.call_count == 1
    assert mock_build.call_count == 1


@patch("src.services.generation.devin_codegen.try_build_from_sources")
@patch("src.services.generation.devin_codegen.DevinClient")
@patch("src.services.generation.devin_codegen.settings")
async def test_second_repair_succeeds(
    mock_settings, mock_client_cls, mock_build
):
    """Build fails, first repair also fails, second repair succeeds."""
    mock_settings.course_build_use_devin = True
    mock_settings.course_build_repair_max_retries = 2

    client = AsyncMock()
    client.enabled = True
    client.run = AsyncMock(
        side_effect=[
            ("sess-1", _devin_output(BAD_FILES)),
            ("sess-2", _devin_output(BAD_FILES)),  # first repair still bad
            ("sess-3", _devin_output(REPAIRED_FILES)),  # second repair good
        ]
    )
    mock_client_cls.return_value = client

    mock_build.side_effect = [
        BuildError("build failed", "error 1"),  # initial
        BuildError("build failed", "error 2"),  # after first repair
        Path("/tmp/dist"),  # after second repair
    ]

    sid, files = await generate_course_app(MINIMAL_SPEC, ASSET_MAP)
    assert sid == "sess-1"
    assert files is not None
    assert files["src/main.tsx"] == "const x: number = 42"
    assert mock_build.call_count == 3
    assert client.run.call_count == 3
