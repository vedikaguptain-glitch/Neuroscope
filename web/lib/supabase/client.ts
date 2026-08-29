import { createBrowserClient } from "@supabase/ssr";
import { getSupabaseEnv } from "@/lib/supabase/env";

export function createBrowserSupabaseClient() {
  const env = getSupabaseEnv();
  if (!env) {
    throw new Error("Supabase environment variables are not configured.");
  }

  return createBrowserClient(env.url, env.key);
}
