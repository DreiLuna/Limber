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
    super(errorMessage(status, detail));
  }
}

// FastAPI returns a string detail for HTTPException and a list of field errors for 422s.
function errorMessage(status: number, detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d: { msg?: string }) => d.msg).filter(Boolean).join(". ") || `HTTP ${status}`;
  return (detail as { message?: string })?.message ?? `HTTP ${status}`;
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
  register: (email: string, password: string, display_name = "") =>
    request<{ access_token: string }>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, display_name }),
    }),
  login: (email: string, password: string) =>
    request<{ access_token: string }>("/auth/login", {
      method: "POST",
      body: new URLSearchParams({ username: email, password }),
    }),
  createAssessment: (a: AssessmentCreate) =>
    request<Assessment>("/assessments", { method: "POST", body: JSON.stringify(a) }),
  latestAssessment: () => request<Assessment>("/assessments/latest"),
  createPlan: () => request<Plan>("/plans", { method: "POST" }),
  currentPlan: () => request<Plan>("/plans/current"),
  exercises: () => request<Exercise[]>("/exercises"),
  exercise: (id: string) => request<Exercise>(`/exercises/${encodeURIComponent(id)}`),
};
