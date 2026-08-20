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
import { readSessionItem, SESSION_KEYS } from "@/lib/experiment/session-store";

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

  return (
    <main className="mx-auto flex min-h-dvh max-w-xl items-center px-6">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Session complete</CardTitle>
          <CardDescription>
            {saved
              ? "Every trial was written to the database as it happened. You can close this window."
              : "The session finished, but some trial rows could not be saved. Please tell the researcher your anonymous ID."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Anonymous ID:{" "}
            <span className="font-mono text-foreground">{publicId || "—"}</span>
          </p>
          <p className="text-sm text-muted-foreground">
            Session points: <span className="text-foreground">{points}</span>
          </p>
          {!saved ? (
            <p className="text-sm text-destructive">
              Unsaved trials: {failedLogs}
            </p>
          ) : null}
          <Link
            href="/"
            className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90"
          >
            Return to start
          </Link>
        </CardContent>
      </Card>
    </main>
  );
}
