import type { Assessment, AssessmentCreate, Exercise, Plan } from "./types";

const TOKEN_KEY = "limber_token";

export const auth = {
  get token() {
    try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
  },
  set(token: string | null) {
    try { token ? localStorage.setItem(TOKEN_KEY, token) : localStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ }
  },
};

export class ApiError extends Error {
  constructor(public status: number, public detail: unknown) {
    super(typeof detail === "string" ? detail : (detail as { message?: string })?.message ?? `HTTP ${status}`);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (auth.token) headers.set("Authorization", `Bearer ${auth.token}`);
  if (init.body && !(init.body instanceof URLSearchParams)) headers.set("Content-Type", "application/json");
  const res = await fetch(`/api${path}`, { ...init, headers });
  const body = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) throw new ApiError(res.status, body?.detail ?? body);
  return body as T;
}

export const api = {
  register: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: new URLSearchParams({ username: email, password }),
    }),
  createAssessment: (a: AssessmentCreate) =>
    request<Assessment>("/assessments", { method: "POST", body: JSON.stringify(a) }),
  createPlan: () => request<Plan>("/plans", { method: "POST" }),
  currentPlan: () => request<Plan>("/plans/current"),
  exercise: (id: string) => request<Exercise>(`/exercises/${encodeURIComponent(id)}`),
};
