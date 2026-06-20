import { useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";

// Sends the user straight to Keycloak's hosted registration page. If they
// already have a session (check-sso), they go directly to the dashboard.
export function SignUpPage() {
  const { ready, authenticated, register } = useAuth();
  const navigate = useNavigate();
  const triggered = useRef(false);

  useEffect(() => {
    if (!ready || triggered.current) return;
    if (authenticated) {
      navigate("/dashboard", { replace: true });
      return;
    }
    triggered.current = true;
    register(window.location.origin + "/dashboard");
  }, [ready, authenticated, register, navigate]);

  return (
    <div className="flex h-screen items-center justify-center">
      <span className="text-muted-foreground text-sm">Redirecting to sign up…</span>
    </div>
  );
}
