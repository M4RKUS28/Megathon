import { jsx as _jsx, jsxs as _jsxs, Fragment as _Fragment } from "react/jsx-runtime";
import { Link } from "react-router-dom";
export function Wordmark({ className = "" }) {
    return (_jsxs(Link, { to: "/", className: `inline-flex items-center gap-2 ${className}`, children: [_jsx("span", { className: "grid h-7 w-7 place-items-center rounded-md bg-iris font-display text-sm font-bold text-white", children: "C" }), _jsx("span", { className: "font-display text-lg font-bold tracking-tight", children: "Coursive" })] }));
}
export function SiteHeader({ signedIn }) {
    return (_jsx("header", { className: "sticky top-0 z-30 border-b border-mist/60 bg-paper/80 backdrop-blur", children: _jsxs("div", { className: "mx-auto flex max-w-7xl items-center justify-between px-6 py-4", children: [_jsx(Wordmark, {}), _jsxs("nav", { className: "flex items-center gap-2 text-sm", children: [_jsx(Link, { to: "/about", className: "rounded-full px-4 py-2 text-ink/70 transition hover:text-ink", children: "About" }), signedIn ? (_jsx(Link, { to: "/dashboard", className: "rounded-full bg-ink px-4 py-2 font-medium text-paper transition hover:bg-ink/90", children: "Dashboard" })) : (_jsxs(_Fragment, { children: [_jsx(Link, { to: "/signin", className: "rounded-full px-4 py-2 text-ink/70 transition hover:text-ink", children: "Sign in" }), _jsx(Link, { to: "/signup", className: "rounded-full bg-ink px-4 py-2 font-medium text-paper transition hover:bg-ink/90", children: "Get started" })] }))] })] }) }));
}
export function SiteFooter() {
    return (_jsx("footer", { className: "border-t border-mist bg-paper", children: _jsxs("div", { className: "mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-6 py-10 text-sm text-ink/50 sm:flex-row", children: [_jsx(Wordmark, {}), _jsx("p", { className: "font-mono text-xs", children: "White-label AI course generation \u00B7 built on Devin" }), _jsxs("div", { className: "flex gap-5", children: [_jsx(Link, { to: "/about", className: "hover:text-ink", children: "About" }), _jsx(Link, { to: "/signin", className: "hover:text-ink", children: "Sign in" })] })] }) }));
}
