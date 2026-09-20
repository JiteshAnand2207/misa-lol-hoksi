"use client";

import { Check, Sparkles } from "lucide-react";
import { useT } from "@/lib/i18n";
import { Button, PageHeader } from "@/components/ui";

export function PremiumView() {
  const t = useT();
  const plans = [
    { name: t("premium.free"), price: "$0", tone: "text-zinc-300", border: "border-white/[.08]", features: [t("premium.free1"), t("premium.free2"), t("premium.free3")], current: true },
    { name: t("premium.pro"), price: "$4.99", tone: "text-[#6cb0ff]", border: "border-[#4d9fff]/40", features: [t("premium.pro1"), t("premium.pro2"), t("premium.pro3"), t("premium.pro4")], current: false },
    { name: t("premium.supporter"), price: "$9.99", tone: "text-[#e0a63c]", border: "border-[#e0a63c]/40", features: [t("premium.sup1"), t("premium.sup2"), t("premium.sup3"), t("premium.sup4")], current: false },
  ];
  return (
    <main className="mx-auto min-h-screen max-w-[1100px] px-5 py-8 sm:px-8 sm:py-11 xl:px-12">
      <PageHeader eyebrow={t("premium.eyebrow")} title={t("premium.title")} description={t("premium.description")} />
      <div className="grid gap-4 lg:grid-cols-3">
        {plans.map((plan) => (
          <section key={plan.name} className={`surface rounded-2xl border p-6 ${plan.border}`}>
            <p className={`text-xs font-semibold uppercase tracking-[.16em] ${plan.tone}`}>{plan.name}</p>
            <p className="mt-3 text-3xl font-semibold tracking-[-.04em]">{plan.price}<span className="ms-1 text-sm font-normal text-zinc-600">{t("premium.month")}</span></p>
            <ul className="mt-6 space-y-3 text-sm text-zinc-400">
              {plan.features.map((feature) => (
                <li key={feature} className="flex items-start gap-2"><Check size={15} className={plan.tone} />{feature}</li>
              ))}
            </ul>
            <Button variant={plan.current ? "subtle" : "accent"} className="mt-6 w-full" disabled={!plan.current}>
              {plan.current ? t("common.currentPlan") : t("common.comingSoon")}
            </Button>
          </section>
        ))}
      </div>
      <p className="mt-6 flex items-center gap-2 text-xs text-zinc-600"><Sparkles size={14} />{t("premium.later")}</p>
    </main>
  );
}
