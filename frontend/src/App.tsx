import { useState } from "react";
import { Link, Navigate, NavLink, Route, Routes, useNavigate } from "react-router-dom";
import { auth } from "./api";
import AuthPage from "./pages/AuthPage";
import ExercisePage from "./pages/ExercisePage";
import IntakePage from "./pages/IntakePage";
import LibraryPage from "./pages/LibraryPage";
import PlanPage from "./pages/PlanPage";
import ProgressPage from "./pages/ProgressPage";

const navClass = ({ isActive }: { isActive: boolean }) =>
  `shrink-0 rounded-lg px-3 py-1.5 text-sm ${isActive ? "bg-teal-50 font-medium text-teal-800" : "text-slate-600 hover:bg-slate-100"}`;

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
      <header className="sticky top-0 z-10 border-b border-slate-200 bg-white/90 backdrop-blur">
        <nav className="mx-auto flex max-w-5xl items-center gap-1 overflow-x-auto px-4 py-3">
          <Link to="/" className="mr-3 shrink-0 text-lg font-bold tracking-tight text-teal-700">LIMBER</Link>
          {token && (
            <>
              <NavLink to="/plan" className={navClass}>My plan</NavLink>
              <NavLink to="/intake" className={navClass}>Check-in</NavLink>
              <NavLink to="/progress" className={navClass}>Progress</NavLink>
            </>
          )}
          <NavLink to="/library" className={navClass}>Library</NavLink>
          {token
            ? <button onClick={signOut} className="ml-auto shrink-0 pl-3 text-sm text-slate-500 hover:underline">Sign out</button>
            : <Link to="/" className="ml-auto shrink-0 rounded-lg bg-teal-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-800">Sign in</Link>}
        </nav>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-8">
        <Routes>
          <Route path="/" element={token ? <Navigate to={landing} replace /> : <AuthPage onAuth={signIn} />} />
          <Route path="/intake" element={guard(<IntakePage />)} />
          <Route path="/plan" element={guard(<PlanPage />)} />
          <Route path="/progress" element={guard(<ProgressPage />)} />
          <Route path="/library" element={<LibraryPage signedIn={!!token} />} />
          <Route path="/library/:id" element={<ExercisePage />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </main>
    </div>
  );
}
