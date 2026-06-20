import { useNavigate } from "react-router-dom";
import { GraduationCap, PlayCircle } from "lucide-react";
import { useMyLearning } from "@/hooks/useLearning";

function ProgressBar({ pct }: { pct: number }) {
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-secondary">
      <div className="h-full rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} />
    </div>
  );
}

export function MyLearningPage() {
  const { data: courses } = useMyLearning();
  const navigate = useNavigate();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">My Learning</h1>
        <p className="text-muted-foreground">Courses assigned to you.</p>
      </div>

      {courses && courses.length === 0 ? (
        <div className="flex flex-col items-center justify-center rounded-2xl border border-dashed border-border py-16 text-center">
          <GraduationCap className="h-8 w-8 text-muted-foreground" />
          <p className="mt-3 text-sm text-muted-foreground">No courses assigned yet.</p>
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {courses?.map((c) => {
          const pct = c.enrollment?.progress_pct ?? 0;
          const done = c.enrollment?.status === "completed";
          return (
            <button
              key={c.id}
              onClick={() => navigate(`/learn/${c.id}`)}
              className="flex flex-col rounded-xl border border-border bg-card p-5 text-left transition hover:border-primary/50 hover:shadow-sm"
            >
              <h3 className="font-semibold">{c.title}</h3>
              <p className="mt-1 line-clamp-2 flex-1 text-sm text-muted-foreground">
                {c.description}
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
        })}
      </div>
    </div>
  );
}
