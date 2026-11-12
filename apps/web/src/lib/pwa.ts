"use client";

import { useSyncExternalStore } from "react";
import { EARLY_PROMPT_KEY, isStandalone } from "./install";

/**
 * Installable app (SH-PWA-01), browser side: the install offer and the hooks. Pure
 * helpers live in ./install so the server layout can use them too.
 */

/** Chromium's install event, not yet in the DOM typings. */
export type BeforeInstallPromptEvent = Event & {
  prompt(): Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed"; platform: string }>;
};

export type InstallState = {
  /** The browser offered installation and the offer has not been used. */
  prompt: BeforeInstallPromptEvent | null;
  /** The browser fired `appinstalled`: the only proof the app was installed. */
  installed: boolean;
};

const INITIAL: InstallState = { prompt: null, installed: false };
let state: InstallState = INITIAL;
const listeners = new Set<() => void>();

function update(next: Partial<InstallState>) {
  state = { ...state, ...next };
  listeners.forEach((l) => l());
}

/** Back to the start; tests only. */
export function resetInstallState() {
  state = INITIAL;
  listeners.forEach((l) => l());
}

/** Listen for install events for the whole app; returns the cleanup. */
export function startInstallListener(win: Window = window) {
  const early = (win as unknown as Record<string, unknown>)[EARLY_PROMPT_KEY];
  if (early) {
    update({ prompt: early as BeforeInstallPromptEvent });
    delete (win as unknown as Record<string, unknown>)[EARLY_PROMPT_KEY];
  }
  const onPrompt = (event: Event) => {
    // Keep the offer for our own button instead of the browser's banner.
    event.preventDefault();
    update({ prompt: event as BeforeInstallPromptEvent });
  };
  const onInstalled = () => update({ prompt: null, installed: true });
  win.addEventListener("beforeinstallprompt", onPrompt);
  win.addEventListener("appinstalled", onInstalled);
  return () => {
    win.removeEventListener("beforeinstallprompt", onPrompt);
    win.removeEventListener("appinstalled", onInstalled);
  };
}

/**
 * Show the browser's install dialog. "accepted" only means the person agreed: the app
 * counts as installed when `appinstalled` arrives.
 */
export async function promptInstall(): Promise<
  "accepted" | "dismissed" | "unavailable"
> {
  const offer = state.prompt;
  if (!offer) return "unavailable";
  // An offer can be shown only once; the browser sends a new one if it allows it.
  update({ prompt: null });
  try {
    await offer.prompt();
    return (await offer.userChoice).outcome;
  } catch {
    return "unavailable";
  }
}

export function useInstallState() {
  return useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => state,
    () => INITIAL,
  );
}

const STANDALONE_QUERY = "(display-mode: standalone)";

/** Running as the installed app; false on the server and until hydration. */
export function useStandalone() {
  return useSyncExternalStore(
    (listener) => {
      if (typeof window.matchMedia !== "function") return () => {};
      const query = window.matchMedia(STANDALONE_QUERY);
      query.addEventListener?.("change", listener);
      return () => query.removeEventListener?.("change", listener);
    },
    () => isStandalone(),
    () => false,
  );
}

const noSubscription = () => () => {};

/**
 * A fact about this browser read from its user agent; null on the server and until
 * hydration, so server and client render the same first frame.
 */
export function useDevice<T extends string | boolean>(
  read: (userAgent: string, maxTouchPoints: number) => T,
): T | null {
  return useSyncExternalStore(
    noSubscription,
    () => read(navigator.userAgent, navigator.maxTouchPoints),
    () => null,
  );
}
