import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import {
  useCreateDepartment,
  useDeleteDepartment,
  useDepartments,
  usePeople,
  useUpdatePerson,
} from "@/hooks/useOrg";
import { useMe } from "@/hooks/useMe";
import type { AppRole } from "@/lib/api";

const ROLES: AppRole[] = ["user", "course_creator", "admin"];

export function PeoplePage() {
  const { data: me } = useMe();
  const isAdmin = me?.role === "admin";
  const { data: people } = usePeople();
  const { data: departments } = useDepartments();
  const updatePerson = useUpdatePerson();
  const createDept = useCreateDepartment();
  const deleteDept = useDeleteDepartment();
  const [newDept, setNewDept] = useState("");

  const deptName = (id: string | null) =>
    departments?.find((d) => d.id === id)?.name ?? "—";

  return (
    <div className="space-y-10">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">People</h1>
        <p className="text-muted-foreground">Manage roles and departments for your company.</p>
      </div>

      <section>
        <h2 className="text-lg font-semibold">Team</h2>
        <div className="mt-4 overflow-hidden rounded-xl border border-border">
          <table className="w-full text-sm">
            <thead className="bg-secondary/50 text-left text-muted-foreground">
              <tr>
                <th className="px-4 py-3 font-medium">Name</th>
                <th className="px-4 py-3 font-medium">Email</th>
                <th className="px-4 py-3 font-medium">Role</th>
                <th className="px-4 py-3 font-medium">Department</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {people?.map((p) => (
                <tr key={p.id}>
                  <td className="px-4 py-3 font-medium">{p.display_name || "—"}</td>
                  <td className="px-4 py-3 text-muted-foreground">{p.email}</td>
                  <td className="px-4 py-3">
                    {isAdmin ? (
                      <select
                        value={p.role}
                        onChange={(e) =>
                          updatePerson.mutate({ id: p.id, role: e.target.value as AppRole })
                        }
                        className="rounded-md border border-border bg-background px-2 py-1"
                      >
                        {ROLES.map((r) => (
                          <option key={r} value={r}>
                            {r}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <span className="font-mono text-xs">{p.role}</span>
                    )}
                  </td>
                  <td className="px-4 py-3">
                    {isAdmin ? (
                      <select
                        value={p.department_id ?? ""}
                        onChange={(e) =>
                          updatePerson.mutate({
                            id: p.id,
                            department_id: e.target.value || null,
                          })
                        }
                        className="rounded-md border border-border bg-background px-2 py-1"
                      >
                        <option value="">—</option>
                        {departments?.map((d) => (
                          <option key={d.id} value={d.id}>
                            {d.name}
                          </option>
                        ))}
                      </select>
                    ) : (
                      deptName(p.department_id)
                    )}
                  </td>
                </tr>
              ))}
              {people && people.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-4 py-8 text-center text-muted-foreground">
                    No teammates yet. People appear here after they sign in.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </section>

      <section>
        <h2 className="text-lg font-semibold">Departments</h2>
        {isAdmin ? (
          <form
            className="mt-4 flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (!newDept.trim()) return;
              createDept.mutate({ name: newDept.trim() });
              setNewDept("");
            }}
          >
            <input
              value={newDept}
              onChange={(e) => setNewDept(e.target.value)}
              placeholder="New department"
              className="w-64 rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
            />
            <button
              type="submit"
              className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
            >
              <Plus className="h-4 w-4" /> Add
            </button>
          </form>
        ) : null}
        <ul className="mt-4 flex flex-wrap gap-2">
          {departments?.map((d) => (
            <li
              key={d.id}
              className="inline-flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1.5 text-sm"
            >
              {d.name}
              {isAdmin ? (
                <button
                  onClick={() => deleteDept.mutate(d.id)}
                  className="text-muted-foreground hover:text-destructive"
                  aria-label={`Delete ${d.name}`}
                >
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              ) : null}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}
