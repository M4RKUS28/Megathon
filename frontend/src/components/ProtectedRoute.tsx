import { Navigate } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";

interface Props {
  children: React.ReactNode;
  requiredRole?: string;
}

export function ProtectedRoute({ children, requiredRole }: Props) {
  const { ready, authenticated, user } = useAuth();

  if (!ready) {
    return (
      <div className="flex h-screen items-center justify-center">
        <span className="text-muted-foreground text-sm">Loading...</span>
      </div>
    );
  }

  if (!authenticated) return <Navigate to="/signin" replace />;

  if (requiredRole && !user?.roles.includes(requiredRole)) {
    return <Navigate to="/forbidden" replace />;
  }

  return <>{children}</>;
}
