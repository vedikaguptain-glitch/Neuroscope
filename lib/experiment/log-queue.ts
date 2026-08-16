import { logTrial } from "@/app/actions/trials";
import type { TrialLogPayload } from "@/lib/types/experiment";

const MAX_ATTEMPTS = 5;

export class TrialLogQueue {
  private queue: TrialLogPayload[] = [];
  private flushing = false;
  private failed = 0;

  get pending(): number {
    return this.queue.length;
  }

  get failures(): number {
    return this.failed;
  }

  enqueue(trial: TrialLogPayload) {
    this.queue.push(trial);
    void this.flush();
  }

  async drain(): Promise<void> {
    const started = Date.now();
    while (this.queue.length > 0 && Date.now() - started < 15_000) {
      await this.flush();
      if (this.queue.length > 0) {
        await new Promise((resolve) => setTimeout(resolve, 200));
      }
    }
  }

  private async flush() {
    if (this.flushing) return;
    this.flushing = true;

    while (this.queue.length > 0) {
      const item = this.queue[0]!;
      let attempt = 0;
      let success = false;

      while (attempt < MAX_ATTEMPTS && !success) {
        attempt += 1;
        const result = await logTrial(item);
        if (result.ok) {
          success = true;
          break;
        }
        await new Promise((resolve) => setTimeout(resolve, 250 * attempt));
      }

      this.queue.shift();
      if (!success) this.failed += 1;
    }

    this.flushing = false;
  }
}
