import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, api } from "../api";
import { RED_FLAGS, label, type Notification, type Plan, type Progress, type SessionLog } from "../types";

const today = () => {
  const date = new Date();
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
};

function dateLabel(value: string) {
  return new Date(`${value.slice(0, 10)}T12:00:00`).toLocaleDateString(undefined, {
    month: "short", day: "numeric", year: "numeric",
  });
}

export default function ProgressPage() {
  const [plan, setPlan] = useState<Plan | null>(null);
  const [progress, setProgress] = useState<Progress | null>(null);
  const [sessions, setSessions] = useState<SessionLog[]>([]);
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [notificationTab, setNotificationTab] = useState<"alerts" | "reminders">("alerts");
  const [now, setNow] = useState(Date.now());
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [scheduledId, setScheduledId] = useState("");
  const [completed, setCompleted] = useState(true);
  const [painBefore, setPainBefore] = useState(3);
  const [painAfter, setPainAfter] = useState(3);
  const [difficulty, setDifficulty] = useState(3);
  const [redFlags, setRedFlags] = useState<string[]>([]);
  const [notes, setNotes] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [p, logs, alerts] = await Promise.all([api.currentPlan(), api.sessions(), api.notifications()]);
      setPlan(p);
      setSessions(logs);
      setNotifications(alerts);
      setProgress(await api.progress());
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setPlan(null); setProgress(null); setSessions([]); setNotifications([]);
      } else {
        setError(err instanceof Error ? err.message : "Could not load your tracking information.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  useEffect(() => {
    const timer = window.setInterval(() => setNow(Date.now()), 60_000);
    return () => window.clearInterval(timer);
  }, []);

  const loggedScheduleIds = useMemo(
    () => new Set(sessions.map((s) => s.scheduled_session_id).filter((id): id is number => id !== null)),
    [sessions],
  );
  const availableSessions = useMemo(() =>
    (plan?.schedule ?? []).filter((s) => s.scheduled_date <= today() && !loggedScheduleIds.has(s.id)),
  [plan, loggedScheduleIds]);
  const withinNextDay = now + 24 * 60 * 60 * 1000;
  const alertNotifications = notifications.filter((n) =>
    n.kind !== "reminder" || Date.parse(n.send_at) <= withinNextDay,
  );
  const upcomingReminders = notifications
    .filter((n) => n.kind === "reminder" && Date.parse(n.send_at) > withinNextDay)
    .sort((a, b) => Date.parse(a.send_at) - Date.parse(b.send_at));
  const visibleNotifications = notificationTab === "alerts" ? alertNotifications : upcomingReminders;
  const unreadAlerts = alertNotifications.filter((n) => !n.read).length;

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true); setError(null); setSuccess(null);
    try {
      await api.logSession({
        scheduled_session_id: scheduledId ? Number(scheduledId) : null,
        completed, pain_before: painBefore, pain_after: painAfter,
        perceived_difficulty: difficulty, new_red_flags: redFlags,
        notes: notes.trim() || undefined,
      });
      setSuccess("Your session was saved and your progress has been updated.");
      setRedFlags([]); setNotes(""); setScheduledId("");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save this session.");
    } finally {
      setBusy(false);
    }
  }

  async function markRead(notification: Notification) {
    try {
      const updated = await api.markNotificationRead(notification.id);
      setNotifications((current) => current.map((item) => item.id === updated.id ? updated : item));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update the notification.");
    }
  }

  if (loading) return <p role="status">Loading your progress…</p>;
  if (!plan) return <div className="space-y-2"><h1 className="text-2xl font-semibold">Progress</h1><p className="text-slate-600">Create a recovery plan from Intake before you log sessions.</p></div>;

  return (
    <div className="space-y-7">
      <header>
        <h1 className="text-2xl font-semibold">Progress &amp; session log</h1>
        <p className="mt-1 text-slate-600">Track completed sessions and how your pain changes over time.</p>
      </header>

      {error && <p role="alert" className="rounded-lg bg-red-50 p-3 text-sm text-red-800">{error}</p>}
      {success && <p role="status" className="rounded-lg bg-emerald-50 p-3 text-sm text-emerald-800">{success}</p>}

      <section className="rounded-xl bg-white p-5 shadow-sm" aria-labelledby="weekly-progress-title">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
          <div><h2 id="weekly-progress-title" className="text-lg font-semibold">Weekly progress</h2>
            <p className="text-sm text-slate-500">{progress?.explanation}</p></div>
          <button onClick={() => void refresh()} className="text-sm text-teal-800 underline">Refresh</button>
        </div>
        {progress?.weeks.length ? <div className="space-y-4">
          {progress.weeks.map((week) => <div key={week.week_index} className="rounded-lg border border-slate-100 p-4">
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
              <h3 className="font-medium">Week {week.week_index + 1}</h3>
              <span className="text-sm text-slate-600">{Math.round(week.completion_rate * 100)}% complete · {week.missed_sessions} due</span>
            </div>
            <div className="mb-3 h-2 overflow-hidden rounded-full bg-slate-100" role="progressbar"
              aria-label={`Week ${week.week_index + 1} completion`} aria-valuemin={0} aria-valuemax={100}
              aria-valuenow={Math.round(week.completion_rate * 100)}>
              <div className="h-full rounded-full bg-teal-600" style={{ width: `${Math.round(week.completion_rate * 100)}%` }} />
            </div>
            <div className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-3">
              <p>Avg. pain after session <b>{week.avg_post_pain === null ? "—" : `${week.avg_post_pain}/10`}</b></p>
              <p>Highest pain <b>{week.max_session_pain === null ? "—" : `${week.max_session_pain}/10`}</b></p>
              <p>Pain change <b>{week.pain_change === null ? "—" : `${week.pain_change > 0 ? "+" : ""}${week.pain_change}`}</b></p>
            </div>
          </div>)}
        </div> : <p className="text-sm text-slate-500">Your weekly summary will appear after a session is due.</p>}
      </section>

      <section className="rounded-xl bg-white p-5 shadow-sm" aria-labelledby="log-session-title">
        <h2 id="log-session-title" className="mb-1 text-lg font-semibold">Log a session</h2>
        <p className="mb-4 text-sm text-slate-500">Record completion and pain so your weekly progress stays current.</p>
        <form onSubmit={submit} className="space-y-4">
          <label className="block text-sm font-medium">Scheduled session
            <select className="mt-1 w-full rounded border bg-white px-3 py-2" value={scheduledId}
              onChange={(e) => setScheduledId(e.target.value)}>
              <option value="">Unscheduled / extra session</option>
              {availableSessions.map((s) => <option key={s.id} value={s.id}>{dateLabel(s.scheduled_date)} · week {s.week_index + 1}</option>)}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={completed} onChange={(e) => setCompleted(e.target.checked)} /> I completed this session</label>
          <div className="grid gap-4 sm:grid-cols-3">
            <label className="text-sm">Pain before <b>{painBefore}/10</b><input className="mt-2 block w-full" type="range" min={0} max={10} value={painBefore} onChange={(e) => setPainBefore(Number(e.target.value))} /></label>
            <label className="text-sm">Pain after <b>{painAfter}/10</b><input className="mt-2 block w-full" type="range" min={0} max={10} value={painAfter} onChange={(e) => setPainAfter(Number(e.target.value))} /></label>
            <label className="text-sm">Difficulty <b>{difficulty}/5</b><input className="mt-2 block w-full" type="range" min={1} max={5} value={difficulty} onChange={(e) => setDifficulty(Number(e.target.value))} /></label>
          </div>
          <fieldset>
            <legend className="mb-2 text-sm font-medium">New warning symptoms? Select any that apply</legend>
            <div className="grid gap-2 sm:grid-cols-2">{RED_FLAGS.map((flag) => <label key={flag} className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={redFlags.includes(flag)} onChange={() => setRedFlags((current) => current.includes(flag) ? current.filter((v) => v !== flag) : [...current, flag])} />{label(flag)}
            </label>)}</div>
          </fieldset>
          <label className="block text-sm font-medium">Notes <span className="font-normal text-slate-500">(optional)</span>
            <textarea className="mt-1 w-full rounded border px-3 py-2" rows={2} maxLength={2000} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </label>
          <button disabled={busy} className="rounded bg-teal-700 px-5 py-2 font-medium text-white hover:bg-teal-800 disabled:opacity-50">
            {busy ? "Saving…" : "Save session"}
          </button>
        </form>
      </section>

      <section className="rounded-xl bg-white p-5 shadow-sm" aria-labelledby="notifications-title">
        <h2 id="notifications-title" className="mb-3 text-lg font-semibold">Alerts &amp; reminders</h2>
        <div role="tablist" aria-label="Notification categories" className="mb-4 grid max-w-sm grid-cols-2 gap-1 rounded-lg bg-slate-100 p-1">
          <button role="tab" aria-selected={notificationTab === "alerts"} onClick={() => setNotificationTab("alerts")}
            className={`rounded-md px-3 py-2 text-sm ${notificationTab === "alerts" ? "bg-white font-medium shadow-sm" : "text-slate-600"}`}>
            Alerts {unreadAlerts > 0 && <span>({unreadAlerts} unread)</span>}
          </button>
          <button role="tab" aria-selected={notificationTab === "reminders"} onClick={() => setNotificationTab("reminders")}
            className={`rounded-md px-3 py-2 text-sm ${notificationTab === "reminders" ? "bg-white font-medium shadow-sm" : "text-slate-600"}`}>
            Reminders {upcomingReminders.length > 0 && <span>({upcomingReminders.length})</span>}
          </button>
        </div>
        {visibleNotifications.length ? <ul role="tabpanel" className="space-y-3">{visibleNotifications.map((notice) => <li key={notice.id} className={`rounded-lg border p-3 ${notice.read ? "border-slate-100" : "border-teal-200 bg-teal-50/50"}`}>
          <div className="flex flex-wrap items-start justify-between gap-2"><div>
            <p className="font-medium">{notice.kind === "referral" ? "Please seek care" : notice.kind === "reminder" ? notificationTab === "alerts" ? "Session due soon" : "Session reminder" : "Plan update"}</p>
            <p className="mt-1 text-sm text-slate-700">{notice.message}</p>
            <p className="mt-1 text-xs text-slate-500">{dateLabel(notice.send_at)}</p>
          </div>{!notice.read && <button onClick={() => void markRead(notice)} className="text-sm text-teal-800 underline">Mark read</button>}</div>
        </li>)}</ul> : <p className="text-sm text-slate-500">{notificationTab === "alerts" ? "No alerts right now." : "No future reminders scheduled."}</p>}
      </section>

      <section className="rounded-xl bg-white p-5 shadow-sm" aria-labelledby="history-title">
        <h2 id="history-title" className="mb-3 text-lg font-semibold">Session history</h2>
        {sessions.length ? <ul className="divide-y">{sessions.map((session) => <li key={session.id} className="flex flex-wrap justify-between gap-2 py-3 text-sm">
          <span>{dateLabel(session.performed_at)} · {session.completed ? "Completed" : "Missed"}</span>
          <span className="text-slate-600">Pain {session.pain_before} → {session.pain_after}/10 · difficulty {session.perceived_difficulty}/5</span>
        </li>)}</ul> : <p className="text-sm text-slate-500">No sessions logged yet.</p>}
      </section>
      <p className="text-xs text-slate-500">If you report a warning symptom or pain of 8/10 or higher after a session, LIMBER will show an alert recommending that you contact a licensed physical therapist.</p>
    </div>
  );
}
