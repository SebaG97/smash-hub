import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import {
  Tournaments,
  TournamentPage,
  EventPage,
  Players,
  PlayerPage,
} from "../src/components/competition-browser";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const tournament = {
  id: "t1",
  name: "Open Paraguay",
  starts_at: null,
  status: "COMPLETED",
  games: ["Ultimate"],
  participant_count: 4,
  entrant_count: 3,
  source: "start.gg",
  location: null,
};
const event = {
  id: "e1",
  tournament_id: "t1",
  name: "Dobles",
  game: "Ultimate",
  team_size: 2,
  entrant_count: 2,
  status: "COMPLETED",
};
const page = (items: unknown[]) => ({
  items,
  total: items.length,
  page: 1,
  page_size: 20,
});
function mock(data: (url: string) => unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => ({ ok: true, json: async () => data(url) })),
  );
}

it("shows tournament dates, game, participants and entrants separately", async () => {
  mock(() => page([tournament]));
  render(<Tournaments />);
  expect(screen.getByRole("status")).toHaveTextContent("Cargando");
  expect(
    await screen.findByRole("link", { name: /Open Paraguay/ }),
  ).toHaveAttribute("href", "/tournaments/t1");
  expect(
    screen.getByText(/4 jugadores, 3 inscripciones en Ultimate/),
  ).toBeInTheDocument();
});
it("shows tournament detail and access to event results", async () => {
  mock((url) => (url.includes("/events?") ? page([event]) : tournament));
  render(<TournamentPage id="t1" />);
  expect(await screen.findByRole("link", { name: /Dobles/ })).toHaveAttribute(
    "href",
    "/events/e1",
  );
  expect(screen.getByText(/Fuente: start.gg/)).toBeInTheDocument();
});
it("shows individual doubles members, placements, pending, DQ and missing scores", async () => {
  mock((url) =>
    url.includes("view=bracket")
      ? page([])
      : url.includes("/entrants?")
        ? page([
            {
              id: "en",
              name: "Equipo A",
              seed: 1,
              placement: 2,
              members: [
                { player_id: "p1", tag: "Ana" },
                { player_id: "p2", tag: "Luis" },
              ],
            },
          ])
        : url.includes("/sets?")
          ? page([
              {
                id: "s1",
                status: "dq",
                round_label: "Final",
                sides: [{ name: "Equipo A", score: null, is_winner: true }],
              },
              { id: "s2", status: "pending", round_label: null, sides: [] },
            ])
          : event,
  );
  render(<EventPage id="e1" />);
  expect(await screen.findByRole("link", { name: "Ana" })).toHaveAttribute(
    "href",
    "/players/p1",
  );
  expect(screen.getByRole("link", { name: "Luis" })).toBeInTheDocument();
  expect(await screen.findByText("Descalificación")).toBeInTheDocument();
  expect(screen.getByText("Pendiente")).toBeInTheDocument();
  expect(screen.getByText(/Sin puntuación/)).toBeInTheDocument();
  expect(screen.getByText(/Placement: 2/)).toBeInTheDocument();
});
it("searches players and encodes user input", async () => {
  mock(() => page([{ id: "p1", tag: "Ana" }]));
  render(<Players />);
  expect(await screen.findByRole("link", { name: /Ana/ })).toBeInTheDocument();
  fireEvent.change(screen.getByRole("searchbox"), { target: { value: "a&b" } });
  await screen.findByRole("link", { name: /Ana/ });
  expect(vi.mocked(fetch).mock.calls.at(-1)?.[0]).toContain("q=a%26b");
});
it("shows known tags and historical competition records", async () => {
  mock(() => ({
    id: "p1",
    tag: "Ana",
    aliases: ["Ana", "Old"],
    history: page([
      {
        tournament_id: "t1",
        tournament_name: "Open Paraguay",
        event_id: "e1",
        event_name: "Dobles",
        tag: "Old",
        entrant_name: "Equipo A",
        placement: null,
      },
    ]),
  }));
  render(<PlayerPage id="p1" />);
  fireEvent.click(await screen.findByRole("tab", { name: "Historial" }));
  expect(screen.getByText("Ana, Old")).toBeInTheDocument();
  expect(screen.getByText(/como Old/)).toBeInTheDocument();
  expect(
    screen.getByRole("link", { name: "Open Paraguay" }),
  ).toBeInTheDocument();
});
it("shows empty state and pagination controls", async () => {
  mock(() => page([]));
  render(<Tournaments />);
  expect(
    await screen.findByText("No hay registros disponibles."),
  ).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled();
});
it("handles errors and retry without exposing internal details", async () => {
  vi.stubGlobal(
    "fetch",
    vi
      .fn()
      .mockRejectedValueOnce(new Error("SECRET"))
      .mockResolvedValue({ ok: true, json: async () => page([]) }),
  );
  render(<Players />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "No se pudieron cargar",
  );
  expect(screen.queryByText("SECRET")).not.toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Reintentar" }));
  expect(
    await screen.findByText("No hay registros disponibles."),
  ).toBeInTheDocument();
});
it("shows a clear missing detail state", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 404 }));
  render(<PlayerPage id="missing" />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "No se encontró este registro.",
  );
});

it("distinguishes BYE, placeholder and conditional reset from pending matches", async () => {
  mock((url) =>
    url.includes("/entrants?")
      ? page([])
      : url.includes("view=bracket")
        ? page([
            {
              id: "empty",
              status: "not_played",
              resolution: "placeholder",
              round_label: "Losers Round 1",
              sides: [],
            },
            {
              id: "reset",
              status: "not_played",
              resolution: "conditional_unused",
              round_label: "Grand Final Reset",
              sides: [],
            },
          ])
        : url.includes("/sets?")
          ? page([
              {
                id: "bye",
                status: "completed",
                resolution: "bye",
                round_label: "Winners Round 1",
                sides: [{ name: "Ana", score: null, is_winner: true }],
              },
              {
                id: "dq",
                status: "completed",
                resolution: "dq",
                round_label: "Final",
                sides: [],
              },
              {
                id: "missing",
                status: "completed",
                resolution: "unresolved",
                round_label: "Final sin score",
                sides: [],
              },
            ])
          : event,
  );
  render(<EventPage id="e1" />);
  expect(
    await screen.findByText("Pase libre · Sin partido jugado"),
  ).toBeInTheDocument();
  expect(
    await screen.findByText("Posición del bracket sin enfrentamiento"),
  ).toBeInTheDocument();
  expect(
    screen.getByText("Reset condicional no utilizado"),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/Excluido de victorias y derrotas jugadas/),
  ).toBeInTheDocument();
  expect(
    screen.getByText(/Final informado sin evidencia suficiente/),
  ).toBeInTheDocument();
  expect(screen.queryByText("Pendiente")).not.toBeInTheDocument();
  expect(screen.getByText(/Ana · Sin puntuación · Avanza/)).toBeInTheDocument();
  expect(
    vi
      .mocked(fetch)
      .mock.calls.some(([url]) =>
        String(url).includes("sets?view=bracket&page=1"),
      ),
  ).toBe(true);
});
