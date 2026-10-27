import React from "react";
import { afterEach, describe, it, expect, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import Home from "../src/app/page";
import { BackendStatus } from "../src/components/backend-status";
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
describe("public foundation", () => {
  it("opens with the published ranking and recent tournaments", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) => {
        const body = url.endsWith("/seeding?kind=ranking")
          ? [{ slug: "rk" }]
          : url.endsWith("/seeding/rk")
            ? {
                slug: "rk",
                name: "Ranking Paraguay",
                method_label: "Combinado",
                seeds: [{ seed: 1, gamer_tag: "Wesker", wins: 84, losses: 13 }],
              }
            : url.includes("/tournaments")
              ? {
                  items: [
                    {
                      id: "t1",
                      name: "PGP 2026",
                      starts_at: "2026-10-11T15:00:00Z",
                      participant_count: 51,
                    },
                  ],
                  total: 1,
                  page: 1,
                  page_size: 6,
                }
              : { status: "ready" };
        return Promise.resolve(new Response(JSON.stringify(body)));
      }),
    );
    render(<Home />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent(
      "Smash Club Paraguay",
    );
    expect(
      await screen.findByRole("heading", { name: "Ranking Paraguay" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Wesker" })).toHaveAttribute(
      "href",
      "/rankings/rk",
    );
    expect(
      await screen.findByRole("link", { name: "PGP 2026" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Ver ranking completo" }),
    ).toBeInTheDocument();
  });
  it("reports readiness", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => ({ status: "ready" }),
      }),
    );
    render(<BackendStatus />);
    expect(await screen.findByText("Backend disponible")).toBeInTheDocument();
  });
  it("handles connection errors without exposing details", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("secret")));
    render(<BackendStatus />);
    expect(
      await screen.findByText("Backend no disponible"),
    ).toBeInTheDocument();
    expect(screen.queryByText("secret")).not.toBeInTheDocument();
  });
});
