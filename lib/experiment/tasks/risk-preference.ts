import instructions from "@jspsych/plugin-instructions";
import { trialCount } from "@/lib/constants";
import { pointsHud } from "@/lib/experiment/markup";
import TwoChoicePlugin from "@/lib/experiment/plugins/two-choice";
import { shuffle } from "@/lib/experiment/rng";
import type { ExperimentTimeline, SessionState } from "@/lib/types/experiment";

export function buildRiskPreference(
  session: SessionState,
  random: () => number,
): ExperimentTimeline {
  const n = trialCount(50, 6);
  const grid: Array<{ p: number; win: number }> = [];
  const probabilities = [0.2, 0.35, 0.5, 0.65, 0.8];
  const amounts = [80, 100, 120, 160, 200, 250, 300];
  for (const p of probabilities) {
    for (const win of amounts) {
      grid.push({ p, win });
    }
  }
  const schedule = shuffle(grid, random).slice(0, n);
  const safeAmount = 50;

  const trials: ExperimentTimeline = [
    {
      type: instructions,
      pages: [
        `<h1>Module 2 · Risk Preference</h1>
         <p>Each round, choose a guaranteed ${safeAmount} points or a gamble with a stated chance of a larger win.</p>
         <p>If you gamble, the wheel resolves immediately.</p>`,
      ],
      show_clickable_nav: true,
      allow_backward: false,
      button_label_next: "Continue",
    },
  ];

  schedule.forEach((item, index) => {
    const trialIndex = index + 1;
    trials.push({
      type: TwoChoicePlugin,
      prompt: "Choose your payout for this round:",
      left_label: "Safe",
      right_label: "Gamble",
      left_html: `Guaranteed <strong>${safeAmount}</strong> points`,
      right_html: `<strong>${Math.round(item.p * 100)}%</strong> chance to win <strong>${item.win}</strong><br/><span class="ns-muted">${Math.round((1 - item.p) * 100)}% chance of 0</span>`,
      hud_html: () => pointsHud(session.points),
      show_wheel: true,
      data: {
        loggable: true,
        task_id: "risk_pref",
        trial_index: trialIndex,
      },
      resolve_outcome: (choice: "left" | "right") => {
        const gambled = choice === "right";
        const won = gambled ? Math.random() < item.p : true;
        const points = gambled ? (won ? item.win : 0) : safeAmount;
        session.points += points;
        return {
          feedback_html: gambled
            ? won
              ? `<span class="ns-ok">Wheel lands on +${item.win}</span>`
              : `<span class="ns-bad">Wheel lands on 0</span>`
            : `<span class="ns-ok">+${safeAmount} guaranteed</span>`,
          extra_data: {
            action_taken: gambled ? "gamble" : "safe",
            points,
            state_vector: {
              safe_amount: safeAmount,
              gamble_probability: item.p,
              gamble_win_amount: item.win,
            },
            reward_received: { points, won: gambled ? won : true },
            latent_variables: {
              safe_amount: safeAmount,
              gamble_probability: item.p,
              gamble_win_amount: item.win,
              expected_value: item.p * item.win,
            },
          },
        };
      },
    });
  });

  return trials;
}
