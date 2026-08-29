import instructions from "@jspsych/plugin-instructions";
import { trialCount } from "@/lib/constants";
import {
  buildProbLearningSchedule,
  rewardForSymbol,
  symbolOnSide,
} from "@/lib/experiment/logic/prob-learning";
import { skippableTrial, trialMeta } from "@/lib/experiment/logic/meta";
import { pointsHud } from "@/lib/experiment/markup";
import TwoChoicePlugin from "@/lib/experiment/plugins/two-choice";
import { completedTrials, shouldRunTaskTrial } from "@/lib/experiment/session-store";
import type { ExperimentTimeline, SessionState } from "@/lib/types/experiment";

function fractal(kind: "blue" | "red"): string {
  const color = kind === "blue" ? "#38bdf8" : "#fb7185";
  const pattern =
    kind === "blue"
      ? `<polygon points="64,8 120,120 8,120" fill="none" stroke="${color}" stroke-width="3"/>
         <polygon points="64,28 104,108 24,108" fill="none" stroke="${color}" stroke-width="2"/>
         <circle cx="64" cy="72" r="18" fill="${color}" opacity="0.35"/>`
      : `<rect x="18" y="18" width="92" height="92" rx="8" fill="none" stroke="${color}" stroke-width="3" transform="rotate(12 64 64)"/>
         <rect x="34" y="34" width="60" height="60" rx="6" fill="none" stroke="${color}" stroke-width="2" transform="rotate(-8 64 64)"/>
         <circle cx="64" cy="64" r="16" fill="${color}" opacity="0.4"/>`;
  return `<svg class="ns-fractal" viewBox="0 0 128 128" aria-hidden="true">${pattern}</svg>`;
}

const SYMBOL = {
  A: { id: "blue_fractal" as const, label: "Blue", html: fractal("blue") },
  B: { id: "red_fractal" as const, label: "Red", html: fractal("red") },
};

export function buildProbabilisticLearning(
  session: SessionState,
  random: () => number,
): ExperimentTimeline {
  const n = trialCount(60, 8);
  const schedule = buildProbLearningSchedule(n, random);
  const trials: ExperimentTimeline = [];

  trials.push(
    skippableTrial(
      () => completedTrials("prob_learning") === 0,
      {
        type: instructions,
        pages: [
          `<h1>Module 1 · Probabilistic Learning</h1>
           <p>Two symbols will appear. One is more likely to pay a point, but it is noisy.</p>
           <p>The better symbol can change without warning. Choose the symbol you think will pay.</p>
           <p class="ns-note">Do not refresh this page. The next modules will start automatically.</p>`,
        ],
        show_clickable_nav: true,
        allow_backward: false,
        button_label_next: "Start",
      },
    ),
  );

  for (const item of schedule) {
    const left = SYMBOL[item.leftSymbol];
    const right = SYMBOL[symbolOnSide(item, "right")];

    trials.push(
      skippableTrial(
        () => shouldRunTaskTrial("prob_learning", item.trialIndex),
        {
          type: TwoChoicePlugin,
          prompt: "Which symbol will give you a point?",
          left_label: left.label,
          right_label: right.label,
          left_html: left.html,
          right_html: right.html,
          hud_html: () => pointsHud(session.points),
          data: trialMeta("prob_learning", item.trialIndex),
          resolve_outcome: (choice: "left" | "right") => {
            const symbol = symbolOnSide(item, choice);
            const rewarded = rewardForSymbol(item, symbol);
            const points = rewarded ? 1 : 0;
            session.points += points;
            return {
              feedback_html: rewarded
                ? `<span class="ns-ok">+1 Point</span>`
                : `<span class="ns-bad">0 Points</span>`,
              extra_data: {
                action_taken: symbol,
                points,
                state_vector: {
                  option_a: SYMBOL.A.id,
                  option_b: SYMBOL.B.id,
                  left_symbol: item.leftSymbol,
                  right_symbol: symbolOnSide(item, "right"),
                  trial: item.trialIndex,
                },
                reward_received: { points, outcome: rewarded ? "reward" : "omit" },
                latent_variables: {
                  prob_reward_a: item.probA,
                  prob_reward_b: item.probB,
                  volatility_reversal: item.volatilityReversal,
                  reversed: item.reversed,
                  chosen_side: choice,
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
