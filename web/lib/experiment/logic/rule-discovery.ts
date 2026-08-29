export interface CardSpec {
  color: "red" | "green" | "blue" | "yellow";
  shape: "triangle" | "star" | "plus" | "circle";
  count: 1 | 2 | 3 | 4;
}

export type RuleId = "color" | "shape" | "number";

export const KEY_CARDS: CardSpec[] = [
  { color: "red", shape: "triangle", count: 1 },
  { color: "green", shape: "star", count: 2 },
  { color: "yellow", shape: "plus", count: 3 },
  { color: "blue", shape: "circle", count: 4 },
];

export const RULE_ORDER: RuleId[] = ["color", "shape", "number", "color"];

export function ruleBlockSize(n: number): number {
  return Math.max(2, Math.floor(n / RULE_ORDER.length));
}

export function ruleAtTrial(
  trialIndex: number,
  n: number,
): { rule: RuleId; previousRule: RuleId; ruleShift: boolean; block: number } {
  const block = ruleBlockSize(n);
  const ruleIndex = Math.min(RULE_ORDER.length - 1, Math.floor((trialIndex - 1) / block));
  const previousIndex =
    trialIndex === 1
      ? ruleIndex
      : Math.min(RULE_ORDER.length - 1, Math.floor((trialIndex - 2) / block));
  const rule = RULE_ORDER[ruleIndex]!;
  const previousRule = RULE_ORDER[previousIndex]!;
  return { rule, previousRule, ruleShift: rule !== previousRule, block };
}

export interface DiagnosticTarget {
  target: CardSpec;
  matchIndex: Record<RuleId, number>;
}

export function diagnosticTarget(random: () => number): DiagnosticTarget {
  const colorIdx = Math.floor(random() * 4);
  let shapeIdx = Math.floor(random() * 3);
  if (shapeIdx >= colorIdx) shapeIdx += 1;
  const remaining = [0, 1, 2, 3].filter((index) => index !== colorIdx && index !== shapeIdx);
  const countIdx = remaining[Math.floor(random() * remaining.length)]!;

  return {
    target: {
      color: KEY_CARDS[colorIdx]!.color,
      shape: KEY_CARDS[shapeIdx]!.shape,
      count: KEY_CARDS[countIdx]!.count,
    },
    matchIndex: {
      color: colorIdx,
      shape: shapeIdx,
      number: countIdx,
    },
  };
}

export function isDiagnostic(matchIndex: Record<RuleId, number>): boolean {
  const values = [matchIndex.color, matchIndex.shape, matchIndex.number];
  return new Set(values).size === 3 && values.every((index) => index >= 0 && index <= 3);
}
