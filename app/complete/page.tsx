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

function subscribe() {
  return () => undefined;
}

function useSessionValue(key: string, fallback: string) {
  return useSyncExternalStore(
    subscribe,
    () => sessionStorage.getItem(key) ?? fallback,
    () => fallback,
  );
}

export default function CompletePage() {
  const publicId = useSessionValue("ns_public_id", "");
  const points = useSessionValue("ns_points", "0");

  return (
    <main className="mx-auto flex min-h-dvh max-w-xl items-center px-6">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Session complete</CardTitle>
          <CardDescription>
            Every trial was written to the database as it happened. You can close
            this window.
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
