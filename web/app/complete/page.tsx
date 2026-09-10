"use client";

import Link from "next/link";
import { useSyncExternalStore } from "react";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  readSessionItem,
  SESSION_KEYS,
  type SessionSummary,
} from "@/lib/experiment/session-store";

function subscribe() {
  return () => undefined;
}

function useSessionValue(key: string, fallback: string) {
  return useSyncExternalStore(
    subscribe,
    () => readSessionItem(key) ?? fallback,
    () => fallback,
  );
}

export default function CompletePage() {
  const publicId = useSessionValue(SESSION_KEYS.publicId, "");
  const points = useSessionValue(SESSION_KEYS.points, "0");
  const failedLogs = Number(useSessionValue(SESSION_KEYS.failedLogs, "0"));
  const saved = !Number.isFinite(failedLogs) || failedLogs <= 0;
  const summaryRaw = useSessionValue(SESSION_KEYS.summary, "{}");
  let summary: Partial<SessionSummary> = {};
  try {
    summary = JSON.parse(summaryRaw) as Partial<SessionSummary>;
  } catch {
    summary = {};
  }

  const totalTrials = summary.totalTrials ?? 0;
  const averageSeconds = totalTrials
    ? (Number(summary.totalReactionTimeMs ?? 0) / totalTrials / 1000).toFixed(1)
    : "—";
  const patternAccuracy = summary.patternChoices
    ? Math.round(
        (Number(summary.correctPatternChoices ?? 0) / summary.patternChoices) * 100,
      )
    : null;
  const gambleRate = summary.riskChoices
    ? Math.round((Number(summary.gambleChoices ?? 0) / summary.riskChoices) * 100)
    : null;
  const delayedRate = summary.delayChoices
    ? Math.round((Number(summary.delayedChoices ?? 0) / summary.delayChoices) * 100)
    : null;

  const insights = [
    { value: totalTrials || "—", label: "choices completed" },
    { value: `${averageSeconds}${averageSeconds === "—" ? "" : "s"}`, label: "average decision time" },
    patternAccuracy == null
      ? null
      : { value: `${patternAccuracy}%`, label: "hidden patterns matched" },
    gambleRate == null
      ? null
      : { value: `${gambleRate}%`, label: "chose the uncertain option" },
    delayedRate == null
      ? null
      : { value: `${delayedRate}%`, label: "preferred the later reward" },
  ].filter((item): item is { value: string | number; label: string } => item !== null);

  return (
    <main className="completion-shell mx-auto flex min-h-dvh max-w-3xl items-center px-4 py-8 sm:px-6">
      <Card className="w-full overflow-hidden border-border/70 bg-card/90 shadow-2xl shadow-black/20">
        <CardHeader className="p-5 sm:p-8">
          <p className="text-xs font-medium uppercase tracking-[0.22em] text-primary">Session complete</p>
          <CardTitle className="text-3xl sm:text-4xl">Your decision snapshot</CardTitle>
          <CardDescription>
            {saved
              ? "Your responses were saved. This snapshot describes today’s choices and is not a personality or ability score."
              : "The session finished, but part of its database record could not be saved. Please tell the researcher your anonymous ID."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6 p-5 pt-0 sm:p-8 sm:pt-0">
          <section className="grid grid-cols-2 gap-px overflow-hidden rounded-xl bg-border sm:grid-cols-3" aria-label="Your session statistics">
            {insights.map((insight) => (
              <div key={insight.label} className="min-h-28 bg-secondary/70 p-4 sm:p-5">
                <strong className="block font-mono text-2xl font-medium tabular-nums text-foreground sm:text-3xl">
                  {insight.value}
                </strong>
                <span className="mt-2 block text-xs leading-5 text-muted-foreground sm:text-sm">
                  {insight.label}
                </span>
              </div>
            ))}
            <div className="min-h-28 bg-primary p-4 text-primary-foreground sm:p-5">
              <strong className="block font-mono text-2xl font-medium tabular-nums sm:text-3xl">{points}</strong>
              <span className="mt-2 block text-xs leading-5 opacity-75 sm:text-sm">points collected</span>
            </div>
          </section>
          {!saved ? (
            <p className="text-sm text-destructive">
              Unsaved records: {failedLogs}
            </p>
          ) : null}
          <div className="flex flex-col gap-4 border-t border-border pt-5 sm:flex-row sm:items-center sm:justify-between">
            <p className="min-w-0 text-xs text-muted-foreground">
              Anonymous ID:{" "}
              <span className="break-all font-mono text-foreground">{publicId || "—"}</span>
            </p>
            <Link
              href="/"
              className="inline-flex h-11 shrink-0 items-center justify-center rounded-md bg-primary px-5 text-sm font-medium text-primary-foreground transition hover:bg-primary/90 active:scale-[0.98]"
            >
              Return to start
            </Link>
          </div>
        </CardContent>
      </Card>
    </main>
  );
}
