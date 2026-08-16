import instructions from "@jspsych/plugin-instructions";
import { trialCount } from "@/lib/constants";
import { pointsHud } from "@/lib/experiment/markup";
import RuleMatchPlugin, {
  type CardSpec,
} from "@/lib/experiment/plugins/rule-match";
import { sample } from "@/lib/experiment/rng";
import type { ExperimentTimeline, SessionState } from "@/lib/types/experiment";

const COLORS: CardSpec["color"][] = ["red", "green", "blue", "yellow"];
const SHAPES: CardSpec["shape"][] = ["triangle", "star", "plus", "circle"];
const COUNTS: CardSpec["count"][] = [1, 2, 3, 4];

const KEY_CARDS: CardSpec[] = [
  { color: "red", shape: "triangle", count: 1 },
  { color: "green", shape: "star", count: 2 },
  { color: "yellow", shape: "plus", count: 3 },
  { color: "blue", shape: "circle", count: 4 },
];

type RuleId = "color" | "shape" | "number";

function matches(rule: RuleId, target: CardSpec, option: CardSpec): boolean {
  if (rule === "color") return target.color === option.color;
  if (rule === "shape") return target.shape === option.shape;
  return target.count === option.count;
}

function randomTarget(random: () => number): CardSpec {
  return {
    color: sample(COLORS, random),
    shape: sample(SHAPES, random),
    count: sample(COUNTS, random),
  };
}

export function buildRuleDiscovery(
  session: SessionState,
  random: () => number,
): ExperimentTimeline {
  const n = trialCount(60, 8);
  const block = Math.max(2, Math.floor(n / 4));
  const rules: RuleId[] = ["color", "shape", "number", "color"];

  const trials: ExperimentTimeline = [
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
  ];

  for (let i = 1; i <= n; i += 1) {
    const ruleIndex = Math.min(rules.length - 1, Math.floor((i - 1) / block));
    const currentRule = rules[ruleIndex]!;
    const previousRule = i === 1 ? currentRule : rules[Math.min(rules.length - 1, Math.floor((i - 2) / block))]!;
    const ruleShift = currentRule !== previousRule;
    const target = randomTarget(random);
    const correctIndex = KEY_CARDS.findIndex((card) => matches(currentRule, target, card));

    trials.push({
      type: RuleMatchPlugin,
      prompt: "Match the center card. The rule is hidden.",
      hud_html: () => pointsHud(session.points),
      target,
      options: KEY_CARDS,
      correct_index: correctIndex < 0 ? 0 : correctIndex,
      data: {
        loggable: true,
        task_id: "rule_discovery",
        trial_index: i,
      },
      on_finish: (data: { correct?: boolean; response?: number }) => {
        const points = data.correct ? 1 : 0;
        session.points += points;
        Object.assign(data, {
          action_taken: String(data.response ?? ""),
          points,
          state_vector: {
            target,
            options: KEY_CARDS,
          },
          reward_received: {
            points,
            outcome: data.correct ? "correct" : "incorrect",
          },
          latent_variables: {
            current_rule_id: currentRule,
            rule_shift: ruleShift,
          },
        });
      },
    });
  }

  return trials;
}
