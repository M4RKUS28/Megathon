import { Link } from "react-router-dom";

export function Wordmark({ className = "" }: { className?: string }) {
  return (
    <Link to="/" className={`inline-flex items-center gap-2 ${className}`}>
      <span className="grid h-7 w-7 place-items-center rounded-md bg-iris font-display text-sm font-bold text-white">
        C
      </span>
      <span className="font-display text-lg font-bold tracking-tight">Coursive</span>
    </Link>
  );
}

export function SiteHeader({ signedIn }: { signedIn: boolean }) {
  return (
    <header className="sticky top-0 z-30 border-b border-mist/60 bg-paper/80 backdrop-blur">
      <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <Wordmark />
        <nav className="flex items-center gap-2 text-sm">
          <Link to="/about" className="rounded-full px-4 py-2 text-ink/70 transition hover:text-ink">
            About
          </Link>
          {signedIn ? (
            <Link
              to="/dashboard"
              className="rounded-full bg-ink px-4 py-2 font-medium text-paper transition hover:bg-ink/90"
            >
              Dashboard
            </Link>
          ) : (
            <>
              <Link
                to="/signin"
                className="rounded-full px-4 py-2 text-ink/70 transition hover:text-ink"
              >
                Sign in
              </Link>
              <Link
                to="/signup"
                className="rounded-full bg-ink px-4 py-2 font-medium text-paper transition hover:bg-ink/90"
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
    <footer className="border-t border-mist bg-paper">
      <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-6 py-10 text-sm text-ink/50 sm:flex-row">
        <Wordmark />
        <p className="font-mono text-xs">White-label AI course generation · built on Devin</p>
        <div className="flex gap-5">
          <Link to="/about" className="hover:text-ink">
            About
          </Link>
          <Link to="/signin" className="hover:text-ink">
            Sign in
          </Link>
        </div>
      </div>
    </footer>
  );
}
