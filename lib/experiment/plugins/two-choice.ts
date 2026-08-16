import { JsPsych, JsPsychPlugin, ParameterType, TrialType } from "jspsych";

export interface ChoiceOutcome {
  feedback_html: string;
  extra_data?: Record<string, unknown>;
}

const info = {
  name: "neuroscope-two-choice",
  version: "1.0.0",
  parameters: {
    prompt: { type: ParameterType.HTML_STRING, default: "" },
    left_html: { type: ParameterType.HTML_STRING, default: "" },
    right_html: { type: ParameterType.HTML_STRING, default: "" },
    left_label: { type: ParameterType.STRING, default: "Option A" },
    right_label: { type: ParameterType.STRING, default: "Option B" },
    hud_html: { type: ParameterType.HTML_STRING, default: "" },
    feedback_duration: { type: ParameterType.INT, default: 850 },
    show_wheel: { type: ParameterType.BOOL, default: false },
    resolve_outcome: {
      type: ParameterType.FUNCTION,
      default: () => ({ feedback_html: "" }) as ChoiceOutcome,
    },
  },
  data: {
    rt: { type: ParameterType.FLOAT },
    response: { type: ParameterType.STRING },
  },
} as const;

type Info = typeof info;

export default class TwoChoicePlugin implements JsPsychPlugin<Info> {
  static readonly info = info;

  constructor(private jsPsych: JsPsych) {}

  trial(display_element: HTMLElement, trial: TrialType<Info>) {
    display_element.innerHTML = `
      <div class="ns-trial">
        ${trial.hud_html}
        <p class="ns-prompt">${trial.prompt}</p>
        <div class="ns-options">
          <button type="button" class="ns-option" data-choice="left">
            <span class="ns-option-kicker">${trial.left_label}</span>
            <span class="ns-option-body">${trial.left_html}</span>
          </button>
          <button type="button" class="ns-option" data-choice="right">
            <span class="ns-option-kicker">${trial.right_label}</span>
            <span class="ns-option-body">${trial.right_html}</span>
          </button>
        </div>
        <div class="ns-feedback" hidden></div>
      </div>
    `;

    const start = performance.now();
    const buttons = display_element.querySelectorAll<HTMLButtonElement>("[data-choice]");
    const feedback = display_element.querySelector<HTMLElement>(".ns-feedback");

    const finish = (choice: "left" | "right") => {
      const rt = performance.now() - start;
      buttons.forEach((button) => {
        button.disabled = true;
      });

      const resolver = trial.resolve_outcome as (picked: "left" | "right") => ChoiceOutcome;
      const outcome = resolver(choice);
      const data = {
        rt,
        response: choice,
        ...(outcome.extra_data ?? {}),
      };

      if (feedback && outcome.feedback_html) {
        feedback.hidden = false;
        feedback.innerHTML = trial.show_wheel
          ? `<div class="ns-wheel" aria-hidden="true"></div>${outcome.feedback_html}`
          : outcome.feedback_html;
        this.jsPsych.pluginAPI.setTimeout(() => {
          this.jsPsych.finishTrial(data);
        }, trial.feedback_duration ?? 850);
        return;
      }

      this.jsPsych.finishTrial(data);
    };

    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        const choice = button.dataset.choice === "right" ? "right" : "left";
        finish(choice);
      });
    });
  }
}
