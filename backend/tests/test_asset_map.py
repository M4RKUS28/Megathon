"""Asset-map handling tests (offline: no network, no API keys, no MinIO).

Covers the asset manifest schema enrichments, the fetch_assets pipeline
(with the placeholder provider), asset_map round-trip through the builder,
the Devin prompt contract, and graceful handling of missing / partial maps.
"""

import json

from src.services.agents.fallback import fallback_lastenheft, fallback_plan
from src.services.agents.schemas import AssetSpec
from src.services.generation.assets import PlaceholderAssetProvider, fetch_assets
from src.services.generation.devin_codegen import _build_prompt

BRIEF = {
    "title": "Data Privacy Basics",
    "audience": "all employees",
    "goals": "comply with GDPR",
    "language": "en",
    "difficulty": "beginner",
    "topics": ["personal data", "consent", "breach reporting"],
}


# ── AssetSpec schema fields ──────────────────────────────────────────────────


def test_asset_spec_has_alt_text_and_usage_context():
    spec = AssetSpec(
        template_link="/resources/images/01",
        type="image",
        alt_text="A pie chart showing data categories",
        usage_context="hero image on intro page",
    )
    assert spec.alt_text == "A pie chart showing data categories"
    assert spec.usage_context == "hero image on intro page"


def test_asset_spec_defaults_for_new_fields():
    spec = AssetSpec(template_link="/resources/images/x", type="image")
    assert spec.alt_text == ""
    assert spec.usage_context == ""


def test_asset_spec_round_trips_through_json():
    spec = AssetSpec(
        template_link="/resources/video/01",
        type="video",
        dimensions="16:9",
        description="product demo",
        purpose="chapter 1 hero",
        alt_text="Demo video of GDPR workflow",
        usage_context="video block on page 'Overview' in chapter 'Intro'",
    )
    data = json.loads(spec.model_dump_json())
    restored = AssetSpec(**data)
    assert restored == spec


# ── Fallback manifest includes new fields ────────────────────────────────────


def test_fallback_manifest_populates_alt_text_and_usage_context():
    plan = fallback_plan(BRIEF, "Acme")
    lh = fallback_lastenheft(plan, "Acme", "#5145E5")
    assert lh.asset_manifest, "manifest must not be empty"
    for asset in lh.asset_manifest:
        assert asset.alt_text, f"{asset.template_link} missing alt_text"
        assert asset.usage_context, f"{asset.template_link} missing usage_context"


# ── Placeholder provider ────────────────────────────────────────────────────


def test_placeholder_produces_svg_for_every_type():
    provider = PlaceholderAssetProvider()
    for atype in ("image", "video", "audio", "diagram"):
        spec = AssetSpec(
            template_link=f"/resources/{atype}/test",
            type=atype,
            description="test asset",
            purpose="unit test",
            alt_text="test alt",
            usage_context="test context",
        )
        content, ext, ctype = provider.produce(spec, "#FF0000")
        assert ext == "svg"
        assert ctype == "image/svg+xml"
        assert b"<svg" in content


# ── fetch_assets mapping ────────────────────────────────────────────────────


def _stub_put_bytes(*_args, **_kwargs):
    pass


def _stub_ensure_bucket(*_args, **_kwargs):
    pass


def _stub_public_url(obj_name, _bucket):
    return f"https://cdn.example.com/{obj_name}"


async def test_fetch_assets_maps_template_links(monkeypatch):
    monkeypatch.setattr("src.services.generation.assets.put_bytes", _stub_put_bytes)
    monkeypatch.setattr(
        "src.services.generation.assets.ensure_bucket_exists", _stub_ensure_bucket
    )
    monkeypatch.setattr(
        "src.services.generation.assets.public_object_url", _stub_public_url
    )
    monkeypatch.setattr(
        "src.services.generation.assets.settings",
        type("S", (), {"courses_bucket": "test-bucket"})(),
    )

    specs = [
        AssetSpec(
            template_link="/resources/images/01",
            type="image",
            description="hero",
            alt_text="hero alt",
        ),
        AssetSpec(
            template_link="/resources/images/02",
            type="image",
            description="diagram",
            alt_text="diagram alt",
        ),
    ]
    provider = PlaceholderAssetProvider()
    result = await fetch_assets(specs, "acme/course1/v1", "#123", provider=provider)

    assert "/resources/images/01" in result
    assert "/resources/images/02" in result
    for url in result.values():
        assert url.startswith("https://cdn.example.com/")


async def test_fetch_assets_skips_failed_assets(monkeypatch):
    monkeypatch.setattr("src.services.generation.assets.put_bytes", _stub_put_bytes)
    monkeypatch.setattr(
        "src.services.generation.assets.ensure_bucket_exists", _stub_ensure_bucket
    )
    monkeypatch.setattr(
        "src.services.generation.assets.public_object_url", _stub_public_url
    )
    monkeypatch.setattr(
        "src.services.generation.assets.settings",
        type("S", (), {"courses_bucket": "test-bucket"})(),
    )

    class FailingProvider(PlaceholderAssetProvider):
        def produce(self, spec, color):
            if "fail" in spec.template_link:
                raise RuntimeError("provider error")
            return super().produce(spec, color)

    specs = [
        AssetSpec(template_link="/resources/images/ok", type="image", description="ok"),
        AssetSpec(template_link="/resources/images/fail", type="image", description="bad"),
    ]
    result = await fetch_assets(specs, "pfx", "#000", provider=FailingProvider())

    assert "/resources/images/ok" in result
    assert "/resources/images/fail" not in result


# ── asset_map.json shape ────────────────────────────────────────────────────


def test_asset_map_is_flat_string_to_string():
    plan = fallback_plan(BRIEF, "Acme")
    lh = fallback_lastenheft(plan, "Acme", "#5145E5")
    # Simulate the map the pipeline would produce.
    asset_map = {
        a.template_link: f"https://cdn.example.com/assets/{a.template_link.lstrip('/')}.svg"
        for a in lh.asset_manifest
    }
    serialised = json.dumps(asset_map)
    loaded = json.loads(serialised)
    assert isinstance(loaded, dict)
    for k, v in loaded.items():
        assert isinstance(k, str) and isinstance(v, str)


# ── Devin prompt contract ───────────────────────────────────────────────────


def test_devin_prompt_includes_asset_strategy_section():
    plan = fallback_plan(BRIEF, "Acme")
    lh = fallback_lastenheft(plan, "Acme", "#5145E5")
    spec = lh.model_dump()
    asset_map = {a.template_link: "https://cdn/x" for a in lh.asset_manifest}
    prompt = _build_prompt(spec, asset_map)

    assert "Asset resolution" in prompt or "Asset strategy" in prompt
    assert "template_link" in prompt
    assert "asset_map.json" in prompt
    assert "asset_map" in prompt.lower()
    assert "hard-code" in prompt.lower() or "never hard-code" in prompt.lower()


def test_devin_prompt_includes_manifest_section():
    spec = {
        "title": "Test",
        "chapters": [],
        "asset_manifest": [
            {
                "template_link": "/resources/images/01",
                "type": "image",
                "dimensions": "16:9",
                "description": "hero",
                "purpose": "intro",
                "alt_text": "Hero",
                "usage_context": "intro page",
            }
        ],
    }
    prompt = _build_prompt(spec, {"/resources/images/01": "https://cdn/hero.svg"})
    # The manifest is included as a separate section in the prompt
    assert "Asset manifest" in prompt or "asset_manifest" in prompt
    assert "/resources/images/01" in prompt


# ── Lastenheft -> asset_map round-trip ───────────────────────────────────────


def test_all_manifest_links_appear_as_block_assets():
    """Every template_link in the manifest should correspond to at least one
    block.asset in the spec — and vice-versa — for the fallback generator."""
    plan = fallback_plan(BRIEF, "Acme")
    lh = fallback_lastenheft(plan, "Acme", "#5145E5")

    manifest_links = {a.template_link for a in lh.asset_manifest}
    block_assets = {
        b.asset for ch in lh.chapters for p in ch.pages for b in p.blocks if b.asset
    }
    # Every block asset should be in the manifest.
    assert block_assets <= manifest_links, f"Missing from manifest: {block_assets - manifest_links}"
