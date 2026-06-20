import type { ComponentType } from "react";
import type { AssetMap, Page } from "../types";

// Props every bespoke, per-page component receives. Page components are authored
// independently (one Devin session per page) and registered below. When a page
// has no bespoke component, the shell falls back to the generic block renderer.
export interface PageComponentProps {
  page: Page;
  resolve: (link?: string) => string | undefined;
  assetMap: AssetMap;
}

// Keyed by "<chapterIndex>.<pageIndex>" (0-based). Populated by the generated
// registry when per-page code-gen runs; empty here so the template builds and
// renders via the generic fallback on its own.
export const pageComponents: Record<string, ComponentType<PageComponentProps>> = {};
