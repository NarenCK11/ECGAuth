// Mirrors the FastAPI schemas (backend/app/schemas). The server is the source of truth.

export interface User {
  id: string;
  patient_id: string | null;
  username: string;
  full_name: string;
  email: string;
  date_of_birth: string | null;
  role: string;
  status: "pending" | "active" | "inactive";
  created_at: string;
}

export interface Trace { t: number[]; v: number[] }

export type StageStatus = "pending" | "processing" | "completed" | "failed";

export interface Stage {
  id: string;
  label: string;
  description: string;
  detail: string;
  duration_ms: number;
  timing_kind: "demonstration";
  status: StageStatus;
}

export interface Metric {
  key: string;
  label: string;
  value: number | string | null;
  unit: string;
  /** measured = from the request/recording, derived = computed from the signal, demonstration = illustrative */
  kind: "measured" | "derived" | "demonstration";
}

export interface Analysis {
  pipeline_version: string;
  source: "enrolled_profile" | "uploaded_file";
  signal: {
    fs: number; units: string; samples_total: number; view_samples: number; decimation: number;
    t: number[]; v: number[];
    segment: { start_idx: number; end_idx: number; start_s: number; end_s: number };
  };
  processed: { filtered: Trace; normalized: Trace; method: Record<string, string> };
  features: {
    embedding: number[]; dimension: number; source: "cnn_feature_extractor" | "deterministic_placeholder";
    mean_beat: { t: number[]; v: number[]; beats_averaged: number };
    r_peaks_s: number[];
    stats: { l2_norm: number; mean: number; std: number };
  };
  stages: Stage[];
  total_stage_ms: number;
  metrics: Metric[];
  authentication: {
    authenticated: boolean; method: "ecg_hash" | "ecg_model"; message: string;
    identity: { patient_id: string | null; name: string } | null;
  };
}

export interface LoginResponse {
  authenticated: boolean;
  message: string;
  user: User | null;
  attempt_id: string | null;
  analysis: Analysis | null;
}

export interface ModelAnalyzeResponse {
  authenticated: boolean;
  predicted_name: string;
  similarity: number | null;
  threshold: number;
  analysis: Analysis;
}

export interface Enrollment {
  reference: string; original_filename: string; sampling_rate: number | null; sample_count: number | null; enrolled_at: string;
}
export interface Profile {
  user: User; enrollment: Enrollment | null; authentication_count: number; last_authenticated_at: string | null;
}

export interface MedicalRecord {
  id: string; record_date: string; department: string; doctor: string; record_type: string;
  diagnosis: string | null; notes: string | null; report_title: string | null; report_summary: string | null;
}
export interface RecordList { disclaimer: string; items: MedicalRecord[] }

export interface AttemptSummary {
  id: string; created_at: string; result: "success" | "failure"; method: string; processing_time_ms: number | null;
  pipeline_version: string | null; enrollment_reference: string | null; has_analysis: boolean;
}
export interface AttemptDetail extends AttemptSummary { analysis: Analysis | null; note: string | null }

// --- admin ---
export interface AuthEvent {
  id: string; created_at: string; user_id: string | null; patient_id: string | null; username: string | null;
  full_name: string | null; result: "success" | "failure"; failure_reason: string | null; method: string;
  pipeline_version: string | null; processing_time_ms: number | null;
}
export interface AdminUser extends User {
  enrolled: boolean; auth_total: number; auth_failed: number; last_auth_at: string | null;
}
export interface Page<T> { total: number; items: T[] }
export interface AdminUserDetail { user: AdminUser; enrollment_reference: string | null; recent_events: AuthEvent[] }
export interface AuditLog {
  id: string; created_at: string; actor_id: string | null; actor_role: string; actor_name: string | null;
  action: string; metadata: Record<string, unknown> | null;
}
export interface TrendDay { date: string; success: number; failure: number; avg_ms: number | null }
export interface Dashboard {
  totals: {
    registered_users: number; pending_users: number; authentication_events: number; successful: number;
    failed: number; active_users_7d: number; failed_24h: number;
  };
  trend: TrendDay[];
  recent_events: AuthEvent[];
  recent_registrations: AdminUser[];
  system: {
    ml_available: boolean; pipeline_version: string;
    recent_activity: { id: string; created_at: string; action: string; actor_role: string; actor_name: string | null }[];
  };
}
export interface Analytics {
  daily: TrendDay[];
  by_method: { method: string; count: number }[];
  failure_reasons: { reason: string; count: number }[];
  hourly_utc: { hour: number; count: number }[];
  top_failed_usernames: { username: string; count: number }[];
  user_status: { status: string; count: number }[];
  processing_ms: { avg: number | null; p50: number | null; p95: number | null; samples: number };
}
