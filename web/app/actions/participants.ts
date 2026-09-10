"use server";

import { z } from "zod";
import { PARTICIPANT_AGES, SCHOOL_CLASSES } from "@/lib/constants";
import {
  hashParticipantId,
  readParticipantIdFromCookie,
  setParticipantCookie,
} from "@/lib/session/participant-cookie";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import { getSessionSecret } from "@/lib/supabase/env";
import { seedFromString } from "@/lib/experiment/rng";
import type { ActionResult } from "@/lib/types/experiment";

const createParticipantSchema = z.object({
  age: z.number().refine(
    (value): value is (typeof PARTICIPANT_AGES)[number] =>
      PARTICIPANT_AGES.includes(value as (typeof PARTICIPANT_AGES)[number]),
  ),
  schoolClass: z.number().refine(
    (value): value is (typeof SCHOOL_CLASSES)[number] =>
      SCHOOL_CLASSES.includes(value as (typeof SCHOOL_CLASSES)[number]),
  ),
  comprehensionPassed: z.literal(true),
  consentAccepted: z.literal(true),
  guardianConsent: z.boolean(),
});

export async function createParticipant(
  input: unknown,
): Promise<ActionResult<{ publicId: string; seed: number }>> {
  const parsed = createParticipantSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false, error: "Please complete consent, comprehension, and demographics." };
  }

  if (parsed.data.age < 18 && !parsed.data.guardianConsent) {
    return {
      ok: false,
      error: "Participants under 18 need permission from a parent or guardian.",
    };
  }

  if (!getSessionSecret()) {
    return {
      ok: false,
      error: "SESSION_SECRET is missing. Add it to .env.local before starting a session.",
    };
  }

  const supabase = await createServerSupabaseClient();
  if (!supabase) {
    return {
      ok: false,
      error: "Supabase is not configured. Copy .env.example to .env.local and add your project keys.",
    };
  }

  const id = crypto.randomUUID();
  const sessionStart = new Date().toISOString();
  const publicId = await hashParticipantId(id, sessionStart);

  const { error } = await supabase.from("participants").insert({
    id,
    participant_id: publicId,
    age: parsed.data.age,
    school_class: parsed.data.schoolClass,
    session_start_timestamp: sessionStart,
    comprehension_passed: true,
  });

  if (error) {
    return { ok: false, error: error.message };
  }

  const cookieSet = await setParticipantCookie(id);
  if (!cookieSet) {
    return { ok: false, error: "Could not create a signed session cookie." };
  }

  const seed = seedFromString(publicId);

  return {
    ok: true,
    data: {
      publicId,
      seed,
    },
  };
}

export async function completeParticipantSession(): Promise<ActionResult> {
  const participantId = await readParticipantIdFromCookie();
  if (!participantId) {
    return { ok: false, error: "No active participant session." };
  }

  const supabase = await createServerSupabaseClient();
  if (!supabase) {
    return { ok: false, error: "Supabase is not configured." };
  }

  const { data, error } = await supabase.rpc("complete_participant_session", {
    target_participant_id: participantId,
  });

  if (error) {
    return { ok: false, error: error.message };
  }

  if (data !== true) {
    return { ok: false, error: "Could not find the active participant session." };
  }

  return { ok: true, data: undefined };
}
