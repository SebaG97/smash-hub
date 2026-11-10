import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { ProdeTab, type Contest } from "../src/components/prode";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.resetModules();
});

const candidates = Array.from({ length: 10 }, (_, i) => ({
  startgg_player_id: String(i + 1),
  tag: `P${i + 1}`,
  prefix: null,
  seed: i + 1,
  id: null,
  withdrawn: i === 9,
}));

function contest(extra: Partial<Contest> = {}): Contest {
  return {
    id: "c1",
    tournament_slug: "cs",
    name: "Center Stage",
    event_name: "Ultimate Singles",
    status: "open",
    locks_at: "2026-11-14T19:00:00+00:00",
    settled_at: null,
    rules: { champion: 10, runner_up: 7, top8: 2 },
    participants: 3,
    candidates,
    mine: { champion: null, runner_up: null, top8: [] },
    results: {},
    ranking: [],
    ...extra,
  };
}

function serve(user: object | null, body: Contest) {
  const calls: { url: string; init?: RequestInit }[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      if (url.endsWith("/auth/me"))
        return {
          ok: true,
          status: 200,
          json: async () => ({ enabled: true, user }),
        };
      const sent = init?.body ? JSON.parse(String(init.body)) : null;
      return {
        ok: true,
        status: 200,
        json: async () => (sent ? { ...body, mine: sent } : body),
      };
    }),
  );
  return calls;
}

it("asks to sign in with start.gg before playing", async () => {
  serve(null, contest());
  const { ProdeTab: Tab } = await import("../src/components/prode");
  render(<Tab slug="cs" />);
  const login = await screen.findByRole("link", {
    name: "Ingresar con start.gg",
  });
  expect(login.getAttribute("href")).toContain("/auth/startgg/login?next=");
  expect(screen.getByText(/cierra el/)).toBeInTheDocument();
});

it("saves champion, runner-up and a top 8 with the hub's header", async () => {
  const calls = serve({ id: "u1", name: "vBash" }, contest());
  const { ProdeTab: Tab } = await import("../src/components/prode");
  render(<Tab slug="cs" />);
  const [champion, runnerUp] = await screen.findAllByRole("combobox");
  fireEvent.change(champion, { target: { value: "7" } });
  fireEvent.change(runnerUp, { target: { value: "1" } });
  // A withdrawn entrant cannot be picked.
  expect(screen.queryByRole("button", { name: "10 · P10" })).toBeNull();
  for (const n of [1, 2, 3, 4, 5, 6, 7, 8])
    fireEvent.click(screen.getByRole("button", { name: `${n} · P${n}` }));
  expect(screen.getByRole("button", { name: "9 · P9" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Guardar pronóstico" }));
  expect(await screen.findByText(/Guardado/)).toBeInTheDocument();
  const put = calls.find((c) => c.init?.method === "PUT")!;
  expect(put.url).toMatch(/prode\/contests\/c1\/picks$/);
  expect(put.init?.credentials).toBe("include");
  expect(
    (put.init?.headers as Record<string, string>)["X-Requested-With"],
  ).toBe("smashhub");
  expect(JSON.parse(String(put.init?.body))).toEqual({
    champion: "7",
    runner_up: "1",
    top8: ["1", "2", "3", "4", "5", "6", "7", "8"],
  });
});

it("shows results, my hits and the ranking once settled", async () => {
  serve(
    { id: "u1", name: "vBash" },
    contest({
      status: "settled",
      mine: { champion: "7", runner_up: "2", top8: ["1"] },
      results: { champion: ["7"], runner_up: ["1"], top8: ["1", "7"] },
      ranking: [
        {
          rank: 1,
          user_id: "u1",
          name: "vBash",
          points: 12,
          exact_hits: 1,
          hits: 2,
          picks: { champion: "7" },
        },
      ],
    }),
  );
  const { ProdeTab: Tab } = await import("../src/components/prode");
  render(<Tab slug="cs" />);
  expect(await screen.findByText("Campeón: P7")).toHaveAttribute(
    "data-result",
    "hit",
  );
  expect(screen.getByText("Subcampeón: P2")).toHaveAttribute(
    "data-result",
    "miss",
  );
  expect(screen.getByRole("link", { name: "vBash" })).toHaveAttribute(
    "href",
    "/prode/u/u1",
  );
});

it("lets organizers open a Prode when there is none", async () => {
  sessionStorage.setItem(
    "seeding-admin",
    JSON.stringify({ key: "k".repeat(32), name: "Org" }),
  );
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) =>
      url.endsWith("/auth/me")
        ? {
            ok: true,
            status: 200,
            json: async () => ({ enabled: true, user: null }),
          }
        : { ok: false, status: 404, json: async () => ({}) },
    ),
  );
  render(<ProdeTab slug="cs" />);
  expect(
    await screen.findByRole("button", { name: "Abrir Prode" }),
  ).toBeInTheDocument();
  sessionStorage.clear();
});
