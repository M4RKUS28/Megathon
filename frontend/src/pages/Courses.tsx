import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Loader2, Plus, Sparkles } from "lucide-react";
import { useCourses, useCreateCourse } from "@/hooks/useCourses";
import { StatusBadge } from "@/components/StatusBadge";

const inputCls =
  "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary";

export function CoursesPage() {
  const { data: courses } = useCourses();
  const create = useCreateCourse();
  const navigate = useNavigate();
  // Opening from the dashboard CTA (/courses?new=1) jumps straight into the form.
  const [searchParams] = useSearchParams();
  const [open, setOpen] = useState(() => searchParams.get("new") !== null);
  const [title, setTitle] = useState("");
  const [goals, setGoals] = useState("");
  const [audience, setAudience] = useState("new employees");
  const [topics, setTopics] = useState("");

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;
    create.mutate(
      {
        title: title.trim(),
        description: goals.trim(),
        brief: {
          audience: audience.trim() || "new employees",
          goals: goals.trim(),
          tone: "friendly and professional",
          duration: "4-6 chapters",
          topics: topics.split(",").map((t) => t.trim()).filter(Boolean),
        },
      },
      { onSuccess: (res) => navigate(`/courses/${res.data.id}`) },
    );
  };

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Courses</h1>
          <p className="text-muted-foreground">
            Describe a course; Devin drafts the concept and builds an interactive Vite course.
          </p>
        </div>
        <button
          onClick={() => setOpen((o) => !o)}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          <Plus className="h-4 w-4" /> New course
        </button>
      </div>

      {open ? (
        <form onSubmit={submit} className="space-y-4 rounded-2xl border border-border bg-card p-6">
          <div className="grid gap-4 sm:grid-cols-2">
            <label className="block">
              <span className="text-sm font-medium">Title</span>
              <input
                className={`mt-1.5 ${inputCls}`}
                placeholder="Security & Compliance Onboarding"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
              />
            </label>
            <label className="block">
              <span className="text-sm font-medium">Audience</span>
              <input
                className={`mt-1.5 ${inputCls}`}
                value={audience}
                onChange={(e) => setAudience(e.target.value)}
              />
            </label>
          </div>
          <label className="block">
            <span className="text-sm font-medium">Goals</span>
            <textarea
              className={`mt-1.5 ${inputCls}`}
              rows={2}
              placeholder="What should learners be able to do after this course?"
              value={goals}
              onChange={(e) => setGoals(e.target.value)}
            />
          </label>
          <label className="block">
            <span className="text-sm font-medium">Key topics (comma-separated)</span>
            <input
              className={`mt-1.5 ${inputCls}`}
              placeholder="Phishing, Passwords, Data handling"
              value={topics}
              onChange={(e) => setTopics(e.target.value)}
            />
          </label>
          <button
            type="submit"
            disabled={create.isPending}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
          >
            {create.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            Draft with Devin
          </button>
        </form>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {courses?.map((c) => (
          <button
            key={c.id}
            onClick={() => navigate(`/courses/${c.id}`)}
            className="rounded-xl border border-border bg-card p-5 text-left transition hover:border-primary/50 hover:shadow-sm"
          >
            <div className="flex items-center justify-between">
              <StatusBadge status={c.status} />
              <span className="text-xs text-muted-foreground">v{c.version}</span>
            </div>
            <h3 className="mt-3 font-semibold">{c.title}</h3>
            <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
              {c.description || "No description"}
            </p>
          </button>
        ))}
        {courses && courses.length === 0 ? (
          <p className="text-sm text-muted-foreground">No courses yet. Create your first one.</p>
        ) : null}
      </div>
    </div>
  );
}
