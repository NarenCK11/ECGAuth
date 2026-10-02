const dateFmt = new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", year: "numeric" });
const timeFmt = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

/** "02 Oct 2026". Plain dates (YYYY-MM-DD) are not shifted by the viewer's timezone. */
export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "-";
  const d = /^\d{4}-\d{2}-\d{2}$/.test(iso) ? new Date(`${iso}T00:00:00`) : new Date(iso);
  return Number.isNaN(d.getTime()) ? "-" : dateFmt.format(d);
}

export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return "-";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "-" : timeFmt.format(d);
}

export function fmtDateTime(iso: string | null | undefined): string {
  return iso ? `${fmtDate(iso)}, ${fmtTime(iso)}` : "-";
}

export function fmtNumber(n: number | null | undefined, digits = 0): string {
  return n === null || n === undefined ? "-" : n.toLocaleString("en-GB", { maximumFractionDigits: digits });
}

export function shortDay(iso: string): string {
  return new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

export const METHOD_LABEL: Record<string, string> = {
  ecg_hash: "Enrolled ECG match",
  ecg_model: "ECG model",
};

export const REASON_LABEL: Record<string, string> = {
  ecg_mismatch: "ECG did not match",
  unknown_user: "Unknown username",
  account_inactive: "Account deactivated",
  not_enrolled: "Not enrolled",
  invalid_files: "Invalid files",
  model_mismatch: "Model mismatch",
  unspecified: "Unspecified",
};

export const ACTION_LABEL: Record<string, string> = {
  register: "Registered", enroll: "Enrolled ECG", login_success: "Signed in", login_failure: "Failed sign-in",
  logout: "Signed out", admin_login_success: "Admin signed in", admin_login_failure: "Admin sign-in failed",
  admin_logout: "Admin signed out", user_status_changed: "Account status changed", admin_bootstrap: "Admin created",
  model_identify: "Model identification",
};
