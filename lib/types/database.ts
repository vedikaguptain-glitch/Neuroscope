import type { AGE_BRACKETS, EDUCATION_LEVELS, TASK_IDS } from "@/lib/constants";

export type AgeBracket = (typeof AGE_BRACKETS)[number];
export type EducationLevel = (typeof EDUCATION_LEVELS)[number];
export type TaskId = (typeof TASK_IDS)[number];

export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[];

export interface ParticipantRow {
  id: string;
  participant_id: string;
  name: string;
  age_bracket: AgeBracket;
  education_level: EducationLevel;
  session_start_timestamp: string;
  comprehension_passed: boolean;
}

export interface TrialRow {
  id: string;
  participant_id: string;
  task_id: TaskId;
  trial_index: number;
  state_vector: Json;
  action_taken: string;
  reward_received: Json;
  reaction_time_ms: number;
  latent_variables: Json;
  created_at: string;
}

export type ParticipantInsert = {
  id?: string;
  participant_id: string;
  name: string;
  age_bracket: AgeBracket;
  education_level: EducationLevel;
  session_start_timestamp?: string;
  comprehension_passed: boolean;
};

export type TrialInsert = {
  id?: string;
  participant_id: string;
  task_id: TaskId;
  trial_index: number;
  state_vector?: Json;
  action_taken: string;
  reward_received?: Json;
  reaction_time_ms: number;
  latent_variables?: Json;
  created_at?: string;
};
