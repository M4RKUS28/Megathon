import { Link, useNavigate } from "react-router-dom";
import {
  ArrowUpRight,
  BookOpen,
  CheckCircle2,
  Clock,
  GraduationCap,
  Layers,
  PlayCircle,
  Target,
  Trophy,
  Users,
} from "lucide-react";
import { useMe } from "@/hooks/useMe";
import { useBrand } from "@/theme/ThemeProvider";
import { useMyLearning } from "@/hooks/useLearning";
import type { LearningCourse } from "@/lib/api";

function ProgressRing({ pct, size = 48 }: { pct: number; size?: number }) {
  const r = (size - 6) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - (pct / 100) * circ;
  return (
    <svg width={size} height={size} className="-rotate-90">
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        strokeWidth={5}
        className="stroke-secondary"
      />
      <circle
        cx={size / 2}
        cy={size / 2}
        r={r}
        fill="none"
        strokeWidth={5}
        strokeLinecap="round"
        strokeDasharray={circ}
        strokeDashoffset={offset}
        className="stroke-primary transition-all"
      />
    </svg>
  );
}

function ProgressBar({ pct }: { pct: number }) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-secondary">
      <div
        className="h-full rounded-full bg-primary transition-all"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function ContinueLearningCard({ course }: { course: LearningCourse }) {
  const pct = course.enrollment?.progress_pct ?? 0;
  const navigate = useNavigate();
  return (
    <button
      onClick={() => navigate(`/learn/${course.id}`)}
      className="flex w-full items-center gap-5 rounded-2xl border border-border bg-card p-5 text-left transition hover:border-primary/50 hover:shadow-sm"
    >
      <ProgressRing pct={pct} size={56} />
      <div className="min-w-0 flex-1">
        <p className="text-xs font-medium uppercase tracking-wide text-primary">Continue where you left off</p>
        <h3 className="mt-1 truncate text-lg font-semibold">{course.title}</h3>
        <p className="mt-0.5 text-sm text-muted-foreground">{pct}% complete</p>
      </div>
      <PlayCircle className="h-8 w-8 shrink-0 text-primary" />
    </button>
  );
}

function CourseCard({ course }: { course: LearningCourse }) {
  const pct = course.enrollment?.progress_pct ?? 0;
  const done = course.enrollment?.status === "completed";
  const navigate = useNavigate();
  return (
    <button
      onClick={() => navigate(`/learn/${course.id}`)}
      className="flex flex-col rounded-xl border border-border bg-card p-5 text-left transition hover:border-primary/50 hover:shadow-sm"
    >
      <h3 className="font-semibold">{course.title}</h3>
      <p className="mt-1 line-clamp-2 flex-1 text-sm text-muted-foreground">
        {course.description}
      </p>
      <div className="mt-4 space-y-1.5">
        <ProgressBar pct={pct} />
        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>{done ? "Completed" : pct > 0 ? `${pct}% complete` : "Not started"}</span>
          <span className="inline-flex items-center gap-1 text-primary">
            <PlayCircle className="h-3.5 w-3.5" />
            {pct > 0 && !done ? "Resume" : done ? "Review" : "Start"}
          </span>
        </div>
      </div>
    </button>
  );
}

function EmployeeDashboard({ firstName }: { firstName: string }) {
  const { companyName } = useBrand();
  const { data: courses } = useMyLearning();

  const total = courses?.length ?? 0;
  const completed = courses?.filter((c) => c.enrollment?.status === "completed").length ?? 0;
  const inProgress = courses?.filter(
    (c) => c.enrollment && c.enrollment.progress_pct > 0 && c.enrollment.status !== "completed",
  ).length ?? 0;

  const overallPct =
    total > 0
      ? Math.round(courses!.reduce((sum, c) => sum + (c.enrollment?.progress_pct ?? 0), 0) / total)
      : 0;

  // Course the user was most recently working on (in progress, highest %)
  const continueCourse = courses
    ?.filter((c) => c.enrollment && c.enrollment.progress_pct > 0 && c.enrollment.status !== "completed")
    .sort((a, b) => (b.enrollment?.progress_pct ?? 0) - (a.enrollment?.progress_pct ?? 0))[0];

  const pendingCourses = courses?.filter(
    (c) => !c.enrollment || c.enrollment.progress_pct === 0,
  ) ?? [];

  const completedCourses = courses?.filter((c) => c.enrollment?.status === "completed") ?? [];

  const stats = [
    { label: "Assigned", value: total, icon: BookOpen },
    { label: "In Progress", value: inProgress, icon: Clock },
    { label: "Completed", value: completed, icon: CheckCircle2 },
  ];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-end justify-between">
        <div>
          <p className="font-mono text-xs uppercase tracking-[0.2em] text-primary">
            {companyName}
          </p>
          <h1 className="mt-2 text-3xl font-bold tracking-tight">
            Welcome back, {firstName}.
          </h1>
          <p className="mt-1 text-muted-foreground">
            Here's your learning progress at a glance.
          </p>
        </div>
        {total > 0 && (
          <div className="hidden items-center gap-3 sm:flex">
            <ProgressRing pct={overallPct} size={44} />
            <div className="text-right">
              <p className="text-2xl font-bold">{overallPct}%</p>
              <p className="text-xs text-muted-foreground">Overall</p>
            </div>
          </div>
        )}
      </div>

      {/* Stats row */}
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

      {/* Continue learning */}
      {continueCourse && <ContinueLearningCard course={continueCourse} />}

      {/* Empty state */}
      {total === 0 && (
        <div className="rounded-2xl border border-dashed border-border bg-gradient-to-br from-primary/5 to-transparent p-10 text-center">
          <Target className="mx-auto h-10 w-10 text-muted-foreground" />
          <h2 className="mt-4 text-xl font-semibold">No courses assigned yet</h2>
          <p className="mx-auto mt-2 max-w-md text-sm text-muted-foreground">
            Your team hasn't published any training for you yet. When they do, assigned courses will
            appear here so you can start learning right away.
          </p>
        </div>
      )}

      {/* Pending courses */}
      {pendingCourses.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Ready to start</h2>
            <span className="text-sm text-muted-foreground">{pendingCourses.length} course{pendingCourses.length > 1 ? "s" : ""}</span>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {pendingCourses.map((c) => (
              <CourseCard key={c.id} course={c} />
            ))}
          </div>
        </div>
      )}

      {/* Completed courses */}
      {completedCourses.length > 0 && (
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-lg font-semibold">
              <Trophy className="h-5 w-5 text-primary" />
              Completed
            </h2>
            <span className="text-sm text-muted-foreground">{completedCourses.length} course{completedCourses.length > 1 ? "s" : ""}</span>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {completedCourses.map((c) => (
              <CourseCard key={c.id} course={c} />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StaffDashboard({ firstName }: { firstName: string }) {
  const { companyName } = useBrand();

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
          Welcome back, {firstName}.
        </h1>
        <p className="mt-1 text-muted-foreground">
          Generate, brand and assign training — then watch it land.
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
        <h2 className="text-xl font-semibold">Spin up a course in minutes</h2>
        <p className="mt-2 max-w-xl text-sm text-muted-foreground">
          Describe what people need to know. Coursive drafts the concept, generates a branded
          interactive course, and hosts it for you.
        </p>
        <Link
          to="/courses?new=1"
          className="mt-5 inline-flex items-center gap-2 rounded-full bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition hover:opacity-90"
        >
          Create a course
          <ArrowUpRight className="h-4 w-4" />
        </Link>
      </div>
    </div>
  );
}

export function DashboardPage() {
  const { data: me } = useMe();
  const role = me?.role ?? "user";
  const isStaff = role === "admin" || role === "course_creator";
  const firstName = me?.display_name?.split(" ")[0] || "there";

  if (isStaff) {
    return <StaffDashboard firstName={firstName} />;
  }
  return <EmployeeDashboard firstName={firstName} />;
}
