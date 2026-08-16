export const DELAY_LADDER = [1, 2, 3, 7, 14, 21, 30, 45, 60, 90] as const;
export const IMMEDIATE_ANCHORS = [40, 60, 80, 100, 120] as const;

export interface DelayState {
  immediate: number;
  delayed: number;
  delayDays: number;
}

export function initialDelayState(): DelayState {
  return { immediate: 100, delayed: 150, delayDays: 7 };
}

function ladderIndex(delayDays: number): number {
  const exact = DELAY_LADDER.indexOf(delayDays as (typeof DELAY_LADDER)[number]);
  if (exact >= 0) return exact;
  const next = DELAY_LADDER.findIndex((value) => value >= delayDays);
  return next >= 0 ? next : DELAY_LADDER.length - 1;
}

function ensureDelayedAdvantage(state: DelayState): DelayState {
  if (state.delayed > state.immediate) return state;
  return { ...state, delayed: state.immediate + 50 };
}

export function titrateDelay(
  state: DelayState,
  choseDelayed: boolean,
  trialIndex: number,
): DelayState {
  const pos = ladderIndex(state.delayDays);
  let next: DelayState = choseDelayed
    ? {
        immediate: state.immediate,
        delayed: Math.max(state.immediate + 10, state.delayed - 10),
        delayDays: DELAY_LADDER[Math.min(DELAY_LADDER.length - 1, pos + 1)]!,
      }
    : {
        immediate: state.immediate,
        delayed: Math.min(400, state.delayed + 15),
        delayDays: DELAY_LADDER[Math.max(0, pos - 1)]!,
      };

  if (trialIndex % 10 === 0) {
    const anchorIndex = (trialIndex / 10 - 1) % IMMEDIATE_ANCHORS.length;
    next = {
      ...next,
      immediate: IMMEDIATE_ANCHORS[(anchorIndex + IMMEDIATE_ANCHORS.length) % IMMEDIATE_ANCHORS.length]!,
    };
  }

  return ensureDelayedAdvantage(next);
}

export function replayDelayState(choices: readonly boolean[]): DelayState {
  return choices.reduce(
    (state, choseDelayed, index) => titrateDelay(state, choseDelayed, index + 1),
    initialDelayState(),
  );
}
