// Shared chart pieces for the clinician dashboard.
// Palette: the validated reference categorical order (light surface). Slots 3-5 sit below 3:1
// contrast on white, so every chart ships a legend for 2+ series and a "Table" view.
import { useState, type ReactNode } from "react";
import {
  Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
  type TooltipContentProps,
} from "recharts";

export const SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"] as const;
const GRID = "#e2e8f0";
const AXIS_TEXT = "#64748b";
const SURFACE = "#ffffff";

export interface Series { key: string; label: string; color: string }

export function StatTile({ label, value, hint }: { label: string; value: ReactNode; hint?: string }) {
  return (
    <div className="rounded-xl bg-white p-4 ring-1 ring-slate-200">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-semibold tabular-nums text-slate-900">{value}</p>
      {hint && <p className="mt-0.5 text-xs text-slate-500">{hint}</p>}
    </div>
  );
}

export interface TableSpec { columns: string[]; rows: (string | number)[][] }

/** Card with a title and a Chart / Table toggle so values are never colour-only. */
export function ChartCard({ title, subtitle, table, children, empty }: {
  title: string; subtitle?: string; table?: TableSpec; children: ReactNode; empty?: boolean;
}) {
  const [showTable, setShowTable] = useState(false);
  return (
    <section className="min-w-0 rounded-xl bg-white p-4 ring-1 ring-slate-200">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div className="min-w-0">
          <h3 className="font-semibold text-slate-900">{title}</h3>
          {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
        </div>
        {table && !empty && (
          <button type="button" onClick={() => setShowTable((v) => !v)}
            className="shrink-0 rounded-md px-2 py-1 text-xs text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50">
            {showTable ? "Chart" : "Table"}
          </button>
        )}
      </div>
      {empty ? <p className="py-8 text-center text-sm text-slate-500">No data for these filters yet.</p>
        : showTable && table ? <DataTable {...table} /> : children}
    </section>
  );
}

export function DataTable({ columns, rows }: TableSpec) {
  return (
    <div className="max-h-72 overflow-auto">
      <table className="w-full text-left text-sm">
        <thead className="sticky top-0 bg-white text-xs text-slate-500">
          <tr>{columns.map((c) => <th key={c} className="border-b px-2 py-1.5 font-medium">{c}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-slate-100">
              {r.map((v, j) => <td key={j} className={`px-2 py-1.5 ${j ? "tabular-nums" : ""}`}>{v}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Legend({ series }: { series: Series[] }) {
  if (series.length < 2) return null;
  return (
    <ul className="mb-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
      {series.map((s) => (
        <li key={s.key} className="flex items-center gap-1.5">
          <span aria-hidden className="h-2.5 w-2.5 rounded-sm" style={{ background: s.color }} />{s.label}
        </li>
      ))}
    </ul>
  );
}

function TooltipBox({ active, payload, label, labelFormatter, valueFormatter }: TooltipContentProps<number, string> & {
  labelFormatter?: (l: string | number) => string; valueFormatter?: (v: number) => string;
}) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg bg-white px-3 py-2 text-xs shadow-lg ring-1 ring-slate-200">
      <p className="mb-1 font-medium text-slate-900">{labelFormatter ? labelFormatter(label as string) : label}</p>
      {payload.map((p) => (
        <p key={String(p.dataKey)} className="flex items-center gap-1.5 text-slate-600">
          <span aria-hidden className="h-2 w-2 rounded-full" style={{ background: p.color }} />
          {p.name}: <span className="font-medium tabular-nums text-slate-900">
            {p.value === null || p.value === undefined ? "—" : valueFormatter ? valueFormatter(Number(p.value)) : p.value}
          </span>
        </p>
      ))}
    </div>
  );
}

/** Horizontal bars for a ranked count list. Single series: value at the tip, no legend. */
export function BarList({ items, format = (n) => n.toLocaleString(), color = SERIES[0], labelOf = (k) => k }: {
  items: { key: string; count: number }[]; format?: (n: number) => string; color?: string;
  labelOf?: (k: string) => string;
}) {
  const max = Math.max(1, ...items.map((i) => i.count));
  return (
    <ul className="space-y-2">
      {items.map((i) => (
        <li key={i.key} className="grid grid-cols-[minmax(0,14rem)_1fr] items-center gap-3 text-sm"
          title={`${labelOf(i.key)}: ${format(i.count)}`}>
          <span className="truncate text-slate-700">{labelOf(i.key)}</span>
          <span className="flex items-center gap-2">
            <span className="h-4 rounded-r" style={{ width: `${Math.max(2, (i.count / max) * 85)}%`, background: color }} />
            <span className="shrink-0 tabular-nums text-slate-600">{format(i.count)}</span>
          </span>
        </li>
      ))}
    </ul>
  );
}

/** Stacked columns over a shared x key (weeks). 2px surface gaps between segments. */
export function StackedColumns<T extends object>({ data, xKey, series, xFormat, height = 220 }: {
  data: T[]; xKey: keyof T & string; series: Series[]; xFormat?: (v: string) => string; height?: number;
}) {
  return (
    <>
      <Legend series={series} />
      <div style={{ height }}>
        <ResponsiveContainer>
          <BarChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: -16 }} barCategoryGap="30%">
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey={xKey as string} tickFormatter={xFormat} tick={{ fill: AXIS_TEXT, fontSize: 11 }}
              axisLine={{ stroke: GRID }} tickLine={false} minTickGap={12} />
            <YAxis allowDecimals={false} tick={{ fill: AXIS_TEXT, fontSize: 11 }} axisLine={false} tickLine={false} />
            <Tooltip cursor={{ fill: "#f1f5f9" }}
              content={(p) => <TooltipBox {...(p as TooltipContentProps<number, string>)}
                labelFormatter={xFormat ? (l) => xFormat(String(l)) : undefined} />} />
            {series.map((s, i) => (
              <Bar key={s.key} dataKey={s.key} name={s.label} stackId="a" fill={s.color} maxBarSize={24}
                stroke={SURFACE} strokeWidth={series.length > 1 ? 1 : 0}
                radius={i === series.length - 1 ? [4, 4, 0, 0] : 0} isAnimationActive={false} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </>
  );
}

/** Line chart. One y-scale only; give it `domain` for bounded measures (pain 0-10, rates 0-1). */
export function Lines<T extends object>({ data, xKey, series, xFormat, yFormat, domain, height = 220 }: {
  data: T[]; xKey: keyof T & string; series: Series[]; xFormat?: (v: string | number) => string;
  yFormat?: (v: number) => string; domain?: [number, number]; height?: number;
}) {
  return (
    <>
      <Legend series={series} />
      <div style={{ height }}>
        <ResponsiveContainer>
          <LineChart data={data} margin={{ top: 6, right: 12, bottom: 0, left: -16 }}>
            <CartesianGrid vertical={false} stroke={GRID} />
            <XAxis dataKey={xKey as string} tickFormatter={xFormat} tick={{ fill: AXIS_TEXT, fontSize: 11 }}
              axisLine={{ stroke: GRID }} tickLine={false} minTickGap={12} />
            <YAxis domain={domain} tickFormatter={yFormat}
              ticks={domain ? Array.from({ length: 6 }, (_, i) => domain[0] + ((domain[1] - domain[0]) * i) / 5) : undefined} tick={{ fill: AXIS_TEXT, fontSize: 11 }}
              axisLine={false} tickLine={false} />
            <Tooltip cursor={{ stroke: "#94a3b8", strokeWidth: 1 }}
              content={(p) => <TooltipBox {...(p as TooltipContentProps<number, string>)}
                labelFormatter={xFormat ? (l) => xFormat(l as string | number) : undefined} valueFormatter={yFormat} />} />
            {series.map((s) => (
              <Line key={s.key} dataKey={s.key} name={s.label} stroke={s.color} strokeWidth={2}
                dot={{ r: 4, fill: s.color, stroke: SURFACE, strokeWidth: 2 }}
                activeDot={{ r: 6, fill: s.color, stroke: SURFACE, strokeWidth: 2 }}
                connectNulls isAnimationActive={false} />
            ))}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </>
  );
}

export const weekLabel = (iso: string | number) =>
  new Date(`${String(iso)}T12:00:00`).toLocaleDateString(undefined, { month: "short", day: "numeric" });
