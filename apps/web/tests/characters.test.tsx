import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { CharactersPage, PlayerMatchups } from "../src/components/characters";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function mock(body: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => body })),
  );
}

it("lists the scene's characters with their top players and filters them", async () => {
  mock({
    games: 3647,
    items: [
      {
        character: "Incineroar",
        games: 411,
        share: 5.6,
        win_rate: 53,
        players: 15,
        top_players: [{ id: "p1", tag: "Spike", games: 184, win_rate: 56.5 }],
      },
      {
        character: "Pikachu",
        games: 271,
        share: 3.7,
        win_rate: 46.5,
        players: 8,
        top_players: [],
      },
    ],
  });
  render(<CharactersPage />);
  expect(
    await screen.findByText("3.647 partidas con 2 personajes distintos."),
  ).toBeInTheDocument();
  expect(screen.getByText("Incineroar")).toBeInTheDocument();
  expect(screen.getByText("53 % de victorias")).toBeInTheDocument();
  expect(screen.getByRole("link", { name: /Spike/ })).toHaveAttribute(
    "href",
    "/players/p1",
  );
  fireEvent.change(screen.getByRole("searchbox"), {
    target: { value: "pika" },
  });
  expect(screen.queryByText("Incineroar")).not.toBeInTheDocument();
  expect(screen.getByText("Pikachu")).toBeInTheDocument();
  fireEvent.change(screen.getByRole("searchbox"), {
    target: { value: "zzz" },
  });
  expect(screen.getByText("Ningún personaje coincide.")).toBeInTheDocument();
});

it("shows a player's best and worst matchups", async () => {
  mock({
    items: [
      { character: "Cloud", games: 40, wins: 25, win_rate: 62.5 },
      { character: "Incineroar", games: 18, wins: 15, win_rate: 83.3 },
      { character: "Roy", games: 14, wins: 4, win_rate: 28.6 },
      // Too few games to be highlighted.
      { character: "Wolf", games: 2, wins: 0, win_rate: 0 },
    ],
  });
  render(<PlayerMatchups id="p1" />);
  const summary = await screen.findByText(/Le va mejor contra/);
  expect(summary).toHaveTextContent(
    "Le va mejor contra Incineroar (83,3 % en 18 partidas) y peor contra Roy (28,6 % en 14).",
  );
  expect(screen.getByText("Wolf")).toBeInTheDocument();
  expect(screen.getByText("25–15")).toBeInTheDocument();
});

it("hides matchups when there are no games", async () => {
  mock({ items: [] });
  const { container } = render(<PlayerMatchups id="p1" />);
  await vi.waitFor(() => expect(fetch).toHaveBeenCalled());
  expect(container).toBeEmptyDOMElement();
});
