import { Link } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";
import { useFiles } from "@/hooks/useFiles";

export function DashboardPage() {
  const { user } = useAuth();
  const { data: files } = useFiles();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Dashboard</h1>
        <p className="text-muted-foreground">Hello, {user?.username}</p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="rounded-xl border border-border bg-card p-5 text-card-foreground shadow-sm">
          <p className="text-sm text-muted-foreground">Total Files</p>
          <p className="text-3xl font-bold">{files?.length ?? "—"}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-5 text-card-foreground shadow-sm">
          <p className="text-sm text-muted-foreground">User ID</p>
          <p className="truncate font-mono text-xs">{user?.id}</p>
        </div>
        <div className="rounded-xl border border-border bg-card p-5 text-card-foreground shadow-sm">
          <p className="text-sm text-muted-foreground">Roles</p>
          <p className="text-sm">{user?.roles.join(", ") || "none"}</p>
        </div>
      </div>

      <Link
        to="/files"
        className="inline-flex items-center rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground shadow hover:bg-primary/90"
      >
        Manage Files
      </Link>
    </div>
  );
}
