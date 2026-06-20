import { Link } from "react-router-dom";
import { ArrowRight, Boxes, GaugeCircle, Wand2 } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { SiteHeader, SiteFooter } from "@/components/Site";

const pipeline = [
  {
    n: "01",
    title: "Describe the course",
    body: "A team lead types what new hires need to learn — tools, processes, compliance, the org itself.",
  },
  {
    n: "02",
    title: "Devin builds it",
    body: "An AI pipeline drafts the concept, then generates and tests a real interactive course app in your brand.",
  },
  {
    n: "03",
    title: "Embed & track",
    body: "The course is hosted and embedded in your dashboard. Completion and scores stream back automatically.",
  },
];

const roles = [
  {
    icon: Wand2,
    label: "Course creators",
    body: "HR and department leads generate courses, refine them by prompt, and assign mandatory training.",
  },
  {
    icon: GaugeCircle,
    label: "Employees",
    body: "Learners get a personalized path with progress tracking, picking up exactly where they left off.",
  },
  {
    icon: Boxes,
    label: "Admins",
    body: "Run the whole tenant — branding, people, departments — isolated from every other company.",
  },
];

function AssemblyVisual() {
  const cards = [
    { tag: "BRIEF", title: "Onboarding · Engineering", tint: "bg-white/5", delay: "0ms", tilt: "-3deg" },
    { tag: "CONCEPT", title: "6 chapters · 12 quiz items", tint: "bg-white/[0.07]", delay: "140ms", tilt: "2deg" },
    { tag: "LIVE COURSE", title: "Hosted · brand-themed", tint: "bg-iris/20", delay: "280ms", tilt: "-1deg" },
  ];
  return (
    <div className="relative mx-auto w-full max-w-md">
      <div className="absolute inset-0 -z-10 bg-[radial-gradient(circle_at_70%_30%,rgba(81,69,229,0.35),transparent_60%)] blur-2xl" />
      <div className="flex flex-col gap-4">
        {cards.map((c) => (
          <div
            key={c.tag}
            style={{ animationDelay: c.delay, ["--tilt" as string]: c.tilt }}
            className={`animate-assemble-in rounded-2xl border border-white/10 ${c.tint} p-5 backdrop-blur`}
          >
            <p className="font-mono text-[11px] tracking-[0.2em] text-signal">{c.tag}</p>
            <p className="mt-2 font-display text-lg font-semibold text-paper">{c.title}</p>
            <div className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-white/10">
              <div className="h-full w-2/3 rounded-full bg-iris" />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export function LandingPage() {
  const { ready, authenticated } = useAuth();
  const signedIn = ready && authenticated;

  return (
    <div className="min-h-screen bg-paper text-ink">
      <SiteHeader signedIn={signedIn} />

      {/* Hero */}
      <section className="bg-ink text-paper">
        <div className="mx-auto grid max-w-7xl items-center gap-14 px-6 py-20 lg:grid-cols-[1.1fr_0.9fr] lg:py-28">
          <div>
            <p className="font-mono text-xs tracking-[0.3em] text-signal">
              WHITE-LABEL COURSE ENGINE
            </p>
            <h1 className="mt-5 font-display text-5xl font-extrabold leading-[1.02] tracking-tight sm:text-6xl">
              Onboarding that
              <br />
              builds itself.
            </h1>
            <p className="mt-6 max-w-lg text-lg text-paper/70">
              Coursive turns a short brief into a fully interactive training course — generated,
              tested, and hosted in your company's brand. No authoring tools, no slide decks.
            </p>
            <div className="mt-9 flex flex-wrap items-center gap-3">
              <Link
                to={signedIn ? "/dashboard" : "/signup"}
                className="group inline-flex items-center gap-2 rounded-full bg-iris px-6 py-3 font-medium text-white transition hover:bg-iris/90"
              >
                {signedIn ? "Open dashboard" : "Start building"}
                <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
              </Link>
              <Link
                to="/about"
                className="inline-flex items-center rounded-full border border-white/15 px-6 py-3 font-medium text-paper/90 transition hover:bg-white/5"
              >
                How it works
              </Link>
            </div>
            <p className="mt-6 font-mono text-xs text-paper/40">
              Demo tenant: <span className="text-paper/70">acme</span> · creator / creator
            </p>
          </div>
          <AssemblyVisual />
        </div>
      </section>

      {/* Pipeline — a real ordered sequence, so numbering carries meaning */}
      <section className="mx-auto max-w-7xl px-6 py-20">
        <div className="flex items-end justify-between gap-6">
          <h2 className="max-w-md font-display text-3xl font-bold tracking-tight sm:text-4xl">
            From sentence to shipped course.
          </h2>
          <p className="hidden max-w-xs text-sm text-ink/60 sm:block">
            Every course is a real, standalone web app — generated by Devin and embedded over a
            secure boundary.
          </p>
        </div>
        <div className="mt-12 grid gap-px overflow-hidden rounded-2xl border border-mist bg-mist sm:grid-cols-3">
          {pipeline.map((s) => (
            <div key={s.n} className="bg-paper p-8">
              <span className="font-mono text-sm text-signal">{s.n}</span>
              <h3 className="mt-4 text-xl font-semibold">{s.title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-ink/60">{s.body}</p>
            </div>
          ))}
        </div>
      </section>

      {/* White-label proof */}
      <section className="bg-ink text-paper">
        <div className="mx-auto grid max-w-7xl items-center gap-12 px-6 py-20 lg:grid-cols-2">
          <div>
            <p className="font-mono text-xs tracking-[0.3em] text-signal">ONE PLATFORM · EVERY BRAND</p>
            <h2 className="mt-5 font-display text-3xl font-bold tracking-tight sm:text-4xl">
              Your company. Your colors. Your domain.
            </h2>
            <p className="mt-5 max-w-md text-paper/70">
              Each tenant defines a style guide once. Coursive re-skins the dashboard and every
              generated course to match — strictly isolated from all other companies.
            </p>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 p-3 shadow-2xl">
            <div className="flex items-center gap-1.5 px-2 py-2">
              <span className="h-3 w-3 rounded-full bg-signal/80" />
              <span className="h-3 w-3 rounded-full bg-amber-400/70" />
              <span className="h-3 w-3 rounded-full bg-emerald-400/70" />
              <span className="ml-3 font-mono text-xs text-paper/40">acme.coursive.app</span>
            </div>
            <div className="rounded-xl bg-paper p-5 text-ink">
              <div className="flex items-center gap-2">
                <span className="grid h-7 w-7 place-items-center rounded-md bg-[#6d28d9] text-xs font-bold text-white">
                  A
                </span>
                <span className="font-display font-semibold">Acme Academy</span>
              </div>
              <div className="mt-4 grid grid-cols-3 gap-3">
                {["Security 101", "Git & CI", "Brand Voice"].map((t) => (
                  <div key={t} className="rounded-lg border border-mist p-3">
                    <div className="h-1.5 w-8 rounded-full bg-[#6d28d9]" />
                    <p className="mt-2 text-xs font-medium">{t}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Roles */}
      <section className="mx-auto max-w-7xl px-6 py-20">
        <h2 className="font-display text-3xl font-bold tracking-tight sm:text-4xl">
          Built for the whole org.
        </h2>
        <div className="mt-10 grid gap-6 sm:grid-cols-3">
          {roles.map(({ icon: Icon, label, body }) => (
            <div key={label} className="rounded-2xl border border-mist bg-white p-7">
              <Icon className="h-6 w-6 text-iris" />
              <h3 className="mt-4 text-lg font-semibold">{label}</h3>
              <p className="mt-2 text-sm leading-relaxed text-ink/60">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <SiteFooter />
    </div>
  );
}
