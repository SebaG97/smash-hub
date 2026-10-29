import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import {
  PlayerAchievements,
  RecordsPage,
  TournamentSummaryBlock,
} from "../src/components/insights";
import { clearAdmin, saveAdmin } from "../src/lib/admin";

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
      month: "2026-10",
      label: "octubre de 2026",
      in_progress: true,
      months: ["2026-09", "2026-10"],
      regions: [
        {
          region: "central",
          name: "Gran Asunción",
          winner: {
            ...wesker,
            points: 85.7,
            results: [
              {
                tournament: "PGP 2026",
                tournament_id: "t1",
                placement: 1,
                entrants: 51,
                seed: 4,
                upsets: 3,
                top10_wins: 2,
                points: 63.2,
              },
            ],
          },
          runners: [{ ...zio, points: 30.1 }],
        },
        { region: "cde", name: "Ciudad del Este", winner: null, runners: [] },
      ],
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
  expect(
    await screen.findByRole("heading", { name: "Jugador del mes" }),
  ).toBeInTheDocument();
  expect(
    screen.getByText(
      "Jugador del mes · Gran Asunción · octubre de 2026 (en curso)",
    ),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/1\.º de 51 en PGP 2026 \(siendo seed 4, 3 sorpresas\)/),
  ).toBeInTheDocument();
  expect(screen.getByText("Le siguen Zio (30,1).")).toBeInTheDocument();
  expect(screen.getByText("Sin torneos este mes.")).toBeInTheDocument();
  expect(
    screen.getByRole("button", { name: "Mes siguiente →" }),
  ).toBeDisabled();
  expect(screen.getByText("+2")).toBeInTheDocument();
  expect(screen.getByText("18 sets")).toBeInTheDocument();
  expect(screen.getByText("26 sets seguidos")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "PGP 2026" })).toHaveAttribute(
    "href",
    "/tournaments/t1",
  );
});

it("summarizes a tournament with its share image for organizers", async () => {
  saveAdmin({ key: "k", name: "Org" });
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
  clearAdmin();
});
