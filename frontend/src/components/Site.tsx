import { Link } from "react-router-dom";

export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <Link to="/" className={`inline-flex items-center gap-2 ${className}`}>
      <span className="grid h-7 w-7 place-items-center rounded-lg bg-primary font-display text-sm font-bold text-primary-foreground shadow-neu-sm">
        C
      </span>
      <span className="font-display text-lg font-bold tracking-tight text-foreground">Coursive</span>
    </Link>
  );
}

export function SiteHeader({ signedIn }: { signedIn: boolean }) {
  return (
    <header className="sticky top-0 z-30 border-b border-border/60 bg-background/80 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <Wordmark />
        <nav className="flex items-center gap-2 text-sm">
          <Link to="/about" className="rounded-lg px-4 py-2 text-muted-foreground transition hover:text-foreground">
            About
          </Link>
          {signedIn ? (
            <Link
              to="/dashboard"
              className="rounded-lg bg-primary px-4 py-2 font-medium text-primary-foreground shadow-neu-sm transition hover:bg-primary/90"
            >
              Dashboard
            </Link>
          ) : (
            <>
              <Link
                to="/signin"
                className="rounded-lg px-4 py-2 text-muted-foreground transition hover:text-foreground"
              >
                Sign in
              </Link>
              <Link
                to="/signup"
                className="rounded-lg bg-primary px-4 py-2 font-medium text-primary-foreground shadow-neu-sm transition hover:bg-primary/90"
              >
                Get started
              </Link>
            </>
          )}
        </nav>
      </div>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="border-t border-border bg-background">
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-6 py-10 text-sm text-muted-foreground sm:flex-row">
        <Wordmark />
        <p className="font-mono text-xs">
          White-label AI course generation &middot; built on Devin
          <span className="ml-2 text-muted-foreground/60">&middot; UI adapted from Sourasith (CC BY 4.0)</span>
        </p>
        <div className="flex gap-5">
          <Link to="/about" className="hover:text-foreground">
            About
          </Link>
          <Link to="/signin" className="hover:text-foreground">
            Sign in
          </Link>
        </div>
      </div>
    </footer>
  );
}
