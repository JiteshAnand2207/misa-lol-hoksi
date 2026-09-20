"use client";

import { BookOpen, Check, ExternalLink, KeyRound, ListChecks, MessageSquare, Paintbrush, Send, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { Button, PageHeader, SectionTitle, TextInput } from "@/components/ui";
import { useAuth } from "@/lib/auth-store";
import { useT } from "@/lib/i18n";
import {
  answerAsk,
  approveDoodle,
  approveSignature,
  binAsk,
  binDoodle,
  binSignature,
  clearTally,
  listAsks,
  listDoodles,
  listGuestbook,
  type AskItem,
  type DoodleItem,
  type GuestbookItem,
} from "@/lib/me-moderation";
import { useProfile } from "@/lib/profile-store";
import { publicProfileUrl } from "@/lib/share";

function timeAgo(iso: string) {
  const time = Date.parse(iso);
  if (!Number.isFinite(time)) return "";
  const gap = Math.max(0, (Date.now() - time) / 1000);
  if (gap < 60) return "just now";
  const minutes = Math.round(gap / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

function safeSvg(raw: string) {
  const value = String(raw || "");
  return /^<svg[\s\S]*<\/svg>$/.test(value) && !/<script|on[a-z]+=|<foreignObject|<image|href=/i.test(value) ? value : "";
}

function StatusPill({ on }: { on: boolean }) {
  const t = useT();
  return <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium ${on ? "bg-emerald-400/10 text-emerald-300" : "bg-white/[.06] text-zinc-400"}`}><span className={`h-1.5 w-1.5 rounded-full ${on ? "bg-emerald-400" : "bg-zinc-600"}`} />{on ? t("me.statusOn") : t("me.statusOff")}</span>;
}

export function MeView() {
  const t = useT();
  const { user } = useAuth();
  const { config } = useProfile();
  const [ready, setReady] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [asks, setAsks] = useState<{ waiting: AskItem[]; answered: AskItem[] }>({ waiting: [], answered: [] });
  const [guestbook, setGuestbook] = useState<{ pending: GuestbookItem[]; approved: GuestbookItem[] }>({ pending: [], approved: [] });
  const [doodles, setDoodles] = useState<{ pending: DoodleItem[]; approved: DoodleItem[] }>({ pending: [], approved: [] });
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [toast, setToast] = useState({ type: "ok" as "ok" | "error", text: "" });

  const say = useCallback((text: string, type: "ok" | "error" = "ok") => setToast({ type, text }), []);

  const load = useCallback(async () => {
    setReady("loading");
    const results = await Promise.allSettled([listAsks(), listGuestbook(), listDoodles()]);
    const [asksResult, guestbookResult, doodlesResult] = results;
    if (asksResult.status === "fulfilled") setAsks(asksResult.value);
    if (guestbookResult.status === "fulfilled") setGuestbook(guestbookResult.value);
    if (doodlesResult.status === "fulfilled") setDoodles(doodlesResult.value);
    if (results.some((result) => result.status === "rejected")) {
      setError(t("me.error"));
      setReady("error");
    } else {
      setReady("ready");
    }
  }, [t]);

  useEffect(() => { void load(); }, [load]);

  const run = async (id: string, work: () => Promise<void>) => {
    setBusy((current) => ({ ...current, [id]: true }));
    try {
      await work();
    } catch {
      say(t("me.error"), "error");
    } finally {
      setBusy((current) => ({ ...current, [id]: false }));
    }
  };

  const sendAnswer = (item: AskItem) => {
    const text = (drafts[item.id] || "").trim();
    if (!text) return;
    void run(item.id, async () => {
      await answerAsk(item.id, text);
      const wasPending = asks.waiting.some((entry) => entry.id === item.id);
      setAsks((current) => ({
        waiting: current.waiting.filter((entry) => entry.id !== item.id),
        answered: wasPending ? [{ ...item, a: text, status: "published" }, ...current.answered] : current.answered.map((entry) => entry.id === item.id ? { ...entry, a: text } : entry),
      }));
      say(wasPending ? t("me.answerOnPage") : t("me.answerUpdated"));
    });
  };

  const bin = (item: AskItem) => {
    void run(item.id, async () => {
      await binAsk(item.id);
      setAsks((current) => ({ waiting: current.waiting.filter((entry) => entry.id !== item.id), answered: current.answered.filter((entry) => entry.id !== item.id) }));
      say(t("me.binned"));
    });
  };

  const approveEntry = (item: GuestbookItem) => {
    void run(item.id, async () => {
      await approveSignature(item.id);
      setGuestbook((current) => ({
        pending: current.pending.filter((entry) => entry.id !== item.id),
        approved: [{ ...item, status: "approved" }, ...current.approved],
      }));
      say(t("me.approved"));
    });
  };

  const binEntry = (item: GuestbookItem) => {
    void run(item.id, async () => {
      await binSignature(item.id);
      setGuestbook((current) => ({ pending: current.pending.filter((entry) => entry.id !== item.id), approved: current.approved.filter((entry) => entry.id !== item.id) }));
      say(t("me.binned"));
    });
  };

  const keepDoodle = (item: DoodleItem) => {
    void run(item.id, async () => {
      await approveDoodle(item.id);
      setDoodles((current) => ({
        pending: current.pending.filter((entry) => entry.id !== item.id),
        approved: [{ ...item, status: "approved" }, ...current.approved],
      }));
      say(t("me.kept"));
    });
  };

  const binTile = (item: DoodleItem) => {
    void run(item.id, async () => {
      await binDoodle(item.id);
      setDoodles((current) => ({ pending: current.pending.filter((entry) => entry.id !== item.id), approved: current.approved.filter((entry) => entry.id !== item.id) }));
      say(t("me.binned"));
    });
  };

  const clearMyTally = () => {
    if (!window.confirm(t("me.tallyClearConfirm"))) return;
    void run("tally", async () => {
      await clearTally();
      say(t("me.tallyCleared"));
    });
  };

  const tally = config.settings.tally;
  const tallyEnabled = Boolean(tally?.q?.trim() && (tally?.options?.length || 0) >= 2);
  const secret = config.settings.secret;
  const secretOn = Boolean(secret?.hasSecret);
  const liveHref = user?.username ? publicProfileUrl(user.username) : "";

  return (
    <main className="mx-auto min-h-screen max-w-[1100px] px-5 py-8 sm:px-8 sm:py-11 xl:px-12">
      <PageHeader
        eyebrow={t("me.eyebrow")}
        title={t("me.title")}
        description={t("me.description")}
        action={liveHref ? <a href={liveHref} target="_blank" rel="noreferrer"><Button variant="ghost"><ExternalLink size={15} />{t("me.livePage")}</Button></a> : undefined}
      />
      {ready === "loading" && <p className="text-sm text-zinc-500">{t("me.loading")}</p>}
      {ready === "error" && <p className="mb-4 rounded-xl border border-red-500/20 bg-red-500/10 px-4 py-3 text-xs text-red-300">{error}</p>}
      {toast.text && <p role="status" className={`mb-4 text-xs ${toast.type === "error" ? "text-red-300" : "text-emerald-300"}`}>{toast.text}</p>}
      {ready !== "loading" && (
        <div className="space-y-12">
          <section>
            <SectionTitle icon={MessageSquare} title={t("me.asksTitle")} description={t("me.asksDescription")} />
            <div className="surface rounded-2xl p-5">
              <p className="mb-3 text-[11px] font-semibold uppercase tracking-[.16em] text-[#fb7185]">{asks.waiting.length ? t("me.asksWaiting", { count: asks.waiting.length }) : t("me.asksEmpty")}</p>
              {asks.waiting.map((item) => <AskCard key={item.id} item={item} draft={drafts[item.id] || ""} busy={Boolean(busy[item.id])} onChange={(value) => setDrafts((current) => ({ ...current, [item.id]: value }))} onAnswer={() => sendAnswer(item)} onBin={() => bin(item)} />)}
            </div>
            <div className="surface mt-4 rounded-2xl p-5">
              <p className="mb-3 text-[11px] font-semibold uppercase tracking-[.16em] text-zinc-500">{asks.answered.length ? t("me.asksAnswered", { count: asks.answered.length }) : t("me.asksEmpty")}</p>
              {asks.answered.map((item) => <AskCard key={item.id} item={item} draft={drafts[item.id] || ""} busy={Boolean(busy[item.id])} onChange={(value) => setDrafts((current) => ({ ...current, [item.id]: value }))} onAnswer={() => sendAnswer(item)} onBin={() => bin(item)} />)}
            </div>
          </section>

          <section>
            <SectionTitle icon={BookOpen} title={t("me.guestbookTitle")} description={t("me.guestbookDescription")} />
            <div className="surface rounded-2xl p-5">
              <p className="mb-3 text-[11px] font-semibold uppercase tracking-[.16em] text-[#fb7185]">{guestbook.pending.length ? t("me.guestbookPending", { count: guestbook.pending.length }) : t("me.guestbookEmptyPending")}</p>
              {guestbook.pending.map((item) => <SignatureRow key={item.id} item={item} busy={Boolean(busy[item.id])} onApprove={() => approveEntry(item)} onBin={() => binEntry(item)} />)}
            </div>
            <div className="surface mt-4 rounded-2xl p-5">
              <p className="mb-3 text-[11px] font-semibold uppercase tracking-[.16em] text-zinc-500">{guestbook.approved.length ? t("me.guestbookApproved", { count: guestbook.approved.length }) : t("me.guestbookEmptyApproved")}</p>
              {guestbook.approved.map((item) => <SignatureRow key={item.id} item={item} busy={Boolean(busy[item.id])} onApprove={undefined} onBin={() => binEntry(item)} />)}
            </div>
          </section>

          <section>
            <SectionTitle icon={Paintbrush} title={t("me.doodlesTitle")} description={t("me.doodlesDescription")} />
            <div className="surface rounded-2xl p-5">
              <p className="mb-3 text-[11px] font-semibold uppercase tracking-[.16em] text-[#fb7185]">{doodles.pending.length ? t("me.doodlesPending", { count: doodles.pending.length }) : t("me.doodlesEmptyPending")}</p>
              {doodles.pending.length ? <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{doodles.pending.map((item) => <DoodleTile key={item.id} item={item} busy={Boolean(busy[item.id])} onApprove={() => keepDoodle(item)} onBin={() => binTile(item)} />)}</div> : <p className="text-xs text-zinc-600">{t("me.doodlesEmptyPending")}</p>}
            </div>
            <div className="surface mt-4 rounded-2xl p-5">
              <p className="mb-3 text-[11px] font-semibold uppercase tracking-[.16em] text-zinc-500">{doodles.approved.length ? t("me.doodlesApproved", { count: doodles.approved.length }) : t("me.doodlesEmptyApproved")}</p>
              {doodles.approved.length ? <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{doodles.approved.map((item) => <DoodleTile key={item.id} item={item} busy={Boolean(busy[item.id])} onApprove={undefined} onBin={() => binTile(item)} />)}</div> : <p className="text-xs text-zinc-600">{t("me.doodlesEmptyApproved")}</p>}
            </div>
          </section>

          <section>
            <SectionTitle icon={ListChecks} title={t("me.tallyTitle")} description={t("me.tallyDescription")} />
            <div className="surface rounded-2xl p-5">
              {tallyEnabled ? (
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <p className="text-sm text-zinc-200">{t("me.tallyQuestion")}: <span className="text-white">{tally?.q}</span></p>
                    <p className="mt-1 text-xs text-zinc-500">{tally?.options?.join(" · ")}</p>
                  </div>
                  <Button variant="ghost" className="h-9 min-h-0 px-3 text-xs text-red-300" disabled={Boolean(busy.tally)} onClick={clearMyTally}><Trash2 size={13} />{t("me.tallyClear")}</Button>
                </div>
              ) : <p className="text-xs text-zinc-600">{t("me.tallyOff")}</p>}
            </div>
          </section>

          <section>
            <SectionTitle icon={KeyRound} title={t("me.secretTitle")} description={t("me.secretDescription")} />
            <div className="surface rounded-2xl p-5">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-zinc-300">{secretOn ? t("me.secretOn") : t("me.secretOff")}</p>
                <StatusPill on={secretOn} />
              </div>
              <p className="mt-3 text-xs text-zinc-500">{secretOn ? (String(secret?.wordHash || "").length ? t("me.secretWordSet") : t("me.secretNoWord")) : ""}</p>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}

function AskCard({ item, draft, busy, onChange, onAnswer, onBin }: { item: AskItem; draft: string; busy: boolean; onChange: (value: string) => void; onAnswer: () => void; onBin: () => void }) {
  const t = useT();
  return (
    <div className="border-b border-white/[.06] py-4 last:border-b-0">
      <div className="flex items-baseline justify-between gap-3">
        <p className="text-sm text-zinc-200">{item.q}</p>
        <span className="shrink-0 text-[10px] text-zinc-600">{timeAgo(item.at)}</span>
      </div>
      <div className="mt-3 flex gap-2">
        <TextInput value={draft} onChange={onChange} placeholder={t("me.askPlaceholder")} className="flex-1" />
        <Button variant="accent" className="h-11 min-h-0 px-3 text-xs" disabled={busy || !draft.trim()} onClick={onAnswer}>{item.a ? <><Check size={13} />{t("me.askSave")}</> : <><Send size={13} />{t("me.askAnswer")}</>}</Button>
        <Button variant="ghost" className="h-11 min-h-0 px-3 text-xs" disabled={busy} onClick={onBin}><Trash2 size={13} />{t("me.bin")}</Button>
      </div>
    </div>
  );
}

function SignatureRow({ item, busy, onApprove, onBin }: { item: GuestbookItem; busy: boolean; onApprove: (() => void) | undefined; onBin: () => void }) {
  const t = useT();
  return (
    <div className="flex items-start justify-between gap-3 border-b border-white/[.06] py-4 last:border-b-0">
      <div className="min-w-0">
        <p className="text-sm text-zinc-200">{item.line}</p>
        <p className="mt-1 text-xs text-zinc-500">— {item.name || "anonymous"} · {timeAgo(item.at)}</p>
      </div>
      <div className="flex shrink-0 gap-2">
        {onApprove && <Button variant="subtle" className="h-8 min-h-0 px-3 text-xs" disabled={busy} onClick={onApprove}><Check size={13} />{t("me.approve")}</Button>}
        <Button variant="ghost" className="h-8 min-h-0 px-3 text-xs" disabled={busy} onClick={onBin}><Trash2 size={13} />{t("me.bin")}</Button>
      </div>
    </div>
  );
}

function DoodleTile({ item, busy, onApprove, onBin }: { item: DoodleItem; busy: boolean; onApprove: (() => void) | undefined; onBin: () => void }) {
  const t = useT();
  const svg = safeSvg(item.svg);
  const isDataUrl = String(item.svg || "").startsWith("data:image/");
  return (
    <div className="rounded-xl border border-white/[.06] bg-white/[.02] p-3">
      <div className="flex h-32 items-center justify-center overflow-hidden rounded-lg border border-white/[.05] bg-white/[.03]">
        {isDataUrl ? <img src={item.svg} alt="" className="max-h-full max-w-full object-contain" /> : svg ? <div className="max-h-full max-w-full" dangerouslySetInnerHTML={{ __html: svg }} /> : <p className="text-[10px] text-zinc-600">{t("me.doodlesEmptyPending")}</p>}
      </div>
      <div className="mt-2 flex items-center justify-between gap-2">
        <span className="text-[10px] text-zinc-600">{timeAgo(item.at)}</span>
        <div className="flex gap-2">
          {onApprove && <Button variant="subtle" className="h-8 min-h-0 px-3 text-xs" disabled={busy} onClick={onApprove}><Check size={13} />{t("me.keep")}</Button>}
          <Button variant="ghost" className="h-8 min-h-0 px-3 text-xs" disabled={busy} onClick={onBin}><Trash2 size={13} />{t("me.bin")}</Button>
        </div>
      </div>
    </div>
  );
}