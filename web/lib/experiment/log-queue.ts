import { logTrial } from "@/app/actions/trials";
import { readJson, SESSION_KEYS, writeJson } from "@/lib/experiment/session-store";
import type { TrialLogPayload } from "@/lib/types/experiment";

const MAX_ATTEMPTS = 5;

function delay(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export class TrialLogQueue {
  private queue: TrialLogPayload[] = [];
  private chain: Promise<void> = Promise.resolve();

  constructor() {
    const stored = readJson<TrialLogPayload[]>(SESSION_KEYS.logQueue, []);
    if (Array.isArray(stored)) {
      this.queue = stored.filter((item) => item && typeof item.id === "string");
    }
    if (this.queue.length > 0) {
      this.chain = this.chain.then(() => this.flushOnce());
    }
  }

  get pending(): number {
    return this.queue.length;
  }

  enqueue(trial: TrialLogPayload) {
    this.queue.push(trial);
    this.persist();
    this.chain = this.chain.then(() => this.flushOnce());
  }

  async drain(): Promise<void> {
    const started = Date.now();
    this.chain = this.chain.then(() => this.flushOnce());
    await this.chain;
    while (this.queue.length > 0 && Date.now() - started < 30_000) {
      await delay(400);
      this.chain = this.chain.then(() => this.flushOnce());
      await this.chain;
    }
    this.persist();
  }

  private persist() {
    writeJson(SESSION_KEYS.logQueue, this.queue);
  }

  private async flushOnce() {
    while (this.queue.length > 0) {
      const item = this.queue[0]!;
      let success = false;

      for (let attempt = 1; attempt <= MAX_ATTEMPTS; attempt += 1) {
        const result = await logTrial(item);
        if (result.ok) {
          success = true;
          break;
        }
        await delay(250 * attempt);
      }

      if (!success) {
        return;
      }

      this.queue.shift();
      this.persist();
    }
  }
}
