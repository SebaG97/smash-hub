import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ProdeTab, type Contest } from "../src/components/prode";
import { SyncPanel, type SyncStatus } from "../src/components/sync-panel";
import { setMe } from "../src/lib/session";

// SH-FIX-01: organizers type Paraguay's wall-clock time; the API converts it.

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
  setMe(null);
});

type Call = { url: string; init?: RequestInit };

function serve(answer: (url: string, init?: RequestInit) => unknown) {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      return {
        ok: true,
        status: 200,
        json: async () => answer(url, init),
      };
    }),
  );
  return calls;
}

function legacyAdmin() {
  sessionStorage.setItem(
    "seeding-admin",
    JSON.stringify({ key: "k".repeat(32), name: "Org" }),
  );
}

const STATUS: SyncStatus = {
  enabled: true,
  tournaments: [
    {
      slug: "center-stage-2026-1",
      name: "Center Stage 2026",
      starts_at: "2026-11-14T17:00:00+00:00",
      startgg_starts_at: "2026-11-14T19:00:00+00:00",
      start_confirmed: true,
      start_confirmed_by: "org",
      tracked: true,
      reason: "calendar",
      in_calendar: true,
      tier: "week",
      next_sync_at: null,
      last_attempt_at: null,
      last_success_at: null,
      last_status: "completed",
      last_error: null,
      failures: 0,
    },
  ],
  runs: [],
};

it("shows the confirmed start next to start.gg's and confirms a new one", async () => {
  legacyAdmin();
  setMe({ user: null, legacy_admin_key: true });
  const calls = serve((url, init) =>
    init?.method === "PUT" ? { confirmed: true } : STATUS,
  );
  render(<SyncPanel />);
  // 17:00 UTC is 14:00 in Asunción; start.gg's 19:00 UTC is 16:00 (24 h or 12 h clock,
  // depending on the runtime's es-PY data).
  const start = await screen.findByText(/^Inicio /);
  expect(start.textContent).toMatch(
    /^Inicio 14\/11, (14:00|02:00 p\.\s?m\.) \(confirmado; start\.gg dice 14\/11, (16:00|04:00 p\.\s?m\.)\)$/,
  );
  fireEvent.change(screen.getByLabelText("Torneo"), {
    target: { value: "center-stage-2026-1" },
  });
  fireEvent.change(screen.getByLabelText("Día"), {
    target: { value: "2026-11-14" },
  });
  fireEvent.change(screen.getByLabelText("Hora de Paraguay"), {
    target: { value: "14:00" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Confirmar inicio" }));
  await vi.waitFor(() =>
    expect(calls.some((c) => c.init?.method === "PUT")).toBe(true),
  );
  const put = calls.find((c) => c.init?.method === "PUT")!;
  expect(put.url).toMatch(/\/sync\/tournaments\/center-stage-2026-1\/start$/);
  expect(JSON.parse(String(put.init?.body))).toEqual({
    starts_at: "2026-11-14T14:00",
  });
});

it("lets organizers move an open Prode's close in Paraguay's time", async () => {
  legacyAdmin();
  const open: Contest = {
    id: "c1",
    tournament_slug: "cs",
    name: "Center Stage",
    event_name: "Ultimate Singles",
    status: "open",
    locks_at: "2026-11-14T19:00:00+00:00",
    settled_at: null,
    rules: { champion: 10, runner_up: 7, top8: 2 },
    participants: 6,
    candidates: [],
    mine: { champion: null, runner_up: null, top8: [] },
    results: {},
    ranking: [],
  };
  const calls = serve((url) =>
    url.endsWith("/auth/me") ? { user: null, legacy_admin_key: true } : open,
  );
  render(<ProdeTab slug="cs" />);
  fireEvent.change(await screen.findByLabelText("Día del cierre"), {
    target: { value: "2026-11-14" },
  });
  fireEvent.change(screen.getByLabelText("Hora de Paraguay"), {
    target: { value: "14:00" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Cambiar cierre" }));
  await vi.waitFor(() =>
    expect(calls.some((c) => c.url.endsWith("/locks-at"))).toBe(true),
  );
  const post = calls.find((c) => c.url.endsWith("/locks-at"))!;
  expect(post.url).toMatch(/prode\/contests\/c1\/locks-at$/);
  expect(post.init?.method).toBe("POST");
  expect(JSON.parse(String(post.init?.body))).toEqual({
    locks_at: "2026-11-14T14:00",
  });
});
