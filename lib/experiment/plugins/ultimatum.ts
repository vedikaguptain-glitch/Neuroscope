import { JsPsych, JsPsychPlugin, ParameterType, TrialType } from "jspsych";
import { clampOffer, splitPayoff } from "@/lib/experiment/logic/ultimatum";
import { renderHtml } from "@/lib/experiment/markup";

export interface UltimatumResult {
  response: string;
  offer_amount: number;
  accepted: boolean;
  points: number;
  proposer_points: number;
  responder_points: number;
}

const info = {
  name: "neuroscope-ultimatum",
  version: "1.1.0",
  parameters: {
    prompt: { type: ParameterType.HTML_STRING, default: "" },
    hud_html: { type: ParameterType.HTML_STRING, default: "" },
    role: { type: ParameterType.STRING, default: "proposer" },
    endowment: { type: ParameterType.INT, default: 100 },
    offer_amount: { type: ParameterType.INT, default: 20 },
    feedback_duration: { type: ParameterType.INT, default: 1100 },
    reject_below: { type: ParameterType.INT, default: 20 },
    resolve_outcome: {
      type: ParameterType.FUNCTION,
      default: () => ({}),
    },
  },
  data: {
    rt: { type: ParameterType.FLOAT },
    response: { type: ParameterType.STRING },
  },
} as const;

type Info = typeof info;

export default class UltimatumPlugin implements JsPsychPlugin<Info> {
  static readonly info = info;

  constructor(private jsPsych: JsPsych) {}

  trial(display_element: HTMLElement, trial: TrialType<Info>) {
    const isProposer = trial.role === "proposer";
    const endowment = trial.endowment ?? 100;
    const offerAmount = clampOffer(trial.offer_amount ?? 20, endowment);
    const rejectBelow = trial.reject_below ?? 20;
    const feedbackDuration = trial.feedback_duration ?? 1100;

    display_element.innerHTML = `
      <div class="ns-trial">
        ${renderHtml(trial.hud_html)}
        <p class="ns-prompt">${renderHtml(trial.prompt)}</p>
        ${
          isProposer
            ? `
              <div class="ns-offer">
                <label class="ns-offer-label">
                  Offer to partner
                  <input class="ns-slider" type="range" min="0" max="${endowment}" step="1" value="${Math.round(endowment / 2)}" />
                </label>
                <p class="ns-offer-readout">You keep <strong data-keep></strong> · Partner gets <strong data-offer></strong></p>
                <button type="button" class="ns-submit">Submit offer</button>
              </div>
            `
            : `
              <div class="ns-options">
                <button type="button" class="ns-option" data-choice="accept">
                  <span class="ns-option-kicker">Accept</span>
                  <span class="ns-option-body">Take ${offerAmount} points</span>
                </button>
                <button type="button" class="ns-option" data-choice="reject">
                  <span class="ns-option-kicker">Reject</span>
                  <span class="ns-option-body">Both get 0</span>
                </button>
              </div>
            `
        }
        <div class="ns-feedback" hidden></div>
      </div>
    `;

    const start = performance.now();
    const feedback = display_element.querySelector<HTMLElement>(".ns-feedback");
    let settled = false;

    const complete = (payload: UltimatumResult, html: string) => {
      if (settled) return;
      settled = true;
      const resolver = trial.resolve_outcome as (
        result: UltimatumResult,
      ) => Record<string, unknown>;
      const extra = resolver(payload) ?? {};
      if (feedback) {
        feedback.hidden = false;
        feedback.innerHTML = html;
      }
      this.jsPsych.pluginAPI.setTimeout(() => {
        this.jsPsych.finishTrial({
          rt: performance.now() - start,
          ...payload,
          ...extra,
        });
      }, feedbackDuration);
    };

    if (isProposer) {
      const slider = display_element.querySelector<HTMLInputElement>(".ns-slider");
      const keepEl = display_element.querySelector("[data-keep]");
      const offerEl = display_element.querySelector("[data-offer]");
      const submit = display_element.querySelector<HTMLButtonElement>(".ns-submit");

      const sync = () => {
        const offer = clampOffer(Number(slider?.value ?? 0), endowment);
        if (keepEl) keepEl.textContent = String(endowment - offer);
        if (offerEl) offerEl.textContent = String(offer);
      };
      sync();
      slider?.addEventListener("input", sync);

      submit?.addEventListener("click", () => {
        if (submit) submit.disabled = true;
        if (slider) slider.disabled = true;
        const offer = clampOffer(Number(slider?.value ?? 0), endowment);
        const accepted = offer >= rejectBelow;
        const payoff = splitPayoff(offer, accepted, endowment);
        complete(
          {
            response: String(offer),
            offer_amount: offer,
            accepted,
            points: payoff.proposer,
            proposer_points: payoff.proposer,
            responder_points: payoff.responder,
          },
          accepted
            ? `<span class="ns-ok">Offer accepted. You keep ${payoff.proposer}, they get ${payoff.responder}.</span>`
            : `<span class="ns-bad">Offer rejected. You both get 0.</span>`,
        );
      });
      return;
    }

    display_element.querySelectorAll<HTMLButtonElement>("[data-choice]").forEach((button) => {
      button.addEventListener("click", () => {
        display_element.querySelectorAll<HTMLButtonElement>("[data-choice]").forEach((item) => {
          item.disabled = true;
        });
        const accepted = button.dataset.choice === "accept";
        const payoff = splitPayoff(offerAmount, accepted, endowment);
        complete(
          {
            response: accepted ? "accept" : "reject",
            offer_amount: offerAmount,
            accepted,
            points: payoff.responder,
            proposer_points: payoff.proposer,
            responder_points: payoff.responder,
          },
          accepted
            ? `<span class="ns-ok">You accepted ${offerAmount} points.</span>`
            : `<span class="ns-bad">You rejected the offer. Both get 0.</span>`,
        );
      });
    });
  }
}
