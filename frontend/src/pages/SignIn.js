import { jsx as _jsx } from "react/jsx-runtime";
import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
// Sends the user straight to Keycloak's hosted login page. If they already
// have a session (check-sso), they go directly to the dashboard instead.
export function SignInPage() {
    const { ready, authenticated, login } = useAuth();
    const navigate = useNavigate();
    const triggered = useRef(false);
    useEffect(() => {
        if (!ready || triggered.current)
            return;
        if (authenticated) {
            navigate("/dashboard", { replace: true });
            return;
        }
        triggered.current = true;
        login(window.location.origin + "/dashboard");
    }, [ready, authenticated, login, navigate]);
    return (_jsx("div", { className: "flex h-screen items-center justify-center", children: _jsx("span", { className: "text-muted-foreground text-sm", children: "Redirecting to sign in\u2026" }) }));
}
