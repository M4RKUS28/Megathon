import { Loader2 } from "lucide-react";
import { useManagerDashboard } from "@/hooks/useCourses";

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
      <p className="mt-1 text-2xl font-bold">{value}</p>
    </div>
  );
}

export function ManagerDashboardPage() {
  const { data, isLoading } = useManagerDashboard();

  if (isLoading) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!data) {
    return <p className="text-muted-foreground">No team data available.</p>;
  }

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Team dashboard</h1>
        <p className="mt-1 text-muted-foreground">
          Progress and compliance across your {data.team_size} direct report(s).
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Stat label="Team size" value={data.team_size} />
        <Stat label="Assigned" value={data.assigned_courses} />
        <Stat label="Completed" value={data.completed_courses} />
        <Stat label="Open" value={data.open_courses} />
        <Stat label="Compliance" value={`${data.compliance_pct}%`} />
      </div>

      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="w-full text-sm">
          <thead className="bg-secondary/50 text-left text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-4 py-2">Member</th>
              <th className="px-4 py-2">Assigned</th>
              <th className="px-4 py-2">Completed</th>
              <th className="px-4 py-2">In progress</th>
              <th className="px-4 py-2">Not started</th>
              <th className="px-4 py-2">Avg score</th>
              <th className="px-4 py-2">Compliance</th>
            </tr>
          </thead>
          <tbody>
            {data.members.map((m) => (
              <tr key={m.user_id} className="border-t border-border">
                <td className="px-4 py-2">
                  <p className="font-medium">{m.display_name}</p>
                  <p className="text-xs text-muted-foreground">{m.email}</p>
                </td>
                <td className="px-4 py-2">{m.assigned}</td>
                <td className="px-4 py-2">{m.completed}</td>
                <td className="px-4 py-2">{m.in_progress}</td>
                <td className="px-4 py-2">{m.not_started}</td>
                <td className="px-4 py-2">
                  {m.avg_score != null ? `${Math.round(m.avg_score)}%` : "—"}
                </td>
                <td className="px-4 py-2">{m.compliance_pct}%</td>
              </tr>
            ))}
            {data.members.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-4 py-6 text-center text-muted-foreground">
                  No direct reports yet.
                </td>
              </tr>
            ) : null}
          </tbody>
        </table>
      </div>
    </div>
  );
}
