import { seedFromString } from "@/lib/experiment/rng";
import type { TrialLogPayload } from "@/lib/types/experiment";

const PREFIX = "ns_";

export const SESSION_KEYS = {
  publicId: `${PREFIX}public_id`,
  seed: `${PREFIX}seed`,
  points: `${PREFIX}points`,
  progress: `${PREFIX}progress`,
  delayChoices: `${PREFIX}delay_choices`,
  logQueue: `${PREFIX}log_queue`,
  failedLogs: `${PREFIX}failed_logs`,
  completed: `${PREFIX}completed`,
  summary: `${PREFIX}summary`,
} as const;

export interface SessionSummary {
  totalTrials: number;
  totalReactionTimeMs: number;
  fastestReactionTimeMs: number | null;
  riskChoices: number;
  gambleChoices: number;
  delayChoices: number;
  delayedChoices: number;
  patternChoices: number;
  correctPatternChoices: number;
}

const EMPTY_SUMMARY: SessionSummary = {
  totalTrials: 0,
  totalReactionTimeMs: 0,
  fastestReactionTimeMs: null,
  riskChoices: 0,
  gambleChoices: 0,
  delayChoices: 0,
  delayedChoices: 0,
  patternChoices: 0,
  correctPatternChoices: 0,
};

function storageOf(kind: "session" | "local"): Storage | null {
  try {
    if (typeof window === "undefined") return null;
    return kind === "session" ? window.sessionStorage : window.localStorage;
  } catch {
    return null;
  }
}

export function getSessionStorage(): Storage | null {
  return storageOf("session");
}

function getLocalStorage(): Storage | null {
  return storageOf("local");
}

function writeBoth(key: string, value: string): void {
  getSessionStorage()?.setItem(key, value);
  getLocalStorage()?.setItem(key, value);
}

function removeBoth(key: string): void {
  getSessionStorage()?.removeItem(key);
  getLocalStorage()?.removeItem(key);
}

export function readSessionItem(key: string): string | null {
  const session = getSessionStorage();
  const local = getLocalStorage();
  const fromSession = session?.getItem(key);
  if (fromSession != null) {
    if (local?.getItem(key) !== fromSession) {
      local?.setItem(key, fromSession);
    }
    return fromSession;
  }
  const fromLocal = local?.getItem(key) ?? null;
  if (fromLocal != null) {
    session?.setItem(key, fromLocal);
  }
  return fromLocal;
}

export function writeSessionItem(key: string, value: string): void {
  writeBoth(key, value);
}

export function readJson<T>(key: string, fallback: T): T {
  const raw = readSessionItem(key);
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function writeJson(key: string, value: unknown): void {
  writeSessionItem(key, JSON.stringify(value));
}

export function writeSessionIdentity(publicId: string, seed: number): void {
  writeSessionItem(SESSION_KEYS.publicId, publicId);
  writeSessionItem(SESSION_KEYS.seed, String(seed));
}

export function readPublicId(): string {
  return readSessionItem(SESSION_KEYS.publicId) ?? "unknown";
}

export function readSessionSeed(publicId: string): number {
  const raw = readSessionItem(SESSION_KEYS.seed);
  if (raw != null && raw !== "") {
    const stored = Number(raw);
    if (Number.isFinite(stored)) {
      return stored >>> 0;
    }
  }
  const derived = seedFromString(publicId);
  writeSessionItem(SESSION_KEYS.seed, String(derived));
  return derived;
}

export function readProgress(): Record<string, number> {
  const progress = readJson<Record<string, number>>(SESSION_KEYS.progress, {});
  return progress && typeof progress === "object" ? progress : {};
}

export function completedTrials(taskId: string): number {
  const value = readProgress()[taskId] ?? 0;
  return Number.isFinite(value) ? value : 0;
}

export function shouldRunTaskTrial(taskId: string, trialIndex: number): boolean {
  return trialIndex > completedTrials(taskId);
}

export function hasAnyProgress(): boolean {
  return Object.values(readProgress()).some((value) => value > 0);
}

export function recordTaskTrial(taskId: string, trialIndex: number): void {
  const progress = readProgress();
  progress[taskId] = Math.max(progress[taskId] ?? 0, trialIndex);
  writeJson(SESSION_KEYS.progress, progress);
}

export function recordTrialSummary(trial: TrialLogPayload): void {
  const summary = readJson<SessionSummary>(SESSION_KEYS.summary, EMPTY_SUMMARY);
  const reactionTime = Number.isFinite(trial.reaction_time_ms)
    ? trial.reaction_time_ms
    : 0;

  summary.totalTrials += 1;
  summary.totalReactionTimeMs += reactionTime;
  summary.fastestReactionTimeMs =
    reactionTime > 0
      ? Math.min(summary.fastestReactionTimeMs ?? reactionTime, reactionTime)
      : summary.fastestReactionTimeMs;

  if (trial.task_id === "risk_pref") {
    summary.riskChoices += 1;
    if (trial.action_taken === "gamble") summary.gambleChoices += 1;
  }

  if (trial.task_id === "delay_disc") {
    summary.delayChoices += 1;
    if (trial.action_taken === "delayed") summary.delayedChoices += 1;
  }

  if (trial.task_id === "rule_discovery") {
    summary.patternChoices += 1;
    if (trial.reward_received.outcome === "correct") {
      summary.correctPatternChoices += 1;
    }
  }

  writeJson(SESSION_KEYS.summary, summary);
}

export function readDelayChoices(): boolean[] {
  const choices = readJson<unknown>(SESSION_KEYS.delayChoices, []);
  if (!Array.isArray(choices)) return [];
  return choices.map((choice) => Boolean(choice));
}

export function appendDelayChoice(choseDelayed: boolean): void {
  const choices = readDelayChoices();
  choices.push(choseDelayed);
  writeJson(SESSION_KEYS.delayChoices, choices);
}

export function isSessionComplete(): boolean {
  return readSessionItem(SESSION_KEYS.completed) === "1";
}

export function markSessionComplete(): void {
  writeSessionItem(SESSION_KEYS.completed, "1");
}

export function readSessionPoints(): number {
  const points = Number(readSessionItem(SESSION_KEYS.points) ?? "0");
  return Number.isFinite(points) ? points : 0;
}

export function writeSessionPoints(points: number): void {
  writeSessionItem(SESSION_KEYS.points, String(points));
}

export function clearExperimentSession(): void {
  for (const key of Object.values(SESSION_KEYS)) {
    removeBoth(key);
  }
}
