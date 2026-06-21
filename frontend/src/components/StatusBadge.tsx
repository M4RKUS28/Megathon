import type { CourseStatus } from "@/lib/api";

const MAP: Record<string, { label: string; cls: string }> = {
  draft: { label: "Draft", cls: "bg-secondary text-muted-foreground" },
  planning: { label: "Planning…", cls: "bg-primary/15 text-primary" },
  plan_review: { label: "Plan review", cls: "bg-accent/15 text-accent" },
  authoring: { label: "Authoring…", cls: "bg-primary/15 text-primary" },
  spec_ready: { label: "Spec ready", cls: "bg-accent/15 text-accent" },
  building: { label: "Building…", cls: "bg-primary/15 text-primary" },
  ready: { label: "Ready", cls: "bg-green-500/15 text-green-400" },
  published: { label: "Published", cls: "bg-green-500/15 text-green-400" },
  failed: { label: "Failed", cls: "bg-destructive/15 text-destructive" },
  queued: { label: "Queued", cls: "bg-secondary text-muted-foreground" },
  running: { label: "Running…", cls: "bg-primary/15 text-primary" },
  succeeded: { label: "Succeeded", cls: "bg-green-500/15 text-green-400" },
  not_started: { label: "Not started", cls: "bg-secondary text-muted-foreground" },
  in_progress: { label: "In progress", cls: "bg-primary/15 text-primary" },
  completed: { label: "Completed", cls: "bg-green-500/15 text-green-400" },
};

export function StatusBadge({ status }: { status: CourseStatus | string }) {
  const s = MAP[status] ?? { label: status, cls: "bg-secondary text-muted-foreground" };
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${s.cls}`}>
      {s.label}
    </span>
  );
}
