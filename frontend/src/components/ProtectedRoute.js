import { jsx as _jsx, Fragment as _Fragment } from "react/jsx-runtime";
import { Navigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
export function ProtectedRoute({ children, requiredRole }) {
    const { ready, authenticated, user } = useAuth();
    if (!ready) {
        return (_jsx("div", { className: "flex h-screen items-center justify-center", children: _jsx("span", { className: "text-muted-foreground text-sm", children: "Loading..." }) }));
    }
    if (!authenticated)
        return _jsx(Navigate, { to: "/signin", replace: true });
    if (requiredRole && !user?.roles.includes(requiredRole)) {
        return _jsx(Navigate, { to: "/forbidden", replace: true });
    }
    return _jsx(_Fragment, { children: children });
}
