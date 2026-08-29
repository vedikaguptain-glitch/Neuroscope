import { cookies } from "next/headers";
import {
  COOKIE_MAX_AGE_SECONDS,
  PARTICIPANT_COOKIE,
} from "@/lib/constants";
import { getSessionSecret } from "@/lib/supabase/env";

function bytesToBase64Url(bytes: ArrayBuffer): string {
  return Buffer.from(bytes).toString("base64url");
}

async function hmac(value: string, secret: string): Promise<string> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(secret),
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const signature = await crypto.subtle.sign(
    "HMAC",
    key,
    new TextEncoder().encode(value),
  );
  return bytesToBase64Url(signature);
}

export async function signParticipantId(participantUuid: string): Promise<string | null> {
  const secret = getSessionSecret();
  if (!secret) return null;
  const signature = await hmac(participantUuid, secret);
  return `${participantUuid}.${signature}`;
}

export async function readParticipantIdFromCookie(): Promise<string | null> {
  const secret = getSessionSecret();
  if (!secret) return null;

  const cookieStore = await cookies();
  const raw = cookieStore.get(PARTICIPANT_COOKIE)?.value;
  if (!raw) return null;

  const separator = raw.lastIndexOf(".");
  if (separator <= 0) return null;

  const uuid = raw.slice(0, separator);
  const provided = raw.slice(separator + 1);
  const expected = await hmac(uuid, secret);

  if (provided.length !== expected.length) return null;

  let mismatch = 0;
  for (let i = 0; i < expected.length; i += 1) {
    mismatch |= provided.charCodeAt(i) ^ expected.charCodeAt(i);
  }
  if (mismatch !== 0) return null;

  return uuid;
}

export async function setParticipantCookie(participantUuid: string): Promise<boolean> {
  const signed = await signParticipantId(participantUuid);
  if (!signed) return false;

  const cookieStore = await cookies();
  cookieStore.set(PARTICIPANT_COOKIE, signed, {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: COOKIE_MAX_AGE_SECONDS,
  });
  return true;
}

export async function hashParticipantId(uuid: string, timestamp: string): Promise<string> {
  const payload = `${uuid}:${timestamp}:${crypto.randomUUID()}`;
  const digest = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(payload),
  );
  return bytesToBase64Url(digest).slice(0, 22);
}
