import { jsx as _jsx, jsxs as _jsxs } from "react/jsx-runtime";
import { createBrowserRouter } from "react-router-dom";
import { Layout } from "@/components/Layout";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { LandingPage } from "@/pages/Landing";
import { AboutPage } from "@/pages/About";
import { SignInPage } from "@/pages/SignIn";
import { SignUpPage } from "@/pages/SignUp";
import { DashboardPage } from "@/pages/Dashboard";
import { FileManagerPage } from "@/pages/FileManager";
export const router = createBrowserRouter([
    {
        path: "/",
        element: _jsx(LandingPage, {}),
    },
    {
        path: "/about",
        element: _jsx(AboutPage, {}),
    },
    {
        path: "/signin",
        element: _jsx(SignInPage, {}),
    },
    {
        path: "/signup",
        element: _jsx(SignUpPage, {}),
    },
    {
        element: (_jsx(ProtectedRoute, { children: _jsx(Layout, {}) })),
        children: [
            { path: "dashboard", element: _jsx(DashboardPage, {}) },
            { path: "files", element: _jsx(FileManagerPage, {}) },
            {
                path: "admin",
                element: (_jsx(ProtectedRoute, { requiredRole: "admin", children: _jsxs("div", { children: [_jsx("h1", { className: "text-2xl font-bold", children: "Admin Panel" }), _jsx("p", { className: "text-muted-foreground", children: "Admin-only area." })] }) })),
            },
        ],
    },
    {
        path: "/forbidden",
        element: (_jsxs("div", { className: "flex h-screen flex-col items-center justify-center gap-2", children: [_jsx("h1", { className: "text-2xl font-bold", children: "403 \u2014 Forbidden" }), _jsx("p", { className: "text-muted-foreground", children: "You don't have permission to access this page." })] })),
    },
]);
