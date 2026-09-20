"use client";

import { useEffect, useState, type CSSProperties } from "react";
import { renderSafeMarkdown } from "@/lib/markdown";
import { parseLyrics, sectionCoverSrc, sectionLabel } from "@/lib/sections";
import type { ProfileConfig, ProfileSection } from "@/lib/types";

export function ProfileSections({ config, preview = false }: { config: ProfileConfig; preview?: boolean }) {
  const sections = (config.sections || []).filter((item) => item.enabled);
  const swap = Boolean(config.settings.widgetColorSwap);
  const ink = config.settings.backgroundColor;
  const accent = config.settings.accentColor;
  const time = useAudioClock();
  if (sections.length === 0) return null;
  return (
    <div className="mt-6 space-y-2.5 text-left" onClick={(event) => event.stopPropagation()} onPointerDown={(event) => event.stopPropagation()}>
      {sections.map((item) => (
        <SectionCard key={item.id} item={item} config={config} preview={preview} time={time} swap={swap} accent={accent} ink={ink} />
      ))}
    </div>
  );
}

function SectionCard({ item, config, preview, time, swap, accent, ink }: { item: ProfileSection; config: ProfileConfig; preview: boolean; time: number; swap: boolean; accent: string; ink: string }) {
  const className = `rounded-2xl border p-3 ${swap ? "" : "border-white/[.1] bg-black/25 text-white"}`;
  const style = swap ? { backgroundColor: accent, color: ink, borderColor: `${ink}33` } : undefined;
  const muted = swap ? { opacity: 0.7 } : undefined;
  if (item.type === "skills") {
    const tags = item.tags || [];
    if (!preview && tags.length === 0) return null;
    return (
      <section className={className} style={style}>
        {item.title && <h2 className="text-sm font-semibold">{item.title}</h2>}
        <div className="mt-2 flex flex-wrap gap-1.5">
          {tags.length ? tags.map((tag) => (
            <span key={tag} className={`rounded-full px-2 py-0.5 text-[10px] ${swap ? "" : "bg-white/10 text-white/80"}`} style={swap ? { backgroundColor: `${ink}22` } : undefined}>{tag}</span>
          )) : <p className="text-[11px] opacity-50">Add skills in Portfolio.</p>}
        </div>
      </section>
    );
  }
  if (item.type === "project") {
    const cover = sectionCoverSrc(config.profile.username, item, preview);
    if (!preview && !item.title && !item.body && !cover && !item.href) return null;
    const inner = (
      <>
        {cover ? <img src={cover} alt="" className="h-16 w-16 shrink-0 rounded-xl object-cover" /> : null}
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold">{item.title || (preview ? "Project" : "")}</h2>
          {item.body ? <Markdown body={item.body} className="mt-1 text-[13px] leading-5" style={muted} /> : preview ? <p className="mt-1 text-[11px] opacity-50">Add a description.</p> : null}
          {!!item.tags?.length && (
            <div className="mt-2 flex flex-wrap gap-1.5">
              {item.tags.map((tag) => <span key={tag} className={`rounded-full px-2 py-0.5 text-[10px] ${swap ? "" : "bg-white/10 text-white/80"}`} style={swap ? { backgroundColor: `${ink}22` } : undefined}>{tag}</span>)}
            </div>
          )}
        </div>
      </>
    );
    if (item.href && !preview) {
      return <a href={item.href} target="_blank" rel="noopener noreferrer" className={`${className} flex items-start gap-3 no-underline`} style={style}>{inner}</a>;
    }
    return <section className={`${className} flex items-start gap-3`} style={style}>{inner}</section>;
  }
  if (item.type === "lyrics") {
    const lines = parseLyrics(item.body);
    if (!preview && lines.length === 0) return null;
    let active = -1;
    lines.forEach((line, index) => {
      if (line.t != null && time >= line.t) active = index;
    });
    return (
      <section className={className} style={style}>
        <h2 className="text-sm font-semibold">{item.title || sectionLabel(item.type)}</h2>
        <div className={`mt-2 max-h-40 overflow-auto${preview ? "" : " hide-scroll"}`}>
          {lines.length ? lines.map((line, index) => (
            <p key={`${line.text}-${index}`} className={`py-0.5 text-[13px] ${index === active ? "font-semibold opacity-100" : "opacity-50"}`}>{line.text}</p>
          )) : <p className="text-[11px] opacity-50">Add LRC lines in Portfolio.</p>}
        </div>
      </section>
    );
  }
  if (!preview && !item.body && !item.title) return null;
  return (
    <section className={className} style={style}>
      {item.title && <h2 className="text-sm font-semibold">{item.title}</h2>}
      {item.body ? <Markdown body={item.body} className={item.title ? "mt-1 text-[13px] leading-5" : "text-[13px] leading-5"} style={muted} /> : preview ? <p className="text-[11px] opacity-50">Add Markdown in Portfolio.</p> : null}
    </section>
  );
}

function Markdown({ body, className, style }: { body: string; className?: string; style?: CSSProperties }) {
  return <div className={`[&_a]:underline [&_code]:rounded [&_code]:bg-white/10 [&_code]:px-1 [&_h2]:text-sm [&_h3]:text-sm [&_li]:my-0.5 [&_ol]:ml-4 [&_p]:mb-2 [&_p:last-child]:mb-0 [&_ul]:ml-4 ${className || ""}`} style={style} dangerouslySetInnerHTML={{ __html: renderSafeMarkdown(body) }} />;
}

function useAudioClock() {
  const [time, setTime] = useState(0);
  useEffect(() => {
    const tick = () => {
      const audio = document.querySelector("audio");
      setTime(audio?.currentTime || 0);
    };
    const timer = window.setInterval(tick, 250);
    return () => window.clearInterval(timer);
  }, []);
  return time;
}
