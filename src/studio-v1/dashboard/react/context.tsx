import { createContext, useContext, type PropsWithChildren } from "react";
import type { StudioDashboardGateway } from "../adapters/gateway.js";

const GatewayContext = createContext<StudioDashboardGateway | null>(null);

export function StudioDashboardProvider({ gateway, children }: PropsWithChildren<{ gateway: StudioDashboardGateway }>) {
  return <GatewayContext.Provider value={gateway}>{children}</GatewayContext.Provider>;
}

export function useStudioDashboardGateway(): StudioDashboardGateway {
  const gateway = useContext(GatewayContext);
  if (!gateway) throw new Error("StudioDashboardProvider is required.");
  return gateway;
}
