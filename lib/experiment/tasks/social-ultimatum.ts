import instructions from "@jspsych/plugin-instructions";
import { trialCount } from "@/lib/constants";
import { pointsHud } from "@/lib/experiment/markup";
import UltimatumPlugin from "@/lib/experiment/plugins/ultimatum";
import { sample } from "@/lib/experiment/rng";
import type { ExperimentTimeline, SessionState } from "@/lib/types/experiment";

const BOT_OFFERS = [10, 15, 20, 25, 30, 40, 50] as const;
const REJECT_BELOW = 20;
const ENDOWMENT = 100;

export function buildSocialUltimatum(
  session: SessionState,
  random: () => number,
): ExperimentTimeline {
  const n = trialCount(40, 8);
  const block = 5;

  const trials: ExperimentTimeline = [
    {
      type: instructions,
      pages: [
        `<h1>Module 5 · Social Ultimatum</h1>
         <p>You are paired with a partner for splits of a ${ENDOWMENT}-point endowment.</p>
         <p>If the responder rejects, both of you get 0. Roles switch every ${block} trials.</p>`,
      ],
      show_clickable_nav: true,
      allow_backward: false,
      button_label_next: "Continue",
    },
  ];

  for (let i = 1; i <= n; i += 1) {
    const blockIndex = Math.floor((i - 1) / block);
    const role = blockIndex % 2 === 0 ? "proposer" : "responder";
    const botOffer = sample(BOT_OFFERS, random);

    trials.push({
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
      data: {
        loggable: true,
        task_id: "social_ultimatum",
        trial_index: i,
      },
      on_finish: (data: {
        response?: string;
        points?: number;
        accepted?: boolean;
        offer_amount?: number;
      }) => {
        const points = data.points ?? 0;
        session.points += points;
        Object.assign(data, {
          action_taken: String(data.response ?? ""),
          state_vector: {
            trial_role: role,
            endowment: ENDOWMENT,
            partner_offer: role === "responder" ? botOffer : null,
          },
          reward_received: {
            points,
            accepted: Boolean(data.accepted),
          },
          latent_variables: {
            trial_role: role,
            endowment: ENDOWMENT,
            offer_amount: data.offer_amount ?? botOffer,
            reject_below: REJECT_BELOW,
            bot_policy: "reject_below_20",
          },
        });
      },
    });
  }

  return trials;
}
