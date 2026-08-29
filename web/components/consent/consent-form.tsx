"use client";

import { useMemo, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { createParticipant } from "@/app/actions/participants";
import {
  AGE_BRACKETS,
  COMPREHENSION_ITEMS,
  EDUCATION_LABELS,
  EDUCATION_LEVELS,
} from "@/lib/constants";
import {
  clearExperimentSession,
  writeSessionIdentity,
  writeSessionPoints,
} from "@/lib/experiment/session-store";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/select";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";

type Answers = Record<string, boolean | null>;

export function ConsentForm() {
  const router = useRouter();
  const [step, setStep] = useState(0);
  const [consentAccepted, setConsentAccepted] = useState(false);
  const [answers, setAnswers] = useState<Answers>(() =>
    Object.fromEntries(COMPREHENSION_ITEMS.map((item) => [item.id, null])),
  );
  const [ageBracket, setAgeBracket] = useState("");
  const [educationLevel, setEducationLevel] = useState("");
  const [guardianConsent, setGuardianConsent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const comprehensionPassed = useMemo(
    () =>
      COMPREHENSION_ITEMS.every((item) => answers[item.id] === item.correct),
    [answers],
  );

  const progress = ((step + 1) / 3) * 100;

  function submit() {
    setError(null);
    startTransition(async () => {
      const result = await createParticipant({
        ageBracket,
        educationLevel,
        comprehensionPassed: true,
        consentAccepted: true,
        guardianConsent,
      });

      if (!result.ok) {
        setError(result.error);
        return;
      }

      clearExperimentSession();
      writeSessionIdentity(result.data.publicId, result.data.seed);
      writeSessionPoints(0);
      router.push("/experiment");
    });
  }

  return (
    <Card className="overflow-hidden border-border/70 bg-card/90 shadow-2xl shadow-black/20 backdrop-blur">
      <CardHeader className="p-5 sm:p-6">
        <p className="text-xs uppercase tracking-[0.2em] text-primary">Participation consent</p>
        <CardTitle>Before you begin</CardTitle>
        <CardDescription>
          A roughly 30-minute sequence of choice-based activities. Your responses
          are stored under a random participant ID, without your name.
        </CardDescription>
        <Progress value={progress} className="mt-3" />
      </CardHeader>
      <CardContent className="space-y-6 p-5 pt-0 sm:p-6 sm:pt-0">
        {step === 0 ? (
          <div className="space-y-4 text-sm leading-6 text-muted-foreground">
            <p>
              This school student-led study explores how people respond to a
              variety of short decision challenges.
            </p>
            <ul className="list-disc space-y-2 pl-5">
              <li>You will complete five activities in one continuous session.</li>
              <li>Your choices and response times will be recorded for analysis.</li>
              <li>You may stop at any time by closing the browser.</li>
              <li>We do not ask for or store your name.</li>
            </ul>
            <label className="flex items-start gap-3 text-foreground">
              <Checkbox
                checked={consentAccepted}
                onChange={(event) => setConsentAccepted(event.target.checked)}
              />
              <span>I understand the risks and agree to participate.</span>
            </label>
            <Button className="w-full sm:w-auto" disabled={!consentAccepted} onClick={() => setStep(1)}>
              Continue
            </Button>
          </div>
        ) : null}

        {step === 1 ? (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">
              Confirm each statement to show you understood the consent form.
            </p>
            {COMPREHENSION_ITEMS.map((item) => (
              <fieldset key={item.id} className="space-y-2">
                <legend className="text-sm font-medium">{item.prompt}</legend>
                <div className="grid grid-cols-2 gap-3 sm:flex">
                  <Button
                    size="sm"
                    variant={answers[item.id] === true ? "default" : "outline"}
                    onClick={() =>
                      setAnswers((current) => ({ ...current, [item.id]: true }))
                    }
                  >
                    True
                  </Button>
                  <Button
                    size="sm"
                    variant={answers[item.id] === false ? "default" : "outline"}
                    onClick={() =>
                      setAnswers((current) => ({ ...current, [item.id]: false }))
                    }
                  >
                    False
                  </Button>
                </div>
              </fieldset>
            ))}
            <div className="grid grid-cols-[auto_1fr] gap-3 sm:flex">
              <Button variant="ghost" onClick={() => setStep(0)}>
                Back
              </Button>
              <Button disabled={!comprehensionPassed} onClick={() => setStep(2)}>
                Continue
              </Button>
            </div>
          </div>
        ) : null}

        {step === 2 ? (
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="age">What is your age?</Label>
              <NativeSelect
                id="age"
                value={ageBracket}
                onChange={(event) => setAgeBracket(event.target.value)}
              >
                <option value="">Select age bracket</option>
                {AGE_BRACKETS.map((bracket) => (
                  <option key={bracket} value={bracket}>
                    {bracket}
                  </option>
                ))}
              </NativeSelect>
            </div>
            <div className="space-y-2">
              <Label htmlFor="education">Highest level of education</Label>
              <NativeSelect
                id="education"
                value={educationLevel}
                onChange={(event) => setEducationLevel(event.target.value)}
              >
                <option value="">Select education</option>
                {EDUCATION_LEVELS.map((level) => (
                  <option key={level} value={level}>
                    {EDUCATION_LABELS[level]}
                  </option>
                ))}
              </NativeSelect>
            </div>
            {ageBracket === "13-17" ? (
              <label className="flex items-start gap-3 text-sm">
                <Checkbox
                  checked={guardianConsent}
                  onChange={(event) => setGuardianConsent(event.target.checked)}
                />
                <span>
                  A parent or legal guardian has consented to my participation.
                </span>
              </label>
            ) : null}
            <Separator />
            {error ? <p className="text-sm text-destructive">{error}</p> : null}
            <div className="grid grid-cols-[auto_1fr] gap-3 sm:flex">
              <Button variant="ghost" onClick={() => setStep(1)}>
                Back
              </Button>
              <Button
                size="lg"
                disabled={
                  pending ||
                  !ageBracket ||
                  !educationLevel ||
                  (ageBracket === "13-17" && !guardianConsent)
                }
                onClick={submit}
              >
                {pending ? "Creating session…" : "I agree — begin"}
              </Button>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
