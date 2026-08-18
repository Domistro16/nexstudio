import { keyedHash } from "./auth";
import { getPrisma } from "./db";

export function requestIpHash(request: Request) {
  const forwarded = request.headers.get("cf-connecting-ip") || request.headers.get("x-real-ip") || request.headers.get("x-forwarded-for")?.split(",")[0]?.trim() || "unavailable";
  return keyedHash("ip", forwarded);
}

export async function consumeRateLimit(key: string, category: string, limit: number, windowMs: number) {
  const prisma=getPrisma(); if(!prisma) return {allowed:false,remaining:0,retryAfterSeconds:60};
  const now = Date.now();
  const startMs = Math.floor(now / windowMs) * windowMs;
  const windowStart = new Date(startMs);
  const expiresAt = new Date(startMs + windowMs * 2);
  const bucket = await prisma.rateLimitBucket.upsert({
    where: { key_category_windowStart: { key, category, windowStart } },
    create: { key, category, windowStart, expiresAt, count: 1 },
    update: { count: { increment: 1 }, expiresAt },
  });
  return { allowed: bucket.count <= limit, remaining: Math.max(0, limit - bucket.count), retryAfterSeconds: Math.max(1, Math.ceil((startMs + windowMs - now) / 1_000)) };
}
