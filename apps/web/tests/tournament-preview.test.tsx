import React from "react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { TournamentPreviewPage } from "../src/components/tournament-preview";

beforeEach(() => window.history.replaceState(null, "", "/"));
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const wesker = { id: "p1", tag: "Wesker", seed: 1 };
const zio = { id: "p2", tag: "Zio", seed: 2 };
const h2h = {
  a_wins: 9,
  b_wins: 3,
  last: {
    tournament: "PGP 2026",
    tournament_id: "t1",
    date: "2026-10-11",
    winner: "Wesker",
  },
};
const chag = {
  id: null,
  tag: "Chag",
  seed: 3,
  ranked: true,
  startgg_player_id: "70916",
  country: "MX",
  mains: [{ character: "Min Min", games: 9, share: 90 }],
  startgg: {
    wins: 40,
    losses: 10,
    events: 12,
    country: "MX",
    last_event: "2026-10-19",
    best: [],
    mains: [{ character: "Min Min", games: 9, share: 90 }],
  },
};
const tournament = {
  name: "Center Stage 2026",
  slug: "center-stage-2026-1",
  url: "https://www.start.gg/tournament/center-stage-2026-1",
  starts_at: "2026-11-14T19:00:00+00:00",
  city: "Asunción",
  venue: null,
  attendees: 76,
  images: {
    profile: "https://images.start.gg/logo.png",
    banner: "https://images.start.gg/banner.png",
  },
};

function preview(extra = {}) {
  return {
    tournament,
    event: { name: "Ultimate Singles", entrants: 3 },
    seeding: { source: "seeding", label: "Seeding oficial publicado (CS)" },
    entrants: [
      {
        ...wesker,
        ranked: true,
        wins: 84,
        losses: 13,
        streak: 9,
        country: "PY",
      },
      { ...zio, ranked: true, wins: 56, losses: 23, streak: 0, country: "PY" },
      chag,
    ],
    favorites: [
      { ...wesker, ranked: true, wins: 84, losses: 13, streak: 9 },
      { ...zio, ranked: true, wins: 56, losses: 23, streak: 0 },
      chag,
    ],
    on_fire: [{ ...wesker, ranked: true, streak: 9 }],
    crossings: [{ stage: "Final de winners", a: wesker, b: zio, h2h }],
    rivalries: [],
    newcomers: { count: 1, tags: ["Chag"] },
    ...extra,
  };
}

const pools = {
  phase: "Pools",
  pools: [
    {
      id: "g1",
      name: "Pool A1",
      players: [
        {
          seed: 1,
          pool_seed: 1,
          player_id: "1",
          id: "p1",
          tag: "Wesker",
          prefix: null,
          mains: [],
          country: "PY",
        },
      ],
    },
    {
      id: "g2",
      name: "Pool A2",
      players: [
        {
          seed: 3,
          pool_seed: 1,
          player_id: "70916",
          id: null,
          tag: "Chag",
          prefix: "ISG",
          mains: [],
          country: "MX",
        },
      ],
    },
  ],
};

function serve(body: unknown) {
  const fetchMock = vi.fn(async (url: string) => ({
    ok: true,
    json: async () => (url.endsWith("/pools") ? pools : body),
  }));
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

it("opens on a summary with favorites, streaks and crossings", async () => {
  serve(preview());
  render(<TournamentPreviewPage slug="center-stage-2026-1" />);
  expect(
    await screen.findByRole("heading", { name: "Previa: Center Stage 2026" }),
  ).toBeInTheDocument();
  expect(screen.getByText("inscritos")).toHaveTextContent("3 inscritos");
  expect(screen.getByText("países")).toHaveTextContent("2 países");
  expect(screen.getByText("de afuera")).toHaveTextContent("1 de afuera");
  expect(
    screen.getByText("9 sets ganados seguidos, seed 1"),
  ).toBeInTheDocument();
  expect(screen.getByText("Final de winners")).toBeInTheDocument();
  expect(screen.getByText("Wesker 9–3 Zio")).toBeInTheDocument();
  // A favorite without hub results shows the seeding's start.gg record.
  expect(screen.getByTitle(/Sets de start.gg/)).toHaveTextContent(
    "40–10 start.gg",
  );
  expect(screen.getByRole("img", { name: "México" })).toBeInTheDocument();
  // No list of "players without hub results" anymore.
  expect(screen.queryByText(/Sin resultados en el hub/)).toBeNull();
  // start.gg banner on top; the logo only shows when there is no banner.
  expect(
    screen.getByRole("img", { name: "Banner de Center Stage 2026" }),
  ).toHaveAttribute("src", "https://images.start.gg/banner.png");
  expect(document.querySelector(".tournament-logo")).toBeNull();
  expect(screen.getByRole("link", { name: "Ver en start.gg" })).toHaveAttribute(
    "href",
    "https://www.start.gg/tournament/center-stage-2026-1",
  );
  expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual([
    "Resumen",
    "Pools",
    "Seeds",
  ]);
});

it("explains a missing tournament", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: false, status: 404 })),
  );
  render(<TournamentPreviewPage slug="nada" />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "No se encontró este registro.",
  );
});

it("pages the seeds and searches them", async () => {
  const many = Array.from({ length: 70 }, (_, i) => ({
    id: `h${i + 1}`,
    tag: i === 49 ? "José" : `Player ${i + 1}`,
    seed: i + 1,
    ranked: true,
    wins: 1,
    losses: 1,
  }));
  serve(preview({ entrants: many, event: { name: "Singles", entrants: 70 } }));
  render(<TournamentPreviewPage slug="cs" />);
  fireEvent.click(await screen.findByRole("tab", { name: "Seeds" }));
  expect(window.location.hash).toBe("#seeds");
  expect(screen.getAllByRole("row")).toHaveLength(33); // header + 32
  expect(screen.getByRole("link", { name: "Player 1" })).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "33–64" }));
  expect(screen.getByRole("link", { name: "Player 33" })).toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Player 1" })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Siguiente →" }));
  expect(screen.getAllByRole("row")).toHaveLength(7); // header + 6
  // Searching ignores accents and starts again on the first page.
  fireEvent.change(screen.getByRole("searchbox", { name: "Buscar jugador" }), {
    target: { value: "jose" },
  });
  expect(screen.getAllByRole("row")).toHaveLength(2);
  expect(screen.getByRole("link", { name: "José" })).toBeInTheDocument();
  expect(
    screen.queryByRole("navigation", { name: "Páginas de seeds" }),
  ).toBeNull();
});

it("shows the official seeding in start.gg's pools", async () => {
  const fetchMock = serve(preview());
  render(<TournamentPreviewPage slug="cs" />);
  fireEvent.click(await screen.findByRole("tab", { name: "Pools" }));
  expect(
    await screen.findByRole("region", { name: "Pool A1" }),
  ).toBeInTheDocument();
  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("insights/upcoming/cs/pools"),
    expect.anything(),
  );
  fireEvent.change(screen.getByRole("searchbox", { name: "Buscar jugador" }), {
    target: { value: "isg" },
  });
  // Only pools with a match stay, and the match is marked.
  expect(screen.queryByRole("region", { name: "Pool A1" })).toBeNull();
  expect(screen.getByText("Chag").closest("li")).toHaveClass("match");
});

it("without the official seeding shows entrants but no seeds or pools", async () => {
  serve(
    preview({
      seeding: {
        source: "none",
        label: "Todavía no hay un seeding oficial publicado",
      },
      entrants: [{ ...wesker, seed: null, ranked: false, wins: 3, losses: 1 }],
      favorites: [],
      crossings: [],
      event: { name: "Singles", entrants: 1 },
    }),
  );
  render(<TournamentPreviewPage slug="cs" />);
  expect(
    await screen.findByText(/aparecen cuando se publique/),
  ).toBeInTheDocument();
  expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual([
    "Resumen",
    "Inscritos",
  ]);
  fireEvent.click(screen.getByRole("tab", { name: "Inscritos" }));
  expect(screen.queryByRole("columnheader", { name: "Seed" })).toBeNull();
  expect(screen.getByRole("link", { name: "Wesker" })).toBeInTheDocument();
});
