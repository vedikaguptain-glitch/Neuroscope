import assert from "node:assert/strict";
import { test } from "node:test";
import { replayDelayState, titrateDelay, initialDelayState } from "./delay-discounting.ts";
import {
  buildProbLearningSchedule,
  reversalTrial,
  rewardForSymbol,
  symbolOnSide,
} from "./prob-learning.ts";
import { buildRiskGrid, buildRiskSchedule, expectedValue, riskPoints } from "./risk-preference.ts";
import {
  diagnosticTarget,
  isDiagnostic,
  ruleAtTrial,
} from "./rule-discovery.ts";
import { botAccepts, clampOffer, roleAtTrial, splitPayoff } from "./ultimatum.ts";
import { mulberry32, seedFromString, shuffle } from "../rng.ts";

test("probabilistic learning reverses at trial 51 of 100", () => {
  assert.equal(reversalTrial(100), 51);
  const schedule = buildProbLearningSchedule(100, mulberry32(1));
  assert.equal(schedule.length, 100);
  assert.equal(schedule[49]!.probA, 0.8);
  assert.equal(schedule[49]!.volatilityReversal, false);
  assert.equal(schedule[50]!.probA, 0.2);
  assert.equal(schedule[50]!.probB, 0.8);
  assert.equal(schedule[50]!.volatilityReversal, true);
  assert.equal(schedule[50]!.reversed, true);
});

test("probabilistic learning is seeded and side-counterbalanced", () => {
  const a = buildProbLearningSchedule(100, mulberry32(42));
  const b = buildProbLearningSchedule(100, mulberry32(42));
  const c = buildProbLearningSchedule(100, mulberry32(43));
  assert.deepEqual(a, b);
  assert.notDeepEqual(a, c);
  const leftA = a.filter((trial) => trial.leftSymbol === "A").length;
  assert.ok(leftA > 30 && leftA < 70);
  const trial = a[0]!;
  const picked = symbolOnSide(trial, "left");
  assert.equal(rewardForSymbol(trial, picked), picked === "A" ? trial.rewardIfA : trial.rewardIfB);
});

test("risk preference builds 50 unique probability-amount cells", () => {
  const grid = buildRiskGrid();
  assert.equal(grid.length, 50);
  const keys = new Set(grid.map((cell) => `${cell.p}:${cell.win}`));
  assert.equal(keys.size, 50);
  assert.ok(grid.some((cell) => expectedValue(cell) < 50));
  assert.ok(grid.some((cell) => expectedValue(cell) > 50));
});

test("risk schedule length, seeding, and payoffs", () => {
  const schedule = buildRiskSchedule(50, mulberry32(7));
  assert.equal(schedule.length, 50);
  assert.deepEqual(schedule, buildRiskSchedule(50, mulberry32(7)));
  const win = schedule.find((trial) => trial.gambleWins)!;
  const lose = schedule.find((trial) => !trial.gambleWins)!;
  assert.equal(riskPoints(win, true), win.win);
  assert.equal(riskPoints(lose, true), 0);
  assert.equal(riskPoints(win, false), 50);
});

test("delay titration changes the next trial and replays identically", () => {
  const start = initialDelayState();
  const afterDelay = titrateDelay(start, true, 1);
  const afterNow = titrateDelay(start, false, 1);
  assert.ok(afterDelay.delayDays > start.delayDays);
  assert.ok(afterDelay.delayed <= start.delayed);
  assert.ok(afterNow.delayDays < start.delayDays);
  assert.ok(afterNow.delayed >= start.delayed);
  assert.ok(afterDelay.delayed > afterDelay.immediate);
  const choices = [true, true, false, false, true];
  assert.deepEqual(replayDelayState(choices), replayDelayState(choices));
  let state = start;
  choices.forEach((choice, index) => {
    state = titrateDelay(state, choice, index + 1);
  });
  assert.deepEqual(replayDelayState(choices), state);
});

test("rule discovery shifts at trial 16 and stays diagnostic", () => {
  const first = ruleAtTrial(1, 60);
  const shift = ruleAtTrial(16, 60);
  const later = ruleAtTrial(31, 60);
  assert.equal(first.rule, "color");
  assert.equal(first.ruleShift, false);
  assert.equal(shift.rule, "shape");
  assert.equal(shift.ruleShift, true);
  assert.equal(later.rule, "number");
  const random = mulberry32(99);
  for (let i = 0; i < 200; i += 1) {
    const { matchIndex } = diagnosticTarget(random);
    assert.equal(isDiagnostic(matchIndex), true);
  }
});

test("ultimatum roles, bot threshold, and payoffs", () => {
  assert.equal(roleAtTrial(1), "proposer");
  assert.equal(roleAtTrial(5), "proposer");
  assert.equal(roleAtTrial(6), "responder");
  assert.equal(roleAtTrial(10), "responder");
  assert.equal(roleAtTrial(11), "proposer");
  assert.equal(botAccepts(19), false);
  assert.equal(botAccepts(20), true);
  assert.equal(clampOffer(19.6), 20);
  assert.equal(clampOffer(-4), 0);
  assert.equal(clampOffer(140), 100);
  assert.deepEqual(splitPayoff(20, true), { proposer: 80, responder: 20 });
  assert.deepEqual(splitPayoff(10, false), { proposer: 0, responder: 0 });
});

test("rng seed and shuffle are deterministic", () => {
  assert.equal(seedFromString("abc"), seedFromString("abc"));
  assert.notEqual(seedFromString("abc"), seedFromString("abd"));
  const items = [1, 2, 3, 4, 5, 6, 7, 8];
  assert.deepEqual(shuffle(items, mulberry32(3)), shuffle(items, mulberry32(3)));
  assert.notDeepEqual(shuffle(items, mulberry32(3)), shuffle(items, mulberry32(4)));
});
