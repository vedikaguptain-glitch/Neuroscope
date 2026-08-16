"use server";

import { z } from "zod";
import { TASK_IDS } from "@/lib/constants";
import { readParticipantIdFromCookie } from "@/lib/session/participant-cookie";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import type { Json } from "@/lib/types/database";
import type { ActionResult } from "@/lib/types/experiment";

const trialSchema = z.object({
  id: z.string().uuid(),
  task_id: z.enum(TASK_IDS),
  trial_index: z.number().int().min(0).max(10_000),
  state_vector: z.record(z.string(), z.unknown()),
  action_taken: z.string().min(1).max(128),
  reward_received: z.record(z.string(), z.unknown()),
  reaction_time_ms: z.number().min(0).max(600_000),
  latent_variables: z.record(z.string(), z.unknown()),
});

export async function logTrial(input: unknown): Promise<ActionResult> {
  const participantId = await readParticipantIdFromCookie();
  if (!participantId) {
    return { ok: false, error: "No active participant session." };
  }

  const parsed = trialSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false, error: "Invalid trial payload." };
  }

  const supabase = await createServerSupabaseClient();
  if (!supabase) {
    return { ok: false, error: "Supabase is not configured." };
  }

  const { error } = await supabase.from("trials").insert({
    id: parsed.data.id,
    participant_id: participantId,
    task_id: parsed.data.task_id,
    trial_index: parsed.data.trial_index,
    state_vector: parsed.data.state_vector as Json,
    action_taken: parsed.data.action_taken,
    reward_received: parsed.data.reward_received as Json,
    reaction_time_ms: parsed.data.reaction_time_ms,
    latent_variables: parsed.data.latent_variables as Json,
  });

  if (error) {
    if (error.code === "23505") {
      return { ok: true, data: undefined };
    }
    return { ok: false, error: error.message };
  }

  return { ok: true, data: undefined };
}
