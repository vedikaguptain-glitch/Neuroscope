export const ENDOWMENT = 100;
export const REJECT_BELOW = 20;
export const ROLE_BLOCK = 5;
export const BOT_OFFERS = [10, 15, 20, 25, 30, 40, 50] as const;

export type UltimatumRole = "proposer" | "responder";

export function roleAtTrial(trialIndex: number, block = ROLE_BLOCK): UltimatumRole {
  const blockIndex = Math.floor((trialIndex - 1) / block);
  return blockIndex % 2 === 0 ? "proposer" : "responder";
}

export function clampOffer(offer: number, endowment = ENDOWMENT): number {
  if (!Number.isFinite(offer)) return 0;
  return Math.max(0, Math.min(endowment, Math.round(offer)));
}

export function botAccepts(offer: number, rejectBelow = REJECT_BELOW): boolean {
  return clampOffer(offer) >= rejectBelow;
}

export function splitPayoff(
  offer: number,
  accepted: boolean,
  endowment = ENDOWMENT,
): { proposer: number; responder: number } {
  const clamped = clampOffer(offer, endowment);
  if (!accepted) return { proposer: 0, responder: 0 };
  return { proposer: endowment - clamped, responder: clamped };
}
