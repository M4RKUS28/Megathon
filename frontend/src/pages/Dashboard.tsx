import { Link } from "react-router-dom";
import { ArrowUpRight, GraduationCap, Layers, Users } from "lucide-react";
import { useMe } from "@/hooks/useMe";
import { useBrand } from "@/theme/ThemeProvider";

export function DashboardPage() {
  const { data: me } = useMe();
  const { companyName } = useBrand();
  const role = me?.role ?? "user";
  const isStaff = role === "admin" || role === "course_creator";

  const stats = [
    { label: "Published courses", value: "—", icon: Layers },
    { label: "Active learners", value: "—", icon: Users },
    { label: "Avg. completion", value: "—", icon: GraduationCap },
  ];

  return (
    <div className="space-y-8">
      <div>
        <p className="font-mono text-xs uppercase tracking-[0.2em] text-primary">{companyName}</p>
        <h1 className="mt-2 text-3xl font-bold tracking-tight">
          Welcome back, {me?.display_name?.split(" ")[0] || "there"}.
        </h1>
        <p className="mt-1 text-muted-foreground">
          {isStaff
            ? "Generate, brand and assign training — then watch it land."
            : "Pick up your assigned courses and keep your progress moving."}
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        {stats.map(({ label, value, icon: Icon }) => (
          <div key={label} className="rounded-xl border border-border bg-card p-5">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">{label}</p>
              <Icon className="h-4 w-4 text-primary" />
            </div>
            <p className="mt-3 text-3xl font-bold">{value}</p>
          </div>
        ))}
      </div>

      <div className="rounded-2xl border border-border bg-gradient-to-br from-primary/10 to-transparent p-8">
        <h2 className="text-xl font-semibold">
          {isStaff ? "Spin up a course in minutes" : "Your learning, personalized"}
        </h2>
        <p className="mt-2 max-w-xl text-sm text-muted-foreground">
          {isStaff
            ? "Describe what people need to know. Coursive drafts the concept, generates a branded interactive course, and hosts it for you."
            : "Assigned courses appear here once your team publishes them. Mandatory training is flagged so you never miss it."}
        </p>
        <Link
          to={isStaff ? "/courses?new=1" : "/learn"}
          className="mt-5 inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition hover:opacity-90"
        >
          {isStaff ? "Create a course" : "Go to my learning"}
          <ArrowUpRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}
