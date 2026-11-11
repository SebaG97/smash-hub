"use client";

import { useEffect, useSyncExternalStore } from "react";

/**
 * Smash Hub accounts (ADR-021). The session lives in an HttpOnly cookie the page never
 * reads; nothing about it is kept in localStorage or sessionStorage.
 */

const api = (process.env.NEXT_PUBLIC_API_URL || "/api/v1").replace(/\/$/, "");

export type Role = "user" | "admin" | "superadmin";
export type SessionUser = {
  id: string;
  username: string;
  display_name: string;
  name: string;
  role: Role;
  email: string | null;
  player: { id: string; tag: string } | null;
};
export type Me = {
  user: SessionUser | null;
  legacy_admin_key: boolean;
};

const SIGNED_OUT: Me = {
  user: null,
  legacy_admin_key: false,
};

let current: Me | null = null;
let loading = false;
const listeners = new Set<() => void>();

function publish(next: Me) {
  setMe(next);
}

/** Set who is signed in (null: unknown, so the next reader asks the API). */
export function setMe(next: Me | null) {
  current = next;
  listeners.forEach((l) => l());
}

export function refreshMe() {
  if (loading) return;
  loading = true;
  fetch(`${api}/auth/me`, { credentials: "include" })
    .then((r) => (r.ok ? (r.json() as Promise<Me>) : null))
    .then((me) => publish(me ?? SIGNED_OUT))
    .catch(() => publish(SIGNED_OUT))
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

export function isStaff(user: SessionUser | null | undefined) {
  return user?.role === "admin" || user?.role === "superadmin";
}

/** Only paths of this site after signing in: never another host. */
export function safeNext(value: string | null | undefined) {
  if (
    !value ||
    !value.startsWith("/") ||
    value.startsWith("//") ||
    value.includes("\\") ||
    value.length > 300
  )
    return "/";
  return value;
}

/** The sign-in page, coming back to `next` (this page by default). */
export function signInHref(next?: string) {
  const back =
    next ??
    (typeof window === "undefined"
      ? "/"
      : `${window.location.pathname}${window.location.search}${window.location.hash}`);
  return `/ingresar?next=${encodeURIComponent(safeNext(back))}`;
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

/** The API's explanation of a failed request, in Spanish. */
export async function errorText(r: Response) {
  try {
    const body = (await r.json()) as { detail?: unknown };
    if (typeof body.detail === "string") return body.detail;
    if (Array.isArray(body.detail))
      return "Revisá los datos: hay un campo con un formato no válido.";
  } catch {
    /* non-JSON error */
  }
  return `La API respondió ${r.status}.`;
}

async function signedIn(r: Response): Promise<string | null> {
  if (!r.ok) return errorText(r);
  publish((await r.json()) as Me);
  return null;
}

/** Sign in; returns the problem to show, or null when it worked. */
export async function login(loginName: string, password: string) {
  const r = await apiFetch("auth/login", {
    method: "POST",
    body: JSON.stringify({ login: loginName, password }),
  }).catch(() => null);
  return r ? signedIn(r) : "No se pudo contactar a la API.";
}

export async function register(fields: {
  username: string;
  email: string;
  password: string;
  display_name?: string;
}) {
  const r = await apiFetch("auth/register", {
    method: "POST",
    body: JSON.stringify(fields),
  }).catch(() => null);
  return r ? signedIn(r) : "No se pudo contactar a la API.";
}

export async function logout() {
  await apiFetch("auth/logout", { method: "POST" }).catch(() => null);
  publish({ ...(current ?? SIGNED_OUT), user: null });
}
