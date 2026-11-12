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

/** The public origin: the configured one when valid, the club's domain otherwise. */
export function publicOrigin(
  configured: string | undefined = process.env.NEXT_PUBLIC_SITE_URL,
) {
  return validPublicOrigin(configured) ?? DEFAULT_PUBLIC_ORIGIN;
}

/** Public install page for the QR: never carries user data. */
export function installUrl(
  configured: string | undefined = process.env.NEXT_PUBLIC_SITE_URL,
) {
  return `${publicOrigin(configured)}/install`;
}

/**
 * Android link that asks the system to open `url` in Chrome, for browsers embedded in
 * other apps. If Chrome is missing, Android falls back to the same https address.
 */
export function openInChromeUrl(url: string) {
  const { host, pathname } = new URL(url);
  return `intent://${host}${pathname}#Intent;scheme=https;package=com.android.chrome;S.browser_fallback_url=${encodeURIComponent(url)};end`;
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

/**
 * Browsers inside other apps cannot install sites: WhatsApp, Instagram, Facebook,
 * TikTok, the Google app (what some QR readers open) and any Android WebView (`; wv)`).
 */
export function isInAppBrowser(userAgent: string) {
  return /FBAN|FBAV|FB_IAB|Instagram|WhatsApp|Line\/|TikTok|musical_ly|Twitter|Snapchat|GSA\/|; wv\)/i.test(
    userAgent,
  );
}

export type Browser =
  "chrome" | "edge" | "samsung" | "firefox" | "safari" | "inapp" | "other";

export function detectBrowser(userAgent: string, maxTouchPoints = 0): Browser {
  if (isInAppBrowser(userAgent)) return "inapp";
  if (/SamsungBrowser/i.test(userAgent)) return "samsung";
  if (/Edg(A|iOS)?\//i.test(userAgent)) return "edge";
  if (/Firefox|FxiOS/i.test(userAgent)) return "firefox";
  if (/OPR\/|Opera|YaBrowser|UCBrowser|DuckDuckGo/i.test(userAgent))
    return "other";
  if (/Chrome\/|CriOS/i.test(userAgent)) return "chrome";
  if (isIosSafari(userAgent, maxTouchPoints) || /Safari/i.test(userAgent))
    return "safari";
  return "other";
}

/**
 * Browsers that can show their own install dialog (`beforeinstallprompt`): Chromium on
 * Android and computers. Never on iPhone, where every browser is Safari underneath.
 */
export function offersInstallDialog(userAgent: string, maxTouchPoints = 0) {
  if (detectPlatform(userAgent, maxTouchPoints) === "ios") return false;
  const browser = detectBrowser(userAgent, maxTouchPoints);
  return browser === "chrome" || browser === "edge" || browser === "samsung";
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
