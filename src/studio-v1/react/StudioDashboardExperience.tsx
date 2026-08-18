"use client";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { HttpStudioDashboardGateway } from "@/studio-v1/dashboard/adapters/http-dashboard-gateway";
import { StudioDashboardProvider } from "@/studio-v1/dashboard/react/context";
import { AuthenticatedStudioShell, type DashboardSection } from "@/studio-v1/dashboard/react/components/AuthenticatedStudioShell";

export function StudioDashboardExperience() {
  const router = useRouter();
  const gateway = useMemo(() => new HttpStudioDashboardGateway(), []);
  const [section, setSection] = useState<DashboardSection>("work");

  async function signOut() {
    await fetch("/api/v1/auth/logout", { method: "POST", credentials: "same-origin" }).catch(() => undefined);
    router.replace("/");
    router.refresh();
  }

  return <div className="sv1-root sv1-calm" data-environment="calm" data-phase="dashboard">
    <StudioDashboardProvider gateway={gateway}>
      <AuthenticatedStudioShell
        section={section}
        onSectionChange={setSection}
        onCreate={() => router.push("/")}
        onOpenProject={(id) => router.push(`/production/${id}`)}
        onSignOut={signOut}
      />
    </StudioDashboardProvider>
  </div>;
}
