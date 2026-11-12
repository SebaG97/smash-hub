/**
 * Installable app (SH-PWA-01): pure helpers shared by the server layout and the client.
 * Installing only adds the site to the home screen: no token, cookie or storage entry.
 */

/** Where the QR and shared links point when no public origin is configured. */
export const DEFAULT_PUBLIC_ORIGIN = "https://smashclubpy.com";

const LOCAL_HOSTS = new Set(["localhost", "127.0.0.1", "[::1]"]);

/**
 * The configured public origin, or null when it is not a bare https origin (http only on
 * localhost). Paths, queries, fragments and credentials are refused, so a misconfigured
 * value can never send a scanned QR somewhere unexpected.
 */
export function validPublicOrigin(value: string | null | undefined) {
  if (!value) return null;
  let url: URL;
  try {
    url = new URL(value.trim());
  } catch {
    return null;
  }
  const secure =
    url.protocol === "https:" ||
    (url.protocol === "http:" && LOCAL_HOSTS.has(url.hostname));
  if (
    !secure ||
    url.username ||
    url.password ||
    url.search ||
    url.hash ||
    (url.pathname !== "/" && url.pathname !== "")
  )
    return null;
  return url.origin;
}

/** Public install page for the QR: never carries user data. */
export function installUrl(
  configured: string | undefined = process.env.NEXT_PUBLIC_SITE_URL,
) {
  return `${validPublicOrigin(configured) ?? DEFAULT_PUBLIC_ORIGIN}/install`;
}

export type Platform = "ios" | "android" | "desktop";

export function detectPlatform(
  userAgent: string,
  maxTouchPoints = 0,
): Platform {
  if (/iPhone|iPad|iPod/i.test(userAgent)) return "ios";
  // iPadOS 13+ presents itself as a Mac; only the touch screen tells them apart.
  if (/Macintosh/i.test(userAgent) && maxTouchPoints > 1) return "ios";
  if (/Android/i.test(userAgent)) return "android";
  return "desktop";
}

/** Browsers inside other apps (Instagram, Facebook, TikTok…) cannot install sites. */
export function isInAppBrowser(userAgent: string) {
  return /FBAN|FBAV|Instagram|Line\/|TikTok|musical_ly|Twitter/i.test(
    userAgent,
  );
}

/** On iPhone only Safari is sure to offer «Agregar a pantalla de inicio». */
export function isIosSafari(userAgent: string, maxTouchPoints = 0) {
  return (
    detectPlatform(userAgent, maxTouchPoints) === "ios" &&
    /Safari/i.test(userAgent) &&
    !/CriOS|FxiOS|EdgiOS|OPiOS|GSA\/|YaBrowser|DuckDuckGo/i.test(userAgent) &&
    !isInAppBrowser(userAgent)
  );
}

type Win = Pick<Window, "matchMedia" | "navigator">;

/** True when running as the installed app, not inside a browser tab. */
export function isStandalone(win: Win | undefined = globalThis.window) {
  if (!win) return false;
  if ((win.navigator as { standalone?: boolean }).standalone === true)
    return true;
  if (typeof win.matchMedia !== "function") return false;
  return ["standalone", "fullscreen", "minimal-ui"].some(
    (mode) => win.matchMedia(`(display-mode: ${mode})`).matches,
  );
}

/** Name of the global where the inline head script keeps an event fired before React. */
export const EARLY_PROMPT_KEY = "__smashInstallPrompt";

/**
 * Inline script for <head>: Chromium can fire `beforeinstallprompt` before the app
 * hydrates, and the event is not repeated, so it is caught as early as possible.
 */
export const EARLY_PROMPT_SCRIPT = `window.addEventListener("beforeinstallprompt",function(e){e.preventDefault();window.${EARLY_PROMPT_KEY}=e;});`;
