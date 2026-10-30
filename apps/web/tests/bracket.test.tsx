import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import {
  BracketPreview,
  BracketView,
  EventBracket,
  type Bracket,
  type BracketSide,
} from "../src/components/bracket";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function side(tag: string, seed: number, extra: Partial<BracketSide> = {}) {
  return {
    tag,
    prefix: null,
    id: `p-${tag}`,
    seed,
    score: null,
    winner: false,
    characters: [],
    ...extra,
  };
}

const ken = { name: "Ken", icon: null };
const pit = { name: "Dark Pit", icon: null };

const bracket: Bracket = {
  projected: false,
  groups: [
    {
      id: "71",
      name: "Bracket",
      type: "DOUBLE_ELIMINATION",
      height: 1,
      winners: [
        {
          round: 1,
          label: "Winners ronda 1",
          sets: [
            {
              id: "s1",
              round: 1,
              label: "Winners Round 1",
              row: 0,
              to: null,
              status: "dq",
              completed_at: null,
              sides: [side("Lucas", 9, { winner: true }), side("Arthur", 24)],
              games: [],
            },
          ],
        },
      ],
      losers: [],
    },
    {
      id: "72",
      name: "Top 8",
      type: "DOUBLE_ELIMINATION",
      height: 1,
      winners: [
        {
          round: 3,
          label: "Gran final",
          sets: [
            {
              id: "gf",
              round: 3,
              label: "Grand Final",
              row: 0,
              to: null,
              status: "played",
              completed_at: "2026-07-19T17:04:57+00:00",
              sides: [
                side("Wesker", 2, {
                  prefix: "BG",
                  score: 3,
                  winner: true,
                  characters: [ken],
                }),
                side("Zio", 1, { prefix: "BG", score: 2, characters: [pit] }),
              ],
              games: [
                { number: 1, winner: 2, characters: [ken, pit] },
                { number: 2, winner: 1, characters: [ken, pit] },
              ],
            },
          ],
        },
      ],
      losers: [],
    },
  ],
};

it("opens on the final phase and shows a set game by game", () => {
  render(<BracketView bracket={bracket} />);
  expect(screen.getByRole("tab", { name: "Top 8" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  expect(screen.getByText("Gran final")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Wesker contra Zio" }));
  const detail = screen.getByRole("region", { name: "Detalle del set" });
  expect(detail).toHaveTextContent("Partida 1");
  expect(detail).toHaveTextContent("gana Zio");
  expect(detail).toHaveTextContent("gana Wesker");
  expect(screen.getByRole("link", { name: /Wesker/ })).toHaveAttribute(
    "href",
    "/players/p-Wesker",
  );
});

it("switches phases and marks disqualifications", () => {
  render(<BracketView bracket={bracket} />);
  fireEvent.click(screen.getByRole("tab", { name: "Bracket" }));
  expect(screen.getByText("DQ")).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Lucas contra Arthur" }));
  expect(screen.getByText(/No se cargaron los personajes/)).toBeInTheDocument();
});

it("loads the bracket of an event", async () => {
  const fetch = vi.fn((url: string) =>
    Promise.resolve(new Response(JSON.stringify(url && bracket))),
  );
  vi.stubGlobal("fetch", fetch);
  render(<EventBracket eventId="e1" />);
  expect(
    await screen.findByRole("heading", { name: "Bracket" }),
  ).toBeInTheDocument();
  expect(String(fetch.mock.calls[0][0])).toMatch(/\/events\/e1\/bracket$/);
});

it("shows projected sets as a guess", () => {
  const projected: Bracket = {
    projected: true,
    groups: [
      {
        ...bracket.groups[1],
        winners: [
          { ...bracket.groups[1].winners[0], round: 1 },
          {
            round: 2,
            label: "Final de winners",
            sets: [{ ...bracket.groups[1].winners[0].sets[0], id: "w2" }],
          },
        ],
      },
    ],
  };
  render(<BracketView bracket={projected} />);
  const cards = screen.getAllByRole("button", { name: "Wesker contra Zio" });
  expect(cards[0]).not.toHaveClass("guess");
  expect(cards[1]).toHaveClass("guess");
});

it("lets organizers see start.gg's pools with an unpublished seeding", async () => {
  sessionStorage.setItem(
    "seeding-admin",
    JSON.stringify({ key: "secret-key", name: "Org" }),
  );
  const pools: Bracket = {
    projected: true,
    source: "startgg",
    later: ["TOP 32 (BO5)", "TOP 8 (BO5)"],
    groups: [
      { ...bracket.groups[1], id: "p1", name: "Pools (BO3) · 1" },
      { ...bracket.groups[1], id: "p2", name: "Pools (BO3) · 2" },
    ],
  };
  const fetch = vi.fn((url: string, init?: RequestInit) =>
    Promise.resolve(new Response(JSON.stringify(url && init && pools))),
  );
  vi.stubGlobal("fetch", fetch);
  render(<BracketPreview slug="cs" />);
  fireEvent.click(screen.getByRole("button", { name: "Ver bracket" }));
  expect(
    await screen.findByRole("tab", { name: "Pools (BO3) · 1" }),
  ).toHaveAttribute("aria-selected", "true");
  expect(screen.getByText(/Después siguen: TOP 32/)).toBeInTheDocument();
  const [url, init] = fetch.mock.calls[0];
  expect(url).toMatch(/\/seeding\/cs\/bracket$/);
  expect((init?.headers as Record<string, string>).Authorization).toBe(
    "Bearer secret-key",
  );
  sessionStorage.clear();
});
