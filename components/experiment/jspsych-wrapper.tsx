"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { initJsPsych } from "jspsych";
import { TrialLogQueue } from "@/lib/experiment/log-queue";
import { buildBatteryTimeline, createSessionState } from "@/lib/experiment/timeline";
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
  const [status, setStatus] = useState("Loading the task engine…");

  useEffect(() => {
    if (started.current || !hostRef.current) return;
    started.current = true;

    const publicId = sessionStorage.getItem("ns_public_id") ?? "unknown";
    const seed = Number(sessionStorage.getItem("ns_seed") ?? Date.now());
    const session = createSessionState(publicId, seed);
    const queue = new TrialLogQueue();
    const host = hostRef.current;

    const onLeave = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", onLeave);

    const jsPsych = initJsPsych({
      display_element: host,
      show_progress_bar: true,
      auto_update_progress_bar: true,
      message_progress_bar: "Battery progress",
      on_data_update: (data: Record<string, unknown>) => {
        const record = data as Record<string, unknown>;
        if (record.loggable !== true || !isTaskId(record.task_id)) return;

        const payload: TrialLogPayload = {
          id: crypto.randomUUID(),
          task_id: record.task_id,
          trial_index: Number(record.trial_index ?? 0),
          state_vector: (record.state_vector as Record<string, unknown>) ?? {},
          action_taken: String(record.action_taken ?? record.response ?? ""),
          reward_received: (record.reward_received as Record<string, unknown>) ?? {},
          reaction_time_ms: Number(record.rt ?? record.reaction_time_ms ?? 0),
          latent_variables: (record.latent_variables as Record<string, unknown>) ?? {},
        };

        if (!payload.action_taken) return;
        sessionStorage.setItem("ns_points", String(session.points));
        queue.enqueue(payload);
      },
      on_finish: async () => {
        window.removeEventListener("beforeunload", onLeave);
        setStatus("Saving remaining trials…");
        sessionStorage.setItem("ns_points", String(session.points));
        sessionStorage.setItem("ns_failed_logs", String(queue.failures));
        await queue.drain();
        router.replace("/complete");
      },
    });

    setStatus("");
        void jsPsych.run(buildBatteryTimeline(session) as never);

    return () => {
      window.removeEventListener("beforeunload", onLeave);
    };
  }, [router]);

  return (
    <div className="ns-shell">
      {status ? <p className="ns-status">{status}</p> : null}
      <div ref={hostRef} className="ns-host" />
    </div>
  );
}
