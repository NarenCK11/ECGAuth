import type { LoginResponse } from "./types";

export class ApiError extends Error {
  constructor(public status: number, message: string, public body?: unknown) {
    super(message);
  }
}

function messageFrom(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown } | null)?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // FastAPI validation errors: [{ loc, msg }]
    return detail.map((d) => String((d as { msg?: string }).msg ?? "").replace(/^Value error, /, "")).filter(Boolean).join(". ") || fallback;
  }
  return fallback;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, { credentials: "include", ...init });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Check that the backend is running.");
  }
  if (res.status === 204) return undefined as T;
  const body = await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, messageFrom(body, `Request failed (${res.status})`), body);
  return body as T;
}

const json = (method: string, data?: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: data === undefined ? undefined : JSON.stringify(data),
});

export const api = {
  get: <T>(path: string, params?: Record<string, string | number | undefined | null>) => {
    const q = new URLSearchParams();
    Object.entries(params ?? {}).forEach(([k, v]) => v !== undefined && v !== null && v !== "" && q.set(k, String(v)));
    const qs = q.toString();
    return request<T>(qs ? `${path}?${qs}` : path);
  },
  post: <T>(path: string, data?: unknown) => request<T>(path, json("POST", data)),
  patch: <T>(path: string, data?: unknown) => request<T>(path, json("PATCH", data)),
  postForm: <T>(path: string, form: FormData) => request<T>(path, { method: "POST", body: form }),
};

/**
 * Login returns 401 *with* a body for failed attempts (it carries the analysis of the uploaded
 * recording). Treat that as a normal result; everything else is an error.
 */
export async function loginWithEcg(username: string, hea: File, dat: File): Promise<LoginResponse> {
  const form = new FormData();
  form.set("username", username);
  form.set("hea_file", hea);
  form.set("dat_file", dat);
  try {
    return await api.postForm<LoginResponse>("/api/auth/login", form);
  } catch (e) {
    if (e instanceof ApiError && e.status === 401 && (e.body as LoginResponse | undefined)?.analysis) {
      return e.body as LoginResponse;
    }
    throw e;
  }
}
