import { useState } from "react";
import { Link, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { auth } from "./api";
import AuthPage from "./pages/AuthPage";
import IntakePage from "./pages/IntakePage";
import PlanPage from "./pages/PlanPage";
import ProgressPage from "./pages/ProgressPage";

export default function App() {
  const [token, setToken] = useState(auth.token);
  const [landing, setLanding] = useState("/plan");
  const navigate = useNavigate();
  // New accounts go straight to intake; returning users land on their plan.
  const signIn = (t: string, isNew: boolean) => { auth.set(t); setLanding(isNew ? "/intake" : "/plan"); setToken(t); };
  const signOut = () => { auth.set(null); setToken(null); navigate("/"); };
  const guard = (el: React.ReactElement) => (token ? el : <Navigate to="/" replace />);

  return (
    <div className="min-h-screen">
      <header className="border-b bg-white">
        <nav className="mx-auto flex max-w-3xl items-center gap-4 px-4 py-3">
          <span className="font-bold text-teal-700">LIMBER</span>
          {token && (
            <>
              <Link to="/intake" className="text-sm hover:underline">Intake</Link>
              <Link to="/plan" className="text-sm hover:underline">My plan</Link>
              <Link to="/progress" className="text-sm hover:underline">Progress</Link>
              <button onClick={signOut} className="ml-auto text-sm text-slate-500 hover:underline">Sign out</button>
            </>
          )}
        </nav>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-8">
        <Routes>
          <Route path="/" element={token ? <Navigate to={landing} replace /> : <AuthPage onAuth={signIn} />} />
          <Route path="/intake" element={guard(<IntakePage />)} />
          <Route path="/plan" element={guard(<PlanPage />)} />
          <Route path="/progress" element={guard(<ProgressPage />)} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
