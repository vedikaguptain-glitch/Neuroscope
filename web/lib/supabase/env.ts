export function getSupabaseEnv(): { url: string; key: string } | null {
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const key = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

  if (!url || !key || url.includes("YOUR_PROJECT_REF") || key.includes("YOUR_KEY")) {
    return null;
  }

  return { url, key };
}

export function getSessionSecret(): string | null {
  const secret = process.env.SESSION_SECRET;
  if (!secret || secret.includes("replace-with")) {
    return null;
  }
  return secret;
}
