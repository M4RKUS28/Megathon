import type { CourseStatus } from "@/lib/api";

const MAP: Record<string, { label: string; cls: string }> = {
  draft: { label: "Draft", cls: "bg-secondary text-muted-foreground" },
  planning: { label: "Planning…", cls: "bg-blue-100 text-blue-700" },
  plan_review: { label: "Plan review", cls: "bg-amber-100 text-amber-700" },
  authoring: { label: "Authoring…", cls: "bg-blue-100 text-blue-700" },
  spec_ready: { label: "Spec ready", cls: "bg-amber-100 text-amber-700" },
  building: { label: "Building…", cls: "bg-blue-100 text-blue-700" },
  concept_ready: { label: "Concept ready", cls: "bg-amber-100 text-amber-700" },
  generating: { label: "Generating…", cls: "bg-blue-100 text-blue-700" },
  ready: { label: "Ready", cls: "bg-emerald-100 text-emerald-700" },
  published: { label: "Published", cls: "bg-emerald-100 text-emerald-700" },
  failed: { label: "Failed", cls: "bg-red-100 text-red-700" },
  queued: { label: "Queued", cls: "bg-secondary text-muted-foreground" },
  running: { label: "Running…", cls: "bg-blue-100 text-blue-700" },
  succeeded: { label: "Succeeded", cls: "bg-emerald-100 text-emerald-700" },
  not_started: { label: "Not started", cls: "bg-secondary text-muted-foreground" },
  in_progress: { label: "In progress", cls: "bg-blue-100 text-blue-700" },
  completed: { label: "Completed", cls: "bg-emerald-100 text-emerald-700" },
};

export function StatusBadge({ status }: { status: CourseStatus | string }) {
  const s = MAP[status] ?? { label: status, cls: "bg-secondary text-muted-foreground" };
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${s.cls}`}>
      {s.label}
    </span>
  );
}
