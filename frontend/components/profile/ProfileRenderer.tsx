"use client";

import { AnimatePresence, motion } from "framer-motion";
import { type CSSProperties, useEffect, useLayoutEffect, useRef, useState } from "react";
import { ProfileAvatar, ProfileBanner, ProfileIdentity, ProfileMediaModules, ProfileMeta, ProfileModules } from "@/components/profile/ProfileCardModules";
import { BackgroundEffectLayer } from "@/components/profile/BackgroundEffectLayer";
import { playClickSound, prefersReducedMotion } from "@/lib/enter";
import { resolvedAudioSource } from "@/lib/audio";
import { useDefaultFonts } from "@/lib/default-fonts";
import { contentAlign, profileFont, profileLayout } from "@/lib/profile-layout";
import { typeSize } from "@/lib/typography";
import type { ProfileConfig } from "@/lib/types";

function colorWithAlpha(value: string | undefined, alpha: number) {
  const raw = (value || "#ffffff").replace("#", "");
  const hex = raw.length === 3 ? raw.split("").map((part) => part + part).join("") : raw.slice(0, 6);
  if (!/^[0-9a-f]{6}$/i.test(hex)) return "rgba(255,255,255," + alpha.toFixed(3) + ")";
  const red = parseInt(hex.slice(0, 2), 16);
  const green = parseInt(hex.slice(2, 4), 16);
  const blue = parseInt(hex.slice(4, 6), 16);
  return "rgba(" + red + "," + green + "," + blue + "," + alpha.toFixed(3) + ")";
}

type FrameResizeHandle = "n" | "ne" | "e" | "se" | "s" | "sw" | "w" | "nw";
type FrameDragMode = "move" | FrameResizeHandle;
type FramePositionPatch = { profileFrameScale?: number; profileFrameWidth?: number; profileFrameHeight?: number; profileFrameX?: number; profileFrameY?: number };

const FRAME_RESIZE_HANDLES: Array<{ id: FrameResizeHandle; className: string }> = [
  { id: "nw", className: "-left-2 -top-2 cursor-nwse-resize" },
  { id: "n", className: "left-1/2 -top-2 -translate-x-1/2 cursor-ns-resize" },
  { id: "ne", className: "-right-2 -top-2 cursor-nesw-resize" },
  { id: "e", className: "-right-2 top-1/2 -translate-y-1/2 cursor-ew-resize" },
  { id: "se", className: "-bottom-2 -right-2 cursor-nwse-resize" },
  { id: "s", className: "-bottom-2 left-1/2 -translate-x-1/2 cursor-ns-resize" },
  { id: "sw", className: "-bottom-2 -left-2 cursor-nesw-resize" },
  { id: "w", className: "-left-2 top-1/2 -translate-y-1/2 cursor-ew-resize" },
];

export function ProfileRenderer({ config, preview = false, screenshot = false, className = "", manualPositioning = false, onFramePositionChange, fitViewport = false, embedded = false }: { config: ProfileConfig; preview?: boolean; screenshot?: boolean; className?: string; manualPositioning?: boolean; onFramePositionChange?: (patch: FramePositionPatch) => void; fitViewport?: boolean; embedded?: boolean }) {
  const rootRef = useRef<HTMLDivElement>(null);
  const frameStageRef = useRef<HTMLDivElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const s = config.settings;
  const defaultFonts = useDefaultFonts();
  const selectedDefaultFont = defaultFonts.find((font) => font.id === s.profileFont);
  const layout = profileLayout(s);
  const align = contentAlign(s.socialAlign);
  const customCursor = config.assets.cursor.url ? { cursor: `url(${config.assets.cursor.url}), auto` } : undefined;
  const customFont = config.assets.customFont?.url || "";
  const family = customFont
    ? `"MisaProfile", "Inter", ui-sans-serif, system-ui, sans-serif`
    : selectedDefaultFont?.url
      ? `"MisaDefaultFont", "Inter", ui-sans-serif, system-ui, sans-serif`
      : profileFont(s.profileFont);
  const pageFamily = "Inter, ui-sans-serif, system-ui, sans-serif";
  const [entered, setEntered] = useState(embedded || !s.entryScreen);
  const [quiet, setQuiet] = useState(false);
  useEffect(() => { setQuiet(prefersReducedMotion()); }, []);
  useEffect(() => { setEntered(embedded || !s.entryScreen); }, [embedded, s.entryScreen, s.pageEnter]);
  const enter = s.pageEnter || "Fade";
  const motionStart = screenshot
    ? { opacity: 1, scale: 1, scaleY: 1 }
    : quiet || !entered || enter === "None"
      ? false
    : enter === "Unfold"
      ? { opacity: 0, scaleY: 0.12 }
      : enter === "Pop"
        ? { opacity: 0, scale: 0.86 }
        : { opacity: 0 };
  const frameAnchor = s.cardAlign === "left" ? 25 : s.cardAlign === "right" ? 75 : 50;
  const frameScale = Math.min(150, Math.max(50, s.profileFrameScale ?? 100)) / 100;
  const frameWidth = Math.min(800, Math.max(260, s.profileFrameWidth ?? 430));
  const storedFrameHeight = Math.min(1000, Math.max(0, s.profileFrameHeight ?? 0));
  const frameHeight = storedFrameHeight >= 200 ? storedFrameHeight : 0;
  const frameX = Math.min(45, Math.max(-45, s.profileFrameX ?? 0));
  const frameY = Math.min(45, Math.max(-45, s.profileFrameY ?? 0));
  const showFrame = s.showProfileFrame !== false;
  const frameOpacity = Math.min(100, Math.max(0, s.profileFrameOpacity ?? 100)) / 100;
  const frameDrag = useRef<{ mode: FrameDragMode; pointerId: number; startX: number; startY: number; baseX: number; baseY: number; baseWidth: number; baseHeight: number } | null>(null);
  const frameVisible = showFrame && frameOpacity > 0;
  const audioSource = resolvedAudioSource(config.assets);
  const [fit, setFit] = useState({ width: 0, height: 0, stageWidth: 0, stageHeight: 0 });

  useLayoutEffect(() => {
    const root = rootRef.current;
    const stage = frameStageRef.current;
    if (!root || !stage || embedded) return;
    const measure = () => {
      const next = { width: root.clientWidth, height: root.clientHeight, stageWidth: stage.offsetWidth, stageHeight: stage.offsetHeight };
      setFit((current) => current.width === next.width && current.height === next.height && current.stageWidth === next.stageWidth && current.stageHeight === next.stageHeight ? current : next);
    };
    const observer = new ResizeObserver(measure);
    observer.observe(root);
    observer.observe(stage);
    window.visualViewport?.addEventListener("resize", measure);
    measure();
    return () => {
      observer.disconnect();
      window.visualViewport?.removeEventListener("resize", measure);
    };
  }, [embedded, entered]);

  const compactViewport = !embedded && fit.width > 0 && fit.width < 640;
  const responsiveFrameScale = compactViewport && fit.stageWidth > 0 && fit.stageHeight > 0
    ? Math.min(frameScale, Math.max(0.1, (fit.width - 24) / fit.stageWidth), Math.max(0.1, (fit.height - 24) / fit.stageHeight))
    : frameScale;
  const availableOffsetX = Math.max(0, (fit.width - fit.stageWidth * responsiveFrameScale) / 2 - 12);
  const availableOffsetY = Math.max(0, (fit.height - fit.stageHeight * responsiveFrameScale) / 2 - 12);
  const safeFrameX = Math.min(availableOffsetX, Math.max(-availableOffsetX, frameX / 100 * fit.width));
  const safeFrameY = Math.min(availableOffsetY, Math.max(-availableOffsetY, frameY / 100 * fit.height));

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    video.volume = Math.min(1, Math.max(0, config.assets.volume / 100));
    video.muted = audioSource !== "video";
    if (entered) void video.play().catch(() => undefined);
  }, [audioSource, config.assets.backgroundVideo.url, config.assets.volume, entered]);
  const tap = () => { if (s.clickSound) playClickSound(config.assets.clickSound?.url); };
  const openPage = () => { tap(); setEntered(true); };
  const tilt = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!s.cardTilt || quiet || !cardRef.current) return;
    const box = cardRef.current.getBoundingClientRect();
    const x = (event.clientX - box.left) / box.width - 0.5;
    const y = (event.clientY - box.top) / box.height - 0.5;
    cardRef.current.style.transform = `rotateX(${(-y * 7).toFixed(2)}deg) rotateY(${(x * 9).toFixed(2)}deg)`;
  };
  const untilt = () => { if (cardRef.current) cardRef.current.style.transform = ""; };
  const startFrameDrag = (event: React.PointerEvent<HTMLDivElement>, mode: FrameDragMode = "move") => {
    if (!manualPositioning || !onFramePositionChange || event.button !== 0) return;
    event.preventDefault();
    event.stopPropagation();
    frameDrag.current = {
      mode,
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      baseX: frameX,
      baseY: frameY,
      baseWidth: cardRef.current?.offsetWidth || frameWidth,
      baseHeight: cardRef.current?.offsetHeight || frameHeight || 360,
    };
    event.currentTarget.setPointerCapture(event.pointerId);
  };
  const moveFrameDrag = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = frameDrag.current;
    if (!drag || drag.pointerId !== event.pointerId || !onFramePositionChange) return;
    const viewportWidth = typeof window === "undefined" ? 1 : window.innerWidth;
    const viewportHeight = typeof window === "undefined" ? 1 : window.innerHeight;
    const deltaX = event.clientX - drag.startX;
    const deltaY = event.clientY - drag.startY;
    if (drag.mode !== "move") {
      const horizontalDelta = deltaX / frameScale;
      const verticalDelta = deltaY / frameScale;
      const changesWidth = drag.mode.includes("e") || drag.mode.includes("w");
      const changesHeight = drag.mode.includes("n") || drag.mode.includes("s");
      const nextWidth = changesWidth
        ? Math.min(800, Math.max(260, drag.baseWidth + (drag.mode.includes("w") ? -horizontalDelta : horizontalDelta)))
        : drag.baseWidth;
      const nextHeight = changesHeight
        ? Math.min(1000, Math.max(200, drag.baseHeight + (drag.mode.includes("n") ? -verticalDelta : verticalDelta)))
        : drag.baseHeight;
      const widthChange = nextWidth - drag.baseWidth;
      const heightChange = nextHeight - drag.baseHeight;
      const shiftX = drag.mode.includes("w") ? -widthChange / 2 : drag.mode.includes("e") ? widthChange / 2 : 0;
      const shiftY = drag.mode.includes("n") ? -heightChange / 2 : drag.mode.includes("s") ? heightChange / 2 : 0;
      const patch: FramePositionPatch = {
        profileFrameX: Math.round(Math.min(45, Math.max(-45, drag.baseX + ((shiftX * frameScale) / viewportWidth) * 100)) * 10) / 10,
        profileFrameY: Math.round(Math.min(45, Math.max(-45, drag.baseY + ((shiftY * frameScale) / viewportHeight) * 100)) * 10) / 10,
      };
      if (changesWidth) patch.profileFrameWidth = Math.round(nextWidth);
      if (changesHeight) patch.profileFrameHeight = Math.round(nextHeight);
      onFramePositionChange(patch);
      return;
    }
    onFramePositionChange({
      profileFrameX: Math.round(Math.min(45, Math.max(-45, drag.baseX + (deltaX / viewportWidth) * 100)) * 10) / 10,
      profileFrameY: Math.round(Math.min(45, Math.max(-45, drag.baseY + (deltaY / viewportHeight) * 100)) * 10) / 10,
    });
  };
  const endFrameDrag = (event: React.PointerEvent<HTMLDivElement>) => {
    if (frameDrag.current?.pointerId === event.pointerId) frameDrag.current = null;
  };
  return (
    <div ref={rootRef} className={`relative isolate ${embedded ? "h-full min-h-0 overflow-visible bg-transparent" : (fitViewport || screenshot ? "h-full min-h-0 overflow-hidden bg-[#07070a]" : "min-h-[100svh] overflow-hidden bg-[#07070a]")} ${preview ? "rounded-[inherit]" : ""} ${className}`} style={{ ...customCursor, fontFamily: pageFamily, fontSize: typeSize(s.fontSize), ["--misa-profile-font" as string]: family } as CSSProperties}>
      {customFont ? <style>{`@font-face{font-family:MisaProfile;src:url("${customFont}");font-display:swap}`}</style> : null}
      {selectedDefaultFont?.url ? <style>{`@font-face{font-family:MisaDefaultFont;src:url("${selectedDefaultFont.url}");font-display:swap}`}</style> : null}
      {!embedded && <ProfileBackground config={config} videoRef={videoRef} reduceMotion={quiet} />}
      {!embedded && <div className="pointer-events-none absolute inset-0 bg-black/35" />}
      <div className={"relative z-10 " + (embedded || fitViewport || screenshot ? "h-full" : "min-h-[100svh]") + (embedded ? "" : " px-4 py-10 sm:px-8")} style={{ perspective: s.cardTilt ? 900 : undefined }}>
        {!embedded && s.entryScreen && !entered && (
          <button type="button" className="absolute inset-0 z-20 grid place-items-center bg-black/60 text-white" onClick={openPage}>
            <span className="flex flex-col items-center gap-3">
              <span className="flex h-12 w-12 items-center justify-center rounded-2xl border border-white/20 bg-white/10 text-lg">▶</span>
              <span className="text-xs text-white/70">{s.entryText || "click to enter..."}</span>
            </span>
          </button>
        )}
        <AnimatePresence initial={false}>
          {entered && (
            <div ref={frameStageRef} className={"absolute " + (manualPositioning ? "cursor-move touch-none" : "")} onPointerDown={startFrameDrag} onPointerMove={moveFrameDrag} onPointerUp={endFrameDrag} onPointerCancel={endFrameDrag} style={{ width: frameWidth + "px", maxWidth: "calc(100% - 24px)", left: (embedded || compactViewport ? 50 : frameAnchor) + "%", top: "50%", transformOrigin: "center", transform: embedded ? "translate(-50%, -50%) scale(" + frameScale + ")" : compactViewport ? `translate(-50%, -50%) translate(${safeFrameX}px, ${safeFrameY}px) scale(${responsiveFrameScale})` : "translate(calc(-50% + " + frameX + "vw), calc(-50% + " + frameY + "vh)) scale(" + frameScale + ")" }}>
              <motion.div key="profile-card" initial={motionStart} animate={{ opacity: 1, scale: 1, scaleY: 1 }} transition={{ duration: screenshot || quiet ? 0 : 0.55, ease: [0.22, 1, .36, 1] }} className="relative w-full" style={{ transformOrigin: enter === "Unfold" ? "top center" : undefined, opacity: screenshot ? 1 : undefined }} onClick={(event) => { const node = event.target as HTMLElement; if (node.closest("a, button, [data-copy]")) tap(); }}>
                <div
                  ref={cardRef}
                  onPointerMove={manualPositioning ? undefined : tilt}
                  onPointerLeave={manualPositioning ? undefined : untilt}
                  className={"relative overflow-hidden shadow-2xl transition-transform duration-150 " + (layout === "Sleek" ? "p-0" : layout === "Simplistic" ? "p-6 sm:p-7" : "p-7 sm:p-9")}
                  style={{
                    borderRadius: s.profileRadius + "px",
                    backgroundColor: frameVisible ? "rgba(8,8,13," + (((layout === "Simplistic" ? Math.min(s.profileOpacity + 8, 80) : s.profileOpacity) / 100) * frameOpacity) + ")" : "transparent",
                    backgroundImage: frameVisible && s.profileGradient && layout !== "Simplistic" ? "linear-gradient(145deg, " + colorWithAlpha(s.accentColor, 0.07 * frameOpacity) + ", transparent 40%)" : "none",
                    backdropFilter: frameVisible ? "blur(" + (layout === "Simplistic" ? Math.max(s.profileBlur - 10, 0) : s.profileBlur) + "px)" : "none",
                    border: frameVisible ? (s.borderWidth ?? 1) + "px solid " + colorWithAlpha(s.borderColor, frameOpacity) : "0 solid transparent",
                    boxShadow: embedded ? "none" : frameVisible ? (layout === "Simplistic" ? "0 12px 40px rgba(0,0,0," + (0.22 * frameOpacity).toFixed(3) + ")" : "0 25px 90px rgba(0,0,0," + (0.36 * frameOpacity).toFixed(3) + "), 0 0 70px " + colorWithAlpha(s.accentColor, 0.09 * frameOpacity)) : "none",
                    color: s.textColor,
                    minHeight: frameHeight ? frameHeight + "px" : undefined,
                  }}
                >
                  {layout === "Modern" && frameVisible && <div className="absolute inset-x-8 top-0 h-px" style={{ background: "linear-gradient(90deg, transparent, " + s.accentColor + "aa, transparent)" }} />}
                  {layout === "Modern" && <ModernCard config={config} preview={preview} align={align} />}
                  {layout === "Simplistic" && <SimplisticCard config={config} preview={preview} align={align} />}
                  {layout === "Sleek" && <SleekCard config={config} preview={preview} align={align} />}
                </div>
                {manualPositioning && <>
                  <div className="pointer-events-none absolute inset-0 border border-sky-300/80" style={{ borderRadius: s.profileRadius + "px" }} />
                  {FRAME_RESIZE_HANDLES.map((handle) => <div key={handle.id} role="presentation" aria-label={`Resize profile frame ${handle.id}`} onPointerDown={(event) => startFrameDrag(event, handle.id)} className={`pointer-events-auto absolute z-30 h-4 w-4 rounded-full border-2 border-white bg-sky-500 shadow-lg ${handle.className}`} />)}
                </>}
              </motion.div>
              <ProfileMediaModules config={config} preview={preview} />
            </div>
          )}
        </AnimatePresence>
      </div>
      {entered && <ProfileMeta config={config} align="left" floating />}
    </div>
  );
}

function ModernCard({ config, preview, align }: { config: ProfileConfig; preview: boolean; align: "left" | "center" | "right" }) {
  return (
    <>
      <ProfileBanner config={config} />
      <div className={config.assets.banner?.url ? "pt-5" : ""}>
        {config.settings.showAvatar !== false && <ProfileAvatar config={config} className="mb-5" />}
        <ProfileIdentity config={config} align={align} />
        <ProfileModules config={config} preview={preview} align={align} />
      </div>
    </>
  );
}

function SimplisticCard({ config, preview, align }: { config: ProfileConfig; preview: boolean; align: "left" | "center" | "right" }) {
  return (
    <>
      {config.settings.showAvatar !== false && <ProfileAvatar config={config} className="mb-4 h-20 w-20" />}
      <ProfileIdentity config={config} align={align} />
      <ProfileModules config={config} preview={preview} align={align} />
    </>
  );
}

function SleekCard({ config, preview, align }: { config: ProfileConfig; preview: boolean; align: "left" | "center" | "right" }) {
  return (
    <>
      <div className="relative">
        {config.assets.banner?.url ? <ProfileBanner config={config} /> : <div className="h-28" style={{ background: `linear-gradient(135deg, ${config.settings.accentColor}55, transparent)` }} />}
        {config.settings.showAvatar !== false && <div className="absolute -bottom-8 left-5"><ProfileAvatar config={config} className="mb-0 h-[4.5rem] w-[4.5rem]" /></div>}
      </div>
      <div className="px-5 pb-6 pt-12">
        <ProfileIdentity config={config} align={align} />
        <ProfileModules config={config} preview={preview} align={align} />
      </div>
    </>
  );
}

function ProfileBackground({ config, videoRef, reduceMotion }: { config: ProfileConfig; videoRef: React.RefObject<HTMLVideoElement | null>; reduceMotion: boolean }) {
  const { background, backgroundVideo, backgroundEffectVideo } = config.assets;
  const accent = config.settings.accentColor;
  return (
    <div className="pointer-events-none absolute inset-0 overflow-hidden" style={{ backgroundColor: config.settings.backgroundColor }}>
      <div className="absolute -inset-[10%] animate-background-drift" style={{ opacity: config.settings.backgroundOpacity / 100, backgroundImage: background?.url ? "url(" + background.url + ")" : "radial-gradient(circle at 19% 10%, " + accent + "30, transparent 28%), radial-gradient(circle at 80% 75%, #3c205a70, transparent 32%), linear-gradient(135deg, #090a13, #140d25 48%, #07070a)", backgroundSize: "cover", backgroundPosition: "center" }} />
      {backgroundVideo.url && <video ref={videoRef} className="absolute inset-0 h-full w-full object-cover" style={{ opacity: config.settings.backgroundOpacity / 100 }} src={backgroundVideo.url} autoPlay loop muted={resolvedAudioSource(config.assets) !== "video"} playsInline preload="metadata" />}
      <BackgroundEffectLayer effect={config.settings.backgroundEffect || "None"} className="z-[1]" />
      {config.settings.backgroundEffect === "None" && backgroundEffectVideo?.url ? <video className="absolute inset-0 z-[1] h-full w-full object-cover" src={backgroundEffectVideo.url} autoPlay={!reduceMotion} loop muted playsInline preload="metadata" aria-hidden="true" /> : null}
    </div>
  );
}