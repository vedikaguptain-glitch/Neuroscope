"use client";

import dynamic from "next/dynamic";

const JsPsychWrapper = dynamic(
  () =>
    import("@/components/experiment/jspsych-wrapper").then(
      (mod) => mod.JsPsychWrapper,
    ),
  {
    ssr: false,
    loading: () => (
      <div className="flex min-h-dvh items-center justify-center bg-background text-muted-foreground">
        Preparing the experiment…
      </div>
    ),
  },
);

export function ExperimentClient() {
  return <JsPsychWrapper />;
}
