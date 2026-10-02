import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  BarChart3, ClipboardList, FileText, HeartPulse, LayoutDashboard, LogOut, Menu, ScrollText, ShieldCheck, UserCircle, Users,
} from "lucide-react";
import { useAdmin, useAuth } from "../lib/auth";
import { Brand, Loading, ThemeToggle } from "./ui";

function Initials({ name }: { name: string }) {
  const s = name.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]?.toUpperCase()).join("");
  return <span className="avatar" aria-hidden>{s || "?"}</span>;
}

type NavItem = { to: string; label: string; icon: ReactNode };

function Shell({ items, label, children, user, onLogout, badge }: {
  items: NavItem[]; label: string; children: ReactNode; user: { name: string; sub: string }; onLogout: () => void; badge?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const loc = useLocation();
  useEffect(() => setOpen(false), [loc.pathname]);
  return (
    <div className="shell">
      <aside className={`sidebar${open ? " open" : ""}`} aria-label={label}>
        <Brand to={items[0].to} />
        <div className="nav-label">{label}</div>
        <nav className="stack" style={{ gap: 2 }}>
          {items.map((it) => (
            <NavLink key={it.to} to={it.to} end={it.to.split("/").length <= 2} className={({ isActive }) => `nav-link${isActive ? " active" : ""}`}>
              {it.icon}{it.label}
            </NavLink>
          ))}
        </nav>
        <div className="sidebar-foot">{badge}</div>
      </aside>
      <div className="main">
        <header className="topbar">
          <button className="icon-btn menu-btn" aria-label="Open menu" onClick={() => setOpen(true)}><Menu size={20} /></button>
          <div className="grow" />
          <ThemeToggle />
          <div className="row" style={{ gap: 10 }}>
            <Initials name={user.name} />
            <div className="small" style={{ lineHeight: 1.2 }}><strong>{user.name}</strong><br /><span className="muted">{user.sub}</span></div>
          </div>
          <button className="btn sm" onClick={onLogout}><LogOut size={15} />Sign out</button>
        </header>
        <main className="content" id="main">{children}</main>
      </div>
    </div>
  );
}

// --- patient portal ---------------------------------------------------------------------------------
export function PortalLayout() {
  const { user, loading, logout } = useAuth();
  const nav = useNavigate();
  if (loading) return <Loading label="Checking session" />;
  if (!user) return <Navigate to="/login" replace />;
  const items: NavItem[] = [
    { to: "/dashboard", label: "Dashboard", icon: <LayoutDashboard size={18} /> },
    { to: "/medical-records", label: "Medical Records", icon: <FileText size={18} /> },
    { to: "/ecg-history", label: "ECG History", icon: <HeartPulse size={18} /> },
    { to: "/profile", label: "Profile", icon: <UserCircle size={18} /> },
  ];
  return (
    <Shell items={items} label="Medical Portal" user={{ name: user.full_name, sub: user.patient_id ?? "" }}
      onLogout={async () => { await logout(); nav("/login"); }}
      badge={<span className="row" style={{ gap: 6, color: "var(--good-text)" }}><ShieldCheck size={14} />ECG-verified session</span>}>
      <Outlet />
    </Shell>
  );
}

// --- administration ------------------------------------------------------------------------------------
export function AdminLayout() {
  const { admin, loading, logout } = useAdmin();
  const nav = useNavigate();
  if (loading) return <Loading label="Checking session" />;
  if (!admin) return <Navigate to="/admin/login" replace />;
  const items: NavItem[] = [
    { to: "/admin/dashboard", label: "Dashboard", icon: <LayoutDashboard size={18} /> },
    { to: "/admin/users", label: "Users", icon: <Users size={18} /> },
    { to: "/admin/authentication", label: "Authentication", icon: <ClipboardList size={18} /> },
    { to: "/admin/analytics", label: "Analytics", icon: <BarChart3 size={18} /> },
    { to: "/admin/audit", label: "Audit Logs", icon: <ScrollText size={18} /> },
  ];
  return (
    <Shell items={items} label="Administration" user={{ name: admin.username, sub: "Administrator" }}
      onLogout={async () => { await logout(); nav("/admin/login"); }}
      badge={<span>ECGAuth Administration</span>}>
      <Outlet />
    </Shell>
  );
}

// --- public pages --------------------------------------------------------------------------------------
export function PublicLayout() {
  return (
    <div className="public">
      <header className="public-nav">
        <Brand />
        <div className="row">
          <Link className="btn ghost" to="/admin/login">Administration</Link>
          <ThemeToggle />
        </div>
      </header>
      <main className="public-main"><Outlet /></main>
    </div>
  );
}

