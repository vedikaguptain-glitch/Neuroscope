import { ConsentForm } from "@/components/consent/consent-form";

export default function HomePage() {
  return (
    <main className="mx-auto grid min-h-dvh w-full max-w-6xl gap-10 px-6 py-12 lg:grid-cols-[1.1fr_0.9fr] lg:items-center">
      <section className="space-y-6">
        <p className="text-xs uppercase tracking-[0.28em] text-primary">
          Behavioral representation learning
        </p>
        <h1 className="text-4xl font-semibold tracking-tight sm:text-5xl">
          NEUROSCOPE
        </h1>
        <p className="max-w-xl text-lg leading-8 text-muted-foreground">
          Learn a general latent representation of decision-making directly from
          behavior. Five tasks, one unbroken sequence of choices, logged as
          x<sub>t</sub> = [S<sub>t</sub>, A<sub>t</sub>, R<sub>t</sub>, Δt]
          after every trial.
        </p>
        <ul className="grid gap-3 text-sm text-muted-foreground sm:grid-cols-2">
          <li className="rounded-lg border border-border bg-card/60 p-4">
            Probabilistic learning
          </li>
          <li className="rounded-lg border border-border bg-card/60 p-4">
            Risk preference
          </li>
          <li className="rounded-lg border border-border bg-card/60 p-4">
            Delay discounting
          </li>
          <li className="rounded-lg border border-border bg-card/60 p-4">
            Rule discovery + ultimatum
          </li>
        </ul>
      </section>
      <ConsentForm />
    </main>
  );
}
