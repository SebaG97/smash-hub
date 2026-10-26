import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { SeedingBoard } from "../src/components/seeding-board";
import type { SeedingRow, SeedingView } from "../src/lib/api";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

function row(seed: number, tag: string, extra: Partial<SeedingRow> = {}) {
  return {
    seed,
    seed_algorithm: seed,
    player_id: String(seed),
    gamer_tag: tag,
    rating: 1800 - seed,
    rd: 60,
    conservative: 1680 - seed,
    placement_score: 4.5,
    best_placements: [],
    wins: 10,
    losses: 2,
    sets: 12,
    offline_sets: 12,
    events: 4,
    offline_events: 4,
    last_event: "2026-10-11",
    main_circuit: "PY",
    circuits: { PY: 12 },
    confidence: "alta",
    combined: 0.9,
    rank_conservative: seed,
    rank_placement: seed,
    merged_sets: 0,
    flags: [],
    reasons: [`Razón de ${tag}`],
    override: null,
    ...extra,
  } satisfies SeedingRow;
}

const view: SeedingView = {
  slug: "cs",
  name: "Center Stage",
  startgg_event_slug: "tournament/cs/event/singles",
  event_date: "2026-11-14T03:00:00Z",
  window_start: "2025-11-14T03:00:00Z",
  data_cutoff: "2026-10-21T19:58:48Z",
  refresh: { status: "IDLE", started_at: null, progress: null, error: null },
  dataset: {
    entrants: 2,
    sets: 30,
    counted_sets: 20,
    events: 5,
    offline_events: 4,
    classifications: { played: 20, bye: 10 },
  },
  merges: [],
  duplicates: [],
  run: {
    id: "r",
    created_at: "2026-10-26T15:00:00Z",
    actor: "cli",
    algorithm_version: "v1",
    parameters: { conservative_k: 2, rating_weight: 0.5 },
    window_start: "2025-11-14T03:00:00Z",
    window_end: "2026-11-14T03:00:00Z",
    data_cutoff: "2026-10-21T19:58:48Z",
    set_count: 20,
    event_count: 5,
    offline_event_count: 4,
    player_count: 9,
  },
  seeds: [
    row(1, "Ace"),
    row(2, "Bee", {
      seed_algorithm: 1,
      override: {
        player_id: "2",
        seed: 2,
        reason: "Conocido local",
        actor: "Org",
        updated_at: null,
      },
    }),
  ],
};

describe("seeding board", () => {
  it("shows data window, explanations and manual adjustments", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => Promise.resolve(new Response(JSON.stringify(view)))),
    );
    render(<SeedingBoard slug="cs" />);
    expect(
      await screen.findByRole("heading", { name: "Center Stage" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/14\/11\/2025 al 14\/11\/2026/),
    ).toBeInTheDocument();
    expect(screen.getByText(/\(método 1\)/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Exportar CSV" })).toHaveAttribute(
      "href",
      expect.stringContaining("/seeding/cs/export.csv"),
    );
    fireEvent.click(screen.getByRole("button", { name: "Bee" }));
    expect(screen.getByText("Razón de Bee")).toBeInTheDocument();
    expect(screen.getByText(/Conocido local/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Subir a/ })).toBeNull();
  });

  it("logs in with the admin key and moves a player", async () => {
    const calls: { url: string; init?: RequestInit }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string, init?: RequestInit) => {
        calls.push({ url, init });
        if (url.endsWith("/session"))
          return Promise.resolve(
            new Response(JSON.stringify({ actor: "Org" })),
          );
        if (init?.method === "PUT")
          return Promise.resolve(
            new Response(JSON.stringify({ status: "moved" })),
          );
        return Promise.resolve(new Response(JSON.stringify(view)));
      }),
    );
    render(<SeedingBoard slug="cs" />);
    await screen.findByRole("heading", { name: "Center Stage" });
    fireEvent.change(screen.getByLabelText("Tu nombre"), {
      target: { value: "Org" },
    });
    fireEvent.change(screen.getByLabelText("Clave de administración"), {
      target: { value: "secret-key" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Entrar" }));
    const down = await screen.findByRole("button", { name: "Bajar a Ace" });
    fireEvent.click(down);
    await waitFor(() =>
      expect(calls.some((c) => c.init?.method === "PUT")).toBe(true),
    );
    const put = calls.find((c) => c.init?.method === "PUT")!;
    expect(put.url).toContain("/seeding/cs/overrides/1");
    expect(JSON.parse(String(put.init?.body))).toMatchObject({ seed: 2 });
    expect((put.init?.headers as Record<string, string>).Authorization).toBe(
      "Bearer secret-key",
    );
  });
});
