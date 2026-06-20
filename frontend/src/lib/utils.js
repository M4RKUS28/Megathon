import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
export function cn(...inputs) {
    return twMerge(clsx(inputs));
}
/**
 * Convert a #rrggbb (or #rgb) hex color into the "H S% L%" triple that the
 * Tailwind/shadcn CSS variables expect (e.g. "262 83% 58%").
 */
export function hexToHslTriple(hex) {
    let h = hex.trim().replace("#", "");
    if (h.length === 3)
        h = h.split("").map((c) => c + c).join("");
    if (h.length !== 6 || /[^0-9a-fA-F]/.test(h))
        return null;
    const r = parseInt(h.slice(0, 2), 16) / 255;
    const g = parseInt(h.slice(2, 4), 16) / 255;
    const b = parseInt(h.slice(4, 6), 16) / 255;
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const l = (max + min) / 2;
    let hue = 0;
    let sat = 0;
    if (max !== min) {
        const d = max - min;
        sat = l > 0.5 ? d / (2 - max - min) : d / (max + min);
        switch (max) {
            case r:
                hue = (g - b) / d + (g < b ? 6 : 0);
                break;
            case g:
                hue = (b - r) / d + 2;
                break;
            default:
                hue = (r - g) / d + 4;
        }
        hue /= 6;
    }
    return `${Math.round(hue * 360)} ${Math.round(sat * 100)}% ${Math.round(l * 100)}%`;
}
/** Accept either an "H S% L%" triple or a hex color and normalize to a triple. */
export function toHslTriple(value) {
    if (!value)
        return null;
    if (value.startsWith("#"))
        return hexToHslTriple(value);
    return value;
}
export function formatBytes(bytes) {
    if (bytes === 0)
        return "0 B";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}
