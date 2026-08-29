import { ConsentForm } from "@/components/consent/consent-form";

export default function HomePage() {
  return (
    <main className="landing-shell mx-auto grid min-h-dvh w-full max-w-6xl gap-8 px-4 py-6 sm:px-6 sm:py-10 lg:grid-cols-[1.05fr_0.95fr] lg:items-center lg:gap-14">
      <section className="px-1 pt-5 sm:px-0 sm:pt-0">
        <p className="mb-5 text-xs font-medium uppercase tracking-[0.24em] text-primary">
          A student-led research activity
        </p>
        <h1 className="max-w-xl text-5xl font-semibold leading-[0.92] tracking-[-0.055em] sm:text-7xl">
          How do you make a choice?
        </h1>
        <p className="mt-7 max-w-lg text-base leading-7 text-muted-foreground sm:text-lg sm:leading-8">
          Take part in a school research project through a sequence of quick,
          interactive challenges. There are no right answers overall—just respond
          naturally and see your session snapshot at the end.
        </p>
        <div className="mt-8 grid max-w-lg grid-cols-3 border-y border-border/80 py-5 text-sm">
          <div>
            <span className="block font-mono text-lg text-foreground">5</span>
            <span className="text-muted-foreground">activities</span>
          </div>
          <div className="border-x border-border/80 px-4">
            <span className="block font-mono text-lg text-foreground">~30</span>
            <span className="text-muted-foreground">minutes</span>
          </div>
          <div className="pl-4">
            <span className="block font-mono text-lg text-foreground">No</span>
            <span className="text-muted-foreground">name collected</span>
          </div>
        </div>
      </section>
      <ConsentForm />
    </main>
  );
}
