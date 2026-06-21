import { AlertCircle, BarChart3, BookOpen, CheckCircle2, Loader2, Users } from "lucide-react";
import { useManagerDashboard } from "@/hooks/useCourses";
import { useBrand } from "@/theme/ThemeProvider";

const statConfig = [
  { key: "team_size", label: "Team size", icon: Users, accent: "from-blue-500/20 to-blue-500/5" },
  { key: "assigned_courses", label: "Assigned", icon: BookOpen, accent: "from-violet-500/20 to-violet-500/5" },
  { key: "completed_courses", label: "Completed", icon: CheckCircle2, accent: "from-emerald-500/20 to-emerald-500/5" },
  { key: "open_courses", label: "Open", icon: AlertCircle, accent: "from-amber-500/20 to-amber-500/5" },
  { key: "compliance_pct", label: "Compliance", icon: BarChart3, accent: "from-primary/20 to-primary/5" },
] as const;

function ComplianceBar({ pct }: { pct: number }) {
  const color =
    pct >= 80 ? "bg-emerald-500" : pct >= 50 ? "bg-amber-500" : "bg-red-500";
  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-secondary">
        <div className={`h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
      <span>{pct}%</span>
    </div>
  );
}

export function ManagerDashboardPage() {
  const { data, isLoading } = useManagerDashboard();
  const { companyName } = useBrand();

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
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-primary">{companyName}</p>
        <h1 className="mt-2 text-2xl font-bold tracking-tight">Team dashboard</h1>
        <p className="mt-1 text-muted-foreground">
          Progress and compliance across your {data.team_size} direct report(s).
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {statConfig.map(({ key, label, icon: Icon, accent }) => {
          const raw = data[key];
          const value = key === "compliance_pct" ? `${raw}%` : raw;
          return (
            <div key={key} className="relative overflow-hidden rounded-xl border border-border bg-card p-4 shadow-neu-sm">
              <div className={`absolute inset-0 bg-gradient-to-br ${accent} pointer-events-none`} />
              <div className="relative">
                <div className="flex items-center justify-between">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">{label}</p>
                  <div className="rounded-lg bg-primary/10 p-1.5">
                    <Icon className="h-3.5 w-3.5 text-primary" />
                  </div>
                </div>
                <p className="mt-1 text-2xl font-bold">{value}</p>
              </div>
            </div>
          );
        })}
      </div>

      <div className="overflow-x-auto rounded-xl border border-border shadow-neu">
        <table className="w-full text-sm">
          <thead className="bg-secondary/60 text-left text-xs uppercase text-muted-foreground">
            <tr>
              <th className="px-4 py-3">Member</th>
              <th className="px-4 py-3">Assigned</th>
              <th className="px-4 py-3">Completed</th>
              <th className="px-4 py-3">In progress</th>
              <th className="px-4 py-3">Not started</th>
              <th className="px-4 py-3">Avg score</th>
              <th className="px-4 py-3">Compliance</th>
            </tr>
          </thead>
          <tbody>
            {data.members.map((m, idx) => (
              <tr
                key={m.user_id}
                className={`border-t border-border transition-colors hover:bg-secondary/30 ${
                  idx % 2 === 1 ? "bg-secondary/10" : ""
                }`}
              >
                <td className="px-4 py-3">
                  <p className="font-medium">{m.display_name}</p>
                  <p className="text-xs text-muted-foreground">{m.email}</p>
                </td>
                <td className="px-4 py-3">{m.assigned}</td>
                <td className="px-4 py-3">
                  <span className="inline-flex items-center gap-1">
                    <CheckCircle2 className="h-3 w-3 text-emerald-400" />
                    {m.completed}
                  </span>
                </td>
                <td className="px-4 py-3">{m.in_progress}</td>
                <td className="px-4 py-3">{m.not_started}</td>
                <td className="px-4 py-3">
                  {m.avg_score != null ? `${Math.round(m.avg_score)}%` : "\u2014"}
                </td>
                <td className="px-4 py-3">
                  <ComplianceBar pct={m.compliance_pct} />
                </td>
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
