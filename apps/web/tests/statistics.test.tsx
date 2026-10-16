import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import {
  HeadToHeadPage,
  PlayerStatistics,
} from "../src/components/player-statistics";
import { PlayerPage } from "../src/components/competition-browser";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const scopes = [
  { game_id: "game", game_name: "Ultimate", mode: "singles" as const },
];
const page = (items: unknown[]) => ({
  items,
  total: items.length,
  page: 1,
  page_size: 20,
});
const stats = {
  player: { id: "a", tag: "Alpha" },
  sets_played: 3,
  wins: 2,
  losses: 1,
  win_rate: 66.67,
  tournaments_played: 1,
  tournaments_registered: 2,
  best_final_placement: null,
  first_set_at: null,
  last_set_at: null,
  unique_opponents: 1,
};
const match = {
  id: "set",
  tournament_id: "t",
  tournament_name: "Open",
  event_id: "e",
  event_name: "Singles",
  completed_at: null,
  opponents: [{ id: "b", tag: "Beta" }],
  result: "W",
  score: null,
  opponent_score: null,
  round_label: "Final",
  stats_eligible: true,
  source: "start.gg",
  source_url: "https://www.start.gg/tournament/open",
};
function mock(data: (url: string) => unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => ({ ok: true, json: async () => data(url) })),
  );
}

it("integrates API statistics into the existing profile and links comparisons", async () => {
  mock((url) =>
    url.includes("/statistics?")
      ? stats
      : url.includes("/opponents?")
        ? page([
            {
              opponent: { id: "b", tag: "Beta" },
              sets_played: 3,
              wins: 2,
              losses: 1,
              win_rate: 66.67,
              last_encounter_at: null,
            },
          ])
        : url.includes("/matches?")
          ? page([match])
          : {
              id: "a",
              tag: "Alpha",
              aliases: [],
              history: page([]),
              scopes,
            },
  );
  render(<PlayerPage id="a" />);
  expect(
    await screen.findByText("Porcentaje de victorias: 66.67 %"),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/1 torneos disputados · 2 torneos con inscripción/),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Mejor placement final: No disponible"),
  ).toBeInTheDocument();
  expect(
    await screen.findByRole("link", { name: /Ver Head-to-Head/ }),
  ).toHaveAttribute("href", "/players/a/vs/b?game_id=game&mode=singles");
  expect(
    await screen.findByText("Puntuación no disponible · Final"),
  ).toBeInTheDocument();
  expect(
    vi.mocked(fetch).mock.calls.some(([url]) => String(url).includes("&q=")),
  ).toBe(false);
});

it("renders no denominator without inventing a percentage", async () => {
  mock((url) =>
    url.includes("/statistics?")
      ? { ...stats, sets_played: 0, wins: 0, losses: 0, win_rate: null }
      : page([]),
  );
  render(<PlayerStatistics id="a" scopes={scopes} />);
  expect(screen.getAllByRole("status").length).toBeGreaterThan(0);
  expect(
    await screen.findByText("Porcentaje de victorias: No calculable"),
  ).toBeInTheDocument();
  expect(
    screen.getByText("No hay sets elegibles en este ámbito."),
  ).toBeInTheDocument();
});

it("shows absent modality without requesting misleading statistics", () => {
  mock(() => stats);
  render(<PlayerStatistics id="a" scopes={[]} />);
  expect(
    screen.getByText(/No hay una modalidad confirmada/),
  ).toBeInTheDocument();
  expect(fetch).not.toHaveBeenCalled();
});

it("changes game/modality scope and validates the period", async () => {
  mock((url) => (url.includes("/statistics?") ? stats : page([])));
  render(
    <PlayerStatistics
      id="a"
      scopes={[
        ...scopes,
        { game_id: "game", game_name: "Ultimate", mode: "doubles" },
      ]}
    />,
  );
  await screen.findByText(/Porcentaje de victorias/);
  fireEvent.change(screen.getByRole("combobox"), {
    target: { value: "game:doubles" },
  });
  expect(
    await screen.findByText(/Dobles: resultados del equipo/),
  ).toBeInTheDocument();
  expect(
    vi
      .mocked(fetch)
      .mock.calls.some(([url]) => String(url).includes("mode=doubles")),
  ).toBe(true);
  fireEvent.change(screen.getByLabelText("Desde (hora local)"), {
    target: { value: "2026-10-16T15:00" },
  });
  fireEvent.change(screen.getByLabelText("Hasta, exclusivo (hora local)"), {
    target: { value: "2026-10-15T15:00" },
  });
  expect(screen.getByRole("alert")).toHaveTextContent(
    "La fecha inicial debe ser anterior",
  );
});

it("renders a comparison from API totals and paginates history", async () => {
  mock((url) =>
    url.includes("/head-to-head/")
      ? {
          player_a: { id: "a", tag: "Alpha" },
          player_b: { id: "b", tag: "Beta" },
          encounters: 21,
          wins_a: 13,
          wins_b: 8,
          win_rate_a: 61.9,
          win_rate_b: 38.1,
          first_encounter_at: null,
          last_encounter_at: null,
          history: { ...page([match]), total: 21 },
        }
      : { id: "a", scopes },
  );
  render(
    <HeadToHeadPage
      id="a"
      opponentId="b"
      initialGame="game"
      initialMode="singles"
    />,
  );
  expect(
    await screen.findByText(/21 enfrentamientos · Marcador histórico: 13 – 8/),
  ).toBeInTheDocument();
  expect(screen.getByText(/Alpha: 61.9 % · Beta: 38.1 %/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Siguiente" }));
  await screen.findByText("Página 2");
  expect(vi.mocked(fetch).mock.calls.at(-1)?.[0]).toContain("page=2");
});

it("shows players without encounters and null percentages", async () => {
  mock((url) =>
    url.includes("/head-to-head/")
      ? {
          player_a: { id: "a", tag: "Alpha" },
          player_b: { id: "b", tag: "Beta" },
          encounters: 0,
          wins_a: 0,
          wins_b: 0,
          win_rate_a: null,
          win_rate_b: null,
          first_encounter_at: null,
          last_encounter_at: null,
          history: page([]),
        }
      : { id: "a", scopes },
  );
  render(<HeadToHeadPage id="a" opponentId="b" />);
  expect(
    await screen.findByText(/No hay enfrentamientos elegibles/),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/Alpha: No calculable · Beta: No calculable/),
  ).toBeInTheDocument();
});

it("rejects self comparison without making API calls", () => {
  mock(() => ({}));
  render(<HeadToHeadPage id="a" opponentId="a" />);
  expect(screen.getByRole("alert")).toHaveTextContent(
    /no puede enfrentarse a sí mismo/,
  );
  expect(fetch).not.toHaveBeenCalled();
});

it("handles comparison errors and retries", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));
  render(<HeadToHeadPage id="a" opponentId="b" />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "No se encontró este registro.",
  );
  fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
  expect(await screen.findByRole("alert")).toBeInTheDocument();
  expect(fetch).toHaveBeenCalledTimes(2);
});
