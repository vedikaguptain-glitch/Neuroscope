import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";

export default function DashboardPage() {
  return (
    <main className="mx-auto min-h-dvh max-w-3xl px-6 py-16">
      <Card>
        <CardHeader>
          <CardTitle>Researcher access</CardTitle>
          <CardDescription>
            The web client is INSERT-only. Trial and participant rows are not
            readable from this app.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
          <p>
            Use the Supabase Table Editor or SQL with the service role to inspect
            <code className="mx-1 rounded bg-secondary px-1.5 py-0.5">participants</code>
            and
            <code className="mx-1 rounded bg-secondary px-1.5 py-0.5">trials</code>.
          </p>
          <p>
            Each trial row is one x<sub>t</sub> sample:
            <code className="mx-1 rounded bg-secondary px-1.5 py-0.5">state_vector</code>,
            <code className="mx-1 rounded bg-secondary px-1.5 py-0.5">action_taken</code>,
            <code className="mx-1 rounded bg-secondary px-1.5 py-0.5">reward_received</code>,
            <code className="mx-1 rounded bg-secondary px-1.5 py-0.5">reaction_time_ms</code>,
            plus task-specific
            <code className="mx-1 rounded bg-secondary px-1.5 py-0.5">latent_variables</code>.
          </p>
        </CardContent>
      </Card>
    </main>
  );
}
