import { env } from "./env";
export function isProductionOperator(user:{id:string}){return env.studioOperatorUserIds.includes(user.id);}
