import "server-only";

import { cloneMockProfile } from "@/lib/mock-data";
import type { ProfileConfig } from "@/lib/types";
import { getDatabase, type DatabaseUser } from "./database";

export function profileForUser(user: DatabaseUser): ProfileConfig {
  const profile = cloneMockProfile();
  profile.profile.username = user.username;
  profile.profile.displayName = user.displayName;
  profile.profile.uid = user.uid;
  profile.socials = profile.socials.map((social) => ({ ...social, value: social.value.replaceAll("demo", user.username) }));
  return profile;
}

export function getProfile(username: string) {
  const row = getDatabase().prepare("SELECT config_json FROM profiles WHERE username = ?").get(username) as { config_json?: string } | undefined;
  if (!row?.config_json) return null;
  try { return JSON.parse(row.config_json) as ProfileConfig; } catch { return null; }
}

export function saveProfile(username: string, config: ProfileConfig) {
  const db = getDatabase();
  db.prepare(`INSERT INTO profiles (username, config_json, updated_at) VALUES (?, ?, ?) ON CONFLICT(username) DO UPDATE SET config_json = excluded.config_json, updated_at = excluded.updated_at`).run(username, JSON.stringify(config), new Date().toISOString());
  return config;
}
