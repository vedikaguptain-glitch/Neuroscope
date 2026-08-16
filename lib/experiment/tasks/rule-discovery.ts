import instructions from "@jspsych/plugin-instructions";
import { trialCount } from "@/lib/constants";
import { skippableTrial, trialMeta } from "@/lib/experiment/logic/meta";
import {
  diagnosticTarget,
  KEY_CARDS,
  ruleAtTrial,
} from "@/lib/experiment/logic/rule-discovery";
import { pointsHud } from "@/lib/experiment/markup";
import RuleMatchPlugin from "@/lib/experiment/plugins/rule-match";
import { completedTrials, shouldRunTaskTrial } from "@/lib/experiment/session-store";
import type { ExperimentTimeline, SessionState } from "@/lib/types/experiment";

export function buildRuleDiscovery(
  session: SessionState,
  random: () => number,
): ExperimentTimeline {
  const n = trialCount(60, 8);

  const trials: ExperimentTimeline = [
    skippableTrial(
      () => completedTrials("rule_discovery") === 0,
      {
        type: instructions,
        pages: [
          `<h1>Module 4 · Rule Discovery</h1>
           <p>Match the center card to one of the four corner cards. The matching rule is hidden.</p>
           <p>The rule can shift without warning. Use the Correct / Incorrect feedback to rediscover it.</p>`,
        ],
        show_clickable_nav: true,
        allow_backward: false,
        button_label_next: "Continue",
      },
    ),
  ];

  for (let i = 1; i <= n; i += 1) {
    const { rule, ruleShift } = ruleAtTrial(i, n);
    const { target, matchIndex } = diagnosticTarget(random);
    const correctIndex = matchIndex[rule];

    trials.push(
      skippableTrial(
        () => shouldRunTaskTrial("rule_discovery", i),
        {
          type: RuleMatchPlugin,
          prompt: "Match the center card. The rule is hidden.",
          hud_html: () => pointsHud(session.points),
          target,
          options: KEY_CARDS,
          correct_index: correctIndex,
          data: trialMeta("rule_discovery", i),
          resolve_outcome: (choice: { response: number; correct: boolean }) => {
            const points = choice.correct ? 1 : 0;
            session.points += points;
            return {
              action_taken: String(choice.response),
              points,
              state_vector: {
                target,
                options: KEY_CARDS,
                color_match_index: matchIndex.color,
                shape_match_index: matchIndex.shape,
                number_match_index: matchIndex.number,
              },
              reward_received: {
                points,
                outcome: choice.correct ? "correct" : "incorrect",
              },
              latent_variables: {
                current_rule_id: rule,
                rule_shift: ruleShift,
                correct_index: correctIndex,
              },
            };
          },
        },
      ),
    );
  }

  return trials;
}
