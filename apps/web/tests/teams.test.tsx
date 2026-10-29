import React from "react";
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { TeamsPage } from "../src/components/teams";
import { Prefix } from "../src/components/prefix";
import { clearAdmin, saveAdmin } from "../src/lib/admin";

afterEach(() => {
  cleanup();
  clearAdmin();
  vi.unstubAllGlobals();
});

const teams = {
  items: [
    {
      key: "bg",
      name: "BG",
      titles: 12,
      top8: 29,
      ranked: 2,
      members: [
        { id: "p1", tag: "Wesker", ranking: 1, wins: 84, losses: 13 },
        { id: "p2", tag: "Zio", ranking: 2, wins: 56, losses: 23 },
      ],
      results: [],
    },
  ],
};

it("shows a prefix only when there is one", () => {
  const { container } = render(<Prefix prefix={null} />);
  expect(container).toBeEmptyDOMElement();
  render(<Prefix prefix="BG" />);
  expect(screen.getByText("BG")).toHaveClass("tag-prefix");
});

it("lists teams with their members and hides the review from readers", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, json: async () => teams })),
  );
  render(<TeamsPage />);
  expect(await screen.findByRole("link", { name: "BG" })).toHaveAttribute(
    "href",
    "/equipos/bg",
  );
  expect(
    screen.getByText(/2 jugadores · 12 títulos · 29 top 8/),
  ).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Wesker" })).toBeInTheDocument();
  expect(screen.queryByText(/Prefijos \(solo organizadores\)/)).toBeNull();
});

it("lets organizers approve, join or hide prefixes", async () => {
  saveAdmin({ key: "k", name: "Org" });
  const review = {
    tournaments_to_read: 0,
    items: [
      {
        key: "g0",
        example: "G0",
        players: 2,
        last_seen: null,
        status: null,
        name: null,
        team: null,
      },
      {
        key: "go",
        example: "GO",
        players: 9,
        last_seen: null,
        status: "team",
        name: "GO",
        team: null,
      },
    ],
  };
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => ({
    ok: true,
    json: async () =>
      url.endsWith("/teams")
        ? { items: [] }
        : init?.method === "PUT"
          ? {}
          : review,
  }));
  vi.stubGlobal("fetch", fetchMock);
  render(<TeamsPage />);
  const choice = await screen.findByLabelText("Decisión para G0");
  expect(screen.getByText("sin revisar")).toBeInTheDocument();
  fireEvent.change(choice, { target: { value: "alias" } });
  await vi.waitFor(() =>
    expect(
      fetchMock.mock.calls.some(([, init]) => init?.method === "PUT"),
    ).toBe(true),
  );
  const [url, init] = fetchMock.mock.calls.find(
    ([, i]) => i?.method === "PUT",
  ) as [string, RequestInit];
  expect(url).toMatch(/\/prefixes\/g0$/);
  expect(JSON.parse(String(init.body))).toEqual({
    status: "alias",
    name: "G0",
    team: "go",
  });
});
