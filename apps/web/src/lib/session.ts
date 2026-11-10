"use client";

import { useEffect, useSyncExternalStore } from "react";

/** Prode sign-in with start.gg (ADR-020): the session lives in an HttpOnly cookie. */

const api = (process.env.NEXT_PUBLIC_API_URL || "/api/v1").replace(/\/$/, "");

export type SessionUser = {
  id: string;
  name: string;
  slug: string | null;
  startgg_player_id: string | null;
};
export type Me = { enabled: boolean; user: SessionUser | null };

let current: Me | null = null;
let loading = false;
const listeners = new Set<() => void>();

function publish(next: Me) {
  current = next;
  listeners.forEach((l) => l());
}

export function refreshMe() {
  if (loading) return;
  loading = true;
  fetch(`${api}/auth/me`, { credentials: "include" })
    .then((r) => (r.ok ? (r.json() as Promise<Me>) : null))
    .then((me) => publish(me ?? { enabled: false, user: null }))
    .catch(() => publish({ enabled: false, user: null }))
    .finally(() => {
      loading = false;
    });
}

/** Who is signed in; null while the first answer is on its way. */
export function useMe(): Me | null {
  const me = useSyncExternalStore(
    (listener) => {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
    () => current,
    () => null,
  );
  useEffect(() => {
    if (current === null) refreshMe();
  }, []);
  return me;
}

/** start.gg's sign-in page, coming back to `next` (this page by default). */
export function loginUrl(next?: string) {
  const back =
    next ??
    `${window.location.pathname}${window.location.search}${window.location.hash}`;
  return `${api}/auth/startgg/login?next=${encodeURIComponent(back)}`;
}

/** API call with the session cookie and the header that proves it comes from the hub. */
export function apiFetch(path: string, init: RequestInit = {}) {
  return fetch(`${api}/${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "X-Requested-With": "smashhub",
      ...(init.body ? { "Content-Type": "application/json" } : {}),
      ...(init.headers ?? {}),
    },
  });
}

export async function logout() {
  await apiFetch("auth/logout", { method: "POST" }).catch(() => null);
  publish({ enabled: current?.enabled ?? true, user: null });
}
