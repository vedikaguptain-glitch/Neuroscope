import instructions from "@jspsych/plugin-instructions";
import { mulberry32 } from "@/lib/experiment/rng";
import { skippableTrial } from "@/lib/experiment/logic/meta";
import { hasAnyProgress } from "@/lib/experiment/session-store";
import { buildDelayDiscounting } from "@/lib/experiment/tasks/delay-discounting";
import { buildProbabilisticLearning } from "@/lib/experiment/tasks/probabilistic-learning";
import { buildRiskPreference } from "@/lib/experiment/tasks/risk-preference";
import { buildRuleDiscovery } from "@/lib/experiment/tasks/rule-discovery";
import { buildSocialUltimatum } from "@/lib/experiment/tasks/social-ultimatum";
import type { ExperimentTimeline, SessionState } from "@/lib/types/experiment";

export function createSessionState(
  publicId: string,
  seed: number,
  points = 0,
): SessionState {
  return { points, seed, publicId };
}

export function buildBatteryTimeline(session: SessionState): ExperimentTimeline {
  const random = mulberry32(session.seed);

  return [
    skippableTrial(
      () => !hasAnyProgress(),
      {
        type: instructions,
        pages: [
          `<h1>Your activities are ready</h1>
           <p>You will complete five short challenges in one continuous session.</p>
           <p>Stay on this page. Each activity begins when the previous one ends.</p>
           <p class="ns-note">Participant ${session.publicId}</p>`,
        ],
        show_clickable_nav: true,
        allow_backward: false,
        button_label_next: "Begin activities",
      },
    ),
    ...buildProbabilisticLearning(session, random),
    ...buildRiskPreference(session, random),
    ...buildDelayDiscounting(session),
    ...buildRuleDiscovery(session, random),
    ...buildSocialUltimatum(session, random),
  ];
}
