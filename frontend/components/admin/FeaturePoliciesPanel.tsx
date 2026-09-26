"use client";

import { useCallback, useEffect, useState } from "react";
import { SlidersHorizontal } from "lucide-react";
import { Button, SectionTitle } from "@/components/ui";
import { featureName, type FeaturePolicy } from "@/lib/profile-features";

const PLANS = ["free", "lifetime", "supporter"] as const;

async function requestPolicy(path = "", init?: RequestInit): Promise<Record<string, unknown>> {
  const response = await fetch(`/api/v1/admin/feature-policies${path}`, {
    ...init,
    cache: "no-store",
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
  });
  const payload = await response.json().catch(() => ({})) as Record<string, unknown>;
  if (!response.ok) throw new Error(typeof payload.detail === "string" ? payload.detail : "Feature policy request failed.");
  return payload;
}

function PolicyCard({ policy, canEdit, onSaved }: { policy: FeaturePolicy; canEdit: boolean; onSaved: () => Promise<void> }) {
  const [globalEnabled, setGlobalEnabled] = useState(policy.globally_enabled);
  const [plans, setPlans] = useState<FeaturePolicy["eligible_plans"]>(policy.eligible_plans);
  const [rollout, setRollout] = useState(policy.rollout_percent);
  const [defaultEnabled, setDefaultEnabled] = useState(policy.default_enabled);
  const [reason, setReason] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    setGlobalEnabled(policy.globally_enabled);
    setPlans(policy.eligible_plans);
    setRollout(policy.rollout_percent);
    setDefaultEnabled(policy.default_enabled);
  }, [policy]);

  const togglePlan = (plan: typeof PLANS[number]) => {
    setPlans((current) => current.includes(plan) ? current.filter((item) => item !== plan) : [...current, plan]);
    setSaved(false);
  };

  const save = async () => {
    if (!reason.trim()) { setError("Enter a reason for this change."); return; }
    if (plans.length === 0) { setError("Select at least one eligible plan."); return; }
    setSaving(true);
    setError("");
    setSaved(false);
    try {
      await requestPolicy(`/${encodeURIComponent(policy.key)}`, {
        method: "PUT",
        body: JSON.stringify({
          globally_enabled: globalEnabled,
          eligible_plans: PLANS.filter((plan) => plans.includes(plan)),
          rollout_percent: rollout,
          default_enabled: defaultEnabled,
          expected_version: policy.version,
          reason: reason.trim(),
        }),
      });
      await onSaved();
      setReason("");
      setSaved(true);
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : "Could not save this policy.");
      await onSaved().catch(() => undefined);
    } finally {
      setSaving(false);
    }
  };

  return <section className="surface rounded-2xl p-5">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div><h3 className="text-sm font-semibold text-white">{featureName(policy.key, policy.name)}</h3><p className="mt-1 font-mono text-[11px] text-zinc-600">{policy.key} · {policy.reference_tier} · policy v{policy.version}</p><p className="mt-1 text-[11px] text-zinc-500">{policy.requested_profile_count} pages requested · updated {policy.updated_at ? new Date(policy.updated_at).toLocaleString() : "never"}</p></div>
      <span className={`rounded-full px-2.5 py-1 text-[11px] ${policy.globally_enabled ? "bg-emerald-400/10 text-emerald-300" : "bg-zinc-700/40 text-zinc-400"}`}>{policy.globally_enabled ? "Global switch on" : "Globally off"}</span>
    </div>
    <div className="mt-5 grid gap-4 text-xs text-zinc-300 sm:grid-cols-2">
      <label className="flex items-center gap-2"><input type="checkbox" checked={globalEnabled} disabled={!canEdit || saving} onChange={(event) => { setGlobalEnabled(event.target.checked); setSaved(false); }} className="accent-rose-500" /> Globally available</label>
      <label className="flex items-center gap-2"><input type="checkbox" checked={defaultEnabled} disabled={!canEdit || saving} onChange={(event) => { setDefaultEnabled(event.target.checked); setSaved(false); }} className="accent-rose-500" /> Default for new pages</label>
      <fieldset className="sm:col-span-2"><legend className="mb-2 text-zinc-500">Eligible plans</legend><div className="flex flex-wrap gap-4">{PLANS.map((plan) => <label key={plan} className="flex items-center gap-2 capitalize"><input type="checkbox" checked={plans.includes(plan)} disabled={!canEdit || saving} onChange={() => togglePlan(plan)} className="accent-rose-500" />{plan}</label>)}</div></fieldset>
      <label className="sm:col-span-2">Rollout: <strong className="text-white">{rollout}%</strong><input type="range" min="0" max="100" step="5" value={rollout} disabled={!canEdit || saving} onChange={(event) => { setRollout(Number(event.target.value)); setSaved(false); }} className="mt-2 block w-full accent-rose-500" /></label>
    </div>
    {canEdit ? <div className="mt-5 flex flex-col gap-2 sm:flex-row"><input aria-label={`Reason for changing ${featureName(policy.key)} policy`} value={reason} onChange={(event) => setReason(event.target.value)} maxLength={500} placeholder="Reason for change" className="h-10 min-w-0 flex-1 rounded-xl border border-white/[.08] bg-white/[.025] px-3 text-xs text-white outline-none focus:border-rose-400/60" /><Button variant="accent" disabled={saving} onClick={() => void save()}>{saving ? "Saving…" : "Save policy"}</Button></div> : null}
    {error ? <p className="mt-3 text-xs text-rose-300" role="alert">{error}</p> : null}
    {saved ? <p className="mt-3 text-xs text-emerald-300" role="status">Policy saved.</p> : null}
  </section>;
}

export function FeaturePoliciesPanel({ canEdit }: { canEdit: boolean }) {
  const [policies, setPolicies] = useState<FeaturePolicy[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const reload = useCallback(async () => {
    const payload = await requestPolicy();
    if (!Array.isArray(payload.features)) throw new Error("The feature catalogue is unavailable.");
    setPolicies(payload.features as FeaturePolicy[]);
  }, []);
  useEffect(() => {
    let mounted = true;
    void reload().catch((failure) => { if (mounted) setError(failure instanceof Error ? failure.message : "Could not load feature policies."); }).finally(() => { if (mounted) setLoading(false); });
    return () => { mounted = false; };
  }, [reload]);

  return <section>
    <SectionTitle icon={SlidersHorizontal} title="Feature catalogue" description="Global availability takes precedence over owner switches. New features start unavailable until their public flow is ready." />
    {loading ? <p className="text-sm text-zinc-500" role="status">Loading policies…</p> : null}
    {error ? <p className="mb-4 text-sm text-rose-300" role="alert">{error}</p> : null}
    <div className="grid gap-3 xl:grid-cols-2">{policies.map((policy) => <PolicyCard key={policy.key} policy={policy} canEdit={canEdit} onSaved={reload} />)}</div>
  </section>;
}
