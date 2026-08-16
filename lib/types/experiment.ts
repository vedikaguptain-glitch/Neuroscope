import type { TaskId } from "@/lib/types/database";

export interface TrialLogPayload {
  id: string;
  task_id: TaskId;
  trial_index: number;
  state_vector: Record<string, unknown>;
  action_taken: string;
  reward_received: Record<string, unknown>;
  reaction_time_ms: number;
  latent_variables: Record<string, unknown>;
}

export interface SessionState {
  points: number;
  seed: number;
  publicId: string;
}

export type ActionResult<T = undefined> =
  | { ok: true; data: T }
  | { ok: false; error: string };

export type ExperimentTimeline = Array<Record<string, unknown>>;
