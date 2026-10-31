import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import {
  LiveNotice,
  LivePage,
  type LiveTournament,
} from "../src/components/live";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const side = (tag: string, seed: number, score: number | null = null) => ({
  tag,
  prefix: null,
  id: null,
  seed,
  score,
  winner: false,
  characters: [],
});

const running = {
  id: "s1",
  round: 1,
  label: "Winners Round 1",
  row: 0,
  to: null,
  status: "live",
  completed_at: null,
  sides: [side("Zio", 1, 1), side("Wesker", 2, 1)],
  games: [],
};

const live: LiveTournament = {
  tournament: {
    name: "SaN's 11",
    slug: "sans-11",
    url: "https://www.start.gg/tournament/sans-11",
    starts_at: "2026-11-20T22:00:00Z",
    city: "Ciudad del Este",
  },
  events: [
    { id: "1", name: "Singles", entrants: 16 },
    { id: "2", name: "Amateur", entrants: 9 },
  ],
  event: { id: "1", name: "Singles", entrants: 16 },
  final: false,
  top: [
    {
      placement: 1,
      tag: "Zio",
      prefix: "BG",
      id: "p1",
      seed: 1,
      mains: [],
    },
  ],
  projected: false,
  groups: [
    {
      id: "g1",
      name: "Pools · 1",
      type: "DOUBLE_ELIMINATION",
      height: 1,
      winners: [{ round: 1, label: "Winners ronda 1", sets: [] }],
      losers: [],
    },
    {
      id: "g2",
      name: "Pools · 2",
      type: "DOUBLE_ELIMINATION",
      height: 1,
      winners: [{ round: 1, label: "Winners ronda 1", sets: [running] }],
      losers: [],
    },
  ],
  current: "g2",
  updated_at: "2026-11-20T23:15:00Z",
};

function respond(body: unknown, status = 200) {
  vi.stubGlobal(
    "fetch",
    vi.fn(() =>
      Promise.resolve(new Response(JSON.stringify(body), { status })),
    ),
  );
}

it("opens on the group being played and marks sets in progress", async () => {
  respond(live);
  render(<LivePage slug="sans-11" />);
  expect(await screen.findByRole("tab", { name: "Pools · 2" })).toHaveAttribute(
    "aria-selected",
    "true",
  );
  expect(screen.getByRole("button", { name: "Zio contra Wesker" })).toHaveClass(
    "live",
  );
  expect(screen.getByText("Posiciones hasta ahora")).toBeInTheDocument();
  expect(screen.getByRole("tab", { name: /Amateur/ })).toBeInTheDocument();
});

it("offers organizers the top, flagged until grand finals end", async () => {
  sessionStorage.setItem(
    "seeding-admin",
    JSON.stringify({ key: "secret-key", name: "Org" }),
  );
  respond(live);
  const { unmount } = render(<LivePage slug="sans-11" />);
  expect(
    await screen.findByRole("link", { name: /top parcial/ }),
  ).toHaveAttribute("href", "/og/en-vivo/sans-11");
  unmount();
  respond({ ...live, final: true });
  render(<LivePage slug="sans-11" />);
  expect(
    await screen.findByRole("link", { name: "Descargar imagen del top" }),
  ).toBeInTheDocument();
  expect(screen.getByText("Terminó")).toBeInTheDocument();
});

it("hides the top image from readers", async () => {
  respond(live);
  render(<LivePage slug="sans-11" />);
  await screen.findByText("Posiciones hasta ahora");
  expect(screen.queryByRole("link", { name: /top parcial/ })).toBeNull();
});

it("says so when the tournament is not live", async () => {
  respond({ detail: "no" }, 404);
  render(<LivePage slug="nada" />);
  expect(await screen.findByRole("alert")).toHaveTextContent(
    "Este torneo no está en vivo.",
  );
});

it("shows a notice on the home page only while something is on", async () => {
  respond({
    items: [{ name: "SaN's 11", slug: "sans-11", active: true }],
  });
  const { unmount } = render(<LiveNotice />);
  expect(await screen.findByRole("link")).toHaveAttribute(
    "href",
    "/en-vivo/sans-11",
  );
  expect(screen.getByText("En vivo")).toBeInTheDocument();
  unmount();
  respond({ items: [] });
  const { container } = render(<LiveNotice />);
  await new Promise((r) => setTimeout(r, 0));
  expect(container).toBeEmptyDOMElement();
});
