"""Asset-pipeline providers (Phase 2.5 Process A).

Each provider implements `AssetProvider.produce`. `build_asset_provider` returns a
`CompositeAssetProvider` that dispatches per asset type (image/video/audio) to the
configured real provider, falling back to the branded-SVG placeholder when a
provider is not configured or fails.

Smart filtering: the pipeline detects forced/generic asset descriptions and routes
them directly to the placeholder, saving expensive API calls for assets that have
genuine, rich creative briefs.
"""

from .composite import build_asset_provider

__all__ = ["build_asset_provider"]
