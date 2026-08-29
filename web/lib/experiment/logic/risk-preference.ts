export const SAFE_AMOUNT = 50;

export interface RiskCell {
  p: number;
  win: number;
}

export interface RiskTrial {
  trialIndex: number;
  p: number;
  win: number;
  safeAmount: number;
  safeOnLeft: boolean;
  gambleWins: boolean;
}

export function buildRiskGrid(): RiskCell[] {
  const probabilities = [0.2, 0.35, 0.5, 0.65, 0.8];
  const amounts = [80, 100, 120, 140, 160, 180, 200, 220, 250, 300];
  const grid: RiskCell[] = [];
  for (const p of probabilities) {
    for (const win of amounts) {
      grid.push({ p, win });
    }
  }
  return grid;
}

export function expectedValue(cell: Pick<RiskCell, "p" | "win">): number {
  return cell.p * cell.win;
}

function shuffle<T>(items: T[], random: () => number): T[] {
  const copy = [...items];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

export function buildRiskSchedule(
  n: number,
  random: () => number,
  safeAmount = SAFE_AMOUNT,
): RiskTrial[] {
  const cells: RiskCell[] = [];
  while (cells.length < n) {
    cells.push(...shuffle(buildRiskGrid(), random));
  }

  return cells.slice(0, n).map((item, index) => ({
    trialIndex: index + 1,
    p: item.p,
    win: item.win,
    safeAmount,
    safeOnLeft: random() < 0.5,
    gambleWins: random() < item.p,
  }));
}

export function riskPoints(trial: RiskTrial, gambled: boolean): number {
  if (!gambled) return trial.safeAmount;
  return trial.gambleWins ? trial.win : 0;
}
