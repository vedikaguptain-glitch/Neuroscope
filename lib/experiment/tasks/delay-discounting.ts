import instructions from "@jspsych/plugin-instructions";
import { trialCount } from "@/lib/constants";
import {
  replayDelayState,
  titrateDelay,
  type DelayState,
} from "@/lib/experiment/logic/delay-discounting";
import { skippableTrial, trialMeta } from "@/lib/experiment/logic/meta";
import { pointsHud } from "@/lib/experiment/markup";
import TwoChoicePlugin from "@/lib/experiment/plugins/two-choice";
import { completedTrials, readDelayChoices, shouldRunTaskTrial } from "@/lib/experiment/session-store";
import type { ExperimentTimeline, SessionState } from "@/lib/types/experiment";

export function buildDelayDiscounting(session: SessionState): ExperimentTimeline {
  const n = trialCount(50, 6);
  const titration: DelayState = replayDelayState(readDelayChoices());

  const trials: ExperimentTimeline = [
    skippableTrial(
      () => completedTrials("delay_disc") === 0,
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
    ),
  ];

  for (let i = 1; i <= n; i += 1) {
    trials.push(
      skippableTrial(
        () => shouldRunTaskTrial("delay_disc", i),
        {
          type: TwoChoicePlugin,
          prompt: "Would you rather have:",
          left_label: "Now",
          right_label: "Later",
          left_html: () => `<strong>${titration.immediate}</strong> points right now`,
          right_html: () =>
            `<strong>${titration.delayed}</strong> points in <strong>${titration.delayDays}</strong> days`,
          hud_html: () => pointsHud(session.points),
          feedback_duration: 450,
          data: trialMeta("delay_disc", i),
          resolve_outcome: (choice: "left" | "right") => {
            const shown = {
              immediate: titration.immediate,
              delayed: titration.delayed,
              delayDays: titration.delayDays,
            };
            const tookDelayed = choice === "right";
            const next = titrateDelay(titration, tookDelayed, i);
            titration.immediate = next.immediate;
            titration.delayed = next.delayed;
            titration.delayDays = next.delayDays;
            return {
              feedback_html: `<span class="ns-muted">Choice banked</span>`,
              extra_data: {
                action_taken: tookDelayed ? "delayed" : "immediate",
                points: 0,
                state_vector: {
                  immediate_reward: shown.immediate,
                  delayed_reward: shown.delayed,
                  delay_duration: shown.delayDays,
                },
                reward_received: { points: 0, banked: true },
                latent_variables: {
                  immediate_reward: shown.immediate,
                  delayed_reward: shown.delayed,
                  delay_duration: shown.delayDays,
                  chose_delayed: tookDelayed,
                  next_immediate_reward: titration.immediate,
                  next_delayed_reward: titration.delayed,
                  next_delay_duration: titration.delayDays,
                },
              },
            };
          },
        },
      ),
    );
  }

  return trials;
}
