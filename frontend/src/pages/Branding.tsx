import { useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Check, Loader2 } from "lucide-react";
import { brandingApi, type StyleGuide } from "@/lib/api";
import { useMyBranding } from "@/hooks/useBranding";
import { toHslTriple } from "@/lib/utils";

const EMPTY: StyleGuide = {
  companyName: "",
  logoUrls: [],
  brandColors: [],
  fonts: [],
  imageUrls: [],
  websiteUrl: "",
};

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="text-sm font-medium">{label}</span>
      <div className="mt-1.5">{children}</div>
    </label>
  );
}

const inputCls =
  "w-full rounded-lg border border-border bg-background px-3 py-2 text-sm outline-none focus:border-primary";

export function BrandingPage() {
  const { data, isLoading } = useMyBranding();
  const qc = useQueryClient();

  const [name, setName] = useState("");
  const [primary, setPrimary] = useState("#5145E5");
  const [logo, setLogo] = useState("");
  const [website, setWebsite] = useState("");
  const [colors, setColors] = useState("");
  const [fonts, setFonts] = useState("");

  useEffect(() => {
    if (!data) return;
    const sg = data.style_guide ?? EMPTY;
    setName(data.company_name || sg.companyName || "");
    setPrimary(sg.brandColors?.[0] || "#5145E5");
    setLogo(data.logo_url || sg.logoUrls?.[0] || "");
    setWebsite(sg.websiteUrl || "");
    setColors((sg.brandColors ?? []).join(", "));
    setFonts((sg.fonts ?? []).join(", "));
  }, [data]);

  const save = useMutation({
    mutationFn: () => {
      const brandColors = colors.split(",").map((c) => c.trim()).filter(Boolean);
      const style_guide: StyleGuide = {
        companyName: name,
        logoUrls: logo ? [logo] : [],
        brandColors: brandColors.length ? brandColors : [primary],
        fonts: fonts.split(",").map((f) => f.trim()).filter(Boolean),
        imageUrls: data?.style_guide?.imageUrls ?? [],
        websiteUrl: website,
      };
      return brandingApi.update({ style_guide, primary_color: primary, logo_url: logo || null });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["branding"] });
    },
  });

  const previewVars = useMemo(() => {
    const triple = toHslTriple(primary);
    return triple ? ({ ["--primary" as string]: triple } as React.CSSProperties) : {};
  }, [primary]);

  if (isLoading) return <p className="text-sm text-muted-foreground">Loading…</p>;

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Branding</h1>
        <p className="text-muted-foreground">
          Define your style guide. It themes this dashboard and every generated course.
        </p>
      </div>

      <div className="grid gap-8 lg:grid-cols-[1fr_360px]">
        <form
          className="space-y-5"
          onSubmit={(e) => {
            e.preventDefault();
            save.mutate();
          }}
        >
          <Field label="Company name">
            <input className={inputCls} value={name} onChange={(e) => setName(e.target.value)} />
          </Field>

          <Field label="Primary color">
            <div className="flex items-center gap-3">
              <input
                type="color"
                value={primary}
                onChange={(e) => setPrimary(e.target.value)}
                className="h-10 w-14 cursor-pointer rounded-lg border border-border bg-background"
              />
              <input
                className={inputCls}
                value={primary}
                onChange={(e) => setPrimary(e.target.value)}
              />
            </div>
          </Field>

          <Field label="Brand colors (comma-separated hex)">
            <input
              className={inputCls}
              placeholder="#6d28d9, #0ea5e9, #f59e0b"
              value={colors}
              onChange={(e) => setColors(e.target.value)}
            />
          </Field>

          <Field label="Fonts (comma-separated)">
            <input
              className={inputCls}
              placeholder="Inter, Sora"
              value={fonts}
              onChange={(e) => setFonts(e.target.value)}
            />
          </Field>

          <Field label="Logo URL">
            <input className={inputCls} value={logo} onChange={(e) => setLogo(e.target.value)} />
          </Field>

          <Field label="Website">
            <input
              className={inputCls}
              value={website}
              onChange={(e) => setWebsite(e.target.value)}
            />
          </Field>

          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={save.isPending}
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground transition hover:opacity-90 disabled:opacity-60"
            >
              {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              Save branding
            </button>
            {save.isSuccess && !save.isPending ? (
              <span className="inline-flex items-center gap-1 text-sm text-emerald-600">
                <Check className="h-4 w-4" /> Saved
              </span>
            ) : null}
            {save.isError ? (
              <span className="text-sm text-destructive">Couldn't save — check your access.</span>
            ) : null}
          </div>
        </form>

        {/* Live preview */}
        <div style={previewVars} className="h-fit rounded-2xl border border-border bg-card p-5">
          <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            Live preview
          </p>
          <div className="mt-3 flex items-center gap-2.5">
            {logo ? (
              <img src={logo} alt="" className="h-9 w-9 rounded-md object-cover" />
            ) : (
              <span className="grid h-9 w-9 place-items-center rounded-md bg-primary text-sm font-bold text-primary-foreground">
                {(name || "C").charAt(0)}
              </span>
            )}
            <span className="font-semibold">{name || "Your company"}</span>
          </div>
          <button className="mt-4 w-full rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground">
            Primary button
          </button>
          <div className="mt-3 rounded-lg bg-primary/10 p-3 text-sm text-primary">
            Tinted surface & accent text
          </div>
          <div className="mt-4 flex gap-2">
            {colors
              .split(",")
              .map((c) => c.trim())
              .filter(Boolean)
              .map((c) => (
                <span
                  key={c}
                  className="h-7 w-7 rounded-full border border-border"
                  style={{ background: c }}
                  title={c}
                />
              ))}
          </div>
        </div>
      </div>
    </div>
  );
}
