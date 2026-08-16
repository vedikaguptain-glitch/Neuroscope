import { JsPsych, JsPsychPlugin, ParameterType, TrialType } from "jspsych";

export interface CardSpec {
  color: "red" | "green" | "blue" | "yellow";
  shape: "triangle" | "star" | "plus" | "circle";
  count: 1 | 2 | 3 | 4;
}

const COLOR_HEX: Record<CardSpec["color"], string> = {
  red: "#ef4444",
  green: "#22c55e",
  blue: "#38bdf8",
  yellow: "#facc15",
};

function shapeSvg(shape: CardSpec["shape"], color: string): string {
  if (shape === "circle") {
    return `<circle cx="16" cy="16" r="10" fill="${color}" />`;
  }
  if (shape === "triangle") {
    return `<polygon points="16,4 28,26 4,26" fill="${color}" />`;
  }
  if (shape === "plus") {
    return `<rect x="13" y="4" width="6" height="24" rx="1" fill="${color}" /><rect x="4" y="13" width="24" height="6" rx="1" fill="${color}" />`;
  }
  return `<polygon points="16,3 20,12 30,13 22,20 24,30 16,24 8,30 10,20 2,13 12,12" fill="${color}" />`;
}

export function renderCard(card: CardSpec): string {
  const items = Array.from({ length: card.count }, () => {
    return `<svg viewBox="0 0 32 32" class="ns-glyph" aria-hidden="true">${shapeSvg(card.shape, COLOR_HEX[card.color])}</svg>`;
  }).join("");
  return `<div class="ns-card" data-color="${card.color}" data-shape="${card.shape}" data-count="${card.count}">${items}</div>`;
}

const info = {
  name: "neuroscope-rule-match",
  version: "1.0.0",
  parameters: {
    prompt: { type: ParameterType.HTML_STRING, default: "" },
    hud_html: { type: ParameterType.HTML_STRING, default: "" },
    target: { type: ParameterType.COMPLEX, default: undefined },
    options: { type: ParameterType.COMPLEX, array: true, default: [] },
    correct_index: { type: ParameterType.INT, default: 0 },
    feedback_duration: { type: ParameterType.INT, default: 700 },
  },
  data: {
    rt: { type: ParameterType.FLOAT },
    response: { type: ParameterType.INT },
  },
} as const;

type Info = typeof info;

export default class RuleMatchPlugin implements JsPsychPlugin<Info> {
  static readonly info = info;

  constructor(private jsPsych: JsPsych) {}

  trial(display_element: HTMLElement, trial: TrialType<Info>) {
    const target = trial.target as CardSpec;
    const options = trial.options as CardSpec[];

    display_element.innerHTML = `
      <div class="ns-trial">
        ${trial.hud_html}
        <p class="ns-prompt">${trial.prompt}</p>
        <div class="ns-wcst">
          <div class="ns-wcst-target">
            <span class="ns-option-kicker">Target</span>
            ${renderCard(target)}
          </div>
          <div class="ns-wcst-options">
            ${options
              .map(
                (card, index) => `
                  <button type="button" class="ns-card-btn" data-index="${index}">
                    ${renderCard(card)}
                  </button>
                `,
              )
              .join("")}
          </div>
        </div>
        <div class="ns-feedback" hidden></div>
      </div>
    `;

    const start = performance.now();
    const buttons = display_element.querySelectorAll<HTMLButtonElement>("[data-index]");
    const feedback = display_element.querySelector<HTMLElement>(".ns-feedback");

    buttons.forEach((button) => {
      button.addEventListener("click", () => {
        const response = Number(button.dataset.index);
        const rt = performance.now() - start;
        const correct = response === trial.correct_index;
        buttons.forEach((item) => {
          item.disabled = true;
        });
        if (feedback) {
          feedback.hidden = false;
          feedback.innerHTML = correct
            ? `<span class="ns-ok">Correct</span>`
            : `<span class="ns-bad">Incorrect</span>`;
        }
        this.jsPsych.pluginAPI.setTimeout(() => {
          this.jsPsych.finishTrial({ rt, response, correct });
        }, trial.feedback_duration ?? 700);
      });
    });
  }
}
