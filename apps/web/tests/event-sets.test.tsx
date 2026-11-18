import React from "react";
import { afterEach, expect, it } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  within,
} from "@testing-library/react";
import {
  SetBrowser,
  roundSections,
  upsetFactor,
} from "../src/components/event-sets";
import { orderEvents } from "../src/components/tournament-events";
import type { Bracket, BracketSet } from "../src/components/bracket";
import type { Event } from "../src/lib/api";

afterEach(cleanup);

function side(tag: string, seed: number, score: number, winner: boolean) {
  return { tag, prefix: null, id: null, seed, score, winner, characters: [] };
}
function set(
  id: string,
  row: number,
  a: [string, number, number],
  b: [string, number, number],
  completed_at: string,
): BracketSet {
  return {
    id,
    round: 1,
    label: null,
    row,
    status: "played",
    completed_at,
    sides: [side(...a, a[2] > b[2]), side(...b, b[2] > a[2])],
    games: [],
  };
}
const bracket: Bracket = {
  projected: false,
  groups: [
    {
      id: "g1",
      name: "Bracket",
      type: "DOUBLE_ELIMINATION",
      height: 4,
      winners: [
        {
          round: 1,
          label: "Winners Round 1",
          sets: [
            set("w1", 0, ["Ace", 1, 2], ["Dot", 4, 0], "2026-11-14T15:00:00Z"),
            // Seed 3 beats seed 2: one bracket tier, an upset.
            set("w2", 1, ["Bee", 2, 1], ["Cid", 3, 2], "2026-11-14T15:10:00Z"),
          ],
        },
        {
          round: 2,
          label: "Grand Final",
          sets: [
            set("gf", 0, ["Ace", 1, 3], ["Cid", 3, 1], "2026-11-14T18:00:00Z"),
          ],
        },
      ],
      losers: [
        {
          round: -1,
          label: "Losers Round 1",
          sets: [
            set("l1", 0, ["Bee", 2, 2], ["Dot", 4, 0], "2026-11-14T16:00:00Z"),
          ],
        },
      ],
    },
  ],
};

it("orders rounds from the final down and marks upsets by bracket tier", () => {
  const sections = roundSections(bracket);
  expect(sections.map((s) => s.title)).toEqual([
    "Grand Final",
    "Losers Round 1",
    "Winners Round 1",
  ]);
  const w2 = sections[2].rows.find((r) => r.set.id === "w2")!;
  expect(w2.upset).toBe(1);
  expect(upsetFactor(sections[0].rows[0].set)).toBe(0);
  // Unreliable seeding: no upsets at all.
  expect(
    roundSections(bracket, false).flatMap((s) => s.rows.map((r) => r.upset)),
  ).toEqual([0, 0, 0, 0]);
});

it("filters by player, side and upsets and opens the games", () => {
  render(<SetBrowser bracket={bracket} />);
  expect(screen.getByRole("status")).toHaveTextContent("4 sets.");
  expect(screen.getByText("Sorpresa")).toBeInTheDocument();

  fireEvent.change(screen.getByPlaceholderText("Buscar por tag"), {
    target: { value: "cid" },
  });
  expect(screen.getByRole("status")).toHaveTextContent("2 de 4 sets.");
  expect(screen.getByRole("status")).toHaveTextContent("Cid fue 1-1");

  fireEvent.change(screen.getByPlaceholderText("Buscar por tag"), {
    target: { value: "" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Losers" }));
  expect(screen.getByRole("status")).toHaveTextContent("1 de 4 sets.");
  fireEvent.click(screen.getByRole("button", { name: "Todo" }));

  fireEvent.click(screen.getByLabelText("Solo sorpresas"));
  expect(screen.getByRole("status")).toHaveTextContent("1 de 4 sets.");
  const row = screen.getByRole("button", { name: /Bee 1, Cid 2/ });
  fireEvent.click(row);
  expect(row).toHaveAttribute("aria-expanded", "true");
  const open = row.closest("li")!;
  expect(
    within(open).getByText(/Cid \(seed 3\) le ganó a Bee/),
  ).toBeInTheDocument();
});

it("puts the main bracket first, singles before teams", () => {
  const e = (id: string, extra: Partial<Event>): Event => ({
    id,
    tournament_id: "t",
    name: id,
    game: "Ultimate",
    team_size: 1,
    entrant_count: 10,
    status: null,
    ...extra,
  });
  expect(
    orderEvents([
      e("dobles", { team_size: 2, entrant_count: 40 }),
      e("amateur", { main: false, entrant_count: 30 }),
      e("singles", { main: true, entrant_count: 20 }),
    ]).map((x) => x.id),
  ).toEqual(["singles", "amateur", "dobles"]);
});
