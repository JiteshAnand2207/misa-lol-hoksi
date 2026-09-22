import "server-only";

import { redis } from "./redis";

export async function withinLimit(key: string, maximum: number, seconds: number) {
  const client = redis();
  if (client.status === "wait") await client.connect();
  const count = await client.incr(key);
  if (count === 1) await client.expire(key, seconds);
  return count <= maximum;
}
