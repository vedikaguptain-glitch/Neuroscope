import instructions from "@jspsych/plugin-instructions";
import { trialCount } from "@/lib/constants";
import { pointsHud } from "@/lib/experiment/markup";
import TwoChoicePlugin from "@/lib/experiment/plugins/two-choice";
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

export function buildProbabilisticLearning(session: SessionState): ExperimentTimeline {
  const n = trialCount(100, 8);
  const reversalAt = Math.floor(n / 2) + 1;
  const trials: ExperimentTimeline = [];

  trials.push({
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
  });

  for (let i = 1; i <= n; i += 1) {
    const reversed = i >= reversalAt;
    const probA = reversed ? 0.2 : 0.8;
    const probB = reversed ? 0.8 : 0.2;

    trials.push({
      type: TwoChoicePlugin,
      prompt: "Which symbol will give you a point?",
      left_label: "Blue",
      right_label: "Red",
      left_html: fractal("blue"),
      right_html: fractal("red"),
      hud_html: () => pointsHud(session.points),
      data: {
        loggable: true,
        task_id: "prob_learning",
        trial_index: i,
      },
      resolve_outcome: (choice: "left" | "right") => {
        const pickedA = choice === "left";
        const p = pickedA ? probA : probB;
        const rewarded = Math.random() < p;
        const points = rewarded ? 1 : 0;
        session.points += points;
        return {
          feedback_html: rewarded
            ? `<span class="ns-ok">+1 Point</span>`
            : `<span class="ns-bad">0 Points</span>`,
          extra_data: {
            action_taken: pickedA ? "A" : "B",
            points,
            state_vector: {
              option_a: "blue_fractal",
              option_b: "red_fractal",
              trial: i,
            },
            reward_received: { points, outcome: rewarded ? "reward" : "omit" },
            latent_variables: {
              prob_reward_a: probA,
              prob_reward_b: probB,
              volatility_reversal: i === reversalAt,
              reversed,
            },
          },
        };
      },
    });
  }

  return trials;
}
