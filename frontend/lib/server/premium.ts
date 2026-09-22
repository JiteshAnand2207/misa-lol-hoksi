import "server-only";
import { one } from "./postgres";

const SHARED_SETTINGS = [
  "layout", "pageEnter", "profileFont", "profileFontScope", "entryScreen",
  "entryText", "clickSound", "bioTypewriter", "bioTypeMs", "bioDeleteMs",
  "bioPauseMs", "cardTilt", "showViews", "showAvatar", "showSocials",
  "borderColor", "borderWidth", "profileRadius", "ogTitle", "ogDescription",
  "ogOverlayAvatar", "ogOverlayName", "ogOverlayAddress"
] as const;

const PREMIUM_ASSETS = [
  "customFont", "clickSound", "entryIcon", "ogImage", "favicon"
] as const;

export async function hasActivePremium(userId: string): Promise<boolean> {
  try {
    const row = await one<{ active: boolean }>(`
      SELECT EXISTS (
        SELECT 1 FROM premium_entitlements
        WHERE user_id = $1 AND active = TRUE AND (expires_at IS NULL OR expires_at > NOW())
      ) AS active
    `, [userId]);
    return Boolean(row?.active);
  } catch {
    return false;
  }
}

function presentationSnapshot(config: Record<string, unknown>): Record<string, unknown> {
  const settings = (config.settings && typeof config.settings === "object" ? config.settings : {}) as Record<string, unknown>;
  const assets = (config.assets && typeof config.assets === "object" ? config.assets : {}) as Record<string, unknown>;
  const sections = Array.isArray(config.sections) ? structuredClone(config.sections) : [];

  const snapSettings: Record<string, unknown> = {};
  for (const key of SHARED_SETTINGS) {
    snapSettings[key] = settings[key];
  }

  const snapAssets: Record<string, unknown> = {};
  for (const key of PREMIUM_ASSETS) {
    snapAssets[key] = assets[key];
  }

  return {
    settings: snapSettings,
    assets: snapAssets,
    sections,
  };
}

export function protectWrite(
  incoming: Record<string, unknown>,
  previous: Record<string, unknown> | null,
  entitled: boolean
): Record<string, unknown> {
  const prev = previous || {};
  const inSettings = (incoming.settings && typeof incoming.settings === "object" ? incoming.settings : {}) as Record<string, unknown>;
  const oldSettings = (prev.settings && typeof prev.settings === "object" ? prev.settings : {}) as Record<string, unknown>;
  const inAssets = (incoming.assets && typeof incoming.assets === "object" ? incoming.assets : {}) as Record<string, unknown>;
  const oldAssets = (prev.assets && typeof prev.assets === "object" ? prev.assets : {}) as Record<string, unknown>;
  const inSections = Array.isArray(incoming.sections) ? incoming.sections : [];
  const oldSections = Array.isArray(prev.sections) ? prev.sections : [];

  const advanced = inSettings.premium;
  const base = prev._premium_base as Record<string, unknown> | undefined;

  let changed = JSON.stringify(advanced) !== JSON.stringify(oldSettings.premium);

  if (["Default", "Portfolio"].includes(String(inSettings.layout || "")) && inSettings.layout !== oldSettings.layout) {
    changed = true;
  }

  const hasAdvancedSections = inSections.some((s: any) =>
    s && typeof s === "object" && (s.leftCard || s.rightCard || s.subtitle || (s.type === "about" && s.tags) || s.type === "integration")
  );
  if (hasAdvancedSections && JSON.stringify(inSections) !== JSON.stringify(oldSections)) {
    changed = true;
  }

  const inEntryIcon = (inAssets.entryIcon as Record<string, unknown> | undefined)?.url;
  const oldEntryIcon = (oldAssets.entryIcon as Record<string, unknown> | undefined)?.url;
  if (inEntryIcon !== oldEntryIcon) {
    changed = true;
  }

  if (base) {
    const currSnap = presentationSnapshot(incoming);
    const oldSnap = presentationSnapshot(prev);
    if (JSON.stringify(currSnap) !== JSON.stringify(oldSnap)) {
      changed = true;
    }
  }

  if (changed && !entitled) {
    throw new Error("An active Premium entitlement is required to change premium settings. Your saved settings have been kept.");
  }

  const result = { ...incoming };
  delete result._premium_base;

  if (base) {
    result._premium_base = structuredClone(base);
  } else if (entitled && advanced) {
    result._premium_base = presentationSnapshot(prev);
  }

  return result;
}

export function publicProjection(
  config: Record<string, unknown>,
  entitled: boolean
): Record<string, unknown> {
  const result = structuredClone(config);
  const base = result._premium_base as Record<string, unknown> | undefined;
  delete result._premium_base;

  if (!entitled) {
    if (result.settings && typeof result.settings === "object") {
      delete (result.settings as Record<string, unknown>).premium;
    }

    if (base) {
      for (const group of ["settings", "assets"] as const) {
        const groupObj = (base[group] && typeof base[group] === "object" ? base[group] : {}) as Record<string, unknown>;
        if (!result[group] || typeof result[group] !== "object") {
          result[group] = {};
        }
        const targetGroup = result[group] as Record<string, unknown>;
        for (const [key, value] of Object.entries(groupObj)) {
          if (value === null || value === undefined) {
            delete targetGroup[key];
          } else {
            targetGroup[key] = value;
          }
        }
      }
      result.sections = Array.isArray(base.sections) ? structuredClone(base.sections) : [];
    } else {
      const settings = (result.settings && typeof result.settings === "object" ? result.settings : {}) as Record<string, unknown>;
      if (["Default", "Portfolio"].includes(String(settings.layout || ""))) {
        settings.layout = "Modern";
      }
    }
  }

  return result;
}
