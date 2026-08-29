import { JsPsych, JsPsychPlugin, ParameterType, TrialType } from "jspsych";
import { renderHtml } from "@/lib/experiment/markup";

export interface ChoiceOutcome {
  feedback_html: string;
  extra_data?: Record<string, unknown>;
  spin_wheel?: boolean;
}

const info = {
  name: "neuroscope-two-choice",
  version: "1.1.0",
  parameters: {
    prompt: { type: ParameterType.HTML_STRING, default: "" },
    left_html: { type: ParameterType.HTML_STRING, default: "" },
    right_html: { type: ParameterType.HTML_STRING, default: "" },
    left_label: { type: ParameterType.STRING, default: "Option A" },
    right_label: { type: ParameterType.STRING, default: "Option B" },
    hud_html: { type: ParameterType.HTML_STRING, default: "" },
    feedback_duration: { type: ParameterType.INT, default: 850 },
    wheel_duration: { type: ParameterType.INT, default: 700 },
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
        ${renderHtml(trial.hud_html)}
        <p class="ns-prompt">${renderHtml(trial.prompt)}</p>
        <div class="ns-options">
          <button type="button" class="ns-option" data-choice="left">
            <span class="ns-option-kicker">${renderHtml(trial.left_label)}</span>
            <span class="ns-option-body">${renderHtml(trial.left_html)}</span>
          </button>
          <button type="button" class="ns-option" data-choice="right">
            <span class="ns-option-kicker">${renderHtml(trial.right_label)}</span>
            <span class="ns-option-body">${renderHtml(trial.right_html)}</span>
          </button>
        </div>
        <div class="ns-feedback" hidden></div>
      </div>
    `;

    const start = performance.now();
    const buttons = display_element.querySelectorAll<HTMLButtonElement>("[data-choice]");
    const feedback = display_element.querySelector<HTMLElement>(".ns-feedback");
    let settled = false;

    const finish = (choice: "left" | "right") => {
      if (settled) return;
      settled = true;
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

      const showFeedback = (html: string, done: () => void) => {
        if (feedback && html) {
          feedback.hidden = false;
          feedback.innerHTML = html;
          this.jsPsych.pluginAPI.setTimeout(done, trial.feedback_duration ?? 850);
          return;
        }
        done();
      };

      if (outcome.spin_wheel) {
        if (feedback) {
          feedback.hidden = false;
          feedback.innerHTML = `<div class="ns-wheel" aria-hidden="true"></div><span class="ns-muted">Spinning…</span>`;
        }
        this.jsPsych.pluginAPI.setTimeout(() => {
          showFeedback(
            `<div class="ns-wheel ns-wheel-stop" aria-hidden="true"></div>${outcome.feedback_html}`,
            () => this.jsPsych.finishTrial(data),
          );
        }, trial.wheel_duration ?? 700);
        return;
      }

      showFeedback(outcome.feedback_html, () => this.jsPsych.finishTrial(data));
    };

    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        const choice = button.dataset.choice === "right" ? "right" : "left";
        finish(choice);
      });
    });
  }
}
