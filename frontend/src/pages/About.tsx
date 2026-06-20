import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { SiteHeader, SiteFooter } from "@/components/Site";

const architecture = [
  {
    k: "Platform dashboard",
    v: "A multi-tenant React app. Each company sees only its own data, people, and courses, re-skinned to its brand.",
  },
  {
    k: "Generation pipeline",
    v: "A queue hands course briefs to the Devin API, which scaffolds, builds and tests a standalone course web app from your style guide.",
  },
  {
    k: "Course hosting",
    v: "Built courses are stored as static apps and embedded over a sandboxed boundary — progress flows back without exposing tokens.",
  },
  {
    k: "Edit loop",
    v: "Creators select an element in a course and request a change in plain language. Devin proposes it; the creator accepts or rejects.",
  },
];

const principles = [
  ["Strict isolation", "One company can never see or affect another. Tenancy is enforced on every request."],
  ["Brand-native", "The style guide drives both the dashboard and every generated course — not a logo in a corner."],
  ["Real apps, not slides", "Courses are interactive web apps, versioned and improvable, not static exports."],
];

export function AboutPage() {
  const { ready, authenticated } = useAuth();
  const signedIn = ready && authenticated;

  return (
    <div className="min-h-screen bg-paper text-ink">
      <SiteHeader signedIn={signedIn} />

      <section className="bg-ink text-paper">
        <div className="mx-auto max-w-3xl px-6 py-20 lg:py-28">
          <p className="font-mono text-xs tracking-[0.3em] text-signal">ABOUT COURSIVE</p>
          <h1 className="mt-5 font-display text-4xl font-extrabold leading-tight tracking-tight sm:text-5xl">
            We turn company knowledge into living courses.
          </h1>
          <p className="mt-6 text-lg text-paper/70">
            Onboarding and internal training are stuck in slide decks that go stale the moment
            they're made. Coursive replaces the authoring grind with a pipeline: describe what people
            need to know, and an AI agent generates a real, branded, interactive course — then keeps
            it improvable.
          </p>
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-6 py-20">
        <h2 className="font-display text-3xl font-bold tracking-tight">How the system fits together</h2>
        <div className="mt-10 divide-y divide-mist border-y border-mist">
          {architecture.map((row, i) => (
            <div key={row.k} className="grid gap-2 py-6 sm:grid-cols-[auto_1fr] sm:gap-10">
              <div className="flex items-baseline gap-4">
                <span className="font-mono text-sm text-signal">{String(i + 1).padStart(2, "0")}</span>
                <span className="font-display text-lg font-semibold">{row.k}</span>
              </div>
              <p className="text-ink/60 sm:pt-0.5">{row.v}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-5xl px-6 pb-20">
        <div className="grid gap-6 sm:grid-cols-3">
          {principles.map(([k, v]) => (
            <div key={k} className="rounded-2xl border border-mist bg-white p-6">
              <h3 className="font-display text-lg font-semibold">{k}</h3>
              <p className="mt-2 text-sm leading-relaxed text-ink/60">{v}</p>
            </div>
          ))}
        </div>
        <div className="mt-12 flex items-center gap-4">
          <Link
            to={signedIn ? "/dashboard" : "/signup"}
            className="group inline-flex items-center gap-2 rounded-full bg-iris px-6 py-3 font-medium text-white transition hover:bg-iris/90"
          >
            {signedIn ? "Open dashboard" : "Try the demo tenant"}
            <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
          </Link>
          <span className="font-mono text-xs text-ink/40">acme · creator / creator</span>
        </div>
      </section>

      <SiteFooter />
    </div>
  );
}
