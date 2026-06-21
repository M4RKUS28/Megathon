import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { BookOpen, FileText, Loader2, Plus, Sparkles, Target, Users } from "lucide-react";
import { useCourses, useCreateCourse } from "@/hooks/useCourses";
import { StatusBadge } from "@/components/StatusBadge";
import { apiErrorMessage } from "@/lib/api";

const inputCls =
  "w-full rounded-lg border border-border bg-muted shadow-neu-inset px-3 py-2 text-sm outline-none focus:border-primary";

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
  const createError = create.isError
    ? apiErrorMessage(create.error, "Course creation failed")
    : null;

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
          className="inline-flex items-center gap-1.5 rounded-lg shadow-neu-sm bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
        >
          <Plus className="h-4 w-4" /> New course
        </button>
      </div>

      {open ? (
        <form onSubmit={submit} className="rounded-2xl border border-border bg-card shadow-neu p-6">
          {/* Step indicator */}
          <div className="mb-6 flex items-center justify-center gap-2">
            {[
              { num: 1, label: "Basic Info", icon: FileText },
              { num: 2, label: "Goals", icon: Target },
              { num: 3, label: "Topics", icon: BookOpen },
            ].map(({ num, label, icon: Icon }, idx) => (
              <div key={num} className="flex items-center gap-2">
                <div className="flex items-center gap-1.5 rounded-full bg-primary/10 px-3 py-1">
                  <Icon className="h-3.5 w-3.5 text-primary" />
                  <span className="text-xs font-medium text-primary">{label}</span>
                </div>
                {idx < 2 && <div className="h-px w-6 bg-border" />}
              </div>
            ))}
          </div>

          <div className="space-y-5">
            {/* Section 1: Basic Info */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <FileText className="h-4 w-4 text-primary" />
                <h3 className="text-sm font-semibold">Basic Information</h3>
              </div>
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
            </div>

            {/* Section 2: Goals */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <Target className="h-4 w-4 text-primary" />
                <h3 className="text-sm font-semibold">Learning Goals</h3>
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
            </div>

            {/* Section 3: Topics */}
            <div className="space-y-3">
              <div className="flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-primary" />
                <h3 className="text-sm font-semibold">Key Topics</h3>
              </div>
              <label className="block">
                <span className="text-sm font-medium">Key topics (comma-separated)</span>
                <input
                  className={`mt-1.5 ${inputCls}`}
                  placeholder="Phishing, Passwords, Data handling"
                  value={topics}
                  onChange={(e) => setTopics(e.target.value)}
                />
              </label>
            </div>
          </div>

          {createError ? <p className="mt-4 text-sm text-destructive">{createError}</p> : null}
          <div className="mt-6 flex items-center gap-3">
            <button
              type="submit"
              disabled={create.isPending}
              className="inline-flex items-center gap-2 rounded-lg shadow-neu-sm bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
            >
              {create.isPending ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              Draft with Devin
            </button>
            <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-medium text-primary">AI-powered</span>
          </div>
        </form>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {courses?.map((c) => (
          <button
            key={c.id}
            onClick={() => navigate(`/courses/${c.id}`)}
            className="group rounded-xl border border-border bg-card shadow-neu-sm p-5 text-left transition hover:border-primary/50 hover:shadow-neu"
          >
            <div className="flex items-center justify-between">
              <StatusBadge status={c.status} />
              <span className="text-xs text-muted-foreground">v{c.version}</span>
            </div>
            <h3 className="mt-3 font-semibold group-hover:text-primary transition-colors">{c.title}</h3>
            <p className="mt-1 line-clamp-2 text-sm text-muted-foreground">
              {c.description || "No description"}
            </p>
            <div className="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
              <Users className="h-3 w-3" />
              <span>Course</span>
            </div>
          </button>
        ))}
        {courses && courses.length === 0 && !open ? (
          <div className="col-span-full rounded-2xl border border-dashed border-border bg-card/50 p-10 text-center">
            <BookOpen className="mx-auto h-10 w-10 text-muted-foreground" />
            <h3 className="mt-4 text-lg font-semibold">No courses yet</h3>
            <p className="mx-auto mt-2 max-w-sm text-sm text-muted-foreground">
              Create your first AI-powered course by clicking the "New course" button above.
            </p>
          </div>
        ) : null}
      </div>
    </div>
  );
}
