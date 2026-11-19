import { jointAngle, SquatCounter } from "./squatCounter.ts";
import type { Landmark, PoseSample } from "./squatCounter.ts";

export const MOVEMENTS = {
  Bodyweight_Squat: { name: "Bodyweight squat", joint: "Knee", view: "Side view: shoulder, hip, knee and ankle visible. Start standing.", indices: [[11, 23, 25, 27], [12, 24, 26, 28]], reverse: false, limits: { standing: 160, bending: 145, bent: 110 } },
  Seated_Knee_Extension: { name: "Seated knee extension", joint: "Knee", view: "Side view: sit upright on a stable chair. Keep shoulder, hip, knee and ankle visible. Start with your foot down.", indices: [[11, 23, 25, 27], [12, 24, 26, 28]], reverse: true, limits: { standing: 165, bending: 145, bent: 115 } },
  Wall_Press_Up: { name: "Wall press-up", joint: "Elbow", view: "Side view: keep hip, shoulder, elbow and wrist visible. Start with your arms extended toward the wall.", indices: [[23, 11, 13, 15], [24, 12, 14, 16]], reverse: false, limits: { standing: 155, bending: 140, bent: 110 } },
} as const;
export type MovementId = keyof typeof MOVEMENTS;
export type Side = "left" | "right";
export interface MovementSummary {
  exercise_id: MovementId; protocol: "movement-v1"; side: Side;
  reps: number; partials: number; hold_seconds: number;
  min_angle: number; max_angle: number; tracking_ratio: number; duration_seconds: number;
}

export function readMovementPose(id: MovementId, poses: Landmark[][], width: number, height: number, side: Side): PoseSample | null {
  if (poses.length !== 1 || !Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) return null;
  const points = MOVEMENTS[id].indices[side === "left" ? 0 : 1].map(i => poses[0][i]);
  if (!points.every(p => p && Number.isFinite(p.x) && Number.isFinite(p.y) && p.x > .02 && p.x < .98 && p.y > .02 && p.y < .98 && (p.visibility ?? 0) >= .65 && (p.presence === undefined || p.presence >= .65))) return null;
  const [anchor, a, b, c] = points;
  if (id === "Wall_Press_Up" ? anchor.y - a.y < .08 : a.y - anchor.y < .08) return null;
  if (Math.hypot((a.x - c.x) * width, (a.y - c.y) * height) < Math.min(width, height) * .08) return null;
  const angle = jointAngle(a, b, c, width, height);
  return angle === null ? null : { side, angle, points };
}

export class MovementTracker {
  private counter: SquatCounter;
  private id: MovementId;
  private side: Side;
  private started: number | null = null;
  private last: number | null = null;
  private valid = 0;
  private held = 0;
  private lastValid = false;
  private lastBent = false;
  private min = Infinity;
  private max = -Infinity;
  private state;

  constructor(id: MovementId = "Bodyweight_Squat", side: Side = "left") {
    this.id = id; this.side = side;
    this.counter = new SquatCounter(MOVEMENTS[id].limits);
    this.state = this.counter.reset();
  }
  reset() {
    this.started = this.last = null; this.valid = this.held = 0;
    this.min = Infinity; this.max = -Infinity; this.lastValid = this.lastBent = false;
    this.state = this.counter.reset(); return this.state;
  }
  update(sample: PoseSample | null, now: number) {
    if (!Number.isFinite(now) || (this.last !== null && now <= this.last)) return this.state;
    if (this.started === null) this.started = now;
    const dt = this.last === null ? 0 : now - this.last;
    this.last = now;
    const reliable = !!sample && sample.side === this.side && Number.isFinite(sample.angle) && sample.angle >= 0 && sample.angle <= 180;
    const normalized = reliable ? { ...sample!, angle: MOVEMENTS[this.id].reverse ? Math.min(180, 270 - sample!.angle) : sample!.angle } : null;
    const bent = !!normalized && normalized.angle <= MOVEMENTS[this.id].limits.bent;
    if (dt <= 400 && reliable && this.lastValid) {
      this.valid += dt;
      if (bent && this.lastBent) this.held += dt;
    }
    this.lastValid = reliable; this.lastBent = bent;
    if (reliable) { this.min = Math.min(this.min, sample!.angle); this.max = Math.max(this.max, sample!.angle); }
    this.state = this.counter.update(normalized, now);
    // The state machine uses normalized angles; the person sees the actual joint estimate.
    const message = !reliable ? "Tracking paused. Keep the selected side and all required joints in view."
      : this.state.phase === "waiting" ? "Return to the starting position to begin."
      : this.state.phase === "ready" ? "Starting position detected. Ready to count."
      : "Movement detected. Return slowly to your starting position.";
    return { ...this.state, angle: reliable ? sample!.angle : null, message };
  }
  summary(): MovementSummary | null {
    if (this.started === null || this.last === null || !Number.isFinite(this.min) || this.last - this.started < 1000) return null;
    const duration = (this.last - this.started) / 1000;
    return { exercise_id: this.id, protocol: "movement-v1", side: this.side, reps: this.state.reps, partials: this.state.partials,
      min_angle: this.min, max_angle: this.max, hold_seconds: this.held / 1000,
      tracking_ratio: Math.min(1, this.valid / (this.last - this.started)), duration_seconds: duration };
  }
}
