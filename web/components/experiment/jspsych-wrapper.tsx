"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { initJsPsych } from "jspsych";
import { TrialLogQueue } from "@/lib/experiment/log-queue";
import { buildBatteryTimeline, createSessionState } from "@/lib/experiment/timeline";
import {
  appendDelayChoice,
  isSessionComplete,
  markSessionComplete,
  readPublicId,
  readSessionPoints,
  readSessionSeed,
  recordTaskTrial,
  recordTrialSummary,
  SESSION_KEYS,
  writeSessionItem,
  writeSessionPoints,
} from "@/lib/experiment/session-store";
import type { TaskId } from "@/lib/types/database";
import type { TrialLogPayload } from "@/lib/types/experiment";
import "@/app/experiment.css";

const TASK_IDS: TaskId[] = [
  "prob_learning",
  "risk_pref",
  "delay_disc",
  "rule_discovery",
  "social_ultimatum",
];

function isTaskId(value: unknown): value is TaskId {
  return typeof value === "string" && (TASK_IDS as string[]).includes(value);
}

export function JsPsychWrapper() {
  const router = useRouter();
  const hostRef = useRef<HTMLDivElement>(null);
  const started = useRef(false);
  const [status, setStatus] = useState("");

  useEffect(() => {
    if (started.current || !hostRef.current) return;
    started.current = true;

    const publicId = readPublicId();
    const seed = readSessionSeed(publicId);
    const session = createSessionState(publicId, seed, readSessionPoints());
    const queue = new TrialLogQueue();
    const host = hostRef.current;
    let cancelled = false;
    let jsPsychInstance: ReturnType<typeof initJsPsych> | null = null;

    const recordQueueStatus = () => {
      writeSessionItem(SESSION_KEYS.failedLogs, String(queue.failures + queue.pending));
    };

    const onLeave = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };

    void (async () => {
      if (queue.pending > 0) {
        setStatus("Saving remaining trials…");
        await queue.drain();
        recordQueueStatus();
      }
      if (cancelled) return;

      if (isSessionComplete() && queue.pending === 0) {
        router.replace("/complete");
        return;
      }

      window.addEventListener("beforeunload", onLeave);

      const jsPsych = initJsPsych({
        display_element: host,
        show_progress_bar: true,
        auto_update_progress_bar: true,
        message_progress_bar: "Battery progress",
        on_data_update: (data: Record<string, unknown>) => {
          const record = data as Record<string, unknown>;
          if (record.loggable !== true || !isTaskId(record.task_id)) return;

          const taskTrialIndex = Number(record.task_trial_index);
          if (!Number.isInteger(taskTrialIndex) || taskTrialIndex < 1) return;

          const payload: TrialLogPayload = {
            id: crypto.randomUUID(),
            task_id: record.task_id,
            trial_index: taskTrialIndex,
            state_vector: (record.state_vector as Record<string, unknown>) ?? {},
            action_taken: String(record.action_taken ?? record.response ?? ""),
            reward_received: (record.reward_received as Record<string, unknown>) ?? {},
            reaction_time_ms: Number(record.rt ?? record.reaction_time_ms ?? 0),
            latent_variables: (record.latent_variables as Record<string, unknown>) ?? {},
          };

          if (!payload.action_taken) return;
          writeSessionPoints(session.points);
          recordTaskTrial(payload.task_id, payload.trial_index);
          recordTrialSummary(payload);
          if (payload.task_id === "delay_disc") {
            appendDelayChoice(payload.action_taken === "delayed");
          }
          queue.enqueue(payload);
        },
        on_finish: async () => {
          window.removeEventListener("beforeunload", onLeave);
          jsPsychInstance = null;
          if (cancelled) return;
          setStatus("Saving remaining trials…");
          writeSessionPoints(session.points);
          await queue.drain();
          recordQueueStatus();
          if (queue.pending === 0) {
            markSessionComplete();
          }
          router.replace("/complete");
        },
      });
      jsPsychInstance = jsPsych;

      await jsPsych.run(buildBatteryTimeline(session) as never);
    })();

    return () => {
      cancelled = true;
      window.removeEventListener("beforeunload", onLeave);
      jsPsychInstance?.abortExperiment();
    };
  }, [router]);

  return (
    <div className="ns-shell">
      {status ? <p className="ns-status">{status}</p> : null}
      <div ref={hostRef} className="ns-host" />
    </div>
  );
}
