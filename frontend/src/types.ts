// Mirrors backend/app/core/vocab.py and the Pydantic response schemas.
export const BODY_REGIONS = ["lower_back", "shoulder", "knee", "ankle", "neck", "hip", "wrist", "other"] as const;
export const LIMITATIONS = ["cannot_kneel", "cannot_lie_on_floor", "limited_overhead_reach", "poor_balance", "no_equipment"] as const;
export const ACTIVITIES = ["walking", "climbing_stairs", "squatting", "bending", "lifting", "reaching_overhead", "sitting_long", "running"] as const;
export const RED_FLAGS = ["numbness", "swelling", "loss_of_function", "pain_unrelated_to_activity"] as const;

export type BodyRegion = (typeof BODY_REGIONS)[number];

export const SUPPORTED_REGIONS = ["lower_back", "shoulder", "knee", "ankle"] as const satisfies readonly BodyRegion[];
export const OTHER_REGIONS = ["neck", "hip", "wrist", "other"] as const satisfies readonly BodyRegion[];

export interface AssessmentCreate {
  body_region: BodyRegion;
  pain_level: number;
  limitations: string[];
  activity_difficulties: string[];
  red_flags: string[];
  description?: string;
}

export interface Assessment extends AssessmentCreate {
  id: number;
  in_scope: boolean;
  referral_reasons: string[];
  starting_difficulty: number | null;
  created_at: string;
}

export interface Exercise {
  id: string;
  name: string;
  body_regions: string[];
  difficulty: number;
  category: string;
  equipment: string | null;
  instructions: string[];
  sets_min: number;
  sets_max: number;
  reps_min: number;
  reps_max: number;
  media: string[];
  contraindications: string[];
  targets_activities: string[];
}

export interface Plan {
  id: number;
  status: string;
  difficulty_level: number;
  frequency_per_week: number;
  source: "ai" | "fallback";
  start_date: string;
  items: { exercise_id: string; position: number; sets: number; reps: number }[];
  schedule: { id: number; scheduled_date: string; week_index: number }[];
}

export interface SessionLog {
  id: number;
  plan_id: number;
  scheduled_session_id: number | null;
  performed_at: string;
  completed: boolean;
  pain_before: number;
  pain_after: number;
  perceived_difficulty: number;
}

export interface SessionCreate {
  scheduled_session_id: number | null;
  completed: boolean;
  pain_before: number;
  pain_after: number;
  perceived_difficulty: number;
  new_red_flags: string[];
  notes?: string;
}

export interface WeekStats {
  week_index: number;
  completion_rate: number;
  avg_post_pain: number | null;
  max_session_pain: number | null;
  pain_change: number | null;
  missed_sessions: number;
}

export interface Progress {
  plan_id: number;
  weeks: WeekStats[];
  explanation: string;
}

export interface Notification {
  id: number;
  kind: string;
  message: string;
  send_at: string;
  read: boolean;
}

export const label = (s: string) => s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());

const COPY: Record<string, string> = {
  lower_back: "Lower back", other: "Somewhere else", cannot_kneel: "I can't kneel",
  cannot_lie_on_floor: "I can't get down on the floor", limited_overhead_reach: "I can't reach overhead comfortably",
  poor_balance: "My balance isn't great", no_equipment: "I don't have any equipment",
  sitting_long: "Sitting for a long time", reaching_overhead: "Reaching overhead",
};
export const copy = (s: string) => COPY[s] ?? label(s);

export const RED_FLAG_COPY: Record<string, { title: string; hint: string }> = {
  numbness: { title: "Numbness or tingling", hint: "Pins and needles or loss of feeling in an arm, leg, hand, or foot" },
  swelling: { title: "Noticeable swelling", hint: "The area looks puffy or bigger than the other side" },
  loss_of_function: { title: "Can't use it normally", hint: "You can't put weight on it, grip, or move it the way you usually can" },
  pain_unrelated_to_activity: { title: "Pain that doesn't change with movement", hint: "It hurts at rest or at night no matter what you do" },
};

export function referralText(reason: string): string {
  const [kind, value = ""] = reason.split(":");
  if (kind === "unsupported_region") return `LIMBER only covers the lower back, shoulder, knee, and ankle (you chose ${copy(value).toLowerCase()}).`;
  if (kind === "pain_too_high") return `Your pain level (${value}/10) is higher than a self-guided plan should handle.`;
  if (kind === "red_flag") return `You reported: ${RED_FLAG_COPY[value]?.title.toLowerCase() ?? label(value).toLowerCase()}.`;
  return label(reason);
}
