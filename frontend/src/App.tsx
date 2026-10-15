import { useEffect, useRef, useState } from "react";
import { Link, Navigate, NavLink, Route, Routes, useNavigate } from "react-router-dom";
import { api, auth } from "./api";
import type { Notification } from "./types";
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
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [notificationTab, setNotificationTab] = useState<"alerts" | "reminders">("alerts");
  const [notificationsError, setNotificationsError] = useState<string | null>(null);
  const notificationsRef = useRef<HTMLDivElement>(null);
  const [now, setNow] = useState(Date.now());
  const navigate = useNavigate();
  // New accounts go straight to intake; returning users land on their plan.
  const signIn = (t: string, isNew: boolean) => { auth.set(t); setLanding(isNew ? "/intake" : "/plan"); setToken(t); };
  const signOut = () => { auth.set(null); setToken(null); navigate("/"); };
  const guard = (el: React.ReactElement) => (token ? el : <Navigate to="/" replace />);

  async function loadNotifications() {
    try {
      setNotificationsError(null);
      setNotifications(await api.notifications());
    } catch {
      setNotificationsError("Could not load notifications.");
    }
  }

  useEffect(() => {
    if (token) void loadNotifications();
    else setNotifications([]);
  }, [token]);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 60_000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!notificationsOpen) return;
    const closeOutside = (event: PointerEvent) => {
      if (event.target instanceof Node && !notificationsRef.current?.contains(event.target)) {
        setNotificationsOpen(false);
      }
    };
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setNotificationsOpen(false);
    };
    document.addEventListener("pointerdown", closeOutside);
    document.addEventListener("keydown", closeOnEscape);
    return () => {
      document.removeEventListener("pointerdown", closeOutside);
      document.removeEventListener("keydown", closeOnEscape);
    };
  }, [notificationsOpen]);

  async function toggleNotifications() {
    const open = !notificationsOpen;
    setNotificationsOpen(open);
    if (open) await loadNotifications();
  }

  async function markRead(notification: Notification) {
    try {
      const updated = await api.markNotificationRead(notification.id);
      setNotifications((current) => current.map((item) => item.id === updated.id ? updated : item));
    } catch {
      setNotificationsError("Could not update that notification.");
    }
  }

  const withinNextDay = now + 24 * 60 * 60 * 1000;
  const alertNotifications = notifications.filter((notification) =>
    notification.kind !== "reminder" || new Date(notification.send_at).getTime() <= withinNextDay,
  );
  const upcomingReminders = notifications
    .filter((notification) => notification.kind === "reminder" && new Date(notification.send_at).getTime() > withinNextDay)
    .sort((a, b) => Date.parse(a.send_at) - Date.parse(b.send_at));
  const visibleNotifications = notificationTab === "alerts" ? alertNotifications : upcomingReminders;
  const unreadCount = alertNotifications.filter((notification) => !notification.read).length;

  return (
    <div className="min-h-screen">
      <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/95 backdrop-blur">
        <nav className="mx-auto flex max-w-5xl flex-wrap items-center gap-1 overflow-visible px-4 py-3">
          <Link to="/" className="mr-3 shrink-0 text-lg font-bold tracking-tight text-teal-700">LIMBER</Link>
          {token && (
            <>
              <NavLink to="/plan" className={navClass}>My plan</NavLink>
              <NavLink to="/intake" className={navClass}>Check-in</NavLink>
              <NavLink to="/progress" className={navClass}>Progress</NavLink>
              <div ref={notificationsRef} className="relative ml-auto">
                <button
                  type="button"
                  onClick={() => void toggleNotifications()}
                  aria-label={`Notifications${unreadCount ? `, ${unreadCount} unread` : ""}`}
                  aria-expanded={notificationsOpen}
                  aria-haspopup="true"
                  className="relative rounded p-2 text-slate-600 hover:bg-slate-100 hover:text-teal-800"
                >
                  <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" className="h-5 w-5">
                    <path strokeLinecap="round" strokeLinejoin="round" d="M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4" />
                  </svg>
                  {unreadCount > 0 && <span className="absolute -right-1 -top-1 min-w-5 rounded-full bg-red-600 px-1 text-center text-xs font-semibold leading-5 text-white">{unreadCount > 99 ? "99+" : unreadCount}</span>}
                </button>
                {notificationsOpen && <section role="dialog" aria-label="Notifications" className="absolute right-0 top-full z-50 mt-2 max-h-[min(70vh,32rem)] w-80 max-w-[calc(100vw-2rem)] overflow-y-auto rounded-xl border border-slate-200 bg-white p-3 shadow-xl sm:w-96">
                  <div className="mb-2 flex items-center justify-between border-b pb-2">
                    <h2 className="font-semibold">Notifications</h2>
                    <span className="text-xs text-slate-500">{unreadCount} unread</span>
                  </div>
                  <div role="tablist" aria-label="Notification categories" className="mb-3 grid grid-cols-2 gap-1 rounded-lg bg-slate-100 p-1">
                    <button role="tab" aria-selected={notificationTab === "alerts"} onClick={() => setNotificationTab("alerts")}
                      className={`rounded-md px-3 py-2 text-sm ${notificationTab === "alerts" ? "bg-white font-medium shadow-sm" : "text-slate-600"}`}>
                      Alerts {unreadCount > 0 && <span>({unreadCount})</span>}
                    </button>
                    <button role="tab" aria-selected={notificationTab === "reminders"} onClick={() => setNotificationTab("reminders")}
                      className={`rounded-md px-3 py-2 text-sm ${notificationTab === "reminders" ? "bg-white font-medium shadow-sm" : "text-slate-600"}`}>
                      Reminders {upcomingReminders.length > 0 && <span>({upcomingReminders.length})</span>}
                    </button>
                  </div>
                  {notificationsError ? <p role="alert" className="py-3 text-sm text-red-700">{notificationsError}</p>
                    : visibleNotifications.length === 0 ? <p className="py-3 text-sm text-slate-500">{notificationTab === "alerts" ? "No alerts right now." : "No future reminders scheduled."}</p>
                      : <ul role="tabpanel" className="space-y-2">{visibleNotifications.map((notification) => <li key={notification.id} className={`rounded-lg border p-3 ${notification.read ? "border-slate-100" : "border-teal-200 bg-teal-50/60"}`}>
                        <p className="text-sm font-medium">{notification.kind === "referral" ? "Please seek care" : notification.kind === "reminder" ? notificationTab === "alerts" && Date.parse(notification.send_at) >= now ? "Session due soon" : "Session reminder" : "Plan update"}</p>
                        <p className="mt-1 text-sm text-slate-700">{notification.message}</p>
                        <div className="mt-2 flex items-center justify-between gap-2">
                          <time className="text-xs text-slate-500" dateTime={notification.send_at}>{new Date(notification.send_at).toLocaleString()}</time>
                          {!notification.read && <button onClick={() => void markRead(notification)} className="text-xs font-medium text-teal-800 underline">Mark read</button>}
                        </div>
                      </li>)}</ul>}
                </section>}
              </div>
              <button onClick={signOut} className="ml-auto shrink-0 pl-3 text-sm text-slate-500 hover:underline">Sign out</button>
            </>
          )}
          <NavLink to="/library" className={`${navClass} ${token ? "" : "ml-auto"}`}>Library</NavLink>
          {!token && <Link to="/" className="ml-auto shrink-0 rounded-lg bg-teal-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-teal-800">Sign in</Link>}
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
