export type SymbolId = "A" | "B";

export interface ProbLearningTrial {
  trialIndex: number;
  probA: number;
  probB: number;
  reversed: boolean;
  volatilityReversal: boolean;
  leftSymbol: SymbolId;
  rewardIfA: boolean;
  rewardIfB: boolean;
}

export function reversalTrial(n: number): number {
  return Math.floor(n / 2) + 1;
}

export function buildProbLearningSchedule(
  n: number,
  random: () => number,
): ProbLearningTrial[] {
  const reversalAt = reversalTrial(n);
  const trials: ProbLearningTrial[] = [];

  for (let i = 1; i <= n; i += 1) {
    const reversed = i >= reversalAt;
    const probA = reversed ? 0.2 : 0.8;
    const probB = reversed ? 0.8 : 0.2;
    trials.push({
      trialIndex: i,
      probA,
      probB,
      reversed,
      volatilityReversal: i === reversalAt,
      leftSymbol: random() < 0.5 ? "A" : "B",
      rewardIfA: random() < probA,
      rewardIfB: random() < probB,
    });
  }

  return trials;
}

export function symbolOnSide(
  trial: Pick<ProbLearningTrial, "leftSymbol">,
  side: "left" | "right",
): SymbolId {
  if (side === "left") return trial.leftSymbol;
  return trial.leftSymbol === "A" ? "B" : "A";
}

export function rewardForSymbol(
  trial: Pick<ProbLearningTrial, "rewardIfA" | "rewardIfB">,
  symbol: SymbolId,
): boolean {
  return symbol === "A" ? trial.rewardIfA : trial.rewardIfB;
}
