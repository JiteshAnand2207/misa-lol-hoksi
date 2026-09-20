"use client";

import { useEffect, useRef, useState } from "react";
import { Check, ChevronDown, Languages } from "lucide-react";
import { LOCALES, useI18n } from "@/lib/i18n";

export function LanguageSelect({ compact = false }: { compact?: boolean }) {
  const { locale, setLocale, t } = useI18n();
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const current = LOCALES.find((item) => item.id === locale) || LOCALES[0];

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: MouseEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    window.addEventListener("mousedown", onPointer);
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("mousedown", onPointer);
      window.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div ref={root} className={`relative ${compact ? "" : "w-full"}`}>
      <button
        type="button"
        aria-label={t("language.label")}
        aria-expanded={open}
        aria-haspopup="listbox"
        onClick={() => setOpen((value) => !value)}
        className={`flex w-full items-center gap-3 rounded-xl border border-white/[.08] bg-black/20 text-sm text-zinc-300 outline-none transition hover:border-white/[.14] hover:bg-white/[.04] ${compact ? "h-9 px-3" : "h-11 px-3.5"}`}
      >
        <Languages size={15} className="shrink-0 text-zinc-600" />
        <span className="min-w-0 flex-1 truncate text-start text-zinc-200">{current.native}</span>
        <ChevronDown size={14} className={`shrink-0 text-zinc-600 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <ul
          role="listbox"
          aria-label={t("language.label")}
          className={`glass-floating absolute z-40 w-full min-w-[228px] overflow-hidden rounded-[14px] p-1.5 ${compact ? "bottom-[calc(100%+8px)] start-0" : "top-[calc(100%+8px)] start-0"}`}
        >
          {LOCALES.map((item) => {
            const selected = item.id === locale;
            return (
              <li key={item.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={selected}
                  onClick={() => {
                    setLocale(item.id);
                    setOpen(false);
                  }}
                  className={`flex w-full items-center gap-3 rounded-[10px] px-3 py-2 text-start transition ${selected ? "bg-[#e11d48]/16 text-white" : "text-zinc-300 hover:bg-white/[.07] hover:text-white"}`}
                >
                  <span className="min-w-0 flex-1">
                    <span className="block text-[13px] leading-5">{item.native}</span>
                    <span className="mt-0.5 block text-[10px] leading-4 text-zinc-500">{item.name}</span>
                  </span>
                  {selected ? <Check size={14} className="shrink-0 text-[#b6aaff]" /> : <span className="h-3.5 w-3.5 shrink-0" />}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
