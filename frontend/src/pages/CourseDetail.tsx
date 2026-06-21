import { useEffect, useMemo, useRef, useState } from "react";
import { useParams, Link } from "react-router-dom";
import {
  ArrowLeft,
  Bot,
  Check,
  ChevronDown,
  ChevronUp,
  ExternalLink,
  Loader2,
  Maximize,
  Minimize,
  MousePointerClick,
  Plus,
  Sparkles,
  Trash2,
  X,
  Zap,
} from "lucide-react";
import {
  useAcceptEdit,
  useApprovePlan,
  useCourse,
  useCourseEdits,
  useCourseJobs,
  useCreateEdit,
  useRejectEdit,
} from "@/hooks/useCourses";
import { useFullscreen } from "@/hooks/useFullscreen";
import { StatusBadge } from "@/components/StatusBadge";
import { CourseAssignPanel } from "@/components/CourseAssignPanel";
import { PipelineMonitor } from "@/components/PipelineMonitor";
import type { CoursePlan, PlanChapter } from "@/lib/api";

let _cid = 0;
function newChapterId() {
  _cid += 1;
  return `ch_new_${Date.now()}_${_cid}`;
}

const sumMinutes = (chapters: PlanChapter[]) =>
  chapters.reduce((s, c) => s + (c.estimated_minutes || 0), 0);

// Spread a target total duration across chapters, keeping their relative
// weights and making the per-chapter minutes add up exactly to the target.
function rescaleChapterMinutes(chapters: PlanChapter[], target: number): PlanChapter[] {
  const n = chapters.length;
  if (n === 0) return chapters;
  const safeTarget = Math.max(0, Math.round(target));
  const current = sumMinutes(chapters);
  const next =
    current <= 0
      ? chapters.map((c) => ({ ...c, estimated_minutes: Math.floor(safeTarget / n) }))
      : chapters.map((c) => ({
          ...c,
          estimated_minutes: Math.max(
            1,
            Math.round(((c.estimated_minutes || 0) / current) * safeTarget),
          ),
        }));
  const drift = safeTarget - sumMinutes(next);
  if (drift !== 0) {
    let maxIdx = 0;
    for (let k = 1; k < next.length; k++) {
      if (next[k].estimated_minutes > next[maxIdx].estimated_minutes) maxIdx = k;
    }
    next[maxIdx] = {
      ...next[maxIdx],
      estimated_minutes: Math.max(0, next[maxIdx].estimated_minutes + drift),
    };
  }
  return next;
}

function PlanReview({ plan, courseId }: { plan: CoursePlan; courseId: string }) {
  const approve = useApprovePlan(courseId);
  const [draft, setDraft] = useState<CoursePlan>(() => {
    const cloned = structuredClone(plan);
    // Keep the headline duration in sync with the chapter breakdown so the
    // estimate reflects the actual sum of chapter times.
    const sum = sumMinutes(cloned.chapters);
    if (sum > 0) cloned.estimated_minutes = sum;
    return cloned;
  });

  const totalMinutes = useMemo(() => sumMinutes(draft.chapters), [draft.chapters]);

  const patchChapter = (i: number, patch: Partial<PlanChapter>) =>
    setDraft((d) => ({
      ...d,
      chapters: d.chapters.map((c, j) => (j === i ? { ...c, ...patch } : c)),
    }));

  // Editing one chapter's minutes updates the headline total to match.
  const setChapterMinutes = (i: number, minutes: number) =>
    setDraft((d) => {
      const chapters = d.chapters.map((c, j) =>
        j === i ? { ...c, estimated_minutes: minutes } : c,
      );
      return { ...d, chapters, estimated_minutes: sumMinutes(chapters) };
    });

  // Editing the total duration redistributes minutes across all chapters. The
  // redistribution runs on blur so typing the total digit-by-digit doesn't
  // rescale from intermediate values and skew the per-chapter proportions.
  const setTotalMinutes = (target: number) =>
    setDraft((d) => ({ ...d, estimated_minutes: target }));

  const redistributeMinutes = () =>
    setDraft((d) => ({
      ...d,
      chapters:
        d.estimated_minutes > 0
          ? rescaleChapterMinutes(d.chapters, d.estimated_minutes)
          : d.chapters,
    }));

  const move = (i: number, dir: -1 | 1) =>
    setDraft((d) => {
      const next = [...d.chapters];
      const j = i + dir;
      if (j < 0 || j >= next.length) return d;
      [next[i], next[j]] = [next[j], next[i]];
      return { ...d, chapters: next };
    });

  const remove = (i: number) =>
    setDraft((d) => {
      const chapters = d.chapters.filter((_, j) => j !== i);
      return { ...d, chapters, estimated_minutes: sumMinutes(chapters) };
    });

  const add = () =>
    setDraft((d) => {
      const chapters = [
        ...d.chapters,
        {
          id: newChapterId(),
          title: "New chapter",
          objective: "",
          competency: "",
          estimated_minutes: 15,
          key_points: [],
          bloom_level: "understand",
        },
      ];
      return { ...d, chapters, estimated_minutes: sumMinutes(chapters) };
    });

  return (
    <section className="space-y-5">
      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
        <p className="font-semibold">Approval required</p>
        <p className="mt-1">
          Review the course plan below. Add, remove, reorder chapters or edit objectives and
          duration. Generation continues only after you approve.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2">
        <div className="rounded-xl border border-border bg-card p-4">
          <h3 className="text-sm font-semibold">Learning objectives</h3>
          <textarea
            className="mt-2 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
            rows={4}
            value={draft.objectives.join("\n")}
            onChange={(e) =>
              setDraft((d) => ({
                ...d,
                objectives: e.target.value.split("\n").filter((l) => l.trim()),
              }))
            }
          />
        </div>
        <div className="space-y-3">
          <div className="rounded-xl border border-border bg-card p-4">
            <h3 className="text-sm font-semibold">Estimated duration</h3>
            <div className="mt-2 flex items-center gap-2 text-sm">
              <input
                type="number"
                min={0}
                className="w-24 rounded-lg border border-border bg-background px-3 py-1.5 outline-none focus:border-primary"
                value={draft.estimated_minutes}
                onChange={(e) => setTotalMinutes(Number(e.target.value) || 0)}
                onBlur={redistributeMinutes}
              />
              <span className="text-muted-foreground">
                min total · auto-distributed across {draft.chapters.length}{" "}
                chapter{draft.chapters.length === 1 ? "" : "s"} ({totalMinutes} min)
              </span>
            </div>
          </div>
          {draft.compliance_requirements.length ? (
            <div className="rounded-xl border border-border bg-card p-4">
              <h3 className="text-sm font-semibold">Compliance requirements</h3>
              <ul className="mt-2 list-disc pl-5 text-sm text-muted-foreground">
                {draft.compliance_requirements.map((c, i) => (
                  <li key={i}>{c}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">Chapters ({draft.chapters.length})</h3>
          <button
            onClick={add}
            className="inline-flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-sm font-medium hover:bg-secondary"
          >
            <Plus className="h-4 w-4" /> Add chapter
          </button>
        </div>
        <ol className="space-y-3">
          {draft.chapters.map((ch, i) => (
            <li key={ch.id} className="rounded-xl border border-border bg-card p-4">
              <div className="flex items-start gap-3">
                <span className="mt-1 grid h-6 w-6 shrink-0 place-items-center rounded-full bg-primary text-xs font-bold text-primary-foreground">
                  {i + 1}
                </span>
                <div className="flex-1 space-y-2">
                  <input
                    className="w-full rounded-lg border border-border bg-background px-3 py-1.5 text-sm font-semibold outline-none focus:border-primary"
                    value={ch.title}
                    onChange={(e) => patchChapter(i, { title: e.target.value })}
                  />
                  <textarea
                    className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
                    rows={2}
                    placeholder="Objective"
                    value={ch.objective}
                    onChange={(e) => patchChapter(i, { objective: e.target.value })}
                  />
                  <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                    <label className="flex items-center gap-1">
                      Bloom:
                      <input
                        className="w-28 rounded border border-border bg-background px-2 py-1"
                        value={ch.bloom_level}
                        onChange={(e) => patchChapter(i, { bloom_level: e.target.value })}
                      />
                    </label>
                    <label className="flex items-center gap-1">
                      Minutes:
                      <input
                        type="number"
                        min={0}
                        className="w-20 rounded border border-border bg-background px-2 py-1"
                        value={ch.estimated_minutes}
                        onChange={(e) => setChapterMinutes(i, Number(e.target.value) || 0)}
                      />
                    </label>
                  </div>
                </div>
                <div className="flex flex-col gap-1">
                  <button
                    onClick={() => move(i, -1)}
                    disabled={i === 0}
                    className="rounded p-1 text-muted-foreground hover:bg-secondary disabled:opacity-40"
                  >
                    <ChevronUp className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => move(i, 1)}
                    disabled={i === draft.chapters.length - 1}
                    className="rounded p-1 text-muted-foreground hover:bg-secondary disabled:opacity-40"
                  >
                    <ChevronDown className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => remove(i)}
                    className="rounded p-1 text-red-500 hover:bg-red-50"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </div>
            </li>
          ))}
        </ol>
      </div>

      <div className="flex items-center gap-3">
        <button
          onClick={() => approve.mutate(draft)}
          disabled={approve.isPending || draft.chapters.length === 0}
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
        >
          {approve.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Check className="h-4 w-4" />
          )}
          Approve & generate course
        </button>
        <span className="text-xs text-muted-foreground">
          Starts Phase 2 (script writer) → assets → build → hosting.
        </span>
      </div>
    </section>
  );
}

const BUSY_STATUSES = new Set([
  "draft",
  "planning",
  "authoring",
  "spec_ready",
  "building",
]);

const BUSY_MESSAGES: Record<string, string> = {
  draft: "Preparing the course…",
  planning: "The planner agent is analyzing the brief and company knowledge…",
  authoring: "The script writer is producing the Lastenheft…",
  spec_ready: "Spec ready — fetching assets and building the course app…",
  building: "Building the per-course application and publishing it…",
};

function devinUrlFromId(sessionId?: string | null) {
  return sessionId ? `https://app.devin.ai/sessions/${sessionId}` : null;
}

export function CourseDetailPage() {
  const { id } = useParams<{ id: string }>();
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const { ref: frameWrapRef, isFullscreen, toggle: toggleFullscreen } =
    useFullscreen<HTMLDivElement>();

  const { data: course } = useCourse(id, true);
  const poll = course ? BUSY_STATUSES.has(course.status) : true;
  const { data: jobs } = useCourseJobs(id, poll);
  const { data: edits } = useCourseEdits(id, true);

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
  const isBusy = BUSY_STATUSES.has(course.status);
  const activeBuildJob = jobs?.find((j) => j.type === "build" && j.status === "running");
  const latestDevinJob = jobs?.find((j) => j.devin_session_id || j.devin_session_url);
  const devinJob = activeBuildJob ?? latestDevinJob;
  const devinSessionId = course.devin_session_id ?? devinJob?.devin_session_id ?? null;
  const devinSessionUrl =
    course.devin_session_url ??
    devinJob?.devin_session_url ??
    devinUrlFromId(devinSessionId);

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

      {isBusy ? (
        <>
        <PipelineMonitor courseId={course.id} />
        <div className="rounded-xl border border-border bg-card p-5 text-sm text-muted-foreground">
          <div className="flex items-center gap-2">
            <Loader2 className="h-4 w-4 animate-spin" />
            {BUSY_MESSAGES[course.status] ?? "Working…"}
          </div>
          {devinSessionUrl ? (
            <a
              href={devinSessionUrl}
              target="_blank"
              rel="noreferrer"
              className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-border bg-background px-3 py-1.5 text-sm font-medium text-foreground hover:bg-secondary"
            >
              Open live Devin session
              <ExternalLink className="h-3.5 w-3.5" />
              {devinSessionId ? (
                <span className="ml-1 font-mono text-xs text-muted-foreground">
                  {devinSessionId}
                </span>
              ) : null}
            </a>
          ) : course.status === "building" ? (
            <p className="mt-2 text-xs">
              If this build uses Devin, the live session link will appear here as soon as Devin
              starts.
            </p>
          ) : null}
        </div>
        </>
      ) : null}

      {course.status === "failed" ? (
        <div className="rounded-xl border border-red-200 bg-red-50 p-5 text-sm text-red-700">
          Generation failed. Check the job log below.
        </div>
      ) : null}

      {/* Phase 1 — plan approval gate */}
      {course.status === "plan_review" && course.plan ? (
        <PlanReview plan={course.plan} courseId={course.id} />
      ) : null}

      {/* Pipeline completed summary */}
      {isReady ? <PipelineMonitor courseId={course.id} /> : null}

      {/* Built course preview + edit-loop */}
      {isReady && course.host_url ? (
        <section className="grid gap-6 lg:grid-cols-[1fr_340px]">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Preview</h2>
              <div className="flex items-center gap-2">
                <button
                  onClick={toggleFullscreen}
                  title={isFullscreen ? "Exit fullscreen" : "Fullscreen"}
                  className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-sm font-medium text-muted-foreground hover:text-foreground"
                >
                  {isFullscreen ? (
                    <Minimize className="h-4 w-4" />
                  ) : (
                    <Maximize className="h-4 w-4" />
                  )}
                  {isFullscreen ? "Exit" : "Fullscreen"}
                </button>
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
            </div>
            <div ref={frameWrapRef} className="relative bg-background">
              {isFullscreen ? (
                <button
                  onClick={toggleFullscreen}
                  title="Exit fullscreen"
                  className="absolute right-3 top-3 z-10 inline-flex items-center gap-1.5 rounded-lg border border-border bg-background/90 px-3 py-1.5 text-sm font-medium text-muted-foreground shadow-sm backdrop-blur hover:text-foreground"
                >
                  <Minimize className="h-4 w-4" /> Exit
                </button>
              ) : null}
              <iframe
                ref={iframeRef}
                src={course.host_url}
                title={course.title}
                className={`w-full bg-white ${
                  isFullscreen ? "h-screen" : "h-[640px] rounded-xl border border-border"
                }`}
              />
            </div>
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

              {/* Suggested prompt chips */}
              <div className="mt-3 flex flex-wrap gap-1.5">
                {[
                  "Make it friendlier",
                  "Add an example",
                  "Simplify the language",
                  "Add a quiz question",
                  "Make it shorter",
                  "Add compliance note",
                ].map((chip) => (
                  <button
                    key={chip}
                    type="button"
                    onClick={() => setPrompt(chip)}
                    className="rounded-full border border-border bg-background px-2.5 py-1 text-xs text-muted-foreground hover:border-primary hover:text-primary"
                  >
                    {chip}
                  </button>
                ))}
              </div>

              <form onSubmit={submitEdit} className="mt-3 space-y-2">
                <textarea
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
                  rows={3}
                  placeholder="e.g. Make chapter 1 friendlier and add an example"
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  minLength={3}
                  maxLength={2000}
                />
                <button
                  type="submit"
                  disabled={createEdit.isPending || prompt.trim().length < 3}
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
                  <div className="flex items-start justify-between gap-2">
                    <p className="font-medium">{ed.prompt}</p>
                    {ed.edit_tier ? (
                      <span
                        className={`inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${
                          ed.edit_tier === "simple"
                            ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                            : "bg-violet-50 text-violet-700 border border-violet-200"
                        }`}
                      >
                        {ed.edit_tier === "simple" ? (
                          <Zap className="h-3 w-3" />
                        ) : (
                          <Bot className="h-3 w-3" />
                        )}
                        {ed.edit_tier === "simple" ? "Quick edit" : "Deep edit with Devin"}
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">Status: {ed.status}</p>

                  {/* Devin session link */}
                  {ed.devin_session_url || ed.devin_session_id ? (
                    <a
                      href={
                        ed.devin_session_url ||
                        `https://app.devin.ai/sessions/${ed.devin_session_id}`
                      }
                      target="_blank"
                      rel="noreferrer"
                      className="mt-1.5 inline-flex items-center gap-1 text-xs text-primary underline"
                    >
                      Watch Devin work
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  ) : null}

                  {/* Running banner */}
                  {ed.status === "running" &&
                  (ed.devin_session_url || ed.devin_session_id) ? (
                    <div className="mt-1.5 rounded-md border border-blue-200 bg-blue-50 px-2 py-1.5 text-xs text-blue-700">
                      Devin is working on this edit.{" "}
                      <a
                        href={
                          ed.devin_session_url ||
                          `https://app.devin.ai/sessions/${ed.devin_session_id}`
                        }
                        target="_blank"
                        rel="noreferrer"
                        className="font-medium underline"
                      >
                        Watch live
                      </a>
                    </div>
                  ) : null}

                  {/* Diff summary */}
                  {ed.diff ? (
                    <p className="mt-1.5 rounded-md bg-secondary/50 px-2 py-1 text-xs text-muted-foreground">
                      {ed.diff.summary}
                    </p>
                  ) : null}

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
              {j.devin_session_url ? (
                <a
                  href={j.devin_session_url}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 font-mono text-xs text-primary underline"
                >
                  {j.devin_session_id ?? "Devin session"}
                  <ExternalLink className="h-3 w-3" />
                </a>
              ) : j.devin_session_id ? (
                <span className="font-mono text-xs text-muted-foreground">{j.devin_session_id}</span>
              ) : null}
              {j.error ? <span className="text-xs text-red-600">{j.error}</span> : null}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}
