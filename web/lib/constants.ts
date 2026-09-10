export const PARTICIPANT_AGES = [14, 15, 16, 17, 18] as const;

export const SCHOOL_CLASSES = [9, 10, 11, 12] as const;

export const SCHOOL_CLASS_LABELS: Record<(typeof SCHOOL_CLASSES)[number], string> = {
  9: "Class IX",
  10: "Class X",
  11: "Class XI",
  12: "Class XII",
};

export const TASK_IDS = [
  "prob_learning",
  "risk_pref",
  "delay_disc",
  "rule_discovery",
  "social_ultimatum",
] as const;

export const TASK_LABELS: Record<(typeof TASK_IDS)[number], string> = {
  prob_learning: "Probabilistic Learning",
  risk_pref: "Risk Preference",
  delay_disc: "Delay Discounting",
  rule_discovery: "Different Patterns: Discover the Rule That Connects Them",
  social_ultimatum: "Social Ultimatum",
};

export const PARTICIPANT_COOKIE = "ns_session";
export const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 8;

export const IS_DEMO = process.env.NEXT_PUBLIC_EXPERIMENT_MODE === "demo";

export function trialCount(full: number, demo = 4): number {
  return IS_DEMO ? demo : full;
}

export const COMPREHENSION_ITEMS = [
  {
    id: "voluntary",
    prompt: "Can you stop participating at any time without a penalty?",
    correct: true,
  },
  {
    id: "duration",
    prompt: "Will the five activities run as one continuous session for roughly 30 minutes?",
    correct: true,
  },
] as const;
