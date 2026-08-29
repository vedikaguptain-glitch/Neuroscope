import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { ExperimentClient } from "@/components/experiment/experiment-client";
import { PARTICIPANT_COOKIE } from "@/lib/constants";

export default async function ExperimentPage() {
  const cookieStore = await cookies();
  if (!cookieStore.get(PARTICIPANT_COOKIE)) {
    redirect("/");
  }

  return <ExperimentClient />;
}
