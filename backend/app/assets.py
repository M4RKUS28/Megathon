from __future__ import annotations

from .timeutils import now_iso


def build_asset_map(asset_manifest: list[dict]) -> list[dict]:
    created_at = now_iso()
    asset_map = []
    for index, asset in enumerate(asset_manifest, start=1):
        extension = "svg" if asset["type"] in {"image", "diagram", "icon"} else "placeholder"
        final_url = f"/generated/assets/asset_{index:03d}.{extension}"
        asset_map.append(
            {
                "template_link": asset["template_link"],
                "status": "ready",
                "final_url": final_url,
                "validation_result": "deterministic local demo asset mapped; production interface ready for Unsplash, Pexels, image generation, TTS, and S3/MinIO",
                "source": "local_deterministic_asset_worker",
                "created_at": created_at,
                "updated_at": created_at,
            }
        )
    return asset_map


def asset_interfaces() -> dict:
    return {
        "unsplash": {"status": "designed", "adapter": "future ImageProvider.search"},
        "pexels": {"status": "designed", "adapter": "future ImageProvider.search"},
        "image_generation": {"status": "designed", "adapter": "future ImageProvider.generate"},
        "tts": {"status": "designed", "adapter": "future AudioProvider.generate_narration"},
        "minio_s3": {"status": "designed", "adapter": "future ObjectStore.put"},
    }
