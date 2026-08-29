import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function DashboardPage() {
  return (
    <main className="mx-auto min-h-dvh max-w-3xl px-6 py-16">
      <Card>
        <CardHeader>
          <CardTitle>Research area</CardTitle>
          <CardDescription>
            Study data are available only to the project team through the
            approved research workspace.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm leading-6 text-muted-foreground">
          <p>This participant-facing site does not provide access to research records.</p>
          <Link className="text-primary underline-offset-4 hover:underline" href="/">
            Return to the study
          </Link>
        </CardContent>
      </Card>
    </main>
  );
}
