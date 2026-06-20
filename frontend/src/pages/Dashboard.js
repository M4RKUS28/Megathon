import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { Link } from "react-router-dom";
import { ArrowUpRight, GraduationCap, Layers, Users } from "lucide-react";
import { useMe } from "@/hooks/useMe";
import { useBrand } from "@/theme/ThemeProvider";
export function DashboardPage() {
    const { data: me } = useMe();
    const { companyName } = useBrand();
    const role = me?.role ?? "user";
    const isStaff = role === "admin" || role === "course_creator";
    const stats = [
        { label: "Published courses", value: "—", icon: Layers },
        { label: "Active learners", value: "—", icon: Users },
        { label: "Avg. completion", value: "—", icon: GraduationCap },
    ];
    return (_jsxs("div", { className: "space-y-8", children: [_jsxs("div", { children: [_jsx("p", { className: "font-mono text-xs uppercase tracking-[0.2em] text-primary", children: companyName }), _jsxs("h1", { className: "mt-2 text-3xl font-bold tracking-tight", children: ["Welcome back, ", me?.display_name?.split(" ")[0] || "there", "."] }), _jsx("p", { className: "mt-1 text-muted-foreground", children: isStaff
                            ? "Generate, brand and assign training — then watch it land."
                            : "Pick up your assigned courses and keep your progress moving." })] }), _jsx("div", { className: "grid gap-4 sm:grid-cols-3", children: stats.map(({ label, value, icon: Icon }) => (_jsxs("div", { className: "rounded-xl border border-border bg-card p-5", children: [_jsxs("div", { className: "flex items-center justify-between", children: [_jsx("p", { className: "text-sm text-muted-foreground", children: label }), _jsx(Icon, { className: "h-4 w-4 text-primary" })] }), _jsx("p", { className: "mt-3 text-3xl font-bold", children: value })] }, label))) }), _jsxs("div", { className: "rounded-2xl border border-border bg-gradient-to-br from-primary/10 to-transparent p-8", children: [_jsx("h2", { className: "text-xl font-semibold", children: isStaff ? "Spin up a course in minutes" : "Your learning, personalized" }), _jsx("p", { className: "mt-2 max-w-xl text-sm text-muted-foreground", children: isStaff
                            ? "Describe what people need to know. Coursive drafts the concept, generates a branded interactive course, and hosts it for you."
                            : "Assigned courses appear here once your team publishes them. Mandatory training is flagged so you never miss it." }), _jsxs(Link, { to: isStaff ? "/courses/new" : "/learning", className: "mt-5 inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition hover:opacity-90", children: [isStaff ? "Create a course" : "Go to my learning", _jsx(ArrowUpRight, { className: "h-4 w-4" })] })] })] }));
}
