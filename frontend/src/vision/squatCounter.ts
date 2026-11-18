export interface Landmark {
  x: number;
  y: number;
  visibility?: number;
  presence?: number;
}

export interface PoseSample {
  angle: number;
  side: "left" | "right";
  points: Landmark[];
}

export const LIMITS = {
  standing: 160,
  bending: 145,
  bent: 110,
  confidence: 0.65,
  holdMs: 200,
  minimumCycleMs: 800,
  maximumCycleMs: 15_000,
  maximumGapMs: 400,
} as const;

// These are prototype counting thresholds, not clinical range-of-motion targets.
export function jointAngle(a: Landmark, b: Landmark, c: Landmark, width: number, height: number): number | null {
  const u = [(a.x - b.x) * width, (a.y - b.y) * height];
  const v = [(c.x - b.x) * width, (c.y - b.y) * height];
  const magnitude = Math.hypot(...u) * Math.hypot(...v);
  if (!Number.isFinite(magnitude) || magnitude < 1) return null;
  return Math.acos(Math.max(-1, Math.min(1, (u[0] * v[0] + u[1] * v[1]) / magnitude))) * 180 / Math.PI;
}

function visible(point: Landmark | undefined): point is Landmark {
  return !!point && Number.isFinite(point.x) && Number.isFinite(point.y)
    && point.x > 0.02 && point.x < 0.98 && point.y > 0.02 && point.y < 0.98
    && (point.visibility ?? 0) >= LIMITS.confidence
    && (point.presence === undefined || point.presence >= LIMITS.confidence);
}

export function readPose(poses: Landmark[][], width: number, height: number, preferredSide?: PoseSample["side"]): PoseSample | null {
  if (poses.length !== 1 || width <= 0 || height <= 0) return null;
  const pose = poses[0];
  const candidates: PoseSample[] = [];
  for (const [side, indices] of [["left", [11, 23, 25, 27]], ["right", [12, 24, 26, 28]]] as const) {
    const points = indices.map((index) => pose[index]);
    if (!points.every(visible)) continue;
    const [shoulder, hip, knee, ankle] = points;
    const angle = jointAngle(hip, knee, ankle, width, height);
    // Reject tiny detections and a horizontal torso; this demo expects an upright side view.
    if (angle === null || ankle.y - shoulder.y < 0.25 || hip.y - shoulder.y < 0.08) continue;
    candidates.push({ angle, side, points });
  }
  return candidates.find((candidate) => candidate.side === preferredSide) ?? candidates.sort((a, b) =>
    Math.min(...b.points.map((p) => p.visibility ?? 0)) - Math.min(...a.points.map((p) => p.visibility ?? 0)),
  )[0] ?? null;
}

export type CounterPhase = "waiting" | "ready" | "lowering" | "bent";
export interface CounterResult {
  reps: number;
  partials: number;
  phase: CounterPhase;
  message: string;
  angle: number | null;
}

export class SquatCounter {
  private limits: { standing: number; bending: number; bent: number };

  constructor(limits = { standing: 160, bending: 145, bent: 110 }) { this.limits = limits; }
  private reps = 0;
  private partials = 0;
  private phase: CounterPhase = "waiting";
  private side: PoseSample["side"] | null = null;
  private lastTime: number | null = null;
  private startedAt = 0;
  private band = "";
  private bandSince = 0;

  reset(): CounterResult {
    this.reps = 0;
    this.partials = 0;
    this.lastTime = null;
    this.interrupt();
    return this.result("Camera is off.", null);
  }

  private interrupt() {
    this.phase = "waiting";
    this.side = null;
    this.band = "";
    this.startedAt = 0;
  }

  private result(message: string, angle: number | null): CounterResult {
    return { reps: this.reps, partials: this.partials, phase: this.phase, message, angle };
  }

  update(sample: PoseSample | null, now: number): CounterResult {
    if (!Number.isFinite(now) || (this.lastTime !== null && now <= this.lastTime)) {
      this.interrupt();
      return this.result("Tracking paused. Stand in view to restart.", null);
    }
    const gap = this.lastTime !== null && now - this.lastTime > LIMITS.maximumGapMs;
    this.lastTime = now;
    if (!sample || !Number.isFinite(sample.angle) || sample.angle < 0 || sample.angle > 180) {
      this.interrupt();
      return this.result("Tracking paused. Keep one person’s shoulder, hip, knee and ankle in view.", null);
    }
    if (gap || (this.side !== null && this.side !== sample.side)) this.interrupt();
    this.side = sample.side;
    const band = sample.angle >= this.limits.standing ? "standing" : sample.angle <= this.limits.bent ? "bent"
      : sample.angle <= this.limits.bending ? "lowering" : "between";
    if (this.band !== band) { this.band = band; this.bandSince = now; }
    const stable = now - this.bandSince >= LIMITS.holdMs;
    if (this.startedAt && now - this.startedAt > LIMITS.maximumCycleMs) {
      this.interrupt();
      return this.result("Attempt timed out. Stand in view to restart.", sample.angle);
    }
    if (this.phase === "waiting") {
      if (band === "standing" && stable) this.phase = "ready";
    } else if (this.phase === "ready" && (band === "lowering" || band === "bent") && stable) {
      this.startedAt = this.bandSince;
      this.phase = band === "bent" ? "bent" : "lowering";
    } else if (this.phase === "lowering" && band === "bent" && stable) {
      this.phase = "bent";
    } else if ((this.phase === "lowering" || this.phase === "bent") && band === "standing" && stable) {
      if (this.phase === "bent" && now - this.startedAt >= LIMITS.minimumCycleMs) this.reps++;
      else this.partials++;
      this.phase = "ready";
      this.startedAt = 0;
    }
    const messages = {
      waiting: "Stand in view to begin a new cycle.",
      ready: "Standing detected. Ready to count.",
      lowering: "Movement detected. Cycle in progress.",
      bent: "Bent position detected. Waiting for a return to standing.",
    };
    return this.result(messages[this.phase], sample.angle);
  }
}
