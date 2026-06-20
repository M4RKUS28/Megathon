import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { SiteHeader, SiteFooter } from "@/components/Site";
const architecture = [
    {
        k: "Platform dashboard",
        v: "A multi-tenant React app. Each company sees only its own data, people, and courses, re-skinned to its brand.",
    },
    {
        k: "Generation pipeline",
        v: "A queue hands course briefs to the Devin API, which scaffolds, builds and tests a standalone course web app from your style guide.",
    },
    {
        k: "Course hosting",
        v: "Built courses are stored as static apps and embedded over a sandboxed boundary — progress flows back without exposing tokens.",
    },
    {
        k: "Edit loop",
        v: "Creators select an element in a course and request a change in plain language. Devin proposes it; the creator accepts or rejects.",
    },
];
const principles = [
    ["Strict isolation", "One company can never see or affect another. Tenancy is enforced on every request."],
    ["Brand-native", "The style guide drives both the dashboard and every generated course — not a logo in a corner."],
    ["Real apps, not slides", "Courses are interactive web apps, versioned and improvable, not static exports."],
];
export function AboutPage() {
    const { ready, authenticated } = useAuth();
    const signedIn = ready && authenticated;
    return (_jsxs("div", { className: "min-h-screen bg-paper text-ink", children: [_jsx(SiteHeader, { signedIn: signedIn }), _jsx("section", { className: "bg-ink text-paper", children: _jsxs("div", { className: "mx-auto max-w-3xl px-6 py-20 lg:py-28", children: [_jsx("p", { className: "font-mono text-xs tracking-[0.3em] text-signal", children: "ABOUT COURSIVE" }), _jsx("h1", { className: "mt-5 font-display text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl", children: "We turn company knowledge into living courses." }), _jsx("p", { className: "mt-6 text-lg text-paper/70", children: "Onboarding and internal training are stuck in slide decks that go stale the moment they're made. Coursive replaces the authoring grind with a pipeline: describe what people need to know, and an AI agent generates a real, branded, interactive course \u2014 then keeps it improvable." })] }) }), _jsxs("section", { className: "mx-auto max-w-5xl px-6 py-20", children: [_jsx("h2", { className: "font-display text-3xl font-bold tracking-tight", children: "How the system fits together" }), _jsx("div", { className: "mt-10 divide-y divide-mist border-y border-mist", children: architecture.map((row, i) => (_jsxs("div", { className: "grid gap-2 py-6 sm:grid-cols-[auto_1fr] sm:gap-10", children: [_jsxs("div", { className: "flex items-baseline gap-4", children: [_jsx("span", { className: "font-mono text-sm text-signal", children: String(i + 1).padStart(2, "0") }), _jsx("span", { className: "font-display text-lg font-semibold", children: row.k })] }), _jsx("p", { className: "text-ink/60 sm:pt-0.5", children: row.v })] }, row.k))) })] }), _jsxs("section", { className: "mx-auto max-w-5xl px-6 pb-20", children: [_jsx("div", { className: "grid gap-6 sm:grid-cols-3", children: principles.map(([k, v]) => (_jsxs("div", { className: "rounded-2xl border border-mist bg-white p-6", children: [_jsx("h3", { className: "font-display text-lg font-semibold", children: k }), _jsx("p", { className: "mt-2 text-sm leading-relaxed text-ink/60", children: v })] }, k))) }), _jsxs("div", { className: "mt-12 flex items-center gap-4", children: [_jsxs(Link, { to: signedIn ? "/dashboard" : "/signup", className: "group inline-flex items-center gap-2 rounded-full bg-iris px-6 py-3 font-medium text-white transition hover:bg-iris/90", children: [signedIn ? "Open dashboard" : "Try the demo tenant", _jsx(ArrowRight, { className: "h-4 w-4 transition group-hover:translate-x-0.5" })] }), _jsx("span", { className: "font-mono text-xs text-ink/40", children: "acme \u00B7 creator / creator" })] })] }), _jsx(SiteFooter, {})] }));
}
