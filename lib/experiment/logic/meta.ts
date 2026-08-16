import type { TaskId } from "../../types/database";

export function trialMeta(taskId: TaskId, trialIndex: number) {
  return {
    loggable: true as const,
    task_id: taskId,
    task_trial_index: trialIndex,
  };
}

export function skippableTrial(
  shouldRun: () => boolean,
  trial: Record<string, unknown>,
): Record<string, unknown> {
  return {
    timeline: [trial],
    conditional_function: shouldRun,
  };
}
