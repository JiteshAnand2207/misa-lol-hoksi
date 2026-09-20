import type { BannerShape, ProfileConfig, ProfileFont, ProfileLayout, ProfileShape, SocialAlign } from "./types";
import { fontStack } from "./typography";

export function profileLayout(settings: ProfileConfig["settings"]): ProfileLayout {
  return settings.layout === "Simplistic" || settings.layout === "Sleek" ? settings.layout : "Modern";
}

export function avatarRadius(shape?: ProfileShape) {
  return shape === "square" ? "12px" : shape === "rounded" ? "22px" : "999px";
}

export function bannerRadius(shape?: BannerShape, cardRadius = 24) {
  if (shape === "square") return "0px";
  if (shape === "pill") return "999px";
  return `${Math.max(10, cardRadius - 6)}px`;
}

export function profileFont(font?: ProfileFont) {
  return fontStack(font);
}

export function pageJustify(align?: SocialAlign) {
  return align === "left" ? "flex-start" : align === "right" ? "flex-end" : "center";
}

export function contentAlign(align?: SocialAlign) {
  return align === "left" ? "left" : align === "right" ? "right" : "center";
}

export function formatJoinDate(value?: string) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return `Joined ${date.toLocaleString("en-US", { month: "short", year: "numeric" })}`;
}
