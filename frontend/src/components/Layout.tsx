import { NavLink, Outlet } from "react-router-dom";
import {
  Building2,
  FolderClosed,
  GraduationCap,
  LayoutDashboard,
  Palette,
  Users,
  type LucideIcon,
} from "lucide-react";
import { useAuth } from "@/hooks/useAuth";
import { useMe } from "@/hooks/useMe";
import { useMyBranding } from "@/hooks/useBranding";
import { BrandProvider, useBrand } from "@/theme/ThemeProvider";
import type { AppRole } from "@/lib/api";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  roles: AppRole[];
}

const ALL: AppRole[] = ["admin", "course_creator", "user"];
const STAFF: AppRole[] = ["admin", "course_creator"];

// Nav grows as each phase lands its pages.
const NAV: NavItem[] = [
  { to: "/dashboard", label: "Dashboard", icon: LayoutDashboard, roles: ALL },
  { to: "/courses", label: "Courses", icon: GraduationCap, roles: STAFF },
  { to: "/people", label: "People", icon: Users, roles: STAFF },
  { to: "/branding", label: "Branding", icon: Palette, roles: ["admin"] },
  { to: "/companies", label: "Companies", icon: Building2, roles: ["admin"] },
  { to: "/files", label: "Files", icon: FolderClosed, roles: ALL },
];

function Brandmark() {
  const { companyName, logoUrl } = useBrand();
  return (
    <div className="flex items-center gap-2.5">
      {logoUrl ? (
        <img src={logoUrl} alt="" className="h-8 w-8 rounded-md object-cover" />
      ) : (
        <span className="grid h-8 w-8 place-items-center rounded-md bg-primary text-sm font-bold text-primary-foreground">
          {companyName.charAt(0)}
        </span>
      )}
      <div className="leading-tight">
        <p className="text-sm font-semibold">{companyName}</p>
        <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
          on Coursive
        </p>
      </div>
    </div>
  );
}

function Shell() {
  const { user, logout } = useAuth();
  const { data: me } = useMe();
  const role = (me?.role ?? "user") as AppRole;
  const items = NAV.filter((i) => i.roles.includes(role));

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-border bg-card px-4 py-5 md:flex">
        <Brandmark />
        <nav className="mt-8 flex flex-1 flex-col gap-1">
          {items.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition ${
                  isActive
                    ? "bg-primary/10 font-medium text-primary"
                    : "text-muted-foreground hover:bg-secondary hover:text-foreground"
                }`
              }
            >
              <Icon className="h-4 w-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className="mt-auto rounded-lg border border-border p-3">
          <p className="truncate text-sm font-medium">{me?.display_name || user?.username}</p>
          <p className="font-mono text-[10px] uppercase tracking-wider text-muted-foreground">
            {role}
          </p>
          <button
            onClick={() => logout()}
            className="mt-3 w-full rounded-md bg-secondary px-3 py-1.5 text-xs text-secondary-foreground transition hover:bg-secondary/80"
          >
            Sign out
          </button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-border px-6 py-3 md:hidden">
          <Brandmark />
          <button
            onClick={() => logout()}
            className="rounded-md bg-secondary px-3 py-1.5 text-xs text-secondary-foreground"
          >
            Sign out
          </button>
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-6 py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}

export function Layout() {
  const { data: branding } = useMyBranding();
  return (
    <BrandProvider branding={branding}>
      <Shell />
    </BrandProvider>
  );
}
