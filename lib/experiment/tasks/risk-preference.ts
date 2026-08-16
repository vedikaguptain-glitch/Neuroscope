import instructions from "@jspsych/plugin-instructions";
import { trialCount } from "@/lib/constants";
import { skippableTrial, trialMeta } from "@/lib/experiment/logic/meta";
import {
  buildRiskSchedule,
  expectedValue,
  riskPoints,
  SAFE_AMOUNT,
} from "@/lib/experiment/logic/risk-preference";
import { pointsHud } from "@/lib/experiment/markup";
import TwoChoicePlugin from "@/lib/experiment/plugins/two-choice";
import { completedTrials, shouldRunTaskTrial } from "@/lib/experiment/session-store";
import type { ExperimentTimeline, SessionState } from "@/lib/types/experiment";

export function buildRiskPreference(
  session: SessionState,
  random: () => number,
): ExperimentTimeline {
  const n = trialCount(50, 6);
  const schedule = buildRiskSchedule(n, random, SAFE_AMOUNT);

  const trials: ExperimentTimeline = [
    skippableTrial(
      () => completedTrials("risk_pref") === 0,
      {
        type: instructions,
        pages: [
          `<h1>Module 2 · Risk Preference</h1>
           <p>Each round, choose a guaranteed ${SAFE_AMOUNT} points or a gamble with a stated chance of a larger win.</p>
           <p>If you gamble, the wheel spins and then resolves.</p>`,
        ],
        show_clickable_nav: true,
        allow_backward: false,
        button_label_next: "Continue",
      },
    ),
  ];

  for (const item of schedule) {
    const safeHtml = `Guaranteed <strong>${item.safeAmount}</strong> points`;
    const gambleHtml = `<strong>${Math.round(item.p * 100)}%</strong> chance to win <strong>${item.win}</strong><br/><span class="ns-muted">${Math.round((1 - item.p) * 100)}% chance of 0</span>`;

    trials.push(
      skippableTrial(
        () => shouldRunTaskTrial("risk_pref", item.trialIndex),
        {
          type: TwoChoicePlugin,
          prompt: "Choose your payout for this round:",
          left_label: item.safeOnLeft ? "Safe" : "Gamble",
          right_label: item.safeOnLeft ? "Gamble" : "Safe",
          left_html: item.safeOnLeft ? safeHtml : gambleHtml,
          right_html: item.safeOnLeft ? gambleHtml : safeHtml,
          hud_html: () => pointsHud(session.points),
          data: trialMeta("risk_pref", item.trialIndex),
          resolve_outcome: (choice: "left" | "right") => {
            const gambled = item.safeOnLeft ? choice === "right" : choice === "left";
            const points = riskPoints(item, gambled);
            session.points += points;
            return {
              spin_wheel: gambled,
              feedback_html: gambled
                ? item.gambleWins
                  ? `<span class="ns-ok">Wheel lands on +${item.win}</span>`
                  : `<span class="ns-bad">Wheel lands on 0</span>`
                : `<span class="ns-ok">+${item.safeAmount} guaranteed</span>`,
              extra_data: {
                action_taken: gambled ? "gamble" : "safe",
                points,
                state_vector: {
                  safe_amount: item.safeAmount,
                  gamble_probability: item.p,
                  gamble_win_amount: item.win,
                  safe_side: item.safeOnLeft ? "left" : "right",
                },
                reward_received: {
                  points,
                  outcome: gambled ? (item.gambleWins ? "win" : "lose") : "safe",
                },
                latent_variables: {
                  safe_amount: item.safeAmount,
                  gamble_probability: item.p,
                  gamble_win_amount: item.win,
                  expected_value: expectedValue(item),
                  ev_minus_safe: expectedValue(item) - item.safeAmount,
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
