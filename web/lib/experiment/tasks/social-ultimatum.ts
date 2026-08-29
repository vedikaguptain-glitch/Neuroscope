import instructions from "@jspsych/plugin-instructions";
import { trialCount } from "@/lib/constants";
import { skippableTrial, trialMeta } from "@/lib/experiment/logic/meta";
import {
  BOT_OFFERS,
  ENDOWMENT,
  REJECT_BELOW,
  ROLE_BLOCK,
  roleAtTrial,
} from "@/lib/experiment/logic/ultimatum";
import { pointsHud } from "@/lib/experiment/markup";
import UltimatumPlugin from "@/lib/experiment/plugins/ultimatum";
import { sample } from "@/lib/experiment/rng";
import { completedTrials, shouldRunTaskTrial } from "@/lib/experiment/session-store";
import type { ExperimentTimeline, SessionState } from "@/lib/types/experiment";

export function buildSocialUltimatum(
  session: SessionState,
  random: () => number,
): ExperimentTimeline {
  const n = trialCount(40, 8);

  const trials: ExperimentTimeline = [
    skippableTrial(
      () => completedTrials("social_ultimatum") === 0,
      {
        type: instructions,
        pages: [
          `<h1>Module 5 · Social Ultimatum</h1>
           <p>You are paired with a partner for splits of a ${ENDOWMENT}-point endowment.</p>
           <p>If the responder rejects, both of you get 0. Roles switch every ${ROLE_BLOCK} trials.</p>`,
        ],
        show_clickable_nav: true,
        allow_backward: false,
        button_label_next: "Continue",
      },
    ),
  ];

  for (let i = 1; i <= n; i += 1) {
    const role = roleAtTrial(i);
    const botOffer = sample(BOT_OFFERS, random);

    trials.push(
      skippableTrial(
        () => shouldRunTaskTrial("social_ultimatum", i),
        {
          type: UltimatumPlugin,
          prompt:
            role === "proposer"
              ? `You have been given an endowment of ${ENDOWMENT} points. How much do you offer your partner? If they reject, you both get 0.`
              : `Your partner has ${ENDOWMENT} points. They offered you ${botOffer} points. Do you accept or reject?`,
          hud_html: () => pointsHud(session.points),
          role,
          endowment: ENDOWMENT,
          offer_amount: botOffer,
          reject_below: REJECT_BELOW,
          data: trialMeta("social_ultimatum", i),
          resolve_outcome: (result: {
            response: string;
            offer_amount: number;
            accepted: boolean;
            points: number;
            proposer_points: number;
            responder_points: number;
          }) => {
            session.points += result.points;
            return {
              action_taken: result.response,
              state_vector: {
                trial_role: role,
                endowment: ENDOWMENT,
                partner_offer: role === "responder" ? botOffer : null,
              },
              reward_received: {
                points: result.points,
                accepted: result.accepted,
                proposer_points: result.proposer_points,
                responder_points: result.responder_points,
              },
              latent_variables: {
                trial_role: role,
                endowment: ENDOWMENT,
                offer_amount: result.offer_amount,
                reject_below: REJECT_BELOW,
                bot_policy: "reject_below_20",
                bot_offer: role === "responder" ? botOffer : null,
              },
            };
          },
        },
      ),
    );
  }

  return trials;
}
