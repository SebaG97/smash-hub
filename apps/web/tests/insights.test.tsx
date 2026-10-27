import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import {
  PlayerAchievements,
  RecordsPage,
  TournamentSummaryBlock,
} from "../src/components/insights";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function mock(data: (url: string) => unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      const body = data(url);
      return body === undefined
        ? { ok: false, status: 404 }
        : { ok: true, json: async () => body };
    }),
  );
}

const wesker = { id: "p1", tag: "Wesker", mains: [] };
const zio = { id: "p2", tag: "Zio", mains: [] };

it("shows badges and personal records on the profile", async () => {
  mock(() => ({
    badges: [
      {
        id: "lider",
        name: "Líder indiscutible",
        why: "Número 1 del ranking.",
      },
      { id: "david", name: "David y Goliat", why: "Le ganó a un seed 1." },
    ],
    records: {
      biggest_upset: {
        opponent_id: "p2",
        opponent: "Zio",
        tournament: "PGP 2026",
        tournament_id: "t1",
        round: "Grand Final",
        factor: 2,
        seed: 4,
        opponent_seed: 1,
        date: "2026-10-11T15:00:00Z",
      },
      best_streak: 26,
      current_streak: 3,
      comebacks: 7,
      titles: 11,
      top8: 20,
      tournaments: 30,
      best_overperformance: null,
      main_rival: { id: "p2", tag: "Zio", sets: 18 },
    },
  }));
  render(<PlayerAchievements id="p1" />);
  expect(await screen.findByText("Líder indiscutible")).toBeInTheDocument();
  expect(screen.getByText("David y Goliat")).toBeInTheDocument();
  expect(screen.getByText("26 sets seguidos")).toBeInTheDocument();
  expect(screen.getByText(/Siendo seed 4 le ganó a/)).toBeInTheDocument();
  expect(screen.getAllByRole("link", { name: "Zio" })[0]).toHaveAttribute(
    "href",
    "/players/p2",
  );
});

it("hides achievements when the player has no data", async () => {
  mock(() => undefined);
  const { container } = render(<PlayerAchievements id="p9" />);
  await vi.waitFor(() =>
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      expect.stringContaining("insights/players/p9"),
      expect.anything(),
    ),
  );
  expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  expect(container).toBeEmptyDOMElement();
});

it("lists community records with the player of the month", async () => {
  mock(() => ({
    player_of_month: {
      ...wesker,
      wins: 22,
      losses: 3,
      upsets: 5,
      titles: 3,
      since: "2026-09-27T00:00:00Z",
      until: "2026-10-27T00:00:00Z",
    },
    streaks: [{ ...wesker, value: 26 }],
    rivalries: [{ a: wesker, b: zio, sets: 18, a_wins: 12, b_wins: 6 }],
    upsets: [
      {
        winner: wesker,
        loser: zio,
        factor: 2,
        winner_seed: 4,
        loser_seed: 1,
        tournament: "PGP 2026",
        tournament_id: "t1",
      },
    ],
    comebacks: [],
    most_active: [],
    titles: [{ ...wesker, value: 11 }],
  }));
  render(<RecordsPage />);
  expect(await screen.findByText("Jugador del mes")).toBeInTheDocument();
  expect(screen.getByText(/22 sets ganados, 5 sorpresas y 3 títulos/));
  expect(screen.getByText("+2")).toBeInTheDocument();
  expect(screen.getByText("18 sets")).toBeInTheDocument();
  expect(screen.getByText("26 sets seguidos")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "PGP 2026" })).toHaveAttribute(
    "href",
    "/tournaments/t1",
  );
});

it("summarizes a tournament with its share image", async () => {
  mock(() => ({
    entrants: 51,
    top: [
      { ...wesker, placement: 1, seed: 4 },
      { ...zio, placement: 2, seed: 1 },
    ],
    upsets: [],
    overperformers: [{ ...wesker, seed: 4, placement: 1 }],
  }));
  render(<TournamentSummaryBlock id="t1" />);
  expect(
    await screen.findByRole("link", { name: "Descargar imagen del top" }),
  ).toHaveAttribute("href", "/og/tournament/t1");
  expect(screen.getByText("seed 4, terminó 1.º")).toBeInTheDocument();
  expect(screen.queryByText("Sorpresas")).not.toBeInTheDocument();
});
