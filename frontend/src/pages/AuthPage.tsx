import { useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError } from "../api";

export default function AuthPage({ onAuth }: { onAuth: (token: string, isNew: boolean) => void }) {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [agreed, setAgreed] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const isLogin = mode === "login";

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      const res = isLogin ? await api.login(email, password) : await api.register(email, password, name.trim());
      onAuth(res.access_token, !isLogin);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Is the backend running?");
    } finally {
      setBusy(false);
    }
  }

  const input = "w-full rounded-lg border border-slate-300 bg-white px-3 py-2.5 focus:border-teal-600 focus:outline-none focus:ring-2 focus:ring-teal-600/20";

  return (
    <div className="mx-auto grid max-w-4xl items-center gap-10 md:grid-cols-2">
      <section className="hidden md:block">
        <h1 className="text-4xl font-bold tracking-tight text-slate-900">Move better, one small step at a time.</h1>
        <p className="mt-4 text-lg text-slate-600">
          Guided exercise plans for minor lower back, shoulder, knee, and ankle pain, without the cost of weekly
          appointments.
        </p>
        <ul className="mt-6 space-y-2 text-slate-700">
          <li>✓ A 2-minute check-in builds your plan</li>
          <li>✓ Exercises picked to match what you can do today</li>
          <li>✓ We tell you when it's time to see a professional</li>
        </ul>
      </section>

      <div className="rounded-2xl bg-white p-6 shadow-sm ring-1 ring-slate-200 sm:p-8">
        <h2 className="text-2xl font-semibold">{isLogin ? "Welcome back" : "Create your account"}</h2>
        <p className="mb-6 mt-1 text-sm text-slate-500">
          {isLogin ? "Sign in to see your plan." : "It takes less than a minute."}
        </p>
        <form onSubmit={submit} className="space-y-4">
          {!isLogin && (
            <label className="block">
              <span className="mb-1 block text-sm font-medium">First name <span className="text-slate-400">(optional)</span></span>
              <input className={input} autoComplete="given-name" maxLength={100}
                value={name} onChange={(e) => setName(e.target.value)} />
            </label>
          )}
          <label className="block">
            <span className="mb-1 block text-sm font-medium">Email</span>
            <input className={input} type="email" autoComplete="email" required
              value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label className="block">
            <span className="mb-1 block text-sm font-medium">Password</span>
            <input className={input} type="password" autoComplete={isLogin ? "current-password" : "new-password"}
              minLength={8} required value={password} onChange={(e) => setPassword(e.target.value)} />
            {!isLogin && <span className="mt-1 block text-xs text-slate-500">At least 8 characters.</span>}
          </label>

          {!isLogin && (
            <label className="flex gap-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900 ring-1 ring-amber-200">
              <input type="checkbox" className="mt-0.5 h-4 w-4 shrink-0 accent-teal-700" required
                checked={agreed} onChange={(e) => setAgreed(e.target.checked)} />
              <span>
                I understand LIMBER is for minor aches and pains. It does not diagnose conditions or replace a licensed
                physical therapist.
              </span>
            </label>
          )}

          {error && <p role="alert" className="text-sm text-red-600">{error}</p>}
          <button disabled={busy}
            className="w-full rounded-lg bg-teal-700 py-2.5 font-medium text-white hover:bg-teal-800 disabled:opacity-50">
            {busy ? "One moment..." : isLogin ? "Sign in" : "Create account"}
          </button>
        </form>

        <button className="mt-4 text-sm text-teal-700 hover:underline"
          onClick={() => { setMode(isLogin ? "register" : "login"); setError(null); }}>
          {isLogin ? "New here? Create an account" : "Already have an account? Sign in"}
        </button>
        <div className="mt-6 border-t border-slate-200 pt-4 text-sm text-slate-500">
          Just looking? <Link to="/library" className="font-medium text-teal-700 hover:underline">Browse the exercise library</Link>
        </div>
      </div>
    </div>
  );
}
