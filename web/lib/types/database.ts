import type { PARTICIPANT_AGES, SCHOOL_CLASSES, TASK_IDS } from "@/lib/constants";

export type ParticipantAge = (typeof PARTICIPANT_AGES)[number];
export type SchoolClass = (typeof SCHOOL_CLASSES)[number];
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
  age: ParticipantAge;
  school_class: SchoolClass;
  session_start_timestamp: string;
  session_completed_timestamp: string | null;
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
  age: ParticipantAge;
  school_class: SchoolClass;
  session_start_timestamp?: string;
  session_completed_timestamp?: string | null;
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
