import { useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  Check,
  ChevronRight,
  ExternalLink,
  GitFork,
  Loader2,
  X,
} from "lucide-react";
import {
  usePipelineStatus,
  type PipelinePhase,
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
  pending: "border-zinc-600 bg-zinc-800/60",
  running: "border-blue-400 bg-blue-500/20 shadow-[0_0_12px_rgba(59,130,246,0.35)]",
  done: "border-emerald-400 bg-emerald-500/20",
  failed: "border-red-400 bg-red-500/20",
};

const STATUS_ICON: Record<PhaseStatus, React.ReactNode> = {
  pending: <span className="h-2.5 w-2.5 rounded-full bg-zinc-500" />,
  running: <Loader2 className="h-4 w-4 animate-spin text-blue-400" />,
  done: <Check className="h-4 w-4 text-emerald-400" />,
  failed: <X className="h-4 w-4 text-red-400" />,
};

const STATUS_LABEL_COLOR: Record<PhaseStatus, string> = {
  pending: "text-zinc-500",
  running: "text-blue-300",
  done: "text-emerald-300",
  failed: "text-red-300",
};

// ── Sub-components ─────────────────────────────────────────────────────────

function AssetBar({ progress }: { progress: AssetProgress }) {
  const pct = progress.total > 0 ? Math.round((progress.completed / progress.total) * 100) : 0;
  return (
    <div className="mt-2 space-y-1">
      <div className="flex items-center justify-between text-[11px]">
        <span className="text-zinc-400">
          {progress.completed}/{progress.total} assets
        </span>
        {progress.failed > 0 && (
          <span className="text-red-400">{progress.failed} failed</span>
        )}
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-700">
        <div
          className="h-full rounded-full bg-gradient-to-r from-blue-500 to-emerald-400 transition-all duration-700 ease-out"
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
      <span className="text-[11px] text-zinc-400">
        {progress.chapters_completed}/{progress.chapters_total} chapters
      </span>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-zinc-700">
        <div
          className="h-full rounded-full bg-gradient-to-r from-violet-500 to-blue-400 transition-all duration-700 ease-out"
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
                ? "bg-blue-500/20 text-blue-300 animate-pulse"
                : isDone
                  ? "bg-emerald-500/15 text-emerald-300"
                  : isFailed
                    ? "bg-red-500/15 text-red-300"
                    : "bg-zinc-700/60 text-zinc-400"
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
        <span className="text-[10px] tabular-nums text-zinc-500">{elapsed}</span>
      )}
      {phase.error && (
        <span
          className="max-w-[120px] truncate text-[10px] text-red-400"
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
            ? "bg-emerald-500/50"
            : status === "running"
              ? "bg-blue-500/40"
              : "bg-zinc-700"
        }`}
      />
      <ChevronRight
        className={`-ml-1 h-3.5 w-3.5 transition-colors duration-500 ${
          status === "done"
            ? "text-emerald-500/50"
            : status === "running"
              ? "text-blue-500/50"
              : "text-zinc-700"
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
        <GitFork className="h-3.5 w-3.5 rotate-90 text-zinc-600" />
      </div>

      <div className="flex flex-col gap-3 rounded-xl border border-zinc-700/60 bg-zinc-800/40 px-4 py-3">
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
                  className="inline-flex items-center gap-0.5 text-[10px] text-blue-400 hover:text-blue-300"
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
        <GitFork className="h-3.5 w-3.5 -rotate-90 text-zinc-600" />
      </div>
    </div>
  );
}

// ── Completed summary ──────────────────────────────────────────────────────

function CompletedSummary({ phases }: { phases: PipelinePhase[] }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-emerald-500/30 bg-emerald-500/10 px-5 py-3">
      <div className="grid h-8 w-8 place-items-center rounded-full border-2 border-emerald-400 bg-emerald-500/20">
        <Check className="h-4 w-4 text-emerald-400" />
      </div>
      <div>
        <p className="text-sm font-semibold text-emerald-300">Pipeline complete</p>
        <p className="text-xs text-zinc-400">
          All {phases.length} phases finished successfully.
        </p>
      </div>
    </div>
  );
}

// ── Main component ─────────────────────────────────────────────────────────

export function PipelineMonitor({ courseId }: { courseId: string }) {
  const { phases, overallStatus } = usePipelineStatus(courseId);

  const plan = phases.find((p) => p.id === "plan");
  const spec = phases.find((p) => p.id === "spec");
  const assets = phases.find((p) => p.id === "assets");
  const codegen = phases.find((p) => p.id === "codegen");
  const build = phases.find((p) => p.id === "build");

  if (!plan || !spec || !assets || !codegen || !build) return null;

  if (overallStatus === "done") {
    return (
      <section className="rounded-2xl border border-zinc-800 bg-zinc-900 p-5">
        <CompletedSummary phases={phases} />
      </section>
    );
  }

  return (
    <section className="rounded-2xl border border-zinc-800 bg-zinc-900 p-5">
      <h3 className="mb-4 text-sm font-semibold text-zinc-300">Pipeline progress</h3>

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
    </section>
  );
}
