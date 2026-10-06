// Mirrors backend/app/core/vocab.py and the Pydantic response schemas.
export const BODY_REGIONS = ["lower_back", "shoulder", "knee", "ankle", "neck", "hip", "wrist", "other"] as const;
export const LIMITATIONS = ["cannot_kneel", "cannot_lie_on_floor", "limited_overhead_reach", "poor_balance", "no_equipment"] as const;
export const ACTIVITIES = ["walking", "climbing_stairs", "squatting", "bending", "lifting", "reaching_overhead", "sitting_long", "running"] as const;
export const RED_FLAGS = ["numbness", "swelling", "loss_of_function", "pain_unrelated_to_activity"] as const;

export type BodyRegion = (typeof BODY_REGIONS)[number];

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

export const label = (s: string) => s.replace(/_/g, " ").replace(/^\w/, (c) => c.toUpperCase());
