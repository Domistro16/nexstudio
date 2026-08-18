import { PrismaPg } from "@prisma/adapter-pg";
import { PrismaClient } from "@/generated/prisma/client";
import { env } from "./env";
let prisma: PrismaClient | null = null;
export function getPrisma() {
  if (!env.databaseUrl) return null;
  if (!prisma) prisma = new PrismaClient({ adapter: new PrismaPg({ connectionString: env.databaseUrl, max: env.databasePoolMax }) });
  return prisma;
}
