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
} as const;

export function getSessionStorage(): Storage | null {
  try {
    if (typeof window === "undefined") return null;
    return window.sessionStorage;
  } catch {
    return null;
  }
}

export function readJson<T>(key: string, fallback: T): T {
  const raw = getSessionStorage()?.getItem(key);
  if (!raw) return fallback;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

export function writeJson(key: string, value: unknown): void {
  getSessionStorage()?.setItem(key, JSON.stringify(value));
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
  return getSessionStorage()?.getItem(SESSION_KEYS.completed) === "1";
}

export function markSessionComplete(): void {
  getSessionStorage()?.setItem(SESSION_KEYS.completed, "1");
}

export function readSessionPoints(): number {
  const points = Number(getSessionStorage()?.getItem(SESSION_KEYS.points) ?? "0");
  return Number.isFinite(points) ? points : 0;
}

export function writeSessionPoints(points: number): void {
  getSessionStorage()?.setItem(SESSION_KEYS.points, String(points));
}

export function clearExperimentSession(): void {
  const storage = getSessionStorage();
  if (!storage) return;
  for (const key of Object.values(SESSION_KEYS)) {
    storage.removeItem(key);
  }
}
