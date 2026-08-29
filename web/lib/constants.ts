export const AGE_BRACKETS = [
  "13-17",
  "18-24",
  "25-34",
  "35-44",
  "45-54",
  "55-64",
  "65+",
] as const;

export const EDUCATION_LEVELS = [
  "high_school",
  "some_college",
  "bachelors",
  "masters",
  "doctoral",
  "other",
] as const;

export const EDUCATION_LABELS: Record<(typeof EDUCATION_LEVELS)[number], string> = {
  high_school: "High school or equivalent",
  some_college: "Some college",
  bachelors: "Bachelor's degree",
  masters: "Master's degree",
  doctoral: "Doctoral degree",
  other: "Other",
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
    id: "anonymous",
    prompt: "Will we collect or store your name?",
    correct: false,
  },
  {
    id: "duration",
    prompt: "Will the five activities run as one continuous session for roughly 30 minutes?",
    correct: true,
  },
] as const;
