import { useState } from "react";
import { Building2, Plus } from "lucide-react";
import { useCompanies, useCreateCompany } from "@/hooks/useCompanies";

export function CompaniesPage() {
  const { data: companies } = useCompanies();
  const create = useCreateCompany();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Companies</h1>
        <p className="text-muted-foreground">Tenants on the platform. Each is fully isolated.</p>
      </div>

      <form
        className="flex flex-wrap items-end gap-3 rounded-xl border border-border bg-card p-5"
        onSubmit={(e) => {
          e.preventDefault();
          if (!name.trim() || !slug.trim()) return;
          create.mutate(
            { name: name.trim(), slug: slug.trim().toLowerCase() },
            { onSuccess: () => { setName(""); setSlug(""); } },
          );
        }}
      >
        <label className="block">
          <span className="text-sm font-medium">Name</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            className="mt-1.5 w-56 rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary"
          />
        </label>
        <label className="block">
          <span className="text-sm font-medium">Slug</span>
          <input
            value={slug}
            onChange={(e) => setSlug(e.target.value)}
            placeholder="acme"
            className="mt-1.5 w-40 rounded-lg border border-border bg-background px-3 py-2 font-mono text-sm outline-none focus:border-primary"
          />
        </label>
        <button
          type="submit"
          disabled={create.isPending}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:opacity-90 disabled:opacity-60"
        >
          <Plus className="h-4 w-4" /> Create company
        </button>
        {create.isError ? (
          <span className="text-sm text-destructive">Slug may already exist.</span>
        ) : null}
      </form>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {companies?.map((c) => (
          <div key={c.id} className="rounded-xl border border-border bg-card p-5">
            <div className="flex items-center gap-2">
              <Building2 className="h-5 w-5 text-primary" />
              <span className="font-semibold">{c.name}</span>
            </div>
            <p className="mt-2 font-mono text-xs text-muted-foreground">{c.slug}</p>
            <span className="mt-3 inline-block rounded-full bg-secondary px-2 py-0.5 text-xs">
              {c.status}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}
