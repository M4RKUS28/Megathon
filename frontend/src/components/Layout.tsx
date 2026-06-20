import { Link, Outlet } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";

export function Layout() {
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
          <nav className="flex items-center gap-6">
            <Link to="/dashboard" className="font-semibold text-primary">
              App
            </Link>
            <Link to="/files" className="text-sm text-muted-foreground hover:text-foreground">
              Files
            </Link>
          </nav>
          <div className="flex items-center gap-3">
            <span className="text-sm text-muted-foreground">{user?.email}</span>
            <button
              onClick={() => logout()}
              className="rounded-md bg-secondary px-3 py-1.5 text-sm text-secondary-foreground hover:bg-secondary/80"
            >
              Sign out
            </button>
          </div>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-8">
        <Outlet />
      </main>
    </div>
  );
}
