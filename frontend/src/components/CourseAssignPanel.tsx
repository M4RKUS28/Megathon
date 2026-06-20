import { useState } from "react";
import { Trash2, UserPlus } from "lucide-react";
import { usePeople, useDepartments } from "@/hooks/useOrg";
import {
  useAssignments,
  useCourseReport,
  useCreateAssignment,
  useRemoveAssignment,
} from "@/hooks/useLearning";
import { StatusBadge } from "@/components/StatusBadge";

export function CourseAssignPanel({ courseId }: { courseId: string }) {
  const { data: people } = usePeople();
  const { data: departments } = useDepartments();
  const { data: assignments } = useAssignments(courseId);
  const { data: report } = useCourseReport(courseId);
  const createAssignment = useCreateAssignment(courseId);
  const removeAssignment = useRemoveAssignment(courseId);

  const [target, setTarget] = useState("");

  const assign = () => {
    if (!target) return;
    if (target.startsWith("dept:")) {
      createAssignment.mutate({ department_id: target.slice(5) });
    } else if (target.startsWith("user:")) {
      createAssignment.mutate({ user_id: target.slice(5) });
    }
    setTarget("");
  };

  const userName = (uid: string | null) =>
    people?.find((p) => p.id === uid)?.display_name ?? uid ?? "—";
  const deptName = (did: string | null) =>
    departments?.find((d) => d.id === did)?.name ?? did ?? "—";

  return (
    <section className="grid gap-6 lg:grid-cols-2">
      <div className="space-y-4 rounded-xl border border-border bg-card p-5">
        <h3 className="font-semibold">Assign</h3>
        <div className="flex gap-2">
          <select
            className="flex-1 rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
          >
            <option value="">Choose person or department…</option>
            {departments && departments.length > 0 ? (
              <optgroup label="Departments">
                {departments.map((d) => (
                  <option key={d.id} value={`dept:${d.id}`}>
                    {d.name} (department)
                  </option>
                ))}
              </optgroup>
            ) : null}
            {people && people.length > 0 ? (
              <optgroup label="People">
                {people.map((p) => (
                  <option key={p.id} value={`user:${p.id}`}>
                    {p.display_name || p.email}
                  </option>
                ))}
              </optgroup>
            ) : null}
          </select>
          <button
            onClick={assign}
            disabled={!target || createAssignment.isPending}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
          >
            <UserPlus className="h-4 w-4" /> Assign
          </button>
        </div>

        <ul className="space-y-1.5">
          {assignments?.map((a) => (
            <li
              key={a.id}
              className="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-sm"
            >
              <span>
                {a.assignee_department_id
                  ? `${deptName(a.assignee_department_id)} (dept)`
                  : userName(a.assignee_user_id)}
              </span>
              <button
                onClick={() => removeAssignment.mutate(a.id)}
                className="text-muted-foreground hover:text-red-600"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </li>
          ))}
          {assignments && assignments.length === 0 ? (
            <li className="text-xs text-muted-foreground">No assignments yet.</li>
          ) : null}
        </ul>
      </div>

      <div className="space-y-3 rounded-xl border border-border bg-card p-5">
        <h3 className="font-semibold">Progress report</h3>
        <div className="overflow-hidden rounded-lg border border-border">
          <table className="w-full text-sm">
            <thead className="bg-secondary/60 text-left text-xs uppercase text-muted-foreground">
              <tr>
                <th className="px-3 py-2">Name</th>
                <th className="px-3 py-2">Status</th>
                <th className="px-3 py-2">Progress</th>
                <th className="px-3 py-2">Score</th>
              </tr>
            </thead>
            <tbody>
              {report?.map((r) => (
                <tr key={r.user_id} className="border-t border-border">
                  <td className="px-3 py-2">{r.display_name || r.email}</td>
                  <td className="px-3 py-2">
                    <StatusBadge status={r.status} />
                  </td>
                  <td className="px-3 py-2">{r.progress_pct}%</td>
                  <td className="px-3 py-2">{r.score != null ? `${r.score}%` : "—"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}
