import { JsPsych, JsPsychPlugin, ParameterType, TrialType } from "jspsych";

const info = {
  name: "neuroscope-ultimatum",
  version: "1.0.0",
  parameters: {
    prompt: { type: ParameterType.HTML_STRING, default: "" },
    hud_html: { type: ParameterType.HTML_STRING, default: "" },
    role: { type: ParameterType.STRING, default: "proposer" },
    endowment: { type: ParameterType.INT, default: 100 },
    offer_amount: { type: ParameterType.INT, default: 20 },
    feedback_duration: { type: ParameterType.INT, default: 1100 },
    reject_below: { type: ParameterType.INT, default: 20 },
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
    const offerAmount = trial.offer_amount ?? 20;
    const rejectBelow = trial.reject_below ?? 20;
    const feedbackDuration = trial.feedback_duration ?? 1100;

    display_element.innerHTML = `
      <div class="ns-trial">
        ${trial.hud_html}
        <p class="ns-prompt">${trial.prompt}</p>
        ${
          isProposer
            ? `
              <div class="ns-offer">
                <label class="ns-offer-label">
                  Offer to partner
                  <input class="ns-slider" type="range" min="0" max="${endowment}" value="${Math.round(endowment / 2)}" />
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

    const complete = (payload: Record<string, unknown>, html: string) => {
      if (feedback) {
        feedback.hidden = false;
        feedback.innerHTML = html;
      }
      this.jsPsych.pluginAPI.setTimeout(() => {
        this.jsPsych.finishTrial({
          rt: performance.now() - start,
          ...payload,
        });
      }, feedbackDuration);
    };

    if (isProposer) {
      const slider = display_element.querySelector<HTMLInputElement>(".ns-slider");
      const keepEl = display_element.querySelector("[data-keep]");
      const offerEl = display_element.querySelector("[data-offer]");
      const submit = display_element.querySelector<HTMLButtonElement>(".ns-submit");

      const sync = () => {
        const offer = Number(slider?.value ?? 0);
        if (keepEl) keepEl.textContent = String(endowment - offer);
        if (offerEl) offerEl.textContent = String(offer);
      };
      sync();
      slider?.addEventListener("input", sync);

      submit?.addEventListener("click", () => {
        if (submit) submit.disabled = true;
        if (slider) slider.disabled = true;
        const offer = Number(slider?.value ?? 0);
        const accepted = offer >= rejectBelow;
        const keep = accepted ? endowment - offer : 0;
        complete(
          {
            response: String(offer),
            offer_amount: offer,
            accepted,
            points: keep,
          },
          accepted
            ? `<span class="ns-ok">Offer accepted. You keep ${keep}, they get ${offer}.</span>`
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
        const points = accepted ? offerAmount : 0;
        complete(
          {
            response: accepted ? "accept" : "reject",
            accepted,
            points,
          },
          accepted
            ? `<span class="ns-ok">You accepted ${offerAmount} points.</span>`
            : `<span class="ns-bad">You rejected the offer. Both get 0.</span>`,
        );
      });
    });
  }
}
