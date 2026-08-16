import instructions from "@jspsych/plugin-instructions";
import { mulberry32 } from "@/lib/experiment/rng";
import { buildDelayDiscounting } from "@/lib/experiment/tasks/delay-discounting";
import { buildProbabilisticLearning } from "@/lib/experiment/tasks/probabilistic-learning";
import { buildRiskPreference } from "@/lib/experiment/tasks/risk-preference";
import { buildRuleDiscovery } from "@/lib/experiment/tasks/rule-discovery";
import { buildSocialUltimatum } from "@/lib/experiment/tasks/social-ultimatum";
import type { ExperimentTimeline, SessionState } from "@/lib/types/experiment";

export function createSessionState(publicId: string, seed: number): SessionState {
  return { points: 0, seed, publicId };
}

export function buildBatteryTimeline(session: SessionState): ExperimentTimeline {
  const random = mulberry32(session.seed);

  return [
    {
      type: instructions,
      pages: [
        `<h1>NEUROSCOPE</h1>
         <p>You will complete five decision-making modules in one continuous session.</p>
         <p>Stay on this page. Each module starts when the previous one ends.</p>
         <p class="ns-note">Participant ${session.publicId}</p>`,
      ],
      show_clickable_nav: true,
      allow_backward: false,
      button_label_next: "Begin battery",
    },
    ...buildProbabilisticLearning(session),
    ...buildRiskPreference(session, random),
    ...buildDelayDiscounting(session),
    ...buildRuleDiscovery(session, random),
    ...buildSocialUltimatum(session, random),
  ];
}
