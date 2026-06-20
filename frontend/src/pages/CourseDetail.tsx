import { useEffect, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { ArrowLeft, Check, Loader2, MousePointerClick, Sparkles, X } from "lucide-react";
import {
  useAcceptEdit,
  useCourse,
  useCourseEdits,
  useCourseJobs,
  useCreateEdit,
  useGenerateCourse,
  useRejectEdit,
} from "@/hooks/useCourses";
import { StatusBadge } from "@/components/StatusBadge";
import { CourseAssignPanel } from "@/components/CourseAssignPanel";
import type { CourseConceptChapter, GenerationJobRecord } from "@/lib/api";

const INTERACTIVE = new Set([
  "dialogue",
  "dragdrop",
  "ordering",
  "hotspot",
  "flipcards",
  "chart",
  "image",
  "video",
  "audio",
]);

function chapterBlocks(ch: CourseConceptChapter) {
  if (ch.pages && ch.pages.length) return ch.pages.flatMap((p) => p.blocks ?? []);
  return ch.blocks ?? [];
}

function ConceptPreview({ chapters }: { chapters: CourseConceptChapter[] }) {
  return (
    <ol className="space-y-3">
      {chapters.map((ch, i) => {
        const blocks = chapterBlocks(ch);
        const pages = ch.pages?.length ?? 1;
        const kinds = [...new Set(blocks.map((b) => b.type).filter((t) => INTERACTIVE.has(t)))];
        return (
          <li key={ch.id} className="rounded-xl border border-border bg-card p-4">
            <div className="flex items-center gap-2">
              <span className="grid h-6 w-6 place-items-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
                {i + 1}
              </span>
              <h4 className="font-semibold">{ch.title}</h4>
            </div>
            {ch.objective ? (
              <p className="mt-1.5 text-sm text-muted-foreground">{ch.objective}</p>
            ) : null}
            <p className="mt-2 text-xs text-muted-foreground">
              {pages} page(s) · {blocks.length} blocks · {ch.quiz.length} quiz Q ·{" "}
              gate {ch.passingScore ?? 80}%
            </p>
            {kinds.length ? (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {kinds.map((k) => (
                  <span
                    key={k}
                    className="rounded-full bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary"
                  >
                    {k}
                  </span>
                ))}
              </div>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

function LiveProgress({ jobs }: { jobs?: GenerationJobRecord[] }) {
  if (!jobs || jobs.length === 0) return null;
  const active =
    jobs.find((j) => j.status === "running") ??
    [...jobs].sort((a, b) => b.created_at.localeCompare(a.created_at))[0];
  const p = active?.progress;
  if (!active || active.status !== "running" || !p) return null;
  return (
    <div className="rounded-xl border border-border bg-card p-5">
      <div className="flex items-center gap-2 text-sm font-medium">
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
        {p.message}
      </div>
      <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-secondary">
        <div
          className="h-full rounded-full bg-primary transition-all duration-500"
          style={{ width: `${p.pct}%` }}
        />
      </div>
      {p.steps && p.steps.length > 1 ? (
        <ul className="mt-3 space-y-1">
          {p.steps.slice(-5).map((s, i) => (
            <li key={i} className="text-xs text-muted-foreground">
              {s.message}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

export function CourseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const iframeRef = useRef<HTMLIFrameElement>(null);

  const busyStatuses = new Set(["draft", "generating"]);
  const { data: course } = useCourse(id, true);
  const { data: edits } = useCourseEdits(id, true);
  const editBusy = edits?.some((e) => ["queued", "running"].includes(e.status)) ?? false;
  const poll = (course ? busyStatuses.has(course.status) : true) || editBusy;
  useCourse(id, poll); // keep polling cadence while busy
  const { data: jobs } = useCourseJobs(id, poll);

  const generate = useGenerateCourse(id!);
  const createEdit = useCreateEdit(id!);
  const acceptEdit = useAcceptEdit(id!);
  const rejectEdit = useRejectEdit(id!);

  const [selectMode, setSelectMode] = useState(false);
  const [selected, setSelected] = useState<{ blockId: string; text: string } | null>(null);
  const [prompt, setPrompt] = useState("");

  useEffect(() => {
    function onMessage(e: MessageEvent) {
      const d = e.data;
      if (d && typeof d === "object" && d.type === "coursive:element-selected") {
        setSelected({ blockId: d.blockId, text: d.text });
        setSelectMode(false);
      }
    }
    window.addEventListener("message", onMessage);
    return () => window.removeEventListener("message", onMessage);
  }, []);

  const toggleSelect = () => {
    const next = !selectMode;
    setSelectMode(next);
    iframeRef.current?.contentWindow?.postMessage(
      { type: "coursive:select-mode", enabled: next },
      "*",
    );
  };

  const submitEdit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    createEdit.mutate(
      {
        prompt: prompt.trim(),
        target_selector: selected?.blockId,
        target_text: selected?.text,
      },
      {
        onSuccess: () => {
          setPrompt("");
          setSelected(null);
        },
      },
    );
  };

  if (!course) {
    return (
      <div className="flex h-64 items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const isReady = course.status === "ready" || course.status === "published";

  return (
    <div className="space-y-8">
      <div>
        <Link
          to="/courses"
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" /> Courses
        </Link>
        <div className="mt-2 flex items-center gap-3">
          <h1 className="text-2xl font-bold tracking-tight">{course.title}</h1>
          <StatusBadge status={course.status} />
          <span className="text-xs text-muted-foreground">v{course.version}</span>
        </div>
        <p className="mt-1 text-muted-foreground">{course.description}</p>
      </div>

      <LiveProgress jobs={jobs} />

      {course.status === "draft" && !jobs?.some((j) => j.status === "running" && j.progress) ? (
        <div className="flex items-center gap-2 rounded-xl border border-border bg-card p-5 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" /> Devin is drafting the course concept…
        </div>
      ) : null}

      {course.status === "failed" ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">
          Generation failed. Check the job log below.
        </div>
      ) : null}

      {/* Concept review + generate */}
      {course.concept && !isReady ? (
        <section className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Concept</h2>
            <button
              onClick={() => generate.mutate()}
              disabled={generate.isPending || course.status === "generating"}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
            >
              {generate.isPending || course.status === "generating" ? (
                <Loader2 className="h-4 w-4 animate-spin" />
              ) : (
                <Sparkles className="h-4 w-4" />
              )}
              {course.status === "generating" ? "Building…" : "Generate course"}
            </button>
          </div>
          <ConceptPreview chapters={course.concept.chapters} />
        </section>
      ) : null}

      {/* Built course preview + edit-loop */}
      {isReady && course.host_url ? (
        <section className="grid gap-6 lg:grid-cols-[1fr_340px]">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Preview</h2>
              <button
                onClick={toggleSelect}
                className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium ${
                  selectMode
                    ? "border-primary bg-primary/10 text-primary"
                    : "border-border text-muted-foreground hover:text-foreground"
                }`}
              >
                <MousePointerClick className="h-4 w-4" />
                {selectMode ? "Click an element…" : "Select element to edit"}
              </button>
            </div>
            <iframe
              ref={iframeRef}
              src={course.host_url}
              title={course.title}
              className="h-[640px] w-full rounded-xl border border-border bg-white"
            />
          </div>

          <div className="space-y-5">
            <div className="rounded-xl border border-border bg-card p-5">
              <h3 className="font-semibold">Edit with Devin</h3>
              {selected ? (
                <div className="mt-3 rounded-lg bg-secondary/60 p-3 text-xs">
                  <span className="font-medium">Selected:</span> {selected.text.slice(0, 120)}
                </div>
              ) : (
                <p className="mt-2 text-sm text-muted-foreground">
                  Optionally select an element, then describe the change.
                </p>
              )}
              <form onSubmit={submitEdit} className="mt-3 space-y-2">
                <textarea
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
                  rows={3}
                  placeholder="e.g. Make chapter 1 friendlier and add an example"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                />
                <button
                  type="submit"
                  disabled={createEdit.isPending}
                  className="inline-flex w-full items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
                >
                  {createEdit.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Sparkles className="h-4 w-4" />
                  )}
                  Request edit
                </button>
              </form>
            </div>

            <div className="space-y-2">
              <h3 className="text-sm font-semibold text-muted-foreground">Edit requests</h3>
              {edits?.map((ed) => (
                <div key={ed.id} className="rounded-lg border border-border bg-card p-3 text-sm">
                  <p className="font-medium">{ed.prompt}</p>
                  <p className="mt-1 text-xs text-muted-foreground">Status: {ed.status}</p>
                  {ed.status === "preview_ready" ? (
                    <div className="mt-2 flex items-center gap-2">
                      {ed.preview_url ? (
                        <a
                          href={ed.preview_url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs text-primary underline"
                        >
                          Preview
                        </a>
                      ) : null}
                      <button
                        onClick={() => acceptEdit.mutate(ed.id)}
                        className="ml-auto inline-flex items-center gap-1 rounded-md bg-emerald-600 px-2 py-1 text-xs font-medium text-white"
                      >
                        <Check className="h-3 w-3" /> Accept
                      </button>
                      <button
                        onClick={() => rejectEdit.mutate(ed.id)}
                        className="inline-flex items-center gap-1 rounded-md border border-border px-2 py-1 text-xs"
                      >
                        <X className="h-3 w-3" /> Reject
                      </button>
                    </div>
                  ) : null}
                </div>
              ))}
              {edits && edits.length === 0 ? (
                <p className="text-xs text-muted-foreground">No edits yet.</p>
              ) : null}
            </div>
          </div>
        </section>
      ) : null}

      {/* Assign & report */}
      {isReady ? (
        <div className="space-y-3">
          <h2 className="text-lg font-semibold">Assign & track</h2>
          <CourseAssignPanel courseId={course.id} />
        </div>
      ) : null}

      {/* Job log */}
      <section>
        <h2 className="text-sm font-semibold text-muted-foreground">Generation log</h2>
        <div className="mt-3 space-y-1.5">
          {jobs?.map((j) => (
            <div
              key={j.id}
              className="flex items-center gap-3 rounded-lg border border-border bg-card px-3 py-2 text-sm"
            >
              <span className="font-mono text-xs uppercase text-muted-foreground">{j.type}</span>
              <StatusBadge status={j.status} />
              {j.devin_session_id ? (
                <span className="font-mono text-xs text-muted-foreground">
                  {j.devin_session_id}
                </span>
              ) : null}
              {j.error ? <span className="text-xs text-red-600">{j.error}</span> : null}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
