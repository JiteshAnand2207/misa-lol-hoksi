"use client";

import { useEffect, useMemo, useState } from "react";
import type { ProfileConfig, ProfileWidget, ResolvedWidget } from "@/lib/types";
import { emptyResolvedWidget, previewResolvedWidget, widgetLabel } from "@/lib/widgets";

export function ProfileWidgets({ config, preview = false }: { config: ProfileConfig; preview?: boolean }) {
  const widgets = useMemo(() => (config.widgets || []).filter((item) => item.enabled), [config.widgets]);
  const [resolved, setResolved] = useState<ResolvedWidget[]>([]);
  const [loading, setLoading] = useState(false);
  const swap = Boolean(config.settings.widgetColorSwap);
  const ink = config.settings.backgroundColor;
  const accent = config.settings.accentColor;
  const signature = widgets.map((item) => `${item.id}:${item.type}:${item.value}`).join("|");

  useEffect(() => {
    if (widgets.length === 0) {
      setResolved([]);
      setLoading(false);
      return;
    }
    let cancelled = false;
    const timer = window.setTimeout(async () => {
      setLoading(true);
      try {
        const response = preview
          ? await fetch("/api/v1/widgets/preview", {
              method: "POST",
              credentials: "include",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({ widgets }),
            })
          : await fetch(`/api/v1/profile/${encodeURIComponent(config.profile.username)}/widgets`, { cache: "no-store" });
        if (!response.ok) {
          // Local preview can run without a signed-in API session. Keep the
          // cards visible there; live profiles still use the backend resolver.
          if (preview) {
            if (!cancelled) setResolved(widgets.map(previewResolvedWidget));
            return;
          }
          throw new Error(`Widget request failed (${response.status})`);
        }
        const data = await response.json() as { widgets?: ResolvedWidget[] };
        if (!Array.isArray(data.widgets)) throw new Error("Widget response was invalid");
        if (!cancelled) setResolved(data.widgets);
      } catch {
        if (!cancelled) setResolved(widgets.map((item) => emptyResolvedWidget(item, "error")));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }, preview ? 400 : 0);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [signature, preview, config.profile.username, widgets]);

  if (widgets.length === 0) return null;

  const cards = resolved.length ? resolved : (loading ? widgets.map((item) => emptyResolvedWidget(item)) : []);

  return (
    <div className="mt-6 space-y-2.5" onClick={(event) => event.stopPropagation()} onPointerDown={(event) => event.stopPropagation()}>
      {loading && resolved.length === 0
        ? widgets.map((item) => <WidgetSkeleton key={item.id} swap={swap} accent={accent} ink={ink} />)
        : cards.map((item) => <WidgetCard key={item.id} widget={item} swap={swap} accent={accent} ink={ink} />)}
    </div>
  );
}

function WidgetCard({ widget, swap, accent, ink }: { widget: ResolvedWidget; swap: boolean; accent: string; ink: string }) {
  const className = `flex items-center gap-3 rounded-2xl border p-3 text-left no-underline ${swap ? "" : "border-white/[.1] bg-black/25 text-white"} ${widget.status !== "ok" ? "opacity-85" : ""}`;
  const style = swap ? { backgroundColor: accent, color: ink, borderColor: `${ink}33` } : undefined;
  const inner = (
    <>
      {widget.image ? (
        <img src={widget.image} alt="" className="h-14 w-14 shrink-0 rounded-xl object-cover" />
      ) : (
        <div className={`grid h-14 w-14 shrink-0 place-items-center rounded-xl text-[10px] uppercase tracking-[.06em] ${swap ? "" : "bg-white/[.06] text-white/40"}`} style={swap ? { backgroundColor: `${ink}1a` } : undefined}>
          {widgetLabel(widget.type)}
        </div>
      )}
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">{widget.type === "timezone" && widget.meta?.timezone ? <ClockTitle timezone={widget.meta.timezone} initial={widget.title} /> : widget.title || widgetLabel(widget.type)}</p>
        <p className={`mt-0.5 truncate text-[11px] ${swap ? "" : "text-white/40"}`} style={swap ? { opacity: 0.66 } : undefined}>{widget.subtitle}</p>
      </div>
    </>
  );
  if (widget.href && widget.status === "ok") {
    return <a href={widget.href} target="_blank" rel="noopener noreferrer" className={className} style={style}>{inner}</a>;
  }
  return <div className={className} style={style}>{inner}</div>;
}

function WidgetSkeleton({ swap, accent, ink }: { swap: boolean; accent: string; ink: string }) {
  return (
    <div className={`flex animate-pulse items-center gap-3 rounded-2xl border p-3 ${swap ? "" : "border-white/[.1] bg-black/25"}`} style={swap ? { backgroundColor: accent, borderColor: `${ink}33` } : undefined}>
      <div className={`h-14 w-14 rounded-xl ${swap ? "" : "bg-white/[.08]"}`} style={swap ? { backgroundColor: `${ink}22` } : undefined} />
      <div className="min-w-0 flex-1 space-y-2">
        <div className={`h-3 w-2/3 rounded ${swap ? "" : "bg-white/[.08]"}`} style={swap ? { backgroundColor: `${ink}22` } : undefined} />
        <div className={`h-2.5 w-1/2 rounded ${swap ? "" : "bg-white/[.06]"}`} style={swap ? { backgroundColor: `${ink}1a` } : undefined} />
      </div>
    </div>
  );
}

function ClockTitle({ timezone, initial }: { timezone: string; initial: string }) {
  const [text, setText] = useState(initial);
  useEffect(() => {
    const tick = () => {
      try {
        setText(new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", hour12: false, timeZone: timezone }).format(new Date()));
      } catch {
        setText(initial);
      }
    };
    tick();
    const timer = window.setInterval(tick, 15000);
    return () => window.clearInterval(timer);
  }, [timezone, initial]);
  return <>{text}</>;
}

export function widgetCount(widgets: ProfileWidget[] | undefined) {
  return (widgets || []).filter((item) => item.enabled).length;
}
