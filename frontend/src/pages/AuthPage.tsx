import { useState } from "react";
import { api, ApiError } from "../api";

export default function AuthPage({ onAuth }: { onAuth: (token: string, isNew: boolean) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      const res = mode === "login" ? await api.login(email, password) : await api.register(email, password);
      onAuth(res.access_token, mode === "register");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong");
    }
  }

  return (
    <div className="mx-auto max-w-sm rounded-xl bg-white p-6 shadow-sm">
      <h1 className="mb-1 text-2xl font-semibold">{mode === "login" ? "Welcome back" : "Create an account"}</h1>
      <p className="mb-6 text-sm text-slate-500">Low-cost recovery plans for minor aches and pains.</p>
      <form onSubmit={submit} className="space-y-4">
        <input className="w-full rounded border px-3 py-2" type="email" placeholder="Email" required
          value={email} onChange={(e) => setEmail(e.target.value)} />
        <input className="w-full rounded border px-3 py-2" type="password" placeholder="Password (8+ characters)"
          minLength={8} required value={password} onChange={(e) => setPassword(e.target.value)} />
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button className="w-full rounded bg-teal-700 py-2 font-medium text-white hover:bg-teal-800">
          {mode === "login" ? "Sign in" : "Sign up"}
        </button>
      </form>
      <button className="mt-4 text-sm text-teal-700 hover:underline"
        onClick={() => setMode(mode === "login" ? "register" : "login")}>
        {mode === "login" ? "New here? Create an account" : "Already have an account? Sign in"}
      </button>
    </div>
  );
}
