import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { PoolBoard, type Pools } from "../src/components/pool-board";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});

const player = (seed: number, tag: string, extra = {}) => ({
  seed,
  pool_seed: 1,
  player_id: String(seed * 10),
  tag,
  prefix: null,
  mains: [],
  rating: 1500,
  ranking: null,
  startgg_seed: seed,
  ...extra,
});

const pools: Pools = {
  phase: "Pools (BO3)",
  pools: [
    {
      id: "a",
      name: "Pool 1",
      players: [player(1, "Chag"), player(4, "Zio", { startgg_seed: 5 })],
      top20: 2,
      rating: 1600,
    },
    {
      id: "b",
      name: "Pool 2",
      players: [player(2, "Bros"), player(3, "Wesker")],
      top20: 1,
      rating: 1550,
    },
  ],
  outside: [],
  warnings: [
    {
      kind: "team",
      seeds: [1, 4],
      text: "Compañeros de equipo en primera ronda: Chag (seed 1) y Zio (seed 4).",
    },
  ],
  missing: ["Nuevo"],
  startgg_seeded: true,
};

it("shows each pool and swaps two players on two taps", async () => {
  sessionStorage.setItem(
    "seeding-admin",
    JSON.stringify({ key: "secret-key", name: "Org" }),
  );
  const calls: { url: string; init?: RequestInit }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn((url: string, init?: RequestInit) => {
      calls.push({ url, init });
      const body = init?.method === "POST" ? { status: "swapped" } : pools;
      return Promise.resolve(new Response(JSON.stringify(body)));
    }),
  );
  const onChange = vi.fn();
  render(<PoolBoard slug="cs" onChange={onChange} />);
  fireEvent.click(screen.getByRole("button", { name: "Ver por pools" }));
  expect(
    await screen.findByRole("region", { name: "Pool 1" }),
  ).toHaveTextContent("2 del top 20 · rating medio 1600");
  expect(screen.getByText(/Compañeros de equipo/)).toBeInTheDocument();
  expect(screen.getByText("start.gg 5")).toBeInTheDocument();
  expect(screen.getByText(/1 inscriptos de start.gg/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Zio, seed 4" }));
  expect(screen.getByText(/Elegiste a/)).toBeInTheDocument();
  fireEvent.click(screen.getByRole("button", { name: "Wesker, seed 3" }));
  await vi.waitFor(() => expect(onChange).toHaveBeenCalled());
  const swap = calls.find((c) => c.init?.method === "POST")!;
  expect(swap.url).toMatch(/\/seeding\/cs\/pools\/swap$/);
  expect(JSON.parse(String(swap.init?.body))).toEqual({ a: "40", b: "30" });
});

it("is hidden from readers", () => {
  const { container } = render(<PoolBoard slug="cs" />);
  expect(container).toBeEmptyDOMElement();
});
