import instructions from "@jspsych/plugin-instructions";
import { trialCount } from "@/lib/constants";
import { pointsHud } from "@/lib/experiment/markup";
import TwoChoicePlugin from "@/lib/experiment/plugins/two-choice";
import type { ExperimentTimeline, SessionState } from "@/lib/types/experiment";

export function buildDelayDiscounting(session: SessionState): ExperimentTimeline {
  const n = trialCount(50, 6);
  let immediate = 100;
  let delayed = 150;
  let delayDays = 7;

  const trials: ExperimentTimeline = [
    {
      type: instructions,
      pages: [
        `<h1>Module 3 · Delay Discounting</h1>
         <p>Choose between a smaller amount now or a larger amount later.</p>
         <p>These points are banked for the session ledger. You will not see an immediate payout flash.</p>`,
      ],
      show_clickable_nav: true,
      allow_backward: false,
      button_label_next: "Continue",
    },
  ];

  for (let i = 1; i <= n; i += 1) {
    const currentImmediate = immediate;
    const currentDelayed = delayed;
    const currentDelay = delayDays;

    trials.push({
      type: TwoChoicePlugin,
      prompt: "Would you rather have:",
      left_label: "Now",
      right_label: "Later",
      left_html: `<strong>${currentImmediate}</strong> points right now`,
      right_html: `<strong>${currentDelayed}</strong> points in <strong>${currentDelay}</strong> days`,
      hud_html: () => pointsHud(session.points),
      feedback_duration: 450,
      data: {
        loggable: true,
        task_id: "delay_disc",
        trial_index: i,
      },
      resolve_outcome: (choice: "left" | "right") => {
        const tookDelayed = choice === "right";
        if (tookDelayed) {
          delayed = Math.max(currentImmediate + 10, delayed - 10);
          delayDays = Math.min(90, delayDays + 7);
        } else {
          delayed = Math.min(400, delayed + 15);
          delayDays = Math.max(1, delayDays - 3);
        }
        if (i % 10 === 0) {
          immediate = i % 20 === 0 ? 80 : 100;
        }
        return {
          feedback_html: `<span class="ns-muted">Choice banked</span>`,
          extra_data: {
            action_taken: tookDelayed ? "delayed" : "immediate",
            points: 0,
            state_vector: {
              immediate_reward: currentImmediate,
              delayed_reward: currentDelayed,
              delay_duration: currentDelay,
            },
            reward_received: { points: 0, banked: true },
            latent_variables: {
              immediate_reward: currentImmediate,
              delayed_reward: currentDelayed,
              delay_duration: currentDelay,
              chose_delayed: tookDelayed,
            },
          },
        };
      },
    });
  }

  return trials;
}
