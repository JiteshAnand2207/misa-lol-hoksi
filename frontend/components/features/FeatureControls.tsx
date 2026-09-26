"use client";

import { useCallback, useEffect, useState } from "react";
import { SlidersHorizontal } from "lucide-react";
import { PageHeader, SectionTitle } from "@/components/ui";
import { featureName, featureReason, PROFILE_FEATURES, type OwnerFeatureState, type ProfileFeatureKey } from "@/lib/profile-features";

async function policyRequest(path = "", init?: RequestInit): Promise<Record<string, unknown>> {
  const response = await fetch(`/api/v1/features/policy${path}`, {
    ...init,
    cache: "no-store",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  const payload = await response.json().catch(() => ({})) as Record<string, unknown>;
  if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "Could not save this feature setting.");
  return payload;
}

export function FeatureControls() {
  const [features, setFeatures] = useState<OwnerFeatureState[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<ProfileFeatureKey | null>(null);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const reload = useCallback(async () => {
    const payload = await policyRequest();
    if (!Array.isArray(payload.features)) throw new Error("The feature catalogue is unavailable.");
    setFeatures(payload.features as OwnerFeatureState[]);
  }, []);

  useEffect(() => {
    let mounted = true;
    void reload().catch((failure) => { if (mounted) setError(failure instanceof Error ? failure.message : "Could not load features."); }).finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, [reload]);

  const update = async (feature: OwnerFeatureState) => {
    setBusy(feature.key);
    setError("");
    setNotice("");
    try {
      await policyRequest(`/${encodeURIComponent(feature.key)}`, {
        method: "PUT",
        body: JSON.stringify({ requested_enabled: !feature.requested_enabled, expected_version: feature.config_version }),
      });
      await reload();
      setNotice(`${featureName(feature.key)} preference saved.`);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not save this setting.");
      await reload().catch(() => undefined);
    } finally {
      setBusy(null);
    }
  };

  return <main className="mx-auto max-w-[1200px] px-5 py-8 sm:px-8 sm:py-11 xl:px-12">
    <PageHeader eyebrow="Your page" title="Features" description="Choose which features you want on your page. Availability also depends on your plan, feature setup, and the current rollout." />
    <SectionTitle icon={SlidersHorizontal} title="Your feature switches" description="Changes save immediately. Each card shows your preference and the current public state." />
    {loading ? <p className="text-sm text-zinc-500" role="status">Loading features…</p> : null}
    {error ? <p className="mb-4 rounded-xl border border-rose-400/20 bg-rose-400/5 p-3 text-sm text-rose-200" role="alert">{error}</p> : null}
    {notice ? <p className="mb-4 text-sm text-emerald-300" role="status">{notice}</p> : null}
    {!loading && features.length === 0 && !error ? <p className="text-sm text-zinc-500">No feature controls are available yet.</p> : null}
    <div className="grid gap-3 lg:grid-cols-2">
      {features.map((feature) => {
        const meta = PROFILE_FEATURES[feature.key];
        return <section key={feature.key} className="surface rounded-2xl p-5">
          <div className="flex items-start gap-4">
            <div className="min-w-0 flex-1">
              <h2 className="text-base font-semibold text-white">{featureName(feature.key, feature.name)}</h2>
              <p className="mt-1 text-xs text-zinc-500">{meta?.summary || "Optional page feature"}</p>
              <p className="mt-3 text-xs text-zinc-400">{feature.reference_tier} · <span className={feature.effective_enabled ? "text-emerald-300" : "text-zinc-500"}>{featureReason(feature.reason_code)}</span></p>
            </div>
            <button type="button" role="switch" aria-label={`${featureName(feature.key, feature.name)} preference`} aria-checked={feature.requested_enabled} disabled={busy !== null} onClick={() => void update(feature)} className={`relative mt-0.5 h-7 w-12 shrink-0 rounded-full transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-400 disabled:opacity-50 ${feature.requested_enabled ? "bg-rose-600" : "bg-zinc-700"}`}>
              <span className={`absolute top-1 h-5 w-5 rounded-full bg-white transition-all ${feature.requested_enabled ? "start-6" : "start-1"}`} />
            </button>
          </div>
        </section>;
      })}
    </div>
  </main>;
}
