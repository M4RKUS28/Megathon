import { useMemo } from "react";
import { useCourseJobs } from "./useCourses";
import type { GenerationJobRecord } from "@/lib/api";

// ── Types ──────────────────────────────────────────────────────────────────

export type PhaseStatus = "pending" | "running" | "done" | "failed";

export interface AssetProgress {
  total: number;
  completed: number;
  failed: number;
}

export interface CodegenSession {
  chapter: string;
  session_id: string;
  status: string;
}

export interface SpecProgress {
  chapters_total: number;
  chapters_completed: number;
}

export interface PipelinePhase {
  id: string;
  label: string;
  status: PhaseStatus;
  startedAt: string | null;
  error: string | null;
  devinSessionUrl: string | null;
  /** Only for assets phase */
  assetProgress: AssetProgress | null;
  /** Only for codegen phase */
  codegenSessions: CodegenSession[];
  /** Only for spec phase */
  specProgress: SpecProgress | null;
}

export interface PipelineState {
  phases: PipelinePhase[];
  overallStatus: PhaseStatus;
  jobs: GenerationJobRecord[];
}

// ── Helpers ────────────────────────────────────────────────────────────────

const PHASE_ORDER = ["plan", "spec", "assets", "codegen", "build"] as const;

function jobStatus(job: GenerationJobRecord | undefined): PhaseStatus {
  if (!job) return "pending";
  switch (job.status) {
    case "running":
    case "queued":
      return "running";
    case "succeeded":
    case "completed":
      return "done";
    case "failed":
      return "failed";
    default:
      return "pending";
  }
}

function parseResult(job: GenerationJobRecord | undefined): Record<string, unknown> {
  if (!job?.result) return {};
  return job.result;
}

function derivePhases(jobs: GenerationJobRecord[]): PipelinePhase[] {
  const byType = new Map<string, GenerationJobRecord>();
  for (const j of jobs) {
    const existing = byType.get(j.type);
    if (!existing || new Date(j.created_at) > new Date(existing.created_at)) {
      byType.set(j.type, j);
    }
  }

  // The build job may contain assets/codegen sub-progress under parallel_status
  const buildJob = byType.get("build");
  const buildResult = parseResult(buildJob);

  // Backend stores parallel progress under job.result.parallel_status
  const parallelStatus = buildResult.parallel_status as
    | { assets?: { status?: string; progress?: AssetProgress }; codegen?: { status?: string; sessions?: CodegenSession[] } }
    | undefined;
  const assetsResult = parallelStatus?.assets as
    | { status?: string; progress?: AssetProgress }
    | undefined;
  const codegenResult = parallelStatus?.codegen as
    | { status?: string; sessions?: CodegenSession[] }
    | undefined;

  // Spec progress may be at top level or under parallel_status
  const specJob = byType.get("spec");
  const specResult = parseResult(specJob);
  const specProgressResult = (specResult.spec_progress ?? buildResult.spec_progress) as SpecProgress | undefined;

  const phases: PipelinePhase[] = PHASE_ORDER.map((phaseId) => {
    const label =
      phaseId === "plan"
        ? "Plan"
        : phaseId === "spec"
          ? "Spec"
          : phaseId === "assets"
            ? "Assets"
            : phaseId === "codegen"
              ? "Codegen"
              : "Build";

    // Assets and codegen are sub-phases of the build job
    if (phaseId === "assets") {
      let status: PhaseStatus = "pending";
      if (assetsResult) {
        status =
          assetsResult.status === "running"
            ? "running"
            : assetsResult.status === "done" || assetsResult.status === "completed"
              ? "done"
              : assetsResult.status === "failed"
                ? "failed"
                : "pending";
      } else if (buildJob) {
        // If build is running but no assets sub-status, derive from build
        status = jobStatus(buildJob);
      }
      return {
        id: phaseId,
        label,
        status,
        startedAt: buildJob?.created_at ?? null,
        error: null,
        devinSessionUrl: null,
        assetProgress: assetsResult?.progress ?? null,
        codegenSessions: [],
        specProgress: null,
      };
    }

    if (phaseId === "codegen") {
      let status: PhaseStatus = "pending";
      if (codegenResult) {
        status =
          codegenResult.status === "running"
            ? "running"
            : codegenResult.status === "done" || codegenResult.status === "completed"
              ? "done"
              : codegenResult.status === "failed"
                ? "failed"
                : "pending";
      } else if (buildJob) {
        status = jobStatus(buildJob);
      }
      return {
        id: phaseId,
        label,
        status,
        startedAt: buildJob?.created_at ?? null,
        error: null,
        devinSessionUrl: buildJob?.devin_session_url ?? null,
        assetProgress: null,
        codegenSessions: codegenResult?.sessions ?? [],
        specProgress: null,
      };
    }

    const job = byType.get(phaseId);
    return {
      id: phaseId,
      label,
      status: jobStatus(job),
      startedAt: job?.created_at ?? null,
      error: job?.error ?? null,
      devinSessionUrl: job?.devin_session_url ?? null,
      assetProgress: null,
      codegenSessions: [],
      specProgress:
        phaseId === "spec" ? specProgressResult ?? null : null,
    };
  });

  return phases;
}

function overallFromPhases(phases: PipelinePhase[]): PhaseStatus {
  if (phases.some((p) => p.status === "failed")) return "failed";
  if (phases.every((p) => p.status === "done")) return "done";
  if (phases.some((p) => p.status === "running")) return "running";
  return "pending";
}

// ── Hook ───────────────────────────────────────────────────────────────────

export function usePipelineStatus(courseId: string | undefined, enabled = true): PipelineState {
  const { data: jobs } = useCourseJobs(courseId, enabled);

  return useMemo(() => {
    const list = jobs ?? [];
    const phases = derivePhases(list);
    return {
      phases,
      overallStatus: overallFromPhases(phases),
      jobs: list,
    };
  }, [jobs]);
}
