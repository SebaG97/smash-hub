"use client";

import { useSyncExternalStore } from "react";

/** Organizer session: the shared admin key, kept only in this browser tab (ADR-011). */
export type Admin = { key: string; name: string };

const KEY_STORE = "seeding-admin";
const EVENT = "admin-change";
let cachedRaw: string | null | undefined;
let cachedAdmin: Admin | null = null;

export function readAdmin(): Admin | null {
  try {
    const raw = sessionStorage.getItem(KEY_STORE);
    // Same object while the stored value is unchanged, as useSyncExternalStore requires.
    if (raw !== cachedRaw) {
      cachedRaw = raw;
      cachedAdmin = raw ? (JSON.parse(raw) as Admin) : null;
    }
    return cachedAdmin;
  } catch {
    return null;
  }
}

export function saveAdmin(admin: Admin) {
  try {
    sessionStorage.setItem(KEY_STORE, JSON.stringify(admin));
  } catch {
    /* storage blocked: the session ends with the page */
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
  return useSyncExternalStore(subscribe, readAdmin, () => null);
}

export function adminHeaders(admin: Admin | null): Record<string, string> {
  return admin
    ? { Authorization: `Bearer ${admin.key}`, "X-Admin-Name": admin.name }
    : {};
}
