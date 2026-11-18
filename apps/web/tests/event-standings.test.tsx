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
  StandingsView,
  type StandingRow,
  type Standings,
} from "../src/components/event-standings";

afterEach(cleanup);

function row(
  name: string,
  placement: number | null,
  seed: number,
  extra: Partial<StandingRow> = {},
): StandingRow {
  return {
    id: name,
    name,
    seed,
    placement,
    prefix: null,
    members: [{ player_id: `p-${name}`, tag: name }],
    wins: 2,
    losses: 1,
    games_won: 5,
    games_lost: 3,
    performance: 0,
    upsets: 0,
    eliminated_by: null,
    best_win: null,
    characters: [],
    ...extra,
  };
}

const data: Standings = {
  event: { id: "e", name: "Singles", entrants: 5, team_size: 1 },
  reliable: true,
  sets: 9,
  entrants: [
    row("Cid", 1, 4, {
      performance: 3,
      upsets: 2,
      losses: 0,
      best_win: {
        name: "Ace",
        player_id: "p-Ace",
        seed: 1,
        score: "2–1",
        round: "Winners Final",
      },
    }),
    row("Ace", 2, 1, {
      eliminated_by: {
        name: "Cid",
        player_id: "p-Cid",
        seed: 4,
        score: "3–2",
        round: "Grand Final",
      },
    }),
    row("Bee", 3, 2, { performance: -1 }),
    row("Dot", 4, 3),
    row("Eve", 5, 5),
    row("Fox", 5, 6),
  ],
};

it("shows the podium, groups tied places and tells who knocked each one out", () => {
  render(<StandingsView data={data} />);
  const podium = screen.getByRole("list", { name: "Podio" });
  expect(
    within(podium)
      .getAllByRole("link")
      .map((a) => a.textContent),
  ).toEqual(["Ace", "Cid", "Bee"]);
  expect(screen.getByText("Campeón invicto")).toBeInTheDocument();
  expect(screen.getByText("2 sorpresas")).toBeInTheDocument();
  expect(screen.getByText(/Grand Final/)).toBeInTheDocument();
  expect(
    screen.getByRole("region", { name: "5.º puesto" }),
  ).toBeInTheDocument();
  expect(screen.getByTitle(/3 escalones arriba/)).toHaveTextContent("▲3");
  expect(screen.getByTitle(/1 escalón abajo/)).toHaveTextContent("▼1");
  expect(screen.getByRole("status")).toHaveTextContent("6 jugadores · 9 sets");
});

it("filters by tag and by players who beat their seed", () => {
  render(<StandingsView data={data} />);
  fireEvent.change(screen.getByLabelText("Buscar"), {
    target: { value: "fo" },
  });
  expect(screen.getByRole("status")).toHaveTextContent("1 de 6 jugadores");
  expect(screen.queryByRole("list", { name: "Podio" })).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Buscar"), { target: { value: "" } });
  fireEvent.click(screen.getByRole("button", { name: "Superaron su seed" }));
  expect(screen.getByRole("status")).toHaveTextContent("1 de 6 jugadores");
  expect(screen.getByRole("link", { name: "Cid" })).toBeInTheDocument();
});
