"use client";

import { useMemo, useSyncExternalStore } from "react";
import { useMe } from "./session";

/**
 * The organizer behind the admin tools (ADR-021): an account with role admin or
 * superadmin, signed in with its own session cookie. During the transition, the old
 * shared key (ADR-011) can still be typed in /admin; it is kept only in this tab's
 * sessionStorage and the API stops accepting it on ADMIN_TOKEN_EXPIRES.
 */
export type Admin = {
  name: string;
  role: "admin" | "superadmin" | "legacy";
  /** Only for the legacy shared key. */
  key?: string;
};
type LegacyAdmin = { key: string; name: string };

const KEY_STORE = "seeding-admin";
const EVENT = "admin-change";
let cachedRaw: string | null | undefined;
let cachedAdmin: LegacyAdmin | null = null;

/** The legacy shared key typed in this tab, if any. */
export function readAdmin(): LegacyAdmin | null {
  try {
    const raw = sessionStorage.getItem(KEY_STORE);
    // Same object while the stored value is unchanged, as useSyncExternalStore requires.
    if (raw !== cachedRaw) {
      cachedRaw = raw;
      cachedAdmin = raw ? (JSON.parse(raw) as LegacyAdmin) : null;
    }
    return cachedAdmin;
  } catch {
    return null;
  }
}

export function saveAdmin(admin: LegacyAdmin) {
  try {
    sessionStorage.setItem(KEY_STORE, JSON.stringify(admin));
  } catch {
    /* storage blocked: the key lives only until the page closes */
  }
  window.dispatchEvent(new Event(EVENT));
}

export function clearAdmin() {
  try {
    sessionStorage.removeItem(KEY_STORE);
  } catch {
    /* ignore */
  }
  window.dispatchEvent(new Event(EVENT));
}

function subscribe(callback: () => void) {
  window.addEventListener(EVENT, callback);
  window.addEventListener("storage", callback);
  return () => {
    window.removeEventListener(EVENT, callback);
    window.removeEventListener("storage", callback);
  };
}

/** Current organizer, or null for readers (always null while server rendering). */
export function useAdmin(): Admin | null {
  const me = useMe();
  const legacy = useSyncExternalStore(subscribe, readAdmin, () => null);
  const user = me?.user;
  const staff =
    user && (user.role === "admin" || user.role === "superadmin")
      ? user.role
      : null;
  const name = user?.username ?? null;
  return useMemo<Admin | null>(() => {
    if (staff && name) return { name, role: staff };
    if (legacy) return { ...legacy, role: "legacy" };
    return null;
  }, [staff, name, legacy]);
}

/**
 * Headers for an admin request. The session cookie travels with
 * `credentials: "include"`; the shared key, only while one was typed.
 */
export function adminHeaders(admin: Admin | null): Record<string, string> {
  return {
    "X-Requested-With": "smashhub",
    ...(admin?.key
      ? { Authorization: `Bearer ${admin.key}`, "X-Admin-Name": admin.name }
      : {}),
  };
}
