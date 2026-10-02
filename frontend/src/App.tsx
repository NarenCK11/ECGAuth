import { Navigate, Route, Routes } from "react-router-dom";
import { AdminLayout, PortalLayout, PublicLayout } from "./components/Shells";
import Landing from "./pages/Landing";
import Login from "./pages/Login";
import Register from "./pages/Register";
import Enroll from "./pages/Enroll";
import EcgAnalysis from "./pages/EcgAnalysis";
import Dashboard from "./pages/Dashboard";
import MedicalRecords from "./pages/MedicalRecords";
import EcgHistory from "./pages/EcgHistory";
import Profile from "./pages/Profile";
import AdminLogin from "./pages/admin/AdminLogin";
import AdminDashboard from "./pages/admin/AdminDashboard";
import AdminUsers from "./pages/admin/AdminUsers";
import AdminAuthentication from "./pages/admin/AdminAuthentication";
import AdminAnalytics from "./pages/admin/AdminAnalytics";
import AdminAudit from "./pages/admin/AdminAudit";

export default function App() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/enroll" element={<Enroll />} />
        <Route path="/admin/login" element={<AdminLogin />} />
      </Route>

      {/* Analysis page renders what the login response returned; it grants nothing by itself. */}
      <Route path="/ecg-analysis" element={<EcgAnalysis />} />

      <Route element={<PortalLayout />}>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/medical-records" element={<MedicalRecords />} />
        <Route path="/ecg-history" element={<EcgHistory />} />
        <Route path="/profile" element={<Profile />} />
      </Route>

      <Route element={<AdminLayout />}>
        <Route path="/admin" element={<Navigate to="/admin/dashboard" replace />} />
        <Route path="/admin/dashboard" element={<AdminDashboard />} />
        <Route path="/admin/users" element={<AdminUsers />} />
        <Route path="/admin/authentication" element={<AdminAuthentication />} />
        <Route path="/admin/analytics" element={<AdminAnalytics />} />
        <Route path="/admin/audit" element={<AdminAudit />} />
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
