export const PROFILE_FEATURES = {
  ask_anything: { name: "Ask me anything", summary: "Collect questions and publish selected answers." },
  other_side: { name: "The other side", summary: "A second face for selected profile blocks." },
  night_shift: { name: "The night shift", summary: "Show chosen blocks during your local night window." },
  daily_draw: { name: "The draw", summary: "A daily card drawn from your lines." },
  time_capsule: { name: "Time capsule", summary: "A sealed note that opens at a scheduled time." },
  archive: { name: "The archive", summary: "Let visitors browse selected profile history." },
  moon: { name: "The moon", summary: "A small lunar phase display on your page." },
  guestbook: { name: "Guestbook", summary: "Review visitor notes before they appear." },
  neighbours: { name: "Neighbours", summary: "Show mutual connections to other pages." },
  alive: { name: "Alive", summary: "Presence, local time, and visit count controls." },
  secret_word: { name: "Secret word", summary: "Unlock a private destination with a phrase." },
  chalkboard: { name: "A chalkboard", summary: "Keep selected visitor drawings on your page." },
  tally: { name: "The tally", summary: "Publish a small poll and collect votes." },
} as const;

export type ProfileFeatureKey = keyof typeof PROFILE_FEATURES;

export type OwnerFeatureState = {
  key: ProfileFeatureKey;
  name: string;
  reference_tier: string;
  requested_enabled: boolean;
  effective_enabled: boolean;
  reason_code: string;
  policy_version: number;
  config_version: number;
  updated_at: string | null;
};

export type FeaturePolicy = {
  key: ProfileFeatureKey;
  name: string;
  reference_tier: string;
  globally_enabled: boolean;
  eligible_plans: Array<"free" | "lifetime" | "supporter">;
  rollout_percent: number;
  default_enabled: boolean;
  version: number;
  updated_at: string | null;
  requested_profile_count: number;
};

export function featureName(key: string, fallback?: string) {
  return PROFILE_FEATURES[key as ProfileFeatureKey]?.name || fallback || key;
}

export function featureReason(code: string): string {
  const reasons: Record<string, string> = {
    enabled: "Active",
    global_off: "Unavailable for everyone",
    plan_locked: "Not on your plan",
    rollout_excluded: "Not in the current rollout",
    suspended: "Restricted for this page",
    owner_off: "Turned off by you",
    configuration_incomplete: "Complete the feature setup before it can appear",
    unpublished: "Publish the feature setup before it can appear",
    policy_missing: "Unavailable",
  };
  return reasons[code] || code.replaceAll("_", " ");
}
