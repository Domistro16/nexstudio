const int = (value: string | undefined, fallback: number) => Number.isFinite(Number(value)) ? Number(value) : fallback;
const bool = (value: string | undefined, fallback = false) => value == null ? fallback : value.trim().toLowerCase() === "true";
const production = process.env.NODE_ENV === "production";

function requiredSecret(name: string, value: string) {
  if (production && value.length < 32) throw new Error(`${name}_REQUIRED_IN_PRODUCTION`);
  return value;
}

const appOrigin = process.env.APP_ORIGIN?.trim() || "http://localhost:3000";
const trustSecret = process.env.STUDIO_TRUST_SECRET?.trim() || process.env.ENCRYPTION_KEY?.trim() || (production ? "" : "studio-v1-local-development-only");

export const env = {
  appOrigin,
  databaseUrl: process.env.DATABASE_URL?.trim() || "",
  databasePoolMax: int(process.env.DATABASE_POOL_MAX, 10),
  resendApiKey: process.env.RESEND_API_KEY?.trim() || "",
  emailFrom: process.env.EMAIL_FROM?.trim() || "",
  encryptionKey: requiredSecret("STUDIO_TRUST_SECRET", trustSecret),
  trustSecret: requiredSecret("STUDIO_TRUST_SECRET", trustSecret),
  objectStorageEndpoint: process.env.OBJECT_STORAGE_ENDPOINT?.trim() || "",
  objectStorageBucket: process.env.OBJECT_STORAGE_BUCKET?.trim() || "",
  objectStorageAccessKey: process.env.OBJECT_STORAGE_ACCESS_KEY?.trim() || "",
  objectStorageSecretKey: process.env.OBJECT_STORAGE_SECRET_KEY?.trim() || "",
  objectStorageRegion: process.env.OBJECT_STORAGE_REGION?.trim() || "auto",
  objectStorageSessionToken: process.env.OBJECT_STORAGE_SESSION_TOKEN?.trim() || "",
  objectStorageRoot: process.env.OBJECT_STORAGE_LOCAL_ROOT?.trim() || "./data/objects",
  studioOperatorUserIds: (process.env.STUDIO_OPERATOR_USER_IDS || "").split(",").map(v=>v.trim()).filter(Boolean),
  objectStorageLocalRoot: process.env.OBJECT_STORAGE_LOCAL_ROOT?.trim() || "./data/objects",
  objectStorageAllowLocalProduction: bool(process.env.OBJECT_STORAGE_ALLOW_LOCAL_PRODUCTION),
  paymentProvider: (process.env.STUDIO_PAYMENT_PROVIDER?.trim().toLowerCase() || "none") as "none" | "stripe",
  stripeSecretKey: process.env.STRIPE_SECRET_KEY?.trim() || "",
  stripeWebhookSecret: process.env.STRIPE_WEBHOOK_SECRET?.trim() || "",
  stripeLiveRequired: bool(process.env.STUDIO_STRIPE_LIVE_REQUIRED, production),
  uploadMaxBytes: int(process.env.STUDIO_UPLOAD_MAX_BYTES, 50 * 1024 * 1024),
  clamavHost: process.env.CLAMAV_HOST?.trim() || "",
  clamavPort: int(process.env.CLAMAV_PORT, 3310),
  assetTicketTtlSeconds: int(process.env.STUDIO_ASSET_TICKET_TTL_SECONDS, 300),
};

export function assertTrustRuntimeConfiguration() {
  const issues: string[] = [];
  if (production && !env.appOrigin.startsWith("https://")) issues.push("APP_ORIGIN must be https:// in production");
  if (production && env.trustSecret.length < 32) issues.push("STUDIO_TRUST_SECRET must be at least 32 characters");
  if (env.paymentProvider === "stripe") {
    if (!env.stripeSecretKey || !env.stripeWebhookSecret) issues.push("Stripe requires STRIPE_SECRET_KEY and STRIPE_WEBHOOK_SECRET");
    if (env.stripeLiveRequired && !env.stripeSecretKey.startsWith("sk_live_")) issues.push("Live Stripe key required for production payment readiness");
  }
  return { ok: issues.length === 0, issues };
}
