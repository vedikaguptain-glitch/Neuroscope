"use server";

import { z } from "zod";
import { AGE_BRACKETS, EDUCATION_LEVELS } from "@/lib/constants";
import {
  hashParticipantId,
  setParticipantCookie,
} from "@/lib/session/participant-cookie";
import { createServerSupabaseClient } from "@/lib/supabase/server";
import { getSessionSecret } from "@/lib/supabase/env";
import { seedFromString } from "@/lib/experiment/rng";
import type { ActionResult } from "@/lib/types/experiment";

const createParticipantSchema = z.object({
  name: z.string().trim().min(1).max(100),
  ageBracket: z.enum(AGE_BRACKETS),
  educationLevel: z.enum(EDUCATION_LEVELS),
  comprehensionPassed: z.literal(true),
  consentAccepted: z.literal(true),
  guardianConsent: z.boolean(),
});

export async function createParticipant(
  input: unknown,
): Promise<ActionResult<{ publicId: string; seed: number }>> {
  const parsed = createParticipantSchema.safeParse(input);
  if (!parsed.success) {
    return { ok: false, error: "Please complete consent, comprehension, name, and demographics." };
  }

  if (parsed.data.ageBracket === "13-17" && !parsed.data.guardianConsent) {
    return {
      ok: false,
      error: "Participants aged 13–17 need a parent or guardian to consent.",
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
    name: parsed.data.name,
    age_bracket: parsed.data.ageBracket,
    education_level: parsed.data.educationLevel,
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
