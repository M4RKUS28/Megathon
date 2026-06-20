import { Navigate } from "react-router-dom";
import { useMe } from "@/hooks/useMe";
import type { AppRole } from "@/lib/api";

/**
 * Guards a route by the user's *application* role (from /me), which is the
 * authoritative tenant role — as opposed to raw Keycloak realm roles.
 */
export function RoleRoute({ roles, children }: { roles: AppRole[]; children: React.ReactNode }) {
  const { data: me, isLoading, isError } = useMe();

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <span className="text-sm text-muted-foreground">Loading…</span>
      </div>
    );
  }

  if (isError || !me || !roles.includes(me.role)) {
    return <Navigate to="/forbidden" replace />;
  }

  return <>{children}</>;
}
