import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { TournamentPreviewPage } from "../src/components/tournament-preview";

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

it("shows favorites, streaks, crossings and projected seeds", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: true,
      json: async () => ({
        tournament: {
          name: "Center Stage 2026",
          slug: "center-stage-2026-1",
          url: "https://www.start.gg/tournament/center-stage-2026-1",
          starts_at: "2026-11-14T19:00:00+00:00",
          city: "Asunción",
          venue: null,
          attendees: 76,
        },
        event: { name: "Ultimate Singles", entrants: 3 },
        seeding: { source: "ranking", label: "Proyectados con el Ranking" },
        entrants: [
          { ...wesker, ranked: true, wins: 84, losses: 13, streak: 9 },
          { ...zio, ranked: true, wins: 56, losses: 23, streak: 0 },
          {
            id: null,
            tag: "Chag",
            seed: 3,
            ranked: false,
            startgg_player_id: "70916",
          },
        ],
        favorites: [
          { ...wesker, ranked: true, wins: 84, losses: 13, streak: 9 },
          { ...zio, ranked: true, wins: 56, losses: 23, streak: 0 },
        ],
        on_fire: [{ ...wesker, ranked: true, streak: 9 }],
        crossings: [{ stage: "Final de winners", a: wesker, b: zio, h2h }],
        rivalries: [],
        newcomers: { count: 1, tags: ["Chag"] },
      }),
    })),
  );
  render(<TournamentPreviewPage slug="center-stage-2026-1" />);
  expect(
    await screen.findByRole("heading", { name: "Previa: Center Stage 2026" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/3 inscritos en Ultimate Singles/),
  ).toBeInTheDocument();
  expect(
    screen.getByText("9 sets ganados seguidos, seed 1"),
  ).toBeInTheDocument();
  expect(screen.getByText("Final de winners")).toBeInTheDocument();
  expect(screen.getByText("Wesker 9–3 Zio")).toBeInTheDocument();
  expect(screen.getByText(/Es una proyección del hub/)).toBeInTheDocument();
  // Players without a hub profile are listed without a link.
  expect(screen.queryByRole("link", { name: "Chag" })).not.toBeInTheDocument();
  expect(screen.getByText(/1 inscrito no tiene sets/)).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Ver en start.gg" })).toHaveAttribute(
    "href",
    "https://www.start.gg/tournament/center-stage-2026-1",
  );
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

it("loads start.gg data of an entrant without hub results on demand", async () => {
  const fetchMock = vi.fn(async (url: string) => ({
    ok: true,
    json: async () =>
      url.includes("startgg-players/70916")
        ? {
            player_id: "70916",
            tag: "ISG | Chag",
            country: "MX",
            since: "2025-10-28",
            wins: 291,
            losses: 91,
            tournaments: 60,
            mains: [{ character: "Min Min", games: 9, share: 90 }],
            best: [
              {
                tournament: "Pound Cake",
                url: "https://www.start.gg/tournament/pound-cake",
                entrants: 150,
                placement: 1,
                date: "2026-10-19",
                country: "CO",
              },
            ],
            recent: [],
          }
        : {
            tournament: {
              name: "Center Stage 2026",
              slug: "cs",
              url: "https://www.start.gg/tournament/cs",
              starts_at: null,
              city: null,
              venue: null,
              attendees: 1,
            },
            event: { name: "Ultimate Singles", entrants: 1 },
            seeding: { source: "results", label: "Proyectados" },
            entrants: [
              {
                id: null,
                tag: "Chag",
                seed: 1,
                ranked: false,
                startgg_player_id: "70916",
              },
            ],
            favorites: [],
            on_fire: [],
            crossings: [],
            rivalries: [],
            newcomers: { count: 1, tags: ["Chag"] },
          },
  }));
  vi.stubGlobal("fetch", fetchMock);
  render(<TournamentPreviewPage slug="cs" />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Ver datos de start.gg" }),
  );
  expect(await screen.findByText("291–91")).toBeInTheDocument();
  expect(screen.getByText(/Juega sobre todo en México/)).toBeInTheDocument();
  // Bare dates stay on their day in Asunción.
  expect(screen.getByText(/1\.º de 150 en/)).toHaveTextContent(
    "1.º de 150 en Pound Cake (Colombia), 19 oct. 2026",
  );
  expect(fetchMock).toHaveBeenCalledTimes(2);
});
