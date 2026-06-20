"""Tests for the Devin codegen prompt construction and file validation."""

import json

import pytest

from src.services.generation.devin_codegen import (
    FORBIDDEN_PATH_SEGMENTS,
    REQUIRED_FILES,
    REQUIRED_PATH_PREFIXES,
    _build_prompt,
    _validate_files,
)

# ---------------------------------------------------------------------------
# Fixtures — minimal valid Lastenheft & asset map
# ---------------------------------------------------------------------------

SPEC = {
    "title": "Safety 101",
    "description": "Workplace safety basics",
    "companyName": "Acme",
    "primaryColor": "#5145E5",
    "language": "en",
    "passing_pct": 80,
    "chapters": [
        {
            "id": "ch1",
            "title": "PPE",
            "pages": [
                {
                    "id": "p1",
                    "title": "Intro",
                    "blocks": [{"type": "paragraph", "text": "Hello"}],
                }
            ],
            "quiz": {"passing_pct": 80, "retryable": True, "questions": []},
        }
    ],
    "asset_manifest": [
        {
            "template_link": "/resources/images/01",
            "type": "image",
            "description": "Hard hat",
            "purpose": "hero",
        }
    ],
}

ASSET_MAP = {"/resources/images/01": "https://storage.example.com/img01.png"}

# A minimal valid file set that would pass validation.
VALID_FILES = {
    "package.json": json.dumps({"name": "test", "scripts": {"build": "vite build"}}),
    "index.html": "<html></html>",
    "vite.config.ts": "export default {}",
    "src/main.tsx": "console.log('hi')",
    "src/App.tsx": "export function App() { return null; }",
}


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


class TestBuildPrompt:
    def test_contains_lastenheft(self):
        prompt = _build_prompt(SPEC, ASSET_MAP)
        assert "Safety 101" in prompt
        assert "PPE" in prompt

    def test_contains_asset_map(self):
        prompt = _build_prompt(SPEC, ASSET_MAP)
        assert "storage.example.com/img01.png" in prompt

    def test_strips_asset_manifest_from_course_json(self):
        prompt = _build_prompt(SPEC, ASSET_MAP)
        assert "asset_manifest" not in prompt

    def test_contains_platform_contracts(self):
        prompt = _build_prompt(SPEC, ASSET_MAP)
        for keyword in [
            "coursive:ready",
            "coursive:progress",
            "coursive:select-mode",
            "coursive:element-selected",
            "asset_map.json",
            "course.json",
            "quiz.passing_pct",
            "iframe",
        ]:
            assert keyword in prompt, f"prompt missing contract keyword: {keyword}"

    def test_contains_negative_constraints(self):
        prompt = _build_prompt(SPEC, ASSET_MAP)
        for phrase in [
            "Do NOT plan",
            "Do NOT rewrite",
            "Do NOT fetch",
            "Do NOT host",
            "Do NOT build a generic",
            "Do NOT make external API calls",
            "node_modules",
        ]:
            assert phrase in prompt, f"prompt missing negative constraint: {phrase}"

    def test_contains_design_system(self):
        prompt = _build_prompt(SPEC, ASSET_MAP)
        for keyword in [
            "60-30-10",
            "WCAG AA",
            "primaryColor",
            "Audio narration",
            "creative freedom",
        ]:
            assert keyword in prompt, f"prompt missing design keyword: {keyword}"

    def test_contains_interaction_affordances(self):
        prompt = _build_prompt(SPEC, ASSET_MAP)
        for lib in ["Recharts", "React Flow", "Framer Motion", "react-syntax-highlighter"]:
            assert lib in prompt, f"prompt missing library: {lib}"
        for block_type in [
            "flashcards",
            "dragdrop",
            "hotspot",
            "timeline",
            "accordion",
            "scenario",
            "sortable",
            "calculator",
            "simulation",
            "conversation",
            "minigame",
        ]:
            assert block_type in prompt, f"prompt missing block type: {block_type}"

    def test_contains_subagent_workflow(self):
        prompt = _build_prompt(SPEC, ASSET_MAP)
        assert "subagent" in prompt.lower()

    def test_contains_quiz_tabs(self):
        prompt = _build_prompt(SPEC, ASSET_MAP)
        assert "tabs" in prompt.lower() or "steps" in prompt.lower()

    def test_output_format_section(self):
        prompt = _build_prompt(SPEC, ASSET_MAP)
        assert "structured output" in prompt.lower()
        assert '"path"' in prompt
        assert '"content"' in prompt

    def test_truncates_large_spec(self):
        big_spec = {**SPEC, "huge": "x" * 200_000}
        prompt = _build_prompt(big_spec, ASSET_MAP)
        assert len(prompt) < 200_000


# ---------------------------------------------------------------------------
# File validation
# ---------------------------------------------------------------------------


class TestValidateFiles:
    def test_valid_output_accepted(self):
        output = {"files": [{"path": p, "content": c} for p, c in VALID_FILES.items()]}
        result = _validate_files(output)
        assert result is not None
        assert set(result.keys()) == set(VALID_FILES.keys())

    def test_none_on_empty_files(self):
        assert _validate_files({"files": []}) is None

    def test_none_on_missing_files_key(self):
        assert _validate_files({"other": "value"}) is None

    def test_none_on_non_dict(self):
        assert _validate_files("not a dict") is None  # type: ignore[arg-type]

    def test_none_on_non_list_files(self):
        assert _validate_files({"files": "string"}) is None

    def test_rejects_missing_package_json(self):
        files_without_pkg = {k: v for k, v in VALID_FILES.items() if k != "package.json"}
        output = {"files": [{"path": p, "content": c} for p, c in files_without_pkg.items()]}
        assert _validate_files(output) is None

    def test_rejects_missing_index_html(self):
        files_without_idx = {k: v for k, v in VALID_FILES.items() if k != "index.html"}
        output = {"files": [{"path": p, "content": c} for p, c in files_without_idx.items()]}
        assert _validate_files(output) is None

    def test_rejects_missing_src_directory(self):
        no_src = {k: v for k, v in VALID_FILES.items() if not k.startswith("src/")}
        output = {"files": [{"path": p, "content": c} for p, c in no_src.items()]}
        assert _validate_files(output) is None

    def test_rejects_package_json_without_build_script(self):
        bad_pkg = {
            **VALID_FILES,
            "package.json": json.dumps({"name": "test", "scripts": {"dev": "vite"}}),
        }
        output = {"files": [{"path": p, "content": c} for p, c in bad_pkg.items()]}
        assert _validate_files(output) is None

    def test_rejects_invalid_package_json(self):
        bad_pkg = {**VALID_FILES, "package.json": "not json {{{"}
        output = {"files": [{"path": p, "content": c} for p, c in bad_pkg.items()]}
        assert _validate_files(output) is None

    def test_rejects_path_traversal(self):
        files = {
            **VALID_FILES,
            "../../etc/passwd": "root:x:0:0",
        }
        output = {"files": [{"path": p, "content": c} for p, c in files.items()]}
        result = _validate_files(output)
        assert result is not None
        assert "../../etc/passwd" not in result

    def test_rejects_absolute_paths(self):
        files = {**VALID_FILES, "/etc/passwd": "root:x:0:0"}
        output = {"files": [{"path": p, "content": c} for p, c in files.items()]}
        result = _validate_files(output)
        assert result is not None
        assert "/etc/passwd" not in result

    @pytest.mark.parametrize("segment", sorted(FORBIDDEN_PATH_SEGMENTS))
    def test_rejects_forbidden_segments(self, segment: str):
        files = {**VALID_FILES, f"{segment}/bad.js": "bad"}
        output = {"files": [{"path": p, "content": c} for p, c in files.items()]}
        result = _validate_files(output)
        assert result is not None
        assert f"{segment}/bad.js" not in result

    def test_normalises_leading_dot_slash(self):
        files_dot = {"./package.json": VALID_FILES["package.json"]}
        files_dot["./index.html"] = VALID_FILES["index.html"]
        files_dot["./src/main.tsx"] = VALID_FILES["src/main.tsx"]
        files_dot["./src/App.tsx"] = VALID_FILES["src/App.tsx"]
        output = {"files": [{"path": p, "content": c} for p, c in files_dot.items()]}
        result = _validate_files(output)
        assert result is not None
        assert "package.json" in result
        assert "src/main.tsx" in result

    def test_normalises_leading_slash(self):
        files_slash = {"/package.json": VALID_FILES["package.json"]}
        files_slash["/index.html"] = VALID_FILES["index.html"]
        files_slash["/src/main.tsx"] = VALID_FILES["src/main.tsx"]
        files_slash["/src/App.tsx"] = VALID_FILES["src/App.tsx"]
        output = {"files": [{"path": p, "content": c} for p, c in files_slash.items()]}
        result = _validate_files(output)
        assert result is not None
        assert "package.json" in result

    def test_skips_non_dict_entries(self):
        output = {
            "files": [
                {"path": "package.json", "content": VALID_FILES["package.json"]},
                "not a dict",
                {"path": "index.html", "content": VALID_FILES["index.html"]},
                {"path": "src/main.tsx", "content": VALID_FILES["src/main.tsx"]},
                {"path": "src/App.tsx", "content": VALID_FILES["src/App.tsx"]},
            ]
        }
        result = _validate_files(output)
        assert result is not None

    def test_skips_entries_with_non_string_content(self):
        output = {
            "files": [
                {"path": "package.json", "content": VALID_FILES["package.json"]},
                {"path": "index.html", "content": VALID_FILES["index.html"]},
                {"path": "bad.txt", "content": 12345},
                {"path": "src/main.tsx", "content": VALID_FILES["src/main.tsx"]},
                {"path": "src/App.tsx", "content": VALID_FILES["src/App.tsx"]},
            ]
        }
        result = _validate_files(output)
        assert result is not None
        assert "bad.txt" not in result


# ---------------------------------------------------------------------------
# Constants sanity checks
# ---------------------------------------------------------------------------


class TestConstants:
    def test_required_files_not_empty(self):
        assert REQUIRED_FILES

    def test_required_path_prefixes_not_empty(self):
        assert REQUIRED_PATH_PREFIXES

    def test_forbidden_segments_include_node_modules_and_dist(self):
        assert "node_modules" in FORBIDDEN_PATH_SEGMENTS
        assert "dist" in FORBIDDEN_PATH_SEGMENTS
