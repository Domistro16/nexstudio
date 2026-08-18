import { createHash, randomBytes, randomUUID, timingSafeEqual } from "node:crypto";
import type { NextResponse } from "next/server";

export const STUDIO_GUEST_COOKIE = "nex_studio_guest";
export const STUDIO_GUEST_TTL_MS = 30 * 24 * 60 * 60 * 1000;

export type StudioAnonymousSession = {
  id: string;
  secretHash: string;
  expiresAt: Date;
  cookieValue?: string;
};

function hashSecret(value: string) {
  return createHash("sha256").update(value).digest("hex");
}

function cookieValue(request: Request, name: string) {
  const cookies = request.headers.get("cookie") ?? "";
  for (const part of cookies.split(";")) {
    const [key, ...value] = part.trim().split("=");
    if (key === name) return decodeURIComponent(value.join("="));
  }
  return null;
}

function parseGuestCookie(raw: string | null): Omit<StudioAnonymousSession, "expiresAt"> | null {
  if (!raw) return null;
  const separator = raw.indexOf(".");
  if (separator < 1) return null;
  const id = raw.slice(0, separator);
  const secret = raw.slice(separator + 1);
  if (!/^[0-9a-f-]{36}$/i.test(id) || !/^[A-Za-z0-9_-]{30,}$/.test(secret)) return null;
  return { id, secretHash: hashSecret(secret) };
}

export function readStudioAnonymousSession(request: Request): StudioAnonymousSession | null {
  const raw = cookieValue(request, STUDIO_GUEST_COOKIE);
  const parsed = parseGuestCookie(raw);
  return parsed && raw ? { ...parsed, expiresAt: new Date(Date.now() + STUDIO_GUEST_TTL_MS), cookieValue: raw } : null;
}

export function getOrCreateStudioAnonymousSession(request: Request): StudioAnonymousSession {
  const existing = readStudioAnonymousSession(request);
  if (existing) return existing;
  const id = randomUUID();
  const secret = randomBytes(32).toString("base64url");
  return {
    id,
    secretHash: hashSecret(secret),
    expiresAt: new Date(Date.now() + STUDIO_GUEST_TTL_MS),
    cookieValue: `${id}.${secret}`,
  };
}

export function setStudioAnonymousSessionCookie(response: NextResponse, session: StudioAnonymousSession, request: Request) {
  if (!session.cookieValue) return;
  response.cookies.set(STUDIO_GUEST_COOKIE, session.cookieValue, {
    httpOnly: true,
    sameSite: "lax",
    secure: new URL(request.url).protocol === "https:",
    path: "/",
    expires: session.expiresAt,
  });
}

export function clearStudioAnonymousSessionCookie(response: NextResponse, request: Request) {
  response.cookies.set(STUDIO_GUEST_COOKIE, "", {
    httpOnly: true,
    sameSite: "lax",
    secure: new URL(request.url).protocol === "https:",
    path: "/",
    expires: new Date(0),
  });
}

export function constantTimeHashEqual(a: string | null | undefined, b: string | null | undefined) {
  if (!a || !b || a.length !== b.length) return false;
  return timingSafeEqual(Buffer.from(a), Buffer.from(b));
}
