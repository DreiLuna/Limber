import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { SUPPORTED_REGIONS, label } from "../types";
import { clinicianApi, type Filters, type VersionSummary } from "./api";

/** Filters live in the URL so a view can be bookmarked or shared with the team. */
export function useFilters(): [Filters, (f: Filters) => void] {
  const [params, setParams] = useSearchParams();
  const filters = useMemo<Filters>(() => ({
    start: params.get("start") ?? undefined,
    end: params.get("end") ?? undefined,
    region: params.get("region") ?? undefined,
    level: params.get("level") ? Number(params.get("level")) : undefined,
    version: params.get("version") ? Number(params.get("version")) : undefined,
  }), [params]);
  const set = (f: Filters) => {
    const next = new URLSearchParams();
    for (const [k, v] of Object.entries(f)) if (v !== undefined && v !== "") next.set(k, String(v));
    setParams(next, { replace: true });
  };
  return [filters, set];
}

const PRESETS: { label: string; days: number | null }[] = [
  { label: "30 days", days: 30 }, { label: "90 days", days: 90 }, { label: "All time", days: null },
];

const isoDaysAgo = (days: number) => {
  const d = new Date();
  d.setDate(d.getDate() - days);
  return d.toISOString().slice(0, 10);
};

const control = "rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-sm";

export function FilterBar({ filters, onChange, showVersion = true }: {
  filters: Filters; onChange: (f: Filters) => void; showVersion?: boolean;
}) {
  const [versions, setVersions] = useState<VersionSummary[]>([]);
  useEffect(() => {
    if (showVersion) clinicianApi.versions().then(setVersions).catch(() => setVersions([]));
  }, [showVersion]);
  const patch = (p: Partial<Filters>) => onChange({ ...filters, ...p });
  const activePreset = PRESETS.find((p) =>
    p.days === null ? !filters.start && !filters.end : filters.start === isoDaysAgo(p.days) && !filters.end);

  return (
    <div className="mb-6 flex flex-wrap items-end gap-3 rounded-xl bg-white p-3 ring-1 ring-slate-200">
      <div role="group" aria-label="Date range" className="flex rounded-lg bg-slate-100 p-0.5">
        {PRESETS.map((p) => (
          <button key={p.label} type="button" aria-pressed={activePreset === p}
            onClick={() => patch({ start: p.days === null ? undefined : isoDaysAgo(p.days), end: undefined })}
            className={`rounded-md px-2.5 py-1 text-sm ${activePreset === p ? "bg-white font-medium shadow-sm" : "text-slate-600"}`}>
            {p.label}
          </button>
        ))}
      </div>
      <label className="text-xs text-slate-500">From
        <input type="date" className={`${control} mt-0.5 block`} value={filters.start ?? ""}
          onChange={(e) => patch({ start: e.target.value || undefined })} />
      </label>
      <label className="text-xs text-slate-500">To
        <input type="date" className={`${control} mt-0.5 block`} value={filters.end ?? ""}
          onChange={(e) => patch({ end: e.target.value || undefined })} />
      </label>
      <label className="text-xs text-slate-500">Region
        <select className={`${control} mt-0.5 block`} value={filters.region ?? ""}
          onChange={(e) => patch({ region: e.target.value || undefined })}>
          <option value="">All regions</option>
          {SUPPORTED_REGIONS.map((r) => <option key={r} value={r}>{label(r)}</option>)}
        </select>
      </label>
      <label className="text-xs text-slate-500">Starting level
        <select className={`${control} mt-0.5 block`} value={filters.level ?? ""}
          onChange={(e) => patch({ level: e.target.value ? Number(e.target.value) : undefined })}>
          <option value="">All levels</option>
          {[1, 2, 3].map((l) => <option key={l} value={l}>Level {l}</option>)}
        </select>
      </label>
      {showVersion && (
        <label className="text-xs text-slate-500">Config version
          <select className={`${control} mt-0.5 block`} value={filters.version ?? ""}
            onChange={(e) => patch({ version: e.target.value ? Number(e.target.value) : undefined })}>
            <option value="">All versions</option>
            {versions.map((v) => <option key={v.version} value={v.version}>v{v.version}{v.is_active ? " (active)" : ""}</option>)}
          </select>
        </label>
      )}
      {Object.values(filters).some((v) => v !== undefined) && (
        <button type="button" onClick={() => onChange({})} className="ml-auto text-sm text-slate-500 hover:underline">
          Clear filters
        </button>
      )}
    </div>
  );
}
