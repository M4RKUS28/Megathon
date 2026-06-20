import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { NavLink, Outlet } from "react-router-dom";
import { FolderClosed, LayoutDashboard, } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useMe } from "@/hooks/useMe";
import { useMyBranding } from "@/hooks/useBranding";
import { BrandProvider, useBrand } from "@/theme/ThemeProvider";
const ALL = ["admin", "course_creator", "user"];
// Nav grows as each phase lands its pages.
const NAV = [
    { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ALL },
    { to: "/files", label: "Files", icon: FolderClosed, roles: ALL },
];
function Brandmark() {
    const { companyName, logoUrl } = useBrand();
    return (_jsxs("div", { className: "flex items-center gap-2.5", children: [logoUrl ? (_jsx("img", { src: logoUrl, alt: "", className: "h-8 w-8 rounded-md object-cover" })) : (_jsx("span", { className: "grid h-8 w-8 place-items-center rounded-md bg-primary text-sm font-bold text-primary-foreground", children: companyName.charAt(0) })), _jsxs("div", { className: "leading-tight", children: [_jsx("p", { className: "text-sm font-semibold", children: companyName }), _jsx("p", { className: "font-mono text-[10px] uppercase tracking-wider text-muted-foreground", children: "on Coursive" })] })] }));
}
function Shell() {
    const { user, logout } = useAuth();
    const { data: me } = useMe();
    const role = (me?.role ?? "user");
    const items = NAV.filter((i) => i.roles.includes(role));
    return (_jsxs("div", { className: "flex min-h-screen bg-background text-foreground", children: [_jsxs("aside", { className: "sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-border bg-card px-4 py-5 md:flex", children: [_jsx(Brandmark, {}), _jsx("nav", { className: "mt-8 flex flex-1 flex-col gap-1", children: items.map(({ to, label, icon: Icon }) => (_jsxs(NavLink, { to: to, className: ({ isActive }) => `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${isActive
                                ? "bg-primary/10 font-medium text-primary"
                                : "text-muted-foreground hover:bg-secondary hover:text-foreground"}`, children: [_jsx(Icon, { className: "h-4 w-4" }), label] }, to))) }), _jsxs("div", { className: "mt-auto rounded-lg border border-border p-3", children: [_jsx("p", { className: "truncate text-sm font-medium", children: me?.display_name || user?.username }), _jsx("p", { className: "font-mono text-[10px] uppercase tracking-wider text-muted-foreground", children: role }), _jsx("button", { onClick: () => logout(), className: "mt-3 w-full rounded-md bg-secondary px-3 py-1.5 text-xs text-secondary-foreground transition hover:bg-secondary/80", children: "Sign out" })] })] }), _jsxs("div", { className: "flex min-w-0 flex-1 flex-col", children: [_jsxs("header", { className: "flex items-center justify-between border-b border-border px-6 py-3 md:hidden", children: [_jsx(Brandmark, {}), _jsx("button", { onClick: () => logout(), className: "rounded-md bg-secondary px-3 py-1.5 text-xs text-secondary-foreground", children: "Sign out" })] }), _jsx("main", { className: "mx-auto w-full max-w-6xl flex-1 px-6 py-8", children: _jsx(Outlet, {}) })] })] }));
}
export function Layout() {
    const { data: branding } = useMyBranding();
    return (_jsx(BrandProvider, { branding: branding, children: _jsx(Shell, {}) }));
}
