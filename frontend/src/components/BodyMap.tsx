import type { BodyRegion } from "../types";

type Spot = { region: BodyRegion; shape: "circle" | "ellipse"; cx: number; cy: number; r: number; ry?: number };

// Hotspots for the four supported regions on a simple front-facing figure (viewBox 0 0 120 260).
const SPOTS: Spot[] = [
  { region: "shoulder", shape: "circle", cx: 37, cy: 52, r: 8 },
  { region: "shoulder", shape: "circle", cx: 83, cy: 52, r: 8 },
  { region: "lower_back", shape: "ellipse", cx: 60, cy: 112, r: 17, ry: 10 },
  { region: "knee", shape: "circle", cx: 50, cy: 186, r: 7 },
  { region: "knee", shape: "circle", cx: 70, cy: 186, r: 7 },
  { region: "ankle", shape: "circle", cx: 50, cy: 236, r: 6 },
  { region: "ankle", shape: "circle", cx: 70, cy: 236, r: 6 },
];

/** Clickable figure. The region buttons next to it are the accessible control; this is a visual shortcut. */
export default function BodyMap({ value, onSelect }: { value: BodyRegion | null; onSelect: (r: BodyRegion) => void }) {
  return (
    <svg viewBox="0 0 120 260" className="h-72 w-auto" aria-hidden="true">
      <g className="fill-slate-200">
        <circle cx="60" cy="22" r="14" />
        <rect x="54" y="34" width="12" height="10" />
        <rect x="38" y="44" width="44" height="88" rx="14" />
        <rect x="22" y="48" width="13" height="80" rx="6.5" />
        <rect x="85" y="48" width="13" height="80" rx="6.5" />
        <rect x="42" y="126" width="16" height="114" rx="8" />
        <rect x="62" y="126" width="16" height="114" rx="8" />
        <ellipse cx="48" cy="246" rx="9" ry="5" />
        <ellipse cx="72" cy="246" rx="9" ry="5" />
      </g>
      {SPOTS.map((s, i) => {
        const selected = value === s.region;
        const cls = `cursor-pointer stroke-teal-700 transition-colors ${selected ? "fill-teal-600" : "fill-teal-600/15 hover:fill-teal-600/40"}`;
        const onClick = () => onSelect(s.region);
        return s.shape === "circle"
          ? <circle key={i} cx={s.cx} cy={s.cy} r={s.r} strokeWidth={1.5} className={cls} onClick={onClick} />
          : <ellipse key={i} cx={s.cx} cy={s.cy} rx={s.r} ry={s.ry} strokeWidth={1.5} className={cls} onClick={onClick} />;
      })}
    </svg>
  );
}
