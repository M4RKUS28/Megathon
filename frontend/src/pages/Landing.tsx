import { Link } from "react-router-dom";
import { FileText, ShieldCheck, Zap } from "lucide-react";
import { useAuth } from "@/hooks/useAuth";

const features = [
  {
    icon: FileText,
    title: "File storage",
    body: "Upload, organize, and download your files with object storage built in.",
  },
  {
    icon: ShieldCheck,
    title: "Secure by default",
    body: "Single sign-on and role-based access powered by Keycloak.",
  },
  {
    icon: Zap,
    title: "Fast & simple",
    body: "A clean, responsive interface that stays out of your way.",
  },
];

export function LandingPage() {
  const { ready, authenticated } = useAuth();
  const signedIn = ready && authenticated;

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b border-border">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-4">
          <span className="text-lg font-bold text-primary">App</span>
          <nav className="flex items-center gap-3">
            {signedIn ? (
              <Link
                to="/dashboard"
                className="rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground shadow hover:bg-primary/90"
              >
                Dashboard
              </Link>
            ) : (
              <>
                <Link
                  to="/signin"
                  className="text-sm text-muted-foreground hover:text-foreground"
                >
                  Sign in
                </Link>
                <Link
                  to="/signup"
                  className="rounded-lg bg-primary px-4 py-2 text-sm text-primary-foreground shadow hover:bg-primary/90"
                >
                  Get started
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-7xl px-4">
        <section className="py-24 text-center sm:py-32">
          <h1 className="mx-auto max-w-3xl text-4xl font-bold tracking-tight sm:text-5xl">
            Store and share your files, securely.
          </h1>
          <p className="mx-auto mt-6 max-w-xl text-lg text-muted-foreground">
            A simple, fast file manager backed by object storage and protected by
            single sign-on.
          </p>
          <div className="mt-10 flex items-center justify-center gap-4">
            {signedIn ? (
              <Link
                to="/dashboard"
                className="rounded-lg bg-primary px-6 py-3 text-primary-foreground shadow hover:bg-primary/90"
              >
                Go to Dashboard
              </Link>
            ) : (
              <>
                <Link
                  to="/signup"
                  className="rounded-lg bg-primary px-6 py-3 text-primary-foreground shadow hover:bg-primary/90"
                >
                  Create free account
                </Link>
                <Link
                  to="/signin"
                  className="rounded-lg border border-border px-6 py-3 hover:bg-secondary"
                >
                  Sign in
                </Link>
              </>
            )}
          </div>
        </section>

        <section className="grid gap-6 pb-24 sm:grid-cols-3">
          {features.map(({ icon: Icon, title, body }) => (
            <div
              key={title}
              className="rounded-xl border border-border bg-card p-6 text-card-foreground shadow-sm"
            >
              <Icon className="h-6 w-6 text-primary" />
              <h3 className="mt-4 font-semibold">{title}</h3>
              <p className="mt-2 text-sm text-muted-foreground">{body}</p>
            </div>
          ))}
        </section>
      </main>
    </div>
  );
}
