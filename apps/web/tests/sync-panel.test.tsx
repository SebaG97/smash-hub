import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import {
  SyncPanel,
  summary,
  type SyncStatus,
} from "../src/components/sync-panel";
import { setMe } from "../src/lib/session";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  setMe(null);
});

const STATUS: SyncStatus = {
  enabled: true,
  tournaments: [
    {
      slug: "center-stage-2026",
      name: "Center Stage 2026",
      starts_at: "2026-11-17T13:00:00+00:00",
      tracked: true,
      reason: "calendar",
      in_calendar: true,
      tier: "week",
      next_sync_at: "2026-11-12T15:30:00+00:00",
      last_attempt_at: "2026-11-12T15:05:00+00:00",
      last_success_at: "2026-11-12T15:00:00+00:00",
      last_status: "failed",
      last_error: "startgg_rate_limited",
      failures: 2,
    },
  ],
  runs: [
    {
      id: "r1",
      kind: "tournament",
      slug: "center-stage-2026",
      trigger: "manual",
      actor: "org",
      status: "completed",
      started_at: "2026-11-12T15:00:00+00:00",
      finished_at: "2026-11-12T15:01:00+00:00",
      counts: { entrants_created: 12, entrants_retired: 1 },
      warnings: [],
      error: null,
    },
  ],
};

type Call = { url: string; init?: RequestInit };

function serve() {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      const body =
        init?.method === "GET"
          ? STATUS
          : { status: "started", run_id: "r2", slug: "x" };
      return new Response(JSON.stringify(body), {
        status: init?.method === "GET" ? 200 : 202,
      });
    }),
  );
  return calls;
}

function signInAsAdmin() {
  setMe({
    user: {
      id: "u1",
      username: "org",
      display_name: "Org",
      name: "Org",
      role: "admin",
      email: null,
      player: null,
    },
    legacy_admin_key: false,
  });
}

describe("start.gg sync panel", () => {
  it("is hidden from readers", () => {
    const calls = serve();
    setMe({ user: null, legacy_admin_key: false });
    const { container } = render(<SyncPanel />);
    expect(container).toBeEmptyDOMElement();
    expect(calls).toHaveLength(0);
  });

  it("shows each tournament's last sync, failures and next sync", async () => {
    serve();
    signInAsAdmin();
    render(<SyncPanel />);
    expect(await screen.findByText("Center Stage 2026")).toBeInTheDocument();
    expect(screen.getByText("Esta semana")).toBeInTheDocument();
    expect(screen.getByText(/está encendida/)).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(
      "startgg_rate_limited (2 seguidas)",
    );
    expect(
      screen.getByText(/entrants created: 12, entrants retired: 1/),
    ).toBeInTheDocument();
  });

  it("syncs a pasted link right away", async () => {
    const calls = serve();
    signInAsAdmin();
    render(<SyncPanel />);
    await screen.findByText("Center Stage 2026");
    fireEvent.change(screen.getByLabelText("Link del torneo"), {
      target: { value: " https://www.start.gg/tournament/otro " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Sincronizar ahora" }));
    await vi.waitFor(() =>
      expect(calls.some((c) => c.init?.method === "POST")).toBe(true),
    );
    const post = calls.find((c) => c.init?.method === "POST")!;
    expect(post.url).toMatch(/\/sync\/tournaments$/);
    expect(post.init?.credentials).toBe("include");
    expect(JSON.parse(String(post.init?.body))).toEqual({
      tournament: "https://www.start.gg/tournament/otro",
    });
  });

  it("summarizes only what changed", () => {
    expect(summary({ entrants_created: 0, calendar: 3 })).toBe("sin cambios");
    expect(summary({ seeds_updated: 2 })).toBe("seeds updated: 2");
  });
});
