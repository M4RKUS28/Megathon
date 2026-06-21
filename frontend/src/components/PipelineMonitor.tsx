import { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  Check,
  ChevronDown,
  ChevronRight,
  ExternalLink,
  GitFork,
  Loader2,
  Sparkles,
  X,
} from "lucide-react";
import {
  usePipelineStatus,
  type PipelinePhase,
  type PipelineTask,
  type PhaseStatus,
  type AssetProgress,
  type CodegenSession,
  type SpecProgress,
} from "@/hooks/usePipelineStatus";

// ── Elapsed-time helper ────────────────────────────────────────────────────

function useElapsed(startedAt: string | null, running: boolean): string {
  const [now, setNow] = useState(Date.now());
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (running && startedAt) {
      setNow(Date.now());
      timer.current = setInterval(() => setNow(Date.now()), 1000);
    }
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [running, startedAt]);

  if (!startedAt) return "";
  const elapsed = Math.max(0, Math.floor(((running ? now : Date.now()) - new Date(startedAt).getTime()) / 1000));
  const m = Math.floor(elapsed / 60);
  const s = elapsed % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

// ── Status visuals ─────────────────────────────────────────────────────────

const STATUS_RING: Record<PhaseStatus, string> = {
  pending: "border-muted-foreground/30 bg-muted/50",
  running: "border-primary bg-primary/10 shadow-[0_0_8px_rgba(59,130,246,0.15)]",
  done: "border-emerald-500 bg-emerald-500/10",
  failed: "border-red-500 bg-red-500/10",
};

const STATUS_ICON: Record<PhaseStatus, React.ReactNode> = {
  pending: <span className="h-2.5 w-2.5 rounded-full bg-muted-foreground/40" />,
  running: <Loader2 className="h-4 w-4 animate-spin text-primary" />,
  done: <Check className="h-4 w-4 text-emerald-600" />,
  failed: <X className="h-4 w-4 text-red-500" />,
};

const STATUS_LABEL_COLOR: Record<PhaseStatus, string> = {
  pending: "text-muted-foreground",
  running: "text-primary",
  done: "text-emerald-600",
  failed: "text-red-500",
};

// ── Sub-components ─────────────────────────────────────────────────────────

function AssetBar({ progress }: { progress: AssetProgress }) {
  const pct = progress.total > 0 ? Math.round((progress.completed / progress.total) * 100) : 0;
  return (
    <div className="mt-2 space-y-1">
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-muted-foreground">
          {progress.completed}/{progress.total} assets
        </span>
        {progress.failed > 0 && (
          <span className="text-red-500">{progress.failed} failed</span>
        )}
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-gradient-to-r from-primary to-emerald-500 transition-all duration-700 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function SpecProgressBar({ progress }: { progress: SpecProgress }) {
  const pct =
    progress.chapters_total > 0
      ? Math.round((progress.chapters_completed / progress.chapters_total) * 100)
      : 0;
  return (
    <div className="mt-2 space-y-1">
      <span className="text-[11px] text-muted-foreground">
        {progress.chapters_completed}/{progress.chapters_total} chapters
      </span>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-gradient-to-r from-violet-500 to-primary transition-all duration-700 ease-out"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

function CodegenCards({ sessions }: { sessions: CodegenSession[] }) {
  if (sessions.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-1.5">
      {sessions.map((s) => {
        const isRunning = s.status === "running";
        const isDone = s.status === "done" || s.status === "completed";
        const isFailed = s.status === "failed";
        const devinUrl = s.session_id
          ? `https://app.devin.ai/sessions/${s.session_id}`
          : null;

        const card = (
          <span
            className={`inline-flex items-center gap-1 rounded-md px-2 py-1 text-[11px] font-medium transition-colors ${
              isRunning
                ? "bg-primary/10 text-primary animate-pulse"
                : isDone
                  ? "bg-emerald-500/10 text-emerald-600"
                  : isFailed
                    ? "bg-red-500/10 text-red-500"
                    : "bg-muted text-muted-foreground"
            }`}
          >
            {isRunning && <Loader2 className="h-3 w-3 animate-spin" />}
            {isDone && <Check className="h-3 w-3" />}
            {isFailed && <AlertCircle className="h-3 w-3" />}
            {s.chapter}
          </span>
        );

        if (devinUrl) {
          return (
            <a
              key={s.session_id}
              href={devinUrl}
              target="_blank"
              rel="noreferrer"
              className="no-underline hover:brightness-125"
              title={`Open Devin session for ${s.chapter}`}
            >
              {card}
            </a>
          );
        }
        return <span key={s.chapter}>{card}</span>;
      })}
    </div>
  );
}

function PhaseNode({ phase }: { phase: PipelinePhase }) {
  const elapsed = useElapsed(phase.startedAt, phase.status === "running");

  return (
    <div className="flex flex-col items-center gap-1.5">
      <div
        className={`grid h-10 w-10 place-items-center rounded-full border-2 transition-all duration-500 ${STATUS_RING[phase.status]}`}
      >
        {STATUS_ICON[phase.status]}
      </div>
      <span
        className={`text-xs font-semibold transition-colors ${STATUS_LABEL_COLOR[phase.status]}`}
      >
        {phase.label}
      </span>
      {elapsed && phase.status === "running" && (
        <span className="text-[10px] tabular-nums text-muted-foreground">{elapsed}</span>
      )}
      {phase.error && (
        <span
          className="max-w-[120px] truncate text-[10px] text-red-500"
          title={phase.error}
        >
          {phase.error}
        </span>
      )}
    </div>
  );
}

function Connector({ status }: { status: PhaseStatus }) {
  return (
    <div className="flex items-center px-1">
      <div
        className={`h-0.5 w-6 transition-colors duration-500 sm:w-10 ${
          status === "done"
            ? "bg-emerald-500/40"
            : status === "running"
              ? "bg-primary/40"
              : "bg-border"
        }`}
      />
      <ChevronRight
        className={`-ml-1 h-3.5 w-3.5 transition-colors duration-500 ${
          status === "done"
            ? "text-emerald-500/50"
            : status === "running"
              ? "text-primary/50"
              : "text-border"
        }`}
      />
    </div>
  );
}

// ── Parallel lane ──────────────────────────────────────────────────────────

function ParallelLanes({
  assets,
  codegen,
}: {
  assets: PipelinePhase;
  codegen: PipelinePhase;
}) {
  return (
    <div className="flex items-center">
      {/* Fork indicator */}
      <div className="flex flex-col items-center justify-center gap-0.5 pr-2">
        <GitFork className="h-3.5 w-3.5 rotate-90 text-muted-foreground/50" />
      </div>

      <div className="flex flex-col gap-3 rounded-xl border border-border bg-muted/30 px-4 py-3">
        {/* Assets lane */}
        <div className="flex items-start gap-3">
          <div
            className={`mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full border-2 transition-all duration-500 ${STATUS_RING[assets.status]}`}
          >
            {STATUS_ICON[assets.status]}
          </div>
          <div className="min-w-[140px]">
            <span
              className={`text-xs font-semibold ${STATUS_LABEL_COLOR[assets.status]}`}
            >
              Assets
            </span>
            {assets.assetProgress && <AssetBar progress={assets.assetProgress} />}
          </div>
        </div>

        {/* Codegen lane */}
        <div className="flex items-start gap-3">
          <div
            className={`mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-full border-2 transition-all duration-500 ${STATUS_RING[codegen.status]}`}
          >
            {STATUS_ICON[codegen.status]}
          </div>
          <div className="min-w-[140px]">
            <div className="flex items-center gap-2">
              <span
                className={`text-xs font-semibold ${STATUS_LABEL_COLOR[codegen.status]}`}
              >
                Codegen
              </span>
              {codegen.devinSessionUrl && (
                <a
                  href={codegen.devinSessionUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-0.5 text-[10px] text-primary hover:text-primary/80"
                >
                  Devin <ExternalLink className="h-2.5 w-2.5" />
                </a>
              )}
            </div>
            <CodegenCards sessions={codegen.codegenSessions} />
          </div>
        </div>
      </div>

      {/* Join indicator */}
      <div className="flex flex-col items-center justify-center gap-0.5 pl-2">
        <GitFork className="h-3.5 w-3.5 -rotate-90 text-muted-foreground/50" />
      </div>
    </div>
  );
}

// ── Completed summary ──────────────────────────────────────────────────────

function CompletedSummary({ phases }: { phases: PipelinePhase[] }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-5 py-3">
      <div className="grid h-8 w-8 place-items-center rounded-full border-2 border-emerald-500 bg-emerald-100">
        <Check className="h-4 w-4 text-emerald-600" />
      </div>
      <div>
        <p className="text-sm font-semibold text-emerald-700">Pipeline complete</p>
        <p className="text-xs text-muted-foreground">
          All {phases.length} phases finished successfully.
        </p>
      </div>
    </div>
  );
}

// ── Service badge ────────────────────────────────────────────────────────────

const SERVICE_META: Record<string, { label: string; color: string; icon: React.ReactNode }> = {
  gemini: {
    label: "Gemini",
    color: "bg-blue-50 text-blue-600 border-blue-200",
    icon: <Sparkles className="h-3 w-3" />,
  },
  "gemini-tts": {
    label: "Gemini TTS",
    color: "bg-violet-50 text-violet-600 border-violet-200",
    icon: <Sparkles className="h-3 w-3" />,
  },
  "gemini-imagen": {
    label: "Gemini Imagen",
    color: "bg-cyan-50 text-cyan-600 border-cyan-200",
    icon: <Sparkles className="h-3 w-3" />,
  },
  devin: {
    label: "Devin",
    color: "bg-purple-50 text-purple-600 border-purple-200",
    icon: <ExternalLink className="h-3 w-3" />,
  },
  pixverse: {
    label: "PixVerse",
    color: "bg-amber-50 text-amber-600 border-amber-200",
    icon: <Sparkles className="h-3 w-3" />,
  },
  internal: {
    label: "Internal",
    color: "bg-muted text-muted-foreground border-border",
    icon: <Check className="h-3 w-3" />,
  },
};

function ServiceBadge({ service }: { service: string }) {
  const meta = SERVICE_META[service] ?? SERVICE_META.internal;
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-medium ${meta.color}`}
    >
      {meta.icon}
      {meta.label}
    </span>
  );
}

// ── Expandable task list ─────────────────────────────────────────────────────

function TaskList({ tasks }: { tasks: PipelineTask[] }) {
  const [expanded, setExpanded] = useState(false);

  if (tasks.length === 0) return null;

  const running = tasks.filter((t) => t.status === "running");
  const done = tasks.filter((t) => t.status === "done");
  const failed = tasks.filter((t) => t.status === "failed");

  return (
    <div className="mt-3 rounded-lg border border-border">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between px-3 py-2 text-left hover:bg-muted/50 transition-colors rounded-lg"
      >
        <div className="flex items-center gap-1.5">
          {expanded ? (
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-muted-foreground" />
          )}
          <span className="text-[11px] font-medium text-muted-foreground">Build steps</span>
          <span className="text-[10px] text-muted-foreground/70">
            {running.length > 0 && (
              <span className="text-primary">{running.length} running</span>
            )}
            {running.length > 0 && done.length > 0 && " \u00b7 "}
            {done.length > 0 && (
              <span className="text-emerald-600">{done.length} done</span>
            )}
            {failed.length > 0 && (
              <>
                {" \u00b7 "}
                <span className="text-red-500">{failed.length} failed</span>
              </>
            )}
          </span>
        </div>
        <span className="text-[10px] tabular-nums text-muted-foreground/60">
          {done.length + failed.length}/{tasks.length}
        </span>
      </button>

      {expanded && (
        <div className="max-h-[280px] overflow-y-auto border-t border-border px-3 py-1.5">
          <div className="space-y-0.5">
            {tasks.map((task) => (
              <div
                key={task.id}
                className="flex items-center gap-2 rounded-md px-2 py-1 hover:bg-muted/50 transition-colors"
              >
                <div className="shrink-0">
                  {task.status === "running" && (
                    <Loader2 className="h-3 w-3 animate-spin text-primary" />
                  )}
                  {task.status === "done" && (
                    <Check className="h-3 w-3 text-emerald-500" />
                  )}
                  {task.status === "failed" && (
                    <X className="h-3 w-3 text-red-500" />
                  )}
                  {task.status !== "running" && task.status !== "done" && task.status !== "failed" && (
                    <span className="h-1.5 w-1.5 rounded-full bg-muted-foreground/30 block" />
                  )}
                </div>

                <span
                  className={`flex-1 truncate text-[11px] ${
                    task.status === "running"
                      ? "text-foreground"
                      : task.status === "done"
                        ? "text-muted-foreground"
                        : task.status === "failed"
                          ? "text-red-500"
                          : "text-muted-foreground/60"
                  }`}
                >
                  {task.name}
                </span>

                <ServiceBadge service={task.service} />

                {task.session_url && (
                  <a
                    href={task.session_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-0.5 text-[10px] text-purple-500 hover:text-purple-700 shrink-0"
                    title="Open Devin session"
                  >
                    <ExternalLink className="h-2.5 w-2.5" />
                  </a>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

export function PipelineMonitor({ courseId }: { courseId: string }) {
  const { phases, overallStatus, tasks } = usePipelineStatus(courseId);

  const plan = phases.find((p) => p.id === "plan");
  const spec = phases.find((p) => p.id === "spec");
  const assets = phases.find((p) => p.id === "assets");
  const codegen = phases.find((p) => p.id === "codegen");
  const build = phases.find((p) => p.id === "build");

  if (!plan || !spec || !assets || !codegen || !build) return null;

  if (overallStatus === "done") {
    return (
      <section className="rounded-xl border border-border bg-card p-4">
        <CompletedSummary phases={phases} />
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-border bg-card p-4">
      <h3 className="mb-3 text-sm font-semibold text-foreground">Pipeline progress</h3>

      {/* Horizontal pipeline diagram */}
      <div className="flex flex-wrap items-center gap-y-4 overflow-x-auto pb-2">
        <PhaseNode phase={plan} />
        <Connector status={plan.status} />
        <PhaseNode phase={spec} />
        {spec.specProgress && <SpecProgressBar progress={spec.specProgress} />}
        <Connector status={spec.status} />

        {/* Parallel lanes for assets + codegen */}
        <ParallelLanes assets={assets} codegen={codegen} />

        <Connector
          status={
            assets.status === "done" && codegen.status === "done"
              ? "done"
              : assets.status === "failed" || codegen.status === "failed"
                ? "failed"
                : assets.status === "running" || codegen.status === "running"
                  ? "running"
                  : "pending"
          }
        />
        <PhaseNode phase={build} />
      </div>

      {/* Spec progress below the diagram when available */}
      {spec.specProgress && spec.status === "running" && (
        <div className="mt-3 max-w-[200px]">
          <SpecProgressBar progress={spec.specProgress} />
        </div>
      )}

      {/* Expandable task list */}
      <TaskList tasks={tasks} />
    </section>
  );
}
