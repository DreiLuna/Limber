import { Suspense } from "react";
import { Outlet } from "react-router-dom";

export default function ClinicianLayout() {
  return (
    <div>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-slate-900">Clinician dashboard</h1>
          <p className="text-sm text-slate-500">Anonymized patient data. Patients appear only as codes; dates are days since intake.</p>
        </div>
      </div>
      <Suspense fallback={<p className="text-sm text-slate-500">Loading…</p>}>
        <Outlet />
      </Suspense>
    </div>
  );
}
