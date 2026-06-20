import { jsx as _jsx } from "react/jsx-runtime";
import { createContext, useContext, useEffect, useMemo } from "react";
import { toHslTriple } from "@/lib/utils";
const BrandContext = createContext({
    branding: null,
    companyName: "Coursive",
    logoUrl: null,
});
export function useBrand() {
    return useContext(BrandContext);
}
/**
 * Applies a tenant's branding by overriding the `--primary` CSS variable at the
 * document root, so every shadcn/Tailwind primary-colored element re-skins to
 * the company's color at runtime. Cleans up on unmount (e.g. back to landing).
 */
export function BrandProvider({ branding, children, }) {
    const primary = useMemo(() => {
        const fromField = toHslTriple(branding?.primary_color);
        if (fromField)
            return fromField;
        return toHslTriple(branding?.style_guide?.brandColors?.[0]);
    }, [branding]);
    useEffect(() => {
        const root = document.documentElement;
        if (!primary)
            return;
        root.style.setProperty("--primary", primary);
        // Choose readable foreground based on perceived lightness of the primary.
        const lightness = Number(primary.split(" ")[2]?.replace("%", "") ?? "50");
        root.style.setProperty("--primary-foreground", lightness > 62 ? "222 47% 11%" : "210 40% 98%");
        return () => {
            root.style.removeProperty("--primary");
            root.style.removeProperty("--primary-foreground");
        };
    }, [primary]);
    const value = {
        branding: branding ?? null,
        companyName: branding?.company_name || branding?.style_guide?.companyName || "Coursive",
        logoUrl: branding?.logo_url || branding?.style_guide?.logoUrls?.[0] || null,
    };
    return _jsx(BrandContext.Provider, { value: value, children: children });
}
