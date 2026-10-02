import { Link, Navigate, useNavigate } from "react-router-dom";
import { ArrowRight, RotateCcw } from "lucide-react";
import { useAuth } from "../lib/auth";
import AnalysisView from "../components/AnalysisView";
import { Brand, ThemeToggle } from "../components/ui";

/** Shows the analysis returned by the login request. Access is decided by the server, not here. */
export default function EcgAnalysis() {
  const { lastLogin, refresh } = useAuth();
  const nav = useNavigate();
  if (!lastLogin?.analysis) return <Navigate to="/login" replace />;
  const ok = lastLogin.authenticated;

  async function enter() {
    const me = await refresh(); // the portal only opens if the server confirms the session cookie
    nav(me ? "/dashboard" : "/login");
  }

  return (
    <div className="public">
      <header className="public-nav"><Brand /><ThemeToggle /></header>
      <main className="content" style={{ paddingTop: 8 }}>
        <div className="page-head">
          <div><h1>ECG Analysis</h1><p>Analyzing your recording{lastLogin.user ? ` for ${lastLogin.user.full_name}` : ""}…</p></div>
        </div>
        <AnalysisView
          analysis={lastLogin.analysis}
          animate
          verdictActions={ok
            ? <button className="btn primary lg" onClick={enter}>Enter Medical Portal<ArrowRight size={18} /></button>
            : <Link className="btn primary" to="/login"><RotateCcw size={16} />Try again</Link>}
        />
      </main>
    </div>
  );
}
