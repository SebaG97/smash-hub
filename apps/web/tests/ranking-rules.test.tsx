import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { SeedingBoard, requirements } from "../src/components/seeding-board";
import type { PublicSeedingView } from "../src/lib/api";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("explains the entry rule in words", () => {
  expect(requirements({ min_sets: 0, min_events: 2, active_days: 183 })).toBe(
    "Para entrar hace falta al menos 2 torneos presenciales en el período, uno de ellos en los últimos 6 meses.",
  );
  expect(requirements({ min_sets: 10 })).toBe(
    "Para entrar hace falta al menos 10 sets.",
  );
  expect(requirements({ min_sets: 0 })).toBe("");
});

it("shows readers who is about to enter and who is inactive", async () => {
  const view: PublicSeedingView = {
    slug: "rk",
    name: "Ranking Paraguay 2026",
    kind: "ranking",
    country_code: "PY",
    published: true,
    public: true,
    method: "combined",
    method_label: "Combinado",
    startgg_event_slug: null,
    event_date: "2026-11-14T03:00:00Z",
    window_start: "2025-11-14T03:00:00Z",
    data_cutoff: "2026-10-27T00:00:00Z",
    run: {
      window_start: "2025-11-14T03:00:00Z",
      window_end: "2026-10-27T00:00:00Z",
      set_count: 1358,
      event_count: 31,
      parameters: { min_sets: 0, min_events: 2, active_days: 183 },
    },
    seeds: [{ seed: 1, gamer_tag: "Wesker", wins: 79, losses: 13 }],
    pending: [
      {
        gamer_tag: "SpikeCC",
        wins: 7,
        losses: 0,
        events: 1,
        last_event: "2026-06-20",
      },
    ],
    inactive: [
      {
        gamer_tag: "Lucifero",
        prefix: "MGK",
        wins: 25,
        losses: 16,
        events: 4,
        last_event: "2026-03-21",
      },
    ],
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(() => Promise.resolve(new Response(JSON.stringify(view)))),
  );
  render(<SeedingBoard slug="rk" base="rankings" />);
  expect(
    await screen.findByText(/uno de ellos en los últimos 6 meses\. Cuentan 31/),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "Por entrar" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText("7–0 en 1 torneo; le falta 1 torneo"),
  ).toBeInTheDocument();
  expect(
    screen.getByRole("heading", { name: "Inactivos" }),
  ).toBeInTheDocument();
  expect(screen.getByText("MGK")).toHaveClass("tag-prefix");
  expect(screen.getByText(/25–16; último torneo el/)).toBeInTheDocument();
});
