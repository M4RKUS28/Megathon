"""Tests for the gold-standard Lastenheft fixture.

Validates schema compliance, structural invariants, interaction coverage, and
prompt-construction round-trips against the hand-crafted fixture in
``tests/fixtures/gold_lastenheft.json``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.services.agents.schemas import AssetSpec, Block, Lastenheft, Page, SpecChapter
from src.services.generation.builder import _static_fallback_html
from src.services.generation.devin_codegen import _build_prompt

FIXTURE = Path(__file__).parent / "fixtures" / "gold_lastenheft.json"


@pytest.fixture()
def raw() -> dict:
    return json.loads(FIXTURE.read_text())


@pytest.fixture()
def spec(raw: dict) -> Lastenheft:
    return Lastenheft(**raw)


# ── Schema validation ────────────────────────────────────────────────────────


def test_fixture_parses_as_lastenheft(spec: Lastenheft):
    assert spec.title
    assert spec.companyName
    assert spec.primaryColor.startswith("#")
    assert spec.language == "en"
    assert spec.passing_pct == 80


def test_fixture_has_three_chapters(spec: Lastenheft):
    assert len(spec.chapters) == 3


def test_every_chapter_has_pages_and_quiz(spec: Lastenheft):
    for ch in spec.chapters:
        assert isinstance(ch, SpecChapter)
        assert ch.id and ch.title and ch.objective
        assert 2 <= len(ch.pages) <= 4, f"{ch.id} has {len(ch.pages)} pages"
        assert ch.quiz.passing_pct == 80
        assert ch.quiz.retryable is True
        assert len(ch.quiz.questions) >= 3, f"{ch.id} quiz too short"
        for q in ch.quiz.questions:
            assert 0 <= q.answerIndex < len(q.options)
            assert q.explanation


def test_page_ids_unique_within_chapter(spec: Lastenheft):
    for ch in spec.chapters:
        ids = [p.id for p in ch.pages]
        assert len(ids) == len(set(ids)), f"duplicate page ids in {ch.id}"


def test_pages_carry_blocks_and_titles(spec: Lastenheft):
    for ch in spec.chapters:
        for page in ch.pages:
            assert isinstance(page, Page)
            assert page.title
            assert page.blocks
            for block in page.blocks:
                assert isinstance(block, Block)
                assert block.type


def test_quiz_never_inside_content_page(spec: Lastenheft):
    for ch in spec.chapters:
        types = {b.type for p in ch.pages for b in p.blocks}
        assert "quiz" not in types, f"{ch.id} has quiz block inside a page"


# ── Interaction coverage ─────────────────────────────────────────────────────


REQUIRED_BLOCK_TYPES = {
    "heading",
    "paragraph",
    "callout",
    "image",
    "video",
    "dialogue",
    "chart",
    "flashcards",
    "dragdrop",
    "hotspot",
    "timeline",
    "accordion",
    "scenario",
}


def _all_blocks(spec: Lastenheft) -> list[Block]:
    return [b for ch in spec.chapters for p in ch.pages for b in p.blocks]


def test_interaction_coverage(spec: Lastenheft):
    present = {b.type for b in _all_blocks(spec)}
    missing = REQUIRED_BLOCK_TYPES - present
    assert not missing, f"fixture is missing block types: {missing}"


def test_process_flow_via_timeline(spec: Lastenheft):
    timelines = [b for b in _all_blocks(spec) if b.type == "timeline"]
    assert timelines, "no timeline (process-flow) block found"
    for t in timelines:
        assert t.data and "steps" in t.data
        assert len(t.data["steps"]) >= 3
        for step in t.data["steps"]:
            assert "label" in step and "description" in step


def test_scenario_branches(spec: Lastenheft):
    scenarios = [b for b in _all_blocks(spec) if b.type == "scenario"]
    assert scenarios, "no scenario (branching) block found"
    for s in scenarios:
        assert s.data and "branches" in s.data
        branches = s.data["branches"]
        assert len(branches) >= 3
        outcomes = {br["outcome"] for br in branches}
        assert "correct" in outcomes, "scenario must have at least one correct branch"
        for br in branches:
            assert "choice" in br and "feedback" in br


def test_chart_visualisation(spec: Lastenheft):
    charts = [b for b in _all_blocks(spec) if b.type == "chart"]
    assert len(charts) >= 2, "expected at least 2 chart blocks"
    chart_types_seen = set()
    for c in charts:
        assert c.data and "chartType" in c.data
        assert c.data.get("labels") and c.data.get("datasets")
        chart_types_seen.add(c.data["chartType"])
    assert len(chart_types_seen) >= 2, f"only {chart_types_seen} chart types; want >=2"


def test_dragdrop_matching(spec: Lastenheft):
    dd = [b for b in _all_blocks(spec) if b.type == "dragdrop"]
    assert dd, "no dragdrop (matching/sort) block found"
    for d in dd:
        assert d.data and "prompt" in d.data
        has_pairs = "pairs" in d.data
        has_items = "items" in d.data
        assert has_pairs or has_items, "dragdrop needs pairs or items"


def test_hotspot_annotated_diagram(spec: Lastenheft):
    hs = [b for b in _all_blocks(spec) if b.type == "hotspot"]
    assert len(hs) >= 2, "expected at least 2 hotspot blocks"
    for h in hs:
        assert h.data and "regions" in h.data
        assert len(h.data["regions"]) >= 3
        for r in h.data["regions"]:
            assert "id" in r and "label" in r and "detail" in r
            assert "x_pct" in r and "y_pct" in r


# ── Asset manifest ───────────────────────────────────────────────────────────


def test_asset_manifest_well_formed(spec: Lastenheft):
    assert spec.asset_manifest
    assert len(spec.asset_manifest) >= 5
    for a in spec.asset_manifest:
        assert isinstance(a, AssetSpec)
        assert a.template_link.startswith("/resources/")
        assert a.type in {"image", "video", "audio", "diagram"}
        assert a.description
        assert a.purpose


def test_every_block_asset_ref_in_manifest(spec: Lastenheft):
    manifest_links = {a.template_link for a in spec.asset_manifest}
    for b in _all_blocks(spec):
        if b.asset:
            assert b.asset in manifest_links, f"block asset {b.asset!r} not in manifest"


def test_manifest_links_unique(spec: Lastenheft):
    links = [a.template_link for a in spec.asset_manifest]
    assert len(links) == len(set(links)), "duplicate template_links in asset_manifest"


def test_manifest_covers_multiple_asset_types(spec: Lastenheft):
    types = {a.type for a in spec.asset_manifest}
    assert len(types) >= 3, f"only {types} asset types; want >=3"


# ── Prompt construction round-trip ───────────────────────────────────────────


def test_devin_prompt_includes_fixture_content(raw: dict):
    asset_map = {a["template_link"]: f"https://cdn.example.com{a['template_link']}.png"
                 for a in raw.get("asset_manifest", [])}
    prompt = _build_prompt(raw, asset_map)
    assert raw["title"] in prompt
    assert "asset_manifest" not in prompt, "prompt must strip asset_manifest from spec"
    assert "Lastenheft" in prompt
    for ch in raw["chapters"]:
        assert ch["title"] in prompt


def test_static_fallback_renders_fixture(raw: dict):
    render_data = {k: v for k, v in raw.items() if k != "asset_manifest"}
    html = _static_fallback_html(render_data)
    assert "<html" in html
    assert raw["primaryColor"] in html
    assert raw["title"] in html
    assert "coursive:select-mode" in html


# ── Branding / style_guide ───────────────────────────────────────────────────


def test_fixture_carries_style_guide(raw: dict):
    sg = raw.get("style_guide")
    assert sg, "fixture must include a style_guide object"
    assert "font_heading" in sg
    assert "font_body" in sg
    assert "tone" in sg
    assert "illustration_style" in sg


def test_primary_color_is_valid_hex(spec: Lastenheft):
    assert spec.primaryColor.startswith("#")
    assert len(spec.primaryColor) == 7
    int(spec.primaryColor[1:], 16)  # must parse as hex
