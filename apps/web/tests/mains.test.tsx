import React from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import { PlayerPage, Players } from "../src/components/competition-browser";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const mains = [
  { character: "Incineroar", games: 31, share: 62.4 },
  { character: "Cloud", games: 12, share: 24 },
];

describe("player mains", () => {
  it("lists players with their main characters", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(
            JSON.stringify({
              items: [{ id: "p1", tag: "Wesker", mains }],
              total: 1,
              page: 1,
              page_size: 20,
            }),
          ),
        ),
      ),
    );
    render(<Players />);
    expect(
      await screen.findByText("Main: Incineroar (62 %) · Cloud (24 %)"),
    ).toBeInTheDocument();
  });

  it("shows mains with share and games on the player page", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        Promise.resolve(
          new Response(
            JSON.stringify(
              url.includes("/statistics") || url.includes("/matches")
                ? {}
                : {
                    id: "p1",
                    tag: "Wesker",
                    mains,
                    aliases: [],
                    scopes: [],
                    history: { items: [], total: 0, page: 1, page_size: 20 },
                  },
            ),
          ),
        ),
      ),
    );
    render(<PlayerPage id="p1" />);
    expect(
      await screen.findByRole("heading", { name: "Mains" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Incineroar")).toBeInTheDocument();
    expect(screen.getByText("62 % · 31 partidas")).toBeInTheDocument();
  });
});
